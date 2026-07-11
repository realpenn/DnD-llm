from __future__ import annotations

import hashlib
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dnd_llm.config import Settings
from dnd_llm.content.campaign_pack import (
    CampaignPackDefinition,
    CampaignPackLoader,
    CampaignPackValidator,
    campaign_id_validation_error,
)
from dnd_llm.content.runtime import apply_campaign_pack, register_campaign_pack_events
from dnd_llm.core.compendium.loader import Compendium, CompendiumLoader
from dnd_llm.core.compendium.schema_loader import SchemaRegistry
from dnd_llm.core.compendium.validators import RuleDataValidator
from dnd_llm.core.models import Character, GameState
from dnd_llm.core.persistence import AuditLog, load_game, save_game
from dnd_llm.dm.client import OpenAICompatibleClient
from dnd_llm.dm.runtime import DMRuntime
from dnd_llm.dm.usage import CostMonitor, ModelCostConfig, ModelCostReport, render_cost_report
from dnd_llm.orchestrator.reactions import ReactionManager
from dnd_llm.orchestrator.session import GameSession, SessionResult
from dnd_llm.telegram_bot.channels import ChannelDirectory
from dnd_llm.telegram_bot.commands import CommandHandler, CommandRouter
from dnd_llm.telegram_bot.gateway import PlayerIntent
from dnd_llm.telegram_bot.runtime import IncomingMessage, OutgoingMessage, TelegramRuntime

ROLL_EXPR_RE = re.compile(r"^\s*[+-]?\s*(?:\d*d\d+|\d+)(?:\s*[+-]\s*(?:\d*d\d+|\d+))*\s*$", re.I)


@dataclass
class RuntimeStatus:
    campaign_id: str
    current_zone_id: str
    encounter_id: str | None
    current_combatant_id: str | None
    event_counter: int
    roll_counter: int
    combatants: list[dict[str, str]]
    model_usage: dict[str, int]
    model_cost: ModelCostReport | None = None

    def render(self) -> str:
        encounter = self.encounter_id or "无"
        current = self.current_combatant_id or "无"
        lines = [
            f"战役：{self.campaign_id}\n"
            f"区域：{self.current_zone_id}\n"
            f"遭遇：{encounter}\n"
            f"当前行动者：{current}\n"
            f"事件计数：{self.event_counter} 掷骰计数：{self.roll_counter}"
        ]
        if self.combatants:
            lines.append("参战者：")
            lines.extend(
                f"- {combatant['name']}（{combatant['side']}）：{combatant['hp']}"
                for combatant in self.combatants
            )
        if self.model_usage:
            lines.append(
                "模型用量："
                f"prompt={self.model_usage.get('prompt_tokens', 0)} "
                f"completion={self.model_usage.get('completion_tokens', 0)} "
                f"total={self.model_usage.get('total_tokens', 0)} tokens"
            )
        if self.model_cost is not None and self.model_cost.estimated_cost is not None:
            cost_line = f"模型成本：{self.model_cost.currency} {self.model_cost.estimated_cost:.6f}"
            if self.model_cost.budget_ratio is not None:
                status = "已超出" if self.model_cost.budget_exceeded else "未超出"
                cost_line += f"（预算 {self.model_cost.budget_ratio:.1%}，{status}）"
            lines.append(cost_line)
        return "\n".join(lines)


class GameRuntime:
    def __init__(
        self,
        *,
        settings: Settings,
        compendium: Compendium,
        campaign_pack: CampaignPackDefinition,
        state: GameState,
        audit_log: AuditLog,
    ):
        self.settings = settings
        self.compendium = compendium
        self.campaign_pack = campaign_pack
        self.state = state
        self.audit_log = audit_log
        self.session = self._new_session()
        self.dm_runtime = self._new_dm_runtime()
        self.session.timeout_takeover_planner = self.dm_runtime.timeout_takeover_draft
        self.session.monster_turn_planner = self.dm_runtime.monster_turn_draft
        self.command_router = CommandRouter(
            gm_user_ids=set(settings.gm_user_ids),
            handlers=self._command_handlers(),
        )
        self.telegram_runtime = TelegramRuntime(
            session=self.session,
            dm_runtime=self.dm_runtime,
            commands=self.command_router,
            bot_username=settings.bot_username,
        )

    @classmethod
    def build(cls, settings: Settings) -> GameRuntime:
        schema_registry = SchemaRegistry(Path(settings.rules_data_dir) / "schemas")
        rule_validator = RuleDataValidator(schema_registry=schema_registry)
        compendium = CompendiumLoader(settings.rules_data_dir, validator=rule_validator).load()
        pack_path = _campaign_pack_path(settings)
        campaign_pack = CampaignPackLoader().load(pack_path)
        report = CampaignPackValidator(
            compendium=compendium,
            rule_validator=rule_validator,
        ).validate(campaign_pack)
        report.require_ok()
        register_campaign_pack_events(
            compendium,
            campaign_pack,
            validator=rule_validator,
        )
        state = GameState(campaign_id=campaign_pack.campaign_id, rng_seed=settings.rng_seed)
        apply_campaign_pack(state, campaign_pack)
        return cls(
            settings=settings,
            compendium=compendium,
            campaign_pack=campaign_pack,
            state=state,
            audit_log=AuditLog(),
        )

    def status(self) -> RuntimeStatus:
        encounter = self.state.encounter
        return RuntimeStatus(
            campaign_id=self.state.campaign_id,
            current_zone_id=self.state.world.current_zone_id,
            encounter_id=encounter.id if encounter is not None else None,
            current_combatant_id=(
                encounter.current_combatant_id if encounter is not None else None
            ),
            event_counter=self.state.event_counter,
            roll_counter=self.state.roll_counter,
            combatants=(
                [
                    {
                        "id": combatant_id,
                        "name": combatant.name,
                        "side": combatant.side,
                        "hp": _status_hp(
                            combatant.hp_current,
                            combatant.hp_max,
                            strategy=self.state.config.hp_display_strategy,
                        ),
                    }
                    for combatant_id, combatant in encounter.combatants.items()
                ]
                if encounter is not None
                else []
            ),
            model_usage=self.audit_log.model_usage_totals(),
            model_cost=self.cost_report(),
        )

    def cost_report(self) -> ModelCostReport:
        return CostMonitor(
            ModelCostConfig(
                input_cost_per_million=self.settings.model_input_cost_per_million,
                output_cost_per_million=self.settings.model_output_cost_per_million,
                budget=self.settings.model_cost_budget,
                currency=self.settings.model_cost_currency,
            )
        ).report(self.audit_log.events)

    def save(self, slot: str) -> Path:
        path = self._save_path(slot)
        save_game(
            path,
            self.state,
            self.audit_log,
            registry=self.command_router.characters.to_dict(),
        )
        return path

    def load(self, slot: str) -> Path:
        path = self._save_path(slot)
        state, audit_log, registry = load_game(path, include_registry=True)
        self._replace_state(state, audit_log, registry=registry)
        return path

    def list_saves(self) -> list[str]:
        root = self._campaign_save_root()
        if not root.exists():
            return []
        return sorted(path.name for path in root.iterdir() if path.is_dir())

    def new_campaign(self) -> None:
        state = GameState(
            campaign_id=self.campaign_pack.campaign_id, rng_seed=self.settings.rng_seed
        )
        apply_campaign_pack(state, self.campaign_pack)
        self._replace_state(state, AuditLog())

    def force_turn(self) -> SessionResult | object:
        return self.session.advance_turn(f"gm:forceturn:{self.state.event_counter}")

    def kick(self, user_id: str) -> bool:
        removed = self.command_router.characters.leave_campaign(user_id)
        return removed is not None

    def _command_handlers(self) -> dict[str, CommandHandler]:
        return {
            "/status": self._cmd_status,
            "/roll": self._cmd_roll,
            "/save": self._cmd_save,
            "/load": self._cmd_load,
            "/saves": self._cmd_saves,
            "/newcampaign": self._cmd_newcampaign,
            "/forceturn": self._cmd_forceturn,
            "/kick": self._cmd_kick,
            "/cost": self._cmd_cost,
        }

    def _cmd_status(self, _: PlayerIntent) -> str:
        return self.status().render()

    def _cmd_roll(self, intent: PlayerIntent) -> str:
        expr = _first_arg(intent.text, default="1d20")
        if len(expr) > 40 or ROLL_EXPR_RE.match(expr) is None:
            return "骰子表达式不合法。"
        try:
            roll = self.session.roll_service.roll(expr)
        except Exception:
            return "骰子表达式不合法。"
        self.audit_log.append(
            self.state,
            idempotency_key=f"telegram:roll:{self.state.event_counter}",
            player_text=intent.text,
            player_intent=intent.to_dict(),
            tool_name="telegram.roll",
            tool_args={"expr": expr},
            tool_result=roll.to_dict(),
            dice_rolls=[roll.to_dict()],
        )
        return f"掷骰 {expr}：{roll.display} = {roll.total}"

    def _cmd_save(self, intent: PlayerIntent) -> str:
        slot = _first_arg(intent.text, default="manual")
        path = self.save(slot)
        return f"已保存：{path}"

    def _cmd_load(self, intent: PlayerIntent) -> str:
        slot = _first_arg(intent.text, default="manual")
        path = self.load(slot)
        return f"已读取：{path}"

    def _cmd_saves(self, _: PlayerIntent) -> str:
        saves = self.list_saves()
        return "可用存档：\n" + "\n".join(saves) if saves else "暂无存档。"

    def _cmd_newcampaign(self, _: PlayerIntent) -> str:
        self.new_campaign()
        return f"已创建新战役：{self.campaign_pack.title}"

    def _cmd_forceturn(self, _: PlayerIntent) -> str:
        result = self.force_turn()
        if not isinstance(result, SessionResult) or not result.accepted:
            return "当前无法推进回合。"
        return f"已推进到：{result.payload.get('current_combatant_id') or '无'}"

    def _cmd_kick(self, intent: PlayerIntent) -> str:
        user_id = _first_arg(intent.text, default="")
        if not user_id:
            return "请提供要移出的用户 ID。"
        return "已移出战役。" if self.kick(user_id) else "该用户未加入战役。"

    def _cmd_cost(self, _: PlayerIntent) -> str:
        return render_cost_report(self.cost_report())

    def _replace_state(
        self,
        state: GameState,
        audit_log: AuditLog,
        *,
        registry: dict[str, Any] | None = None,
    ) -> None:
        self.state = state
        self.audit_log = audit_log
        if registry is not None:
            self.command_router.characters.replace_from_dict(registry)
        self._sync_character_registry_from_state()
        self.session = self._new_session()
        self.dm_runtime = self._new_dm_runtime()
        self.session.timeout_takeover_planner = self.dm_runtime.timeout_takeover_draft
        self.session.monster_turn_planner = self.dm_runtime.monster_turn_draft
        self.telegram_runtime.session = self.session
        self.telegram_runtime.dm_runtime = self.dm_runtime

    def _sync_character_registry_from_state(self) -> None:
        registry = self.command_router.characters
        registry.sync_from_state(self.state)
        for characters in registry.characters_by_user.values():
            for character_id in list(characters):
                restored = self.state.characters.get(character_id)
                if restored is not None:
                    characters[character_id] = Character.from_dict(restored.to_dict())
        for user_id, character_id in list(registry.campaign_members.items()):
            if character_id not in self.state.characters:
                registry.campaign_members.pop(user_id, None)

    def _new_session(self) -> GameSession:
        return GameSession(
            self.state,
            self.compendium,
            self.audit_log,
            reactions=ReactionManager(mode=self.settings.reaction_mode),
            campaign_pack=self.campaign_pack,
        )

    def _new_dm_runtime(self) -> DMRuntime:
        return DMRuntime(
            self.session,
            client=OpenAICompatibleClient(self.settings, self.settings.dm_model),
            model_id=self.settings.dm_model,
            summary_client=OpenAICompatibleClient(self.settings, self.settings.summary_model),
            summary_model_id=self.settings.summary_model,
        )

    def _campaign_save_root(self) -> Path:
        campaign_id_error = campaign_id_validation_error(self.state.campaign_id)
        if campaign_id_error is not None:
            raise ValueError(campaign_id_error)
        save_root = Path(self.settings.save_dir).expanduser().resolve()
        campaign_root = (save_root / self.state.campaign_id).resolve()
        _require_contained_path(campaign_root, save_root, label="campaign save path")
        return campaign_root

    def _save_path(self, slot: str) -> Path:
        safe_slot = slot.strip() or "manual"
        if "/" in safe_slot or "\\" in safe_slot or safe_slot in {".", ".."}:
            raise ValueError("invalid save slot")
        campaign_root = self._campaign_save_root()
        save_path = (campaign_root / safe_slot).resolve()
        _require_contained_path(save_path, campaign_root, label="save slot path")
        return save_path


class MultiCampaignRuntime:
    """Routes Telegram chats to isolated campaign runtimes."""

    def __init__(
        self,
        *,
        settings: Settings,
        compendium: Compendium,
        campaign_pack: CampaignPackDefinition,
        channels: ChannelDirectory | None = None,
    ):
        self.settings = settings
        self.compendium = compendium
        self.campaign_pack = campaign_pack
        self.channels = channels or ChannelDirectory()
        self._runtimes_by_group: dict[str, GameRuntime] = {}
        self._active_group_by_user: dict[str, str] = {}
        self._routing_lock = threading.RLock()
        self._runtime_locks: dict[int, threading.RLock] = {}

    @classmethod
    def build(cls, settings: Settings) -> MultiCampaignRuntime:
        return cls.from_runtime(GameRuntime.build(settings))

    @classmethod
    def from_runtime(cls, runtime: GameRuntime) -> MultiCampaignRuntime:
        return cls(
            settings=runtime.settings,
            compendium=runtime.compendium,
            campaign_pack=runtime.campaign_pack,
        )

    @property
    def campaign_chat_ids(self) -> list[str]:
        return sorted(self._runtimes_by_group)

    def runtime_for_group(self, chat_id: str) -> GameRuntime:
        with self._routing_lock:
            runtime = self._runtimes_by_group.get(chat_id)
            if runtime is not None:
                return runtime
            state = GameState(
                campaign_id=self.campaign_pack.campaign_id,
                rng_seed=_seed_for_chat(self.settings.rng_seed, chat_id),
            )
            apply_campaign_pack(state, self.campaign_pack)
            state.campaign_id = _campaign_id_for_chat(self.campaign_pack.campaign_id, chat_id)
            runtime = GameRuntime(
                settings=self.settings,
                compendium=self.compendium,
                campaign_pack=self.campaign_pack,
                state=state,
                audit_log=AuditLog(),
            )
            runtime.telegram_runtime.campaign_chat_id = chat_id
            runtime.telegram_runtime.channels = self.channels
            self._runtimes_by_group[chat_id] = runtime
            self._runtime_locks[id(runtime)] = threading.RLock()
            return runtime

    def handle_message(self, incoming: IncomingMessage, *, now: int) -> list[OutgoingMessage]:
        if incoming.is_private:
            with self._routing_lock:
                self.channels.bind_private_chat(incoming.user_id, incoming.chat_id)
            return self._handle_private_message(incoming, now=now)
        with self._routing_lock:
            self._active_group_by_user[incoming.user_id] = incoming.chat_id
            runtime = self.runtime_for_group(incoming.chat_id)
        return self._handle_with_runtime_lock(runtime, incoming, now=now)

    def tick(self, *, now: int) -> list[OutgoingMessage]:
        with self._routing_lock:
            runtimes = list(self._runtimes_by_group.values())
        outgoing: list[OutgoingMessage] = []
        for runtime in runtimes:
            with self._runtime_lock_for(runtime):
                outgoing.extend(runtime.telegram_runtime.tick(now=now))
        return outgoing

    def _handle_private_message(
        self,
        incoming: IncomingMessage,
        *,
        now: int,
    ) -> list[OutgoingMessage]:
        command = _command_name(incoming.text)
        if command == "/start":
            with self._routing_lock:
                group_id = self._active_group_by_user.get(incoming.user_id)
            if group_id is not None:
                return self._handle_with_runtime_lock(
                    self.runtime_for_group(group_id), incoming, now=now
                )
            return [
                OutgoingMessage(
                    chat_id=incoming.chat_id,
                    text="私聊已激活。",
                    private=True,
                    metadata={"command": "/start"},
                )
            ]
        if command == "/react":
            routed = self._runtime_for_reaction(incoming.user_id, incoming.text)
            if routed is not None:
                group_id, runtime = routed
                with self._routing_lock:
                    self._active_group_by_user[incoming.user_id] = group_id
                return self._handle_with_runtime_lock(runtime, incoming, now=now)
        private_runtime = self._runtime_for_private_user(incoming.user_id)
        if private_runtime is None:
            return [
                OutgoingMessage(
                    chat_id=incoming.chat_id,
                    text="请先在目标群发送 /newchar、/join 或 DD 行动，以选择战役上下文。",
                    private=True,
                    metadata={"missing_campaign_context": True},
                )
            ]
        return self._handle_with_runtime_lock(private_runtime, incoming, now=now)

    def _runtime_for_private_user(self, user_id: str) -> GameRuntime | None:
        with self._routing_lock:
            group_id = self._active_group_by_user.get(user_id)
            if group_id is not None:
                return self.runtime_for_group(group_id)
            if len(self._runtimes_by_group) == 1:
                return next(iter(self._runtimes_by_group.values()))
            return None

    def _runtime_for_reaction(
        self,
        user_id: str,
        text: str,
    ) -> tuple[str, GameRuntime] | None:
        parts = text.split()
        if len(parts) < 2:
            return None
        reaction_id = parts[1]
        with self._routing_lock:
            runtimes = list(self._runtimes_by_group.items())
        for group_id, runtime in runtimes:
            with self._runtime_lock_for(runtime):
                character = runtime.command_router.characters.campaign_character_for_user(user_id)
                if character is None or runtime.state.encounter is None:
                    continue
                window = runtime.state.encounter.pending_reactions.get(reaction_id)
                if window is not None and window.get("actor_id") == character.id:
                    return group_id, runtime
        return None

    def _handle_with_runtime_lock(
        self,
        runtime: GameRuntime,
        incoming: IncomingMessage,
        *,
        now: int,
    ) -> list[OutgoingMessage]:
        with self._runtime_lock_for(runtime):
            return runtime.telegram_runtime.handle_message(incoming, now=now)

    def _runtime_lock_for(self, runtime: GameRuntime) -> threading.RLock:
        with self._routing_lock:
            return self._runtime_locks.setdefault(id(runtime), threading.RLock())


def _campaign_pack_path(settings: Settings) -> Path:
    if settings.campaign_pack_path:
        return Path(settings.campaign_pack_path)
    return Path(settings.rules_data_dir) / "campaigns" / "starter" / "pack.json"


def _first_arg(text: str, *, default: str) -> str:
    parts = text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else default


def _status_hp(current: int, maximum: int, *, strategy: str = "fuzzy") -> str:
    if maximum <= 0:
        return "Unknown"
    if strategy == "exact":
        return f"{current}/{maximum}"
    ratio = current / maximum
    if ratio >= 0.75:
        return "Healthy"
    if ratio >= 0.5:
        return "Injured"
    if ratio >= 0.25:
        return "Bloodied"
    return "Critical"


def _command_name(text: str) -> str | None:
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    return stripped.split(maxsplit=1)[0]


def _seed_for_chat(base_seed: int, chat_id: str) -> int:
    digest = hashlib.sha256(f"{base_seed}:{chat_id}".encode()).hexdigest()
    return int(digest[:12], 16)


def _campaign_id_for_chat(base_campaign_id: str, chat_id: str) -> str:
    digest = hashlib.sha256(chat_id.encode("utf-8")).hexdigest()[:10]
    return f"{base_campaign_id}_chat_{digest}"


def _require_contained_path(path: Path, root: Path, *, label: str) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} escapes configured save directory") from exc

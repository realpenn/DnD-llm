from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from dnd_llm.core.models import Character
from dnd_llm.dm.runtime import DMRuntime
from dnd_llm.orchestrator.session import GameSession, SessionResult

from .channels import ChannelDirectory, render_private_required
from .commands import CommandRouter
from .gateway import PlayerIntent, normalize_message


@dataclass(frozen=True)
class IncomingMessage:
    user_id: str
    chat_id: str
    text: str
    is_private: bool = False
    message_id: str | None = None


@dataclass(frozen=True)
class OutgoingMessage:
    chat_id: str
    text: str
    private: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class RateLimiter:
    def __init__(self, *, max_messages: int = 6, window_seconds: int = 10):
        self.max_messages = max_messages
        self.window_seconds = window_seconds
        self._events: dict[str, list[int]] = {}

    def allow(self, user_id: str, now: int) -> bool:
        events = [
            timestamp
            for timestamp in self._events.get(user_id, [])
            if now - timestamp < self.window_seconds
        ]
        if len(events) >= self.max_messages:
            self._events[user_id] = events
            return False
        events.append(now)
        self._events[user_id] = events
        return True


class TelegramRuntime:
    private_commands = {"/newchar", "/editchar", "/mychars", "/usechar", "/sheet"}

    def __init__(
        self,
        *,
        session: GameSession,
        dm_runtime: DMRuntime,
        commands: CommandRouter | None = None,
        channels: ChannelDirectory | None = None,
        bot_username: str | None = None,
        rate_limiter: RateLimiter | None = None,
        campaign_chat_id: str | None = None,
    ):
        self.session = session
        self.dm_runtime = dm_runtime
        self.commands = commands or CommandRouter()
        self.channels = channels or ChannelDirectory()
        self.bot_username = bot_username
        self.campaign_chat_id = campaign_chat_id
        self.rate_limiter = rate_limiter or RateLimiter()
        self._message_cache: dict[str, list[OutgoingMessage]] = {}
        self.commands.handlers.setdefault("/forceturn", self._default_forceturn)

    def handle_message(self, incoming: IncomingMessage, *, now: int) -> list[OutgoingMessage]:
        cache_key = self._message_cache_key(incoming)
        if cache_key is not None and cache_key in self._message_cache:
            return _copy_messages(self._message_cache[cache_key])
        self.session.set_current_time(now)
        if incoming.is_private:
            self.channels.bind_private_chat(incoming.user_id, incoming.chat_id)
        intent = normalize_message(
            user_id=incoming.user_id,
            chat_id=incoming.chat_id,
            text=incoming.text,
            bot_username=self.bot_username,
        )
        if intent is None:
            return self._record_message_result(cache_key, [])
        if not self.rate_limiter.allow(incoming.user_id, now):
            return self._record_message_result(
                cache_key,
                [
                    OutgoingMessage(
                        chat_id=incoming.chat_id,
                        text="操作太频繁，请稍后再试。",
                        metadata={"rate_limited": True},
                    )
                ],
            )
        if intent.is_command:
            messages = self._handle_command(intent, incoming, now=now)
        else:
            messages = self._handle_dm_intent(intent, incoming)
        return self._record_message_result(cache_key, messages)

    def _record_message_result(
        self,
        cache_key: str | None,
        messages: list[OutgoingMessage],
    ) -> list[OutgoingMessage]:
        if cache_key is not None:
            self._message_cache[cache_key] = _copy_messages(messages)
        return messages

    @staticmethod
    def _message_cache_key(incoming: IncomingMessage) -> str | None:
        if incoming.message_id is None:
            return None
        return f"telegram-message:{incoming.chat_id}:{incoming.message_id}"

    def _handle_command(
        self,
        intent: PlayerIntent,
        incoming: IncomingMessage,
        *,
        now: int,
    ) -> list[OutgoingMessage]:
        command = intent.text.split(maxsplit=1)[0]
        if command == "/react":
            return self._handle_reaction_command(intent, incoming, now=now)
        if command == "/start" and incoming.is_private:
            self.channels.bind_private_chat(intent.user_id, intent.chat_id)
        if command in self.private_commands and not incoming.is_private:
            private_chat = self.channels.private_chat_for(intent.user_id)
            if private_chat is None:
                return [
                    OutgoingMessage(
                        chat_id=intent.chat_id,
                        text=render_private_required(intent.user_id),
                        metadata={"private_required": True},
                    )
                ]
            response = self.commands.dispatch(intent)
            if command in {"/newchar", "/editchar", "/usechar"}:
                self._sync_active_character(intent.user_id)
            return [
                OutgoingMessage(
                    chat_id=private_chat,
                    text=response,
                    private=True,
                    metadata={"command": command},
                ),
                OutgoingMessage(
                    chat_id=intent.chat_id,
                    text="已通过私聊发送。",
                    metadata={"private_redirect": True},
                ),
            ]

        before_event_counter = self.session.state.event_counter
        response = self.commands.dispatch(intent)
        if command in {"/newchar", "/editchar", "/usechar", "/join"}:
            self._sync_active_character(intent.user_id)
        messages = [
            OutgoingMessage(
                chat_id=intent.chat_id,
                text=response,
                private=incoming.is_private,
                metadata={"command": command},
            )
        ]
        if command == "/forceturn" and self.session.state.event_counter != before_event_counter:
            next_combatant_id = (
                self.session.state.encounter.current_combatant_id
                if self.session.state.encounter is not None
                else None
            )
            turn_prompt = self._turn_prompt_message(
                group_chat_id=intent.chat_id,
                payload={"next_combatant_id": next_combatant_id},
            )
            if turn_prompt is not None:
                messages.append(turn_prompt)
        return messages

    def _default_forceturn(self, intent: PlayerIntent) -> str:
        result = self.session.advance_turn(
            f"telegram:forceturn:{intent.chat_id}:{self.session.state.event_counter}"
        )
        if not isinstance(result, SessionResult) or not result.accepted:
            return "当前无法推进回合。"
        return f"已推进到：{result.payload.get('current_combatant_id') or '无'}"

    def _handle_dm_intent(
        self,
        intent: PlayerIntent,
        incoming: IncomingMessage,
    ) -> list[OutgoingMessage]:
        if self.commands.characters.is_spectator(intent.user_id):
            return [
                OutgoingMessage(
                    chat_id=intent.chat_id,
                    text="你正在观战模式，不能提交角色行动；如要参战，请先退出观战并 /join。",
                    private=incoming.is_private,
                    metadata={"spectator_blocked_action": True},
                )
            ]
        character = self.commands.characters.campaign_character_for_user(intent.user_id)
        if character is None:
            return [
                OutgoingMessage(
                    chat_id=intent.chat_id,
                    text="请先私聊 /newchar 创建角色，并在群里 /join。",
                    metadata={"missing_character": True},
                )
            ]
        self._ensure_character_in_state(character)
        response = self.dm_runtime.handle_player_text(
            actor_id=character.id,
            text=intent.text,
            idempotency_key=self._idempotency_key(intent, incoming),
        )
        self._sync_campaign_characters_from_state()
        messages = [
            OutgoingMessage(
                chat_id=intent.chat_id,
                text=response.narration,
                metadata={
                    "accepted": response.accepted,
                    "actor_id": character.id,
                    "source": intent.source,
                },
            )
        ]
        messages.extend(
            self._reaction_prompt_messages(
                group_chat_id=intent.chat_id,
                reaction_windows=response.engine_payload.get("reaction_windows", []),
            )
        )
        turn_prompt = self._turn_prompt_message(
            group_chat_id=intent.chat_id,
            payload=response.engine_payload,
        )
        if turn_prompt is not None:
            messages.append(turn_prompt)
        return messages

    def _handle_reaction_command(
        self,
        intent: PlayerIntent,
        incoming: IncomingMessage,
        *,
        now: int,
    ) -> list[OutgoingMessage]:
        if self.commands.characters.is_spectator(intent.user_id):
            return [
                OutgoingMessage(
                    chat_id=intent.chat_id,
                    text="你正在观战模式，不能确认反应。",
                    private=incoming.is_private,
                    metadata={"command": "/react", "spectator_blocked_action": True},
                )
            ]
        parts = intent.text.split()
        if len(parts) < 3:
            return [
                OutgoingMessage(
                    chat_id=intent.chat_id,
                    text="用法：/react <reaction_id> yes|no",
                    private=incoming.is_private,
                    metadata={"command": "/react", "accepted": False},
                )
            ]
        character = self.commands.characters.campaign_character_for_user(intent.user_id)
        if character is None:
            return [
                OutgoingMessage(
                    chat_id=intent.chat_id,
                    text="请先私聊 /newchar 创建角色，并在群里 /join。",
                    metadata={"missing_character": True},
                )
            ]
        reaction_id = parts[1]
        decision = parts[2].casefold()
        if decision not in {"yes", "y", "是", "确认", "no", "n", "否", "放弃"}:
            return [
                OutgoingMessage(
                    chat_id=intent.chat_id,
                    text="请用 yes/no 确认或放弃反应。",
                    private=incoming.is_private,
                    metadata={"command": "/react", "accepted": False},
                )
            ]
        pending = (
            self.session.state.encounter.pending_reactions
            if self.session.state.encounter is not None
            else {}
        )
        window = pending.get(reaction_id)
        if window is None:
            return [
                OutgoingMessage(
                    chat_id=intent.chat_id,
                    text="找不到这个待确认反应。",
                    private=incoming.is_private,
                    metadata={"command": "/react", "accepted": False},
                )
            ]
        if window.get("actor_id") != character.id:
            return [
                OutgoingMessage(
                    chat_id=intent.chat_id,
                    text="这不是你的反应窗口。",
                    private=incoming.is_private,
                    metadata={"command": "/react", "accepted": False},
                )
            ]
        accepted = decision in {"yes", "y", "是", "确认"}
        result = self.session.resolve_reaction(
            reaction_id=reaction_id,
            accept=accepted,
            now=now,
            idempotency_key=f"telegram:react:{incoming.chat_id}:{incoming.message_id or now}",
        )
        if not isinstance(result, SessionResult):
            text = "反应处理失败。"
            metadata = {"command": "/react", "accepted": False}
        else:
            self._sync_campaign_characters_from_state()
            payload = result.payload
            status = payload.get("status")
            text = "反应已确认。" if status == "accepted" else "反应已放弃。"
            metadata = {
                "command": "/react",
                "accepted": status == "accepted",
                "reaction_id": reaction_id,
                "next_combatant_id": payload.get("next_combatant_id"),
            }
        messages = [
            OutgoingMessage(
                chat_id=intent.chat_id,
                text=text,
                private=incoming.is_private,
                metadata=metadata,
            )
        ]
        if isinstance(result, SessionResult) and result.accepted:
            turn_prompt = self._turn_prompt_message(
                group_chat_id=self.campaign_chat_id or intent.chat_id,
                payload=result.payload,
            )
            if turn_prompt is not None:
                messages.append(turn_prompt)
        return messages

    def _turn_prompt_message(
        self,
        *,
        group_chat_id: str,
        payload: dict[str, Any],
    ) -> OutgoingMessage | None:
        if payload.get("pending_reactions"):
            return None
        next_combatant_id = payload.get("next_combatant_id")
        if not isinstance(next_combatant_id, str):
            return None
        encounter = self.session.state.encounter
        if encounter is None:
            return None
        combatant = encounter.combatants.get(next_combatant_id)
        if combatant is None or combatant.side != "party":
            return None
        user_id = self.commands.characters.user_for_character(combatant.entity_id)
        mentions = {}
        if user_id is not None:
            mentions[combatant.entity_id] = f"@{user_id}"
            mentions[combatant.id] = f"@{user_id}"
        prompt = self.session.current_turn_prompt(mentions)
        if prompt is None:
            return None
        return OutgoingMessage(
            chat_id=group_chat_id,
            text=prompt,
            metadata={
                "turn_prompt": True,
                "combatant_id": combatant.id,
                "character_id": combatant.entity_id,
                "user_id": user_id,
            },
        )

    def _reaction_prompt_messages(
        self,
        *,
        group_chat_id: str,
        reaction_windows: object,
    ) -> list[OutgoingMessage]:
        if not isinstance(reaction_windows, list):
            return []
        messages: list[OutgoingMessage] = []
        for window in reaction_windows:
            if not isinstance(window, dict):
                continue
            actor_id = str(window.get("actor_id", ""))
            user_id = self.commands.characters.user_for_character(actor_id)
            private_chat = self.channels.private_chat_for(user_id) if user_id is not None else None
            if private_chat is None:
                messages.append(
                    OutgoingMessage(
                        chat_id=group_chat_id,
                        text=render_private_required(user_id or actor_id),
                        metadata={
                            "reaction_prompt": True,
                            "private_required": True,
                            "actor_id": actor_id,
                        },
                    )
                )
                continue
            chat_id = private_chat or group_chat_id
            prompt = str(window.get("prompt", "你有一个待确认反应。"))
            reaction_id = str(window.get("reaction_id", ""))
            messages.append(
                OutgoingMessage(
                    chat_id=chat_id,
                    text=f"{prompt}\n/react {reaction_id} yes|no",
                    private=private_chat is not None,
                    metadata={"reaction_prompt": True, "reaction_id": reaction_id},
                )
            )
        return messages

    def _sync_active_character(self, user_id: str) -> None:
        character = self.commands.characters.character_for_user(user_id)
        if character is not None:
            self._sync_character(character)

    def _sync_character(self, character: Character) -> None:
        self.session.state.characters[character.id] = Character.from_dict(character.to_dict())

    def _ensure_character_in_state(self, character: Character) -> None:
        if character.id not in self.session.state.characters:
            self._sync_character(character)

    def _sync_campaign_characters_from_state(self) -> list[str]:
        return self.commands.characters.sync_from_state(self.session.state)

    @staticmethod
    def _idempotency_key(intent: PlayerIntent, incoming: IncomingMessage) -> str:
        if incoming.message_id is not None:
            return f"telegram:{incoming.chat_id}:{incoming.message_id}"
        digest = hashlib.sha256(intent.text.encode("utf-8")).hexdigest()[:16]
        return f"telegram:{incoming.chat_id}:{incoming.user_id}:{digest}"


def _copy_messages(messages: list[OutgoingMessage]) -> list[OutgoingMessage]:
    return [
        OutgoingMessage(
            chat_id=message.chat_id,
            text=message.text,
            private=message.private,
            metadata=dict(message.metadata),
        )
        for message in messages
    ]

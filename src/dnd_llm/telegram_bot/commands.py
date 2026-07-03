from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from dnd_llm.content.character_editor import apply_natural_language_character_edit

from .characters import CharacterRegistry
from .gateway import PlayerIntent

CommandHandler = Callable[[PlayerIntent], str]


@dataclass
class CommandRouter:
    gm_user_ids: set[str] = field(default_factory=set)
    characters: CharacterRegistry = field(default_factory=CharacterRegistry)
    handlers: dict[str, CommandHandler] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.handlers.setdefault(
            "/help",
            lambda _: (
                "可用指令：/start /help /newchar /editchar /mychars /usechar /sheet /join "
                "/leave /spectate /unspectate /react /roll /status\n"
                "GM 指令：/newcampaign /save /load /saves /kick /forceturn"
            ),
        )
        self.handlers.setdefault("/start", lambda _: "私聊已激活。")
        self.handlers.setdefault("/status", lambda _: "战役状态读取接口已就绪。")
        self.handlers.setdefault("/newchar", self._newchar)
        self.handlers.setdefault("/editchar", self._editchar)
        self.handlers.setdefault("/mychars", self._mychars)
        self.handlers.setdefault("/usechar", self._usechar)
        self.handlers.setdefault("/sheet", self._sheet)
        self.handlers.setdefault("/join", self._join)
        self.handlers.setdefault("/leave", self._leave)
        self.handlers.setdefault("/spectate", self._spectate)
        self.handlers.setdefault("/unspectate", self._unspectate)
        self.handlers.setdefault(
            "/roll", lambda _: "公开掷骰指令已保留；机械掷骰由 Core RollService 执行。"
        )

    def dispatch(self, intent: PlayerIntent) -> str:
        command = intent.text.split(maxsplit=1)[0]
        if (
            command in {"/newcampaign", "/save", "/load", "/saves", "/kick", "/forceturn"}
            and intent.user_id not in self.gm_user_ids
        ):
            return "该指令仅 GM 可用。"
        handler = self.handlers.get(command)
        if handler is None:
            return "未知指令。"
        return handler(intent)

    def _newchar(self, intent: PlayerIntent) -> str:
        parts = intent.text.split(maxsplit=1)
        name = parts[1].strip() if len(parts) > 1 else f"角色{intent.user_id}"
        character = self.characters.create_default(intent.user_id, name)
        return f"已创建并选中角色：{character.name}（{character.id}）。"

    def _editchar(self, intent: PlayerIntent) -> str:
        character = self.characters.active_character(intent.user_id)
        if character is None:
            return "你还没有 active 角色。"
        parts = intent.text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            return "请提供角色修改描述。"
        result = apply_natural_language_character_edit(character, parts[1].strip())
        if not result.accepted or result.character is None:
            errors = result.errors or ["角色修改未通过校验。"]
            return "角色修改被拒绝：\n" + "\n".join(errors)
        updated = self.characters.update_character(intent.user_id, result.character)
        classes = "/".join(f"{name}{level}" for name, level in updated.class_levels.items())
        return f"已更新角色：{updated.name}（{updated.id}）。\n职业：{classes}"

    def _mychars(self, intent: PlayerIntent) -> str:
        characters = self.characters.list_characters(intent.user_id)
        if not characters:
            return "你还没有角色。"
        active = self.characters.active_by_user.get(intent.user_id)
        lines = []
        for character in characters:
            marker = "*" if character.id == active else "-"
            lines.append(f"{marker} {character.id} {character.name}")
        return "\n".join(lines)

    def _usechar(self, intent: PlayerIntent) -> str:
        parts = intent.text.split(maxsplit=1)
        if len(parts) < 2:
            return "请提供角色 ID。"
        try:
            character = self.characters.use_character(intent.user_id, parts[1].strip())
        except KeyError:
            return "找不到这个角色。"
        return f"已选中角色：{character.name}。"

    def _sheet(self, intent: PlayerIntent) -> str:
        character = self.characters.active_character(intent.user_id)
        if character is None:
            return "你还没有 active 角色。"
        classes = "/".join(f"{name}{level}" for name, level in character.class_levels.items())
        feats = "、".join(character.feats) if character.feats else "无"
        skills = "、".join(character.skill_proficiencies) if character.skill_proficiencies else "无"
        tools = "、".join(character.tool_proficiencies) if character.tool_proficiencies else "无"
        return (
            f"{character.name}（{character.id}）\n"
            f"职业：{classes}\n"
            f"专长：{feats}\n"
            f"技能熟练：{skills}\n"
            f"工具熟练：{tools}\n"
            f"HP：{character.hp_current}/{character.hp_max} AC：{character.armor_class}\n"
            f"属性：{character.abilities}"
        )

    def _join(self, intent: PlayerIntent) -> str:
        try:
            character = self.characters.join_campaign(intent.user_id)
        except ValueError:
            return "请先用 /newchar 创建角色，或用 /usechar 选中角色。"
        return f"{character.name} 已加入当前战役。"

    def _leave(self, intent: PlayerIntent) -> str:
        character_id = self.characters.leave_campaign(intent.user_id)
        if character_id is None:
            return "你当前没有加入战役。"
        return "已离开当前战役。"

    def _spectate(self, intent: PlayerIntent) -> str:
        if not self.characters.spectate_campaign(intent.user_id):
            return "你已经作为玩家加入当前战役。"
        return "已进入观战模式。你可以查看公开状态，但不能提交角色行动。"

    def _unspectate(self, intent: PlayerIntent) -> str:
        if not self.characters.leave_spectator(intent.user_id):
            return "你当前不在观战模式。"
        return "已退出观战模式。"

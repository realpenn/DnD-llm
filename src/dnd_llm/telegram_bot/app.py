from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from dnd_llm.config import Settings

from .runtime import IncomingMessage, OutgoingMessage

BotSender = Callable[[str, str], Awaitable[Any]]


class MessageRuntime(Protocol):
    def handle_message(self, incoming: IncomingMessage, *, now: int) -> list[OutgoingMessage]: ...


def build_application(settings: Settings, runtime: MessageRuntime) -> Application:
    if not settings.bot_token:
        raise ValueError("BOT_TOKEN is required to build the Telegram application")
    application = Application.builder().token(settings.bot_token).build()

    async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await handle_update(update, runtime, context.bot.send_message)

    application.add_handler(MessageHandler(filters.TEXT, on_text))
    return application


async def handle_update(
    update: Update,
    runtime: MessageRuntime,
    sender: BotSender,
    *,
    now: int | None = None,
) -> None:
    if (
        update.effective_message is None
        or update.effective_user is None
        or update.effective_chat is None
    ):
        return
    text = update.effective_message.text
    if text is None:
        return
    outgoing = runtime.handle_message(
        IncomingMessage(
            user_id=str(update.effective_user.id),
            chat_id=str(update.effective_chat.id),
            text=text,
            is_private=update.effective_chat.type == "private",
            message_id=str(update.effective_message.message_id),
        ),
        now=now if now is not None else int(time.time()),
    )
    for message in outgoing:
        await sender(message.chat_id, message.text)

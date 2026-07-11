from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any, Protocol

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from dnd_llm.config import Settings

from .runtime import IncomingMessage, OutgoingMessage

BotSender = Callable[[str, str], Awaitable[Any]]
MAX_CONCURRENT_UPDATES = 32
LOGGER = logging.getLogger(__name__)


class MessageRuntime(Protocol):
    def handle_message(self, incoming: IncomingMessage, *, now: int) -> list[OutgoingMessage]: ...

    def tick(self, *, now: int) -> list[OutgoingMessage]: ...


def build_application(settings: Settings, runtime: MessageRuntime) -> Application:
    if not settings.bot_token:
        raise ValueError("BOT_TOKEN is required to build the Telegram application")
    tick_task: asyncio.Task[None] | None = None

    async def periodic_tick(application: Application) -> None:
        while True:
            await asyncio.sleep(1)
            try:
                outgoing = await asyncio.to_thread(runtime.tick, now=int(time.time()))
                for message in outgoing:
                    await application.bot.send_message(message.chat_id, message.text)
            except Exception:
                LOGGER.exception("Telegram periodic runtime tick failed")

    async def post_init(application: Application) -> None:
        nonlocal tick_task
        tick_task = application.create_task(periodic_tick(application))

    async def post_shutdown(_: Application) -> None:
        if tick_task is None:
            return
        tick_task.cancel()
        with suppress(asyncio.CancelledError):
            await tick_task

    builder = (
        Application.builder().token(settings.bot_token).concurrent_updates(MAX_CONCURRENT_UPDATES)
    )
    if hasattr(builder, "post_init") and hasattr(builder, "post_shutdown"):
        builder = builder.post_init(post_init).post_shutdown(post_shutdown)
    application = builder.build()
    chat_locks: dict[str, asyncio.Lock] = {}

    async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = str(update.effective_chat.id) if update.effective_chat is not None else "unknown"
        lock = chat_locks.setdefault(chat_id, asyncio.Lock())
        async with lock:
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
    incoming = IncomingMessage(
        user_id=str(update.effective_user.id),
        chat_id=str(update.effective_chat.id),
        text=text,
        is_private=update.effective_chat.type == "private",
        message_id=str(update.effective_message.message_id),
    )
    outgoing = await asyncio.to_thread(
        runtime.handle_message,
        incoming,
        now=now if now is not None else int(time.time()),
    )
    for message in outgoing:
        await sender(message.chat_id, message.text)

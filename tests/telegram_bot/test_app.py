from __future__ import annotations

from typing import cast

import pytest

from dnd_llm.config import Settings
from dnd_llm.telegram_bot.app import build_application
from dnd_llm.telegram_bot.runtime import TelegramRuntime


def test_build_application_requires_token() -> None:
    with pytest.raises(ValueError, match="BOT_TOKEN"):
        build_application(Settings(bot_token=None), cast(TelegramRuntime, object()))

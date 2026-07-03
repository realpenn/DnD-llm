from __future__ import annotations

from .config import Settings
from .runtime import GameRuntime, MultiCampaignRuntime
from .telegram_bot.app import build_application


def main() -> int:
    settings = Settings.from_env()
    runtime = GameRuntime.build(settings)
    print(
        "DnD-LLM configured and loaded "
        f"(campaign_dir={settings.campaign_pack_dir}, "
        f"dm_model={settings.dm_model or 'unset'}, "
        f"campaign={runtime.state.campaign_id})"
    )
    if settings.run_telegram:
        application = build_application(settings, MultiCampaignRuntime.from_runtime(runtime))
        application.run_polling()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

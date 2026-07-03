from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    bot_token: str | None = None
    openai_base_url: str | None = None
    openai_api_key: str | None = None
    dm_model: str | None = None
    summary_model: str | None = None
    content_model: str | None = None
    campaign_pack_dir: str = "campaigns"
    rules_data_dir: str = "rules_data"
    campaign_pack_path: str | None = None
    save_dir: str = "saves"
    gm_user_ids: tuple[str, ...] = ()
    bot_username: str | None = None
    rng_seed: int = 20260629
    run_telegram: bool = False
    reaction_mode: str = "interactive"

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            bot_token=os.getenv("BOT_TOKEN"),
            openai_base_url=os.getenv("OPENAI_BASE_URL"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            dm_model=os.getenv("DM_MODEL") or os.getenv("OPENAI_MODEL"),
            summary_model=os.getenv("SUMMARY_MODEL") or os.getenv("OPENAI_MODEL"),
            content_model=os.getenv("CONTENT_MODEL") or os.getenv("OPENAI_MODEL"),
            campaign_pack_dir=os.getenv("CAMPAIGN_PACK_DIR", "campaigns"),
            rules_data_dir=os.getenv("RULES_DATA_DIR", "rules_data"),
            campaign_pack_path=os.getenv("CAMPAIGN_PACK_PATH"),
            save_dir=os.getenv("SAVE_DIR", "saves"),
            gm_user_ids=_split_csv(os.getenv("GM_USER_IDS", "")),
            bot_username=os.getenv("BOT_USERNAME"),
            rng_seed=int(os.getenv("RNG_SEED", "20260629")),
            run_telegram=os.getenv("RUN_TELEGRAM", "").casefold() in {"1", "true", "yes"},
            reaction_mode=os.getenv("REACTION_MODE", "interactive").casefold(),
        )


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())

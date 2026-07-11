from __future__ import annotations

from typing import Any

from .campaign_pack import CampaignPackDefinition
from .map_gen import starter_tactical_graph, starter_zone_graph


def starter_campaign_pack() -> CampaignPackDefinition:
    """Build a deterministic Tier 1 starter campaign pack."""
    zones = starter_zone_graph()
    zones["ruins"]["tactical_graph"] = starter_tactical_graph().to_dict()
    zones["ruins"]["event_ids"] = ["starter.generated_loose_stones"]
    zones["ruins"]["encounter_id"] = "kobold_watch"

    return CampaignPackDefinition(
        campaign_id="starter_generated",
        title="边境遗迹",
        version="0.1.0",
        rules_version="srd-5.2.1",
        start_zone_id="start",
        zones=zones,
        outline=starter_outline(),
        encounters={
            "kobold_watch": {
                "name": "Kobold Watch",
                "budget": {
                    "party_size": 4,
                    "party_level": 1,
                    "difficulty": "low",
                },
                "reward_id": "starter.first_victory",
                "monsters": [
                    {
                        "monster_id": "srd.kobold",
                        "name": "Kobold Warrior",
                        "count": 1,
                        "cr": 0.125,
                        "actions": ["srd.kobold_dagger"],
                    }
                ],
            }
        },
        rewards={
            "starter.first_victory": {
                "gold": 12,
                "experience": 50,
                "items": [],
            }
        },
        events={"starter.generated_loose_stones": loose_stones_event()},
        attribution=[
            "Includes mechanics compatible with SRD 5.2.1 under CC-BY-4.0; see NOTICE.",
        ],
    )


def starter_outline() -> dict[str, Any]:
    return {
        "mainline": "边境营地请求队伍调查遗迹入口的异动，并确认塌陷宝库是否安全。",
        "chapters": [
            {
                "id": "camp_to_ruins",
                "title": "从营地到遗迹",
                "zone_ids": ["start", "ruins"],
            },
            {
                "id": "collapsed_vault",
                "title": "塌陷宝库",
                "zone_ids": ["vault"],
            },
        ],
        "npcs": [
            {
                "id": "mara",
                "name": "Mara",
                "role": "营地联络人",
            }
        ],
        "objectives": [
            "调查遗迹入口。",
            "处理遗迹入口的 Kobold watch。",
            "确认塌陷宝库是否仍可通行。",
        ],
        "endings": [
            "队伍带回遗迹安全情报。",
            "队伍撤回营地并报告需要更多支援。",
        ],
    }


def loose_stones_event() -> dict[str, Any]:
    return {
        "id": "starter.generated_loose_stones",
        "name": "Loose Stones",
        "source": "Generated starter campaign pack",
        "rules_version": "srd-5.2.1",
        "trigger": {
            "type": "zone_entry",
            "zone_id": "ruins",
        },
        "automation": [
            {"type": "target", "mode": "explicit"},
            {
                "type": "saving_throw",
                "ability": "dex",
                "dc_ref": "starter.generated_loose_stones.dex_save",
                "dc_table": {
                    "starter.generated_loose_stones.dex_save": 12,
                },
            },
            {
                "type": "damage",
                "dice": "1d6",
                "damage_type": "bludgeoning",
                "save_half": True,
            },
            {
                "type": "text_result",
                "text": "Loose stones tumble from the ruined archway.",
            },
        ],
        "audit_label": "Loose Stones",
    }

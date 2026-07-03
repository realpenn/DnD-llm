# DnD-LLM

DnD-LLM 是一个以确定性规则引擎为唯一真相、由 LLM 承担 DM 裁决与叙事的 Telegram 文字跑团项目。

当前代码实现了 `tasks.md` Phase 1 的可玩闭环：Core 状态模型、确定性骰子、审计/存档、Automation DSL、规则校验器、Tier 1 compendium 覆盖、编排器、Telegram 适配层、LLM-DM 工具门面、战役包/角色编辑，以及探索→事件→战斗→存读档→读档后继续战斗的本地 playtest。后续阶段已补入多职业/专长编辑基础、6–20 级成长与 9 环槽位恢复、SRD 5.2.1 Tier 1 怪物 stat block 动作、部分 SRD 高环法术、SRD 药水物品动作、Alert 先攻加值、持续效果生命周期、交互式反应窗口、CR 预算自动化、运行时动态地图扩展、长期记忆检索、角色成长回写与角色库持久化、模型用量统计、Telegram 观战模式和多群多战役隔离运行时等增量能力。

## 快速验证

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
ruff check .
ruff format --check .
mypy src/dnd_llm
python -m dnd_llm
```

## 许可

源代码使用 Apache-2.0。SRD 派生规则数据、战役包内容和相关文本使用 CC-BY-4.0；详见 `NOTICE`、`LICENSE`、`LICENSE-CONTENT.md` 与 `LICENSE-THIRD-PARTY`。

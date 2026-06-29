# DnD-LLM：由 LLM 担任 DM 的 Telegram 文字跑团

> 状态：Final v1.0 · 最后更新 2026-06-29

## 1. 项目概述

一个在 Telegram 群里进行的文字版 D&D 跑团游戏。LLM 担任 DM（地下城主），
负责裁决与叙事；一个确定性规则引擎持有全部游戏状态与掷骰计算；一个内容生成
组件产出剧情与地图。群友通过自然语言组队冒险，由 LLM 依据 D&D 5e 规则与剧本
推进游戏。

### 核心设计原则

1. **引擎是唯一真相（Single Source of Truth）。** 所有机械数字（HP、AC、掷骰、
   伤害、金币、位置、状态）只由规则引擎产生和修改。**运行时 LLM-DM 永远不创造、
   不修改、不推断权威机械数字**；它只决定"做什么动作/检定"、选择难度档位或引用
   预定义 DC，并把引擎工具返回的数字与后果翻译成叙事。内容生成组件可以产出含
   DC、奖励、遭遇预算等数字的候选战役包，但只有通过 `RuleDataValidator` 与 GM 审核后，
   才能固化为运行时可引用的规则/战役数据。
   这是防止 LLM 作弊/幻觉的根本机制。
2. **运行时 LLM-DM 通过工具调用（function/tool calling）与引擎交互。** DM 的每个
   机械动作最终都转化为一次对引擎工具函数的调用，由引擎裁决后返回结构化结果。
3. **规则动作数据驱动。** Core 不把每个法术/动作/陷阱硬编码成 Python 分支；
   法术、职业能力、怪物动作、物品、危害与战役事件都定义为已校验的
   `ActionDefinition` / automation tree，由确定性 `AutomationExecutor` 执行。
   LLM-DM 只能触发这些已登记动作并提供有限参数，不能运行时生成任意效果树。
4. **结构化状态 + 叙事摘要 双轨记忆。** 引擎持有结构化状态（精确、可回放）；
   LLM 侧维护滚动剧情摘要（用于叙事连贯）。两者都进入存档。
5. **确定性可回放。** 给定同一存档 + 同一随机种子/roll counter + 同一玩家动作序列 +
   同一 DM 工具调用序列 + 同一规则数据版本，引擎结果完全可复现（便于调试、S&L、
   反作弊审计）。
   LLM 的裁决本身不要求重新生成一致，而是通过审计日志记录其工具调用与参数。

### 关键决策（已确认）

| 维度 | 选择 |
|------|------|
| 规则体系 | D&D 5e SRD 5.2.1（架构全量设计，实现分阶段，见 §9） |
| 规则实现 | 数据驱动 Automation DSL + `AutomationExecutor`；DM 工具只触发已校验动作 |
| 规则数据 | `Compendium` / `rules_data` 持有 SRD 职业、法术、怪物、物品、状态、危害与动作定义 |
| 骰子 | 使用 `d20`，魔改/封装为可注入 RNG、可按 seed + roll counter 确定性回放 |
| 触发方式 | 特殊前缀 + @bot 触发 DM；战斗进入回合制，由 bot 点名 |
| MVP 范围 | 单战役 + 完整 Tier 1 核心循环（探索 → 战斗 → 存读档） |
| 数字边界 | 运行时 LLM-DM 不创造/修改/推断权威机械数字，只复述引擎工具结果；内容生成数字须先校验固化 |
| 工具边界 | DM 工具不开放裸状态修改；直接改状态能力仅限内部/GM 管理工具 |
| 技术栈 | Python（telegram-bot + OpenAI 兼容 SDK/client），技术栈保持可替换 |
| 模型接口 | OpenAI 兼容 API（`base_url` / API key / model id 可配置；DM、摘要、内容生成可用不同模型） |

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Telegram 群 / 私聊                        │
└───────────────┬──────────────────────────────┬──────────────┘
                │ 消息（自然语言 / 指令）         │ 私密信息（暗骰/密信）
                ▼                              ▲
┌─────────────────────────────────────────────────────────────┐
│  Telegram 适配层 (Bot Gateway)                                │
│  · 消息门控（前缀 / @bot / 指令）  · 用户↔角色映射             │
│  · 群 channel ↔ 私聊 channel       · 速率限制 / 队列          │
└───────────────┬─────────────────────────────────────────────┘
                │ 规范化事件 (PlayerIntent)
                ▼
┌─────────────────────────────────────────────────────────────┐
│  游戏编排器 (Orchestrator / Session Manager)                  │
│  · 战役会话状态机（探索 / 战斗 / 过场）                        │
│  · 回合调度 / 行动经济 / 会话锁 / 事件队列                     │
│  · 把 PlayerIntent 路由给 DM，组装上下文                       │
└──────┬───────────────────────────────────┬──────────────────┘
       │ 上下文 + 工具定义                   │ 工具调用结果
       ▼                                   ▲
┌──────────────────────────┐   tool call   ┌──────────────────────┐
│  LLM-DM 组件              │──────────────▶│  规则引擎 (Core)      │
│  · 裁决：选动作/检定难度    │◀──────────────│  · 唯一游戏状态        │
│  · 叙事：翻译引擎结果      │   结构化结果   │  · Automation Executor │
│  · 调用内容生成（Phase 3）│               │  · d20 RollService     │
└──────────┬───────────────┘               │  · 状态机/状态效果     │
           │                               │  · 存读档 / 审计日志   │
           │                               └──────────┬───────────┘
           │                                          │ 读取已校验规则数据
           ▼                                          ▼
┌──────────────────────────┐              ┌──────────────────────┐
│  内容生成组件 (Content Gen)│              │ Compendium / Rule Data│
│  · 战役/区域/NPC/遭遇      │              │ · SRD 法术/职业/怪物   │
│  · 地图（zone/tactical graph）│          │ · ActionDefinition    │
│  · 奖励表 / 事件定义       │              │ · Hazard/Event 定义    │
└──────────┬───────────────┘              └──────────┬───────────┘
           │ 战役包 JSON + 校验后事件定义             │
           ▼                                          ▼
                                      ┌──────────────────────┐
                                      │  数据存储 (State Store)│
                                      │  · 战役/角色/世界状态  │
                                      │  · 剧情摘要/审计日志    │
                                      └──────────────────────┘
```

---

## 3. 组件职责

### 3.1 规则引擎（Core，确定性，不含 LLM）

**持有全部权威状态，对外只暴露受规则约束的工具函数。**

状态对象：
- `Character`：属性值（STR/DEX/CON/INT/WIS/CHA）、调整值、职业/等级/熟练加值、
  HP/临时 HP/生命骰、AC、速度、技能熟练、豁免熟练、装备/物品栏、法术位、状态效果、
  位置（探索期 `zone_id`；战斗期另有关联 combatant 的 `position_node_id`）、金币、经验。
- `Monster/NPC`：5e stat block 子集。
- `Encounter`：参战实体、先攻顺序、当前回合指针、地形/区域、轻量战术位置图
  （Encounter Tactical Graph）。
- `WorldState`：当前 zone、已触发事件标记、门/开关/陷阱状态、时间。
- `SessionConfig`：战役配置（如 `pvp_enabled=false`、`friendly_fire=confirm`、公开/私密展示策略等）。

Phase 1 不使用格子地图，但战斗必须有比 zone 更细的确定性位置抽象：
- `zone_id` 表示宏观探索位置；进入战斗后，编排器为该 zone 生成或读取一个
  **Encounter Tactical Graph**。
- 如果 Tactical Graph 在运行时按模板生成，生成结果必须写入 Encounter 权威状态与审计日志；
  任何随机模板/节点选择必须通过 `RollService` seeded RNG（计入 roll counter）。回放时优先
  使用存档中的图，必要时才按 seed + counter 重新生成。
- `PositionNode` 表示战斗内可站位点（如门口、左侧平台、祭坛旁、后排掩体），至少包含
  `node_id`、显示名、标签、可容纳阵营/实体约束、默认 cover/terrain 信息。
- node 之间的边记录 `distance_ft` / movement cost / line_of_sight / cover /
  difficult terrain 等机械信息。Core/Resolver 用图上的最短路径与 LOS/cover 标记确定
  距离、视线、遮蔽和可达性。
- 每个 combatant 持有 `position_node_id`；`move` 节点消耗 movement budget 后把 combatant
  从一个 node 移到另一个 node。强制位移也落在 node 迁移上。
- "左侧""最近""刚攻击过我"等自然语言标签仅是 target affordance 与解析辅助；机械判断
  一律以 Tactical Graph 中的 node、边、距离、LOS 与 cover 为准。

Core 内部由四层组成：
- **State Model**：权威状态对象与状态不变量。
- **Compendium / Rule Data**：SRD 职业、法术、怪物、物品、状态、危害、基础动作与战役包
  事件定义。规则文本与规则效果数据不散落在业务代码里。
- **Automation DSL + Executor**：把已校验的 `ActionDefinition` / `HazardDefinition` /
  `EventDefinition` 编译为 automation tree，由执行器结算攻击、豁免、伤害、治疗、
  状态、资源消耗、持续时间与行动经济。
- **Tool Facade**：暴露给 LLM-DM 的高层工具。工具只接收 actor、target、action id、
  slot level、可校验 hazard params 等有限参数，再转交 Executor；LLM-DM 不直接操作状态，
  也不能运行时提交任意 automation tree。

工具函数分两层：**DM 可调用工具**只表达规则动作或战役包中已定义的事件；**内部/GM
管理工具**可以直接改状态，但不作为 LLM-DM 的开放入口。

DM 可调用工具（供 LLM-DM 调用，全部由引擎裁决并写状态）：
- `roll_check(actor_id, ability|skill, difficulty_tier|dc_ref, advantage?)` → Core 将标准难度档位
  或预定义 DC 引用解析为实际 DC，返回成功/失败 + 骰值明细
- `roll_save(actor_id, ability, difficulty_tier|dc_ref, advantage?)` → 同上
- `attack(attacker_id, target_id, action_id|weapon_id)` → 加载已定义攻击动作，结算命中、
  伤害与附带效果
- `cast_spell(caster_id, spell_id, targets, slot_level)` → 加载 `SpellDefinition.automation`，
  校验法术位/目标/行动经济后结算
- `use_item(actor_id, item_id, targets?)` → 加载物品动作定义，校验物品、次数、目标并结算效果
- `move(actor_id, to_zone_id?|to_position_node_id?)` → 探索期校验 zone 连通性；战斗期校验
  Tactical Graph 可达性、movement budget、离开 reach 触发的借机攻击候选
- `interact(actor_id, feature_id, intent)` → 门、机关、陷阱、NPC 交互等战役包定义对象
- `trigger_event(event_id, actor_ids?, targets?)` → 执行战役包中已校验的事件 automation
- `apply_hazard(target_ids, hazard_type, params)` → **即兴/环境危害**（仅限 SRD 5.2.1
  Hazards 与 Environmental Effects，如坠落、窒息、燃烧、脱水、饥饿、极端冷热、
  深水、强风等）。DM 只提供类型与**可校验参数**（如来自 zone feature 的坠落高度
  30 尺），参数必须来自地图/战役包/玩家声明或规则允许的离散选项；伤害/效果由引擎按
  SRD 5.2.1 标准规则计算——仍是规则绑定，不是任意数字。
  这是为了支持真实桌游式的涌现叙事（见 §3.1.3）。
- `award(actor_ids, reward_id)` → 只能发放奖励表中已定义的奖励
- `request_combat(participants)` / `request_end_combat()` → DM **请求**进入/结束战斗；
  实际先攻与回合推进由编排器执行（见下方"轮次控制"）。

关于 DC：运行时 LLM-DM 不直接提交任意数值 DC。自由裁量检定使用标准
`difficulty_tier`（如 very_easy / easy / medium / hard / very_hard / nearly_impossible），
由 Core 按规则表映射为实际 DC；陷阱、机关、战役事件、法术与怪物能力等已有规则来源的
场景使用 `dc_ref` 或 action/event automation 中预定义的 DC。所有最终 DC 都进入审计日志。

> **轮次控制归编排器，不是 DM 工具。** `roll_initiative` / `advance_turn` /
> 回合指针由编排器（orchestrator）**确定性独占驱动**，DM 不能调用，避免 LLM
> 跳过/乱序某玩家回合。DM 只负责"轮到谁时这一回合做什么"的裁决与叙事。
> 存读档（`save_game`/`load_game`）也不是 DM 工具：自动存档由编排器触发，
> 手动存读档为 GM 指令（见 §7.1）。

内部/GM 管理工具（不开放给 LLM-DM 任意调用）：
- `apply_damage(target_id, dice|amount, type, source_ref)` / `apply_healing(...)`
- `apply_condition(target_id, condition, duration, source_ref)` / `remove_condition(...)`
- `modify_inventory(actor_id, item, delta, source_ref)` / `transfer_item(...)`
- `save_game(slot)` / `load_game(slot)` → 编排器自动存档 + GM 指令调用。
- `gm_override(...)` → 仅 GM 显式命令可触发，必须写入审计日志。

#### 3.1.1 Automation DSL / Executor

Core 的规则效果以数据定义，而不是散落在工具函数里的硬编码分支。

`ActionDefinition` 基本 schema：
- `id` / `name` / `localization`（中文/英文标准名、少量常用 aliases）/
  `source` / `rules_version`
- `action_type`：weapon_attack / spell / class_feature / item / monster_action /
  base_action / hazard / campaign_event
- `action_economy`：action / bonus_action / reaction / movement / free / none
- `range` / `target_policy` / `requirements` / `friendly_fire_policy`
- `cost`：法术位、物品次数、资源点、弹药、材料等
- `automation`：由节点组成的效果树
- `audit_label`：审计日志展示与回放定位用标签

MVP automation 节点：
- `target`：选择 self / each / all / explicit targets / area targets；area targets 由
  Tactical Graph 上的目标 node / 中心 combatant + shape/radius/line/cone 等参数确定命中集合
- `attack_roll`：命中骰、优势/劣势、重击/大失败、AC 对比
- `saving_throw`：豁免属性、DC、成功/失败分支
- `ability_check`：属性/技能检定、DC、成功/失败分支
- `damage` / `healing` / `temp_hp`：骰式、伤害类型、抗性/免疫/易伤、治疗上限
- `condition`：添加/移除状态，生成 `EffectInstance`
- `resource_delta`：法术位、职业资源、物品次数、金币/奖励等
- `move`：探索期 zone 级移动；战斗期 Tactical Graph node 级移动、强制位移、速度消耗
- `branch`：按命中/豁免/检定/状态/资源条件分支
- `text_result`：仅用于给叙事层的结构化提示，不改变权威状态

`EffectInstance` 是运行时状态效果实例，至少记录：
- `effect_id` / `source_ref` / `source_action_id`
- `target_id` / `applied_by`
- `condition` 或被动修正（AC、豁免、技能、速度、抗性、伤害加值等）
- `duration`、`tick_on`（自身回合开始/结束、施法者回合、固定轮次等）
- `concentration`、`stacking_policy`、`parent_effect_id` / `child_effect_ids`
- `remove_conditions` 与审计信息

行动经济由编排器与 Core 共同强制：
- 每个战斗回合有 action、bonus action、reaction、movement、object/free interaction 等预算。
- 借机攻击与反应消耗 reaction；战斗中移动若让 actor 从敌方 reach 覆盖的 node 离开到
  不再被该敌方 reach 覆盖的 node，则触发借机攻击候选。回合开始/结束重置或 tick
  对应预算与效果。
- `ActionDefinition.action_economy` 与当前回合预算不匹配时，Executor 拒绝执行。

规则数据必须先通过 `RuleDataValidator`：
- schema 校验：字段、节点类型、target policy、friendly fire policy、cost、source、rules version、
  Tactical Graph node/edge 字段。
- 规则校验：法术环位、职业等级、动作经济、状态名称、伤害类型、SRD 来源。
- 本地化/别名校验：检查 alias 归一化后的意外冲突；合理重名保留为运行时
  `ambiguous` 候选，不在加载期强行报错。
- 安全校验：运行时 LLM-DM 不能提交或修改 automation tree；只有开局前已校验的
  Compendium 数据与 GM 审核后的战役包事件可以执行。

#### 3.1.2 骰子与确定性回放

骰子表达式采用 `d20`，但必须魔改或封装为项目自己的确定性 `RollService`：
- 每个战役/存档持有 `rng_seed` 与单调递增 `roll_counter`。
- 每次掷骰生成 `roll_id`，记录 dice expression、seed、counter、advantage/disadvantage、
  每颗骰子的原始骰面、保留/丢弃状态、总值与展示字符串。
- 回放时优先使用 seed + counter 重新计算；若 `d20` 版本升级导致格式或算法差异，
  可退回使用审计日志中的骰面结果重放。
- 所有 `roll_check`、`attack_roll`、`saving_throw`、`damage` 等节点都只能通过
  `RollService` 掷骰，不能直接调用随机数。

#### 3.1.3 关于 `apply_hazard`（即兴危害的受控通道）

用 LLM 当 DM 的核心价值就是还原真实桌游的临场感，因此环境/涌现危害必须有合法路径，
但不能退化成"LLM 凭空报伤害"。`apply_hazard` 的约束：
- 只接受**预定义的危害类型**：SRD 5.2.1 的 Hazards 与 Environmental Effects。
  DM 不能自定义伤害公式，也不能把任意环境叙事塞进 `apply_hazard`。
- hazard params 必须可追溯到地图/战役包/玩家声明或规则允许的离散选项；运行时
  LLM-DM 不能临场编造任意高度、持续时间、强度等级或其他会改变机械结果的数值。
- 每个 hazard type 映射到已校验的 `HazardDefinition.automation`；伤害骰、上限、
  相关豁免与持续效果全部由 Executor 按标准规则计算。
- 每次调用写审计日志（含 hazard_type、params、引擎结算结果）。
- 与战役包预定义的 `trigger_event` 互补：可预设的危害走 `trigger_event`，
  临场涌现的标准危害走 `apply_hazard`。
- 酸池、雷击、挤压机关、落石、岩浆等**非 SRD 标准 hazard/environmental effect**
  不走 `apply_hazard`；它们必须作为战役包事件预先定义 DC、豁免、伤害骰/效果、
  触发条件与奖励/后果，再由 DM 通过 `trigger_event(event_id, ...)` 触发。

**不变量（引擎强制，LLM 无法绕过）：**
- HP 不会变成负伤害治疗 / 法术位为 0 时无法施法 / 移动必须沿 zone 边（探索期）或
  Tactical Graph 边（战斗期）/ 奖励必须来自 `award` 且经过校验 / 任何状态变更都有
  审计日志条目。

### 3.2 LLM-DM 组件（裁决 + 叙事）

- **输入：** 玩家意图、当前结构化状态摘要、相关剧本/地图节点、近期剧情摘要、
  可用工具定义。
- **输出（两类）：**
  1. **意图解析 / 裁决草案**：把玩家的自然语言行动映射为结构化草案
     （如动作/法术名称、可选 `candidate_action_id`、目标描述、难度档位/优势劣势建议）。
     草案必须经过 Orchestrator + Core `ActionResolver` / Validator 审核后，才可转为
     工具执行。
  2. **叙事**：拿到引擎结构化结果或审核驳回原因后，生成符合语气的中文叙事，
     并明确告知后果或不可执行原因。
- **绝不**：自行编造骰值/HP/掉落；越权修改状态；给规则不允许的奖励。
- DM 的"裁量空间"在于：决定是否需要检定、选择标准难度档位或引用战役包预定义 DC、
  判断优势/劣势、描述世界、扮演 NPC、推进剧情节奏——而非直接创造数字本身。
- **隐藏信息隔离**：进入 LLM-DM 叙事/裁决上下文的状态必须先经过可见性过滤。怪物精确
  HP/AC/抗性、未公开线索、其他玩家私密状态等隐藏信息默认只留在 Core 与审计日志中；
  DM 上下文只拿展示层允许的模糊状态。玩家自由文本一律视为不可信输入，不能提升其
  可见性，也不能诱导 DM 泄漏私密状态；工具返回给群聊的结果同样按 channel 可见性过滤。

#### 3.2.1 工具调用校验与纠错回路

主要风险在于 LLM 输出的草案或工具参数可能不可解析或不合法；而模型接口为任意
OpenAI 兼容后端（§11.24），不同后端的 tool-calling 保真度差异大，弱模型常给出
不存在的 `action_id`、角色不具备的法术、错误的 slot level 或非法目标。

**预防优先于纠错：** 在**战斗模式**下，编排器为当前行动者预注入 eager-compact 动作
affordances（见 §5），让 LLM 从"现在合法能做什么"里选，从源头压低 reject 率，而不是
事后反复纠错。下面的纠错回路是**兜底**，不是主路径。

玩家动作采用**两段式解析与审核**：
1. LLM-DM 先把自然语言解析为结构化 `PlayerActionDraft`，例如 actor、intent type、
   法术/动作名称、可选 `candidate_action_id`、目标描述、声明文本、难度档位等；这一步
   只做意图理解，不产生权威规则效果。
2. 编排器调用 Core `ActionResolver` / Validator，对草案做确定性审核：角色是否拥有该动作、
   是否准备/已知该法术、法术位/资源是否足够、行动经济是否允许、目标/距离/视线是否合法。
   `candidate_action_id` 只是**路由提示，不是授权**：Resolver 必须照常校验 id 是否存在、
   是否属于当前 actor、当前状态是否合法、资源/行动经济/目标是否合法；幻觉 id 与其他
   非法动作一样会被打回。
3. 审核结果只有三类：
   - `accepted`：解析到合法 `ActionDefinition` 与参数，交给 Executor 结算。
   - `rejected`：非法，返回结构化原因（如"玩家没有火球术"），LLM 只负责转述。
   - `ambiguous`：目标或动作有歧义，返回少量候选项，请玩家澄清；需要显式确认的场景
     （如 `friendly_fire=confirm` 导致的 `confirm_required`）归入 `ambiguous` 子型。

Executor / Resolver 校验失败后的处理：
- Executor 返回**结构化错误**（错误码 + 原因 + 该 actor 当前**合法可选项**，
  如可用动作 id、可用法术位、合法目标）。
- 编排器把错误与合法可选项**回喂 DM 重试**，让其修正参数或改选动作。
- **重试有硬上限**（默认 1 次，可配）。重试过多会显著拖慢游玩节奏、破坏体验，
  因此**不做无限纠错**。
- 超过上限仍失败 → **降级**：提示该玩家换一种说法，或将该动作标记为待 GM 介入，
  绝不让引擎执行未通过校验的效果。
- 每次失败、重试、降级都写入审计日志（含错误码与最终处置）。

### 3.3 内容生成组件（剧情 + 地图）

- 产出**结构化数据**（引擎/编排器可直接读的 JSON），不是纯散文。这里由 LLM 生成的是
  **候选战役包**，不是运行时权威状态；其中涉及 DC、奖励、数量、遭遇预算等机械数字时，
  必须先通过 `RuleDataValidator` 与 GM 审核，固化后才可被运行时引用。
- 生成物：
  - **战役大纲**：主线、章节、关键 NPC、目标、结局条件。
  - **地图 = Zone Graph**：节点（房间/区域，含描述、出口、内含遭遇/物品/陷阱），
    边（通道，含连通条件如"需钥匙/需 DC15 力量"）。
  - **战斗战术图 = Encounter Tactical Graph**：对可能发生战斗的 zone 预设或按模板生成
    `PositionNode` 与边，标注 distance、LOS、cover、difficult terrain 等机械信息。
  - **遭遇**：怪物组合、难度（按队伍等级算 CR 预算）、战术倾向。
  - **奖励表**：每个遭遇/宝箱的 XP/金币/物品池。
  - **环境/事件定义**：陷阱、酸池、雷击、落石、挤压机关、岩浆等非标准危害，
    必须在战役包中预定义 DC、豁免、伤害骰/效果、触发条件、审计来源与
    `EventDefinition.automation`。
- **候选战役包由 LLM 生成**，再由 GM 用**自然语言修改**（LLM 解析修改意图并改写战役包，
  改写结果仍是结构化 JSON）。战役包必须先通过 `RuleDataValidator`，包括 schema、
  zone 连通、Tactical Graph 连通/距离/LOS/cover 合法性、CR 预算、奖励表、
  事件 automation、SRD 来源、非 SRD 内容边界等校验。
  校验通过且 GM 审核后才可被运行时 `trigger_event` 执行。
- MVP：战役包在**开局前**生成并校对好存为 campaign pack，运行时由 DM 读取；
  运行中**实时**动态生成留到后续阶段（见 §9）。架构图中 LLM-DM 到 Content Gen 的调用
  表示 Phase 3 能力，不是 MVP 默认运行路径。

---

## 4. 多人 & 回合模型（群聊核心难点）

游戏在两种模式间切换，由编排器状态机管理：

同一战役/群在任意时刻只允许一个事件提交写状态。编排器维护 session lock、事件队列
与 idempotency key，确保重复消息、Telegram 重试或并发工具调用不会重复扣资源/造成乱序。

### 4.1 探索 / 社交模式（自由）
- 群友自由用自然语言发言。
- **DM 触发门控**（避免每条消息都烧 LLM）：
  - 消息以**前缀 `DD`** 开头（区分大小写，不要求空格）→ 视为游戏行动，路由给 DM。
  - 消息 **@bot** → 直接向 DM 提问/行动。
  - 其余闲聊不触发 DM（但可被收集进"近期发言"上下文，供 DM 在下次响应时参考）。
- DM 可在一次响应里综合处理多名玩家的近期行动，按叙事节奏推进。

### 4.2 战斗模式（严格回合制）
- DM `request_combat` 后，**编排器**掷先攻、排定顺序并独占管理回合指针
  （轮次控制不在 DM 手里，见 §3.1）。
- **bot 主动点名**：轮到某玩家时，编排器让 bot 在群里 @该玩家，提示其行动。
- 该玩家用前缀/＠bot 声明行动 → DM 裁决 → 引擎结算 → 编排器推进到下一位。
- 轮到某 PC 时，编排器为其预注入 **eager-compact 动作 affordances**（当前合法动作的
  `action_id` + 中文名 + 消耗 + 目标类型，见 §5），让 LLM 从合法集里映射玩家自然语言，
  从源头压低 reject 率；玩家仍自由打字，菜单只进 LLM 上下文。
- 同时注入当前可见目标的精简 affordances（`target_id`、显示名、阵营/敌我、
  `position_node_id`、相对标签、模糊状态），帮助 LLM 把"左边的无头怪""那个残血的"
  "刚打我的"映射为候选目标；目标仍由 Resolver 二次校验。
- 战斗中的距离、视线、遮蔽、可达性、最近/左侧等相对标签均由 Encounter Tactical Graph
  计算。近战、远程、法术射程与 AoE 不依赖叙事文本猜测；Resolver 按 actor 的
  `position_node_id`、目标 node/combatant、边距离、LOS/cover 与 `ActionDefinition.range`
  确定是否合法。
- AoE 以目标 node 或目标 combatant 为中心，结合 action 的 shape/radius/line/cone 等
  target policy 在 Tactical Graph 上计算命中集合；玩家可声明意图，最终波及对象由 Core
  确定并写入审计日志。
- Core 为当前 combatant 建立回合预算：action、bonus action、reaction、movement、
  object/free interaction。`ActionDefinition.action_economy` 消耗预算；预算不足时拒绝。
- **Phase 1 支持 reaction 预算与非交互式反应策略，但不做交互式反应窗口。**
  在异步 Telegram 群里，于某玩家回合中途停下来开"是否触发反应"窗口并等待另一玩家响应，
  会打断回合流、易卡局。Phase 1 采用预声明/自动反应策略：玩家可在私聊配置借机攻击、
  反应法术、资源消耗阈值与优先级；未配置时，非资源型低风险反应可自动执行，
  消耗法术位/关键资源的反应默认不自动使用。完整交互式反应窗口（含超时、提示、插队确认）
  留到 Phase 2。实际触发、命中/豁免、资源消耗仍由 Core Executor 结算并写审计日志。
- 同类怪物支持共享 stat block + 独立 combatant instance（独立 HP、状态、位置），
  可按 group initiative 统一排序和点名。
- 超时机制：超时时长设置得**较宽松**（默认可配，建议较长，给真人留出反应时间）。
  超时后**由 LLM 接管该角色这一回合**——DM 以符合该角色性格/处境的方式替其行动
  一回合（而非简单"防御/跳过"），结算后继续推进。这样既不卡局，又保持叙事连贯。
- **NPC/怪物回合的行动来源分两档**：
  - **常规小怪 = 确定性战术库**，不走 LLM（省成本/延迟）。为每类怪物预定义**多套
    可行战术**（如"扑向最近的低 HP 目标普攻""集火施法者""被压制则后撤找掩护"等），
    每回合先按战场条件、目标可达性、资源、行动经济、状态效果过滤出当前合法战术，
    再从合法战术中用 **seeded weighted choice** 选择一套执行。该选择必须经
    RollService 的 seeded RNG（计入 roll counter），以保持确定性回放——不得用裸
    `random`。
  - **首领/特殊怪 = LLM 驱动**，由 DM 依其战术倾向与战场态势即兴决策；编排器向
    LLM-DM 注入该怪物当前合法动作的精简版 affordances（action id、名称、消耗、
    目标类型、简短效果标签），不注入完整规则文本。
  - 两档最终都通过工具 facade / `ActionDefinition` / 行动经济结算，受同一套规则约束。

### 4.3 PvP 与友军误伤
- Phase 1 默认 `pvp_enabled = false`：玩家不能把其他 PC 作为有害动作、攻击、法术、
  推搡、危害触发或其他负面效果的直接目标。Resolver 遇到这类草案时返回 `rejected`，
  除非 GM 明确开启 PvP 或使用带审计的 GM override。
- 玩家制造的 AoE / area targets 默认 `friendly_fire = confirm`：若 Core 计算出的命中集合
  包含 allied PC，Resolver 返回 `ambiguous/confirm_required`，列出会被波及的友方目标；
  玩家明确确认后才执行。可配置为 `off | confirm | raw`：`off` 表示玩家 AoE 不得波及
  allied PC（要求改目标/站位或拒绝），`confirm` 表示确认后执行，`raw` 表示按规则直接执行；
  MVP 默认 `confirm`。
- 怪物/NPC 的 AoE 与环境/战役事件按规则正常波及 PC，不需要玩家确认；但仍受
  target policy、Tactical Graph、可见性与审计日志约束。
- 治疗、帮助、解除状态等有益动作可以以 allied PC 为目标；若动作同时含负面效果，
  以 `target_policy` / `friendly_fire_policy` 的更严格规则为准。

### 4.4 用户 ↔ 角色映射
- **角色管理在 bot 私聊（DM channel）中进行**，不在群里。
- 一个用户可以**创建并持有复数角色**（角色库），但在一局游戏中**只能使用其中一个**
  （active character）。
- **角色创建**：bot 私聊先给一套**默认模板**（预设职业/属性数组）；玩家可用
  **自然语言修改**（由 LLM 解析意图），但所有修改**必须落在 5e 规则内**——
  LLM 解析后交由**规则引擎校验**（属性点数/职业合法性/起始装备等），越界则拒绝并说明。
- **入队**：`/join` → 从角色库选择一个 active character 绑定到当前战役。
- **角色随游戏成长**：所用角色的 XP/等级/物品/状态变更持久化回该用户的角色库，
  下次仍可继续使用。
- 私密信息（暗骰结果、单独密信、个人物品栏）通过 **bot 私聊** 发送，不进群。

### 4.5 公开 / 私密状态展示
- PC 的完整角色卡、物品栏、暗骰、私密线索默认走私聊；群内只展示必要的行动结果。
- PC 精确 HP/资源可由玩家本人私聊查看；群内 `status` 默认展示摘要，可配置为精确或模糊。
- 怪物 HP/AC/抗性默认由 GM 可见；群内可配置为隐藏、模糊（Healthy/Injured/Bloodied/Critical）
  或精确，MVP 默认模糊展示。
- 审计日志保存完整信息，展示层只做可见性过滤，不影响权威状态。

---

## 5. 记忆与上下文管理

战役会越来越长，必须防止 context 爆掉：

1. **结构化状态**（引擎持有）：永远精确，按需注入"当前相关切片"（当前 zone、
   在场实体、本人角色卡），而非全量历史。
2. **滚动剧情摘要**：每完成一个场景/章节，用 LLM 把发生过的事压缩成结构化摘要
   （已达成目标、重要 NPC 关系、未决线索、玩家重要抉择）。注入 DM 上下文。
3. **近期对话窗口**：最近 K 条群内相关消息原文。
4. **动作 affordances（必需）**：编排器/Core 可为任意 actor 解析出其**已登记、当前合法的
   `ActionDefinition` id 列表**（结合已知/已准备法术、剩余法术位、装备武器、职业特性、
   行动经济、目标可达性等）。注入 DM 上下文的策略**按 actor 类型 + 游戏模式区分**：
   - 玩家角色（**按模式分**）：
     - **战斗模式 → eager-compact**：为**当前行动者**注入一份紧凑、已按实时状态过滤的
       可用动作 affordances（`action_id` + 中文名 + 消耗 + 合法目标类型，**不含规则文本**）。
       这份"现在合法能做什么"本就由 `ActionResolver` 计算，顺手输出即可。LLM 应优先把
       选中的动作 id 回填到 `PlayerActionDraft.candidate_action_id`，让热路径从"中文名→id
       模糊匹配"降为"验证这个 id 是否存在且当前合法"，因为弱后端正是最容易在战斗里编错动作的。
       `candidate_action_id` 只是路由提示，Resolver 仍必须二次校验，不能把它当授权。
     - **探索模式 → lazy**：不注入动作清单。玩家自由输入自然语言（多落到
       `roll_check` / `interact`），LLM-DM 解析为 `PlayerActionDraft` 后由 `ActionResolver`
       审核；仅在驳回/歧义/纠错时返回少量合法候选。
     - 权威 alias 表放在 Compendium / localization 层（每个动作维护中文/英文标准名与少量
       常用别名），供探索模式、菜单缺失、纠错兜底与名称回退时做归一化。战斗菜单保持
       lean，不默认展开 aliases；仅在标准中文名不直观或极易混淆的少数动作上内联 1-2 个
       短别名。
     - 两模式下执行时 resolver 均**二次校验**，菜单过期也不会放过非法效果；玩家始终可
       自由打字，菜单只进 LLM 上下文、不作为选择题甩给玩家。
   - 首领/特殊怪：因由 LLM-DM 代为决策，注入精简版合法动作 affordances（action id、
     名称、消耗、目标类型、简短效果标签）。
   - 常规小怪：不注入 LLM 上下文；内部战术库先条件过滤，再 seeded weighted choice。
5. **目标 affordances（战斗必需）**：战斗模式下为当前行动者注入当前可见目标的紧凑列表：
   `target_id`、显示名、阵营/敌我、`position_node_id`、相对标签（如左侧、最近、
   刚攻击过我）、模糊状态（Healthy/Injured/Bloodied/Critical 等）。相对标签由
   Tactical Graph 与最近事件派生，只用于解析辅助。LLM 可把玩家的目标描述解析为候选
   `target_id`，但目标合法性、距离、视线、遮蔽与死亡/不可选中状态仍由 Resolver 校验。
6. **检索（后续）**：长战役可引入向量检索，按当前情境召回相关历史片段。

进入 DM 的上下文由以下切片拼接：系统提示（DM 人格 + 规则要点）、战役大纲切片、
当前 zone/遭遇、在场角色卡摘要、**当前行动者的精简动作 affordances**（战斗模式必注，
探索模式按需）、当前可见目标 affordances（战斗模式必注）、滚动剧情摘要、近期消息与
工具定义。

---

## 6. 存读档（S&L）

- **存档 = 引擎结构化状态 + 剧情摘要 + 随机种子/roll counter + 事件计数 +
  审计日志引用**
  （保证可回放）。
- 自动存档：每次战斗结束、进入新 zone、章节切换。
- 手动存档：`/save <slot名>`；读档 `/load <slot名>`。
- 存档格式：JSON（人可读、可 diff、便于调试）。
- 审计日志：所有引擎状态变更追加写入事件日志，可用于回放与反作弊核查。
  日志至少记录玩家原文、标准化 `PlayerIntent`、DM 工具调用名与参数、工具结果、
  `ActionDefinition` / automation node path、骰子表达式与骰面、随机事件计数、
  idempotency key、模型 id、prompt/schema 版本、规则数据版本、战役包版本与调用时间。

---

## 7. Telegram 交互设计

### 指令（确定性、不走 LLM）
- `/start`、`/help`
- 角色管理（**私聊**）：`/newchar`（从默认模板创建）、`/mychars`（角色库列表）、
  `/usechar <id>`（设为 active）、`/sheet`（查看角色卡）
- `/join`、`/leave`（用 active 角色加入/退出当前战役）
- `/roll <表达式>`（如 `/roll 1d20+5`，纯工具）
- `/status`（当前场景/回合状态）
- GM 专用（见 §7.1）：`/newcampaign`、`/save`、`/load`、`/saves`、`/kick`、`/forceturn`

### 自然语言（走 DM）
- **前缀触发：`DD`** 开头视为游戏行动（**区分大小写**，只认大写 `DD`；**不要求**
  其后带空格，`DD我推开石门` 与 `DD 我推开石门` 均触发）。例：`DD我推开那扇石门，警惕地查看房间`
- @bot 触发：`@DnDBot 我想说服守卫放我们进去`
- 私聊中的自然语言（如改角色）由 LLM 解析 → 引擎校验 → 应用。

### 7.1 GM / 房主权限
- 每个战役有一名 **GM（房主）**，通常是开局者。
- GM 专属能力：`/newcampaign`（加载/生成战役包并开局）、存读档（`/save` `/load`
  `/saves`）、`/kick <user>`（移除玩家）、`/forceturn`（战斗中强制推进/跳过卡住的回合）。
- 普通玩家无上述权限；引擎在执行这些操作前校验调用者是否为该战役 GM。

### 私密 channel
- 暗骰、个人密信、角色卡详情 → bot 私聊用户。
- 玩家需先 `/start` 私聊过 bot，否则提示去私聊激活。

---

## 8. 技术栈与目录结构

- **语言：** Python 3.11+
- **Telegram：** `python-telegram-bot`（async）
- **模型接口：** OpenAI 兼容 SDK/client；`OPENAI_BASE_URL`、`OPENAI_API_KEY`、model id
  均可配置。DM 裁决、摘要、内容生成可分别配置不同模型。
- **存储：** MVP 用 SQLite + JSON 文件；后续可换 Postgres。
- **配置：** 环境变量（BOT token、OpenAI 兼容 API key/base URL、模型 id）+ 战役包目录。

建议目录：
```
dnd-llm/
├── spec.md
├── core/                 # 规则引擎（确定性，纯函数 + 状态）
│   ├── models.py         # Character / Monster / Encounter / WorldState
│   ├── dice.py           # d20 RollService（可注入 RNG，可回放）
│   ├── automation/
│   │   ├── definitions.py # ActionDefinition / HazardDefinition / EventDefinition
│   │   ├── executor.py    # AutomationExecutor
│   │   ├── nodes.py       # target / attack_roll / save / damage / condition 等节点
│   │   └── effects.py     # EffectInstance 生命周期
│   ├── compendium/
│   │   ├── loader.py      # 加载 rules_data 与战役包事件
│   │   ├── localization.py # 中文/英文标准名、aliases 与名称归一化
│   │   └── validators.py  # RuleDataValidator
│   ├── rules/            # 5e 规则 helper：检定/攻击/豁免/状态/休整
│   ├── positioning.py    # Encounter Tactical Graph、距离/LOS/cover/AoE/可达性
│   ├── resolver.py       # PlayerActionDraft → ActionDefinition/目标/参数的确定性审核
│   ├── economy.py        # action / bonus action / reaction / movement 预算
│   ├── tools.py          # 暴露给 LLM 的工具 facade
│   └── persistence.py    # 存读档 + 审计日志
├── rules_data/           # 已校验规则数据（SRD only）
│   ├── srd/
│   │   ├── actions.json
│   │   ├── classes.json
│   │   ├── spells.json
│   │   ├── monsters.json
│   │   ├── conditions.json
│   │   ├── hazards.json
│   │   └── items.json
│   └── schemas/          # JSON Schema / 版本化规则数据 schema
├── dm/                   # LLM-DM 组件
│   ├── adjudicator.py    # 裁决：意图→工具调用
│   ├── narrator.py       # 叙事：结果→文本
│   ├── prompts/          # 系统提示 / DM 人格
│   └── context.py        # 上下文组装 + 记忆/摘要
├── content/              # 内容生成
│   ├── campaign_gen.py
│   ├── map_gen.py        # zone graph / encounter tactical graph
│   └── packs/            # 战役包 (JSON, LLM 候选生成 + 人工校对)
├── orchestrator/         # 编排器 / 会话状态机
│   ├── session.py        # 探索/战斗状态机
│   ├── turn.py           # 先攻/点名/超时
│   ├── queue.py          # 事件队列、session lock、idempotency
│   └── router.py         # PlayerIntent 路由
├── telegram_bot/         # Telegram 适配层
│   ├── gateway.py        # 消息门控 / 队列
│   ├── commands.py
│   └── channels.py       # 群 vs 私聊
└── tests/                # 引擎确定性回放 + compendium 自动模拟测试为重点
```

---

## 9. SRD 实现的分期策略

架构按 **D&D 5e SRD 5.2.1** 设计（数据结构、状态机预留全量空间），但实现分阶段，
保证 MVP 能跑通核心循环而不被规则全量拖死：

这里的 Phase 指**可玩范围**，不是每日开发任务粒度。第一版对外可玩的版本仍要足够完整；
工程实现可以拆成更细的编程里程碑，但不把初始可玩范围缩成玩具 demo。

- **Phase 1（MVP，完整的 Tier 1 游戏）**
  > 可玩范围扩大但仍有界：目标是"**完整的 Tier 1（1–5 级）跑团体验**"，而不是
  > 缩成 4 职业 3 级的玩具 demo。
  - 引擎：属性/调整值、熟练、AC、HP、生命骰、优势/劣势、技能/豁免检定、
    各伤害类型、死亡豁免、专注（concentration）、Automation DSL + Executor、
    确定性 `d20` RollService。
  - 职业：**SRD 5.2.1 全部基础职业**（各含 SRD 提供的子职），等级 **1–5**，
    3 级选子职；多职业/专长留到 Phase 2。职业能力以 `ActionDefinition` /
    automation 定义。
  - 法术：**1–3 环全部 SRD 5.2.1 法术 + 戏法**，以及**全部核心状态**
    （中毒/眩晕/倒地/束缚/目盲/魅惑/恐慌/麻痹等）。法术效果以
    `SpellDefinition.automation` 定义。
  - 战斗：先攻、回合、探索期 zone 级移动、战斗期 Tactical Graph node 级移动（非格子）、
    动作/附赠动作/反应、
    **借机攻击、额外攻击**、基础动作（攻击/施法/闪避/脱离/冲刺/帮助/躲藏）、
    行动经济预算、非交互式反应策略、休整（**短休/长休**）。
  - 环境/即兴危害：`apply_hazard`（仅 SRD 5.2.1 Hazards 与 Environmental Effects）。
  - 内容：**LLM 候选生成 + GM 自然语言修改**的单战役包（一条主线、若干 zone、
    数个遭遇、奖励表、事件 automation），开局前定稿并通过校验。
  - 角色：默认模板 + 自然语言修改（引擎校验）；私聊管理；角色库（单 active）+ 成长持久化。
  - 跑通：探索 → 战斗 → 存读档，一队真人玩一段完整 Tier 1 冒险（单群单战役）。

  建议工程里程碑（不降低上述可玩范围，只是实现顺序）：
  1. Core 骨架：数据模型、确定性 `d20` RollService、审计日志、存读档。
  2. Automation DSL：`ActionDefinition` schema、节点模型、Executor、`RuleDataValidator`。
  3. 规则核心：检定、豁免、攻击、伤害、抗性/免疫/易伤、状态、专注、休整、行动经济。
  4. Compendium：SRD 基础动作、危害、状态、怪物、全部基础职业 1–5 级、
     1–3 环法术 + 戏法的数据与 automation。
  5. Orchestrator：探索/战斗状态机、Encounter Tactical Graph 装载/生成、先攻、
     回合推进、非交互式反应策略、事件队列、超时接管。
  6. Telegram：群/私聊 channel、指令、`DD` 门控、用户↔角色映射、公开/私密展示。
  7. LLM-DM：工具调用裁决、叙事、摘要、越权防护。
  8. Content/角色：战役包生成与校验、事件 automation、默认角色模板、自然语言改角色。
  9. 测试与 Alpha：compendium 自动模拟、确定性回放测试、单群单战役完整 playtest。

- **Phase 2（拓展规则：Tier 2+）**
  - 等级 6+（更高环法术、更多子职特性）、多职业、专长。
  - 完整交互式反应窗口（含超时、提示、插队确认与默认行为）。
  - 更多魔法物品、状态持续时间与并发的精细化管理。
  - 难度/CR 预算自动化。

- **Phase 3（动态内容）**
  - 内容生成组件实时产出剧情与地图（zone graph / tactical graph 动态扩展），DM 即兴成团。
  - 长战役向量检索记忆。

- **Phase 4（体验与运营）**
  - 多战役并行、观战、角色成长持久化、并发/超时与速率精细化、成本监控。

---

## 10. 关键风险与对策

| 风险 | 对策 |
|------|------|
| 运行时 LLM-DM 作弊/幻觉数字 | 引擎为唯一真相；运行时 LLM-DM 只能调工具，不能改状态；内容生成数字须校验固化；审计日志可回放核查 |
| 群聊并发混乱 | 状态机分模式；战斗严格回合+点名+超时；探索期门控触发 |
| Context 爆掉 | 结构化状态切片 + 滚动摘要 + 近期窗口（+ 后续向量检索） |
| 成本/延迟 | 门控触发；次要任务用更省模型；摘要压缩历史；缓存战役包 |
| 大型战斗 LLM 成本/延迟 | 小怪走确定性战术库（条件过滤 + seeded weighted choice），仅首领/特殊怪由 LLM 驱动 |
| 区域内距离/视线/遮蔽判定悬空 | Phase 1 使用 Encounter Tactical Graph：combatant 挂到 position node，距离/LOS/cover/AoE/借机攻击由图结构确定性计算 |
| 弱后端 tool-call 不可靠 | 战斗预注入 eager-compact 合法动作与目标 affordances，并让 LLM 回填可选 `candidate_action_id`；Resolver 二次校验，Compendium/localization alias 用于 lazy/兜底名称归一；Executor 结构化报错回喂；**有限重试**（默认 1 次）后降级，绝不执行未校验效果 |
| 玩家恶意 PvP / 友军误伤争议 | 默认 `pvp_enabled=false`；玩家 AoE 友伤默认 `friendly_fire=confirm`；GM override 与配置变更必须审计 |
| 玩家嘴炮骗奖励 | 奖励只能经 `award` 且受奖励表约束；DM 提示中明确边界 |
| SRD 5.2.1 规则量过大 | 按等级分期：MVP 落完整 Tier 1（1–5 级），架构留全量空间，高层规则后置 |
| 法术/职业硬编码失控 | 用 Automation DSL + `ActionDefinition` 数据化规则效果；先做 Executor，再填 compendium |
| Automation 规则 bug 难发现 | 每个 compendium 动作做自动模拟；关键规则做确定性回放测试与快照测试 |
| `d20` 魔改后不可回放或升级漂移 | 固定版本/维护 fork；`RollService` 记录 seed、counter 与骰面，必要时按骰面重放 |
| 即兴叙事 vs 数字管控冲突 | `apply_hazard` 只放行 SRD Hazards 与 Environmental Effects，且 hazard params 必须可追溯/可校验；其他环境伤害必须走战役包事件 |
| 群聊重复提交/并发写状态 | 每战役 session lock + 事件队列 + idempotency key；状态提交串行化 |
| 私密信息泄漏 | 暗骰/密信走 bot 私聊 channel，绝不进群 |
| LLM 上下文泄漏隐藏信息 / Prompt Injection | DM 上下文默认只注入展示层可见状态；精确隐藏值留在 Core/审计日志；玩家自由文本视为不可信输入，不能提升可见性或诱导泄漏 |
| 许可证污染 | 分层许可证：代码 Apache-2.0，SRD/默认原创内容 CC-BY-4.0，第三方义务进 `NOTICE` / `LICENSE-THIRD-PARTY`；Avrae 仅作架构参考，不复制 GPL 代码/数据；`d20` 保留 MIT notice |

---

## 11. 已定决策

1. **规则体系 = D&D 5e SRD 5.2.1**；架构按全量 SRD 5.2.1 预留，实现分期落地。
2. **数字边界**：运行时 LLM-DM 不创造、不修改、不推断权威机械数字；只能选择动作、
   检定、难度档位或预定义 DC 引用，并复述引擎工具返回的数字与后果。内容生成组件可提出
   含数字的候选战役包，但必须经 `RuleDataValidator` 与 GM 审核后固化，运行时才可引用。
3. **工具边界**：DM 可调用工具只表达规则动作或战役包事件；`apply_damage` 等裸状态修改
   能力仅限内部规则系统或带审计的 GM 管理工具。工具层是 facade，实际规则效果由
   已校验 `ActionDefinition` / automation 执行。
4. **轮次控制归编排器**：先攻、回合推进、回合指针由编排器确定性独占驱动，
   不作为 DM 工具，避免 LLM 跳过/乱序玩家回合；存读档同理（自动=编排器，手动=GM 指令）。
5. **可回放边界**：引擎回放依赖存档、随机种子/roll counter、玩家动作序列、
   DM 工具调用序列、`ActionDefinition` 版本与审计日志；LLM 裁决不要求重生成一致，
   必须记录到审计日志。
6. **触发前缀 = `DD`**（消息以 `DD` 开头视为游戏行动；**区分大小写**，仅大写 `DD`；
   **不要求**其后带空格）。
7. **战斗超时**：时长设置较宽松（可配，给真人留反应时间）；**超时后由 LLM 接管该角色
   这一回合**（按角色性格/处境替其行动，而非简单防御/跳过）。这是默认桌面规则，
   不再拆成玩家可选的超时策略。
8. **单群单战役**：第一版不允许并行战役。
9. **角色创建/管理**：
   - 私聊（DM channel）中进行；先给**默认模板**，可用**自然语言修改**（LLM 解析 →
     引擎校验，修改必须在 5e 规则内）。
   - 每个用户可创建**复数角色**（角色库），但游戏中**只能用一个 active 角色**。
   - active 角色**随游戏成长**并持久化回角色库。
10. **GM/房主权限**：存在，拥有开局、存读档、踢人、强制推进回合等权限（见 §7.1）。
11. **战役包**：由 **LLM 候选生成**，GM 用**自然语言修改**（LLM 改写 → 引擎校验）。
    战役包事件可包含 automation，但必须先通过 `RuleDataValidator` 与 GM 审核。
12. **首版可玩范围 = 完整 Tier 1**：SRD 5.2.1 全部基础职业、1–5 级、1–3 环全部法术、
    全部核心状态、含借机攻击/专注/休整；扩大范围但仍有界，不缩成玩具 demo（见 §9）。
13. **规则实现 = Automation DSL + Executor**：法术、职业能力、怪物动作、物品、
    基础动作、危害与战役事件都以数据定义，Executor 统一结算。
14. **`ActionDefinition` 为规则动作单位**：包含 source、rules version、localization/aliases、
    action type、action economy、target policy、friendly fire policy、cost、requirements、
    automation 与 audit label。
15. **`cast_spell` / `use_item` / `attack` / `trigger_event` / `apply_hazard` 都执行已定义动作**：
    工具只选择动作、目标和有限参数，不承载具体规则分支。
16. **`EffectInstance` 记录状态生命周期**：持续时间、tick 时机、专注、叠加策略、
    父子效果、来源与解除条件都进入权威状态和审计日志。
17. **骰子 = `d20` 魔改/封装为确定性 `RollService`**：支持注入 RNG，以 seed +
    roll counter 回放，并记录每颗骰面的审计数据。
18. **规则数据 = Compendium / `rules_data`**：SRD 职业、法术、怪物、物品、状态、
    危害、基础动作与 schema 版本化维护，不散落在业务代码中。
19. **测试策略**：每个 compendium 动作必须能自动模拟并 JSON 序列化；关键战斗流程、
    骰子与存读档必须有确定性回放测试。
20. **并发策略**：单战役写状态串行化，使用 session lock、事件队列与 idempotency key。
21. **公开/私密状态**：完整状态在引擎与审计日志中保存；群内展示按可见性策略过滤。
22. **怪物实例/分组**：同类怪物共享 stat block，combatant instance 独立 HP、效果与位置；
    支持 group initiative。
23. **分层许可证**：项目源代码采用 Apache-2.0（根 `LICENSE`）；SRD 派生规则数据与
    默认原创示例内容采用 CC-BY-4.0（`LICENSE-CONTENT.md`）；第三方署名与依赖义务集中在
    `NOTICE` / `LICENSE-THIRD-PARTY`。Avrae/avrae 只作架构参考，不复制 GPL 代码或数据；
    可使用或 fork MIT 许可的 `d20`，但必须保留第三方署名与修改记录。
24. **模型接口 = OpenAI 兼容 API**：LLM 仍作为产品/架构概念使用；具体调用层采用
    OpenAI 兼容 SDK/client，支持配置 `base_url`、API key 与 model id。
25. **工具调用纠错有上限**：Executor 校验失败时回喂合法可选项让 DM 重试，但重试有
    硬上限（默认 1 次，可配），超限即降级（换措辞/待 GM 介入），绝不执行未校验效果。
    重试过多会拖慢节奏、损害体验（见 §3.2.1）。
26. **玩家动作两段式解析与审核**：玩家可自由输入自然语言；LLM-DM 先解析为
    `PlayerActionDraft`（可带 `candidate_action_id` 作为路由提示），再由 Core
    `ActionResolver` / Validator 确定性审核为 `accepted` / `rejected` / `ambiguous`，
    通过才交给 Executor。`candidate_action_id` 不是授权，必须照常校验存在性、归属、
    合法性、资源、行动经济与目标（见 §3.2.1）。
27. **动作 affordances 按 actor + 模式注入**：玩家角色——**战斗模式 eager-compact**
    预注入当前行动者的紧凑合法动作（action_id + 中文名 + 消耗 + 目标类型），从源头压低
    reject 率并绕过热路径中文名→id 模糊匹配；战斗菜单保持 lean，不默认展开 aliases，
    只在易混动作内联 1-2 个短别名。**探索模式 lazy**，不预注入，仅在驳回/歧义/纠错时
    返回少量候选；权威 alias 表放在 Compendium / localization 层，用于 lazy/兜底名称归一。
    首领/特殊怪注入精简合法 affordances；常规小怪不注入 LLM，由内部战术库处理。
    两模式执行时 resolver 均二次校验（见 §5 / §3.2.1 / §4.2）。
28. **小怪确定性战术，首领 LLM 驱动**：常规小怪用预定义的多套确定性战术，每回合先
    条件过滤，再经 **seeded weighted choice** 选一套（计入 roll counter、保持回放）；
    首领/特殊怪由 LLM 即兴决策。
    两档都经工具 facade / 行动经济结算（见 §4.2）。
29. **Phase 1 反应 = 非交互式策略**：Phase 1 支持 reaction 预算、借机攻击与反应法术的
    预声明/自动反应策略；不在 Telegram 群里开交互式反应窗口。完整交互式反应窗口留到
    Phase 2（见 §4.2 / §9）。
30. **战斗目标 affordances**：战斗模式下为当前行动者注入当前可见目标的紧凑列表
    （target_id、显示名、阵营/敌我、position_node_id、相对标签、模糊状态），帮助 LLM
    把自然语言目标描述映射为候选目标；相对标签只作解析辅助，目标合法性、距离、视线、
    遮蔽与死亡/不可选中状态仍由 Resolver 基于 Tactical Graph 校验。
31. **LLM 不直接提交任意数值 DC**：自由裁量检定由 LLM 选择标准 `difficulty_tier`，
    Core 映射为实际 DC；陷阱、机关、战役事件、法术与怪物能力使用 `dc_ref` 或 automation
    中预定义 DC。最终 DC 由 Core/规则数据确定并写入审计日志。
32. **战斗定位 = Encounter Tactical Graph**：探索期位置仍是 `zone_id`；战斗期每个
    combatant 持有 `position_node_id`，Encounter 持有 `PositionNode` 与带 distance/LOS/cover/
    terrain 信息的边。Resolver/Core 用该图确定距离、视线、遮蔽、可达性、AoE 命中集合与
    借机攻击触发；"左侧""最近"等自然语言标签不是机械依据。
33. **PvP 与友军误伤默认策略**：Phase 1 默认 `pvp_enabled=false`，PC 不能直接把 allied PC
    作为有害动作目标；玩家制造的 AoE / area targets 默认 `friendly_fire=confirm`，会波及
    allied PC 时需玩家确认。可配置为 `off | confirm | raw`：`off` 要求改目标/站位或拒绝，
    `confirm` 确认后执行，`raw` 按规则直接执行；怪物/NPC AoE 按规则正常波及 PC。

### 待后续阶段细化（非阻塞）

- 战斗超时的具体默认分钟数。
- 角色库容量上限、删除/改名等管理操作。
- 审计日志的长期保留、归档、压缩与裁剪策略。
- 长战役向量检索记忆的接入时机（Phase 3）。
- 多战役并行与跨群（Phase 4）。

---

## 12. 许可证与署名

- **项目源代码**：采用 **Apache License 2.0**，见根目录 `LICENSE`。这覆盖项目代码、
  代码文档、配置模板与不含 SRD 内容的工程性实现。
- **SRD 派生规则数据**：`rules_data/srd/**`、SRD 派生 compendium、SRD 派生规则文本与
  automation 定义采用 **CC-BY-4.0**，见 `LICENSE-CONTENT.md`。项目使用 SRD 5.2.1 内容
  （职业、法术、状态、怪物、危害规则等）**必须逐字附带下列官方署名声明**：

  > This work includes material from the System Reference Document 5.2.1
  > ("SRD 5.2.1") by Wizards of the Coast LLC, available at
  > https://www.dndbeyond.com/srd. The SRD 5.2.1 is licensed under the Creative
  > Commons Attribution 4.0 International License, available at
  > https://creativecommons.org/licenses/by/4.0/legalcode.

- 在仓库（如 `NOTICE` / `LICENSE-CONTENT.md` / `LICENSE-THIRD-PARTY` / 战役包元数据）中**逐字**保留上述
  SRD 5.2.1 归属文本；分发战役包/角色数据时一并保留。
- 不额外添加其他 Wizards、D&D Beyond 或其关联方署名，避免偏离官方 attribution 要求。
- 仅使用 SRD 5.2.1 开放内容，**不引入**非 SRD 的版权材料（特定设定、未开放的子职/法术等）。
- **原创内容**：项目自带的原创示例战役包、原创 NPC、原创地图、原创文本默认采用
  **CC-BY-4.0**；若某个 pack 的元数据或所在目录另行声明许可证，则以更具体声明为准。
  商业/私有战役包可另行授权，但不得混入未获授权的非 SRD D&D 内容。
- **第三方 notices**：集中维护在 `NOTICE` 与 `LICENSE-THIRD-PARTY`。新增依赖、vendor、
  fork 或修改第三方代码/数据时，必须同步记录许可证、版本、copyright notice 与本地修改。
- Avrae/avrae 项目仅作为架构与产品经验参考；其主仓库为 GPL-3.0，不复制其代码、
  数据文件或受限实现到本项目，避免许可证污染。
- `d20` 骰子库为 MIT 许可；若直接依赖、fork 或魔改，必须保留 MIT 许可声明、
  copyright notice，并在第三方许可文件中记录修改内容与版本。

# MatchLens AI — Architecture Evolution & R0.2 Capability Audit

## 1. 当前 R0.2 代码级能力审查（10 项系统性诊断）

基于真实仓库代码（`services/api/matchlens/*` 与 `apps/web/app/*`）及 R0.1/R0.2 实验记录，对当前系统进行十项核心审查：

1. **Football Event Schema 的扩展边界**
   - **现状**：`football.py` 中 `Event` 为不可变 Pydantic 模型，包含 `id, seq, t (0..720), kind (restart|pass|recovery|shot|end), team (H|N), actor, receiver, start, end, outcome (complete|saved|goal)`。
   - **边界与局限**：Schema 简洁且具备极强的确定性校验能力，但 `kind` 暂不支持未完成传球（incomplete pass / turnover pass）或定位球细分，且缺少派生属性（如传球推进距离 `progressive_distance`、区域标签）。R1 可在不破坏现有字段与 `extra="forbid"` 的前提下，在 `reduce_match` 富化阶段（`enriched` 字典）及独立序列构建器中派生空间与序列属性，保持原始 `Event` 100% 向后兼容。

2. **Reducer 是否适用于多场景、多球队**
   - **现状**：`reduce_match` 已经对称处理 `H` 与 `N` 的球权转移、扑救后门将持球（`other(team)+"1"`）、进球后中圈开球（`pending_restart`）及球门线坐标校验（`attack_x == 105`）。
   - **结论**：Reducer 本身**完全支持双队与多场景**。局限在于 `generate_match` 目前仅支持 `default`（1-0）与 `stalemate`（0-0）且阶段列表（`phases`）写死，需抽离为可扩展的 `ScenarioConfig` 与生成器驱动。

3. **哪些指标和候选检测存在 Harbor FC (`H`) 硬编码**
   - **现状排查**：
     - `football.py:L240`：`metric_receipts` 虽然循环 `for team in TEAMS` 生成了 `H.*` 和 `N.*` 的窗口指标，但进球收据只生成了 `H.goals.match`，缺失 `N.goals.match`（以及双队通用全场指标）。
     - `football.py:L259-263`：`freeze` 中的 `candidate` 问题字符串硬编码了 `"Harbor"` 与 `receipts["H.transition_shots.current"]`、`state["score"]["H"]`。
     - `football.py:L274`：`tool_evidence` 过滤了 `if k.startswith("H.")`，导致客队 `N.*` 的指标收据虽已计算却被挡在 Agent 工具视野之外！
     - `football.py:L292-348`：`detect_moments` 只检查 `H.possession`、`H.shots`、`H.entries`、`H.high_recoveries`，且进球候选 `metric_keys` 写死 `["H.goals.match"]`。
     - `contracts.py:L63-69, L84-94, L145-169`：`REQUIRED`、`assertion_supported`、`evidence_summary` 全部硬编码 `H.` 前缀与 `"Harbor"` 名称。
     - `MetricComparison.tsx:L69-70` 与 `EvidenceDrawer.tsx:L160`：前端组件硬编码读取 `H.${m}.previous` 和 `.filter(r => r.id.startsWith("H."))`。

4. **当前 Assertion Enum 如何限制推理表达能力**
   - **现状**：`Assertion` 仅含 5 个字面量，且绑定主队单向判断。
   - **局限**：无法表达客队洞察、双队对比（如“主队控球占优但客队反击更具威胁”）、球员个体贡献、连续序列特征或自定义窗口比较。需要演进为带 `subject`（`H | N | match | player`）与参数化 `ClaimPlan` 的结构化表达。

5. **`bound-facts-v1` 的安全收益及表达局限**
   - **安全收益**：彻底消除了模型自由文本中常见的数字幻觉、跨窗口張冠李戴（如把上一窗口射门算进当前窗口）和违禁因果词，保障了 100% 事实一致性。
   - **表达局限**：完全用固定模板覆盖模型输出会削弱对特定序列细节、球员配合和用户追问的回答针对性。R2 应升级为 **`bound-facts-v2`（组合式受控事实槽位 + 受验证的结构化观测子句）**，既保留确定性数值与窗口绑定，又允许表达多球队、多假设与具体序列特征。

6. **Analyst / Verifier 是否具有真实独立职责**
   - **现状**：在 `agents.py` 中，Analyst 与 Verifier 是两个独立的 MAF `Agent` 实例，通过 `WorkflowBuilder` 串联，各自强制调用 `get_evidence` 工具并验证 SHA-256 回执。
   - **局限**：目前两者看到的是完全相同的 `tool_evidence` 载荷，且 Verifier 只能输出单次 `publish | qualify | withhold`。在 R2 中，应赋予 Verifier 专门的**反证检索与窗口敏感度工具**，使其在 Hypothesis Lab 和 User Challenge 中发挥真正的对抗性审查作用。

7. **Agent Tools 能否支持动态查询**
   - **现状**：仅有 `get_evidence(snapshot_id)` 和 `get_event_chain(event_ids)` 两个静态读取工具。
   - **局限**：不支持按球队、球员、空间区域、进攻序列或自定义时间窗口进行受控参数化查询。

8. **Snapshot、Epoch、Cache 是否可用于用户挑战及跨时间窗口分析**
   - **现状**：`Snapshot` 采用规范化 JSON + SHA-256 内容寻址；`Session` 具备 `epoch` 递增隔离与 `saved_runs` 历史重验导入机制。
   - **结论**：这套机制**设计极佳，可直接复用并扩展**。只需在 `Snapshot` 中纳入 `team_scope` / `window_spec`，并在 Challenge 流程中引用原 `snapshot_id` 与 `claim_id` 构建版本链，即可完美支撑跨窗口分析与质疑演化。

9. **UI 的现有组件是否支持模块扩展**
   - **现状**：R0.2 已拆分为 `Scoreboard`、`ReplayControls`、`MatchTimeline`、`MatchStage`、`MetricComparison`、`InsightSpotlight`、`EvidenceDrawer`、`BroadcastOverlay`、`EventFeed`、`MatchRecap` 10 个清晰组件，且具备统一的 `tokens.css` / `globals.css`。
   - **局限**：`page.tsx` 目前将所有状态平铺在一个双列网格中；若直接堆砌 R1–R3 的所有新面板会导致页面拥挤。需要引入**上下文工具栏（Scenario / Team Context Selector）**与**工作区标签页（Pitch Explorer / Sequences & Players / Hypothesis & Challenge / Broadcast Studio）**，实现渐进式信息披露。

10. **哪些技术债务会影响后续所有功能**
    - **首要技术债**：`H.` 球队前缀在指标收据、候选检测、Agent 工具、合约校验、前端组件中的全链路硬编码。必须在 R1 第一步通过参数化 `focus_team: Team` 与双队完整收据（含 `N.goals.match`）彻底解耦。
    - **次要技术债**：单一固定场景生成器与固定两窗口（180s/180s）假设。

---

## 2. 当前能力矩阵（R0.2 Baseline Capability Matrix）

| 能力模块 | 状态分类 | 当前代码真实状态说明 |
| :--- | :--- | :--- |
| 连续合成赛事与确定性 Reducer | **Implemented & Verified** | 12 分钟（720s）合法事件流生成、球权区间计算、比分与球门范围校验（50 项 pytest 通过）。 |
| 事件边界动态候选检测 (Auto Candidate Detection) | **Implemented with Limitations** | `detect_moments` 已实现按事件边界触发并锁定快照时间，但仅检测 Harbor FC (`H`) 且仅限 4 类固定条件。 |
| MAF 双 Agent 链路与预算账本 (Analyst + Verifier + Ledger) | **Implemented & Verified** | 真实 DeepSeek Flash 调用、工具回执校验、同会话一次格式修正、SQLite `$0.02` 预扣费与 6 请求准入检查。 |
| 历史真实运行重验导入 (Historical Run Loader) | **Implemented & Verified** | 启动时校验 `.runtime/runs/*.json` 的 canonical snapshot 哈希与当前 Gate，兼容展示 `Historical real analysis`。 |
| 证据抽屉与球场事件高亮 (Evidence Drawer & Pitch Map) | **Implemented & Verified** | 原生 `<dialog>` 模态框、焦点捕获、公式展示、事件坐标检视，但下拉框过滤了 `H.`。 |
| 观众双视角切换 (Fan / Analyst Mode) | **Implemented with Limitations** | 零额外推理成本切换同一批准结论的展示密度，但尚不支持按关注球队/球员定制与 Producer 视角。 |
| 多场景合成赛事引擎 (Multi-Scenario Engine) | **Implemented with Limitations** | 仅支持 `default` 与 `stalemate` 两种微调尾声的场景，缺乏独立战术情节配置（控球压制、防反、逆转等）。 |
| 双队对称智能与球队切换 (Both-Team Intelligence) | **Requires Refactoring** | 底层计算了部分 `N.*` 指标，但工具、检测、合约、UI 均硬编码 `H.`，需重构为参数化双队支持。 |
| 交互式战术探索器 (Tactical Explorer) | **Missing** | 仅有最近 6 个事件箭头展示，缺失传球网络（Passing Network）、推进传球、区域分布与抢断位置图层。 |
| 连续控球序列分析 (Possession Sequence Explorer) | **Missing** | 仅有进球回溯链，缺失通用连续控球序列（`PossessionSequence`）构建、推进距离计算与序列回放。 |
| 球员聚焦分析 (Player Spotlight) | **Missing** | 仅有球员名字字典映射，无球员参与度、推进贡献、序列参与统计及个人事件时间线。 |
| 自定义时间窗口对比 (Compare Match Windows) | **Missing** | 仅固定对比 `(t-360, t-180]` 与 `(t-180, t]`，不支持任意合法窗口选择与对比。 |
| 结构化声明规划与假设实验室 (Typed Claim Plan & Hypothesis Lab) | **Missing** | 仅支持 5 个固定枚举与单一候选解释，不支持多竞争性假设检验。 |
| 交互式质疑与修订时间线 (Challenge Flow & Revision Timeline) | **Missing** | 当前 Challenge 按钮仅打开静态证据抽屉，无交互式质疑复核契约与判断修订历史。 |
| 受约束赛事问答与证据缺失顾问 (Ask the Match & Evidence Gap Advisor) | **Missing** | 无自然语言/结构化提问入口及针对缺失数据（如无球跑动/阵型）的系统性解释顾问。 |
| 个性化导播与转播工作台 (Director, Story, Producer Workbench & Export) | **Implemented with Limitations / Missing** | 仅有基础 `BroadcastOverlay` 预览与 `MatchRecap` 列表，缺失 Producer 审校队列、故事编排与 SVG/PNG/JSON 导出。 |
| 赛事数据适配器与评测基准 (Match Data Adapter & Benchmark / Ablation) | **Missing** | 生成器与引擎直接耦合；S0/S1/M 对照实验与跨场景 Benchmark 尚未执行。 |

---

## 3. 从 R0.2 到 R4 的平滑演进原则

1. **绝不破坏已有测试与历史收据（Zero Regression on R0.2）**
   - 默认参数 `generate_match(seed=17, scenario="default")` 必须产生与 R0.2 **完全一致的 148 个事件与 SHA-256 快照 ID**，确保 `evidence/r0.2/runs/` 下的真实模型收据继续 100% 通过重验导入。
2. **契约版本化演进（Versioned Contracts）**
   - 保留 `evidence-v1` 与 `bound-facts-v1` 的兼容分支；新增雙队与序列扩展时采用向后兼容的附加字段或显式 `team` 参数（默认 `"H"`），让全部 50 个现有单元测试无缝通过，同时为新能力编写增量测试。
3. **共享核心底座（Shared Core Primitives）**
   - 优先建设 `ScenarioRegistry`、双队对称 `metric_receipts`、`PossessionSequence` 聚合器、`PlayerMetrics` 与 `WindowComparator`，让 Tactical Explorer、Player Spotlight、Dynamic Discovery、Hypothesis Lab 共享同一套确定性计算函数。

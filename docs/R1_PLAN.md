# MatchLens AI — R1 Plan: Generalizable Football Intelligence Engine

## 1. R1 阶段目标

将 MatchLens 从“围绕 Harbor FC 单一默认剧本运转的演示原型”升级为**通用的双队、多场景、空间与连续序列驱动的足球智能引擎（Generalizable Football Intelligence Engine）**。
**核心纪律**：
1. `generate_match(seed=17, scenario="default")` 必须保持与 R0.2 完全一致的事件输出与 Snapshot SHA-256 哈希，确保已有 50 项回归测试与历史真实模型收据 100% 兼容。
2. 任何场景配置（Scenario Configuration）的名称或隐藏阶段标签绝不进入 Agent Prompt 或 Tool 返回值。

---

## 2. 模块设计与纵向切片划分（Vertical Slices）

我们将 R1 划分为 **4 个可独立开发、独立运行、独立验收的纵向切片（Slices R1-S1 至 R1-S4）**：

### Slice R1-S1：Multi-Scenario Engine + Both-Team Intelligence + Dynamic Insight Discovery（本轮立即执行切片）

#### (a) Multi-Scenario Match Engine (4.1)
在 `football.py` 中设计可扩展的 `SCENARIOS: dict[str, ScenarioSpec]` 配置注册表，支持全部 6 类足球战术情节：
1. `default` (**Possession Dominance & Late Breakthrough**)：保留 R0.2 经典赛事（Harbor 中段高控球零射门、随后高位抢断反击、终场前连续 13 事件破门 1–0）。
2. `stalemate` (**Low-Event / Defensive Stalemate**)：保留 R0.2 0–0 闷平回归基线。
3. `counterattack` (**Fast Counterattacking — Away Strike**)：主队 Harbor 长时间控球传导但推进受阻，客队 Northbridge United (`N`) 通过高位或中场断球发起快速直传反击，连续形成快速转换射门并由 `N9 (Alex West)` 攻入致胜球（0–1）。
4. `transitions` (**High Transition Activity**)：双方在中前场频繁发生球权转换（`recovery`），10 秒内快速反击射门频繁交替出现，展现高节奏对攻（1–1）。
5. `balanced` (**Balanced Competitive Match**)：双队控球率接近（约 48%–52%），交替进入进攻三区并各有射门与扑救，考验系统在均衡局势下的审慎判断（1–1）。
6. `comeback` (**Comeback / Momentum Reversal**)：主队早段先失一球（0–1），下半程（360s 后）进攻三区进入与射门显著提升，连入两球完成 2–1 逆转。

#### (b) Both-Team Intelligence (4.2)
彻底解除 `H.` 硬编码：
- **双队完整收据**：在 `metric_receipts` 中同时生成 `H.goals.match` 与 `N.goals.match`，并补充双队各自的推进传球 `H|N.progressive_passes.previous|current` 与控球序列统计。
- **双队工具透明访问**：`tool_evidence(snapshot, focus_team=None)` 返回双队完整 `receipts`（含 `H.*` 与 `N.*`），让 Analyst 与 Verifier 能够基于主客队真实对比数据进行推理，而不仅看主队单边数据。
- **参数化契约与渲染**：在 `contracts.py` 中扩展 `assertion_supported(assertion, snapshot, team="H")` 与 `evidence_summary(assertion, snapshot, team="H")`，支持 `team="H"` 或 `team="N"`（通过 `claim` 或候选上下文自动识别主客队，默认 `"H"` 保证旧测试零破坏）。
- **前端双队上下文切换**：在 UI 增加 `Focus Team` 选择器（`Harbor FC (H)` / `Northbridge Utd (N)` / `Compare Both`），动态驱动 `MetricComparison`、`EvidenceDrawer` 与球场进攻方向指示。

#### (c) Unified `InsightCandidate` & Dynamic Discovery (4.7)
升级 `detect_moments(state)`，对 `H` 与 `N` 双队对称扫描，生成包含统一契约字段的候选列表：
- `id`: 唯一候选 ID（如 `moment-H-possession`、`moment-N-transition`、`moment-goal-E0089`）
- `team`: `"H" | "N"`
- `at`: 触发时间戳（秒）
- `window`: `[start, end]`
- `trigger_type`: `"possession_divergence" | "transition_burst" | "attacking_surge" | "goal_breakthrough"`
- `assertion`: 对应核心断言类型
- `metric_keys`: 关联的 `Receipt` ID 列表
- `supporting_event_ids`: 关键支撑事件 ID 列表
- `evidence_completeness`: `"complete_two_windows" | "single_window" | "match_sequence"`
- `priority`: 优先级排序（1 最高）
- `question`: 启发式候选问题（不含预设结论）

---

### Slice R1-S2：Possession Sequence Explorer (4.4)

将离散事件流聚合为连续的球权序列 `PossessionSequence`：
- **聚合规则**：以同一 `possession_id` 下的连续同队有球事件为单位，识别起点（`restart` / `recovery` / 扑救后门将持球）、传导过程（`pass` 次数、推进距离 `progressive_distance = max(0, attack_x(end) - attack_x(start))`、是否跨过 `attack_x = 70m` 进入进攻三区）与终点结果（`goal` / `saved` / `turnover` / `end`）。
- **输出结构**：`sequence_id, team, players, start_t, end_t, duration, event_ids, pass_count, progressive_distance, entered_final_third, outcome`。
- **UI 交互**：在球场下方或专属标签页提供 **Possession Sequence Explorer**，点击任意序列即可在 SVG 球场上高亮整条连续传递轨迹，并支持逐事件检视。

---

### Slice R1-S3：Interactive Tactical Explorer (4.3)

在 `MatchStage.tsx` 基础上扩展多图层战术探索器，允许用户在 5 种严格基于有球事件的图层间切换：
1. **Live Action & Sequences**：最近动作或当前选中控球序列的矢量轨迹。
2. **Passing Network（传球网络）**：按所选球队（`H` 或 `N`）聚合球员平均触球坐标 `(avg_x, avg_y)` 与队友间完成传球频次（连线粗细），点击节点或连线可过滤对应传球事件。
3. **Progressive Passes & Final-Third Entries**：高亮推進距离 $\ge 15\text{m}$ 或跨越 $x=70\text{m}$（主队）/ $x=35\text{m}$（客队）的穿透性传球。
4. **Ball Recovery Locations**：高亮所选球队夺回球权（`recovery`）的空间分布点及高位抢断线。
5. **Attacking Zone Distribution**：将球场划分为后场、中场、进攻三区（左/中/右通道）展示有球事件密度百分比，**明确标注“基于有球事件位置分布，非 22 人无球阵型或 Pitch Control”**。

---

### Slice R1-S4：Player Spotlight & Compare Match Windows (4.5 & 4.6)

1. **Player Spotlight (4.5)**：
   - 确定性计算每位球员的 `passes_completed`、`progressive_passes`、` progressive_meters`、`final_third_entries`、`recoveries`、`shots`、`goals` 与 `sequence_involvements`。
   - 用户选择任意球员（如 `H8 Eli Park` 或 `N9 Alex West`），即可查看其个人数据卡、参与的关键序列及球场触球落点，绝不捏造无验证公式的主观评分。
2. **Compare Match Windows (4.6)**：
   - 提供通用函数 `compare_windows(events, w1_start, w1_end, w2_start, w2_end, team)`，支持对比任意两个合法时间段（如 `00:00–03:00` vs `03:00–06:00` 或 `06:00–09:00` vs `09:00–12:00`），明确展示窗口时长、有效控球分母及样本不足警告。

---

## 3. R1 阶段验收标准

- **多场景真实验证**：6 个场景均可由 `generate_match(seed, scenario)` 确定性生成并通过 `reduce_match` 全部合法性不变量校验；不同场景呈现出截然不同的比分（1–0, 0–0, 0–1, 1–1, 2–1）、控球分布与候选洞察。
- **双队无死角分析**：切换到客队 `Northbridge United (N)` 时，指标面板、候选发现、传球网络、控球序列与证据抽屉全部准确反映 `N` 的数据与左向进攻坐标（`attack_x = 105 - x`）。
- **向后兼容**：原有 50 项 pytest 100% 通过，新增 R1 专项回归测试全部通过。

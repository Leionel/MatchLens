# MatchLens AI — R2 Plan: Interactive Agent Intelligence

## 1. R2 阶段目标与核心设计哲学

R2 是 MatchLens AI 冲击 **Best Multi-Agent System** 奖项的核心技术创新阶段。
在保持 Microsoft Agent Framework (`WorkflowBuilder` + `Agent`) 双角色架构与严格预算/安全边界的前提下，将系统从“单次被动生成卡片”升级为**支持结构化声明规划（Typed Claim Planning）、竞争性假设检验（Tactical Hypothesis Lab）、交互式用户质疑（Challenge an Insight）与证据缺失顾问（Evidence Gap Advisor）的交互式多 Agent 研究工作台**。

---

## 2. 核心模块设计

### 2.1 Typed Claim Planning (5.1) — 突破固定枚举与自由文本的两难

#### 方案对比与架构选型
| 方案 | 表达能力 | 幻觉与越界风险 | 门控可验证性 | 选型结论 |
| :--- | :--- | :--- | :--- | :--- |
| **A. 纯有限枚举 + 固定模板 (`bound-facts-v1`)** | 低（仅 5 种单队句式） | 极低 | 100% 确定性 | 作为安全退守基线保留，但表达力不足 |
| **B. 自由自然语言生成 + 事后正则过滤** | 极高 | 高（易出现隐蔽因果推断、张冠李戴） | 脆弱，需频繁修补正则 | **拒绝**（违背确定性门控原则） |
| **C. 参数化 Typed Claim Plan (`bound-facts-v2`)** | **高（支持双队、多主体、对立假设、序列与球员锚定）** | **极低（所有数值与关系均由确定性谓词核验）** | **100% 结构化可验证** | **采用（Core Architecture）** |

#### `TypedClaimPlan` 数据契约
```python
class TypedClaimPlan(ClosedModel):
    claim_id: str
    subject_team: Literal["H", "N"]
    subject_player: str | None = None
    assertion: Assertion  # 扩展支持双队与转换/推进/序列类型
    scope: Literal["window", "match", "sequence", "causal"]
    time_window: tuple[int, int]
    supporting_refs: list[str]
    counterevidence_refs: list[str]
    sequence_ids: list[str] = []
    quantitative_facts: dict[str, float | int]
    interpretation: str
    limitations: list[str]
```
Publication Gate 对 `TypedClaimPlan` 执行四层校验：
1. **主体与窗口一致性**：`supporting_refs` 与 `counterevidence_refs` 必须匹配 `subject_team` 和 `time_window`。
2. **核心谓词真值检验**：调用参数化的 `assertion_supported(assertion, snapshot, team=subject_team)`。
3. **反证强制披露**：例如检验控球优势时，必须将射门和进攻三区进入作为 `counterevidence_refs` 显式纳入。
4. **组合式受控事实渲染 (`bound-facts-v2`)**：将通过验证的 `TypedClaimPlan` 渲染为包含精确主客队名、时间窗口、正反证据对比及序列链路的 Fan / Analyst 双视角文本。

---

### 2.2 Tactical Hypothesis Lab (5.2) — 竞争性假设检验

围绕同一比赛快照，生成并检验 **2–3 个具有竞争关系的战术假设（Competing Hypotheses）**，直观展现 Analyst 与 Verifier 的思维碰撞：

| 现象场景 | Hypothesis 1 (表象/直觉假设) | Hypothesis 2 (深层/替代假设) | Hypothesis 3 (过度因果/反事实假设) | Verifier 预期裁决 |
| :--- | :--- | :--- | :--- | :--- |
| **控球率大幅上升** | 控球增加带来了更强的进攻威胁 (`attacking_threat_increased`) | 控球增加但缺乏有效渗透与射门 (`possession_without_penetration`) | 对手主动收缩摆大巴导致控球上升 (无阵型数据) | H1: **Rejected** (反证：射门 2→0)<br>H2: **Supported**<br>H3: **Insufficient Evidence** |
| **连续转换射门** | 高位夺回球权后形成了快速转换射门关联 (`recoveries_followed_by_shots`) | 球队整体执行了成功的协同高位压迫战术 (`recoveries_caused_shots`) | 进攻改善来自慢速阵地战传导 (`possession_build_up`) | H1: **Supported / Qualified**<br>H2: **Rejected / Withheld** (因果越界)<br>H3: **Rejected** (时长 $\le 10\text{s}$) |

- **运行机制**：
  - **Deterministic Hypothesis Matrix（零成本即时预览）**：系统根据当前快照的指标组合，实时列出该时刻的候选假设矩阵及确定性证据支持度。
  - **Live Dual-Agent Deliberation（按需深度核查）**：在预算许可下，Analyst 针对候选假设提交主张，Verifier 逐项核查 `Supporting Evidence`、`Counterevidence`、`Sample Coverage` 与 `Unsupported Causal Leaps`，输出 `Supported | Qualified | Rejected | Insufficient Evidence`。

---

### 2.3 Challenge an Insight & Revision Timeline (5.3 & 5.4)

将原本仅打开证据抽屉的静态按钮，升级为**可改變或限定结论状态的交互式质疑工作流**。

#### `ChallengeContract` 数据契约
```python
class ChallengeRequest(ClosedModel):
    claim_id: str
    snapshot_id: str
    challenge_type: Literal[
        "check_counterevidence",
        "check_comparison_window",
        "examine_sequence",
        "challenge_causal_interpretation",
        "check_sample_sufficiency",
    ]
    user_concern: str | None = None
```

#### 复核裁决状态（Challenge Resolution Outcomes）
- `Maintained`（维持原判）：反证检查确认原结论已充分包含限制条件且核心事实稳固。
- `Narrowed / Qualified`（范围收窄/限定）：例如原结论泛谈窗口表现，经 `check_sample_sufficiency` 质疑后，明确收窄为“仅限 180 秒窗口内的 2 次孤立转换序列，不代表全场趋势”。
- `Withdrawn`（撤回结论）：若原结论在跨窗口对比或反证检验下不成立，明确撤回并展示原因。
- `Inconclusive`（证据不足无法定论）：触发 `Evidence Gap Advisor` 说明缺失的数据维度。

#### Challenge & Revision Timeline (5.4)
- 在前端保存并渲染完整的判断演变树：
  `Initial Analyst Claim (t=06:00, snap-abc)` → `Verifier Gate Approval` → `User Challenge (Type: Causal / Sample Check)` → `Additional Evidence Check` → `Revised Assessment (Maintained / Narrowed)`。
- **反作弊铁律**：对 `t=06:00` 结论的 Challenge **永远只读取 `as_of=360` 的原始 Snapshot**，绝不使用 `t=09:00` 的未来事件来事后诸葛亮地推翻 `06:00` 的判断；若比赛已推进到新时间点，UI 明确区分“基于原窗口证据的复核（Retrospective Audit at 06:00）”与“后续比赛新事件带来的局势变化（Subsequent Match Evolution）”。

---

### 2.4 Ask the Match & Evidence Gap Advisor (5.5 & 5.6)

#### 受约束自然语言/意图入口 (`Ask the Match`)
为了在公开 Demo 中保证 100% 安全性（防止 Prompt 注入、防止超额账单、防止脱离证据胡编），采用 **Constrained Intent + Parameterized Query Plan**：
- 支持 5 类核心战术问题模板与结构化参数（球队 `H|N`、窗口、球员）：
  1. `Why did [Team] create more/fewer chances in this window?`
  2. `Which players and passes built the scoring / dangerous sequence?`
  3. `What changed between the previous and current windows?`
  4. `Was [Team]'s possession supported by shots and final-third entries?`
  5. `Compare Harbor FC and Northbridge United's attacking progression.`
- 执行链路：`User Question → Intent & Scope Resolver → Tool Registry Query (Receipts + Sequences + Players) → Grounded Answer + Evidence Chips + Evidence Gap Check`。

#### Evidence Gap Advisor (5.6)
当用户提问或假设涉及当前有球事件 Schema 无法回答的领域（如“球队阵型是否是 4-3-3？”、“高位逼抢强度如何？”、“这次射门的预期进球 xG 是多少？”、“教练换人意图是什么？”）时，系统输出结构化的四段式诊断：
1. **Available Evidence（已有证据）**：例如“当前窗口记录了 4 次发生在 $x \ge 70\text{m}$ 的球权夺回（`high_recoveries`）和 2 次 10 秒内转换射门”。
2. **Missing Data（缺失数据）**：例如“缺少 22 名球员的无球实时追踪坐标（Off-ball Tracking）、压迫距离与防守阵型保持度数据”。
3. **Unsupported Inference（不成立推断）**：例如“不能确认球队执行了协同的高位逼抢战术或特定阵型压迫”。
4. **Supported Narrower Conclusion（仍可支持的较弱结论）**：例如“可以确认主队在进攻三区完成了 4 次球权夺回，且其中 2 次在 8 秒内转化为射门”。

---

### 2.5 Visible Agent Collaboration (5.7)

在 UI 中将原本折叠在底部的纯文本 Trace 升级为直观的 **Agent Collaboration Stage**：
- 清晰展示三步对抗式漏斗：
  1. **Step 1: Analyst Agent** — 读取候选问题、调用 `get_evidence` / `get_event_chain`、提出主判断与保守变体。
  2. **Step 2: Verifier Agent** — 独立拉取原始证据与对立指标（如用 `shots` 检验 `possession`）、审查数值槽位与因果措辞、给出 `publish / qualify / withhold`。
  3. **Step 3: Deterministic Publication Gate** — 校验 SHA-256 Handoff、核心数学谓词与 `bound-facts` 渲染契约。
- 严格基于真实运行记录（`run.audit`），绝不伪造思维链或虚构对话。

# MatchLens AI — Comprehensive Feature Matrix (R0.2–R4)

本矩阵完整涵盖当前已实现的 R0.2 基线能力与 R1–R4 规划的全部功能，明确区分四个交付层级：
- **Tier 1 — Hackathon Release Core**：2026-10-25 18:00 PT 功能冻结前必须交付并验证的核心亮点。
- **Tier 2 — Hackathon Stretch Goals**：核心稳定且预算/时间充裕时在赛前纳入，否则无缝转入赛后第一阶段。
- **Tier 3 — Post-Hackathon Product Expansion**：赛后产品化演进阶段。
- **Tier 4 — Long-Term Research / Engineering**：长期研究与外部商业数据源拓展。

---

## 1. 全量功能矩阵总表

| ID | 功能名称 | 所属阶段 | 功能定义 | 用户价值 | 前置依赖 | 后端影响 | Agent 影响 | UI 影响 | 预计工时 | 风险 | 演示价值 | 推荐交付层级 | 当前实现状态 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **F0.1** | Continuous Synthetic Replay & Reducer | R0.1/R0.2 | 12 分钟连续有球事件流与确定性状态归约 | 可复现、零幻觉的赛事数据底座 | 无 | `football.py` | 提供不可变事实 | `Scoreboard`, `ReplayControls` | 已完成 | 低 | 高 | Baseline (Done) | **Implemented & Verified** |
| **F0.2** | Dual-Agent MAF Pipeline & Budget Ledger | R0.1/R0.2 | Analyst 提案 + Verifier 核查 + SQLite 预扣费账本 | 真实多 Agent 协作与严格成本边界 | F0.1 | `agents.py`, `budget.py` | 双角色独立会话与工具回执 | `InsightSpotlight` Trace | 已完成 | 低 | 极高 | Baseline (Done) | **Implemented & Verified** |
| **F0.3** | Bound-Facts Gate & Historical Revalidation | R0.2 | 确定性发布门控、`bound-facts-v1` 渲染与历史运行重验 | 防止数字幻觉，支持零成本重放真实历史分析 | F0.2 | `contracts.py`, `main.py` | 校验槽位与核心断言 | `EvidenceDrawer`, `MatchRecap` | 已完成 | 低 | 高 | Baseline (Done) | **Implemented & Verified** |
| **F1.1** | Multi-Scenario Match Engine | R1 (4.1) | 支持 6 类足球战术情节配置与可扩展生成器适配器 | 证明系统适用于不同比赛形态而非单一剧本 | F0.1 | `football.py`, `main.py` | 无隐藏标签泄露，工具透明读取 | 顶部 Scenario 选择器 | 4–6h | 低 | 极高 | **Tier 1: Release Core** | **Implemented with Limitations** (仅 default/stalemate) |
| **F1.2** | Both-Team Intelligence | R1 (4.2) | 主队 (H)、客队 (N) 及双队对比的全链路对称支持 | 解决只分析主队的局限，支持任意关注方 | F0.1 | `football.py`, `contracts.py` | `tool_evidence` 与断言支持双队 | 球队视角切换 (H / N / Both) | 4–5h | 中 | 极高 | **Tier 1: Release Core** | **Requires Refactoring** |
| **F1.3** | Tactical Explorer | R1 (4.3) | 传球网络、推进传球、三区进入、区域分布、抢断与射门序列可视化 | 提供专业且诚实的事件级空间战术分析 | F1.2 | `football.py` 派生空间/网络统计 | 提供空间聚合收据 | `MatchStage` 多图层切换面板 | 5–7h | 低 | 极高 | **Tier 1: Release Core** | **Missing** |
| **F1.4** | Possession Sequence Explorer | R1 (4.4) | 离散事件聚合成连续控球链（时长、传球数、推进距离、结果） | 将散乱事件转化为有足球意义的进攻回合 | F1.2 | `football.py` 序列构建器 | `get_sequence` 工具扩展 | 序列列表、球场高亮与逐事件回放 | 4–6h | 低 | 高 | **Tier 1: Release Core** | **Missing** (仅有进球链) |
| **F1.5** | Player Spotlight | R1 (4.5) | 基于可观测事件的球员传球、推进、射门、抢断与序列参与分析 | 满足球迷与分析师对关键球员表现的追踪需求 | F1.4 | `football.py` 球员聚合统计 | 支持球员维度证据引用 | 球员卡片与个人事件时间线 | 3–5h | 低 | 中高 | **Tier 2: Stretch Goal** | **Missing** |
| **F1.6** | Compare Match Windows | R1 (4.6) | 任意两个合法时间窗口的控球、射门、推进、转换效率对比 | 支持跨时段走势对比，明确分母与样本不足状态 | F1.2 | `football.py` 通用窗口计算函数 | 接收自定义窗口对比收据 | 窗口选择器与双窗口差异视图 | 3–4h | 低 | 中高 | **Tier 2: Stretch Goal** | **Missing** (仅固定前/现 3m) |
| **F1.7** | Dynamic Insight Discovery | R1 (4.7) | 统一 `InsightCandidate` 契约，支持双队、多指标、序列异常与优先级排序 | 自主发现全场关键转折，驱动后续 Agent 推理 | F1.2, F1.4 | `football.py:detect_moments` 升级 | 作为 Analyst 调查输入 | 时间轴多类型动态候选标记 | 3–4h | 低 | 高 | **Tier 1: Release Core** | **Implemented with Limitations** |
| **F2.1** | Typed Claim Planning | R2 (5.1) | 包含 Subject/Predicate/Refs/Counterevidence/Scope 的结构化声明计划 | 在保持确定性门控的同时突破 5 个固定枚举限制 | F1.2, F1.7 | `contracts.py` 升级 | Analyst 输出结构化 ClaimPlan | 展示结构化推理要素 | 5–6h | 中 | 高 | **Tier 1: Release Core** | **Missing** |
| **F2.2** | Tactical Hypothesis Lab | R2 (5.2) | 围绕同一现象生成竞争性解释假设，由 Verifier 逐一核查支持/反证 | 最直观体现双 Agent 必要性与科学证伪精神 | F2.1 | `contracts.py`, `agents.py` | Analyst 提多假设，Verifier 判 Supported/Qualified/Rejected | Hypothesis Lab 对比卡片 | 5–7h | 中 | 极高 | **Tier 1: Release Core** | **Missing** |
| **F2.3** | Challenge an Insight | R2 (5.3) | 用户对已发布结论发起反证/窗口/序列/因果质疑并触发复核 | 真正兑现 "Football Intelligence You Can Challenge" | F2.1 | `main.py`, `contracts.py` 新增 `ChallengeContract` | Verifier 执行专项复核或确定性反证核查 | 交互式 Challenge 面板与状态标记 | 5–6h | 中 | 极高 | **Tier 1: Release Core** | **Implemented with Limitations** (仅静态抽屉) |
| **F2.4** | Challenge & Revision Timeline | R2 (5.4) | 记录初始结论→核查→用户质疑→补充证据→修订结论的完整版本链 | 透明展示判断演变，严格区分原窗口复核与新事件变化 | F2.3 | `main.py` 版本链存储 | 审计记录关联原 `claim_id` | Revision Timeline 演变视图 | 3–4h | 低 | 高 | **Tier 2: Stretch Goal** | **Missing** |
| **F2.5** | Ask the Match | R2 (5.5) | 受约束意图（Constrained Intent）与受控工具调用的比赛问答入口 | 让用户主动提问，同时防止开放式 Prompt 注入与越界 | F1.2, F2.1 | `main.py` 意图路由与受控查询 | 基于固定 Tool Registry 回答 | Ask the Match 预设/受控提问栏 | 4–6h | 中 | 高 | **Tier 2: Stretch Goal** | **Missing** |
| **F2.6** | Evidence Gap Advisor | R2 (5.6) | 系统性说明已有证据、缺失数据（如无球追踪）、不可成立推断与退守结论 | 将数据局限转化为产品专业度与诚实性亮点 | F2.1 | `contracts.py` 证据边界规则库 | 复用 Verifier 输出与元数据 | Evidence Gap 提示卡 | 2–3h | 低 | 高 | **Tier 1: Release Core** | **Missing** |
| **F2.7** | Visible Agent Collaboration | R2 (5.7) | 可视化 `Analyst proposes → Verifier challenges → Evidence decides` 协作流 | 让评委在 10 秒内看懂双 Agent 分工、工具调用与交接 | F0.2, F2.2 | `agents.py` 细化阶段回执 | 真实暴露工具与 Handoff 摘要 | 协作流水线可视化组件 | 3–4h | 低 | 极高 | **Tier 1: Release Core** | **Implemented with Limitations** (仅文本列表) |
| **F3.1** | Personalized Match Director | R3 (6.1) | 支持关注主/客队、关注球员、偏好洞察类型及 Fan/Analyst/Broadcast 三视图 | 超越简单文案切换，实现事件排序与故事组织的深度个性化 | F1.2, F1.5 | `main.py` 偏好过滤与排序参数 | 共享同一已核验事实底座 | Director 偏好设置栏与三视图切换 | 4–5h | 低 | 高 | **Tier 2: Stretch Goal** | **Implemented with Limitations** (仅 Fan/Analyst) |
| **F3.2** | Personalized Match Story | R3 (6.2) | 将关键事件与已核验洞察编排为开局、早期模式、转折点、进球序列与总结 | 生成结构完整、去重且带证据锚点的个性化赛报 | F3.1 | `football.py` / `contracts.py` 叙事编排器 | 聚合已批准卡片，零额外幻觉 | 结构化五段式 Match Story 视图 | 4–5h | 低 | 中高 | **Tier 3: Post-Hackathon** | **Implemented with Limitations** (仅基础 Recap) |
| **F3.3** | Broadcast Producer Workbench | R3 (6.3) | 面向转播制作人的待审队列（Pending Queue）、人工 Approve/Reject/Defer 与字幕文案 | 将学生 Demo 升级为真实广电制作人可用的审校工作台 | F3.1 | `main.py` 编辑审校状态机 | 严格区分 Agent 事实核查与人工编辑批准 | Producer Workbench 审校台 | 4–6h | 低 | 高 | **Tier 2: Stretch Goal** | **Missing** |
| **F3.4** | Broadcast Graphics & Export | R3 (6.4) | 将已批准洞察导出为 SVG 图形、结构化 JSON Overlay Payload 与 Story Cards | 打通转播制作最后一公里交付 | F3.3 | 导出格式化接口 | 无 | Broadcast Overlay 升级 + 一键导出 SVG/JSON | 3–4h | 低 | 中高 | **Tier 3: Post-Hackathon** | **Implemented with Limitations** (仅内嵌预览) |
| **F4.1** | Match Data Adapter | R4 (7.1) | 统一赛事数据接口，解耦内置生成器与 JSON/JSONL 及外部研究数据集 | 使分析引擎无需重写即可接入多源标准赛事数据 | F1.1 | 新增 `adapter.py` 规范化层 | 透明读取标准 `Event` 元组 | 数据源与许可证元数据标识 | 4–6h | 低 | 中 | **Tier 3: Post-Hackathon** | **Missing** |
| **F4.2** | Football Analytics Benchmark | R4 (7.2) | 覆盖双队、窗口边界、残缺证据、错误因果与跨场景的验证基准集 | 科学衡量确定性计算精度与 Agent 推理质量 | F1.1, F1.2 | `tests/` 与 `eval/` 基准套件 | 评测模型原始输出与门控拦截率 | 评测报告展示 | 5–7h | 低 | 高 | **Tier 2: Stretch Goal** | **Implemented with Limitations** (已有 50 项回归) |
| **F4.3** | Multi-Agent Ablation Study | R4 (7.3) | S0 (单 Agent) vs S1 (自审) vs M (Analyst+Verifier) 预算匹配对照实验 | 实证检验双 Agent 架构在拦截过度推断上的独立价值 | F4.2 | `scripts/` 评测脚本与独立账本配额 | 分离公共渲染与原始推理评估 | 评测文档披露 | 6–8h | 中 (需额外 API 预算) | 极高 | **Tier 2: Stretch Goal** (视授权预算执行) | **Missing** (`NOT RUN`) |
| **F4.4** | Reliability, Cost & Provenance | R4 (7.4) | 预算账本、运行审计、快照完整性、Epoch 隔离、限流与公网部署探针 | 保障评审期间至 11 月 10 日稳定、安全、零超支运行 | F0.2 | `budget.py`, `main.py` | 严格限制 6 请求/25s | 状态栏与错误恢复提示 | 3–4h | 低 | 高 | **Tier 1: Release Core** | **Implemented & Verified** (待公网部署验证) |

---

## 2. 核心验收标准（Acceptance Criteria Summary）

1. **R1（F1.1–F1.7）**：切换不同 Scenario（如控球压制 vs 快速防反 vs 逆转）及切换主客队（Harbor FC vs Northbridge United）时，系统计算出真实差异化的指标收据、连续控球序列与空间传球网络，自动发现双队各自的候选洞察，且原有 Seed 17 默认场景保持 100% 哈希兼容。
2. **R2（F2.1–F2.7）**：针对同一比赛时刻，系统能展示竞争性战术假设（Hypothesis Lab）及 Verifier 的核查依据；用户点击质疑（Challenge）可触发基于反证或窗口对比的复核，并明确给出 `Maintained / Narrowed / Withdrawn` 结论及 `Evidence Gap Advisor` 边界说明。
3. **R3（F3.1–F3.4）**：切换关注球队/球员及 Fan / Analyst / Broadcast 视图时，同一批已核验事实呈现出不同的信息组织；在 Broadcast Workbench 中可完成待审洞察的 Approve/Reject 并导出带时间戳与来源的 SVG/JSON 转播载荷。
4. **R4（F4.1–F4.4）**：支持通过 `MatchDataAdapter` 加载内置多场景或外部 JSON 事件流；完成跨场景确定性基准测试，并在预算允许下执行 S0/S1/M 对照评测。

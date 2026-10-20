# MatchLens AI — R4 Plan: Data Generalization, Benchmark & Multi-Agent Evaluation

## 1. R4 阶段目标

将 MatchLens AI 的底层赛事输入从单一内部合成生成器解耦，建立标准的 **`MatchDataAdapter`**，并构建可量化验证确定性计算精度与双 Agent 协作价值的 **Football Analytics Benchmark & Ablation Suite**。

---

## 2. 核心模块设计

### 2.1 Match Data Adapter (7.1)

建立统一的赛事数据接口 `MatchFixture` 与 `MatchDataAdapter`，使核心分析引擎（Reducer、Metrics、Sequences、Agents、UI）无需修改一行代码即可消费多种来源的数据：

#### 支持的数据源类型
1. **Built-in Synthetic Scenario Generator**：内置 6 大战术场景（`default`, `stalemate`, `counterattack`, `transitions`, `balanced`, `comeback`）及任意随机种子 `seed`。
2. **Static JSON / JSONL Event Fixtures**：从本地或测试目录加载标准化的赛事事件文件（用于回归基准与离线复现）。
3. **External / Public Research Dataset Adapter（赛后扩展）**：针对开源足球事件数据集（如 StatsBomb Open Data / Wyscout 公共研究子集，需在各自非商业/研究许可证允许范围内单独核实），提供字段映射器（Field Mapping）、坐标归一化（统一映射至 $105\text{m} \times 68\text{m}$ 标准球场与进攻方向）、时间戳对齐与球权连续性重建（Ownership Reconstruction）。

#### 适配器校验契约
所有外部或文件数据在进入 `reduce_match` 前必须经过：
- **Schema & Provenance Validation**：验证来源标识 `source_type`、许可证声明 `license_notice` 与版本哈希。
- **Coordinate & Time Normalization**：确保坐标落在 $[0, 105] \times [0, 68]$，时间严格递增。
- **Explicit Capability Flags**：标记数据源是否包含无球位置或射门质量（默认 `has_tracking=False, has_xg=False`），自动联动 `Evidence Gap Advisor`。

---

### 2.2 Football Analytics Benchmark (7.2)

构建覆盖 9 类核心场景的验证数据集，严格区分四个评测维度：
1. **Deterministic Correctness（确定性计算正确率）**：
   - 核验双队控球秒数区间裁剪、跨窗口边界（如 $t=180\text{s}$ 或 $t=360\text{s}$ 边界处的事件归属）、10 秒转换射门配对、连续控球序列推进距离与球员统计，要求 **100% 精确相等**。
2. **Agent Reasoning Quality（Agent 推理质量）**：
   - 在表象数据具有误导性的窗口（例如控球率 83% 但 0 射门 0 三区进入，或偶然远射破门但全场被动），检验 Analyst 是否能识别核心矛盾、Verifier 是否能拦截过度吹捧。
3. **Groundedness & Boundary Honesty（证据锚定与边界诚实度）**：
   - 检验所有输出对“错误因果推断（`recoveries_caused_shots`）”、“无球战术臆测（`pressing / formation`）”及“跨窗口数字张冠李戴”的拦截率（目标：**100% 拦截严重越界主张**）。
4. **User Utility（用户实用价值）**：
   - 评估 Fan / Analyst / Broadcast 三种视角是否在保持相同证据引用（`refs`）的同时提供了实质性的信息差异。

---

### 2.3 Multi-Agent Ablation Study (7.3)

保留并严格执行 `EVALUATION.md` 定义的三组对照实验：
- **S0 (Single Agent)**：单次 Analyst 生成主张与双视角文案（上限 3 请求 / `$0.06` 预留）。
- **S1 (Single Agent with Budget-Matched Self-Review)**：同一 Agent 先生成再自我审查（上限 6 请求 / `$0.12` 预留，与 M 完全等预算）。
- **M (Specialist Pair: Analyst + Verifier)**：独立 Analyst 提案 + 独立 Verifier 重新拉取证据并审查（上限 6 请求 / `$0.12` 预留）。

**关键评测纪律**：
- **分离原始推理与公共模板渲染**：由于 `bound-facts` 会将通过门控的断言渲染为标准事实摘要，评测必须同时对比**门控前的原始模型草案（Raw Model Draft Support & Overstatement Rate）**与**门控后的最终发布准确率（Post-Gate Precision & Coverage）**。
- **失败样本纳入分母**：超时、JSON 格式错误或被门控拦截的运行全部计入有效分母，绝不剔除失败样本虚增准确率。
- **诚实披露**：目前本地开发账本剩余额度仅 2 次请求（78/80 已用）；在未配置新的专项评测预算前，72 次工作流的完整 S0/S1/M 实验保持明确的 **`NOT RUN`** 状态，绝不伪造实验数据。

---

### 2.4 Reliability, Cost & Provenance (7.4)

持续加固生产级可靠性护栏：
1. **Persistent SQLite Budget Ledger**：每次 HTTP 请求前通过 `BEGIN IMMEDIATE` 原子预留 `$0.02`，整个工作流启动前检查 `6 * active_admissions` 的完整跑道余量。
2. **Epoch & Snapshot Isolation**：切换场景、切换关注时刻或重启回放立即递增 `session.epoch`，任何在途或迟到的旧 Epoch 异步任务绝不污染当前视图。
3. **Sanitized Run Audit & Provenance**：前端清晰标识每张卡片是 `Real model analysis`、`Historical real analysis` 还是 `Deterministic fallback`，杜绝将回退统计伪装成大模型输出。

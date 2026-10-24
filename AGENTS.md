# MatchLens AI — Agent Guidelines & Engineering Handbook (AGENTS.md)

本文件是针对所有参与 **MatchLens AI** 研发、调试、测试与协同的 AI Agent（包括 Antigravity、Claude、Copilot、Cursor 及自定义 Subagents）的最高指导手册与工程规范。所有 Agent 在阅读代码库、提出修改或编写代码前，必须严格遵守本文件确立的数理边界、架构契约与工程铁律。

---

## 1. 核心哲学与不可逾越红线 (Core Philosophy & Inviolable Rules)

### 1.1 四大核心设计哲学
1. **Evidence-First（证据先行）**：
   不存在无证据的观点。AI 提出的每一个战术观点、分析洞察，必须强类型绑定底层事件槽位（`event_ids`, `player_id`, `coordinates`, `sequence_id`）。
2. **Click-to-Inspect（点击即验证）**：
   UI/UX 上的每一个结论、OAAI 波浪图上的每一个波峰拐点、战报里的每一句话，均支持点击穿透，在 105×68m 战术球场大画布上动态回放真实的物理轨迹。
3. **Truth over Illusion（恪守数据边界，反伪科学）**：
   严格坚守数据分水岭。在仅有逐球事件数据（Event Data）时，**绝对禁止伪造全场 22 人无球防守阵型骨架**；面对无球问题，显式触发“数据充分性与盲区顾问机制（Data Sufficiency Advisory）”。
4. **Adversarial & Reversible（对抗可辩驳）**：
   战术观点允许被用户与分析师驳斥。通过战术假设实验室（Hypothesis Lab）与质疑裁决树（Challenge Arbiter），支持人机博弈与观点版本演进（Revision Timeline）。

### 1.2 物理与信息论红线（严防幻觉）
- **【离散事件无法唯一辨识无球阵型】**：
  设全场物理状态为 $S_t = (\mathbf{x}_{\text{ball}}, \mathbf{P}_{\text{on}}, \mathbf{P}_{\text{off}})$，观测事件流为有损测量 $E_t = h(S_t)$。高位压迫造越位与低位收缩铁桶大巴可映射出完全相同的横传事件记录 $h(S_t^{(1)}) = h(S_t^{(2)})$。无球状态在点估计上不可辨识。
  **Agent 禁令**：严禁在缺少光学追踪数据（Optical Tracking, L11）时生成 22 人的无球站位坐标或基于脑补阵型进行绝对因果论断。
- **【OAAI 严禁宣称逆向商业黑盒】**：
  MatchLens 进攻活跃度指数（OAAI）为团队自主定义算法，严禁在文档或 Prompt 中声称“逆向还原了 Sofascore Attack Momentum”。
- **【xT 适用范围约束】**：
  标准 xT 专用于评价“成功保持球权的前向空间推进动作”，严禁将 $\Delta xT$ 作为铲球、扑救、犯规的通用度量。

---

## 2. 运行时环境与工程工具链 (Runtime & Environment Rules)

### 2.1 Python 虚拟环境隔离（P0 级避坑）
- **必须使用专属虚拟环境解释器**：
  `services/api/.venv/Scripts/python.exe`
- **严禁使用宿主机全局 Python 或 Anaconda Python**（缺少 `agent_framework` 等关键依赖，会导致 ModuleNotFoundError）。
- **常用后端命令**：
  ```powershell
  # 运行全量测试套件（必须保持 100% 通过；当前约 199 项）
  services\api\.venv\Scripts\python.exe -m pytest services/api/tests/ -q

  # 启动后端 API（单 Worker，端口 8000）
  services\api\.venv\Scripts\python.exe -m uvicorn matchlens.main:app --host 127.0.0.1 --port 8000 --workers 1
  ```

### 2.2 前端构建与验证环境
- **Next.js 16 (Turbopack) + React 19 + TypeScript**
- **常用前端命令**：
  ```powershell
  # 依赖安装（必须使用 ci）
  npm --prefix apps/web ci

  # 生产编译与类型静态检查（必须保持 0 错误）
  npm --prefix apps/web run build

  # 开发热更新服务（代理后端 /api）
  npm --prefix apps/web run dev
  ```

### 2.3 单 Worker 约束与预算守卫
- **Uvicorn 单进程约束**：`workers=1`。原因：SQLite 原子账本 (`budget.py`) 与全局内存状态机要求单点无竞争写入，多进程会导致文件锁冲突与状态不同步。
- **Token 预算熔断**：单比赛分析默认设防全局限额（32 请求 / $1.00 USD 熔断守卫）。Agent 编写生成式任务时，全场事件必须先经过“关键骨架蒸馏器”（从 1800 个事件压缩至 50~80 个突变事件），确保输入控制在 3,000 Tokens 内。

---

## 3. 四层足球推理体系契约 (Four-Level Tactical Inference Framework)

所有 Agent 输出的结构化主张（`Claim`）必须严格按照以下四层体系进行定级，严禁将时间先后或指标贡献外推为真实因果：

```
┌─────────────┬───────────────────────────┬────────────────────────────────────────────────────────┐
│ 层级        │ 推理类型与置信范畴        │ 典型定义与实证范例                                     │
├─────────────┼───────────────────────────┼────────────────────────────────────────────────────────┤
│ **Level 1** │ **Observable Facts**      │ 【客观事实】：基于底层打标记录直接计算检索。           │
│             │ (确定性观测事实)          │ *范例*：第 35 分钟在 (42, 28) 夺回球权，8 秒后发生射门。│
├─────────────┼───────────────────────────┼────────────────────────────────────────────────────────┤
│ **Level 2** │ **Metric Attribution**    │ 【指标归因】：基于明确数学公式对指标增量进行拆解。     │
│             │ (确定性指标贡献分解)      │ *范例*：第 42 分钟直塞球对 OAAI 贡献 +2.8，对 xT 贡献   │
│             │                           │ +0.084。此为模型代数贡献，非物理现实因果。             │
├─────────────┼───────────────────────────┼────────────────────────────────────────────────────────┤
│ **Level 3** │ **Statistical Association**│ 【统计关联】：基于多场样本统计规律与基准比较。         │
│             │ (统计关联与假设检验)      │ *范例*：高位抢断频次与后续射门机会呈显著正相关 (r=0.68)│
│             │                           │ 需提供样本容量、控制变量基准与 Bootstrap 置信区间。    │
├─────────────┼───────────────────────────┼────────────────────────────────────────────────────────┤
│ **Level 4** │ **Causal Inference**      │ 【因果推断】：满足可识别性假设与混杂控制的反事实推断。 │
│             │ (严格识别因果推断)        │ *范例*：特定压迫线前提是否导致对方失误率因果上升。     │
│             │                           │ 必须显式声明混淆因素、因果图假设与敏感度分析。         │
└─────────────┴───────────────────────────┴────────────────────────────────────────────────────────┘
```

### Claim 强类型数据契约字段
```python
class Claim(BaseModel):
    claim_id: str
    claim_level: Literal[1, 2, 3, 4]
    claim_level_label: str  # "Observable Fact" | "Metric Attribution" | "Statistical Association" | "Causal Inference"
    statement: str
    evidence_scope: Dict[str, Any]      # sequence_ids, event_ids, window_seconds
    assumptions: List[str]              # 核心假设清单
    counterevidence: List[str]          # 竞争性替代假说或反例
    verification_method: str            # 验证算法（如直接回溯、代数贡献分解、Bootstrap）
    verifier_signature: Optional[str] = None
```

---

## 4. 多智能体拓扑与职责划分 (Multi-Agent Deliberation Topology)

系统采用 **Dual-Agent Deliberation + Deterministic Tools + Publication Gate** 架构。在线 MAF 工作流只执行两个模型智能体（`Analyst → Verifier`）；`EventAttributionSpecialist` 是两位智能体都可调用的确定性 Python 工具层，不是第三个模型智能体。`publication_gate_2_0` 是离线/注册表规则引擎，在线发布使用 `publication_gate`。

```
                      ┌─────────────────────────────────┐
                      │    Lightweight Event Pipeline   │
                      └────────────────┬────────────────┘
                                       │
                                       ▼
                      ┌─────────────────────────────────┐
                      │ 1. TacticalAnalyst              │
                      │    • 扫描控球序列、通道负荷与异动 │
                      │    • 输出带槽位占位符的观点草案   │
                      └────────────────┬────────────────┘
                                       │
                                       ▼
                      ┌─────────────────────────────────┐
                      │ 2. Deterministic tool layer     │
                      │    • decompose_window           │
                      │    • query_causal_chain         │
                      │    • assess_alternative_hypotheses│
                      │    （不是智能体，不调用模型）    │
                      └────────────────┬────────────────┘
                                       │
                                       ▼
                      ┌─────────────────────────────────┐
                      │ 3. EvidenceVerifier             │
                      │    • 槽位物理坐标核验与分级审查   │
                      │    • 签署数字验证凭据签名       │
                      └────────────────┬────────────────┘
                                       │
                                       ▼
                      ┌─────────────────────────────────┐
                      │ Publication Gate 2.0 (终审门禁) │
                      │ • 100% 事件槽位绑定校验         │
                      │ • 推理层级一致性校验            │
                      │ • 伪造无球防守阵型拦截与盲区降级│
                      └─────────────────────────────────┘
```

### 4.1 各智能体职责与工具约定
1. **`TacticalAnalyst` (战术分析师)**：
   - 关注宏观态势演进、控球序列切分、进攻通道（左/中/右）分布、S3 九宫格与 TADD 动作密度差异；
   - 绝不直接宣称 Level 4 因果推断，必须用占位符标注关联微观事实。
2. **`EventAttributionSpecialist` (确定性事件归因工具层，不是智能体)**：
   - 提供 3 大原生工具函数：
     - `decompose_window(window_seconds)`: 将时段活跃度净值精确拆解至传球、带球推进与射门；
     - `query_causal_chain(target_event_id, lookback_seconds)`: 逆向检索射门前 5~15 秒的关键控球链；
     - `assess_alternative_hypotheses(primary_hypothesis)`: 评估竞争性假说，输出置信度。
3. **`EvidenceVerifier` (证据核验员)**：
   - 检查每一个声明引用的事件坐标、球员是否在真实打标记录中存在；
   - 检查推论是否属于 Level 2 指标归因却被过度包装成 Level 4 战术因果；
   - 审核通过后生成验证凭据并签名。
4. **`Publication Gate` (发布门禁)**：
   - 在线路径使用 `publication_gate`：未绑槽位直接拦截；出现无球防守臆测立即降级为 `Evidence Gap Advisory`。
   - `publication_gate_2_0` 用于确定性规则校验与 `ClaimRegistry` 注册，不等同于在线双智能体门禁。

---

## 5. 核心算法与领域模型标准 (Algorithmic Guidelines)

### 5.1 OAAI (Observed Attacking Activity Index)
- **有效时间衰减与死球冻结**：
  $$\text{OAAI}(t) = \sum_{k \in W(t)} \text{Weight}(\text{Action}_k) \cdot \text{ZoneMultiplier}(\text{Loc}_k) \cdot e^{-\lambda \Delta t_{\text{eff}}(t, t_k)}$$
  $\Delta t_{\text{eff}}$ 必须扣除死球时间。**严格区分**：`state.intervals` 是球员持球活跃区间，而 `state.dead_intervals` 才是死球区间，计算衰减时只能冻结 `dead_intervals`。
- **预射门无泄露 xG**：
  射门权重为 $\text{Weight}(\text{Shot}) = 1.0 + 7.0 \times xG$。$xG$ 必须采用球门开角与距离的几何预射门模型 `compute_pre_shot_xg(x, y)`，严禁使用扑救后真实结果。
- **定向 xT 空间增益**：
  推进动作结合 16×12 xT 网格威胁差分 $\Delta xT = xT(\text{end}) - xT(\text{start})$，严禁使用反向推进产生正加权。
- **因果性平滑**：
  在线实时流严格使用因果单侧指数平滑滤波，严禁未来信息泄露。

### 5.2 xT 空间网格威胁模型 (详见 `docs/XT_MODELING_SPEC.md`)
- **坐标归一化**：所有动作起止点在代入前强制转换为统一进攻方向（$x \in [0, 105]$ 向右进攻，$y \in [0, 68]$）。
- **两级实施路径**：
  - **Path A（线上生产）**：调用静态预计算已校准网格（`16x12` 或 `12x8`），实现 $\mathcal{O}(1)$ 查表；
  - **Path B（研究拟合）**：针对特定数据子集引入拉普拉斯平滑与经验贝叶斯收缩，避免单场稀疏转移导致奇异矩阵崩溃。
- **单调性校验**：轴向网格价值必须满足自后场向前场单调递增。

### 5.3 What-If 反事实推演沙盘
- **期望效用公式**：
  $$\mathbb{E}[U \mid a, s] = \sum_{o \in \mathcal{O}} P(o \mid a, s) \, U(o, s)$$
- **三种模式严格区分**：
  - **Descriptive**：仅输出落点理想位置价值差 $\Delta xT$，不做成功率预设；
  - **Scenario-based**：用户配置 $P_{\text{success}}$ 与失误惩罚，输出盈亏平衡点与收益区间；
  - **Research**：端到端状态效用建模。
- 界面必须悬浮“防守未观测假定声明”。

---

## 6. 代码库关键文件与模块索引 (Codebase Map)

| 文件路径 | 关键类与函数符号 | 职责与修改注意事项 |
| :--- | :--- | :--- |
| `services/api/matchlens/main.py` | `Engine`, `view`, `run_whatif`, `get_xt_grid` | API 路由网关。注意必须初始化 `self.xt_model` 并传给 `oaai`；只传 `dead_intervals` |
| `services/api/matchlens/football.py` | `build_sequences`, `build_tactical_explorer`, `build_player_spotlight` | 核心足球领域模型。负责序列切分、九宫格、传球网络与球员画像 |
| `services/api/matchlens/oaai.py` | `compute_oaai`, `compute_oaai_window`, `compute_pre_shot_xg` | 活跃度指数核心计算。注意半衰期默认 $\tau=30\text{s}$ 与预射门 xG |
| `services/api/matchlens/models/xt.py` | `ExpectedThreatModel`, `evaluate_action`, `evaluate_progression` | xT 空间网格模型，支持 16×12 与 12×8 分辨率及轴向单调性校验 |
| `services/api/matchlens/contracts.py` | `publication_gate`, `Claim`, `VerificationRecord`, `evaluate_hypotheses` | 在线门禁与契约定义；Gate 2.0 规则在 `gate.py`，可信裁决持久化在 `registry.py` |
| `services/api/matchlens/agents.py` | `AgentRunner`, `Analyst`, `Verifier` | 双智能体 MAF 编排；确定性归因工具在 `attribution.py` |
| `services/api/matchlens/whatif.py` | `simulate_counterfactual`, `WhatIfRequest`, `WhatIfResponse` | What-If 反事实扰动引擎与 OAAI 敏感度差分计算 |
| `services/api/matchlens/catalog.py` | `MatchMetadata`, `get_catalog`, `get_match` | 比赛元数据目录，支持合成剧本与真实 StatsBomb Open Data |
| `apps/web/app/cockpit/` | `MatchCenterWorkspace`, `ValidationLabWorkspace`, `StoryAgentWorkbench` | 统一比赛探索工作区前端容器，全面对接真实 API |

---

## 7. 协同与交付守则 (Contribution & Handoff Protocols)

1. **响应语言**：必须使用**中文**回答用户的一切提问与方案汇报（遵循 `RULE[user_global]`）。
2. **代码超链接规范**：所有在回复中提及的文件名、函数名与类名，必须提供符合 GitHub 语法的可点击链接，格式：`[filename.py](file:///d:/Projects/match-lens/services/api/...#L10-L20)`。
3. **完成前验证协议 (Verification before Completion)**：
   在声称任何任务“已完成”前，必须在终端依次执行并通过：
   - `services\api\.venv\Scripts\python.exe -m pytest services/api/tests/ -q`（要求 100% 通过）
   - `npm --prefix apps/web run build`（要求 0 错误）
   并确认真实控制台输出，严禁任何形式的臆测或无依据断言。
4. **文档同步更新**：代码实现一旦涉及指标定义、契约字段变更，必须同步更新 `docs/` 下的对应规划与规范文件。

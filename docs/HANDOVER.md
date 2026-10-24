# MatchLens AI — 项目研发全案交接文档 (HANDOVER.md)

**文档版本**：v2.0 (Post-R0.2 Flagship Hardening)  
**当前代码基准**：Git Commit `b768f83`（全量 pytest 161 项通过，Next.js Turbopack 编译 0 错误）  
**面向对象**：后续接手研发人员、架构师、算法工程师及协同 AI Agent  
**更新日期**：2026-10-24  

---

## 一、项目定位与交接背景 (Project Context)

### 1.1 平台使命与行业定位
世界足球数字化正经历由“统计离散指标（进球、控球率、热力图）”向“战术因果推理与人机协同探索”的深水区跃迁。行业中存在两大核心价值断层：
1. **传统即时比分网（Sofascore, FotMob 等）**：“数据密集但因果割裂”，堆砌大量指标，用户看到势头逆转却不知是哪次防线被击穿，图表不可下钻验证；
2. **新兴 AI 足球产品**：“通用大模型套词严重且充斥事实幻觉”，缺乏微观坐标约束，盲目伪造全场 22 人无球防守阵型，输出单向不可反驳的文本黑盒。

**MatchLens AI 的核心使命**：打造全球首个**“以微观事件数据为底盘、以空间几何大画布为骨架、以可溯源多智能体因果归因为中枢”的交互式足球战术智能平台**。

### 1.2 核心设计哲学
- **Evidence-First（证据先行）**：所有战术观点必须强类型绑定底层事件槽位（Event Receipts）；
- **Click-to-Inspect（点击即验证）**：UI 上的每一个结论、OAAI 波峰拐点，均支持一键下钻在 105×68m 球场画布上回放；
- **Truth over Illusion（恪守数据边界）**：在事件流数据下严禁伪造全场无球防守阵型，主动触发“数据充分性顾问”；
- **Adversarial & Reversible（对抗可辩驳）**：内置战术假设实验室与质疑裁决树，允许用户驳斥 AI 并沉淀修订版本历史。

---

## 二、系统全栈架构与代码库索引 (Architecture & Code Map)

### 2.1 端到端系统拓扑
```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        MatchLens Web App (Next.js 16 + React 19)                       │
│  apps/web/app/cockpit/                                                                 │
│  ├─ MatchCenterWorkspace     (实时比分、OAAI 波形图、事件时间轴、首发阵容)             │
│  ├─ TacticalLabWorkspace     (105×68m SVG 球场、S2序列、S3九宫格、TADD动作密度、通道)  │
│  ├─ ValidationLabWorkspace   (xT 空间网格、Bootstrap 95% C.I.、What-If 3模态沙盘)       │
│  └─ StoryAgentWorkbench      (结构化战报生成器、微观动作窗口归因、证据追溯与门禁审查)  │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ HTTP / JSON API (:8000)
┌───────────────────────────────────────────▼────────────────────────────────────────────┐
│                        MatchLens Backend (FastAPI + Python 3.11+)                      │
│  services/api/matchlens/                                                               │
│  ├─ main.py            (FastAPI 网关、Engine 状态机、API 路由分发)                     │
│  ├─ football.py        (足球领域模型：S2序列、S3九宫格、TADD差异、球员画像、剧本引擎)  │
│  ├─ oaai.py            (进攻活跃度指数：死球时间冻结、预射门无泄露xG、定向xT空间加权)  │
│  ├─ models/xt.py       (xT 16×12 / 12×8 期望威胁空间转移网格与轴向单调性校验)          │
│  ├─ whatif.py          (反事实推演沙盘：期望效用扰动引擎、敏感度区间度量)              │
│  ├─ contracts.py       (四层足球推理契约、Publication Gate 2.0 终审发布门禁)           │
│  ├─ agents.py          (三智能体协同：Analyst + EventAttributionSpecialist + Verifier) │
│  ├─ catalog.py         (赛事与比赛元数据索引目录：内置 6 大合成剧本 + 真实名局)        │
│  └─ budget.py          (SQLite 原子账本、全局 $1.00 / 32 请求硬限额熔断守卫)           │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心代码文件导航表
| 模块名称 | 物理路径 | 核心职责与关键符号 |
| :--- | :--- | :--- |
| **主入口与路由** | `services/api/matchlens/main.py` | `Engine` (比赛状态容器), `/api/state`, `/api/matches/{id}/whatif`, `/api/xt/grid`, `/api/matches/{id}/attribution` |
| **足球核心算法** | `services/api/matchlens/football.py` | `build_sequences` (S2序列), `build_tactical_explorer` (S3/传球网), `build_player_spotlight` (BL-07球员画像) |
| **活跃度指数** | `services/api/matchlens/oaai.py` | `compute_oaai` (OAAI主函数), `compute_pre_shot_xg` (预射门几何xG), `compute_oaai_window` (时段切片) |
| **xT 空间威胁** | `services/api/matchlens/models/xt.py` | `ExpectedThreatModel` (加载 16×12 / 12×8 网格, $\mathcal{O}(1)$ 查表, `evaluate_progression`) |
| **反事实推演** | `services/api/matchlens/whatif.py` | `simulate_counterfactual`, `WhatIfRequest`, `WhatIfResponse` (支持 4 种扰动动作与敏感度扩散) |
| **发布门禁** | `services/api/matchlens/contracts.py` | `publication_gate`, `Claim` (4 级推理契约), `resolve_challenge` (质疑仲裁), `ask_the_match` |
| **多智能体** | `services/api/matchlens/agents.py` | `AgentRunner`, `EventAttributionSpecialist` (`decompose_window`, `query_causal_chain`, `assess_alternative_hypotheses`) |
| **前端工作区** | `apps/web/app/components/cockpit/` | `MatchCenterWorkspace.tsx`, `ValidationLabWorkspace.tsx`, `StoryAgentWorkbench.tsx`, `TacticalHeader.tsx` |

---

## 三、核心算法与数理模型技术资产 (Mathematical Assets)

### 3.1 四层足球推理体系 (Four-Level Tactical Inference Framework)
在 `contracts.py` 中强制落地，彻底解决将“指标贡献”或“时间先后”混淆为“真实战术因果”的问题：
- **Level 1 — Observable Facts（确定性客观事实）**：打标事件原生直接检索（时间戳、坐标、球员、成功/失败状态）；
- **Level 2 — Metric Attribution（指标贡献分解）**：根据明确数学公式拆解指标代数贡献（如直塞动作对 OAAI 贡献 $+2.8$、对 xT 贡献 $+0.084$），属于模型内部解释；
- **Level 3 — Statistical Association（统计关联）**：多场跨样本统计相关性，必须伴随样本容量与 Bootstrap 95% 置信区间；
- **Level 4 — Causal Inference（严格识别因果推断）**：基于反事实因果图、声明混淆控制与识别假设的战术推断。

### 3.2 OAAI (Observed Attacking Activity Index) 算法三层架构
1. **Layer A（微观事件贡献）**：
   - 基础传球与带球：基于 16×12 xT 网格威胁差分增益 $\Delta xT$ 定向赋权；
   - 进攻三区进入 $+1.5$；禁区触球/传中 $+3.0$；角球/任意球 $+2.5$；
   - **预射门连续 xG 加权**：$\text{Weight}(\text{Shot}) = 1.0 + 7.0 \times xG$。$xG$ 严格采用目标球门张角与距离的几何预射门模型 `compute_pre_shot_xg(x, y)`，杜绝后验扑救信息泄露与固定跳变。
2. **Layer B（时间聚合与死球冻结）**：
   - 采用因果半衰期指数衰减（标准半衰期 $\tau = 60\text{s}$）；
   - **死球时间冻结 (Dead-Time Freeze)**：出界死球、伤停治疗、VAR 审核期间，冻结衰减步进（$\Delta t_{\text{eff}} = 0$），维持暂停前真实攻防势头，杜绝纯壁钟时间造成的假低谷。
3. **Layer C（平滑与因果性保障）**：
   - 在线实时流严格采用因果单侧指数滤波，无未来信息泄露；离线全场复盘采用双侧高斯平滑。

### 3.3 xT 空间网格建模研究规范 (详见 `docs/XT_MODELING_SPEC.md`)
- **双路径设计**：
  - **Path A（线上生产基准）**：静态加载经开源公开数据校准的 `16x12` 与 `12x8` 网格资源，提供 $\mathcal{O}(1)$ 查表与 `/api/xt/grid` 接口；
  - **Path B（科研拟合扩展）**：在小样本子集拟合时引入经验贝叶斯收缩与拉普拉斯平滑，杜绝未观测转移引发的矩阵奇异崩溃。
- **单调性与方向归一化**：所有坐标代入前统一为左向右进攻（$x \in [0, 105]$），且轴向价值沿 $x$ 轴单调递增收敛至球门。

### 3.4 What-If 反事实推演沙盘
- **期望效用数学形式**：
  $$\mathbb{E}[U \mid a, s] = \sum_{o \in \mathcal{O}} P(o \mid a, s) \, U(o, s)$$
- **三种运作模式**：
  - **Descriptive**：仅输出目标网格理想位置威胁差 $\Delta xT$；
  - **Scenario-based**：分析师输入成功概率与丢球惩罚，输出收益区间与盈亏平衡点；
  - **Research**：端到端状态效用建模。
- 界面显式悬浮“无球防守未观测假定声明”。

### 3.5 无球状态统计可辨识性边界与构造性反例
- 设全场物理状态为 $S_t = (\mathbf{x}_{\text{ball}}, \mathbf{P}_{\text{on}}, \mathbf{P}_{\text{off}})$，观测映射为 $E_t = h(S_t)$。
- **构造性反例**：防守方高位压迫造越位（四后卫在 $x \approx 52\text{m}$）与低位收缩铁桶大巴（四后卫在 $x \approx 18\text{m}$），在持球方后卫横传时可生成完全相同的打标事件 $h(S_t^{(1)}) = h(S_t^{(2)})$。
- **结论**：点估计无球防守阵型在离散事件下不可辨识。MatchLens 坚决不伪造 22 人物理骨架，而是提供在球代用指标（6 秒反抢夺回、前场压迫频次、TADD 动作密度差异），以科学诚实树立公信力。

---

## 四、本地运行、测试与构建实操指南 (Operations Guide)

### 4.1 环境依赖与前置要求
- **操作系统**：Windows 10/11, macOS, Linux
- **Python**：3.11 或 3.13（推荐使用 `uv` 统一管理环境）
- **Node.js**：Node 22+ 与 npm
- **环境变量配置**：
  ```powershell
  # 根目录下复制配置模板
  Copy-Item .env.example .env
  # 在 .env 中填入大模型 API 密钥（如 DEEPSEEK_API_KEY）
  ```

### 4.2 一键启停服务
```powershell
# Windows PowerShell 完整编译并运行
powershell -ExecutionPolicy Bypass -File scripts/run.ps1

# 若前端已有构建产物，可跳过前端打包极速启动
powershell -ExecutionPolicy Bypass -File scripts/run.ps1 -SkipBuild
```
浏览器访问：`http://127.0.0.1:8000`

### 4.3 独立调试工作流 (前后端分离开发)
1. **终端 1（后端 API）**：
   ```powershell
   services\api\.venv\Scripts\python.exe -m uvicorn matchlens.main:app --host 127.0.0.1 --port 8000 --workers 1 --reload
   ```
2. **终端 2（前端热更新）**：
   ```powershell
   npm --prefix apps/web run dev
   ```
   访问 `http://localhost:3000`（Next.js 开发服务器会自动将 `/api` 请求代理至 `127.0.0.1:8000`）。

### 4.4 自动化验证守门命令 (必须 100% 通过)
```powershell
# 1. 运行全量 161 项后端测试套件
services\api\.venv\Scripts\python.exe -m pytest services/api/tests/ -q

# 2. 运行前端 Turbopack 生产编译与 TypeScript 静态类型检查
npm --prefix apps/web run build
```

---

## 五、12 项 Net-New 功能 (BL-01 ~ BL-12) 现状与后续演进 (Roadmap Handover)

| 编号与功能 | 当前已就绪代码资产 | 接手后后续迭代重点 | 依赖层级 |
| :--- | :--- | :--- | :--- |
| **BL-01 StatsBomb 适配器** | `catalog.py` 中已预置真实名局元数据，适配器框架已就绪 | 完善批量 JSON 下载、解析与版本许可自动化更新流水线 | Tier 1 (底盘) |
| **BL-02 OAAI 活跃度曲线** | `oaai.py` 完整实现死球冻结、预射门 xG 与定向 xT，前端波浪图已联动 | 增加多场次平滑参数自适应微调工具 | Tier 1 (底盘) |
| **BL-03 6 秒反抢夺回** | `football.py` 具备时序切分逻辑 | 接入 StatsBomb Pressure 真实打标时升级为真压迫分析 | Tier 2 (战术) |
| **BL-04 动作密度差 TADD** | 九宫格与 18 区控球归一化差分矩阵已实现 | 前端 MatchStage SVG 增加色彩自适应对比度开关 | Tier 2 (战术) |
| **BL-05 数据充分性顾问** | `contracts.py` 门禁与 Evidence Gap 深度融合已上线 | 针对自然语言提问扩充更多无球提问识别关键词 | Tier 1 (底盘) |
| **BL-06 赛后复盘战报** | `story.py` 与 `StoryAgentWorkbench.tsx` 已接入 API | 支持用户富文本微调并一键导出 Markdown / PDF | Tier 3 (叙事) |
| **BL-07 球员同队列画像** | `football.py` 包含同位置划分与样本充足度校验 | 接入联赛赛季全量多场聚合数据沉淀更深队列基准 | Tier 2 (战术) |
| **BL-08 进攻通道渗透** | 通道切分与禁区转化归约逻辑已就绪 | 在前端 Match Center 增加通道雷达对比卡片 | Tier 2 (战术) |
| **BL-09 What-If 沙盘** | `whatif.py` 完整支持 4 类扰动动作与敏感度扩散 | 接入机器学习离线拟合的对抗传球成功率模型 | Tier 3 (推演) |
| **BL-10 经典赛事看板** | `catalog.py` 统一元数据索引，支持真实/合成对局切换 | 扩充至 50+ 场世界杯、欧冠巅峰战役数据集 | Tier 1 (底盘) |
| **BL-11 转播级图卡导出** | 现有一键快照原型 | 实现 9:16 移动端海报与防伪时间戳水印批量渲染 | Tier 3 (叙事) |
| **BL-12 战术高光定位** | 多指标极值与突变检测逻辑已就绪 | 支持导出对应高光时刻的动画 GIF 切片 | Tier 3 (叙事) |

---

## 六、关键避坑指南与常见排错 (Troubleshooting & Known Pitfalls)

### 6.1 Python 虚拟环境与包依赖
- **常见报错**：`ModuleNotFoundError: No module named 'agent_framework'`
- **原因**：使用了系统全局 Python 或 Anaconda Python。
- **解决方案**：统一使用项目根目录下的虚拟环境解释器：
  `services/api/.venv/Scripts/python.exe`。

### 6.2 OAAI 衰减冻结的区间混淆 (P0 级陷阱)
- **陷阱现象**：在正常比赛时间内，OAAI 曲线不随时间衰减，出现不合理的横盘。
- **原因**：在调用 `compute_oaai(..., dead_intervals=...)` 时，错误地将 `state["intervals"]`（球员持球连续活跃区间）作为死球区间传入，导致正常踢球时间被误冻结。
- **规则**：**只有伤停、VAR、死球间歇的 `state["dead_intervals"]` 才能传入死球冻结参数**！

### 6.3 Pydantic 模型严格模式与属性扩展
- `catalog.py` 中的 `MatchMetadata` 开启了 `extra="forbid"`。若后续新增字段（如 `format_seconds`, `source_license`），必须在 Pydantic 模型类上显式声明，否则解析元数据时会直接抛出 ValidationError。

### 6.4 SQLite 账本并发与单进程部署
- `budget.py` 使用本地 SQLite 记录 Token 开销与请求频次。在生产与开发环境中，**Uvicorn 必须保持 `workers=1`**，严禁开多进程，否则会发生 `database is locked` 错误。

### 6.5 Next.js TypeScript 严格编译
- Next.js 16 App Router 在静态构建时会对所有 React Hook 与组件类型进行严格静态推断。在数组 `.map` 回调或 `useMemo` 中，务必使用显式泛型类型声明（如 `React.useMemo<Array<...>>`），防止隐式 `any` 导致构建中断。

---

**交接签署确认**：  
MatchLens AI 研发工程编排中枢已完成全代码库基准测试、文档对齐与环境就绪验证。后续团队可直接基于 Git Commit `b768f83` 开展生产部署与迭代开发。

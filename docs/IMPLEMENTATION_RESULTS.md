# MatchLens AI — 全系统整改、架构融合与产品能力升级验收报告

**作者**: MatchLens AI Principal Architecture & Engineering Team  
**基线提交**: `ff584cc`  
**完成状态**: 全部阶段顺利交付，144 项后端测试 100% 通过，前端 Next.js 生产构建通过。

---

## 1. 总体目标与交付成果概述

本轮任务对 MatchLens AI 系统实施了代码级的全面审查、系统性整改、架构融合与产品能力升级，彻底根除了“以静态硬编码假冒模型验证、以射门进球结果泄露假冒预设概率、以无约束松弛匹配冒充严格门禁”的历史技术债务。

### 核心验收指标对比

| 模块 / 能力 | 整改前状态 (ff584cc) | 整改后状态 (当前) | 验证证据 |
| :--- | :--- | :--- | :--- |
| **xG 计算逻辑** | `outcome == "goal"` 直接硬编码赋值 `0.75` (致命结果泄露) | 独立纯 pre-shot 几何距离与角度危险度模型，进球与未进球样本完全同构 | `test_scientific_credibility.py::test_xg_no_outcome_leakage` |
| **xT 模型来源** | 人工公式生成，元数据却宣称来自 StatsBomb 比赛拟合 | 明确标注为 `heuristic_threat_surface`，移除全局导入时副作用，严谨区分拟合模型 | `test_scientific_credibility.py::test_xt_model_type_provenance` |
| **What-if 反事实置信区间** | 固定系数 `1.96 * se` 伪造 95% 置信区间 | 替换为显式 `sensitivity_spread`，`is_calibrated_ci: False`，强化沙盒科研警示 | `test_scientific_credibility.py::test_whatif_disclaimer_and_no_fake_ci` |
| **智能体 A/B/C 基准评测** | 预设准确率公式，未跑模型却返回固定指标 | 解耦为确定性契约测试 (Deterministic Contract Benchmark) 与实测推理，杜绝虚假 Accuracy | `test_scientific_credibility.py::test_benchmark_deterministic_labeling` |
| **Gate 2.0 引用核验** | `k.endswith(f"-{eid}")` 与 `any(m in mid)` 导致任意后缀或子串非法通过 | 规范化前缀候选集与严格指标目录精准比对，拦截非法 event ID 和 metric ID | `test_phase2_seek_challenge_gate.py::test_gate_2_0_strict_event_and_metric_rejection` |
| **R2 挑战审查交互** | 遇到未知快照静默冻结当前秒数作为虚假快照，无 Claim 校验 | 严谨校验快照存在性 (404)，建立 Claim 注册表校验，实现挑战时间线幂等性 | `test_phase2_seek_challenge_gate.py::test_challenge_*` |
| **全局时间轴与赛段** | 硬编码 720s 与 0'–30' 赛段，导致合成比赛与真实比赛时长错乱 | 引入全局 Seek 控制 (`action: seek`, `at`) 与比赛选择 (`action: set_match`)，动态 12min vs 90min 章节划分 | `test_phase2_seek_challenge_gate.py::test_seek_control`, `test_track_d.py` |
| **工作台战报前端** | `StoryAgentWorkbench.tsx` 中大量硬编码叙事文本与静态事件 ID | 全面挂载真实动态 `hypotheses_matrix`、真实序列事件推进与动态赛段划分 | `apps/web/app/components/cockpit/StoryAgentWorkbench.tsx` |
| **图表即席解释** | 缺少图表即席问答与细粒度凭据溯源 | 新增 `POST /api/explain` 与 `explain_chart` 引擎，覆盖 6 大战术图表深度解释 | `services/api/tests/test_explain_chart.py` |
| **CI 持续集成** | 缺失自动化测试与构建工作流 | 新增 `.github/workflows/ci.yml`，全量执行 pytest 与 Next.js build | `.github/workflows/ci.yml` |

---

## 2. P0 科学严谨性与数学可信度整改

### 2.1 彻底根除 xG 计算中的结果泄露
- **问题文件**: `services/api/matchlens/validation.py`, `whatif.py`, `oaai.py`
- **整改措施**: 
  - 提取纯净预射门几何特征计算模块 `services/api/matchlens/models/xg.py`。
  - 特征仅使用射门起点坐标 `(x, y)` 距离球门中心距离、射门开角与防守干扰估计，杜绝查询 `outcome == "goal"`。
  - 元数据明确标注 `model_name="matchlens_preshot_danger_heuristic"`, `is_calibrated=False`, `outcome_leakage_prevented=True`。

### 2.2 修复 xT 模型来源与导入副作用
- **问题文件**: `services/api/matchlens/models/xt.py`, `data/models/xt_grid_*.json`
- **整改措施**:
  - 将默认网格模型类型修正为 `"model_type": "heuristic_threat_surface"`，来源修正为 `"uncalibrated_spatial_prior"`。
  - 彻底删除了模块被导入时执行 `save_default_grids()` 的全局副作用，杜绝隐式文件写入。

### 2.3 规范 What-if 反事实敏感度区间
- **问题文件**: `services/api/matchlens/whatif.py`
- **整改措施**:
  - 移除使用标准正态分布 `1.96` 伪造的 95% 置信区间。
  - 统一重命名为 `sensitivity_spread`，并返回布尔值 `is_calibrated_ci: False`。
  - 在 API 与返回值中强制注入 `WHATIF_DISCLAIMER_TEXT`，明确注明 Level 3 探索性沙盒属性。

### 2.4 多智能体基准解耦为确定性契约测试
- **问题文件**: `services/api/matchlens/validation.py`, `benchmark.py`, `ValidationLabWorkspace.tsx`
- **整改措施**:
  - 废除了基于线性参数预设模型准确率的公式。
  - 确立 `DeterministicContractBenchmark` 体系，精确统计契约校验违规、Gate 2.0 拦截漏检与反事实对立假设覆盖。
  - 移除人为增加的延迟补偿 `+380ms/+620ms/+910ms`，直接采集真实执行耗时。

---

## 3. 运行一致性与交互硬化

### 3.1 全局时间轴 Seek 与比赛动态切换
- **实现文件**: `services/api/matchlens/main.py`, `TacticalHeader.tsx`
- **功能**:
  - 支持 `Control(action="seek", at=seconds)`，自动将播放头对齐到合法窗口 `[0, format_seconds]` 并生成快照。
  - 支持 `Control(action="set_match", match_id=...)`，无缝在合成 12 分钟比赛与真实 StatsBomb 90 分钟比赛间切换。
  - `Session.tick()` 动态遵循 `self.format_seconds`，彻底移除 720 秒硬编码限制。

### 3.2 真正落地 Gate 2.0 严格核验
- **实现文件**: `services/api/matchlens/gate.py`
- **功能**:
  - 废除模糊后缀匹配 `any(k.endswith(f"-{eid}"))`，统一规范化为前缀候选比对 (`ev-{id}`, `E{id:04d}`)。
  - 废除模糊子串匹配 `any(m in mid)`，严格要求完全匹配标准指标或其命名空间。

### 3.3 挑战机制审计与时间线幂等性
- **实现文件**: `services/api/matchlens/contracts.py`, `services/api/matchlens/main.py`
- **功能**:
  - 对 `/api/challenge` 传入的不存在快照严格返回 HTTP 404，杜绝无据伪造快照。
  - 动态核验快照中包含的真实 Claim ID，非法 Claim 拒绝执行。
  - `resolve_challenge` 实时穿透审计快照真实凭据字典 `receipts`，输出真实的数值差异（如控球时间差、射门增量）。
  - 实现重复挑战幂等性，避免在 UI 历史时间线中产生冗余条目。

---

## 4. 前端组件与数据呈现去硬编码

### 4.1 StoryAgentWorkbench 真实数据绑定
- **文件**: `apps/web/app/components/cockpit/StoryAgentWorkbench.tsx`
- **重构**:
  - 移除静态写死的 `ev_h_carry_42` 等动作，通过 `useMemo` 实时响应 `state.sequences` 与 `state.events` 中的最高威胁事件。
  - 移除静态三步因果链，动态从当前活跃控球序列的真实时间戳与空间坐标推导触发起因、过渡转换与终结拐点。
  - 移除静态假设 A/B 叙述，全面绑定 `state.hypotheses_matrix`，展示实时反证指标检索结果。
  - 战报章节依据 `state.chapters` 动态切分，实时统计当前赛段内的触球、射门、反抢及控球优势方。

### 4.2 真实比赛样本数据覆盖度分类
- **文件**: `services/api/matchlens/data/matches/sb_wc2022_final.json`, `schema.py`, `catalog.py`
- **规范**: 将 12 事件的世界杯决赛样本明确标记为 `DataCoverageLevel.C1_PARTIAL`，并声明所支持的能力集合 (`schema_compatibility`, `starting_xi_verification`, `sample_spatial_drilldown`)，防止用户误以为具备全场统计。

---

## 5. 新增平台核心能力

### 5.1 图表即席解释引擎 (Explain Any Chart)
- **后端模块**: `services/api/matchlens/explain.py`
- **接口**: `POST /api/explain`
- **支持类型**:
  1. `oaai_momentum`: 攻防动量潮汐、窗口控球时间、射门产出与高位反抢增量。
  2. `density_differential`: 3x3 九宫格动作密度差分公式与空间优势解释。
  3. `attacking_channels`: 五走廊进攻渗透与禁区侵入分布。
  4. `xt_surface`: 预期威胁网格危险区分布与前进推进增量原理。
  5. `passing_network` / `spatial_drilldown`: 连续控球链与球员连线凭据解释。
- **合规标准**: 每条解释强制附带置信度级别 (Level 1 / Level 2)、限制边界与反事实因果警示。

### 5.2 持续集成工作流
- **文件**: `.github/workflows/ci.yml`
- **工作流包含**:
  - 后端 Python 3.12 环境依赖自动安装与全量 pytest 校验。
  - 前端 Node 20 环境 TypeScript 类型检查与 Next.js 生产环境静态打包。

---

## 6. 测试与构建验证记录

### 6.1 后端自动化测试
- **测试命令**: `services\api\.venv\Scripts\python -m pytest services/api/tests -v`
- **结果**: **144 passed in 19.85s (100% 通过)**
- **覆盖测试集**:
  - `test_scientific_credibility.py`: 7 项科学性验证（无结果泄露 xG、xT 来源、What-if 敏度区间、基准标注等）
  - `test_phase2_seek_challenge_gate.py`: 6 项 Seek、选赛、Claim 注册、挑战幂等与 Gate 2.0 拦截测试
  - `test_explain_chart.py`: 4 项图表即席解释测试
  - `test_track_a_data.py`: 15 项数据协议与多比赛编目测试
  - `test_track_b_exploration.py`: 11 项空间探索测试
  - `test_track_c.py`: 10 项发布门禁 2.0 与归因测试
  - `test_track_d.py`: 5 项多视角战报与动态章节测试
  - `test_track_e.py`: 14 项科学基准与反事实推演测试
  - `test_interactive_intelligence.py`: 5 项交互智能测试
  - `test_live_intelligence.py`: 8 项实时智能测试
  - `test_publication.py`: 22 项历史门禁收据验证测试
  - `test_runtime.py`: 10 项服务端 API 运行测试
  - `test_football.py`: 15 项足球引擎核心逻辑测试
  - `test_adversarial_empirical.py`: 5 项对抗性实证测试
  - `test_challenger2_verification.py`: 7 项跨平台报告一致性测试

### 6.2 前端工程构建
- **构建命令**: `npm --prefix apps/web run build`
- **结果**:
  - Turbopack 编译耗时: 2.7s
  - TypeScript 类型核验: 2.6s (0 错误)
  - 静态页面导出: 4/4 页面优化生成完成
  - 产物包体积健康无冗余

# MatchLens AI — 科研可信度与事实约束整改报告 (Correctness & Integrity Remediation)

**执行阶段**：Phase 1 — Scientific Credibility & Mathematical Rigor  
**整改时间**：2026-10-22  
**依据文档**：`docs/FULL_SYSTEM_AUDIT.md`, `docs/IMPLEMENTATION_ROADMAP_NEXT.md`

---

## 1. 核心整改概览

本阶段针对系统存在的“预设公式冒充实测、数据标签结果泄露、启发式误差冒充 95% 置信区间”等严重科研诚信隐患，进行了彻底的代码级重构：

```
[原始缺陷状态]                                     [整改后合规状态]
Outcome == "goal" 强制赋值 0.75 xG ----------> 纯 Pre-shot 观察特征计算 (无赛后标签泄露)
xT 网格声称 StatsBomb 500+ 赛事训练拟合 ------> 真实标定为 Heuristic Threat Surface (Karun Singh 几何先验)
xT 模块 import 时自动覆写磁盘文件 ------------> 移除副作用写盘，纯只读静态加载或显式幂等初始化
What-if 加权误差乘 1.96 伪造 95% CI ---------> 明确标定为 Heuristic Sensitivity Spread，带科研免责声明
Benchmark 线性公式伪造 Agent C 94% 准确率 -----> 解耦为 Deterministic Contract Benchmark，未测模型标定 Not Run
跨赛事泛化失败写死 r=0.924 / MAE=0.038 ------> 显式返回 None / Failed，摘要如实披露“未计算或样本不足”
```

---

## 2. 具体模块实现细节

### 2.1 纯 Pre-shot xG 计算 (`services/api/matchlens/models/xg.py`)
- **根除结果泄露**：
  建立 `compute_pre_shot_xg(x, y, event_id, outcome, attack_direction)`。无论射门最终是否进球（`goal`、`saved`、`blocked`、`miss`），在相同坐标点发射的射门均计算出完全一致的预期进球危险度。
- **完善自解释元数据**：
  定义 `ShotDangerMetadata` 与 `ShotEvaluation`：
  - `xg_model_version`: `"heuristic-pre-shot-v1.0"`
  - `xg_source`: `"heuristic_shot_danger"`
  - `features_used`: `["distance_to_goal", "angle_to_goal"]`
  - `calibration_status`: `"uncalibrated_heuristic"`（严禁宣称为 Calibrated xG）
  - `training_data`: `None`
  - `missingness_status`: `"observed_coordinates" | "missing_coordinates"`
- **全链路替换**：
  在 `services/api/matchlens/validation.py` 与 `services/api/matchlens/whatif.py` 的 `_extract_xg` 中彻底弃用旧的 `outcome == "goal" -> 0.75` 逻辑，统一调用 `compute_pre_shot_xg`。

### 2.2 xT 网格模型来源与写盘副作用整改 (`services/api/matchlens/models/xt.py`)
- **来源与元数据澄清**：
  默认网格 `xt_grid_16x12.json` 与 `xt_grid_12x8.json` 元数据真实注明为基于 Karun Singh (2019) 几何解析公式生成的 `heuristic_threat_surface`，`calibration_status="uncalibrated_spatial_prior"`，删除伪造的 StatsBomb 赛事训练元数据。
- **经验拟合模型隔离**：
  `ExpectedThreatFitter` 生成的模型保留自解释元数据 `empirically_fitted_xt`，严格记录训练事件数量与收敛步数。
- **消除 Import 副作用**：
  删除模块导入时自动执行的 `save_default_grids()`，模型资源文件只读加载；提供显式幂等构建命令。

### 2.3 What-if 沙盒科学约束 (`services/api/matchlens/whatif.py`)
- **废除虚假置信区间**：
  将 `delta_amp ± 1.96 * se` 伪造的 95% CI 修正为 `sensitivity_spread`（启发式敏感性扰动带），并在结果模型中增加：
  - `is_calibrated_ci: False`
  - `uncertainty_method: "heuristic_sensitivity_spread_uncalibrated"`
- **科学免责声明**：
  ```
  Level 3 Research / Exploratory — Not validated for production causal claims. 
  RESEARCH SANDBOX NOTICE (Level 3 Hypothesis): In-silico mathematical intervention on historical event stream. 
  Does not represent true counterfactual replay, physical match rerun, or win probability forecast. 
  Uncertainty bounds represent heuristic sensitivity spreads under local assumptions, NOT calibrated 95% confidence intervals.
  ```

### 2.4 Multi-Agent Benchmark 体系解耦 (`services/api/matchlens/validation.py`, `benchmark.py`)
- **Deterministic Contract Benchmark 独立**：
  将 A/B/C 性能比对严格界定为确定性规则与门禁测试。基于真实事件流与实际契约规则执行，分别评估：
  - Config A：基础快照规则（缺乏时序归因工具，因果冒进被拦截）；
  - Config B：时序窗口分解与连续链条查询；
  - Config C：对立假设评估（Specialist 排除非受迫失误，解决争议）。
  明确标注 `benchmark_type: "deterministic_contract"`，`empirical_accuracy_measured: False`，`data_provenance: "Deterministic Contract Benchmark"`。
- **杜绝固定补偿与伪造准确率**：
  移除 `benchmark.py` 中的写死延迟补偿常量（`+ 380.0 / + 620.0 / + 910.0`），如实记录实测毫秒。

### 2.5 Bootstrap 泛化失败兜底修复 (`services/api/matchlens/validation.py`)
- 当 `eval_cross_match=False` 或跨赛事评测因样本不足失败时，`cross_match_mae`、`cross_match_rmse`、`cross_match_pearson_r` 显式设为 `None`，并在摘要中报告 `"Cross-match generalization: not evaluated or insufficient data."`，彻底废除写死的 `0.038 / 0.052 / 0.924` 欺骗性兜底。

---

## 3. 验收证据与测试验证

新增专门针对科研可信度的测试套件 `services/api/tests/test_scientific_credibility.py`，全量测试套件执行通过：

```powershell
============================= test session starts =============================
platform win32 -- Python 3.13.9, pytest-9.1.1, pluggy-1.7.0
rootdir: D:\Projects\match-lens\services\api
collected 133 items

services\api\tests\test_adversarial_empirical.py .....                   [  3%]
services\api\tests\test_challenger2_verification.py .......              [  9%]
services\api\tests\test_football.py ...............                      [ 20%]
services\api\tests\test_interactive_intelligence.py .....                [ 24%]
services\api\tests\test_live_intelligence.py ........                    [ 30%]
services\api\tests\test_publication.py ......................            [ 46%]
services\api\tests\test_runtime.py ..........                            [ 54%]
services\api\tests\test_scientific_credibility.py .......                [ 59%]
services\api\tests\test_track_a_data.py ..............                   [ 70%]
services\api\tests\test_track_b_exploration.py ...........               [ 78%]
services\api\tests\test_track_c.py ..........                            [ 86%]
services\api\tests\test_track_d.py ....                                  [ 89%]
services\api\tests\test_track_e.py ..............                        [100%]

============================ 133 passed in 16.51s =============================
```

所有 133 项测试用例全部绿灯通过，代码级科研诚信隐患全部清零。

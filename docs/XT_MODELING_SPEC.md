# MatchLens xT (Expected Threat) 空间威胁建模与评测规范 (`XT_MODELING_SPEC.md`)

**文档版本**：v1.0  
**关联主报告**：[FOOTBALL_INTELLIGENCE_PLATFORMS_2026.md](file:///d:/Projects/match-lens/docs/FOOTBALL_INTELLIGENCE_PLATFORMS_2026.md)  
**适用模块**：Track A (Data & Analytics Foundation)、BL-01 (StatsBomb Adapter)、BL-02 (Attacking Activity Index)、BL-09 (What-if Decision Sandbox)  

---

## 一、定位与方法论边界

### 1.1 标准 xT 模型的定义与适用范围
Expected Threat (xT，由 Karun Singh 提出并在 `socceraction` 等开源库中广泛标准化) 是一种基于离散空间马尔可夫决策过程（MDP / Markov Chain）的**球权推进位置价值模型**。

在 MatchLens 架构中，xT 的适用边界严格界定如下：
1. **核心评价对象**：旨在量化**成功保持球权的地面/空中推进动作**（主要是成功的开放式比赛传球 `Pass` 与带球推进 `Carry`）所带来的球场空间位置价值变化：
   $$\Delta xT(a) = V(z_{\text{end}}) - V(z_{\text{start}})$$
2. **非通用全动作价值评分**：
   - **射门 (`Shot`)**：标准 xT 在网格层面上将区域平均射门转化率作为吸收态回报，但具体单次射门的质量受射门角度、身体部位、门将站位等微观特征影响，必须使用专门的 **xG / xGOT** 模型评估，不能用网格级 $V(z)$ 替代单次射门价值；
   - **防守动作 (`Tackle`, `Interception`, `Clearance`, `Foul`)**：标准 xT 不直接评估防守夺回球权或阻止对手推进的净防守价值（此类双向攻防价值需通过 EPV 或 OBV 等扩展模型单独建模）；
   - **失败动作（传球失误 / 丢球）**：标准 xT 常规定式仅对成功推进动作赋正/负位置差值，或将失败动作记为 0；若要在反事实沙盘（BL-09）中评估传球失误风险，必须显式引入**球权转换后的对手反击期望损失项**，而不能直接使用原始 $\Delta xT$。

### 1.2 双轨工程实现路径
MatchLens 不将“自行收集 500 场比赛从头训练”设为唯一硬性前置门槛，而是借鉴 `socceraction.xthreat` 的成熟工程范式，支持两条可互换、可对比的模型供给路径：
- **路径 A（预计算基准网格导入，Baseline Grid Loading）**：直接加载经社区与学术界广泛验证的公开预计算 xT 价值网格（如基于 StatsBomb Open Data 或解读版 12×8 / 16×12 基准矩阵），用于快速基线对齐与确定性回归测试；
- **路径 B（基于多赛事语料的自主拟合与平滑校准，Custom Corpus Fitting）**：基于本地接入的 StatsBomb Open Data 完整赛季/锦标赛语料，按照本规范第二至五节定义的管线训练、正则化平滑并导出版本化模型文件。

---

## 二、训练语料、事件筛选与空间坐标标准化

### 2.1 训练数据集选择与记录要求
训练或校准 xT 模型时，必须明确登记所使用的赛事与赛季范围（例如 StatsBomb Open Data 中的 La Liga、Champions League、FIFA World Cup、UEFA Euro 等公开赛事包），并在模型元数据中记录：
- 比赛场次数（`num_matches`）与有效推进事件总数（`num_move_events`、`num_shot_events`）；
- 赛事构成比例（避免单一杯赛淘汰赛点球/加时赛偏态分布主导常规时间参数）。

### 2.2 进攻方向与坐标系统一
1. **标准物理球场尺度**：统一映射至长 $L = 105.0\text{ m}$、宽 $W = 68.0\text{ m}$ 的标准米制笛卡尔坐标系：
   - $x \in [0, 105]$：始终归一化为**当前控球方的进攻方向从左向右**（即 $x = 0$ 为本方球门线，$x = 105$ 为对方球门线）；
   - $y \in [0, 68]$：$y = 0$ 为左侧边线，$y = 68$ 为右侧边线（或根据数据源约定并在 Schema 中锁定手系）。
2. **StatsBomb 坐标转换规则**：
   - StatsBomb 原生坐标为 $120 \times 80$ 码制（Yard），其中 $x_{\text{sb}} \in [0, 120], y_{\text{sb}} \in [0, 80]$；
   - 转换过程中必须保持边线、禁区线（$x_{\text{sb}} = 102 \leftrightarrow x = 88.5\text{ m}$）、小禁区线与点球点（$x_{\text{sb}} = 108 \leftrightarrow x = 94.0\text{ m}$）的几何拓扑一致性（支持线性缩放或分段折线关键线对齐，并在模型配置中显式声明 `coordinate_mapping_mode`）。

### 2.3 纳入计算的事件类型与过滤口径
严格遵循马尔可夫状态转移的事件入模准则：

| 事件分类 | 纳入条件 | 排除条件 | 备注 |
| :--- | :--- | :--- | :--- |
| **移动动作 ($M$)** | 开放式比赛（Open Play）中的 `Pass` 与 `Carry` | 定位球直接发球（角球、任意球、界外球、门球、点球）、非控球解围 | 仅当 `outcome == Complete` 时计入成功转移矩阵 $T_{z \to z'}$ |
| **射门动作 ($S$)** | 开放式比赛中的 `Shot` | 点球（Penalty）、直接任意球射门 | 当 `outcome == Goal` 时计入区域射门得分计数 |

---

## 三、数学定义、稀疏网格处理与平滑求解协议

### 3.1 马尔可夫价值迭代方程
将球场划分为 $N_x \times N_y = K$ 个离散网格单元（例如 $12 \times 8 = 96$ 或 $16 \times 12 = 192$）。对于任意网格 $z \in \{1, \dots, K\}$：
- $s_z = \frac{N_{\text{shot}}(z)}{N_{\text{shot}}(z) + N_{\text{move}}(z)}$：在网格 $z$ 发起射门的经验概率；
- $m_z = 1 - s_z$：在网格 $z$ 发起移动（传球或盘带）的概率；
- $g_z = \frac{N_{\text{goal}}(z)}{N_{\text{shot}}(z)}$：在网格 $z$ 射门转化为进球的条件概率（或采用经校准的预期进球均值 $\overline{xG}(z)$ 代替原始 $0/1$ 进球率以降低稀有事件方差）；
- $T_{z \to z'} = \frac{N_{\text{move\_success}}(z \to z')}{N_{\text{move}}(z)}$：在网格 $z$ 选择移动动作后，成功转移至网格 $z'$ 的条件概率（注意：失败移动动作作为球权终止吸收态，使 $\sum_{z'} T_{z \to z'} \le 1$）。

通过动态规划价值迭代（Value Iteration）求解 $H$ 步（通常 $H = 4 \sim 5$ 次控球传递，或迭代至收敛 $\max_z |V^{(k+1)}(z) - V^{(k)}(z)| < 10^{-6}$）：
$$V^{(0)}(z) = 0, \quad V^{(k+1)}(z) = s_z \cdot g_z + m_z \sum_{z'=1}^{K} T_{z \to z'} V^{(k)}(z')$$
> **数值稳定性说明**：采用上述贝尔曼价值迭代（Value Iteration）直接按步递推，计算复杂度为 $\mathcal{O}(H \cdot K^2)$，**在数学与算法上根本不需要对稀疏转移矩阵进行求逆**，因此不会发生“矩阵奇异崩溃”。单场或小样本下真正的统计问题是**有限样本导致的转移概率方差过大与零计数偏差**。

### 3.2 稀疏网格与未观测转移的平滑策略
当网格分辨率较高（如 $16 \times 12$ 或 $24 \times 16$）或训练样本有限时，部分边角网格及长距离跨区转移 $(z \to z')$ 会出现零计数或极低样本量。必须实施以下平滑与正则化策略之一，并在评测中对比：
1. **拉普拉斯 / 狄利克雷先验平滑 (Dirichlet / Empirical Bayes Shrinkage)**：
   - 对区域射门转化率 $g_z$：用区域内所有射门的模型 $\overline{xG}(z)$ 或全局/邻域先验 $g_0(z)$ 进行收缩估计：
     $$\hat{g}_z = \frac{N_{\text{shot}}(z) \cdot g_z + \alpha_g \cdot g_0(z)}{N_{\text{shot}}(z) + \alpha_g}$$
   - 对转移矩阵 $T_{z \to z'}$：引入基于空间欧氏距离衰减的先验核 $\pi(z \to z')$，对低样本网格做经验贝叶斯平滑。
2. **二维空间核平滑 (2D Spatial Gaussian / Spline Smoothing)**：
   - 在每次价值迭代更新后，或对最终收敛的价值表面 $V(x, y)$ 施加保留禁区边界特征的各向异性高斯平滑或双三次样条插值（Bilinear / Bicubic Interpolation），消除离散网格边缘的阶跃伪影（Grid Boundary Artifacts）。

---

## 四、训练、验证与测试划分及评测协议

### 4.1 按比赛严格隔离的数据集划分 (Match-Level Split)
为防止同一场比赛内的战术风格泄漏，严禁按单个事件随机切分，必须**以完整比赛 (`match_id`) 为最小切分粒度**（建议按时间先后或分层抽样划分为 70% Train / 15% Validation / 15% Test）：
- **训练集 (Train)**：拟合 $s_z, m_z, g_z, T_{z \to z'}$ 及网格价值表 $V(z)$；
- **验证集 (Validation)**：选择最优网格分辨率（如 $8 \times 6$, $12 \times 8$, $16 \times 12$）、迭代深度 $H$ 及平滑超参数 $\alpha_g$；
- **测试集 (Test)**：汇报最终样本外泛化与稳定性指标。

### 4.2 核心评测指标体系
1. **后续控球序列射门/进球预测校准度 (Sequence Goal Calibration)**：
   - 检验当前网格价值 $V(z)$ 与测试集中从该网格出发在未来 $H$ 步控球内实际产生进球（或累计产生 xG）的经验频率之间的 **Brier Score**、**Log-Loss** 与 **ECE (Expected Calibration Error)**。
2. **跨样本自举稳定性 (Bootstrap Stability & Variance)**：
   - 对训练集进行 $B = 50$ 次比赛级 Bootstrap 重采样，计算每个网格 $z$ 的价值标准差 $\sigma(V(z))$ 与变异系数 $CV(z) = \frac{\sigma(V(z))}{\mu(V(z))}$；
   - 若某高分辨率网格的平均 $CV(z) > 0.15$，则证明该分辨率在当前语料规模下过拟合，必须降级至更粗分辨率（如 $12 \times 8$）或增大平滑强度。
3. **网格边界连续性检验 (Boundary Continuity Check)**：
   - 对比离散网格直接查表与双线性插值（Bilinear Interpolation）在网格交界线两侧 $\pm 0.5\text{ m}$ 处的 $\Delta xT$ 突变幅度，确保微小的坐标扰动不会引起异常的价值跳变。

---

## 五、模型产物格式、版本溯源与开源合规要求

所有上线供 MatchLens 后端（`football.py`）加载的 xT 静态网格文件，必须包含完整的自描述元数据头（严禁使用无来源说明的裸二维数组）：

```json
{
  "model_name": "matchlens_xt_grid",
  "model_version": "1.0.0",
  "grid_resolution": { "nx": 16, "ny": 12 },
  "pitch_dimensions_meters": { "length": 105.0, "width": 68.0 },
  "interpolation_mode": "bilinear",
  "horizon_steps": 5,
  "smoothing_method": "xg_prior_shrinkage_alpha_10",
  "training_corpus": {
    "provider": "StatsBomb Open Data",
    "competitions": ["<由训练运行填充：竞赛与赛季清单>"],
    "num_matches": "<由训练运行填充>",
    "num_move_events": "<由训练运行填充>",
    "num_shot_events": "<由训练运行填充>",
    "split_seed": 42
  },
  "validation_metrics": {
    "ece": "<由评测运行填充>",
    "mean_bootstrap_cv": "<由评测运行填充>"
  },
  "license_and_attribution": {
    "data_license": "<以 StatsBomb Open Data 仓库当前 LICENSE / 用户协议原文为准，接入时逐字核对并记录>",
    "required_attribution": "Data provided by StatsBomb (https://github.com/statsbomb/open-data)",
    "logo_requirement": "<按官方署名与 Logo 使用要求核对后填写>"
  },
  "values": [
    [0.0012, 0.0015, "..."]
  ]
}
```

> **示例值声明**：上述 JSON 中所有尖括号占位符均须由真实训练/评测运行产出，并附数据集、样本数、程序版本、随机种子与结果文件路径。本文不提供任何未经运行验证的具体数值。

---

## 六、引用与状态更新说明

1. 第 3.1 节：原主报告中“单场在线拟合会引发矩阵求逆崩溃”的说法不成立。价值迭代不涉及求逆，真实风险是小样本下转移概率方差大、存在零计数。
2. 原主报告中“必须使用 500 场以上训练”的硬性门槛已撤销。所需样本量由第 4 节的 Bootstrap 稳定性检验（CV 阈值）经验性确定，该阈值本身也需在实验中校准，不预设为定值。
3. `socceraction` 同时支持拟合模型与加载预计算价值网格，所以路径 A 与路径 B 并行保留。

# Slice C 交付结果 —— 跨场分析深度 + 产品与内容生产深度（#29 / #30）

日期：2026-10-24。本文件是 Slice C 的唯一结果文档；四态分开，不混写。
共享工作区约束：`main.py`、`investigation.py`、`catalog.py`、`ProducerWorkspace.tsx`、`MatchLibraryWorkspace.tsx` 含并行方未提交改动，本切片在这些文件中的增量**保留在工作区未提交**（逐条列于 §5），由主线合并；其余改动已按功能分片提交（5 个 commit，未 push）。

---

## 1. 已完成且已验证

### C-1 球队/球员跨场画像
- 新增 [profiles.py](../services/api/matchlens/profiles.py)：全部数值经 `MetricsService`（注册表单公式）；`query_range_many` 新增 `precomputed_receipts` 缓存参数（同公式，仅省一次 receipts 重算）。
- 端点（main.py 新增块）：`GET /api/profiles/teams`、`/api/profiles/team-discovery`、`/api/profiles/team`、`/api/profiles/players`、`/api/profiles/player`。
- 口径契约（测试断言）：
  - Per-90 只聚合 `COMPLETE_VERIFIED` 场次；部分覆盖保留原始总量并标注 `rate_status=withheld_no_complete_matches`；
  - possession 聚合为"逐场份额均值"，禁止求和；
  - 逐场分布（n/均值/中位/最小/最大 + 全列表）如实输出，**不产生任何置信区间或 p 值**；
  - 风格标签（possession_dominant / possession_deferred / transition_reliant_shot_creation / direct_progression 等）附推导规则与 basis_metric_ids，显式声明"描述性 L1/L2 标签，非因果"；
  - 快照冻结于名义时长（平台既有语义）导致补时/加时被截：每行 `clock_bounded_at_duration` 披露 + limitation 文案；
  - 合成场次按 `provenance_kind` 门禁排除（builder 层测试断言）；
  - 球员画像通过"球员过滤后重新冻结快照"复用同一公式；`possession/entries/transition_shots` 因依赖未过滤控球链被明确排除（写进 limitation）；分钟分母三法（substitution_derived / starter_assumed_full / event_span_fallback）计数披露。
- 实测（8020，7 场阿根廷 provider 场次）：
  - 球队画像冷 4.0s / 热 0.93s；快照 LRU 16 hit/16 miss、行级指标缓存 14 hit/18 miss（响应内 `scope.snapshot_cache` / `row_metrics_cache` 如实上报）；
  - aligned 窗口（逐 Period 交集、不跨 Period 合并、点球剔除）：P1=2764.4s、P2=2226.1s；aligned shots/90=8.81 vs match=8.88；
  - 梅西 8 场：595.6 分钟（starter_assumed_full=4, substitution_derived=4），4 球，passes/90=38.08；
  - `/api/profiles/players` 全语料 71 场首扫 16.7s（一次性，进程内缓存后 0.19s，响应带 `cache: hit/miss`）。

### C-2 Explain Any Chart 扩展 + 调查交接
- [explain.py](../services/api/matchlens/explain.py) 新增 `chart_type=shot_location`（起脚点几何：距离/门角/xT cell/免泄漏几何 pre-shot xG，全部标注启发式；近邻 5m 观测射门作为支撑事件）与 `chart_type=cross_match_diff`（同一注册表指标在两个冻结快照上的观测，n=1/侧，只发布原始差值与双方 coverage/分钟基，`comparison.investigation_focus_*` 直接可交调查）。既有 6 类图与签名语义零改动（回归测试锁定）。
- 调查交接：`InvestigationBody.focus_type` 增 `shot_location`（`evt:<id>` 冻结到射门时刻 / `loc:<x>,<y>` 最近射门解析）与 `cross_match_diff`（`focus_id=metric_id`，走 `compare_match_ids`）；`investigation.py` 相应 `_resolve_focus`/`classify_intent`/scope/工具计划增量。实测：`inv loc` → APPROVED，`inv cross` → WITHHELD（无 compare ids 时诚实拒绝），`explain cross_match_diff` 1.16s。

### C-3 xG/xT 治理
- `GET /api/models/governance`：xt（来源=Karun Singh 解析先验、未拟合、Path A/B 协议、单调性、允许/禁止用途、评测接口 `/api/models/xt` 与 `/api/models/xt/compare`）、pre_shot_xg（几何启发式、禁结果泄漏）、registry_xg（not_calibrated，永不伪造零）、oaai（**明确声明非任何商业产品指标的逆向还原**，因果单侧平滑）。ΔxT 禁用于铲球/扑救/犯规写入接口与 UI。
- UI：ValidationLab 新增"模型治理"折叠面板（内容含禁止清单与评测接口，已实测渲染）+ xT 网格下的启发式警示条。

### C-4 产品与内容生产
- Match Hub：主线在会话中重构为 MatchLibraryWorkspace/Browser/Detail（比赛类型/年份分组），本切片在其上加**组合筛选**（球队/数据来源/覆盖/日期区间，与搜索和赛事轴可叠加，实测 87→8→7→7），并把 [MatchDetailPanel](../apps/web/app/components/cockpit/MatchDetailPanel.tsx) 接入其 deep panel（主线完成接线）。
- Match Detail 七页签实测：概览（来源/完整度/license/数据版本）、阵容（Lloris/Mbappé 首发-替补结构）、统计（两队 Registry 口径全观测前缀）、射门（含几何 xG* 列，18 行 outcome）、战术（通道表+密度差分）、跨场画像（球队切换 France/Argentina、11 指标聚合表、球员入口→姆巴佩画像 8 指标+分钟方法）、已保存调查（`GET /api/investigations` 空态诚实）；跨场对比入口实测可跑（France-Argentina vs Bayern-Inter 2010，comparability note 正确）。
- 后端 `GET /api/matches/{id}/detail` 冷 250ms / 热 164ms（LRU 命中）。
- Broadcast：制作人面板增 Rundown **预览**（明确标注非服务器权威）、条目移除、失效项**回审**跳转；`BroadcastStore` 增 50 条上限的 **manifest 历史**（跨实例持久化）+ `GET /api/broadcast/manifests`（producer-only）。撤回→失效→重批→**必须重建 Rundown**（编辑决策产生新 revision）的服务端权威契约由测试锁定。
- 面板收敛：ValidationLab 基准审计表默认收起（`benchmark-audit` details），证据链未删。

### C-5 验收证据
- 后端：`pytest services/api/tests/ -q` → **313 passed**（含新增 22 项：crossmatch 11 / explain 8 / broadcast_review 3+端点2；既有用例零删改）。
- 前端：`npm --prefix apps/web run build` → **0 error**（静态导出 out/ 由后端同源托管）。
- 真实浏览器走查（静态导出 + 8020 同源，1440×900 / 768×1024 / 412×915）：
  - 桌面：比赛库+组合筛选、详情七页签、画像聚合/球员画像/对比、调查空态、比赛中心深链（`?workspace=match_center&match=sb_7580&at=0`）、回放推进（30× 下 4s 走 108s）与暂停、治理/审计默认收起且治理内容完整、制作人令牌门禁与诚实空队列；
  - 手机/平板：两档视口均无横向溢出（scrollWidth≤innerWidth），筛选与详情可用；
  - 键盘可达性：27 个可聚焦元素全为原生 button/select/input/a，DOM 序即 Tab 序，无 div-onclick 反模式（0 个）；
  - 工具限制备注：本 webview 会话的合成输入桥（cua/keypress/截图）后期不稳定，指针/键盘路径以页面内原生事件分发与 Playwright locator 动作验证（处理器等价），截图仅前段成功数张。
- 性能实测汇总（8020，进程含目录级缓存）：目录列表 31ms；球队画像（7 场）冷 4.0s/热 0.93s；aligned 画像 1.3s（行缓存命中）；球员索引 71 场首扫 16.7s/复访 0.19s；球员画像 0.92s；比赛详情 250/164ms；France 自动发现画像 5.3s。

## 2. 代码完成但未实测（缺哪步证据）
- 制作人 UI 的完整"撤回→重审→重建 Rundown"点击流：无服务器配置的 producer token（仓库不带密钥，禁止伪造身份），UI 侧验证止步于令牌门禁/空队列诚实渲染；该契约已在 **API/store 层**由 `test_broadcast_review.py` 全链路验证。补齐方式：配置 `MATCHLENS_PRODUCER_TOKEN` 后在浏览器走一遍。
- `cross_match_diff` / `shot_location` 在 UI 上的一键"发起到调查"按钮：explain 两个新目标的后端与 planner 交接已实测（含 APPROVED/WITHHELD 状态机落点），但 InspectorDrawer/详情面板尚未添加针对这两个新 focus 的入口按钮（见 §4 明确未做）。
- aligned 窗口模式的前端入口：接口与聚合已验证，UI 未暴露 window=aligned 切换。

## 3. 被外部条件阻塞
- 无数据源阻塞：语料 71 场（1990 前后世界杯 + 2018/2022 世界杯 + Euro 2020/2024 + Copa 2024 + 欧冠 + Finalissima 等）已导入，跨 era 对照已能跑通（如 Argentina 1958-2024 画像）。
- StatsBomb 开放数据不含的赛事/年代（如 2010/2014 世界杯、2012/2016 欧洲杯）仍不可对照——与任务书预期一致，非本切片可解。
- IAB webview 合成输入桥不稳定（见上），属工具环境限制，不影响产品结论。

## 4. 研究未做 —— Not Run
- 跨场差值的显著性检验、Bootstrap 置信区间、回归/因果模型：**Not Run**（设计上不产出，接口与 UI 均只呈现原始分布）。
- 风格标签对联赛基线的校准：**Not Run**（阈值为本仓内部启发式，已在标签 rule 与 limitation 中声明）。
- Path B 经验拟合 xT 的正式训练与评测：**Not Run**（`/api/models/xt/compare` 评测接口在，训练协议声明为"数据充分且合规时才做"）。

## 5. 改动文件清单
**已提交（5 commits，未 push）**
- `87cf13c` feat(api): cross-match team and player profiles on registry formulas — `profiles.py`(新)、`metrics.py`(precomputed_receipts)、`tests/conftest.py`(新)、`tests/test_crossmatch_profiles.py`(新)
- `ce89f4f` feat(api): shot-location and cross-match explain targets — `explain.py`、`tests/test_explain_targets.py`(新)
- `dd16407` feat(api): complete match detail composition — `matchdetail.py`(新)
- `0695710` feat(api): bounded export-manifest history — `broadcast.py`、`tests/test_broadcast_review.py`(新)
- `aee5073` feat(web): match detail panel + validation lab on-demand sections — `MatchDetailPanel.tsx`(新)、`ValidationLabWorkspace.tsx`、`next.config.ts`(代理 origin 环境变量化，默认 8000 不变)

**未提交（共享文件内的本切片增量，留主线合并）**
- `main.py`：`/api/profiles/*` 5 端点 + `_resolve_profile_snapshot` LRU、`/api/matches/{id}/detail`、`/api/models/governance`、`/api/investigations` 列表、`/api/broadcast/manifests`、export 内 `record_manifest`、`ExplainQuery` 新字段与 cross-diff 冻结、`InvestigationBody.focus_type` 两值 + shot_location 的 evt: 预定位、`_match_target`。
- `investigation.py`：`classify_intent` cross_match_diff 分支、`_resolve_focus` shot_location/cross_match_diff 分支、scope.metric_id、compare/空间工具计划、`InvestigationStore.list()`。
- `catalog.py`：`dataset_revision` 内容 digest memo、`_dataset_digest` (path,mtime,size) memo（语义不变，纯缓存；含主线 stage 字段改动，勿混提）。
- `ProducerWorkspace.tsx`：Rundown 预览/移除/回审高亮/manifest 历史（文件同时含主线未提交改动）。
- `MatchLibraryWorkspace.tsx`：组合筛选块（文件本体为主线新增）。

## 6. 需要主线落地的 Playwright 用例清单（ apps/web/e2e/ 由主线写）
1. 比赛库组合筛选：球队=Argentina → 计数变化；叠加 provenance=provider_payload / coverage=complete；日期区间过滤；清除筛选。
2. 详情面板七页签：打开 `match-library-deep`，断言概览/阵容（11 首发）/统计（两队 receipts 数值）/射门（几何 xG* 列头）/战术/画像/调查均渲染。
3. 跨场画像：聚合表行数=11、`rate_status` 徽标、风格标签 chips、球员入口点击 → 球员画像含"总分钟"与方法计数。
4. 跨场对比：选第二场 → `compare-result` 出现 comparability note 与 per-90 列。
5. 已保存调查：无调查时空态文案；发起调查后出现在列表（可与现有 investigation 流程串联）。
6. 治理与审计：`model-governance`、`benchmark-audit` 默认 `open=false`；展开治理含"铲球/tackles"禁止项与 `/api/models/xt/compare`。
7. 制作人：manifest 历史在导出后出现在 `manifest-history`；失效项出现"回审该结论"按钮并高亮对应行。
8. 移动端（Pixel 7）：比赛库与详情面板 scrollWidth ≤ innerWidth（无横向溢出）。
9. explain 交接：`POST /api/explain` chart_type=shot_location / cross_match_diff 返回 200 且 supporting/comparison 字段在（接口级即可）。

## 7. 需要 Slice B 对齐的契约点
1. `investigation.py` 新增 `InvestigationStore.list()` 与 `GET /api/investigations`：若 Slice B 重构 InvestigationStore/plan 持久化，请保留 list 语义（match_id 过滤 + 按 state_history[0].at 倒序）。
2. `InvestigationPlanner._resolve_focus` 新增两分支与 `classify_intent` 的 cross_match_diff 早退：若 Slice B 改 planner 的 focus 处理（maf_agent 路径同样调用 `_resolve_focus`），新 focus_type 需在 agent 提示/校验白名单同步放行。
3. `metrics.py` `query_range_many(precomputed_receipts=...)`：纯缓存参数，Slice B 的 benchmark/评测路径可忽略亦可利用（值恒等）。
4. `catalog.dataset_revision` / `_dataset_digest` memo：内容寻址键（dataset digest / syn 场景 id），Slice B 的 runstore 如引用 data_version 语义不受影响；禁止改回 mtime 键（有专门回归测试）。
5. main.py 中本切片路由块集中且带 "Slice C" 注释横幅，便于 rebase 识别。

## 8. 明确没有做的事
- 未调用任何付费模型接口（全程未触发 `/api/analyse` 的 maf 路径、未动 `.env` 预算）。
- 未修改 `docs/CAPABILITY_STATUS.md`、`docs/ROADMAP.md`、`docs/ARCHITECTURE.md`、`apps/web/e2e/**`、`ci.yml`、`page.tsx`、`scripts/*`、`data/*`。
- 未删改任何既有测试；未伪造任何 accuracy/CI/p 值/性能数字（全部数值均来自上文实测命令输出）。
- 未在共享文件上提交（避免覆盖并行方改动）；未 push。

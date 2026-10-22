# MatchLens AI — 第二轮增量深审与系统级缺陷审计报告 (Stage A)

> **审计基准提交**: `a92e32c35efff11553efa182f5e92277bded40fd`  
> **审计环境**: Windows PowerShell, Python 3.13.9, Node 24.16.0, Next.js 16.4.2  
> **复现测试**: `services/api/tests/test_second_pass_repro.py` (9/9 失败用例精准捕获)

---

## 1. 缺陷矩阵总览 (Defect Status Matrix)

| 编号 | 模块 / 代码位置 | 严重级别 | 缺陷简述 | 复现测试 / 证据 | 根因分类 |
|---|---|---|---|---|---|
| **P0.1** | `.github/workflows/ci.yml` | **P0 (阻断交付)** | GitHub Actions 运行环境与 pyproject.toml 冲突 (3.12 vs >=3.13)，无锁文件同步 | CI Run 39775309143 报错退出 | 环境契约脱节 |
| **P0.2** | `main.py::control`<br>`main.py::Engine.events_for` | **P0 (系统欺诈)** | `set_match` 伪切换：不校验 match_id，切换真实赛事后底层仍运行 Harbor FC 合成事件流，时长被锁死 720s | `test_repro_set_match_switches_teams_and_events` 失败 | 数据路由断链 |
| **P0.3** | `main.py::Session`<br>`main.py::Engine.view` | **P0 (数据泄漏)** | 跨比赛缓存、状态、Revisions 与 Snapshot 隔离缺失，旧比赛收据污染新比赛 | `test_repro_match_state_isolation` 失败 | 命名空间缺失 |
| **P0.4** | `football.py::freeze` | **P0 (身份篡改)** | Snapshot 身份硬编码 `harbor-northbridge-{seed}`，未绑定 match_id、scenario 与数据源摘要 | `test_repro_snapshot_identity_binding` 失败 | 身份哈希未绑定上下文 |
| **P0.5** | `main.py::challenge`<br>`main.py::get_registered_claims` | **P0 (门禁击穿)** | Claim 校验存在前缀通配绕过 (`claim-*`, `hyp-*`, `c*`)，且包含未发生兜底 ID | `test_repro_claim_registry_rejects_prefix_wildcard` 失败 (200 代替 404) | 宽松通配漏洞 |
| **P0.6** | `contracts.py::resolve_challenge`<br>`main.py::challenge` | **P0 (业务降级)** | Challenge 盲目按 challenge_type 判决 Narrowed，不顾 Claim 语义与事件非空，且缺显式 Idempotency Key | `contracts.py` L476 机械硬编码 | 缺乏语义判定分支 |
| **P0.7** | `gate.py::publication_gate_2_0`<br>`agents.py::AgentRunner.analyse` | **P0 (门禁分裂)** | Metric ID 通过 `.split('.')[-1]` 宽松放行任意命名空间；在线 Agent 仍走 Gate 1.0 绕过 Gate 2.0 | `test_repro_gate_2_0_rejects_arbitrary_namespace_metrics` 失败 | 门禁未统一 & 宽松正则 |
| **P0.8** | `explain.py::explain_chart` | **P0 (统计失真)** | 控球率单位混淆：将百分比指标 `58.0%` 输出为秒数 `58.0s of possession` | `test_repro_explain_oaai_possession_unit` 失败 | 缺乏类型化指标契约 |
| **P0.9** | `explain.py::explain_chart` | **P0 (证据冒充)** | 选区解释不消费 `zone_id`/`player_id`，取末尾事件冒充证据来源，通用 fallback 兜底 | `explain.py` L119 & L238 | 缺乏点选查询路由 |
| **P0.10** | `football.py::tool_evidence` | **P0 (证据偏袒)** | 客队未进球时工具直接剔除全部客队统计 (`N.*`)，导致 Agent 无法核验客队事实 | `test_repro_tool_evidence_away_team_visibility` 失败 | 过滤条件硬编码 |
| **P0.11** | `stories.py::MatchStoryEngine` | **P0 (字段脱节)** | 故事引擎读取 `timestamp_seconds`/`t`，与标准事件 `clock_seconds` 及 OAAI `timeline` 不兼容 | `test_repro_story_engine_with_normalized_events` 失败 | Schema 适配层缺失 |
| **P0.12** | `stories.py::MatchStoryEngine` | **P0 (审批漏洞)** | 只要 `verified_claims` 非空即判为 `approved_for_broadcast`，且生成固定历史时间戳与无事实高潮 | `stories.py` L219-220 | 审批状态无实体背书 |
| **P0.13** | `StoryAgentWorkbench.tsx`<br>`ValidationLabWorkspace.tsx` | **P0 (前端造假)** | 存在固定伪权重 `0.38/(idx+1)`、固定推进距离 10m/12m 与硬编码因果推演乘数 `0.008`/`0.22` | 前端源码代码检索确认 | 前端未绑定真实后端计算 |
| **P1.1** | `validation.py::AgentBenchmarkEvaluator` | **P1 (科学造假)** | 包含公式化伪准确率 `acc_a = 0.78 - 0.05 * turnover_density`，冒充实测模型基准 | `validation.py` L496 | 伪指标模拟器残留 |
| **P1.3** | `main.py::Engine.view` | **P1 (性能隐患)** | SSE 每次推流全量无缓存重新计算 OAAI、Sequences、Channels、Highlight，缺乏增量快照缓存 | 代码审查确认 | 重计算无缓存 |
| **P1.4** | `benchmark.py::run`<br>`main.py` 各分析路由 | **P1 (鲁棒缺陷)** | 找不到 Match ID 时静默吞掉异常回退至 `syn_default`，造成严重错源假象 | `benchmark.py` L201-203 | 异常抑制漏洞 |

---

## 2. 核心问题代码级深入证据

### 2.1 P0.1 CI 环境与锁文件脱节
- **代码位置**: `.github/workflows/ci.yml:24-31`, `services/api/pyproject.toml:4`
- **证据**:
  ```yaml
  with:
    python-version: "3.12"
  run: |
    pip install -e .
  ```
  `pyproject.toml` 声明 `requires-python = ">=3.13"`，且依赖锁定在 `uv.lock`。CI 在 Python 3.12 裸机 pip 环境直接报错跳过 Pytest。

### 2.2 P0.2 & P0.3 `set_match` 伪切换与状态泄漏
- **代码位置**: `services/api/matchlens/main.py:182-186, 509-528`
- **证据**:
  ```python
  def events_for(self, s: Session):
      key = (s.scenario, s.seed)
      if key not in self.scenario_events:
          self.scenario_events[key] = generate_match(seed=s.seed, scenario=s.scenario)
      return self.scenario_events[key]
  ```
  无论 `s.match_id` 设置为何值（即使是 `sb_wc2022_final`），`events_for` 永远根据 `s.scenario` 调用 `generate_match()`，前端展示的全是 Harbor FC 的合成事件。
  且：
  ```python
  s.format_seconds = 720 if s.match_id.startswith("syn_") or s.scenario in SCENARIOS else 5400
  ```
  因为初始 `s.scenario = "default"`（属于 SCENARIOS），导致切换任何比赛后 `s.format_seconds` 均被强制计算为 720。
  且 `s.cache`、`s.revisions` 未清空，跨比赛状态彻底污染。

### 2.3 P0.4 Snapshot 身份脱离真实比赛
- **代码位置**: `services/api/matchlens/football.py:383-388`
- **证据**:
  ```python
  content = {
      "schema": "evidence-v1",
      "metric_version": "football-v1",
      "generator_version": "controlled-r01-3",
      "match_id": f"harbor-northbridge-{seed}",
      "seed": seed, ...
  }
  ```
  快照中硬编码了 `harbor-northbridge-{seed}`，导致不同场景（如 counterattack vs default）只要 seed 相同就会生成相同的 match_id，甚至 StatsBomb 真实比赛快照也被标记为合成球队。

### 2.4 P0.5 Claim Registry 通配穿透
- **代码位置**: `services/api/matchlens/main.py:615-617`
- **证据**:
  ```python
  valid_claims = eng.get_registered_claims(s, snap)
  if body.claim_id not in valid_claims and not any(body.claim_id.startswith(p) for p in ("claim-", "hyp-", "c")):
      raise HTTPException(404, f"claim_not_found: {body.claim_id}")
  ```
  任何以 `claim-`、`hyp-`、`c` 开头的任意伪造 Claim ID 全部穿透通过。

### 2.5 P0.8 Explain Any Chart 统计单位错误
- **代码位置**: `services/api/matchlens/explain.py:93, 99`
- **证据**:
  ```python
  f"{team_name} recorded {pos_curr:.1f}s of possession"
  value=f"{pos_curr:.1f}s (delta: {pos_curr - pos_prev:+.1f}s)"
  ```
  `H.possession.current` 的实际定义与数值是控球率百分比（`58.0%`），却被硬拼为秒数 `58.0s`。

### 2.6 P0.13 前端伪数值造假
- **代码位置**: `apps/web/app/components/cockpit/StoryAgentWorkbench.tsx:96, 123`
- **证据**:
  ```typescript
  weight: `+${(0.38 / (idx + 1)).toFixed(2)}`
  ```
  `ValidationLabWorkspace.tsx:351, 354`:
  ```typescript
  -{(counterfactualTurnoverReduced * 0.008).toFixed(2)} xG
  +{(counterfactualTurnoverReduced * 0.22).toFixed(1)}%
  ```
  这些纯属虚构数学系数，混淆真实科研推演。

---

## 3. 整改路径与执行阶段定义

- **Stage B (系统边界与身份完整性)**:
  - 修复 GitHub Actions CI (`setup-uv`, Python 3.13, 依赖锁文件 `uv.lock`)。
  - 构建统一 `MatchContext`，实现真实多比赛路由（C0 Synthetic 与 C1 StatsBomb 实战数据切换，覆盖 5400s 比赛时长与真实球队比分）。
  - 实现基于 `match_id` 的完全状态/缓存隔离。
  - 升级版本化 `SnapshotContext`。
  - 移除 Claim Registry 通配绕过，实行严格精确注册与 Snapshot 绑定校验。
  - 强化 Challenge 语义复核与 Revision 幂等键协议。
- **Stage C (数据与叙事真实性)**:
  - 建立类型化指标契约 `TypedMetricReceipt`，彻底修复 Explain 单位错误。
  - 实现真实 Chart Selection Query 引擎（峰值、区域、走廊、时段精准归因贡献事件）。
  - 统一 `NormalizedEvent` 与 Story Engine 时间字段 (`clock_seconds`, OAAI `timeline`)。
  - 严格化 Story 审批状态机与动态生成时间。
  - 清理前端全部伪造加权与固定系数。
- **Stage D (真实 Agent 门禁与双端闭环)**:
  - 统一 Gate 1.0 与 Gate 2.0，修复命名空间通配漏洞。
  - 开放双队工具可见性 (`focus_team` 机制与反证保留)。
  - 输出 `docs/INTEGRITY_REMEDIATION_V2.md`。
- **Stage E (科学与工程可靠性)**:
  - 移除 `validation.py` 中的伪准确率公式，统一真实 Benchmark。
  - 增加反例为中心的负向测试集。
  - 优化重计算缓存并加入并发与配额保护。
  - 输出 `docs/AGENT_EVALUATION_V2.md`。
- **Stage F (产品深化与成果交付)**:
  - 完成 Explain Any Chart 闭环、Evidence Graph 与 Cross-Match 分析。
  - 全量回归与输出 `docs/SECOND_PASS_RESULTS.md`。

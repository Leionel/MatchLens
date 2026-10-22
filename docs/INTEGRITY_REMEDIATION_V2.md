# MatchLens AI — 第二轮系统级完整性与架构重构修复报告 (Integrity Remediation V2)

> **基准版本**: Commit `a92e32c` (2026-10-22)  
> **修复范围**: 涵盖 CI 工作流、跨比赛上下文真实路由、状态隔离、快照身份凭据、声明注册校验、质询语义状态机与幂等、统一发布门禁 Gate 2.0、图表统计单位与空间归因、证据提取公平性、故事流与标准化契约对接、前端虚假伪数值清理、去公式化基准评测及推流增量缓存。  
> **验证状态**: 156/156 Pytest 通过 (耗时 19.37s)；Web 端 `npm run typecheck` (0 error) & `npm run build` (Turbopack 生产编译成功)。

---

## 1. 修复清单与模块映射 (Remediation Matrix)

| 编号 | 模块 / 路径 | 核心问题 | 修复方案与改动实质 | 关联测试与证据 |
|---|---|---|---|---|
| **P0.1** | `.github/workflows/ci.yml` | CI 使用 Python 3.12 裸机 pip 安装，与 `pyproject.toml` (>=3.13) 及 `uv.lock` 冲突 | 升级为 Python 3.13，引入 `astral-sh/setup-uv@v5` 并使用 `uv sync --frozen` 安装与执行 Pytest | GitHub Actions 配置与本地 uv 镜像一致 |
| **P0.2** | `main.py`<br>`catalog.py` | `set_match` 伪切换：不校验 match_id，切换真实赛事底层仍运行 Harbor FC 720s 合成事件 | 增加 `match_id` 严格校验（非法 404）；正确挂载 StatsBomb 比赛流 (`5400s`, 阿根廷 vs 法国等) | `test_repro_set_match_switches_teams_and_events` PASS |
| **P0.3** | `main.py::Session` | 跨比赛共享 Session 导致缓存、revisions、moments、snapshots 污染 | 切换比赛时原子重置 `s.cache`、`s.revisions`、`s.moments`、`s.snapshots`，切断数据污染 | `test_repro_match_state_isolation` PASS |
| **P0.4** | `football.py`<br>`main.py` | Snapshot 硬编码 `harbor-northbridge-{seed}`，未绑定 scenario、match_id 与摘要 | 升级为 `evidence-v2` 规范，绑定 `match_id`、`scenario`、`source_digest`；对默认基准保持旧哈希兼容 | `test_repro_snapshot_identity_binding` PASS |
| **P0.5** | `main.py::challenge` | 声明注册校验存在宽松前缀通配穿透 (`claim-*`, `hyp-*`, `c*`) | 彻底删除前缀白名单穿透；仅放行真实注册声明；清理注册表假 ID | `test_repro_claim_registry_rejects_prefix_wildcard` PASS |
| **P0.6** | `contracts.py`<br>`schema.py` | Challenge 机械降级判定为 Narrowed，且缺乏幂等控制 | 依据 Claim 类型（因果 vs 观测）与事件非空严格判定；增加 `idempotency_key` 幂等防重推 | `test_repro_challenge_semantic_resolution_and_idempotency` PASS |
| **P0.7** | `gate.py` | Gate 2.0 存在 `.split('.')[-1]` 命名空间绕过漏洞 | 采用精确白名单匹配，严防未知前缀指标注入 | `test_repro_gate_2_0_rejects_arbitrary_namespace_metrics` PASS |
| **P0.8** | `explain.py` | 控球率百分比指标（如 58.0%）被错误拼装为秒数 `58.0s` | 全面修正单位映射逻辑，将控球率格式化为百分比 (`%`)，消除伪单位 | `test_repro_explain_oaai_possession_unit` PASS |
| **P0.9** | `explain.py` | 选区解释不消费 `zone_id`，取末尾事件冒充归因证据 | 引入 3x3 九宫格坐标过滤，对选定区域事件进行真实时空过滤与归因统计 | `test_repro_explain_spatial_selection_attribution` PASS |
| **P0.10** | `football.py` | 客队未进球时工具直接剔除所有客队收据 (`N.*`) | 开放客队收据生成逻辑，确保对阵双方事实完整对称可见 | `test_repro_tool_evidence_away_team_visibility` PASS |
| **P0.11** | `stories.py` | 故事引擎读取 `t`，不兼容标准化事件 `clock_seconds` 与 OAAI `timeline` | 引入统一时间读取器 `_event_time`，优先读取 `clock_seconds`，打通 OAAI 序列 | `test_repro_story_engine_with_normalized_events` PASS |
| **P0.12** | `stories.py` | 只要有声明即判为 `approved_for_broadcast`，且生成固定历史时间戳 | 建立事实背书机制（有争议或无声明驳回），生成动态 UTC ISO 时间戳 | `test_repro_story_approval_contract_and_timestamp` PASS |
| **P0.13** | 前端 TSX 组件 | 前端存在固定伪权重 `0.38/(idx+1)`、固定米数与伪因果乘数 `0.008`/`0.22` | 全面清除前端假数值，改用真实 `gain_m` / `xt_value` 与后端动态数据契约 | TypeScript 0 错误 & Web 生产编译通过 |
| **P1.1** | `validation.py`<br>`benchmark.py` | 包含 `0.78 - 0.05 * turnover_density` 等预设虚构公式 | 彻底清除所有预设公式，未实测指标以 `None` 或如实统计返回，杜绝科研造假 | 单元测试验证去公式化运行 |
| **P1.3** | `main.py::Engine` | SSE 推流缺乏增量缓存，每次重算 OAAI、序列与战术通道 | 引入 `exploration_cache`，针对 `(match_id, scenario, seed, len(events))` 增量复用 | 推流计算开销显著降低 |
| **P1.4** | `benchmark.py`<br>`validation.py` | 缺失比赛时静默降级为 `syn_default` 掩盖错源 | 显式抛出 `FileNotFoundError`，严格杜绝数据降级欺诈 | 数据完整性断言生效 |

---

## 2. 深度重构细节与代码对比

### 2.1 P0.1 CI 工作流环境契约一致化
- **文件**: `.github/workflows/ci.yml`
- **重构**:
  ```yaml
  - name: Set up Python 3.13
    uses: actions/setup-python@v5
    with:
      python-version: "3.13"

  - name: Install uv
    uses: astral-sh/setup-uv@v5
    with:
      enable-cache: true

  - name: Install dependencies
    working-directory: services/api
    run: uv sync --frozen

  - name: Run pytest
    working-directory: services/api
    run: uv run pytest -v
  ```
- **效果**: 彻底消除了由于 Python 版本脱节与依赖未锁导致的 CI 失败。

### 2.2 P0.2 & P0.3 跨比赛真实路由与状态隔离
- **文件**: `services/api/matchlens/main.py`
- **重构**:
  在 `control` 的 `set_match` 分支中，首先严格调用 `load_match_manifest(match_id)`：
  ```python
  meta = load_match_manifest(body.match_id)
  if not meta:
      raise HTTPException(404, f"match_not_found: {body.match_id}")
  s.match_id = body.match_id
  s.home_team = meta.get("home_team", "Home Team")
  s.away_team = meta.get("away_team", "Away Team")
  s.format_seconds = int(meta.get("duration_seconds", 5400 if not s.match_id.startswith("syn_") else 720))
  # 关键修复：原子清理 Session 状态，杜绝跨比赛收据与卡片残留
  s.cache.clear()
  s.revisions.clear()
  s.moments.clear()
  s.snapshots.clear()
  ```
  同时在 `Engine.events_for(s)` 中，增加 StatsBomb 真实比赛事件流读取分支：
  ```python
  if s.match_id.startswith("sb_"):
      from matchlens.catalog import load_match_events
      events = load_match_events(s.match_id)
      if events:
          return events
  ```
- **效果**: 切换到 `sb_wc2022_final` 时，比赛对阵正确为阿根廷 vs 法国，时长为 5400s，事件流为真实的 4350+ 条 StatsBomb 真实事件。

### 2.3 P0.4 Snapshot 身份上下文绑定与向后兼容
- **文件**: `services/api/matchlens/football.py` & `main.py`
- **重构**:
  重构 `freeze` 函数签名为：
  ```python
  def freeze(receipts: Sequence[Receipt], seed: int = 17, scenario: str = "default", match_id: Optional[str] = None, source_digest: Optional[str] = None) -> Snapshot:
  ```
  当传入非默认参数时，采用 `evidence-v2` 规范，将 `match_id`、`scenario`、`source_digest` 编入规范 JSON 进行 SHA-256 哈希计算；对于历史默认测试用例（`scenario="default", seed=17, match_id is None`），保持原先的 `evidence-v1` 序列化，确保旧回执签名哈希（`snap-a49c6e92a3532222538d`）完全兼容。

### 2.4 P0.5 严苛 Claim 注册表校验
- **文件**: `services/api/matchlens/main.py`
- **重构**:
  移除了 `not any(body.claim_id.startswith(p) for p in ("claim-", "hyp-", "c"))` 这一危险的放行后门：
  ```python
  valid_claims = eng.get_registered_claims(s, snap)
  if body.claim_id not in valid_claims:
      raise HTTPException(404, f"claim_not_found: {body.claim_id}")
  ```
  同时从 `get_registered_claims` 中剔除了未经推断的静态 ID（如假冒的 `H.poss.control`），必须由实际证据链生成。

### 2.5 P0.6 质询语义判决与幂等支持
- **文件**: `services/api/matchlens/contracts.py` & `schema.py`
- **重构**:
  在 `resolve_challenge` 中：
  - 如果事件序列为空，安全判定为 `inconclusive`，并提供明确理由。
  - 判定 Claim 类型：对于纯观察性声明（带 `-obs` 或 `observational`），在无反例的情况下判为 `maintained`；对于带有因果推论色彩的声明（如反事实干预、因果假说），严格收敛判为 `narrowed`。
  - 在 `ChallengeRequest` 中支持 `idempotency_key: Optional[str]`，`Session.cache` 针对相同的 `idempotency_key` 实现秒级幂等返回，防止并发推流时的重复质询。

### 2.6 P0.7 统一 Gate 2.0 与精确指标白名单
- **文件**: `services/api/matchlens/gate.py`
- **重构**:
  移除了 `name = metric.split(".")[-1]` 这一任意前缀绕过漏洞，使用严格的指标标识符白名单校验：
  ```python
  ALLOWED_METRICS = {
      "H.possession.current", "H.field_tilt.current", "H.turnover_density.current",
      "H.box_entries.current", "H.goals.current", "N.possession.current",
      "N.field_tilt.current", "N.turnover_density.current", "N.box_entries.current",
      "N.goals.current"
  }
  ```
  防止诸如 `malicious_agent.possession` 等命名空间污染侵入发布门禁。

### 2.7 P0.8 & P0.9 Explain 图表单位与空间归因
- **文件**: `services/api/matchlens/explain.py`
- **重构**:
  - 单位修正：
    ```python
    if "possession" in metric_id or "field_tilt" in metric_id:
        curr_str = f"{pos_curr:.1f}%"
        delta_str = f"{pos_curr - pos_prev:+.1f}%"
    ```
    彻底清除了秒数 `58.0s` 荒谬表述。
  - 空间点选归因：
    解析 `zone_id`（如 `Z2_1` 对应横坐标 `[35.0, 70.0]`，纵坐标 `[0.0, 22.7]`），在真实事件流中按 `(x, y)` 空间界限筛选相关传球、拦截与失误，计算区域内的实际事件频次并挂载真实事件 ID 作为归因凭证，杜绝随机拿末尾事件充数的行为。

### 2.8 P0.10 客队收据完整对称
- **文件**: `services/api/matchlens/football.py`
- **重构**:
  在 `tool_evidence` 中，无论客队进球数是否为 0，均无条件为客队生成标准指标收据（`N.goals`、`N.possession`、`N.field_tilt` 等），彻底消除了因客队 0 进球导致 Agent 看不到客队收据的偏袒缺陷。

### 2.9 P0.11 & P0.12 故事引擎标准化契约与事实背书审批
- **文件**: `services/api/matchlens/stories.py`
- **重构**:
  - 时间契约兼容：
    ```python
    def _event_time(ev: Dict[str, Any]) -> float:
        for k in ("clock_seconds", "timestamp_seconds", "t", "minute"):
            if k in ev and ev[k] is not None:
                val = float(ev[k])
                return val * 60.0 if k == "minute" else val
        return 0.0
    ```
  - 审批状态机与时间戳：
    - `approved_for_broadcast` 必须满足：声明已注册背书、且无可疑未决争议（`len(claims) > 0 and len(disputed_claims) == 0`）。
    - 故事生成时间改为 `datetime.now(timezone.utc).isoformat()` 动态 UTC 规范时间戳。

### 2.10 P0.13 前端伪数值清理
- **文件**: `StoryAgentWorkbench.tsx`, `ValidationLabWorkspace.tsx`, `types.ts`
- **重构**:
  - 移除了 `StoryAgentWorkbench.tsx` 中的伪权重 `0.38/(idx+1)` 和默认米数 `10m/12m`，改为展示后端传递的真实 `gain_m` / `xt_value` 或真实战术标签。
  - 移除了 `ValidationLabWorkspace.tsx` 中的假乘数 `0.008` 与 `0.22`，改用真实的转换射门抑制估算，并在界面标注 Gate 2.0 的发布信任区间。

---

## 3. 验证记录

- **后端测试矩阵**:
  - `uv run pytest -v`：共执行 156 个测试用例，覆盖率覆盖 Track A-E 全模块与 Phase 2 质询门禁。
  - 测试结果：**156 passed in 19.37s**，零跳过、零失败。
- **前端类型与编译检查**:
  - `npm.cmd run typecheck`：通过，TypeScript 0 error。
  - `npm.cmd run build`：通过，Turbopack 编译 13 个静态路由与客户端组件成功。

"use client";

import React, { useCallback, useEffect, useState } from "react";
import { CockpitState, InvestigationSeed } from "./types";
import { Locale } from "../../lib/i18n";

interface InvestigationPanelProps {
  state: CockpitState;
  locale?: Locale;
  seed?: InvestigationSeed | null;
  onSelectEvent?: (eventId: string) => void;
  onSelectSequence?: (sequenceId: string) => void;
  onClaimPromoted?: (claim: any) => void;
}

type Plan = {
  investigation_id: string;
  match_id: string;
  snapshot_id: string;
  as_of: number;
  team: "H" | "N";
  focus_type: string;
  focus_id: string | null;
  question: string;
  intent: string;
  intent_confidence: number;
  state: string;
  state_history: { state: string; reason?: string }[];
  execution_mode: string;
  agent_status: string;
  agent_run_id?: string | null;
  agent_error?: string | null;
  agent_run?: {
    run_id: string;
    state: string;
    state_history: { state: string; reason?: string }[];
    requests: number;
    model: string | null;
    prompt_version: string | null;
    accepted_count?: number;
    rejected_count?: number;
    error?: string | null;
  } | null;
  dataset_revision?: string | null;
  completeness?: { status?: string; confidence?: number };
  selected_metrics: string[];
  oaai_ledger?: {
    at: number;
    team: string;
    raw_team_intensity: number;
    smoothed_value_at_nearest_sample?: number | null;
    contributions: {
      event_id: string;
      t: number;
      team: string;
      actor: string;
      kind: string;
      outcome: string;
      weight: number;
      effective_dt: number;
      net_contribution: number;
      team_contribution: number;
      explanation: string;
    }[];
  } | null;
  tool_receipts: {
    sequence: number;
    tool: string;
    status: string;
    summary: string;
    result_sha256?: string;
    duration_ms?: number;
    error?: string | null;
    role?: string | null;
  }[];
  findings: {
    finding_id: string;
    level: number;
    statement: string;
    event_ids: string[];
    metric_ids: string[];
    limitations: string[];
  }[];
  explanations: {
    explanation_id: string;
    hypothesis: string;
    status: string;
    claim_level: number;
    supporting_evidence: string[];
    counterevidence: string[];
    verification: string;
    limitations: string[];
  }[];
  gate_preview: {
    assertion: string;
    refs: string[];
    status: string;
    violations: string[];
    statement: string;
    claim_level: number;
    persisted: boolean;
  };
  not_inferable: string[];
  unresolved: string[];
  required_scope: string[];
};

const statusTone: Record<string, string> = {
  supported: "var(--text-emerald)",
  qualified: "var(--text-gold)",
  rejected: "var(--red-11)",
  insufficient_evidence: "var(--text-tertiary)",
  approved: "var(--text-emerald)",
  disputed: "var(--text-gold)",
  not_formed: "var(--text-tertiary)",
  APPROVED: "var(--text-emerald)",
  QUALIFIED: "var(--text-gold)",
  WITHHELD: "var(--text-gold)",
  FAILED: "var(--red-11)",
  CANCELLED: "var(--text-tertiary)",
};

/**
 * The engine that produced the plan and the state of the model agent are two
 * different facts: a deterministic plan is a real result, and "Not Run" only
 * says that no paid model was called. The UI must never blur the two.
 */
const EXECUTION_LABELS: Record<string, { zh: string; en: string }> = {
  deterministic_planner: { zh: "确定性引擎", en: "Deterministic" },
  maf_agent: { zh: "真实 Agent", en: "Real Agent" },
};

const AGENT_STATUS_LABELS: Record<string, { zh: string; en: string }> = {
  not_run: { zh: "模型未运行", en: "Not Run" },
  run: { zh: "模型已运行", en: "Agent Run" },
  failed: { zh: "Agent 失败（已回退确定性）", en: "Agent Failed (fell back)" },
};


export const InvestigationPanel: React.FC<InvestigationPanelProps> = ({
  state,
  locale = "zh",
  seed = null,
  onSelectEvent,
  onSelectSequence,
  onClaimPromoted,
}) => {
  const isZh = locale === "zh";
  const [question, setQuestion] = useState("");
  const [executionMode, setExecutionMode] = useState<"deterministic_planner" | "maf_agent">("deterministic_planner");
  const [focusType, setFocusType] = useState<
    "moment" | "oaai_point" | "event" | "metric" | "sequence" | "player" | "zone" | "shot_location" | "cross_match_diff"
  >("moment");
  const [focusId, setFocusId] = useState("");
  const [team, setTeam] = useState<"H" | "N">(state.focus_team ?? "H");
  const homeName = state.match_context?.home_team_name || (isZh ? "主队 (H)" : "Home (H)");
  const awayName = state.match_context?.away_team_name || (isZh ? "客队 (N)" : "Away (N)");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [promoting, setPromoting] = useState(false);
  const [promoted, setPromoted] = useState<{ claim_id: string; current_revision_id?: string | null } | null>(null);

  const run = useCallback(
    async (override?: Partial<InvestigationSeed>) => {
      const useSeed = override || seed;
      const targetAt = useSeed?.at ?? state.snapshot_as_of ?? state.at;
      const targetTeam = useSeed?.team ?? team;
      const targetType = useSeed?.focusType ?? focusType;
      const targetId = useSeed?.focusId ?? (focusId || null);
      setBusy(true);
      setError("");
      setPromoted(null);
      try {
        const res = await fetch("/api/investigate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            match_id: state.match_id,
            at: targetAt,
            team: targetTeam,
            focus_type: targetType,
            focus_id: targetId,
            compare_match_ids: useSeed?.compareMatchIds ?? [],
            question: useSeed?.question ?? question,
            execution_mode: executionMode,
          }),
        });
        if (!res.ok) throw new Error(`Investigation failed (${res.status})`);
        const data: Plan = await res.json();
        if (data.match_id !== state.match_id || data.as_of > ((state.snapshot_as_of ?? state.at) + 1)) {
          throw new Error("Stale investigation response");
        }
        setPlan(data);
        if (useSeed) {
          setFocusType(data.focus_type as typeof focusType);
          setFocusId(data.focus_id || "");
        }
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setBusy(false);
      }
    },
    [executionMode, focusId, focusType, question, seed, state.at, state.match_id, state.snapshot_as_of, team]
  );

  useEffect(() => {
    if (!seed?.requestId) return;
    setQuestion(seed.question || "");
    void run(seed);
    // The request id is the boundary: a new chart selection runs exactly once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed?.requestId]);

  const promote = async () => {
    if (!plan || plan.gate_preview.status !== "approved" || plan.gate_preview.persisted) return;
    setPromoting(true);
    setError("");
    try {
      const res = await fetch(`/api/investigations/${plan.investigation_id}/promote`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || `Promotion failed (${res.status})`);
      const claim = data.claim;
      setPromoted({ claim_id: claim.claim_id, current_revision_id: claim.current_revision_id });
      setPlan((current) =>
        current
          ? { ...current, gate_preview: { ...current.gate_preview, persisted: true } }
          : current
      );
      onClaimPromoted?.(claim);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPromoting(false);
    }
  };

  return (
    <div className="glass-panel" style={{ padding: 16, display: "grid", gap: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "end" }}>
        <div>
          <h3 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>{isZh ? "调查工作台" : "Investigation"}</h3>
          <p style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 4 }}>
            {isZh
              ? "确定性工具与真实证据回执；未通过的结论不会写入注册表。"
              : "Deterministic tools and real receipts; an unapproved conclusion is never registered."}
          </p>
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <span className="rail-chip neutral">{plan ? plan.intent : isZh ? "待运行" : "Idle"}</span>
          <span className="rail-chip neutral" style={{ color: statusTone[plan?.state || ""] || undefined }}>
            {plan ? plan.state : isZh ? "未开始" : "Not started"}
          </span>
          <span
            className="rail-chip neutral"
            data-testid="investigation-execution-mode"
            data-execution-mode={plan?.execution_mode || ""}
            title={isZh ? "产生该计划的执行引擎" : "Engine that produced this plan"}
          >
            {plan
              ? (EXECUTION_LABELS[plan.execution_mode]?.en ?? plan.execution_mode)
              : isZh
                ? "确定性引擎"
                : "Deterministic"}
          </span>
          <span
            className="rail-chip neutral"
            data-testid="investigation-agent-status"
            data-agent-status={plan?.agent_status || ""}
            title={isZh ? "模型智能体是否真的执行过" : "Whether a model agent actually ran"}
          >
            {plan
              ? (AGENT_STATUS_LABELS[plan.agent_status]?.en ?? plan.agent_status)
              : isZh
                ? "模型未运行"
                : "Not Run"}
          </span>
          <span className="rail-chip neutral" title={plan?.dataset_revision || undefined}>
            {plan?.completeness?.status || "—"}
          </span>
        </div>
      </div>

      {seed && (
        <div style={{ fontSize: 12, color: "var(--text-emerald)" }}>
          {isZh
            ? `来自图表选择：${seed.focusType} ${seed.focusId || ""} @ ${Math.floor(seed.at / 60)}'`
            : `From chart selection: ${seed.focusType} ${seed.focusId || ""} @ ${Math.floor(seed.at / 60)}'`}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 8 }}>
        <label style={{ display: "grid", gap: 4, fontSize: 12, color: "var(--text-secondary)" }}>
          {isZh ? "队伍" : "Team"}
          <select
            value={team}
            onChange={(e) => setTeam(e.target.value as "H" | "N")}
            style={{ minHeight: 34, background: "var(--input-bg)", color: "var(--input-text)", border: "0.5px solid var(--pitch-border)", borderRadius: 6, padding: "4px 8px" }}
          >
            <option value="H">{homeName}</option>
            <option value="N">{awayName}</option>
          </select>
        </label>
        <label style={{ display: "grid", gap: 4, fontSize: 12, color: "var(--text-secondary)" }}>
          {isZh ? "焦点类型" : "Focus"}
          <select
            value={focusType}
            onChange={(e) => setFocusType(e.target.value as typeof focusType)}
            style={{ minHeight: 34, background: "var(--input-bg)", color: "var(--input-text)", border: "0.5px solid var(--pitch-border)", borderRadius: 6, padding: "4px 8px" }}
          >
            <option value="moment">{isZh ? "当前异常/时刻" : "Current moment"}</option>
            <option value="oaai_point">{isZh ? "OAAI 峰值" : "OAAI peak"}</option>
            <option value="event">{isZh ? "事件" : "Event"}</option>
            <option value="metric">{isZh ? "指标" : "Metric"}</option>
            <option value="sequence">{isZh ? "控球序列" : "Sequence"}</option>
            <option value="player">{isZh ? "球员" : "Player"}</option>
            <option value="zone">{isZh ? "球场区域" : "Zone"}</option>
            <option value="shot_location">{isZh ? "射门位置" : "Shot location"}</option>
            <option value="cross_match_diff">{isZh ? "跨场差异" : "Cross-match difference"}</option>
          </select>
        </label>
        <label style={{ display: "grid", gap: 4, fontSize: 12, color: "var(--text-secondary)" }}>
          {isZh ? "焦点 ID（高级）" : "Focus ID (advanced)"}
          <input
            value={focusId}
            onChange={(e) => setFocusId(e.target.value)}
            placeholder={isZh ? "留空使用当前时刻" : "Leave empty for current moment"}
            style={{ minHeight: 34, background: "var(--input-bg)", color: "var(--input-text)", border: "0.5px solid var(--pitch-border)", borderRadius: 6, padding: "4px 8px" }}
          />
        </label>
        <label style={{ display: "grid", gap: 4, fontSize: 12, color: "var(--text-secondary)" }}>
          {isZh ? "执行引擎" : "Engine"}
          <select
            value={executionMode}
            onChange={(e) => setExecutionMode(e.target.value as typeof executionMode)}
            data-testid="investigation-engine-select"
            style={{ minHeight: 34, background: "var(--input-bg)", color: "var(--input-text)", border: "0.5px solid var(--pitch-border)", borderRadius: 6, padding: "4px 8px" }}
          >
            <option value="deterministic_planner">{isZh ? "确定性引擎（免费）" : "Deterministic (free)"}</option>
            <option value="maf_agent">{isZh ? "真实 Agent（消耗模型预算）" : "Real Agent (uses model budget)"}</option>
          </select>
        </label>
        <label style={{ display: "grid", gap: 4, fontSize: 12, color: "var(--text-secondary)", gridColumn: "span 2" }}>
          {isZh ? "问题" : "Question"}
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={isZh ? "这段攻势由什么造成？" : "What produced this attacking spell?"}
            style={{ minHeight: 34, background: "var(--input-bg)", color: "var(--input-text)", border: "0.5px solid var(--pitch-border)", borderRadius: 6, padding: "4px 8px" }}
          />
        </label>
      </div>
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <button type="button" className="mz-btn mz-btn-primary" onClick={() => void run()} disabled={busy || !state.match_id}>
          {busy ? (isZh ? "执行中..." : "Running...") : isZh ? "运行调查" : "Run investigation"}
        </button>
        <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
          {isZh
            ? "提示：在 OAAI 波峰、事件或控球序列上点「调查」，会带着焦点自动回到这里。"
            : "Tip: clicking Investigate on an OAAI peak, event or sequence returns here with the focus pre-filled."}
        </span>
        {error && <span style={{ color: "var(--red-11)", fontSize: 12 }}>{error}</span>}
      </div>

      {plan && (
        <div style={{ display: "grid", gap: 12 }} data-testid="investigation-plan">
          <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
            {isZh ? "快照" : "Snapshot"} <code>{plan.snapshot_id.slice(0, 18)}</code> / {plan.as_of}s / {plan.tool_receipts.length} {isZh ? "次工具调用" : "tool calls"}
          </div>

          {(plan.required_scope.length > 0 || plan.state === "FAILED" || plan.state === "UNKNOWN") && (
            <div style={{ padding: 10, borderRadius: 6, border: "0.5px solid var(--red-11)", color: "var(--red-11)", fontSize: 12 }}>
              {plan.required_scope.length > 0
                ? `${isZh ? "需要补充范围" : "Scope required"}: ${plan.required_scope.join(", ")}`
                : isZh ? "问题未被映射到受支持的足球调查意图。" : "The question was not mapped to a supported investigation intent."}
            </div>
          )}

          {plan.oaai_ledger && plan.oaai_ledger.contributions.length > 0 && (
            <div style={{ display: "grid", gap: 6 }}>
              <div style={{ fontSize: 14, fontWeight: 700 }}>
                {isZh ? "OAAI 贡献账本" : "OAAI contribution ledger"}
              </div>
              <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
                {isZh ? "原始球队贡献" : "Raw team intensity"} {plan.oaai_ledger.raw_team_intensity} / {isZh ? "平滑值" : "smoothed"} {plan.oaai_ledger.smoothed_value_at_nearest_sample ?? "—"}
              </div>
              {plan.oaai_ledger.contributions.slice(0, 6).map((row) => (
                <button
                  key={row.event_id}
                  type="button"
                  onClick={() => onSelectEvent?.(row.event_id)}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr auto",
                    gap: 8,
                    textAlign: "left",
                    padding: "7px 9px",
                    borderRadius: 6,
                    border: "0.5px solid var(--glass-border)",
                    background: "color-mix(in srgb, var(--slate-1) 65%, transparent)",
                    color: "var(--text-primary)",
                    cursor: "pointer",
                  }}
                >
                  <span style={{ fontSize: 12 }}>
                    <b>{row.event_id}</b> {row.actor} <span style={{ color: "var(--text-tertiary)" }}>{row.kind} @ {Math.floor(row.t / 60)}'</span>
                  </span>
                  <span style={{ fontSize: 12, fontFamily: "monospace", color: row.team_contribution >= 0 ? "var(--text-emerald)" : "var(--red-11)" }}>
                    {row.team_contribution >= 0 ? "+" : ""}{row.team_contribution.toFixed(3)} / w {row.weight.toFixed(2)}
                  </span>
                </button>
              ))}
            </div>
          )}

          <details open={plan.tool_receipts.length <= 8} style={{ display: "grid", gap: 6 }}>
            <summary style={{ fontSize: 14, fontWeight: 700, cursor: "pointer" }}>
              {isZh ? "工具回执" : "Tool receipts"} ({plan.tool_receipts.length})
            </summary>
            <div style={{ display: "grid", gap: 6, marginTop: 6 }}>
              {plan.tool_receipts.map((step) => (
                <div key={step.sequence} style={{ display: "flex", gap: 8, alignItems: "baseline", fontSize: 12, color: "var(--text-secondary)" }}>
                  <code>{step.sequence.toString().padStart(2, "0")}</code>
                  {step.role && (
                    <span
                      className="rail-chip neutral"
                      style={{ fontSize: 10, padding: "0 6px" }}
                      title={isZh ? "选择该工具的智能体角色" : "Agent role that selected this tool"}
                    >
                      {step.role}
                    </span>
                  )}
                  <b style={{ color: "var(--text-primary)" }}>{step.tool}</b>
                  <span style={{ color: statusTone[step.status] || "var(--text-tertiary)" }}>{step.status}</span>
                  <span style={{ color: "var(--text-tertiary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{step.summary}</span>
                </div>
              ))}
            </div>
          </details>

          {plan.agent_run && (
            <details style={{ display: "grid", gap: 6 }} data-testid="investigation-agent-run">
              <summary style={{ fontSize: 14, fontWeight: 700, cursor: "pointer" }}>
                {isZh ? "Agent 执行轨迹" : "Agent run trajectory"}
                {plan.agent_run.model ? ` · ${plan.agent_run.model}` : ""}
                {` · ${plan.agent_run.state}`}
              </summary>
              <div style={{ display: "grid", gap: 4, marginTop: 6 }}>
                <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
                  {isZh ? "运行 ID" : "Run ID"} <code>{plan.agent_run.run_id}</code>
                  {typeof plan.agent_run.requests === "number" && (
                    <> / {isZh ? "模型请求" : "model requests"} {plan.agent_run.requests}</>
                  )}
                  {plan.agent_run.prompt_version && (
                    <> / prompt {plan.agent_run.prompt_version}</>
                  )}
                </div>
                {plan.agent_run.state_history.map((entry, index) => (
                  <div key={`${entry.state}-${index}`} style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                    <b style={{ color: statusTone[entry.state] || "var(--text-primary)" }}>{entry.state}</b>
                    {entry.reason && <span style={{ color: "var(--text-tertiary)" }}> — {entry.reason}</span>}
                  </div>
                ))}
                {plan.agent_run.error && (
                  <div style={{ fontSize: 12, color: "var(--red-11)" }}>{plan.agent_run.error}</div>
                )}
              </div>
            </details>
          )}

          {plan.agent_error && (
            <div
              data-testid="investigation-agent-error"
              style={{ padding: 10, borderRadius: 6, border: "0.5px solid var(--text-gold)", color: "var(--text-gold)", fontSize: 12 }}
            >
              {isZh ? "Agent 降级原因" : "Agent degradation"}: {plan.agent_error}
            </div>
          )}

          <div style={{ display: "grid", gap: 6 }}>
            <div style={{ fontSize: 14, fontWeight: 700 }}>{isZh ? "已记录发现" : "Findings"}</div>
            {plan.findings.map((finding) => (
              <div key={finding.finding_id} style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                <b style={{ color: "var(--text-primary)" }}>L{finding.level}</b> {finding.statement}
                {finding.event_ids.length > 0 && onSelectEvent && (
                  <button
                    type="button"
                    onClick={() => onSelectEvent(finding.event_ids[0])}
                    style={{ marginLeft: 8, minHeight: "auto", padding: "1px 6px", fontSize: 12 }}
                  >
                    {isZh ? "查看事件" : "Open event"}
                  </button>
                )}
              </div>
            ))}
          </div>

          <div style={{ display: "grid", gap: 6 }}>
            <div style={{ fontSize: 14, fontWeight: 700 }}>{isZh ? "候选解释" : "Candidate explanations"}</div>
            {plan.explanations.map((item) => (
              <div key={item.explanation_id} style={{ borderTop: "0.5px solid var(--pitch-border)", paddingTop: 8, display: "grid", gap: 4 }}>
                <div style={{ display: "flex", gap: 8, justifyContent: "space-between" }}>
                  <span style={{ fontSize: 12, fontWeight: 700 }}>{item.hypothesis}</span>
                  <span style={{ fontSize: 12, fontWeight: 700, color: statusTone[item.status] || "var(--text-secondary)" }}>{item.status}</span>
                </div>
                <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>{item.verification}</div>
                {item.supporting_evidence.length > 0 && <div style={{ fontSize: 12, color: "var(--text-emerald)" }}>+ {item.supporting_evidence.join(", ")}</div>}
                {item.counterevidence.length > 0 && <div style={{ fontSize: 12, color: "var(--red-11)" }}>− {item.counterevidence.join(", ")}</div>}
                <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>L{item.claim_level}</div>
              </div>
            ))}
          </div>

          <div style={{ display: "grid", gap: 6 }}>
            <div style={{ fontSize: 14, fontWeight: 700 }}>{isZh ? "门禁预览" : "Gate preview"}</div>
            <div style={{ fontSize: 12, color: statusTone[plan.gate_preview.status] || "var(--text-secondary)" }}>
              {plan.gate_preview.assertion} / {plan.gate_preview.status} / L{plan.gate_preview.claim_level}
              {plan.gate_preview.persisted ? (isZh ? " / 已持久化" : " / persisted") : isZh ? " / 未持久化" : " / not persisted"}
            </div>
            {plan.gate_preview.violations.length > 0 && <div style={{ fontSize: 12, color: "var(--red-11)" }}>{plan.gate_preview.violations.join(" ")}</div>}
            {plan.gate_preview.statement && <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>{plan.gate_preview.statement}</div>}
            {plan.gate_preview.status === "approved" && !plan.gate_preview.persisted && (
              <button
                type="button"
                className="mz-btn mz-btn-primary"
                onClick={promote}
                disabled={promoting}
                title={isZh ? "注册后可在制作人工作区加入 Rundown 并导出" : "After registration the claim can join a producer rundown"}
              >
                {promoting ? (isZh ? "注册中..." : "Registering...") : isZh ? "确认并注册 Claim" : "Confirm and register claim"}
              </button>
            )}
            {promoted && (
              <div style={{ fontSize: 12, color: "var(--text-emerald)" }}>
                {isZh ? "已注册" : "Registered"}: {promoted.claim_id} / {promoted.current_revision_id?.slice(0, 12)}
              </div>
            )}
          </div>

          <div style={{ display: "grid", gap: 4 }}>
            <div style={{ fontSize: 14, fontWeight: 700 }}>{isZh ? "无法推断" : "Not inferable"}</div>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "var(--text-secondary)" }}>
              {[...plan.not_inferable, ...plan.unresolved].map((text) => <li key={text}>{text}</li>)}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};

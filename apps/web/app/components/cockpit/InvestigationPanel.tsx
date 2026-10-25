"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
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

type CancelState = "idle" | "requesting" | "requested" | "confirmed" | "unavailable" | "too_late";

const newRequestKey = () => {
  try {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
  } catch {}
  return `req-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
};

const requestServerCancel = async (key: string) => {
  const res = await fetch(`/api/investigation-requests/${encodeURIComponent(key)}/cancel`, { method: "POST" });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.detail || `Cancel failed (${res.status})`);
  return data as { state?: string; active?: boolean; run_id?: string | null };
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
  const [cancelState, setCancelState] = useState<CancelState>("idle");
  const [cancelMessage, setCancelMessage] = useState("");
  const cancelStateRef = useRef<CancelState>("idle");
  const requestKeyRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const busyRef = useRef(false);
  const runToken = useRef(0);

  const updateCancelState = useCallback((next: CancelState, message: string) => {
    cancelStateRef.current = next;
    setCancelState(next);
    setCancelMessage(message);
  }, []);

  useEffect(() => {
    busyRef.current = busy;
  }, [busy]);

  const run = useCallback(
    async (override?: Partial<InvestigationSeed>) => {
      const useSeed = override || seed;
      const targetAt = useSeed?.at ?? state.snapshot_as_of ?? state.at;
      const targetTeam = useSeed?.team ?? team;
      const targetType = useSeed?.focusType ?? focusType;
      const targetId = useSeed?.focusId ?? (focusId || null);
      const token = ++runToken.current;
      if (busyRef.current && requestKeyRef.current) {
        void requestServerCancel(requestKeyRef.current).catch(() => {});
      }
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      const requestKey = newRequestKey();
      requestKeyRef.current = requestKey;
      const matchId = state.match_id;
      setBusy(true);
      setError("");
      setPromoted(null);
      setPlan(null);
      updateCancelState("idle", "");
      try {
        const res = await fetch("/api/investigate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: controller.signal,
          body: JSON.stringify({
            match_id: matchId,
            at: targetAt,
            team: targetTeam,
            focus_type: targetType,
            focus_id: targetId,
            compare_match_ids: useSeed?.compareMatchIds ?? [],
            question: useSeed?.question ?? question,
            execution_mode: executionMode,
            request_key: requestKey,
          }),
        });
        if (res.status === 409) {
          const cancelled = await res.json().catch(() => ({}));
          if (cancelled?.cancelled || cancelled?.detail === "investigation_cancelled") {
            if (token !== runToken.current) return;
            updateCancelState(
              "confirmed",
              isZh
                ? `服务端已确认取消${cancelled.run_id ? ` · Run ${cancelled.run_id}` : ""} · CANCELLED`
                : `Server confirmed cancellation${cancelled.run_id ? ` · run ${cancelled.run_id}` : ""} · CANCELLED`,
            );
            return;
          }
        }
        if (!res.ok) throw new Error(`Investigation failed (${res.status})`);
        const data: Plan = await res.json();
        if (token !== runToken.current) return;
        // The plan must belong to the same match and the moment this request
        // asked for. A switched match or a later seek invalidates it.
        if (data.match_id !== matchId || Math.abs(Number(data.as_of) - Number(targetAt)) > 1) {
          throw new Error("Stale investigation response");
        }
        if (cancelStateRef.current === "requesting" || cancelStateRef.current === "requested") {
          updateCancelState(
            "too_late",
            isZh
              ? "取消请求送达时调查已完成；以下为服务端返回的完整结果。"
              : "The investigation had already completed when the cancel arrived; the full result is shown below.",
          );
        }
        setPlan(data);
        setTeam(data.team === "N" ? "N" : "H");
        if (useSeed) {
          setFocusType(data.focus_type as typeof focusType);
          setFocusId(data.focus_id || "");
        }
      } catch (e) {
        if ((e as Error).name === "AbortError") {
          if (token === runToken.current) setError(isZh ? "调查已取消" : "Investigation cancelled");
          return;
        }
        if (token === runToken.current) setError((e as Error).message);
      } finally {
        if (token === runToken.current) setBusy(false);
      }
    },
    [executionMode, focusId, focusType, isZh, question, seed, state.at, state.match_id, state.snapshot_as_of, team, updateCancelState]
  );

  const cancel = async () => {
    const key = requestKeyRef.current;
    if (!key) {
      runToken.current += 1;
      abortRef.current?.abort();
      setBusy(false);
      updateCancelState("unavailable", isZh ? "已停止本地等待。" : "Stopped waiting locally.");
      return;
    }
    if (cancelStateRef.current === "requesting" || cancelStateRef.current === "requested") return;
    updateCancelState("requesting", isZh ? "正在向服务端发送取消请求…" : "Requesting server cancellation…");
    try {
      const data = await requestServerCancel(key);
      // The investigation may have returned while the cancel was in flight.
      if (cancelStateRef.current === "confirmed" || cancelStateRef.current === "too_late") return;
      updateCancelState(
        "requested",
        isZh
          ? `取消请求已送达${data.run_id ? ` · Run ${data.run_id}` : ""}${data.active === false ? "（请求尚未注册，已记录待取消）" : ""}，等待服务端确认…`
          : `Cancel request delivered${data.run_id ? ` · run ${data.run_id}` : ""}${data.active === false ? " (not yet registered; remembered)" : ""}; waiting for server confirmation…`,
      );
    } catch (e) {
      runToken.current += 1;
      abortRef.current?.abort();
      setBusy(false);
      updateCancelState(
        "unavailable",
        isZh
          ? `无法连接服务端取消（${(e as Error).message}），已停止本地等待。`
          : `Server cancellation unavailable (${(e as Error).message}); stopped waiting locally.`,
      );
    }
  };

  useEffect(
    () => () => {
      const key = requestKeyRef.current;
      if (busyRef.current && key) void requestServerCancel(key).catch(() => {});
      abortRef.current?.abort();
    },
    [],
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
    <div className="glass-panel r6-ask-panel" style={{ padding: 18, display: "grid", gap: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "end" }}>
        <div>
          <h3 style={{ fontSize: 20, fontWeight: 800, margin: 0, letterSpacing: "-.02em" }}>{isZh ? "询问这场比赛" : "Ask about this match"}</h3>
          <p style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 4 }}>
            {isZh
              ? "确定性工具与真实证据回执；未通过的结论不会写入注册表。"
              : "Deterministic tools and real receipts; an unapproved conclusion is never registered."}
          </p>
        </div>
        <span className="r6-status-pill">{isZh ? "证据优先 · 未通过门禁不写入" : "Evidence-first · gate required"}</span>
      </div>

      {seed && (
        <div className="r6-seed-context">
          <span>{isZh ? "已继承当前选择" : "Selection carried over"}</span>
          <b>
            {seed.focusType} {seed.focusId || ""} @ {Math.floor(seed.at / 60)}'
          </b>
        </div>
      )}

      <div className="r6-ask-context">
        <span>
          <small>{isZh ? "比赛" : "Match"}</small>
          <b>{homeName} vs {awayName}</b>
        </span>
        <span>
          <small>{isZh ? "快照" : "Snapshot"}</small>
          <b>{Math.floor((state.snapshot_as_of ?? state.at) / 60)}' · {state.coverage?.continuous ? (isZh ? "覆盖已验证" : "coverage verified") : isZh ? "部分覆盖" : "partial"}</b>
        </span>
        <span>
          <small>{isZh ? "分析球队" : "Team"}</small>
          <b>{team === "H" ? homeName : awayName}</b>
        </span>
      </div>

      <div className="r6-question-box">
        <label htmlFor="r6-investigation-question">{isZh ? "你想了解这场比赛的什么？" : "What do you want to understand?"}</label>
        <div className="r6-question-row">
          <input
            id="r6-investigation-question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !busy && state.match_id) void run();
            }}
            placeholder={isZh ? "例如：为什么第 32 分钟的进攻活动上升？" : "e.g. Why did attacking activity rise around 32'?"}
          />
          <button type="button" className="r6-primary-action" onClick={() => void run()} disabled={busy || !state.match_id}>
            {busy ? (isZh ? "分析中…" : "Analysing…") : isZh ? "分析" : "Analyse"}
          </button>
          {busy && (
            <button
              type="button"
              className="r6-text-action"
              onClick={() => void cancel()}
              disabled={cancelState === "requesting" || cancelState === "requested"}
              data-cancel-state={cancelState}
            >
              {cancelState === "requesting"
                ? isZh ? "取消中…" : "Cancelling…"
                : cancelState === "requested"
                  ? isZh ? "已请求取消" : "Cancel requested"
                  : isZh ? "取消" : "Cancel"}
            </button>
          )}
        </div>
        <div className="r6-question-suggestions" aria-label={isZh ? "推荐问题" : "Suggested questions"}>
          {[
            isZh ? "这次攻势有哪些可观测的关键动作？" : "Which recorded actions shaped this spell?",
            isZh ? "前后两个阶段的活动如何变化？" : "How did activity change between the two phases?",
            isZh ? "这些证据足以证明战术因果吗？" : "Does this evidence support a tactical cause?",
          ].map((text) => (
            <button key={text} type="button" onClick={() => setQuestion(text)}>
              {text}
            </button>
          ))}
        </div>
      </div>

      <details className="r6-investigation-advanced" data-testid="investigation-advanced">
        <summary>{isZh ? "高级设置 · 焦点 / 模型执行 / 工具记录" : "Advanced · focus, execution and tool records"}</summary>
        <div className="r6-advanced-grid">
          <label>
            {isZh ? "队伍" : "Team"}
            <select value={team} onChange={(e) => setTeam(e.target.value as "H" | "N")}>
              <option value="H">{homeName}</option>
              <option value="N">{awayName}</option>
            </select>
          </label>
          <label>
            {isZh ? "焦点类型" : "Focus"}
            <select value={focusType} onChange={(e) => setFocusType(e.target.value as typeof focusType)}>
              <option value="moment">{isZh ? "当前时刻" : "Current moment"}</option>
              <option value="oaai_point">{isZh ? "OAAI 变化点" : "OAAI change point"}</option>
              <option value="event">{isZh ? "事件" : "Event"}</option>
              <option value="metric">{isZh ? "指标" : "Metric"}</option>
              <option value="sequence">{isZh ? "控球序列" : "Sequence"}</option>
              <option value="player">{isZh ? "球员" : "Player"}</option>
              <option value="zone">{isZh ? "球场区域" : "Zone"}</option>
              <option value="shot_location">{isZh ? "射门位置" : "Shot location"}</option>
              <option value="cross_match_diff">{isZh ? "跨场差异" : "Cross-match difference"}</option>
            </select>
          </label>
          <label>
            {isZh ? "焦点 ID（可选）" : "Focus ID (optional)"}
            <input
              value={focusId}
              onChange={(e) => setFocusId(e.target.value)}
              placeholder={isZh ? "留空使用当前时刻" : "Leave empty for current moment"}
            />
          </label>
          <label>
            {isZh ? "执行引擎" : "Engine"}
            <select
              value={executionMode}
              onChange={(e) => setExecutionMode(e.target.value as typeof executionMode)}
              data-testid="investigation-engine-select"
            >
              <option value="deterministic_planner">{isZh ? "确定性引擎（免费）" : "Deterministic (free)"}</option>
              <option value="maf_agent">{isZh ? "真实 Agent（消耗模型预算）" : "Real Agent (uses model budget)"}</option>
            </select>
          </label>
        </div>
        <p className="r6-advanced-note">
          {isZh
            ? "焦点 ID、快照与工具收据是高级信息；默认问题会继承当前比赛与时间。"
            : "Focus IDs, snapshots and tool receipts are advanced details; the default question inherits the current match and clock."}
        </p>
      </details>

      {error && (
        <div className="r6-inline-error" role="alert">
          {error}
        </div>
      )}

      {cancelMessage && (
        <div
          className={`r6-cancel-status ${cancelState}`}
          role="status"
          data-testid="investigation-cancel-status"
          data-cancel-state={cancelState}
        >
          {cancelMessage}
        </div>
      )}

      {plan && (
        <div style={{ display: "grid", gap: 12 }} data-testid="investigation-plan">
          <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
            {isZh ? "快照" : "Snapshot"} <code>{plan.snapshot_id.slice(0, 18)}</code> / {plan.as_of}s / {plan.tool_receipts.length} {isZh ? "次工具调用" : "tool calls"}
            {plan.agent_run_id && (
              <span data-testid="investigation-run-id"> / Run <code>{plan.agent_run_id}</code></span>
            )}
          </div>
          <div className="r6-plan-status" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            <span className="rail-chip neutral">{plan.intent}</span>
            <span className="rail-chip neutral" style={{ color: statusTone[plan.state] || undefined }}>{plan.state}</span>
            <span
              className="rail-chip neutral"
              data-testid="investigation-execution-mode"
              data-execution-mode={plan.execution_mode}
              title={isZh ? "产生该计划的执行引擎" : "Engine that produced this plan"}
            >
              {EXECUTION_LABELS[plan.execution_mode]?.[isZh ? "zh" : "en"] ?? plan.execution_mode}
            </span>
            <span
              className="rail-chip neutral"
              data-testid="investigation-agent-status"
              data-agent-status={plan.agent_status}
              title={isZh ? "模型智能体是否真的执行过" : "Whether a model agent actually ran"}
            >
              {AGENT_STATUS_LABELS[plan.agent_status]?.[isZh ? "zh" : "en"] ?? plan.agent_status}
            </span>
            <span className="rail-chip neutral" title={plan.dataset_revision || undefined}>
              {plan.completeness?.status || "—"}
            </span>
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

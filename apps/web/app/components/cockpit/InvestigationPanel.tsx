"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { CockpitState, InvestigationSeed } from "./types";
import { Locale } from "../../lib/i18n";
import { AgentCollaboration, CollaborationSummary } from "./AgentCollaboration";
import { BroadcastOverlay, OverlayProvenance } from "../BroadcastOverlay";

interface InvestigationPanelProps {
  state: CockpitState;
  locale?: Locale;
  seed?: InvestigationSeed | null;
  onSelectEvent?: (eventId: string) => void;
  onSelectSequence?: (sequenceId: string) => void;
  onClaimPromoted?: (claim: any) => void;
  /** Return to the match at the moment this investigation is about. */
  onReturnToMatch?: (at: number) => void;
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
  collaboration?: CollaborationSummary | null;
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

/**
 * A conclusion is only a conclusion when the gate let it through. The label
 * says which of those two situations the reader is looking at.
 */
const verdictLabel = (status: string, lang: "zh" | "en" = "zh"): string => {
  const en: Record<string, string> = {
    approved: "gate approved",
    qualified: "qualified",
    disputed: "disputed",
    rejected: "gate rejected",
    withheld: "withheld",
    not_formed: "no publishable claim",
  };
  const zhTable: Record<string, string> = {
    approved: "已通过门禁",
    qualified: "有条件通过",
    disputed: "存在争议",
    rejected: "未通过门禁",
    withheld: "已扣留",
    not_formed: "未形成可发布主张",
  };
  const table = lang === "zh" ? zhTable : en;
  return table[status] ?? status;
};

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
  onReturnToMatch,
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
  /**
   * The live match id, read at response time. Comparing the response against
   * the match id captured when the request was sent proves nothing: that pair
   * is equal by construction. It has to be compared with what the cockpit is
   * showing *now*.
   */
  const liveMatchRef = useRef<string | undefined>(state.match_id);
  liveMatchRef.current = state.match_id;
  /** The snapshot this panel's result belongs to, for staleness labelling. */
  const [resultScope, setResultScope] = useState<{ matchId: string; asOf: number } | null>(null);

  const updateCancelState = useCallback((next: CancelState, message: string) => {
    cancelStateRef.current = next;
    setCancelState(next);
    setCancelMessage(message);
  }, []);

  useEffect(() => {
    busyRef.current = busy;
  }, [busy]);

  /**
   * Switching match invalidates every number on this panel. The in-flight
   * request is aborted, a server cancellation is requested through the same
   * endpoint the Cancel button uses, and the previous result is dropped rather
   * than left on screen under a different fixture.
   */
  const matchId = state.match_id;
  const resetForMatch = useCallback(() => {
    const key = requestKeyRef.current;
    if (busyRef.current && key) void requestServerCancel(key).catch(() => {});
    runToken.current += 1;
    abortRef.current?.abort();
    abortRef.current = null;
    requestKeyRef.current = null;
    busyRef.current = false;
    setBusy(false);
    setPlan(null);
    setPromoted(null);
    setError("");
    setResultScope(null);
    updateCancelState("idle", "");
  }, [updateCancelState]);

  const lastMatchRef = useRef<string | undefined>(matchId);
  useEffect(() => {
    if (lastMatchRef.current === matchId) return;
    lastMatchRef.current = matchId;
    resetForMatch();
    setFocusId("");
    setQuestion("");
    setTeam(state.focus_team ?? "H");
    setFocusType("moment");
    // A match switch is a hard boundary: nothing from the previous fixture may
    // survive it. `state.focus_team` is intentionally read at switch time only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matchId, resetForMatch]);

  /**
   * A seek moves the snapshot. What happens to an in-flight request depends on
   * what it costs: a paid model run is cancelled through the same server path
   * as the Cancel button, while a free deterministic run is allowed to finish
   * and is then labelled as belonging to the earlier moment. Killing a
   * completed calculation to protect against misreading it loses real work;
   * labelling it does not.
   */
  const currentAsOf = Number(state.snapshot_as_of ?? state.at ?? 0);
  const lastAsOfRef = useRef(currentAsOf);
  const executionModeRef = useRef(executionMode);
  executionModeRef.current = executionMode;
  useEffect(() => {
    if (lastAsOfRef.current === currentAsOf) return;
    lastAsOfRef.current = currentAsOf;
    if (!abortRef.current) return;
    if (executionModeRef.current !== "maf_agent") return;
    const key = requestKeyRef.current;
    if (key) void requestServerCancel(key).catch(() => {});
    runToken.current += 1;
    abortRef.current?.abort();
    abortRef.current = null;
    busyRef.current = false;
    setBusy(false);
    updateCancelState("idle", "");
    setError(
      isZh
        ? "回放时刻已改变，付费 Agent 运行已取消；请在新的时刻重新提问。"
        : "The replay moment changed; the paid agent run was cancelled. Ask again at the new moment.",
    );
  }, [currentAsOf, isZh, updateCancelState]);

  /**
   * Staleness is a display fact, not an error. A deliberate seek is a large
   * jump; a running clock drifts slowly, so only a real move is labelled.
   */
  const momentDelta = resultScope ? Math.abs(resultScope.asOf - currentAsOf) : 0;
  const contextProvenance = state.match_context?.provenance_kind;
  const overlayProvenance: OverlayProvenance =
    contextProvenance === "provider_payload" || contextProvenance === "provider_schema_excerpt"
      ? contextProvenance
      : "synthetic";

  const staleResult = Boolean(resultScope) && (momentDelta > 30 || (state.paused && momentDelta > 1));

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
        // A response is only usable while the cockpit still shows the match it
        // was requested for. Anything else is a late answer to a question the
        // user is no longer asking.
        if (data.match_id !== liveMatchRef.current) {
          return;
        }
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
        // Only a plan that actually formed a result can be misattributed to a
        // moment. A failed plan has nothing to be stale about, so claiming
        // "this belongs to another snapshot" would just be noise.
        const formed = data.state !== "FAILED" && data.state !== "UNKNOWN";
        setResultScope(formed ? { matchId: data.match_id, asOf: Number(data.as_of) } : null);
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
          {/* Every suggestion must be a question the deterministic planner can
              map to a supported intent. A chip that returns "scope required"
              teaches the user the product does not work. */}
          {[
            isZh ? "为什么这一时刻的进攻活动会上升？" : "Why did attacking activity change around this moment?",
            isZh ? "对比最近两个阶段的活动。" : "Compare the activity of the last two phases.",
            isZh ? "样本量足以支持战术结论吗？" : "Is the sample enough to support a tactical cause?",
          ].map((text) => (
            <button key={text} type="button" onClick={() => setQuestion(text)}>
              {text}
            </button>
          ))}
        </div>
        <p
          className="r6-execution-mode-line"
          data-testid="investigation-mode-line"
          data-mode={executionMode}
          data-model-configured={state.model_configured ? "true" : "false"}
        >
          {executionMode === "deterministic_planner"
            ? isZh
              ? "当前模式：确定性引擎 · 不调用模型，结果来自 recorded events 与确定性工具。"
              : "Mode: Deterministic · No model called. Results come from recorded events and deterministic tools."
            : state.model_configured
              ? isZh
                ? "当前模式：真实多智能体 · 需要消耗模型预算；失败时自动回退确定性引擎。"
                : "Mode: Real multi-agent · Model required. Falls back to the deterministic engine on failure."
              : isZh
                ? "当前模式：真实多智能体 · 未配置模型，主分析仍将使用确定性引擎。"
                : "Mode: Real multi-agent · No model configured, the deterministic engine will answer."}
        </p>
      </div>

      {!plan && !busy && (
        <RecentInvestigations matchId={matchId || ""} locale={locale} />
      )}

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
              <option value="maf_agent" disabled={!state.model_configured}>
                {isZh
                  ? state.model_configured
                    ? "真实 Agent（消耗模型预算）"
                    : "真实 Agent（未配置模型）"
                  : state.model_configured
                    ? "Real Agent (uses model budget)"
                    : "Real Agent (no model configured)"}
              </option>
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
        <article className="r6-result" data-testid="investigation-plan" data-result-as-of={resultScope?.asOf ?? "none"} data-plan-state={plan.state}>
          {staleResult && (
            <div className="r6-result-stale" role="status" data-testid="investigation-stale">
              <b>{isZh ? "这份结果属于另一个快照" : "This result belongs to another snapshot"}</b>
              <span>
                {isZh
                  ? `结果时刻 ${Math.round(resultScope!.asOf)}s，当前回放 ${Math.round(currentAsOf)}s。它不是当前时刻的答案。`
                  : `Result at ${Math.round(resultScope!.asOf)}s; the replay is at ${Math.round(currentAsOf)}s. It is not an answer about this moment.`}
              </span>
              <button type="button" className="r6-text-action" onClick={() => void run()}>
                {isZh ? "在当前时刻重新调查" : "Investigate the current moment"}
              </button>
            </div>
          )}

          <header className="r6-result-head">
            <div className="r6-result-kicker">
              <span>{isZh ? "调查结论" : "Conclusion"}</span>
              <span className="r6-result-verdict" data-testid="investigation-verdict" data-verdict={plan.gate_preview.status}>
                {verdictLabel(plan.gate_preview.status, isZh ? "zh" : "en")}
              </span>
            </div>
            <h4 data-testid="investigation-conclusion">
              {plan.gate_preview.statement ||
                plan.findings[0]?.statement ||
                (isZh ? "本次调查没有形成可发布的结论。" : "This investigation did not form a publishable conclusion.")}
            </h4>
            <div className="r6-result-meta">
              <span className="rail-chip neutral">{plan.intent}</span>
              <span className="rail-chip neutral" style={{ color: statusTone[plan.state] || undefined }}>{plan.state}</span>
              <span className="rail-chip neutral" title={plan.dataset_revision || undefined}>
                {plan.completeness?.status || "—"}
              </span>
              <span className="r6-result-when">
                {isZh ? "快照" : "Snapshot"} <code>{plan.snapshot_id.slice(0, 18)}</code> · {plan.as_of}s
                {plan.agent_run_id && (
                  <span data-testid="investigation-run-id"> · Run <code>{plan.agent_run_id}</code></span>
                )}
              </span>
              {onReturnToMatch && (
                <button
                  type="button"
                  className="r6-text-action"
                  data-testid="investigation-return"
                  onClick={() => onReturnToMatch(Number(plan.as_of))}
                >
                  {isZh ? "回到比赛中这一刻 →" : "Back to this moment →"}
                </button>
              )}
            </div>
          </header>

          {(plan.required_scope.length > 0 || plan.state === "FAILED" || plan.state === "UNKNOWN") && (
            <div className="r6-result-blocked" role="alert" data-testid="investigation-blocked">
              {plan.required_scope.length > 0
                ? `${isZh ? "需要补充范围" : "Scope required"}: ${plan.required_scope.join(", ")}`
                : isZh
                  ? `本次调查在 ${plan.as_of}s 的 ${plan.focus_type} 焦点上未能形成结论（${plan.state}）。可以换一个时间点、换一个焦点，或先让回放到达有记录动作的时刻。`
                  : `This investigation formed no conclusion for the ${plan.focus_type} focus at ${plan.as_of}s (${plan.state}). Try another moment, another focus, or let the replay reach recorded actions.`}
            </div>
          )}

          <AgentCollaboration
            collaboration={plan.collaboration}
            stateHistory={plan.state_history}
            toolReceiptCount={plan.tool_receipts.length}
            agentStatus={plan.agent_status}
            agentError={plan.agent_error}
            locale={locale}
          />

          <section className="r6-result-section" aria-labelledby="r6-result-evidence">
            <h5 id="r6-result-evidence">{isZh ? "依据：记录到的动作" : "Evidence: recorded actions"}</h5>
            {plan.findings.length === 0 ? (
              <p className="r6-result-empty">{isZh ? "没有可引用的记录发现。" : "No recordable findings."}</p>
            ) : (
              <ul className="r6-finding-list">
                {plan.findings.map((finding) => (
                  <li key={finding.finding_id} data-testid="investigation-finding">
                    <span className="r6-finding-level">L{finding.level}</span>
                    <span className="r6-finding-text">{finding.statement}</span>
                    {finding.event_ids.length > 0 && onSelectEvent && (
                      <button type="button" className="r6-text-action" onClick={() => onSelectEvent(finding.event_ids[0])}>
                        {isZh ? `查看事件 ${finding.event_ids[0]}` : `Open ${finding.event_ids[0]}`}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="r6-result-section" aria-labelledby="r6-result-alt">
            <h5 id="r6-result-alt">{isZh ? "替代解释与可信度" : "Alternative explanations"}</h5>
            {plan.explanations.length === 0 ? (
              <p className="r6-result-empty">
                {isZh ? "本次调查未生成竞争性假说。" : "No competing hypothesis was formed for this question."}
              </p>
            ) : (
              <ul className="r6-explanation-list">
                {plan.explanations.map((item) => (
                  <li key={item.explanation_id} data-testid="investigation-explanation">
                    <div className="r6-explanation-head">
                      <span>{item.hypothesis}</span>
                      <span style={{ color: statusTone[item.status] || "var(--text-secondary)" }}>
                        {item.status} · L{item.claim_level}
                      </span>
                    </div>
                    <p>{item.verification}</p>
                    {item.supporting_evidence.length > 0 && (
                      <p className="r6-explanation-pro">+ {item.supporting_evidence.join(", ")}</p>
                    )}
                    {item.counterevidence.length > 0 && (
                      <p className="r6-explanation-con">− {item.counterevidence.join(", ")}</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="r6-result-section" aria-labelledby="r6-result-limits" data-testid="investigation-limits">
            <h5 id="r6-result-limits">{isZh ? "哪些无法判断" : "What this cannot decide"}</h5>
            {plan.not_inferable.length === 0 && plan.unresolved.length === 0 ? (
              <p className="r6-result-empty">
                {isZh ? "确定性引擎未返回额外限制。" : "The deterministic engine returned no extra limits."}
              </p>
            ) : (
              <ul className="r6-limit-list">
                {[...plan.not_inferable, ...plan.unresolved].map((text) => (
                  <li key={text}>{text}</li>
                ))}
              </ul>
            )}
          </section>

          <div className="r6-result-actions">
            {plan.gate_preview.status === "approved" && !plan.gate_preview.persisted ? (
              <button
                type="button"
                className="r6-primary-action"
                onClick={promote}
                disabled={promoting}
                title={isZh ? "注册后可在制作人工作区加入 Rundown 并导出" : "After registration the claim can join a producer rundown"}
              >
                {promoting ? (isZh ? "注册中..." : "Registering...") : isZh ? "确认并注册 Claim" : "Confirm and register claim"}
              </button>
            ) : (
              <button type="button" className="r6-text-action" onClick={() => void run()}>
                {isZh ? "换个问法继续调查" : "Ask a different question"}
              </button>
            )}
            {promoted && (
              <span className="r6-result-promoted">
                {isZh ? "已注册" : "Registered"}: {promoted.claim_id} / {promoted.current_revision_id?.slice(0, 12)}
              </span>
            )}
          </div>

          {plan.gate_preview.status === "approved" && (
            <section className="r6-result-section" aria-labelledby="r6-result-overlay">
              <h5 id="r6-result-overlay">{isZh ? "转播预览" : "Broadcast preview"}</h5>
              <BroadcastOverlay
                homeTeam={state.match_context?.home_team_name || state.teams?.H || "Home"}
                awayTeam={state.match_context?.away_team_name || state.teams?.N || "Away"}
                score={state.score}
                asOf={Number(plan.as_of)}
                headline={plan.gate_preview.statement || plan.findings[0]?.statement || plan.gate_preview.assertion}
                verdict={plan.gate_preview.status}
                refs={plan.gate_preview.refs}
                claimLevel={plan.gate_preview.claim_level}
                provenance={overlayProvenance}
                registered={plan.gate_preview.persisted}
                locale={locale}
              />
              <p className="r6-overlay-note">
                {isZh
                  ? "预览使用同一条已通过门禁的主张、同一比赛时间与同一组证据引用；正式导出到 Rundown 仍需制作人权限。"
                  : "The preview uses the same gate-approved claim, match time and evidence refs; exporting to a rundown still requires producer scope."}
              </p>
            </section>
          )}

          {/* Technical receipts stay available, but they are not the answer. */}
          <details className="r6-result-details" data-testid="investigation-technical">
            <summary>{isZh ? "技术回执 · 门禁校验 · 执行轨迹" : "Tool receipts, gate and execution trace"}</summary>

            <div className="r6-tech-grid">
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
            </div>

            <div className="r6-gate-audit" data-testid="investigation-gate">
              <div className="r6-gate-head">
                <b>{isZh ? "门禁校验" : "Gate check"}</b>
                <span style={{ color: statusTone[plan.gate_preview.status] || "var(--text-secondary)" }}>
                  {plan.gate_preview.assertion || "—"} · {plan.gate_preview.status} · L{plan.gate_preview.claim_level} ·{" "}
                  {plan.gate_preview.persisted ? (isZh ? "已持久化" : "persisted") : isZh ? "未持久化" : "not persisted"}
                </span>
              </div>
              {plan.gate_preview.violations.length > 0 && (
                <p className="r6-gate-violation">{plan.gate_preview.violations.join(" ")}</p>
              )}
            </div>

            {plan.oaai_ledger && plan.oaai_ledger.contributions.length > 0 && (
              <div className="r6-ledger">
                <div className="r6-ledger-head">
                  <b>{isZh ? "OAAI 贡献账本" : "OAAI contribution ledger"}</b>
                  <span>
                    {isZh ? "原始" : "raw"} {plan.oaai_ledger.raw_team_intensity} /{" "}
                    {isZh ? "平滑" : "smoothed"} {plan.oaai_ledger.smoothed_value_at_nearest_sample ?? "—"}
                  </span>
                </div>
                {plan.oaai_ledger.contributions.slice(0, 6).map((row) => (
                  <button
                    key={row.event_id}
                    type="button"
                    className="r6-ledger-row"
                    onClick={() => onSelectEvent?.(row.event_id)}
                  >
                    <span>
                      <b>{row.event_id}</b> {row.actor}{" "}
                      <em>{row.kind} @ {Math.floor(row.t / 60)}'</em>
                    </span>
                    <span style={{ color: row.team_contribution >= 0 ? "var(--text-emerald)" : "var(--red-11)" }}>
                      {row.team_contribution >= 0 ? "+" : ""}
                      {row.team_contribution.toFixed(3)} / w {row.weight.toFixed(2)}
                    </span>
                  </button>
                ))}
              </div>
            )}

            <details className="r6-tool-receipts" open={plan.tool_receipts.length <= 8}>
              <summary>{isZh ? "工具回执" : "Tool receipts"} ({plan.tool_receipts.length})</summary>
              <ol>
                {plan.tool_receipts.map((step) => (
                  <li key={step.sequence} data-testid="investigation-tool-receipt">
                    <code>{step.sequence.toString().padStart(2, "0")}</code>
                    {step.role && <span className="r6-role-chip">{step.role}</span>}
                    <b>{step.tool}</b>
                    <span style={{ color: statusTone[step.status] || "var(--text-tertiary)" }}>{step.status}</span>
                    <em>{step.summary}</em>
                  </li>
                ))}
              </ol>
            </details>

            {plan.agent_run && (
              <details data-testid="investigation-agent-run">
                <summary>
                  {isZh ? "Agent 执行轨迹" : "Agent run trajectory"}
                  {plan.agent_run.model ? ` · ${plan.agent_run.model}` : ""}
                  {` · ${plan.agent_run.state}`}
                </summary>
                <div className="r6-agent-trace">
                  <div>
                    {isZh ? "运行 ID" : "Run ID"} <code>{plan.agent_run.run_id}</code>
                    {typeof plan.agent_run.requests === "number" && (
                      <> / {isZh ? "模型请求" : "model requests"} {plan.agent_run.requests}</>
                    )}
                    {plan.agent_run.prompt_version && <> / prompt {plan.agent_run.prompt_version}</>}
                  </div>
                  {plan.agent_run.state_history.map((entry, index) => (
                    <div key={`${entry.state}-${index}`}>
                      <b style={{ color: statusTone[entry.state] || "var(--text-primary)" }}>{entry.state}</b>
                      {entry.reason && <span> — {entry.reason}</span>}
                    </div>
                  ))}
                  {plan.agent_run.error && <div className="r6-agent-error">{plan.agent_run.error}</div>}
                </div>
              </details>
            )}

            {plan.agent_error && (
              <div data-testid="investigation-agent-error" className="r6-agent-degraded">
                {isZh ? "Agent 降级原因" : "Agent degradation"}: {plan.agent_error}
              </div>
            )}
          </details>
        </article>
      )}
    </div>
  );
};

type InvestigationSummary = {
  investigation_id: string;
  state: string;
  focus_type: string;
  team: "H" | "N";
  as_of: number;
  question: string;
  intent: string;
  gate_status: string;
  finding_count: number;
};

/**
 * Before the first result of a session exists, this is what the panel shows
 * instead of empty space: the session's own saved investigations. They are
 * real records from `/api/investigations`, scoped to this browser session —
 * never a demo transcript.
 */
const RecentInvestigations: React.FC<{ matchId: string; locale: Locale }> = ({ matchId, locale }) => {
  const isZh = locale === "zh";
  const [items, setItems] = useState<InvestigationSummary[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    setItems(null);
    setFailed(false);
    if (!matchId) return () => {};
    fetch(`/api/investigations?match_id=${encodeURIComponent(matchId)}&limit=5`)
      .then((res) => {
        if (!res.ok) throw new Error(String(res.status));
        return res.json();
      })
      .then((data) => {
        if (active) setItems(Array.isArray(data?.investigations) ? data.investigations : []);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, [matchId]);

  return (
    <section className="r6-recent-investigations" data-testid="recent-investigations" aria-label={isZh ? "本次会话的调查记录" : "This session's investigations"}>
      <h5>{isZh ? "本次会话已保存的调查" : "Saved investigations in this session"}</h5>
      {failed ? (
        <p className="r6-recent-empty">{isZh ? "调查记录暂不可用；这不影响发起新的调查。" : "Investigation records are unavailable; new investigations are unaffected."}</p>
      ) : items === null ? (
        <p className="r6-recent-empty" role="status">{isZh ? "正在读取…" : "Loading…"}</p>
      ) : items.length === 0 ? (
        <p className="r6-recent-empty">
          {isZh
            ? "还没有记录。提出一个问题，MatchLens 会用确定性工具与真实回执回答，结论必须通过门禁才会展示为可信。"
            : "Nothing yet. Ask a question — MatchLens answers with deterministic tools and real receipts, and a conclusion only counts once the gate approves it."}
        </p>
      ) : (
        <ul>
          {items.map((item) => (
            <li key={item.investigation_id} data-testid="recent-investigation">
              <span className="r6-recent-when">{Math.floor(item.as_of / 60)}′</span>
              <b>{item.question || item.intent}</b>
              <span className="r6-recent-status" data-gate={item.gate_status}>
                {item.state} · {verdictLabel(item.gate_status, isZh ? "zh" : "en")}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
};

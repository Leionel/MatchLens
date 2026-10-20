"use client";

import { AudienceSwitcher } from "./AudienceSwitcher";

type Card = {
  claim_id: string;
  assertion: string;
  verdict: string;
  fan: string;
  analyst: string;
  refs: string[];
  scope: string;
  reason: string;
  limitations: string[];
  snapshot_id: string;
  as_of: number;
};

type Result = {
  status: string;
  origin: string;
  accepted: Card[];
  rejected: {
    claim_id: string;
    reason: string;
    gate: string;
    verdict: string;
  }[];
  error?: string;
  duration_ms?: number;
  requests: number;
  audit: any[];
  snapshot_id: string;
  as_of: number;
  run_id: string;
  reused?: boolean;
};

type Moment = {
  id: string;
  chapter_id?: string;
  at: number;
  badge: string;
  title: string;
  question: string;
  assertion: string;
  summary: string;
  priority: number;
};

type Receipt = {
  id: string;
  value: number;
  unit: string;
};

type InsightSpotlightProps = {
  mode: "fan" | "analyst";
  onModeChange: (m: "fan" | "analyst") => void;
  card: Card | null;
  result: Result | null;
  pending: boolean;
  pendingStatus?: string;
  activeMoment: Moment | null;
  activeChapter: { id: string; at: number; title: string; question: string } | null;
  modelConfigured: boolean;
  busy: boolean;
  analysesRemaining: number;
  onAnalyse: () => void;
  onChallenge: (receiptId: string, snapshotId: string) => void;
  onToggleTrace: () => void;
  showTrace: boolean;
  onToggleOverlay: () => void;
  showOverlay: boolean;
  receipts: Record<string, Receipt>;
  snapshotId: string | null;
  autoStatus: string;
};

const clock = (s: number) =>
  `${Math.floor(s / 60).toString().padStart(2, "0")}:${Math.floor(s % 60).toString().padStart(2, "0")}`;

export function InsightSpotlight({
  mode,
  onModeChange,
  card,
  result,
  pending,
  pendingStatus,
  activeMoment,
  activeChapter,
  modelConfigured,
  busy,
  analysesRemaining,
  onAnalyse,
  onChallenge,
  onToggleTrace,
  showTrace,
  onToggleOverlay,
  showOverlay,
  receipts,
  snapshotId,
  autoStatus,
}: InsightSpotlightProps) {
  const isFallback = result?.status === "fallback";
  const withheld = result?.status === "completed" && result.accepted.length === 0;
  const canRunModel = modelConfigured && autoStatus !== "budget_limited";

  return (
    <section className={`insight-spotlight-panel ${card ? "has-insight" : ""}`} aria-labelledby="spotlight-heading">
      <div className="spotlight-top-strip">
        <div className="spotlight-title-group">
          <span className="live-ai-badge">WHAT CHANGED · WHY IT MATTERS</span>
          <h2 id="spotlight-heading" className="spotlight-main-heading">
            Match intelligence
          </h2>
        </div>
        <AudienceSwitcher mode={mode} onChange={onModeChange} />
      </div>

      {/* Candidate Question Bar */}
      <div className="candidate-question-banner">
        <div className="banner-context">
          <span className="moment-badge">
            {activeChapter ? `CHAPTER ${activeChapter.id}` : activeMoment ? activeMoment.badge : "MATCH OBSERVATION"}
          </span>
          <span className="moment-timing">
            AS OF {clock(activeChapter?.at || activeMoment?.at || card?.as_of || 0)}
          </span>
        </div>
        <h3 className="candidate-title">
          {activeChapter?.question || activeMoment?.question || "A match full of questions. Find the evidence."}
        </h3>
        <p className="candidate-desc">
          {activeMoment?.summary ||
            activeChapter?.title ||
            "Press Play Replay. We'll detect changes in possession, attacking activity and scoring moves as the match unfolds."}
        </p>
      </div>

      {/* Pending State */}
      {pending && (
        <div className="spotlight-evaluating" role="status" aria-live="polite">
          <div className="pulse-glow-track">
            <div className="pulse-glow-bar" />
          </div>
          <div className="eval-status-content">
            <span className="eval-spinner">⚙</span>
            <div className="eval-text">
              <h4>
                {pendingStatus === "verifying"
                  ? "Verifier Agent Cross-Checking Claims"
                  : pendingStatus === "queued"
                    ? "Dispatching to Microsoft Agent Framework Slot"
                    : "Analyst Agent Investigating Receipts"}
              </h4>
              <p>Grounding assertions with deterministic evidence. Replay is non-blocking.</p>
            </div>
          </div>
        </div>
      )}

      {/* Model Unavailable or Fallback */}
      {isFallback && !pending && (
        <div className="spotlight-fallback-card">
          <div className="fallback-header">
            <span className="fallback-tag">DETERMINISTIC FALLBACK</span>
            <span className="fallback-badge">STATISTICS ACCESSIBLE</span>
          </div>
          <p className="fallback-explanation">
            {result?.error === "model_not_configured"
              ? "DeepSeek model credentials are not configured on this host. Deterministic facts, goal chains and metric receipts remain 100% verifiable."
              : result?.error === "inference_budget_exhausted"
                ? "This host's inference allowance is exhausted. Statistics and revalidated historical analyses remain available."
                : result?.error === "analysis_timeout"
                  ? "Agent analysis reached its safety deadline. Source evidence remains available."
                  : "Model output failed gate verification; ungrounded assertions were withheld."}
          </p>
          <button
            type="button"
            className="btn-retry-analysis"
            onClick={() => canRunModel ? onAnalyse() : snapshotId && onChallenge("H.shots.current", snapshotId)}
            disabled={busy || !snapshotId || (canRunModel && analysesRemaining <= 0)}
          >
            <span>{canRunModel ? "Retry live investigation" : "Inspect source evidence"}</span>
            <span>↗</span>
          </button>
        </div>
      )}

      {/* Verified Insight Card */}
      {card && !pending && (
        <article className={`verified-card ${card.verdict}`}>
          <div className="card-seal-row">
            <div className="seal-badge">
              <span className="seal-icon">
                {card.verdict === "qualify" ? "🛡" : "✓"}
              </span>
              <span className="seal-text">
                {card.verdict === "qualify"
                  ? "QUALIFIED BY PUBLICATION GATE"
                  : "VERIFIED BY AGENT GATE"}
              </span>
            </div>
            <div className="seal-provenance">
              <span>{result?.reused ? "Historical real analysis" : "Real model analysis"} · As of {clock(card.as_of)}</span>
              <span className="dot-sep">·</span>
              <span>Scope: {card.scope.toUpperCase()}</span>
            </div>
          </div>

          <div className="insight-body">
            {mode === "fan" ? (
              <div className="fan-editorial">
                <p className="editorial-lead">{card.fan}</p>
                <div className="editorial-chips">
                  <span className="editorial-chip">
                    <b>{card.scope === "window" ? "Short window" : "Recorded sequence"}</b>
                  </span>
                  <span className="editorial-chip">
                    <b>{card.refs.length}</b> Metric Receipts
                  </span>
                  <span className="editorial-chip highlight">
                    <b>Evidence-bound summary</b>
                  </span>
                </div>
              </div>
            ) : (
              <div className="analyst-editorial">
                <p className="analyst-lead">{card.analyst}</p>
                <div className="analyst-verifier-box">
                  <div className="verifier-title">
                    <span className="shield-icon">🛡</span>
                    <b>Verifier Agent Audit & Evidence Limits:</b>
                  </div>
                  <p className="verifier-reason">{card.reason}</p>
                  {card.limitations.length > 0 && (
                    <ul className="verifier-limits-list">
                      {card.limitations.map((lim, i) => (
                        <li key={i}>{lim}</li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="card-action-bar">
            <button
              type="button"
              className="btn-challenge-evidence"
              onClick={() => onChallenge(card.refs[0], card.snapshot_id)}
            >
              <span className="challenge-icon">🔍</span>
              <span>Challenge with Evidence ({card.refs.length} Receipts)</span>
              <span className="arrow-chip">↗</span>
            </button>

            <button
              type="button"
              className={`btn-overlay-toggle ${showOverlay ? "active" : ""}`}
              onClick={onToggleOverlay}
              title="Toggle Broadcast Overlay TV Graphic"
            >
              📺 Broadcast Preview
            </button>
          </div>
        </article>
      )}

      {/* Manual Trigger / Re-run */}
      {withheld && !pending && <div className="spotlight-fallback-card" role="status">
        <h3>No publishable finding</h3>
        <p className="fallback-explanation">The review or factual publication checks did not approve this explanation. Inspect the recorded statistics and events instead.</p>
        {mode === "analyst" && <p className="action-hint">{result?.rejected.map(r => r.gate || r.verdict).join(" · ")}</p>}
        <button type="button" onClick={() => snapshotId && onChallenge("H.shots.current", snapshotId)}>Inspect source evidence</button>
      </div>}
      {!card && !pending && !isFallback && !withheld && (
        <div className="spotlight-prompt-action">
          <button
            type="button"
            className="btn-primary-analyse"
            onClick={() => canRunModel ? onAnalyse() : snapshotId && onChallenge("H.shots.current", snapshotId)}
            disabled={busy || !snapshotId || (canRunModel && analysesRemaining <= 0)}
          >
            <span>
              {!snapshotId ? "Play to discover a moment" : canRunModel ? "Investigate this moment" : "Inspect detected facts"}
            </span>
            <span className="btn-arrow">↗</span>
          </button>
          <span className="action-hint">
            {modelConfigured
              ? autoStatus === "enabled" ? "Live analysis starts automatically for eligible moments." : autoStatus === "budget_limited" ? "Automatic analysis paused: insufficient whole-workflow allowance." : "Automatic detection is free. Live analysis is enabled by the host."
              : "Model unavailable · Automatic detection and source evidence remain available."}
          </span>
        </div>
      )}

      {/* Spot footer: Pipeline & Trace */}
      <div className="spotlight-footer">
        <div className="pipeline-steps">
          <span>Event Stream</span>
          <i>→</i>
          <span>Metric Reducer</span>
          <i>→</i>
          <span>Analyst Agent</span>
          <i>→</i>
          <span>Verifier Agent</span>
          <i>→</i>
          <span>Publication Gate</span>
        </div>
        <button
          type="button"
          className="btn-trace-toggle"
          onClick={onToggleTrace}
          aria-expanded={showTrace}
        >
          {showTrace ? "Hide Agent Trace" : "Inspect Agent Trace"}
        </button>
      </div>

      {/* Trace Dropdown */}
      {showTrace && (
        <div className="execution-trace-panel">
          <div className="trace-header">
            <h4>Agent Execution Trace</h4>
            <span className="trace-engine">Microsoft Agent Framework + DeepSeek Flash</span>
          </div>
          {result ? (
            <div className="trace-details">
              <div className="trace-stats-row">
                <span>Run ID: <code>{result.run_id}</code></span>
                <span>Requests: <b>{result.requests}</b></span>
                {result.duration_ms && (
                  <span>Latency: <b>{(result.duration_ms / 1000).toFixed(2)}s</b></span>
                )}
                <span>Status: <b className="status-green">{result.status}</b></span>
              </div>
              <ol className="trace-audit-list">
                {result.audit
                  ?.filter((e) =>
                    ["tool", "handoff", "http_receipt", "schema_correction", "failure"].includes(
                      e.type,
                    ),
                  )
                  .map((e, idx) => (
                    <li key={idx} className={`trace-item ${e.type}`}>
                      <span className="trace-role">{e.role || e.from || "SYSTEM"}:</span>{" "}
                      <span className="trace-desc">
                        {e.type === "handoff"
                          ? `Handoff from ${e.from} to ${e.to} (SHA256 verified)`
                          : e.type === "tool"
                            ? `Called Tool: ${e.name}()`
                            : e.type === "http_receipt"
                              ? `HTTP ${e.status} from provider ${e.usage ? `(${e.usage.completion_tokens} completion tokens)` : ""}`
                              : e.type === "schema_correction"
                                ? "Bounded Format Correction in Same Session"
                                : "Gate Notice"}
                      </span>
                    </li>
                  ))}
              </ol>
            </div>
          ) : (
            <p className="no-trace-msg">Run an analysis to inspect real multi-agent telemetry.</p>
          )}
        </div>
      )}
    </section>
  );
}

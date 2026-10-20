"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type FootballEvent = {
  id: string;
  seq: number;
  t: number;
  kind: string;
  team: "H" | "N";
  actor: string;
  receiver: string | null;
  start: [number, number];
  end: [number, number];
  outcome: string;
  possession_id: number;
};
type Receipt = {
  id: string;
  value: number;
  unit: string;
  event_ids: string[];
  definition: string;
  start: number;
  end: number;
  numerator?: number;
  denominator?: number;
  chains?: { event_ids: string[]; seconds: number }[] | string[][];
};
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
type Audit = {
  type: string;
  role?: string;
  name?: string;
  from?: string;
  to?: string;
  status?: number;
  request_id?: number;
  usage?: { prompt_tokens: number; completion_tokens: number };
  [key: string]: unknown;
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
  audit: Audit[];
  snapshot_id: string;
  as_of: number;
  run_id: string;
  reused?: boolean;
};
type Evidence = {
  snapshot_id: string;
  as_of: number;
  events: FootballEvent[];
  receipts: Record<string, Receipt>;
  limitations: string[];
};
type State = {
  revision: number;
  epoch: number;
  at: number;
  score: Record<"H" | "N", number>;
  paused: boolean;
  speed: number;
  focus: string | null;
  ball: [number, number];
  events: FootballEvent[];
  receipts: Record<string, Receipt>;
  players: Record<string, Record<string, string>>;
  chapters: { id: string; at: number; title: string; question: string }[];
  snapshot_id: string | null;
  analysis: { status: string; as_of: number; run_id: string } | null;
  result: Result | null;
  history: Card[];
  model_configured: boolean;
  ended: boolean;
  session_analyses_remaining: number;
};

const clock = (seconds: number) =>
  `${Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0")}:${Math.floor(seconds % 60)
    .toString()
    .padStart(2, "0")}`;
const labels: Record<string, string> = {
  possession: "Controlled possession",
  shots: "Shots",
  entries: "Attacking entries",
  high_recoveries: "High recoveries",
  transition_shots: "Recovery → shot",
  goals: "Goals",
};
const titleFor = (id: string) => labels[id.split(".")[1]] || id;
const num = (receipt: Receipt) =>
  `${receipt.value}${receipt.unit === "%" ? "%" : ""}`;

async function api<T>(path: string, body?: object): Promise<T> {
  const response = await fetch(`/api/${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers:
      body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const errors: Record<number, string> = {
      401: "Your session expired. Reload to start a new match.",
      429: "Analysis limit reached. Wait a minute before trying again.",
      503: "The demo is busy. Try again shortly.",
    };
    throw new Error(
      errors[response.status] ||
        `The request failed (${response.status}). Please try again.`,
    );
  }
  return response.json();
}

function Pitch({
  events,
  selected,
  ball,
  players,
}: {
  events: FootballEvent[];
  selected: FootballEvent | null;
  ball: [number, number];
  players: State["players"];
}) {
  const recent = selected
    ? [selected]
    : events.filter((e) => e.kind === "pass" || e.kind === "shot").slice(-5);
  const point = selected ? selected.end : ball;
  const chosen = selected || events.at(-1);
  return (
    <div className="pitch-wrap">
      <div className="pitch-heading">
        <span>
          {selected ? `Evidence · ${selected.id}` : "On-ball event map"}
        </span>
        <span>Harbor attacks →</span>
      </div>
      <svg
        className="pitch"
        viewBox="-6 -6 117 80"
        role="img"
        aria-label={
          selected
            ? `Selected ${selected.kind} at ${clock(selected.t)}, from ${selected.start.join(", ")} to ${selected.end.join(", ")}`
            : "Football pitch showing the last five on-ball actions, not player tracking"
        }
      >
        <defs>
          <marker
            id="arrow-h"
            markerWidth="4"
            markerHeight="4"
            refX="3"
            refY="2"
            orient="auto"
          >
            <path d="M0,0 L4,2 L0,4" fill="#ffce8e" />
          </marker>
          <marker
            id="arrow-n"
            markerWidth="4"
            markerHeight="4"
            refX="3"
            refY="2"
            orient="auto"
          >
            <path d="M0,0 L4,2 L0,4" fill="#bacafa" />
          </marker>
        </defs>
        <g className="pitch-lines" fill="none">
          <rect width="105" height="68" />
          <path d="M52.5 0V68" />
          <circle cx="52.5" cy="34" r="9.15" />
          <path d="M0 13.84H16.5V54.16H0 M105 13.84H88.5V54.16H105 M0 24.84H5.5V43.16H0 M105 24.84H99.5V43.16H105" />
          <circle cx="11" cy="34" r=".4" />
          <circle cx="94" cy="34" r=".4" />
          <path d="M0 30H-2V38H0 M105 30H107V38H105" />
        </g>
        <path d="M70 0V68" className="entry-line" />
        <text x="71.5" y="65" className="pitch-label">
          ENTRY LINE
        </text>
        {recent.map((e, i) => (
          <g key={e.id} opacity={selected ? 1 : 0.25 + 0.15 * i}>
            <line
              x1={e.start[0]}
              y1={e.start[1]}
              x2={e.end[0]}
              y2={e.end[1]}
              stroke={e.team === "H" ? "#ffce8e" : "#bacafa"}
              strokeWidth={selected ? 0.65 : 0.45}
              markerEnd={`url(#arrow-${e.team.toLowerCase()})`}
              strokeDasharray={e.kind === "shot" ? "1.5 1" : undefined}
            />
            <circle
              cx={e.start[0]}
              cy={e.start[1]}
              r=".85"
              fill={e.team === "H" ? "#ffce8e" : "#bacafa"}
            />
          </g>
        ))}
        <circle
          cx={point[0]}
          cy={point[1]}
          r="1.7"
          fill="#fff"
          stroke="#124f50"
          strokeWidth=".65"
        />
      </svg>
      <div className="pitch-caption">
        <span>
          {chosen
            ? `${clock(chosen.t)} · ${players[chosen.team]?.[chosen.actor] || chosen.actor} · ${chosen.kind}${chosen.kind === "shot" ? ` (${chosen.outcome})` : ""}`
            : "Kick-off · Harbor FC"}
        </span>
        <span>On-ball data only</span>
      </div>
    </div>
  );
}

function Comparison({
  state,
  inspect,
}: {
  state: State;
  inspect: (id: string) => void;
}) {
  const at = state.at;
  return (
    <section className="comparison" aria-label="Window comparison">
      <div className="section-heading">
        <h2>What changed?</h2>
        <span>
          {clock(Math.max(0, at - 360))}–{clock(Math.max(0, at - 180))} <b>→</b>{" "}
          {clock(Math.max(0, at - 180))}–{clock(at)}
        </span>
      </div>
      <div className="metric-legend">
        <span>HARBOR FC</span>
        <span>Previous / current</span>
      </div>
      {[
        "possession",
        "shots",
        "entries",
        "high_recoveries",
        "transition_shots",
      ].map((metric) => {
        const previous = state.receipts[`H.${metric}.previous`],
          current = state.receipts[`H.${metric}.current`];
        const max =
          metric === "possession"
            ? 100
            : Math.max(4, previous.value, current.value);
        return (
          <button
            type="button"
            className="metric-row"
            key={metric}
            onClick={() => inspect(current.id)}
            disabled={!state.snapshot_id}
            aria-label={`Inspect ${labels[metric]} evidence: ${num(previous)} previous, ${num(current)} current`}
          >
            <span>{labels[metric]}</span>
            <span className="metric-bars" aria-hidden="true">
              <i style={{ width: `${(100 * previous.value) / max}%` }} />
              <i style={{ width: `${(100 * current.value) / max}%` }} />
            </span>
            <span className="metric-value">
              <em>{num(previous)}</em>
              <b>{num(current)}</b>
            </span>
          </button>
        );
      })}
      <p className="footnote">
        Entries = first pass over attacking 70m per possession. Recovery → shot
        = within 10s, without losing the ball.
      </p>
    </section>
  );
}

export default function MatchLens() {
  const [state, setState] = useState<State | null>(null);
  const [error, setError] = useState("");
  const [connection, setConnection] = useState("Connecting");
  const [mode, setMode] = useState<"fan" | "analyst">("fan");
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [receiptId, setReceiptId] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [showAll, setShowAll] = useState(false);
  const [overlay, setOverlay] = useState(false);
  const [busy, setBusy] = useState(false);
  const [trace, setTrace] = useState(false);
  const evidenceHeading = useRef<HTMLHeadingElement>(null);
  const evidenceTrigger = useRef<HTMLElement | null>(null);
  const commit = useCallback(
    (next: State) =>
      setState((old) =>
        !old ||
        next.epoch > old.epoch ||
        (next.epoch === old.epoch && next.revision >= old.revision)
          ? next
          : old,
      ),
    [],
  );

  useEffect(() => {
    let closed = false;
    let stream: EventSource | undefined;
    api<State>("sessions", {})
      .then((initial) => {
        if (closed) return;
        commit(initial);
        stream = new EventSource("/api/stream");
        stream.onopen = () => {
          if (!closed) setConnection("Connected");
        };
        stream.addEventListener("state", (event: MessageEvent) => {
          if (!closed) {
            commit(JSON.parse(event.data));
            setConnection("Connected");
          }
        });
        stream.onerror = () => {
          if (!closed) setConnection("Reconnecting");
        };
      })
      .catch((e) => {
        if (!closed) {
          setError(e.message);
          setConnection("Unavailable");
        }
      });
    return () => {
      closed = true;
      stream?.close();
    };
  }, [commit]);

  useEffect(() => {
    setEvidence(null);
    setReceiptId("");
    setSelectedId("");
    setShowAll(false);
    setOverlay(false);
  }, [state?.snapshot_id]);

  const control = async (body: object) => {
    setError("");
    setBusy(true);
    try {
      commit(await api<State>("control", body));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const analyse = async () => {
    setError("");
    setBusy(true);
    try {
      commit(await api<State>("analyse", {}));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const inspect = async (id: string, snapshotId?: string) => {
    const target = snapshotId || state?.snapshot_id;
    if (!target) return;
    if (!evidence)
      evidenceTrigger.current = document.activeElement as HTMLElement;
    setError("");
    try {
      const data =
        evidence?.snapshot_id === target
          ? evidence
          : await api<Evidence>(`evidence/${target}`);
      setEvidence(data);
      setReceiptId(id);
      setShowAll(false);
      setSelectedId(data.receipts[id]?.event_ids.at(-1) || "");
      setTimeout(() => {
        evidenceHeading.current?.focus({ preventScroll: true });
        evidenceHeading.current?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }, 30);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const selectedEvent =
    evidence?.events.find((e) => e.id === selectedId) ||
    state?.events.find((e) => e.id === selectedId) ||
    null;
  const receipt = evidence?.receipts[receiptId];
  const focus = state?.chapters.find((c) => c.id === state.focus);
  const result = state?.result;
  const card = result?.accepted[0];
  const pending = ["queued", "analysing", "verifying"].includes(
    state?.analysis?.status || "",
  );

  return (
    <main data-ui="matchlens">
      <a className="skip" href="#match-workspace">
        Skip to match
      </a>
      <header className="masthead">
        <a href="/" className="brand" aria-label="MatchLens AI home">
          <svg viewBox="0 0 32 32" aria-hidden="true">
            <circle cx="14" cy="14" r="10" />
            <circle cx="14" cy="14" r="3" />
            <path d="M21 21L29 29 M4 14H8 M20 14H24 M14 4V8 M14 20V24" />
          </svg>
          <span>
            MatchLens <em>AI</em>
          </span>
        </a>
        <span className="masthead-purpose">
          Football intelligence you can challenge
        </span>
        <span className="connection">
          <i className={connection === "Connected" ? "connected" : ""} />
          {connection}
        </span>
      </header>

      <div className="workspace" id="match-workspace">
        {error && (
          <div className="error-banner" role="alert">
            {error}
            <button
              type="button"
              onClick={() => setError("")}
              aria-label="Dismiss error"
            >
              Dismiss
            </button>
          </div>
        )}
        <section className="scoreboard" aria-label="Match scoreboard">
          <div className="score-context">
            <span className="demo-label">SYNTHETIC MATCH · 12 MINUTES</span>
            <span>
              {state?.focus
                ? `FOCUS MOMENT ${state.focus}`
                : state?.ended
                  ? "FULL TIME"
                  : "MATCH REPLAY"}
            </span>
          </div>
          <div className="score-main">
            <div className="team team-home">
              <span className="team-abbr">HFC</span>
              <div>
                <h1>Harbor FC</h1>
                <span>Home</span>
              </div>
            </div>
            <div className="score-center">
              <div className="score">
                {state?.score.H ?? "–"}
                <span>:</span>
                {state?.score.N ?? "–"}
              </div>
              <div className="match-clock">
                {clock(state?.at || 0)}{" "}
                <span>
                  {state?.focus
                    ? "FROZEN"
                    : !state || state.paused
                      ? "PAUSED"
                      : `${state.speed}×`}
                </span>
              </div>
            </div>
            <div className="team team-away">
              <div>
                <h2>Northbridge United</h2>
                <span>Away</span>
              </div>
              <span className="team-abbr">NBU</span>
            </div>
          </div>
          <div className="score-controls">
            <p>
              {state?.focus
                ? "Analysis and evidence stay fixed at this moment."
                : "One continuous match. Focus a chapter to investigate it."}
            </p>
            <div className="replay-controls">
              <button
                type="button"
                disabled={!state || busy}
                onClick={() => control({ action: "restart" })}
              >
                Restart
              </button>
              {state?.focus ? (
                <button
                  type="button"
                  onClick={() => control({ action: "exit_focus" })}
                  disabled={busy}
                >
                  Exit focus →
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() =>
                    control({ action: state?.paused ? "play" : "pause" })
                  }
                  disabled={!state || busy || state.ended}
                >
                  {!state || state.paused ? "Play replay" : "Pause"}
                </button>
              )}
              <label className="speed-label">
                Speed
                <select
                  name="speed"
                  aria-label="Replay speed"
                  value={state?.speed || 6}
                  disabled={!state || busy}
                  onChange={(e) =>
                    control({ action: "speed", speed: Number(e.target.value) })
                  }
                >
                  <option value="1">1×</option>
                  <option value="6">6×</option>
                  <option value="30">30×</option>
                </select>
              </label>
            </div>
          </div>
          <div
            className="timeline"
            aria-label={`${clock(state?.at || 0)} of 12 minutes`}
          >
            <span style={{ width: `${(state?.at || 0) / 7.2}%` }} />
            {[360, 540, 720].map((t, i) => (
              <i
                key={t}
                style={{ left: `${Math.min(99.8, t / 7.2)}%` }}
                title={`Chapter ${"ABC"[i]} at ${clock(t)}`}
              />
            ))}
          </div>
        </section>

        <nav className="chapters" aria-label="Focus a match chapter">
          {(
            state?.chapters || [
              {
                id: "A",
                at: 360,
                title: "Possession without penetration",
                question: "",
              },
              {
                id: "B",
                at: 540,
                title: "Recoveries to transition shots",
                question: "",
              },
              { id: "C", at: 720, title: "Goal and match recap", question: "" },
            ]
          ).map((chapter) => (
            <button
              type="button"
              key={chapter.id}
              aria-pressed={state?.focus === chapter.id}
              disabled={!state || busy}
              onClick={() => control({ action: "focus", chapter: chapter.id })}
            >
              <span className="chapter-letter">{chapter.id}</span>
              <span>
                <b>{chapter.title}</b>
                <small>{clock(chapter.at)} · Focus moment</small>
              </span>
              <span className="chapter-arrow">↗</span>
            </button>
          ))}
        </nav>

        {!state ? (
          <div className="initial-state" role="status">
            <h2>Preparing the match</h2>
            <p>
              {error ||
                "Loading validated events and connecting to the replay."}
            </p>
          </div>
        ) : (
          <>
            <div className="match-grid">
              <div className="match-analysis">
                <Pitch
                  events={state.events}
                  selected={selectedEvent}
                  ball={state.ball}
                  players={state.players}
                />
                <Comparison state={state} inspect={inspect} />
              </div>
              <section
                className="insight-desk"
                aria-labelledby="insight-heading"
              >
                <div className="section-heading">
                  <h2 id="insight-heading">Match insight</h2>
                  <div
                    className="mode-switch"
                    role="group"
                    aria-label="Audience mode"
                  >
                    <button
                      type="button"
                      aria-pressed={mode === "fan"}
                      onClick={() => setMode("fan")}
                    >
                      Fan
                    </button>
                    <button
                      type="button"
                      aria-pressed={mode === "analyst"}
                      onClick={() => setMode("analyst")}
                    >
                      Analyst
                    </button>
                  </div>
                </div>
                <div className={`focus-question ${card ? "has-result" : ""}`}>
                  <span>
                    {focus
                      ? `CHAPTER ${focus.id} · AS OF ${clock(focus.at)}`
                      : "START AN INVESTIGATION"}
                  </span>
                  <h3>{focus?.question || "What is the score missing?"}</h3>
                  <p>
                    {focus
                      ? "Compare the windows. Inspect the source before accepting the interpretation."
                      : "Choose a focus moment above to compare the numbers and ask both agents to investigate."}
                  </p>
                </div>
                {focus && !pending && !result && (
                  <div className="analyse-action">
                    <button
                      type="button"
                      className="primary"
                      onClick={analyse}
                      disabled={busy || state.session_analyses_remaining <= 0}
                    >
                      {state.model_configured
                        ? "Analyse this moment"
                        : "Show available statistics"}
                      <span>↗</span>
                    </button>
                    <small>
                      {state.model_configured
                        ? "Real model calls · no prepared answers"
                        : "Model unavailable · deterministic statistics remain available"}
                    </small>
                  </div>
                )}
                {pending && (
                  <div className="pending" role="status" aria-live="polite">
                    <div className="working-line" />
                    <span>
                      {state.analysis?.status === "verifying"
                        ? "Verifier is checking the evidence"
                        : state.analysis?.status === "queued"
                          ? "Waiting for an analysis slot"
                          : "Analyst is investigating"}
                    </span>
                    <p>
                      Frozen at {clock(state.analysis?.as_of || 0)}. The match
                      will wait while both agents work.
                    </p>
                  </div>
                )}
                {result?.status === "fallback" && !pending && (
                  <div className="fallback" role="status">
                    <b>Statistics available · AI analysis unavailable</b>
                    <p>
                      {result.error === "model_not_configured"
                        ? "No model credential is configured on this server."
                        : result.error === "inference_budget_exhausted"
                          ? "The demo has reached its configured AI budget."
                          : result.error === "analysis_timeout"
                            ? "The analysis reached its time limit."
                            : "The analysis could not finish or pass validation."}{" "}
                      Explore the computed metrics and source events below.
                    </p>
                    <button
                      type="button"
                      onClick={analyse}
                      disabled={busy || state.session_analyses_remaining <= 0}
                    >
                      Try analysis again
                    </button>
                  </div>
                )}
                {card && !pending && (
                  <article className="insight-card" data-testid="insight-card">
                    <div className="card-provenance">
                      <span className="verdict">
                        {card.verdict === "qualify" ? "QUALIFIED" : "PUBLISHED"}
                      </span>
                      <span>
                        As of {clock(card.as_of)} ·{" "}
                        {result?.reused
                          ? "saved analysis"
                          : card.scope === "match"
                            ? "verified sequence"
                            : "verified window"}
                      </span>
                    </div>
                    <p className={`insight-copy ${mode}`}>{card[mode]}</p>
                    <div className="card-evidence">
                      <span>{card.refs.length} metric receipts</span>
                      <button
                        type="button"
                        onClick={() => inspect(card.refs[0], card.snapshot_id)}
                      >
                        Challenge with evidence <span>↗</span>
                      </button>
                    </div>
                    {mode === "analyst" && (
                      <div className="review-note">
                        <b>Verifier&apos;s reasoning</b>
                        <p>{card.reason}</p>
                        {card.limitations.length > 0 && (
                          <ul>
                            {card.limitations.map((l, i) => (
                              <li key={i}>{l}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}
                  </article>
                )}
                {!!result?.rejected.length && !pending && (
                  <div className="withheld">
                    <b>
                      {card
                        ? "Other claims withheld"
                        : "No claim cleared publication"}
                    </b>
                    {result.rejected.map((r) => (
                      <p key={r.claim_id}>
                        {r.reason}
                        <small>Gate: {r.gate.replaceAll("_", " ")}</small>
                      </p>
                    ))}
                  </div>
                )}
                <div className="desk-footer">
                  <span className="pipeline">
                    Events <i>→</i> metrics <i>→</i> Analyst <i>→</i> Verifier
                  </span>
                  <div>
                    <button
                      type="button"
                      onClick={() => setTrace(!trace)}
                      aria-expanded={trace}
                    >
                      {trace ? "Hide" : "View"} run trace
                    </button>
                    <button
                      type="button"
                      onClick={() => setOverlay(!overlay)}
                      aria-expanded={overlay}
                      disabled={!card}
                    >
                      Overlay preview
                    </button>
                  </div>
                </div>
                {trace && (
                  <div className="run-trace">
                    <h3>Execution trace</h3>
                    {result ? (
                      <>
                        <p>
                          {result.origin === "live_model"
                            ? "Real DeepSeek Flash · Microsoft Agent Framework"
                            : "Deterministic fallback"}
                          <br />
                          {result.duration_ms != null &&
                            `${(result.duration_ms / 1000).toFixed(2)}s · `}
                          {result.requests} model requests · {result.run_id}
                        </p>
                        <ol>
                          {result.audit
                            .filter((e) =>
                              [
                                "tool",
                                "handoff",
                                "http_receipt",
                                "schema_correction",
                                "failure",
                              ].includes(e.type),
                            )
                            .map((e, i) => (
                              <li key={i}>
                                {e.type === "handoff"
                                  ? `${e.from} → ${e.to} · validated claim handoff`
                                  : e.type === "tool"
                                    ? `${e.role} · ${e.name}`
                                    : e.type === "http_receipt"
                                      ? `${e.role} · HTTP ${e.status}${e.usage ? ` · ${e.usage.completion_tokens} output tokens` : ""}`
                                      : e.type === "schema_correction"
                                        ? `${e.role} · bounded format correction`
                                        : `${e.role} · validation or provider failure`}
                              </li>
                            ))}
                        </ol>
                      </>
                    ) : (
                      <p>A trace appears after a real analysis attempt.</p>
                    )}
                  </div>
                )}
                {overlay && card && (
                  <div className="overlay-preview">
                    <span>
                      BROADCAST OVERLAY PREVIEW · AS OF {clock(card.as_of)}
                    </span>
                    <div className="broadcast-strip">
                      <b>
                        HFC {state.score.H}–{state.score.N} NBU
                      </b>
                      <p>{card.fan}</p>
                    </div>
                    <small>
                      Reuses the approved Fan insight. No video processing.
                    </small>
                  </div>
                )}
              </section>
              <aside className="event-feed" aria-label="Match events">
                <div className="section-heading">
                  <h2>Event log</h2>
                  <span>{state.events.length} events</span>
                </div>
                <p className="feed-caption">Latest on-ball actions</p>
                <ol>
                  {state.events
                    .slice(-9)
                    .reverse()
                    .map((event) => (
                      <li key={event.id}>
                        <button
                          type="button"
                          aria-pressed={selectedId === event.id}
                          onClick={() => setSelectedId(event.id)}
                        >
                          <time>{clock(event.t)}</time>
                          <span className={`event-dot ${event.team}`} />
                          <span>
                            <b>
                              {event.kind === "shot" && event.outcome === "goal"
                                ? "Goal"
                                : event.kind === "recovery"
                                  ? "Ball recovery"
                                  : event.kind[0].toUpperCase() +
                                    event.kind.slice(1)}
                            </b>
                            <small>
                              {state.players[event.team][event.actor]}
                              {event.receiver
                                ? ` → ${state.players[event.team][event.receiver]}`
                                : ""}
                            </small>
                          </span>
                          <small className="event-id">{event.id}</small>
                        </button>
                      </li>
                    ))}
                </ol>
                <div className="data-note">
                  <b>Synthetic, not simulated tracking</b>
                  <p>
                    One seeded event sequence. Score, ownership and coordinates
                    are validated before analysis.
                  </p>
                </div>
              </aside>
            </div>

            {evidence && (
              <section
                className="evidence-section"
                aria-labelledby="evidence-heading"
              >
                <div className="section-heading">
                  <div>
                    <span className="small-label">
                      INSPECT THE SOURCE · AS OF {clock(evidence.as_of)}
                    </span>
                    <h2
                      id="evidence-heading"
                      tabIndex={-1}
                      ref={evidenceHeading}
                    >
                      Every claim has a receipt.
                    </h2>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setEvidence(null);
                      setSelectedId("");
                      requestAnimationFrame(() =>
                        evidenceTrigger.current?.focus(),
                      );
                    }}
                    aria-label="Close evidence panel"
                  >
                    Close evidence
                  </button>
                </div>
                <div className="evidence-layout">
                  <div>
                    <div className="receipt-select">
                      <label htmlFor="receipt">Metric receipt</label>
                      <select
                        name="receipt"
                        id="receipt"
                        value={receiptId}
                        onChange={(e) => {
                          setReceiptId(e.target.value);
                          setSelectedId(
                            evidence.receipts[e.target.value].event_ids.at(
                              -1,
                            ) || "",
                          );
                          setShowAll(false);
                        }}
                      >
                        {Object.values(evidence.receipts)
                          .filter((r) => r.id.startsWith("H."))
                          .map((r) => (
                            <option key={r.id} value={r.id}>
                              {titleFor(r.id)} · {r.id.split(".")[2]}
                            </option>
                          ))}
                      </select>
                    </div>
                    {receipt && (
                      <>
                        <div className="receipt-value">
                          <strong>{num(receipt)}</strong>
                          <span>
                            {receipt.unit === "%"
                              ? "controlled time"
                              : receipt.unit}
                            <br />
                            {clock(receipt.start)}–{clock(receipt.end)}
                          </span>
                        </div>
                        <p>{receipt.definition}</p>
                        {receipt.denominator != null && (
                          <p className="arithmetic">
                            {receipt.numerator}s / {receipt.denominator}s × 100
                            = {receipt.value}%
                          </p>
                        )}
                        <p className="footnote">Receipt ID: {receipt.id}</p>
                        {!!receipt.chains?.length && (
                          <div
                            className="receipt-chains"
                            aria-label="Recorded event chains"
                          >
                            {receipt.chains.map((chain, i) => {
                              const ids = Array.isArray(chain)
                                ? chain
                                : chain.event_ids;
                              return (
                                <button
                                  type="button"
                                  key={i}
                                  onClick={() =>
                                    setSelectedId(ids.at(-1) || "")
                                  }
                                >
                                  {Array.isArray(chain)
                                    ? `${chain.length} events ending with the goal`
                                    : `${chain.event_ids.join(" → ")} · ${chain.seconds}s`}
                                </button>
                              );
                            })}
                          </div>
                        )}
                        <div
                          className="source-ids"
                          role="group"
                          aria-label="Source event IDs"
                        >
                          {receipt.event_ids
                            .slice(0, showAll ? undefined : 12)
                            .map((id) => (
                              <button
                                type="button"
                                key={id}
                                aria-pressed={id === selectedId}
                                onClick={() => setSelectedId(id)}
                              >
                                {id}
                              </button>
                            ))}
                          {!receipt.event_ids.length && (
                            <p>
                              No matching events in this window. The full prefix
                              remains inspectable.
                            </p>
                          )}
                        </div>
                        {receipt.event_ids.length > 12 && (
                          <button
                            type="button"
                            className="text-button"
                            onClick={() => setShowAll(!showAll)}
                          >
                            {showAll
                              ? "Show fewer events"
                              : `Show all ${receipt.event_ids.length} source events`}
                          </button>
                        )}
                      </>
                    )}
                  </div>
                  <div className="source-detail">
                    <h3>Original event</h3>
                    {selectedEvent ? (
                      <>
                        <div className="event-detail-title">
                          <b>{selectedEvent.id}</b>
                          <span>
                            {clock(selectedEvent.t)} · {selectedEvent.kind}
                          </span>
                        </div>
                        <dl>
                          <div>
                            <dt>Team / player</dt>
                            <dd>
                              {selectedEvent.team === "H"
                                ? "Harbor FC"
                                : "Northbridge United"}{" "}
                              /{" "}
                              {
                                state.players[selectedEvent.team][
                                  selectedEvent.actor
                                ]
                              }
                            </dd>
                          </div>
                          <div>
                            <dt>Coordinates</dt>
                            <dd>
                              ({selectedEvent.start.join(", ")}) → (
                              {selectedEvent.end.join(", ")}) m
                            </dd>
                          </div>
                          <div>
                            <dt>Outcome</dt>
                            <dd>{selectedEvent.outcome}</dd>
                          </div>
                          <div>
                            <dt>Possession after event</dt>
                            <dd>{selectedEvent.possession_id}</dd>
                          </div>
                        </dl>
                        <details>
                          <summary>Raw event JSON</summary>
                          <pre>{JSON.stringify(selectedEvent, null, 2)}</pre>
                        </details>
                      </>
                    ) : (
                      <p>
                        Select an event ID to inspect its original data and
                        highlight it on the pitch.
                      </p>
                    )}
                    <details className="prefix-events">
                      <summary>
                        All {evidence.events.length} events in this prefix
                      </summary>
                      <div className="prefix-list">
                        {evidence.events.map((e) => (
                          <button
                            type="button"
                            key={e.id}
                            aria-pressed={e.id === selectedId}
                            onClick={() => setSelectedId(e.id)}
                          >
                            {e.id} · {clock(e.t)} · {e.team} {e.kind}
                          </button>
                        ))}
                      </div>
                    </details>
                    <p className="snapshot-hash">
                      Immutable snapshot
                      <br />
                      {evidence.snapshot_id}
                    </p>
                  </div>
                </div>
              </section>
            )}

            {state.ended && (
              <section className="recap">
                <div>
                  <span className="small-label">
                    FULL-TIME · 12-MINUTE DEMONSTRATION
                  </span>
                  <h2>The match, with its evidence.</h2>
                  <p>
                    Harbor FC {state.score.H}–{state.score.N} Northbridge
                    United.{" "}
                    {state.history.length
                      ? "Revisit the approved insights collected during this session."
                      : "Focus the chapters and run analysis to build a recap from approved insights."}
                  </p>
                </div>
                <div className="recap-items">
                  {state.history
                    .sort((a, b) => a.as_of - b.as_of)
                    .map((item) => (
                      <button
                        type="button"
                        key={`${item.snapshot_id}-${item.claim_id}`}
                        onClick={() => inspect(item.refs[0], item.snapshot_id)}
                      >
                        <time>{clock(item.as_of)}</time>
                        <span>{item.fan}</span>
                        <span>↗</span>
                      </button>
                    ))}
                </div>
              </section>
            )}
          </>
        )}
        <footer>
          <span>MatchLens AI · R0.1</span>
          <span>Fictional teams · Seed 17 · No match footage</span>
          <span>Independent review, inspectable evidence</span>
        </footer>
      </div>
    </main>
  );
}

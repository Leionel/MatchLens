"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Scoreboard } from "./components/Scoreboard";
import { ReplayControls } from "./components/ReplayControls";
import { MatchTimeline } from "./components/MatchTimeline";
import { MatchStage } from "./components/MatchStage";
import { MetricComparison } from "./components/MetricComparison";
import { InsightSpotlight } from "./components/InsightSpotlight";
import { EvidenceDrawer } from "./components/EvidenceDrawer";
import { BroadcastOverlay } from "./components/BroadcastOverlay";
import { EventFeed } from "./components/EventFeed";
import { MatchRecap } from "./components/MatchRecap";

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

type Moment = {
  id: string;
  team?: "H" | "N";
  chapter_id?: string;
  at: number;
  badge: string;
  title: string;
  question: string;
  assertion: string;
  summary: string;
  priority: number;
};

type ScenarioMeta = {
  id: string;
  label: string;
  archetype: string;
  description: string;
};

type PossessionSequence = {
  sequence_id: string;
  possession_id: number;
  team: "H" | "N";
  start_t: number;
  end_t: number;
  duration: number;
  origin_kind: string;
  pass_count: number;
  progressive_distance: number;
  territory_gained?: number;
  start_coords?: [number, number];
  end_coords?: [number, number];
  entered_final_third: boolean;
  outcome: string;
  players: string[];
  event_ids: string[];
  events_detail?: {
    seq_step: number;
    id: string;
    kind: string;
    team: "H" | "N";
    actor: string;
    actor_name?: string;
    receiver?: string | null;
    receiver_name?: string | null;
    start: [number, number];
    end: [number, number];
    outcome: string;
    t: number;
    gain_m: number;
    channel?: string;
  }[];
};

type PlayerSpotlight = {
  player_id: string;
  name: string;
  team: "H" | "N";
  team_name: string;
  passes: number;
  progressive_passes: number;
  progressive_distance: number;
  final_third_entries: number;
  recoveries: number;
  shots: number;
  goals: number;
  sequences_involved: number;
  event_ids: string[];
};

type State = {
  revision: number;
  epoch: number;
  at: number;
  scenario?: string;
  scenarios?: ScenarioMeta[];
  focus_team?: "H" | "N";
  score: { H: number; N: number };
  paused: boolean;
  speed: number;
  focus: string | null;
  ball: [number, number];
  events: FootballEvent[];
  receipts: Record<string, Receipt>;
  sequences?: PossessionSequence[];
  tactical?: any;
  player_spotlight?: PlayerSpotlight[];
  players: Record<string, Record<string, string>>;
  chapters: { id: string; at: number; title: string; question: string }[];
  moments?: Moment[];
  active_moment?: Moment | null;
  snapshot_id: string | null;
  snapshot_as_of: number | null;
  analysis_receipts: Record<string, Receipt> | null;
  auto_status: string;
  analysis: { status: string; as_of: number; run_id: string } | null;
  result: Result | null;
  history: Card[];
  model_configured: boolean;
  ended: boolean;
  session_analyses_remaining: number;
};

const clock = (s: number) =>
  `${Math.floor(s / 60).toString().padStart(2, "0")}:${Math.floor(s % 60).toString().padStart(2, "0")}`;

async function api<T>(path: string, body?: object): Promise<T> {
  const response = await fetch(`/api/${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const errors: Record<number, string> = {
      401: "Your session expired. Refresh to start a new match.",
      409: "Please exit focus or select a valid moment to continue.",
      429: "Analysis limit reached. Please wait a moment before trying again.",
      503: "The demo server is currently busy. Please retry shortly.",
    };
    throw Object.assign(new Error(errors[response.status] || `Request failed (${response.status})`), {status: response.status});
  }
  return response.json();
}

export default function MatchLens() {
  const [state, setState] = useState<State | null>(null);
  const [error, setError] = useState("");
  const [connection, setConnection] = useState("Connecting");
  const [mode, setMode] = useState<"fan" | "analyst">("fan");
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [receiptId, setReceiptId] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [selectedSeqId, setSelectedSeqId] = useState("");
  const [explorerTab, setExplorerTab] = useState<"sequences" | "players">("sequences");
  const [showAllEvents, setShowAllEvents] = useState(false);
  const [showOverlay, setShowOverlay] = useState(false);
  const [showTrace, setShowTrace] = useState(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const inspectionRequest = useRef(0);

  useEffect(() => {
    inspectionRequest.current += 1;
    setEvidence(null);
    setSelectedId("");
    setSelectedSeqId("");
    setIsDrawerOpen(false);
    setShowOverlay(false);
    setShowTrace(false);
  }, [state?.epoch]);

  const commit = useCallback((next: State) => {
    setState((old) =>
      !old || next.epoch > old.epoch || (next.epoch === old.epoch && next.revision >= old.revision)
        ? next
        : old,
    );
  }, []);

  useEffect(() => {
    let closed = false;
    let stream: EventSource | undefined;
    let poll: ReturnType<typeof setInterval> | undefined;

    api<State>("sessions", {})
      .then((initial) => {
        if (closed) return;
        commit(initial);
        stream = new EventSource("/api/stream");
        stream.onopen = () => {
          if (!closed) setConnection("Connected");
          if (poll) { clearInterval(poll); poll = undefined; }
        };
        stream.addEventListener("state", (event: MessageEvent) => {
          if (!closed) {
            commit(JSON.parse(event.data));
            setConnection("Connected");
          }
        });
        stream.onerror = () => {
          if (!closed) setConnection("Reconnecting");
          if (!poll) poll = setInterval(() => {
            api<State>("state").then((next) => {
              if (!closed) { commit(next); setConnection("Polling"); }
            }).catch((e) => {
              if (!closed) {
                setError(e.message);
                if (e.status === 401) {
                  stream?.close();
                  if (poll) { clearInterval(poll); poll = undefined; }
                  setConnection("Session expired");
                }
              }
            });
          }, 2000);
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
      if (poll) clearInterval(poll);
    };
  }, [commit]);

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
    const request = ++inspectionRequest.current;
    const target = snapshotId || state?.snapshot_id;
    if (!target) return;
    setError("");
    try {
      const data =
        evidence?.snapshot_id === target
          ? evidence
          : await api<Evidence>(`evidence/${target}`);
      if (request !== inspectionRequest.current) return;
      setEvidence(data);
      setReceiptId(id);
      setSelectedId(data.receipts[id]?.event_ids.at(-1) || "");
      setShowAllEvents(false);
      setIsDrawerOpen(true);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const selectedEvent =
    evidence?.events.find((e) => e.id === selectedId) ||
    state?.events.find((e) => e.id === selectedId) ||
    null;

  const activeChapter = state?.chapters.find((c) => c.id === state.focus) || null;
  const activeMoment = state?.active_moment || null;
  const result = state?.result || null;
  const card = result?.accepted[0] || null;
  const pending = ["queued", "analysing", "verifying"].includes(state?.analysis?.status || "");
  const clockText = clock(state?.at || 0);

  // Approximate possession % for Harbor FC from current receipts
  const posValue = state?.receipts["H.possession.current"]?.value ?? 50;

  return (
    <main className="matchlens-app-root">
      <header className="app-masthead">
        <div className="masthead-container">
          <a href="/" className="brand-lockup" aria-label="MatchLens AI Home">
            <svg viewBox="0 0 32 32" className="brand-icon" aria-hidden="true">
              <circle cx="14" cy="14" r="10" />
              <circle cx="14" cy="14" r="3" />
              <path d="M21 21L29 29 M4 14H8 M20 14H24 M14 4V8 M14 20V24" />
            </svg>
            <div className="brand-text">
              <span className="brand-title">MATCHLENS</span>
              <span className="brand-ai">AI</span>
            </div>
          </a>

          <div className="masthead-tagline">
            <span className="tagline-highlight">FOOTBALL INTELLIGENCE YOU CAN CHALLENGE</span>
            <span className="tagline-sub">Microsoft Agent Framework · DeepSeek Flash · Dual-Agent Verification</span>
          </div>

          <div className="masthead-status">
            <span className={`connection-pill ${connection === "Connected" ? "connected" : ""}`}>
              <i className="status-dot" />
              <span>{connection}</span>
            </span>
          </div>
        </div>
      </header>

      <div className="app-workspace">
        {error && (
          <div className="global-error-toast" role="alert">
            <span className="error-icon">⚠️</span>
            <span className="error-msg">{error}</span>
            <a href="/">Start a new replay</a>
            <button
              type="button"
              className="btn-dismiss-error"
              onClick={() => setError("")}
              aria-label="Dismiss error"
            >
              ✕
            </button>
          </div>
        )}

        {!state ? (
          <div className="initial-loading-card" role="status">
            <div className="loader-ring" />
            <h2>Connecting to MatchLens Replay Engine</h2>
            <p>Ingesting validated event stream & initializing dual-agent deliberation runtime...</p>
          </div>
        ) : (
          <>
            {/* 1. Scoreboard */}
            <Scoreboard
              score={state.score}
              clock={clockText}
              seconds={state.at}
              speed={state.speed}
              paused={state.paused}
              ended={state.ended}
              focus={state.focus}
              activeMomentBadge={activeMoment?.badge}
              possessionH={posValue}
            />

            {/* 2. Replay Toolbar */}
            <ReplayControls
              paused={state.paused}
              speed={state.speed}
              ended={state.ended}
              focus={state.focus}
              busy={busy}
              onPlayPause={() => control({ action: state.paused ? "play" : "pause" })}
              onRestart={() => control({ action: "restart" })}
              onExitFocus={() => control({ action: "exit_focus" })}
              onSpeedChange={(speed) => control({ action: "speed", speed })}
            />

            {/* 2.5 R1 Scenario & Both-Team Intelligence Context Bar */}
            <section className="r1-context-bar" aria-label="Scenario and team intelligence context">
              <div className="r1-scenario-group">
                <label htmlFor="scenario-select" className="r1-context-label">
                  MATCH ARCHETYPE
                </label>
                <select
                  id="scenario-select"
                  value={state.scenario || "default"}
                  disabled={busy}
                  onChange={(e) => control({ action: "set_scenario", scenario: e.target.value })}
                  className="r1-scenario-select"
                >
                  {(state.scenarios || []).map((sc) => (
                    <option key={sc.id} value={sc.id}>
                      {sc.label} — {sc.archetype}
                    </option>
                  ))}
                </select>
              </div>

              <div className="r1-team-group" role="group" aria-label="Focus Team Selection">
                <span className="r1-context-label">TEAM LENS</span>
                <div className="r1-team-buttons">
                  <button
                    type="button"
                    className={`r1-team-btn ${(state.focus_team || "H") === "H" ? "active" : ""}`}
                    aria-pressed={(state.focus_team || "H") === "H"}
                    disabled={busy}
                    onClick={() => control({ action: "set_team", team: "H" })}
                  >
                    <span className="team-h-dot">●</span> Harbor FC (Home)
                  </button>
                  <button
                    type="button"
                    className={`r1-team-btn ${state.focus_team === "N" ? "active" : ""}`}
                    aria-pressed={state.focus_team === "N"}
                    disabled={busy}
                    onClick={() => control({ action: "set_team", team: "N" })}
                  >
                    <span style={{ color: "#60a5fa" }}>●</span> Northbridge Utd (Away)
                  </button>
                </div>
              </div>
            </section>

            {/* 3. Match Timeline with Key Moments */}
            <MatchTimeline
              currentSeconds={state.at}
              totalSeconds={720}
              chapters={state.chapters}
              moments={state.moments || []}
              focus={state.focus}
              busy={busy}
              onFocusChapter={(chapterId) => control({ action: "focus", chapter: chapterId })}
              onFocusMoment={(id) => control({ action: "focus_moment", moment_id: id })}
            />

            {/* 4. Core Tactical Grid */}
            <div className="tactical-main-grid">
              {/* Left Column: Tactical Pitch Stage & Metric Delta */}
              <div className="tactical-left-col">
                <MatchStage
                  events={state.events}
                  selectedEvent={selectedEvent}
                  selectedSequence={
                    state.sequences?.find((sq) => sq.sequence_id === selectedSeqId) || null
                  }
                  ball={state.ball}
                  players={state.players}
                  clockText={clockText}
                  focusTeam={state.focus_team || "H"}
                  tactical={state.tactical}
                  onSelectEvent={(id) => {
                    setSelectedId(id);
                  }}
                  onClearSequence={() => setSelectedSeqId("")}
                />

                {mode === "analyst" && (
                  <MetricComparison
                    receipts={state.analysis_receipts || state.receipts}
                    at={state.snapshot_as_of ?? state.at}
                    snapshotId={state.snapshot_id}
                    focusTeam={state.focus_team || "H"}
                    onInspect={(id) => inspect(id)}
                  />
                )}

                {/* Possession Sequence & Player Spotlight Explorer */}
                <section className="sequence-player-card" aria-label="Possession sequences and player spotlight">
                  <div className="comparison-header">
                    <div>
                      <span className="comparison-tag">EVENT-GROUNDED EXPLORER</span>
                      <h3 className="comparison-title">
                        {explorerTab === "sequences" ? "Possession Sequences" : "Player Spotlight"}
                      </h3>
                    </div>
                    <div className="r1-team-buttons">
                      <button
                        type="button"
                        className={`feed-filter-btn ${explorerTab === "sequences" ? "active" : ""}`}
                        onClick={() => setExplorerTab("sequences")}
                      >
                        Sequences ({(state.sequences || []).filter((sq) => sq.team === (state.focus_team || "H")).length})
                      </button>
                      <button
                        type="button"
                        className={`feed-filter-btn ${explorerTab === "players" ? "active" : ""}`}
                        onClick={() => setExplorerTab("players")}
                      >
                        Players ({(state.player_spotlight || []).filter((p) => p.team === (state.focus_team || "H")).length})
                      </button>
                    </div>
                  </div>

                  {explorerTab === "sequences" ? (
                    <div className="sequence-list">
                      {(state.sequences || [])
                        .filter((sq) => sq.team === (state.focus_team || "H"))
                        .slice(-6)
                        .reverse()
                        .map((sq) => (
                          <div key={sq.sequence_id} className="sequence-row-container">
                            <button
                              type="button"
                              className={`sequence-row-btn ${selectedSeqId === sq.sequence_id ? "active" : ""}`}
                              onClick={() => {
                                setSelectedSeqId(selectedSeqId === sq.sequence_id ? "" : sq.sequence_id);
                                setSelectedId(sq.event_ids.at(-1) || "");
                              }}
                            >
                              <span className="seq-id-badge">{sq.sequence_id}</span>
                              <span className="seq-meta">
                                {clock(sq.start_t)}–{clock(sq.end_t)} ({sq.duration}s) · {sq.pass_count} passes · {sq.territory_gained !== undefined ? `net ${sq.territory_gained > 0 ? `+${sq.territory_gained}` : sq.territory_gained}m` : `+${sq.progressive_distance}m`}
                              </span>
                              <span className={`seq-outcome ${sq.outcome}`}>
                                {sq.outcome.replace("_", " ").toUpperCase()}
                              </span>
                            </button>
                            {selectedSeqId === sq.sequence_id && sq.events_detail && sq.events_detail.length > 0 && (
                              <div className="seq-steps-preview">
                                {sq.events_detail.map((st) => (
                                  <span
                                    key={st.id}
                                    className="seq-step-pill"
                                    onClick={() => setSelectedId(st.id)}
                                  >
                                    {st.seq_step}. {st.actor_name?.split(" ")[1] || st.actor} {st.kind}
                                    {st.gain_m !== 0 ? ` (${st.gain_m > 0 ? `+${st.gain_m}` : st.gain_m}m)` : ""}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      {(state.sequences || []).filter((sq) => sq.team === (state.focus_team || "H")).length === 0 && (
                        <p className="comparison-footer">Play or focus the match to inspect possession sequences.</p>
                      )}
                    </div>
                  ) : (
                    <div className="player-spotlight-list">
                      {(state.player_spotlight || [])
                        .filter((p) => p.team === (state.focus_team || "H"))
                        .map((p) => (
                          <button
                            key={p.player_id}
                            type="button"
                            className="sequence-row-btn"
                            onClick={() => p.event_ids.at(-1) && setSelectedId(p.event_ids.at(-1)!)}
                          >
                            <span className="seq-id-badge">{p.player_id} · {p.name}</span>
                            <span className="seq-meta">
                              {p.passes} passes ({p.progressive_passes} prog, +{p.progressive_distance}m) · {p.recoveries} rec · {p.shots} shots
                            </span>
                            <span className="seq-outcome">
                              {p.goals > 0 ? `⚽ ${p.goals} GOAL` : `${p.sequences_involved} seqs`}
                            </span>
                          </button>
                        ))}
                    </div>
                  )}
                </section>
              </div>

              {/* Right Column: AI Spotlight & Live Event Stream */}
              <div className="tactical-right-col">
                <InsightSpotlight
                  mode={mode}
                  onModeChange={setMode}
                  card={card}
                  result={result}
                  pending={pending}
                  pendingStatus={state.analysis?.status}
                  activeMoment={activeMoment}
                  activeChapter={activeChapter}
                  modelConfigured={state.model_configured}
                  busy={busy}
                  analysesRemaining={state.session_analyses_remaining}
                  onAnalyse={analyse}
                  onChallenge={(rId, sId) => inspect(rId, sId)}
                  onToggleTrace={() => setShowTrace(!showTrace)}
                  showTrace={showTrace}
                  onToggleOverlay={() => setShowOverlay(!showOverlay)}
                  showOverlay={showOverlay}
                  receipts={state.receipts}
                  snapshotId={state.snapshot_id}
                  autoStatus={state.auto_status}
                />

                {showOverlay && card && (
                  <BroadcastOverlay
                    score={Object.fromEntries(["H", "N"].map(team => [team, state.events.filter(e => e.t <= card.as_of && e.team === team && e.kind === "shot" && e.outcome === "goal").length])) as { H: number; N: number }}
                    clockText={clockText}
                    fanText={card.fan}
                    verdict={card.verdict}
                    asOf={card.as_of}
                  />
                )}

                <EventFeed
                  events={state.events}
                  selectedId={selectedId}
                  players={state.players}
                  onSelectEvent={(id) => setSelectedId(id)}
                />
              </div>
            </div>

            {/* 5. Full-time Dossier (Shown when match finishes) */}
            {state.ended && (
              <MatchRecap
                score={state.score}
                history={state.history}
                onInspect={(rId, sId) => inspect(rId, sId)}
              />
            )}

            {/* 6. Tactical Review Evidence Drawer (Modal Sheet) */}
            <EvidenceDrawer
              isOpen={isDrawerOpen}
              evidence={evidence}
              receiptId={receiptId}
              selectedEventId={selectedId}
              showAllEvents={showAllEvents}
              players={state.players}
              onClose={() => setIsDrawerOpen(false)}
              onSelectReceipt={(id) => {
                setReceiptId(id);
                if (evidence?.receipts[id]?.event_ids.length) {
                  setSelectedId(evidence.receipts[id].event_ids.at(-1) || "");
                }
              }}
              onSelectEvent={(id) => setSelectedId(id)}
              onToggleShowAll={() => setShowAllEvents(!showAllEvents)}
            />
          </>
        )}

        <footer className="app-footer">
          <div className="footer-meta">
            <span className="footer-title">MatchLens AI · R0.2 Live Intelligence Upgrade</span>
            <span className="footer-sub">
              Microsoft × Premier League Inside the Game Hackathon · Best Multi-Agent System
            </span>
          </div>
          <div className="footer-notes">
            <span>Deterministic Reducer · Immutable SHA256 Evidence · Dual-Agent Deliberation Gate</span>
          </div>
        </footer>
      </div>
    </main>
  );
}

"use client";

type ScoreboardProps = {
  score: { H: number; N: number };
  clock: string;
  seconds: number;
  speed: number;
  paused: boolean;
  ended: boolean;
  focus: string | null;
  activeMomentBadge?: string | null;
  possessionH?: number;
};

export function Scoreboard({
  score,
  clock,
  seconds,
  speed,
  paused,
  ended,
  focus,
  activeMomentBadge,
  possessionH = 50,
}: ScoreboardProps) {
  const statusLabel = focus
    ? focus.length === 1 ? `FOCUS MOMENT ${focus}` : "FOCUSED MOMENT"
    : ended
      ? "FULL TIME"
      : activeMomentBadge
        ? activeMomentBadge
        : paused
          ? "PAUSED"
          : `LIVE REPLAY · ${speed}×`;

  return (
    <section className="broadcast-scoreboard" aria-label="Synthetic match scoreboard">
      <div className="scoreboard-top-bar">
        <div className="competition-tag">
          <span className="live-dot" aria-hidden="true" />
          <span className="league-title">PREMIER LEAGUE INSIDE THE GAME</span>
          <span className="format-badge">12-MIN SYNTHETIC MATCH</span>
        </div>
        <div className={`status-pill ${focus ? "focus" : activeMomentBadge ? "moment" : ended ? "ended" : "live"}`}>
          {statusLabel}
        </div>
      </div>

      <div className="scoreboard-fixture">
        <div className="team-cell team-home">
          <div className="team-crest crest-harbor">
            <span>HFC</span>
          </div>
          <div className="team-info">
            <h1 className="team-name">Harbor FC</h1>
            <span className="team-meta">Home · Fictional team</span>
          </div>
        </div>

        <div className="score-pod">
          <div className="digits-wrap">
            <span className="digit digit-home">{score.H}</span>
            <span className="digit-separator">:</span>
            <span className="digit digit-away">{score.N}</span>
          </div>
          <div className="clock-wrap">
            <span className="match-time">{clock}</span>
            <span className="clock-state">
              {focus ? "FROZEN" : paused ? "HOLD" : `${speed}×`}
            </span>
          </div>
        </div>

        <div className="team-cell team-away">
          <div className="team-info">
            <h2 className="team-name">Northbridge Utd</h2>
            <span className="team-meta">Away · Fictional team</span>
          </div>
          <div className="team-crest crest-northbridge">
            <span>NBU</span>
          </div>
        </div>
      </div>

      <div className="possession-gauge-wrap" title="Current-window controlled possession; dead-ball time excluded">
        <div className="gauge-label-left">HFC {seconds ? `${possessionH.toFixed(0)}%` : "—"}</div>
        <div className="gauge-track">
          <div className="gauge-fill-h" style={{ width: `${possessionH}%` }} />
          <div className="gauge-fill-n" style={{ width: `${100 - possessionH}%` }} />
        </div>
        <div className="gauge-label-right">{seconds ? `${(100 - possessionH).toFixed(0)}%` : "—"} NBU</div>
      </div>
    </section>
  );
}

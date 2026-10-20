"use client";

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

type MatchStageProps = {
  events: FootballEvent[];
  selectedEvent: FootballEvent | null;
  ball: [number, number];
  players: Record<string, Record<string, string>>;
  clockText: string;
  onSelectEvent?: (eventId: string) => void;
};

export function MatchStage({
  events,
  selectedEvent,
  ball,
  players,
  clockText,
}: MatchStageProps) {
  const recent = selectedEvent
    ? [selectedEvent]
    : events.filter((e) => e.kind === "pass" || e.kind === "shot" || e.kind === "recovery").slice(-6);

  const activeBallPoint = selectedEvent ? selectedEvent.end : ball;
  const currentAction = selectedEvent || events.at(-1);
  const actionTime = currentAction ? `${Math.floor(currentAction.t / 60).toString().padStart(2, "0")}:${(currentAction.t % 60).toString().padStart(2, "0")}` : clockText;

  return (
    <div className="match-stage" aria-label="Interactive Tactical Pitch Stage">
      <div className="stage-header">
        <div className="stage-title-wrap">
          <span className="live-camera-tag">TACTICAL RADAR</span>
          <h2 className="stage-title">
            {selectedEvent ? `Inspecting Event · ${selectedEvent.id}` : "Live On-Ball Action Map"}
          </h2>
        </div>
        <div className="stage-direction">
          <span className="team-h-dot">●</span> Harbor Attacks <b>→</b>
        </div>
      </div>

      <div className="pitch-canvas-wrapper">
        <svg
          className="tactical-pitch-svg"
          viewBox="-4 -4 113 76"
          role="img"
          aria-label={
            selectedEvent
              ? `Selected action ${selectedEvent.kind} at ${actionTime}, from (${selectedEvent.start.join(", ")}) to (${selectedEvent.end.join(", ")})`
              : "Tactical football pitch rendering real-time on-ball event paths"
          }
        >
          <defs>
            <marker
              id="arrow-harbor"
              markerWidth="4"
              markerHeight="4"
              refX="3"
              refY="2"
              orient="auto"
            >
              <path d="M0,0 L4,2 L0,4" fill="#f59e0b" />
            </marker>
            <marker
              id="arrow-northbridge"
              markerWidth="4"
              markerHeight="4"
              refX="3"
              refY="2"
              orient="auto"
            >
              <path d="M0,0 L4,2 L0,4" fill="#60a5fa" />
            </marker>
            <filter id="ball-glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="1.5" />
            </filter>
          </defs>

          {/* Pitch background & markings */}
          <rect
            x="0"
            y="0"
            width="105"
            height="68"
            className="pitch-turf-bg"
            rx="1.5"
          />

          {/* Field line markings */}
          <g className="field-lines" fill="none">
            {/* Outer boundary */}
            <rect x="0" y="0" width="105" height="68" />
            {/* Halfway line */}
            <path d="M52.5 0V68" />
            {/* Center circle */}
            <circle cx="52.5" cy="34" r="9.15" />
            <circle cx="52.5" cy="34" r="0.6" fill="currentColor" />

            {/* Penalty boxes */}
            <path d="M0 13.84H16.5V54.16H0" />
            <path d="M105 13.84H88.5V54.16H105" />

            {/* Goal boxes */}
            <path d="M0 24.84H5.5V43.16H0" />
            <path d="M105 24.84H99.5V43.16H105" />

            {/* Penalty spots */}
            <circle cx="11" cy="34" r="0.5" fill="currentColor" />
            <circle cx="94" cy="34" r="0.5" fill="currentColor" />

            {/* Goals */}
            <path d="M0 30.34H-2V37.66H0" className="goal-net" />
            <path d="M105 30.34H107V37.66H105" className="goal-net" />
          </g>

          {/* Attacking Entry Line (x = 70m) */}
          <path d="M70 0V68" className="tactical-entry-line" />
          <text x="71" y="66" className="tactical-entry-text">
            ENTRY LINE (70M)
          </text>

          {/* Recent/Selected Events */}
          {recent.map((e, idx) => {
            const isHarbor = e.team === "H";
            const color = isHarbor ? "#f59e0b" : "#60a5fa";
            const marker = isHarbor ? "url(#arrow-harbor)" : "url(#arrow-northbridge)";
            const opacity = selectedEvent ? 1 : 0.35 + 0.12 * idx;
            const isShot = e.kind === "shot";

            return (
              <g key={e.id} opacity={opacity} className="event-vector-group">
                <line
                  x1={e.start[0]}
                  y1={e.start[1]}
                  x2={e.end[0]}
                  y2={e.end[1]}
                  stroke={color}
                  strokeWidth={selectedEvent ? 0.9 : 0.65}
                  strokeDasharray={isShot ? "1.5 1" : undefined}
                  markerEnd={marker}
                />
                <circle cx={e.start[0]} cy={e.start[1]} r="1.1" fill={color} />
              </g>
            );
          })}

          {/* Active Ball Pulse */}
          <circle
            cx={activeBallPoint[0]}
            cy={activeBallPoint[1]}
            r="3.5"
            fill="none"
            stroke="var(--turf-emerald)"
            strokeWidth="0.5"
            className="ball-sonar-ring"
          />
          <circle
            cx={activeBallPoint[0]}
            cy={activeBallPoint[1]}
            r="1.6"
            fill="#ffffff"
            stroke="#0a1926"
            strokeWidth="0.5"
          />
        </svg>
      </div>

      <div className="stage-footer">
        <div className="action-pill">
          <span className="action-dot" />
          <span className="action-text">
            {currentAction ? (
              <>
                <b>{actionTime}</b> ·{" "}
                {players[currentAction.team]?.[currentAction.actor] || currentAction.actor} ·{" "}
                <span className="action-kind">{currentAction.kind}</span>
                {currentAction.receiver && ` → ${players[currentAction.team]?.[currentAction.receiver] || currentAction.receiver}`}
                {currentAction.kind === "shot" && (
                  <span className={`outcome-badge ${currentAction.outcome}`}>
                    {currentAction.outcome.toUpperCase()}
                  </span>
                )}
              </>
            ) : (
              "Match Kick-off · Ready"
            )}
          </span>
        </div>
        <span className="stage-meta">Telemetry: On-ball coordinate sequence</span>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";

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

type TacticalData = {
  team: "H" | "N";
  team_name: string;
  attack_direction: "right" | "left";
  nodes: { player_id: string; name: string; touches: number; avg_x: number; avg_y: number }[];
  edges: { from: string; to: string; count: number; event_ids: string[] }[];
  progressive_passes: {
    id: string;
    t: number;
    actor: string;
    receiver: string;
    start: [number, number];
    end: [number, number];
    gain_m: number;
    is_entry: boolean;
  }[];
  recoveries: {
    id: string;
    t: number;
    actor: string;
    location: [number, number];
    attack_x: number;
    is_high: boolean;
  }[];
  zones: { defensive_third: number; middle_third: number; attacking_third: number };
  disclaimer: string;
};

type MatchStageProps = {
  events: FootballEvent[];
  selectedEvent: FootballEvent | null;
  selectedSequenceIds?: string[];
  ball: [number, number];
  players: Record<string, Record<string, string>>;
  clockText: string;
  focusTeam?: "H" | "N";
  tactical?: TacticalData | null;
  onSelectEvent?: (eventId: string) => void;
};

export function MatchStage({
  events,
  selectedEvent,
  selectedSequenceIds = [],
  ball,
  players,
  clockText,
  focusTeam = "H",
  tactical,
  onSelectEvent,
}: MatchStageProps) {
  const [layer, setLayer] = useState<"live" | "network" | "progression" | "recoveries">("live");

  const sequenceEvents =
    selectedSequenceIds.length > 0
      ? events.filter((e) => selectedSequenceIds.includes(e.id))
      : [];

  const recent =
    sequenceEvents.length > 0
      ? sequenceEvents
      : selectedEvent
        ? [selectedEvent]
        : events.filter((e) => e.kind === "pass" || e.kind === "shot" || e.kind === "recovery").slice(-6);

  const activeBallPoint = selectedEvent ? selectedEvent.end : ball;
  const currentAction = selectedEvent || events.at(-1);
  const actionTime = currentAction
    ? `${Math.floor(currentAction.t / 60).toString().padStart(2, "0")}:${(currentAction.t % 60).toString().padStart(2, "0")}`
    : clockText;

  const isNorthbridge = focusTeam === "N";
  const teamColor = isNorthbridge ? "#60a5fa" : "#f59e0b";
  const entryX = isNorthbridge ? 35 : 70;
  const nodeMap = new Map(tactical?.nodes.map((n) => [n.player_id, n]) || []);

  return (
    <div className="match-stage" aria-label="Interactive Tactical Pitch Stage">
      <div className="stage-header">
        <div className="stage-title-wrap">
          <span className="live-camera-tag">TACTICAL EXPLORER · {isNorthbridge ? "NORTHBRIDGE UTD" : "HARBOR FC"}</span>
          <h2 className="stage-title">
            {sequenceEvents.length > 0
              ? `Inspecting Sequence (${sequenceEvents.length} events)`
              : selectedEvent
                ? `Inspecting Event · ${selectedEvent.id}`
                : layer === "network"
                  ? `${isNorthbridge ? "Northbridge" : "Harbor"} Passing Network`
                  : layer === "progression"
                    ? "Progressive Passes & Final-Third Entries"
                    : layer === "recoveries"
                      ? "Ball Recovery Locations"
                      : "Live On-Ball Action Map"}
          </h2>
        </div>
        <div className="stage-direction">
          {isNorthbridge ? (
            <>
              <span style={{ color: "#60a5fa" }}>●</span> <b>←</b> Northbridge Attacks
            </>
          ) : (
            <>
              <span className="team-h-dot">●</span> Harbor Attacks <b>→</b>
            </>
          )}
        </div>
      </div>

      {/* Tactical Explorer Layer Switcher */}
      <div className="tactical-layer-bar" role="group" aria-label="Tactical visualization layers">
        {(
          [
            ["live", "Action & Sequences"],
            ["network", "Passing Network"],
            ["progression", `Progression (${tactical?.progressive_passes.length ?? 0})`],
            ["recoveries", `Recoveries (${tactical?.recoveries.length ?? 0})`],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={`layer-tab-btn ${layer === key ? "active" : ""}`}
            aria-pressed={layer === key}
            onClick={() => setLayer(key)}
          >
            {label}
          </button>
        ))}
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
            <marker id="arrow-harbor" markerWidth="4" markerHeight="4" refX="3" refY="2" orient="auto">
              <path d="M0,0 L4,2 L0,4" fill="#f59e0b" />
            </marker>
            <marker id="arrow-northbridge" markerWidth="4" markerHeight="4" refX="3" refY="2" orient="auto">
              <path d="M0,0 L4,2 L0,4" fill="#60a5fa" />
            </marker>
            <marker id="arrow-emerald" markerWidth="4" markerHeight="4" refX="3" refY="2" orient="auto">
              <path d="M0,0 L4,2 L0,4" fill="#00e599" />
            </marker>
          </defs>

          {/* Pitch background & markings */}
          <rect x="0" y="0" width="105" height="68" className="pitch-turf-bg" rx="1.5" />

          <g className="field-lines" fill="none">
            <rect x="0" y="0" width="105" height="68" />
            <path d="M52.5 0V68" />
            <circle cx="52.5" cy="34" r="9.15" />
            <circle cx="52.5" cy="34" r="0.6" fill="currentColor" />
            <path d="M0 13.84H16.5V54.16H0" />
            <path d="M105 13.84H88.5V54.16H105" />
            <path d="M0 24.84H5.5V43.16H0" />
            <path d="M105 24.84H99.5V43.16H105" />
            <circle cx="11" cy="34" r="0.5" fill="currentColor" />
            <circle cx="94" cy="34" r="0.5" fill="currentColor" />
            <path d="M0 30.34H-2V37.66H0" className="goal-net" />
            <path d="M105 30.34H107V37.66H105" className="goal-net" />
          </g>

          {/* Attacking Entry Line (x = 70m for Harbor, x = 35m for Northbridge) */}
          <path d={`M${entryX} 0V68`} className="tactical-entry-line" />
          <text x={entryX + 1} y="66" className="tactical-entry-text">
            {isNorthbridge ? "NBU ENTRY LINE (35M)" : "HFC ENTRY LINE (70M)"}
          </text>

          {/* Layer 1: Live Action / Highlighted Sequence */}
          {layer === "live" &&
            recent.map((e, idx) => {
              const isHarbor = e.team === "H";
              const color = isHarbor ? "#f59e0b" : "#60a5fa";
              const marker = isHarbor ? "url(#arrow-harbor)" : "url(#arrow-northbridge)";
              const opacity = selectedEvent || sequenceEvents.length > 0 ? 0.95 : 0.35 + 0.12 * idx;
              const isShot = e.kind === "shot";

              return (
                <g
                  key={e.id}
                  opacity={opacity}
                  className="event-vector-group"
                  onClick={() => onSelectEvent?.(e.id)}
                  style={{ cursor: "pointer" }}
                >
                  <line
                    x1={e.start[0]}
                    y1={e.start[1]}
                    x2={e.end[0]}
                    y2={e.end[1]}
                    stroke={color}
                    strokeWidth={selectedEvent?.id === e.id ? 1.1 : 0.7}
                    strokeDasharray={isShot ? "1.5 1" : undefined}
                    markerEnd={marker}
                  />
                  <circle cx={e.start[0]} cy={e.start[1]} r="1.15" fill={color} />
                </g>
              );
            })}

          {/* Layer 2: Passing Network (Event-Derived) */}
          {layer === "network" && tactical && (
            <g className="passing-network-layer">
              {tactical.edges.map((edge) => {
                const fromNode = nodeMap.get(edge.from);
                const toNode = nodeMap.get(edge.to);
                if (!fromNode || !toNode) return null;
                return (
                  <line
                    key={`${edge.from}-${edge.to}`}
                    x1={fromNode.avg_x}
                    y1={fromNode.avg_y}
                    x2={toNode.avg_x}
                    y2={toNode.avg_y}
                    stroke={teamColor}
                    strokeOpacity={0.65}
                    strokeWidth={Math.min(2.2, 0.35 + edge.count * 0.18)}
                    onClick={() => edge.event_ids.at(-1) && onSelectEvent?.(edge.event_ids.at(-1)!)}
                    style={{ cursor: "pointer" }}
                  />
                );
              })}
              {tactical.nodes.map((node) => (
                <g key={node.player_id} transform={`translate(${node.avg_x}, ${node.avg_y})`}>
                  <circle
                    r={Math.min(4.2, 1.8 + node.touches * 0.08)}
                    fill="#091522"
                    stroke={teamColor}
                    strokeWidth="0.65"
                  />
                  <text y="0.6" textAnchor="middle" fill="#ffffff" fontSize="1.9" fontWeight="700">
                    {node.player_id}
                  </text>
                  <text y="4.8" textAnchor="middle" fill="#cbd5e1" fontSize="1.6">
                    {node.name.split(" ")[1]} ({node.touches})
                  </text>
                </g>
              ))}
            </g>
          )}

          {/* Layer 3: Progressive Passes & Entries */}
          {layer === "progression" &&
            tactical?.progressive_passes.map((p) => (
              <g
                key={p.id}
                onClick={() => onSelectEvent?.(p.id)}
                style={{ cursor: "pointer" }}
              >
                <line
                  x1={p.start[0]}
                  y1={p.start[1]}
                  x2={p.end[0]}
                  y2={p.end[1]}
                  stroke={p.is_entry ? "#00e599" : teamColor}
                  strokeWidth={p.is_entry ? 0.9 : 0.65}
                  markerEnd={p.is_entry ? "url(#arrow-emerald)" : isNorthbridge ? "url(#arrow-northbridge)" : "url(#arrow-harbor)"}
                />
                <circle cx={p.start[0]} cy={p.start[1]} r="1.0" fill={p.is_entry ? "#00e599" : teamColor} />
              </g>
            ))}

          {/* Layer 4: Ball Recoveries */}
          {layer === "recoveries" &&
            tactical?.recoveries.map((rec) => (
              <g
                key={rec.id}
                transform={`translate(${rec.location[0]}, ${rec.location[1]})`}
                onClick={() => onSelectEvent?.(rec.id)}
                style={{ cursor: "pointer" }}
              >
                <circle
                  r={rec.is_high ? 2.4 : 1.7}
                  fill={rec.is_high ? "#00e599" : teamColor}
                  fillOpacity={0.85}
                  stroke="#071019"
                  strokeWidth="0.4"
                />
                <text y="-2.8" textAnchor="middle" fill="#f8fafc" fontSize="1.7">
                  {rec.id}
                </text>
              </g>
            ))}

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

      {/* Territorial On-Ball Zone Distribution Bar */}
      {tactical && (
        <div className="zone-distribution-strip" title={tactical.disclaimer}>
          <span>Def Third: <b>{tactical.zones.defensive_third}%</b></span>
          <span>Mid Third: <b>{tactical.zones.middle_third}%</b></span>
          <span>Final Third: <b style={{ color: "var(--turf-emerald)" }}>{tactical.zones.attacking_third}%</b></span>
          <span className="zone-disclaimer">On-ball event density only (no off-ball tracking)</span>
        </div>
      )}

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

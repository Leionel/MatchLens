"use client";

import { useState } from "react";
import { Locale, getTranslation } from "../lib/i18n";

export type FootballEvent = {
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

export type PossessionSequenceEventDetail = {
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
};

export type PossessionSequence = {
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
  events_detail?: PossessionSequenceEventDetail[];
};

export type ZoneCell = {
  cell_id: string;
  name: string;
  third: "defensive" | "middle" | "attacking";
  channel: "left" | "center" | "right";
  x_min: number;
  x_max: number;
  y_min: number;
  y_max: number;
  count: number;
  percentage: number;
  event_ids: string[];
};

export type TacticalData = {
  team: "H" | "N";
  team_name: string;
  attack_direction: "right" | "left";
  nodes: { player_id: string; name: string; touches: number; avg_x: number; avg_y: number }[];
  edges: { from: string; to: string; count: number; event_ids: string[] }[];
  progressive_passes: {
    id: string;
    t: number;
    actor: string;
    actor_name?: string;
    receiver: string;
    receiver_name?: string;
    start: [number, number];
    end: [number, number];
    gain_m: number;
    is_entry: boolean;
    channel?: string;
    entry_channel?: string | null;
  }[];
  final_third_entries?: {
    id: string;
    t: number;
    actor: string;
    receiver: string;
    gain_m: number;
  }[];
  recoveries: {
    id: string;
    t: number;
    actor: string;
    actor_name?: string;
    location: [number, number];
    attack_x: number;
    is_high: boolean;
    channel?: string;
  }[];
  zones: { defensive_third: number; middle_third: number; attacking_third: number };
  channels?: {
    left: number;
    center: number;
    right: number;
    left_count?: number;
    center_count?: number;
    right_count?: number;
  };
  attacking_channels?: {
    left: number;
    center: number;
    right: number;
    left_count?: number;
    center_count?: number;
    right_count?: number;
  };
  zone_cells?: ZoneCell[];
  territorial_progression?: {
    total_progressive_passes: number;
    final_third_entries_count: number;
    avg_progressive_gain_m: number;
    high_recoveries_count: number;
    total_recoveries_count: number;
    high_recovery_threshold_x: number;
  };
  disclaimer: string;
};

type MatchStageProps = {
  events: FootballEvent[];
  selectedEvent: FootballEvent | null;
  selectedSequence?: PossessionSequence | null;
  ball: [number, number];
  players: Record<string, Record<string, string>>;
  clockText: string;
  focusTeam?: "H" | "N";
  tactical?: TacticalData | null;
  selectedPlayerId?: string | null;
  playerSpotlight?: any[];
  selectedZoneId?: string | null;
  sequenceTraversedZones?: string[];
  locale?: Locale;
  onSelectEvent?: (eventId: string) => void;
  onClearSequence?: () => void;
  onSelectPlayer?: (playerId: string | null) => void;
  onSelectZone?: (cellId: string | null) => void;
};

export function MatchStage({
  events,
  selectedEvent,
  selectedSequence,
  ball,
  players,
  clockText,
  focusTeam = "H",
  tactical,
  selectedPlayerId,
  playerSpotlight,
  selectedZoneId,
  sequenceTraversedZones = [],
  locale = "zh",
  onSelectEvent,
  onClearSequence,
  onSelectPlayer,
  onSelectZone,
}: MatchStageProps) {
  const t = getTranslation(locale);
  const isZh = locale === "zh";

  const [layer, setLayer] = useState<"live" | "network" | "progression" | "recoveries" | "zones">("live");
  const [stepIndex, setStepIndex] = useState<number | null>(null);
  const [channelMode, setChannelMode] = useState<"overall" | "attacking">("overall");
  const [hoveredEdge, setHoveredEdge] = useState<string | null>(null);

  const isNorthbridge = focusTeam === "N";
  const teamColor = isNorthbridge ? "#60a5fa" : "#f59e0b";
  const entryX = isNorthbridge ? 35 : 70;
  const nodeMap = new Map(tactical?.nodes.map((n) => [n.player_id, n]) || []);
  const focusedPlayerData = playerSpotlight?.find((p) => p.player_id === selectedPlayerId && p.team === focusTeam);

  const sequenceDetail = selectedSequence?.events_detail || [];
  const activeStep = stepIndex !== null && sequenceDetail[stepIndex] ? sequenceDetail[stepIndex] : null;

  const currentAction = activeStep || selectedEvent || events.at(-1);
  const actionTime = currentAction
    ? `${Math.floor(currentAction.t / 60).toString().padStart(2, "0")}:${(currentAction.t % 60).toString().padStart(2, "0")}`
    : clockText;

  const activeBallPoint = activeStep ? activeStep.end : selectedEvent ? selectedEvent.end : ball;

  return (
    <div className="match-stage" aria-label="Interactive Tactical Pitch Stage">
      <div className="stage-header">
        <div className="stage-title-wrap">
          <span className="live-camera-tag">
            {isZh ? "战术球场实况" : "TACTICAL EXPLORER"} · {isNorthbridge ? "NORTHBRIDGE UTD" : "HARBOR FC"}
          </span>
          <h2 className="stage-title">
            {selectedSequence
              ? isZh
                ? `复盘序列 ${selectedSequence.sequence_id}（${sequenceDetail.length} 动作步阶 · 净增 ${selectedSequence.territory_gained ?? selectedSequence.progressive_distance}m）`
                : `Inspecting ${selectedSequence.sequence_id} (${sequenceDetail.length} steps · net ${selectedSequence.territory_gained ?? selectedSequence.progressive_distance}m)`
              : selectedPlayerId && focusedPlayerData
                ? `${t.playerSpotlightLabel} · ${focusedPlayerData.name} (${focusedPlayerData.player_id})`
                : selectedEvent
                  ? isZh ? `复盘事件 · ${selectedEvent.id}` : `Inspecting Event · ${selectedEvent.id}`
                  : layer === "network"
                    ? isZh ? `${isNorthbridge ? "Northbridge" : "Harbor"} 传球网络拓扑` : `${isNorthbridge ? "Northbridge" : "Harbor"} Passing Network`
                    : layer === "progression"
                      ? isZh ? "推进传球与进前场三区分布" : "Progressive Passes & Final-Third Entries"
                      : layer === "recoveries"
                        ? isZh ? "球权夺回位置分布" : "Ball Recovery Locations"
                        : layer === "zones"
                          ? isZh ? `${isNorthbridge ? "Northbridge" : "Harbor"} 九宫格密度热力图` : `${isNorthbridge ? "Northbridge" : "Harbor"} 9-Zone Spatial Density Map`
                          : isZh ? "实时球权与动作分布" : "Live On-Ball Action Map"}
          </h2>
        </div>
        <div className="stage-direction">
          {selectedZoneId && (
            <button
              type="button"
              className="feed-filter-btn"
              style={{ marginRight: 8, padding: "2px 8px", fontSize: 11, backgroundColor: "#00b074", color: "#ffffff" }}
              onClick={() => onSelectZone?.(null)}
              title={isZh ? "清除九宫格下钻过滤" : "Clear 9-zone drilldown filter"}
            >
              {isZh ? "区域过滤" : "Zone Filter"}: {tactical?.zone_cells?.find(c => c.cell_id === selectedZoneId)?.name || selectedZoneId} ✕
            </button>
          )}
          {selectedSequence && (
            <button
              type="button"
              className="feed-filter-btn"
              style={{ marginRight: 8, padding: "2px 8px", fontSize: 11 }}
              onClick={() => {
                setStepIndex(null);
                onClearSequence?.();
              }}
            >
              {t.exitSequenceView}
            </button>
          )}
          {isNorthbridge ? (
            <>
              <span style={{ color: "#60a5fa" }}>●</span> <b>←</b> {isZh ? "Northbridge 进攻方向" : "Northbridge Attacks"}
            </>
          ) : (
            <>
              <span className="team-h-dot">●</span> {isZh ? "Harbor 进攻方向" : "Harbor Attacks"} <b>→</b>
            </>
          )}
        </div>
      </div>

      {/* Tactical Explorer Layer Switcher */}
      <div className="tactical-layer-bar" role="group" aria-label="Tactical visualization layers">
        {(
          [
            ["live", selectedSequence ? (isZh ? `序列轨迹 (${sequenceDetail.length} 步)` : `Sequence (${sequenceDetail.length} steps)`) : t.layerLive],
            ["network", t.layerNetwork],
            ["progression", `${t.layerProgression} (${tactical?.progressive_passes.length ?? 0})`],
            ["recoveries", `${t.layerRecoveries} (${tactical?.recoveries.length ?? 0})`],
            ["zones", `${t.layerZones} (${tactical?.zone_cells?.length ?? 9})`],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={`layer-tab-btn ${layer === key ? "active" : ""}`}
            aria-pressed={layer === key}
            onClick={() => {
              setLayer(key);
              if (key !== "live") setStepIndex(null);
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Player Spotlight Focus Indicator */}
      {selectedPlayerId && focusedPlayerData && (
        <div
          className="player-focus-bar"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "6px 12px",
            background: "rgba(0, 229, 153, 0.08)",
            border: "1px solid rgba(0, 229, 153, 0.3)",
            borderRadius: 6,
            margin: "6px 0",
            fontSize: 13,
          }}
        >
          <span>
            🎯 <b>{t.playerSpotlightLabel}:</b> <b style={{ color: teamColor }}>{focusedPlayerData.name} ({focusedPlayerData.player_id})</b> · {focusedPlayerData.passes} {isZh ? "次传球" : "passes"} ({focusedPlayerData.progressive_passes} {isZh ? "推进" : "prog"}, +{focusedPlayerData.progressive_distance}m) · {focusedPlayerData.recoveries} {isZh ? "次夺回" : "rec"} · {focusedPlayerData.shots} {isZh ? "次射门" : "shots"}
          </span>
          <button
            type="button"
            className="feed-filter-btn"
            style={{ padding: "2px 8px", fontSize: 11 }}
            onClick={() => onSelectPlayer?.(null)}
          >
            {t.clearPlayerSpotlight}
          </button>
        </div>
      )}

      {/* Sequence Step-by-Step Playback Controller */}
      {selectedSequence && sequenceDetail.length > 0 && layer === "live" && (
        <div className="sequence-step-controller" role="toolbar" aria-label="Sequence step playback">
          <button
            type="button"
            className="layer-tab-btn"
            disabled={stepIndex === null || stepIndex <= 0}
            onClick={() => setStepIndex((prev) => (prev === null ? 0 : Math.max(0, prev - 1)))}
          >
            {t.stepBack}
          </button>

          <div className="step-chips-row">
            <button
              type="button"
              className={`step-chip ${stepIndex === null ? "active" : ""}`}
              onClick={() => setStepIndex(null)}
            >
              {isZh ? `全部 (${sequenceDetail.length})` : `All (${sequenceDetail.length})`}
            </button>
            {sequenceDetail.map((st, idx) => (
              <button
                key={st.id}
                type="button"
                className={`step-chip ${stepIndex === idx ? "active" : ""}`}
                onClick={() => {
                  setStepIndex(idx);
                  onSelectEvent?.(st.id);
                }}
              >
                {st.seq_step}. {st.kind}
              </button>
            ))}
          </div>

          <button
            type="button"
            className="layer-tab-btn"
            disabled={stepIndex !== null && stepIndex >= sequenceDetail.length - 1}
            onClick={() =>
              setStepIndex((prev) => (prev === null ? 0 : Math.min(sequenceDetail.length - 1, prev + 1)))
            }
          >
            {t.stepForward}
          </button>
        </div>
      )}

      <div className="pitch-canvas-wrapper">
        <svg
          className="tactical-pitch-svg"
          viewBox="-4 -4 113 76"
          role="img"
          aria-label={
            selectedEvent
              ? `Selected action ${selectedEvent.kind} at ${actionTime}`
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

          {/* Channel Guidelines (y = 22.67 and y = 45.33) */}
          <line x1="0" y1="22.67" x2="105" y2="22.67" stroke="rgba(255,255,255,0.08)" strokeDasharray="2 2" />
          <line x1="0" y1="45.33" x2="105" y2="45.33" stroke="rgba(255,255,255,0.08)" strokeDasharray="2 2" />
          <text x="3" y="11" fill="rgba(255,255,255,0.22)" fontSize="2.1" fontWeight="600">
            {isNorthbridge ? "LEFT CHANNEL" : "RIGHT CHANNEL"}
          </text>
          <text x="3" y="34.5" fill="rgba(255,255,255,0.22)" fontSize="2.1" fontWeight="600">
            CENTRAL CHANNEL
          </text>
          <text x="3" y="58" fill="rgba(255,255,255,0.22)" fontSize="2.1" fontWeight="600">
            {isNorthbridge ? "RIGHT CHANNEL" : "LEFT CHANNEL"}
          </text>

          {/* Standard Pitch Markings */}
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

          {/* Layer 1: Live Action / Selected Sequence Step Playback */}
          {layer === "live" && selectedSequence && sequenceDetail.length > 0 ? (
            <g className="sequence-vectors-layer">
              {sequenceDetail.map((st, idx) => {
                const isCurrentStep = stepIndex === null || stepIndex === idx;
                const isHarbor = selectedSequence.team === "H";
                const strokeColor = st.kind === "shot" ? "#ef4444" : isHarbor ? "#f59e0b" : "#60a5fa";
                const marker = isHarbor ? "url(#arrow-harbor)" : "url(#arrow-northbridge)";
                const opacity = isCurrentStep ? 1.0 : 0.25;

                return (
                  <g
                    key={st.id}
                    opacity={opacity}
                    style={{ cursor: "pointer" }}
                    onClick={() => {
                      setStepIndex(idx);
                      onSelectEvent?.(st.id);
                    }}
                  >
                    <line
                      x1={st.start[0]}
                      y1={st.start[1]}
                      x2={st.end[0]}
                      y2={st.end[1]}
                      stroke={strokeColor}
                      strokeWidth={isCurrentStep && stepIndex !== null ? 1.4 : 0.85}
                      strokeDasharray={st.kind === "shot" ? "1.5 1" : undefined}
                      markerEnd={marker}
                    />
                    {/* Step number badge circle */}
                    <circle cx={st.start[0]} cy={st.start[1]} r="2.0" fill="#091522" stroke={strokeColor} strokeWidth="0.5" />
                    <text
                      x={st.start[0]}
                      y={st.start[1] + 0.65}
                      textAnchor="middle"
                      fill="#ffffff"
                      fontSize="1.6"
                      fontWeight="700"
                    >
                      {st.seq_step}
                    </text>
                    {/* Progression distance badge */}
                    {isCurrentStep && st.gain_m !== 0 && (
                      <text
                        x={(st.start[0] + st.end[0]) / 2}
                        y={(st.start[1] + st.end[1]) / 2 - 1.2}
                        textAnchor="middle"
                        fill="#00e599"
                        fontSize="1.6"
                        fontWeight="700"
                      >
                        {st.gain_m > 0 ? `+${st.gain_m}m` : `${st.gain_m}m`}
                      </text>
                    )}
                  </g>
                );
              })}
            </g>
          ) : layer === "live" ? (
            events
              .filter((e) => e.kind === "pass" || e.kind === "shot" || e.kind === "recovery")
              .slice(-6)
              .map((e, idx) => {
                const isHarbor = e.team === "H";
                const color = isHarbor ? "#f59e0b" : "#60a5fa";
                const marker = isHarbor ? "url(#arrow-harbor)" : "url(#arrow-northbridge)";
                const opacity = selectedEvent?.id === e.id ? 1.0 : 0.35 + 0.12 * idx;
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
                      strokeWidth={selectedEvent?.id === e.id ? 1.2 : 0.7}
                      strokeDasharray={isShot ? "1.5 1" : undefined}
                      markerEnd={marker}
                    />
                    <circle cx={e.start[0]} cy={e.start[1]} r="1.15" fill={color} />
                  </g>
                );
              })
          ) : null}

          {/* Layer 2: Passing Network (Event-Derived) */}
          {layer === "network" && tactical && (
            <g className="passing-network-layer">
              {tactical.edges.map((edge) => {
                const fromNode = nodeMap.get(edge.from);
                const toNode = nodeMap.get(edge.to);
                if (!fromNode || !toNode) return null;
                const isEdgeHovered = hoveredEdge === `${edge.from}-${edge.to}`;
                return (
                  <g
                    key={`${edge.from}-${edge.to}`}
                    onMouseEnter={() => setHoveredEdge(`${edge.from}-${edge.to}`)}
                    onMouseLeave={() => setHoveredEdge(null)}
                    onClick={() => edge.event_ids.at(-1) && onSelectEvent?.(edge.event_ids.at(-1)!)}
                    style={{ cursor: "pointer" }}
                  >
                    <line
                      x1={fromNode.avg_x}
                      y1={fromNode.avg_y}
                      x2={toNode.avg_x}
                      y2={toNode.avg_y}
                      stroke={isEdgeHovered ? "#00e599" : teamColor}
                      strokeOpacity={isEdgeHovered ? 0.95 : 0.65}
                      strokeWidth={Math.min(2.4, 0.4 + edge.count * 0.22)}
                    />
                    {isEdgeHovered && (
                      <text
                        x={(fromNode.avg_x + toNode.avg_x) / 2}
                        y={(fromNode.avg_y + toNode.avg_y) / 2 - 1.5}
                        textAnchor="middle"
                        fill="#00e599"
                        fontSize="2.0"
                        fontWeight="700"
                      >
                        {edge.count} passes
                      </text>
                    )}
                  </g>
                );
              })}
              {tactical.nodes.map((node) => (
                <g key={node.player_id} transform={`translate(${node.avg_x}, ${node.avg_y})`}>
                  <circle
                    r={Math.min(4.4, 2.0 + node.touches * 0.09)}
                    fill="#091522"
                    stroke={teamColor}
                    strokeWidth="0.7"
                  />
                  <text y="0.6" textAnchor="middle" fill="#ffffff" fontSize="2.0" fontWeight="700">
                    {node.player_id}
                  </text>
                  <text y="4.8" textAnchor="middle" fill="#cbd5e1" fontSize="1.7">
                    {node.name.split(" ")[1]} ({node.touches})
                  </text>
                </g>
              ))}
            </g>
          )}

          {/* Layer 3: Progressive Passes & Final Third Entries */}
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
                  strokeWidth={p.is_entry ? 1.0 : 0.7}
                  markerEnd={p.is_entry ? "url(#arrow-emerald)" : isNorthbridge ? "url(#arrow-northbridge)" : "url(#arrow-harbor)"}
                />
                <circle cx={p.start[0]} cy={p.start[1]} r="1.1" fill={p.is_entry ? "#00e599" : teamColor} />
                {p.is_entry && (
                  <circle cx={p.end[0]} cy={p.end[1]} r="1.8" fill="none" stroke="#00e599" strokeWidth="0.6" />
                )}
              </g>
            ))}

          {/* Layer 4: Ball Recoveries */}
          {layer === "recoveries" && (
            <g className="recoveries-layer">
              {/* High Recovery Threshold Line */}
              <line
                x1={tactical?.territorial_progression?.high_recovery_threshold_x ?? entryX}
                y1="0"
                x2={tactical?.territorial_progression?.high_recovery_threshold_x ?? entryX}
                y2="68"
                stroke="#00e599"
                strokeWidth="0.6"
                strokeDasharray="1.5 1.5"
              />
              {tactical?.recoveries.map((rec) => (
                <g
                  key={rec.id}
                  transform={`translate(${rec.location[0]}, ${rec.location[1]})`}
                  onClick={() => onSelectEvent?.(rec.id)}
                  style={{ cursor: "pointer" }}
                >
                  <circle
                    r={rec.is_high ? 2.6 : 1.8}
                    fill={rec.is_high ? "#00e599" : teamColor}
                    fillOpacity={0.88}
                    stroke="#071019"
                    strokeWidth="0.4"
                  />
                  {rec.is_high && (
                    <circle r="3.4" fill="none" stroke="#00e599" strokeWidth="0.4" strokeDasharray="1 1" />
                  )}
                  <text y="-3.0" textAnchor="middle" fill="#f8fafc" fontSize="1.8">
                    {rec.id}
                  </text>
                </g>
              ))}
            </g>
          )}

          {/* Layer 5: 9-Zone Spatial Distribution & Density Heatmap */}
          {layer === "zones" && tactical?.zone_cells && (
            <g className="zones-grid-layer">
              {tactical.zone_cells.map((cell) => {
                const width = cell.x_max - cell.x_min;
                const height = cell.y_max - cell.y_min;
                const maxPct = Math.max(...tactical.zone_cells!.map((c) => c.percentage), 1.0);
                const opacity = Math.max(0.12, Math.min(0.70, (cell.percentage / maxPct) * 0.72));
                const isCellSelected = cell.event_ids.some((id) => selectedEvent?.id === id);
                const isZoneFiltered = selectedZoneId === cell.cell_id;
                const isTraversedBySeq = sequenceTraversedZones.includes(cell.cell_id);

                let strokeColor = "rgba(255, 255, 255, 0.28)";
                let strokeW = 0.4;
                let strokeDash: string | undefined = "1.5 1";

                if (isZoneFiltered) {
                  strokeColor = "#00e599";
                  strokeW = 1.6;
                  strokeDash = undefined;
                } else if (isTraversedBySeq) {
                  strokeColor = "#38bdf8";
                  strokeW = 1.4;
                  strokeDash = "2 1";
                } else if (isCellSelected) {
                  strokeColor = "var(--turf-emerald)";
                  strokeW = 1.0;
                  strokeDash = undefined;
                }

                return (
                  <g
                    key={cell.cell_id}
                    className="zone-cell-group"
                    style={{ cursor: "pointer" }}
                    onClick={() => {
                      onSelectZone?.(selectedZoneId === cell.cell_id ? null : cell.cell_id);
                      if (cell.event_ids.length > 0) {
                        onSelectEvent?.(cell.event_ids.at(-1)!);
                      }
                    }}
                  >
                    <rect
                      x={cell.x_min}
                      y={cell.y_min}
                      width={width}
                      height={height}
                      fill={isZoneFiltered ? "#00e599" : isTraversedBySeq ? "#0284c7" : teamColor}
                      fillOpacity={isZoneFiltered ? 0.42 : isTraversedBySeq ? 0.38 : opacity}
                      stroke={strokeColor}
                      strokeWidth={strokeW}
                      strokeDasharray={strokeDash}
                    />
                    {isTraversedBySeq && (
                      <g>
                        <rect
                          x={cell.x_min + 1.2}
                          y={cell.y_min + 1.2}
                          width="9.5"
                          height="2.8"
                          rx="0.4"
                          fill="#0284c7"
                          fillOpacity="0.9"
                        />
                        <text
                          x={cell.x_min + 5.9}
                          y={cell.y_min + 3.1}
                          textAnchor="middle"
                          fill="#ffffff"
                          fontSize="1.5"
                          fontWeight="800"
                        >
                          TRAVERSED
                        </text>
                      </g>
                    )}
                    {isZoneFiltered && (
                      <g>
                        <rect
                          x={cell.x_max - 10.7}
                          y={cell.y_min + 1.2}
                          width="9.5"
                          height="2.8"
                          rx="0.4"
                          fill="#00b074"
                        />
                        <text
                          x={cell.x_max - 5.9}
                          y={cell.y_min + 3.1}
                          textAnchor="middle"
                          fill="#ffffff"
                          fontSize="1.5"
                          fontWeight="800"
                        >
                          FILTERED
                        </text>
                      </g>
                    )}
                    <text
                      x={cell.x_min + width / 2}
                      y={cell.y_min + height / 2 - 2.5}
                      textAnchor="middle"
                      fill="#cbd5e1"
                      fontSize="1.7"
                      fontWeight="600"
                    >
                      {cell.name.toUpperCase()}
                    </text>
                    <text
                      x={cell.x_min + width / 2}
                      y={cell.y_min + height / 2 + 2.0}
                      textAnchor="middle"
                      fill="#ffffff"
                      fontSize="3.8"
                      fontWeight="800"
                    >
                      {cell.percentage}%
                    </text>
                    <text
                      x={cell.x_min + width / 2}
                      y={cell.y_min + height / 2 + 5.5}
                      textAnchor="middle"
                      fill="var(--turf-emerald)"
                      fontSize="1.6"
                      fontWeight="600"
                    >
                      {cell.count} on-ball actions
                    </text>
                  </g>
                );
              })}
            </g>
          )}

          {/* Focused Player Touch Points Radar Overlay */}
          {focusedPlayerData?.touch_points && focusedPlayerData.touch_points.length > 0 && (
            <g className="player-touch-points-layer">
              {focusedPlayerData.touch_points.map((pt: [number, number], idx: number) => (
                <g key={`touch-${idx}`} className="player-touch-marker">
                  <circle
                    cx={pt[0]}
                    cy={pt[1]}
                    r="1.8"
                    fill={teamColor}
                    fillOpacity={0.9}
                    stroke="#ffffff"
                    strokeWidth="0.5"
                  />
                  <circle
                    cx={pt[0]}
                    cy={pt[1]}
                    r="3.2"
                    fill="none"
                    stroke={teamColor}
                    strokeWidth="0.4"
                    strokeDasharray="1 1"
                  />
                </g>
              ))}
            </g>
          )}

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

      {/* Territorial & Channel Distribution Strip */}
      {tactical && (
        <div className="zone-distribution-strip" title={tactical.disclaimer}>
          <div className="zone-subgroup">
            <span style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase" }}>Thirds:</span>
            <span>Def: <b>{tactical.zones.defensive_third}%</b></span>
            <span>Mid: <b>{tactical.zones.middle_third}%</b></span>
            <span>Attacking: <b style={{ color: "var(--turf-emerald)" }}>{tactical.zones.attacking_third}%</b></span>
          </div>

          <div className="zone-subgroup">
            <button
              type="button"
              className="channel-mode-toggle"
              onClick={() => setChannelMode(channelMode === "overall" ? "attacking" : "overall")}
              title="Toggle channel distribution view"
            >
              Channels ({channelMode === "overall" ? "Pitch" : "Attacking"}):
            </button>
            {channelMode === "overall" && tactical.channels && (
              <>
                <span>L: <b>{tactical.channels.left}%</b></span>
                <span>C: <b>{tactical.channels.center}%</b></span>
                <span>R: <b>{tactical.channels.right}%</b></span>
              </>
            )}
            {channelMode === "attacking" && tactical.attacking_channels && (
              <>
                <span>L: <b>{tactical.attacking_channels.left}%</b></span>
                <span>C: <b>{tactical.attacking_channels.center}%</b></span>
                <span>R: <b>{tactical.attacking_channels.right}%</b></span>
              </>
            )}
          </div>

          {tactical.territorial_progression && (
            <div className="zone-subgroup">
              <span>Prog: <b>{tactical.territorial_progression.total_progressive_passes}</b></span>
              <span>Entries: <b style={{ color: "var(--turf-emerald)" }}>{tactical.territorial_progression.final_third_entries_count}</b></span>
              <span>High Rec: <b style={{ color: "var(--turf-emerald)" }}>{tactical.territorial_progression.high_recoveries_count}</b></span>
            </div>
          )}
        </div>
      )}

      <div className="stage-footer">
        <div className="action-pill">
          <span className="action-dot" />
          <span className="action-text">
            {activeStep ? (
              <>
                <b>Step {activeStep.seq_step} ({actionTime})</b> ·{" "}
                {activeStep.actor_name || activeStep.actor} ·{" "}
                <span className="action-kind">{activeStep.kind}</span>
                {activeStep.receiver_name && ` → ${activeStep.receiver_name}`}
                {activeStep.gain_m !== 0 && ` (${activeStep.gain_m > 0 ? `+${activeStep.gain_m}m` : `${activeStep.gain_m}m`})`}
              </>
            ) : currentAction ? (
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
        <span className="stage-meta">
          {selectedSequence ? `${selectedSequence.sequence_id} active` : "Telemetry: On-ball coordinate sequence"}
        </span>
      </div>
    </div>
  );
}

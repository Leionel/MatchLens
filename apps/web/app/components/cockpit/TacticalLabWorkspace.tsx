"use client";

import React, { useState } from "react";
import { CockpitState, PerspectiveId, InspectorPayload, PossessionSequence } from "./types";
import { Locale, getTranslation } from "../../lib/i18n";
import { MatchStage } from "../MatchStage";
import { ActionDensityDifferential } from "../ActionDensityDifferential";
import { QuickRecoveryAnalysis } from "../QuickRecoveryAnalysis";
import { MetricComparison } from "../MetricComparison";

export interface TacticalLabWorkspaceProps {
  state: CockpitState;
  perspective: PerspectiveId;
  selectedEventId: string;
  selectedSeqId: string;
  selectedPlayerId: string | null;
  selectedZoneId: string | null;
  locale?: Locale;
  onSelectEvent: (id: string) => void;
  onSelectSequence: (seqId: string) => void;
  onSelectPlayer: (pid: string | null) => void;
  onSelectZone: (zid: string | null) => void;
  onWindowChange: (newWindow: number) => void;
  onInspectReceipt: (receiptId: string) => void;
  onOpenInspector: (payload: InspectorPayload) => void;
}

const clock = (s: number) =>
  `${Math.floor(s / 60)
    .toString()
    .padStart(2, "0")}:${Math.floor(s % 60)
    .toString()
    .padStart(2, "0")}`;

export const TacticalLabWorkspace: React.FC<TacticalLabWorkspaceProps> = ({
  state,
  perspective,
  selectedEventId,
  selectedSeqId,
  selectedPlayerId,
  selectedZoneId,
  locale = "zh",
  onSelectEvent,
  onSelectSequence,
  onSelectPlayer,
  onSelectZone,
  onWindowChange,
  onInspectReceipt,
  onOpenInspector,
}) => {
  const t = getTranslation(locale);
  const isZh = locale === "zh";
  const [explorerTab, setExplorerTab] = useState<"sequences" | "players">("sequences");
  const [sequenceFilter, setSequenceFilter] = useState<
    "all" | "final_third" | "shots" | "progression" | "turnover"
  >("all");

  const clockText = clock(state.at || 0);
  const selectedEvent =
    state.events?.find((e) => e.id === selectedEventId) || null;
  const selectedSeq =
    state.sequences?.find((sq) => sq.sequence_id === selectedSeqId) || null;

  // Filter sequences for the active focus team
  const allTeamSeqs = (state.sequences || []).filter(
    (sq) => sq.team === (state.focus_team || "H")
  );
  const totalSeq = allTeamSeqs.length;
  const entriesCount = allTeamSeqs.filter((sq) => sq.entered_final_third).length;
  const entryRate = totalSeq ? Math.round((entriesCount / totalSeq) * 100) : 0;
  const avgPasses = totalSeq
    ? (allTeamSeqs.reduce((a, b) => a + b.pass_count, 0) / totalSeq).toFixed(1)
    : "0.0";
  const avgProg = totalSeq
    ? (
        allTeamSeqs.reduce(
          (a, b) => a + (b.territory_gained ?? b.progressive_distance),
          0
        ) / totalSeq
      ).toFixed(1)
    : "0.0";

  // Bidirectional drilldown filtering:
  const playerFiltered = selectedPlayerId
    ? allTeamSeqs.filter((sq) => sq.players.includes(selectedPlayerId))
    : allTeamSeqs;

  const zoneFiltered =
    selectedZoneId && state.spatial_drilldown?.zone_to_sequences
      ? playerFiltered.filter((sq) =>
          state.spatial_drilldown?.zone_to_sequences?.[selectedZoneId]?.includes(
            sq.sequence_id
          )
        )
      : playerFiltered;

  const filteredSequences = zoneFiltered.filter((sq) => {
    if (sequenceFilter === "final_third") return sq.entered_final_third;
    if (sequenceFilter === "shots")
      return (
        sq.outcome === "shot" || sq.outcome === "goal" || sq.outcome === "saved"
      );
    if (sequenceFilter === "progression")
      return (sq.territory_gained ?? sq.progressive_distance) >= 15;
    if (sequenceFilter === "turnover") return sq.outcome === "turnover";
    return true;
  });

  return (
    <div className="workspace-pane-fade" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Top Banner: Spatial & Tactical Mode Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "10px 18px",
          background: "rgba(15, 23, 42, 0.75)",
          border: "1px solid var(--glass-border)",
          borderRadius: 10,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 20 }}>🧭</span>
          <div>
            <div style={{ fontSize: 14, fontWeight: 800, color: "var(--text-primary)" }}>
              TACTICAL & SPATIAL LAB
            </div>
            <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
              Bidirectional S2/S3 Spatial Drilldown · 5 Tactical Pitch Layers · 9-Zone Density ΔD(z)
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {selectedZoneId && (
            <button
              type="button"
              onClick={() => onSelectZone(null)}
              style={{
                fontSize: 11,
                fontWeight: 700,
                padding: "4px 10px",
                borderRadius: 6,
                background: "rgba(16, 185, 129, 0.2)",
                border: "1px solid var(--turf-emerald)",
                color: "var(--turf-emerald)",
                cursor: "pointer",
              }}
            >
              Filtered to Zone {selectedZoneId} ✕
            </button>
          )}

          {selectedPlayerId && (
            <button
              type="button"
              onClick={() => onSelectPlayer(null)}
              style={{
                fontSize: 11,
                fontWeight: 700,
                padding: "4px 10px",
                borderRadius: 6,
                background: "rgba(244, 63, 94, 0.15)",
                border: "1px solid var(--crimson-warn)",
                color: "var(--crimson-warn)",
                cursor: "pointer",
              }}
            >
              Player {selectedPlayerId} ✕
            </button>
          )}

          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              padding: "4px 10px",
              borderRadius: 6,
              background: "rgba(56, 189, 248, 0.12)",
              border: "1px solid rgba(56, 189, 248, 0.3)",
              color: "var(--tech-cyan)",
            }}
          >
            {totalSeq} S2 Sequences Detected
          </span>
        </div>
      </div>

      {/* Main Grid: Left Stage (5 Layers) & Right Explorer */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1.25fr 0.75fr",
          gap: 16,
        }}
      >
        {/* Left Column: Full-featured 2D Pitch Stage */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="glass-panel" style={{ padding: 14 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 800, color: "var(--text-primary)" }}>
                  INTERACTIVE TACTICAL CANVAS
                </span>
                <span style={{ fontSize: 10, padding: "2px 6px", borderRadius: 4, background: "rgba(16, 185, 129, 0.15)", color: "var(--turf-emerald)", fontWeight: 700 }}>
                  5 LAYERS ACTIVE
                </span>
              </div>

              {selectedSeq && (
                <button
                  type="button"
                  onClick={() =>
                    onOpenInspector({
                      type: "sequence",
                      sequence: selectedSeq,
                      title: `Sequence ${selectedSeq.sequence_id} (Full Path)`,
                    })
                  }
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    padding: "3px 8px",
                    borderRadius: 6,
                    background: "rgba(56, 189, 248, 0.15)",
                    border: "1px solid rgba(56, 189, 248, 0.4)",
                    color: "var(--tech-cyan)",
                    cursor: "pointer",
                  }}
                >
                  Examine Steps in Drawer →
                </button>
              )}
            </div>

            <MatchStage
              events={state.events}
              selectedEvent={selectedEvent}
              selectedSequence={selectedSeq}
              ball={state.ball}
              players={state.players}
              clockText={clockText}
              focusTeam={state.focus_team || "H"}
              tactical={state.tactical}
              selectedPlayerId={selectedPlayerId}
              playerSpotlight={state.player_spotlight}
              selectedZoneId={selectedZoneId}
              sequenceTraversedZones={
                selectedSeqId && state.spatial_drilldown?.sequence_to_zones
                  ? state.spatial_drilldown.sequence_to_zones[selectedSeqId] || []
                  : []
              }
              onSelectEvent={(id) => onSelectEvent(id)}
              onClearSequence={() => onSelectSequence("")}
              onSelectPlayer={(pid) => onSelectPlayer(pid)}
              onSelectZone={(zid) => {
                onSelectZone(zid);
                if (zid) {
                  onOpenInspector({
                    type: "zone",
                    zoneId: zid,
                    zoneName: state.tactical?.zone_cells?.find((c: any) => c.cell_id === zid)?.name || `Zone ${zid}`,
                    title: `Zone ${zid} Spatial Audit`,
                  });
                }
              }}
            />
          </div>

          {/* Metric Comparison for Tactical Analyst */}
          <div className="glass-panel" style={{ padding: 14 }}>
            <MetricComparison
              receipts={state.analysis_receipts || state.receipts}
              at={state.snapshot_as_of ?? state.at}
              snapshotId={state.snapshot_id}
              focusTeam={state.focus_team || "H"}
              onInspect={(id) => {
                onInspectReceipt(id);
                onOpenInspector({
                  type: "receipt",
                  receiptId: id,
                  receipt: (state.analysis_receipts || state.receipts)?.[id] || null,
                  title: `Metric Receipt: ${id}`,
                });
              }}
            />
          </div>
        </div>

        {/* Right Column: S2 Sequences & Player Spotlight Explorer */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="glass-panel" style={{ padding: 14 }}>
            {/* Header with Sequences / Players Toggle */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <div>
                <span style={{ fontSize: 10, fontWeight: 800, color: "var(--turf-emerald)", textTransform: "uppercase" }}>
                  EVENT-GROUNDED EXPLORER
                </span>
                <h3 style={{ fontSize: 15, fontWeight: 750, margin: "2px 0 0" }}>
                  {explorerTab === "sequences" ? "Possession Sequences (S2)" : "Player Spotlight"}
                </h3>
              </div>

              <div style={{ display: "flex", gap: 4 }}>
                <button
                  type="button"
                  className={`feed-filter-btn ${explorerTab === "sequences" ? "active" : ""}`}
                  onClick={() => setExplorerTab("sequences")}
                  style={{ fontSize: 11, padding: "4px 8px" }}
                >
                  Sequences ({totalSeq})
                </button>
                <button
                  type="button"
                  className={`feed-filter-btn ${explorerTab === "players" ? "active" : ""}`}
                  onClick={() => setExplorerTab("players")}
                  style={{ fontSize: 11, padding: "4px 8px" }}
                >
                  Players ({(state.player_spotlight || []).filter((p) => p.team === (state.focus_team || "H")).length})
                </button>
              </div>
            </div>

            {explorerTab === "sequences" ? (
              <div>
                {/* Summary Metrics Banner */}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(4, 1fr)",
                    gap: 6,
                    padding: "8px 10px",
                    background: "rgba(15, 23, 42, 0.7)",
                    borderRadius: 6,
                    marginBottom: 10,
                    textAlign: "center",
                  }}
                >
                  <div>
                    <div style={{ fontSize: 9, color: "var(--text-tertiary)", textTransform: "uppercase" }}>Total</div>
                    <div style={{ fontSize: 14, fontWeight: 800, color: "var(--text-primary)" }}>{totalSeq}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 9, color: "var(--text-tertiary)", textTransform: "uppercase" }}>Final 3rd</div>
                    <div style={{ fontSize: 14, fontWeight: 800, color: "var(--turf-emerald)" }}>{entryRate}%</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 9, color: "var(--text-tertiary)", textTransform: "uppercase" }}>Avg Pass</div>
                    <div style={{ fontSize: 14, fontWeight: 800, color: "var(--text-primary)" }}>{avgPasses}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 9, color: "var(--text-tertiary)", textTransform: "uppercase" }}>Avg Net</div>
                    <div style={{ fontSize: 14, fontWeight: 800, color: "var(--turf-emerald)" }}>+{avgProg}m</div>
                  </div>
                </div>

                {/* Filter Pills */}
                <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 10 }}>
                  {(
                    [
                      ["all", `All (${zoneFiltered.length})`],
                      ["final_third", `Final 3rd (${zoneFiltered.filter((s) => s.entered_final_third).length})`],
                      ["shots", `Shots (${zoneFiltered.filter((s) => s.outcome === "shot" || s.outcome === "goal" || s.outcome === "saved").length})`],
                      ["progression", `Prog ≥15m (${zoneFiltered.filter((s) => (s.territory_gained ?? s.progressive_distance) >= 15).length})`],
                      ["turnover", `Turnover (${zoneFiltered.filter((s) => s.outcome === "turnover").length})`],
                    ] as const
                  ).map(([key, label]) => (
                    <button
                      key={key}
                      type="button"
                      className={`feed-filter-btn ${sequenceFilter === key ? "active" : ""}`}
                      style={{ fontSize: 11, padding: "2px 7px" }}
                      onClick={() => setSequenceFilter(key)}
                    >
                      {label}
                    </button>
                  ))}
                </div>

                {/* Scrollable Sequences */}
                <div
                  style={{
                    maxHeight: 480,
                    overflowY: "auto",
                    display: "flex",
                    flexDirection: "column",
                    gap: 6,
                  }}
                >
                  {filteredSequences.length === 0 ? (
                    <div style={{ textAlign: "center", padding: "30px 10px", color: "var(--text-tertiary)" }}>
                      <div style={{ fontSize: 20 }}>📍</div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)", marginTop: 4 }}>
                        {selectedZoneId ? "No sequences crossing this 9-zone cell" : "No sequences match filter"}
                      </div>
                      {selectedZoneId && (
                        <button
                          type="button"
                          onClick={() => onSelectZone(null)}
                          style={{
                            marginTop: 8,
                            fontSize: 11,
                            padding: "3px 8px",
                            borderRadius: 4,
                            background: "var(--turf-emerald)",
                            color: "#0b0f19",
                            fontWeight: 700,
                            border: "none",
                            cursor: "pointer",
                          }}
                        >
                          Clear Zone Filter
                        </button>
                      )}
                    </div>
                  ) : (
                    filteredSequences
                      .slice()
                      .reverse()
                      .map((sq) => {
                        const isSelected = selectedSeqId === sq.sequence_id;
                        return (
                          <div
                            key={sq.sequence_id}
                            style={{
                              border: isSelected
                                ? "1px solid var(--turf-emerald)"
                                : "1px solid var(--pitch-border)",
                              borderRadius: 6,
                              background: isSelected
                                ? "rgba(16, 185, 129, 0.08)"
                                : "rgba(15, 23, 42, 0.5)",
                              overflow: "hidden",
                            }}
                          >
                            <button
                              type="button"
                              onClick={() => {
                                onSelectSequence(isSelected ? "" : sq.sequence_id);
                                onSelectEvent(sq.event_ids.at(-1) || "");
                                if (!isSelected) {
                                  onOpenInspector({
                                    type: "sequence",
                                    sequence: sq,
                                    title: `Sequence ${sq.sequence_id}`,
                                  });
                                }
                              }}
                              style={{
                                width: "100%",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "space-between",
                                padding: "8px 10px",
                                background: "transparent",
                                border: "none",
                                cursor: "pointer",
                                textAlign: "left",
                              }}
                            >
                              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                <span className="seq-id-badge">{sq.sequence_id}</span>
                                <div>
                                  <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-primary)" }}>
                                    {clock(sq.start_t)}–{clock(sq.end_t)} ({sq.duration}s) · {sq.pass_count} passes
                                  </div>
                                  <div style={{ fontSize: 10, color: "var(--text-tertiary)" }}>
                                    Net: {sq.territory_gained !== undefined ? `${sq.territory_gained > 0 ? `+${sq.territory_gained}` : sq.territory_gained}m` : `+${sq.progressive_distance}m`}
                                    {sq.entered_final_third ? " · Final 3rd ✓" : ""}
                                  </div>
                                </div>
                              </div>

                              <span className={`seq-outcome ${sq.outcome}`}>
                                {sq.outcome.replace("_", " ").toUpperCase()}
                              </span>
                            </button>

                            {/* Step pills preview when selected */}
                            {isSelected && sq.events_detail && sq.events_detail.length > 0 && (
                              <div
                                style={{
                                  display: "flex",
                                  flexWrap: "wrap",
                                  gap: 4,
                                  padding: "6px 10px 8px",
                                  borderTop: "1px solid rgba(255, 255, 255, 0.06)",
                                  background: "rgba(11, 15, 25, 0.4)",
                                }}
                              >
                                {sq.events_detail.map((st) => (
                                  <span
                                    key={st.id}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      onSelectEvent(st.id);
                                    }}
                                    className="seq-step-pill"
                                    style={{ cursor: "pointer", fontSize: 10 }}
                                  >
                                    {st.seq_step}. {st.actor_name?.split(" ")[1] || st.actor} {st.kind}
                                    {st.gain_m !== 0 ? ` (${st.gain_m > 0 ? `+${st.gain_m}` : st.gain_m}m)` : ""}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        );
                      })
                  )}
                </div>
              </div>
            ) : (
              /* Player Spotlight List */
              <div
                style={{
                  maxHeight: 520,
                  overflowY: "auto",
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                }}
              >
                {(state.player_spotlight || [])
                  .filter((p) => p.team === (state.focus_team || "H"))
                  .map((p) => {
                    const isSelected = selectedPlayerId === p.player_id;
                    return (
                      <button
                        key={p.player_id}
                        type="button"
                        onClick={() => {
                          onSelectPlayer(isSelected ? null : p.player_id);
                          if (p.event_ids.length > 0) {
                            onSelectEvent(p.event_ids.at(-1)!);
                          }
                        }}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          padding: "8px 10px",
                          borderRadius: 6,
                          background: isSelected
                            ? "rgba(16, 185, 129, 0.12)"
                            : "rgba(15, 23, 42, 0.5)",
                          border: isSelected
                            ? "1px solid var(--turf-emerald)"
                            : "1px solid var(--pitch-border)",
                          cursor: "pointer",
                          textAlign: "left",
                        }}
                      >
                        <div>
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <span className="seq-id-badge">{p.player_id}</span>
                            <span style={{ fontSize: 12, fontWeight: 750, color: "var(--text-primary)" }}>
                              {p.name}
                            </span>
                          </div>
                          <div style={{ fontSize: 10, color: "var(--text-tertiary)", marginTop: 2 }}>
                            {p.passes} passes ({p.progressive_passes} prog, +{p.progressive_distance}m) · {p.recoveries} rec
                          </div>
                        </div>

                        <div style={{ textAlign: "right" }}>
                          <span style={{ fontSize: 11, fontWeight: 700, color: "var(--turf-emerald)" }}>
                            {p.goals > 0 ? `⚽ ${p.goals} GOAL` : `${p.shots} shots`}
                          </span>
                          <div style={{ fontSize: 10, color: "var(--text-secondary)" }}>
                            {p.sequences_involved} seqs
                          </div>
                        </div>
                      </button>
                    );
                  })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Bottom Exploration Cards: 9-Zone Density Differential & 6s Quick Recoveries */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 16,
        }}
      >
        <div className="glass-panel" style={{ padding: 14 }}>
          <ActionDensityDifferential
            data={state.density_differential}
            homeTeamName="Harbor FC"
            awayTeamName="Northbridge United"
            locale={locale}
            onSelectZone={(zid) => {
              onSelectZone(zid);
              if (zid) {
                onOpenInspector({
                  type: "zone",
                  zoneId: zid,
                  zoneName: state.tactical?.zone_cells?.find((c: any) => c.cell_id === zid)?.name || `Zone ${zid}`,
                  title: `Zone ${zid} Density Differential`,
                });
              }
            }}
            selectedZoneId={selectedZoneId}
          />
        </div>

        <div className="glass-panel" style={{ padding: 14 }}>
          <QuickRecoveryAnalysis
            data={state.quick_recoveries}
            focusTeam={state.focus_team || "H"}
            locale={locale}
            onWindowChange={onWindowChange}
            onSelectEvent={(id) => onSelectEvent(id)}
          />
        </div>
      </div>
    </div>
  );
};

"use client";

import React from "react";
import { CockpitState, PerspectiveId, InspectorPayload } from "./types";
import { Scoreboard } from "../Scoreboard";
import { OAAITimeline } from "../OAAITimeline";
import { MatchStage } from "../MatchStage";
import { EventFeed } from "../EventFeed";
import { AttackingChannelAnalysis } from "../AttackingChannelAnalysis";
import { HighlightLocator } from "../HighlightLocator";
import { Locale, getTranslation } from "../../lib/i18n";

interface MatchCenterWorkspaceProps {
  state: CockpitState;
  perspective: PerspectiveId;
  selectedEventId: string;
  selectedSeqId: string;
  selectedPlayerId: string | null;
  selectedZoneId: string | null;
  selectedHighlightId: string | null;
  selectedChannel: string | null;
  activeSmoothingMode: "causal" | "bilateral";
  locale?: Locale;
  onSeek: (t: number) => void;
  onSelectEvent: (id: string) => void;
  onSelectSequence: (seqId: string) => void;
  onSelectPlayer: (pid: string | null) => void;
  onSelectZone: (zid: string | null) => void;
  onSelectHighlight: (hl: any) => void;
  onSelectChannel: (ch: string | null) => void;
  onToggleSmoothingMode: (mode: "causal" | "bilateral") => void;
  onOpenInspector: (payload: InspectorPayload) => void;
}

const clock = (s: number) =>
  `${Math.floor(s / 60)
    .toString()
    .padStart(2, "0")}:${Math.floor(s % 60)
    .toString()
    .padStart(2, "0")}`;

export const MatchCenterWorkspace: React.FC<MatchCenterWorkspaceProps> = ({
  state,
  perspective,
  selectedEventId,
  selectedSeqId,
  selectedPlayerId,
  selectedZoneId,
  selectedHighlightId,
  selectedChannel,
  activeSmoothingMode,
  locale = "zh",
  onSeek,
  onSelectEvent,
  onSelectSequence,
  onSelectPlayer,
  onSelectZone,
  onSelectHighlight,
  onSelectChannel,
  onToggleSmoothingMode,
  onOpenInspector,
}) => {
  const t = getTranslation(locale);
  const isZh = locale === "zh";

  const clockText = clock(state.at || 0);
  const posValue = state.receipts?.["H.possession.current"]?.value ?? 50;
  const activeMoment = state.active_moment;
  const selectedEvent =
    state.events?.find((e) => e.id === selectedEventId) || null;
  const selectedSeq =
    state.sequences?.find((sq) => sq.sequence_id === selectedSeqId) || null;

  // Approximate xG based on events
  const shotsH = state.events?.filter((e) => e.team === "H" && e.kind === "shot") || [];
  const shotsN = state.events?.filter((e) => e.team === "N" && e.kind === "shot") || [];
  const xgH = (shotsH.length * 0.14).toFixed(2);
  const xgN = (shotsN.length * 0.12).toFixed(2);

  return (
    <div className="workspace-pane-fade" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* 1. Scoreboard Header Bar */}
      <div className="glass-panel" style={{ padding: 12 }}>
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
      </div>

      {/* Perspective Info Pill Banner */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "8px 16px",
          background: "rgba(15, 23, 42, 0.7)",
          border: "1px solid var(--glass-border)",
          borderRadius: 8,
          fontSize: 12,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontWeight: 800, color: "var(--turf-emerald)" }}>
            {t.workspaceMatchCenter.toUpperCase()}
          </span>
          <span style={{ color: "var(--text-tertiary)" }}>•</span>
          <span style={{ color: "var(--text-secondary)" }}>
            {isZh ? "当前视角: " : "Perspective: "}
            <b style={{ color: "var(--text-primary)", textTransform: "capitalize" }}>
              {perspective === "coach" ? t.perspectiveCoach : perspective === "media" ? t.perspectiveMedia : t.perspectiveFan}
            </b>{" "}
            {perspective === "coach"
              ? isZh ? "（聚焦通道推进率与禁区触球）" : "(Focus: Corridor Penetration & Box Entries)"
              : perspective === "media"
              ? isZh ? "（聚焦 OAAI 动量波峰与战术转折点）" : "(Focus: Momentum Waves & Turning Points)"
              : isZh ? "（聚焦核心射门与球星精彩传控）" : "(Focus: Key Shots & Star Highlights)"}
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <span style={{ color: "var(--text-secondary)" }}>
            {t.xgEstimated}: <b style={{ color: "var(--turf-emerald)" }}>{xgH}</b> -{" "}
            <b style={{ color: "var(--tech-cyan)" }}>{xgN}</b>
          </span>
          <span style={{ color: "var(--text-secondary)" }}>
            {t.possession}: <b style={{ color: "var(--turf-emerald)" }}>{posValue}%</b> -{" "}
            <b style={{ color: "var(--tech-cyan)" }}>{100 - posValue}%</b>
          </span>
          <span style={{ color: "var(--text-secondary)" }}>
            {t.eventsLogged}: <b style={{ color: "var(--text-primary)" }}>{state.events?.length || 0}</b>
          </span>
        </div>
      </div>

      {/* 2. OAAI Momentum Wave Chart (Full Width Card) */}
      <OAAITimeline
        data={state.oaai}
        currentTime={state.at}
        homeTeamName="Harbor FC"
        awayTeamName="Northbridge United"
        locale={locale}
        onSeek={(tVal) => onSeek(Math.round(tVal))}
        onSelectEvent={(eventId) => {
          onSelectEvent(eventId);
          const foundSeq = state.sequences?.find((sq) => sq.event_ids.includes(eventId));
          if (foundSeq) {
            onSelectSequence(foundSeq.sequence_id);
            onOpenInspector({
              type: "sequence",
              sequence: foundSeq,
              title: `Sequence ${foundSeq.sequence_id} (OAAI Turning Point)`,
            });
          }
        }}
        onToggleSmoothingMode={onToggleSmoothingMode}
        activeSmoothingMode={activeSmoothingMode}
      />

      {/* 3. Core Match Stage & Event Stream Split */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1.2fr 0.8fr",
          gap: 16,
        }}
      >
        {/* Left Column: 2D Pitch Stage & Corridors */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="glass-panel" style={{ padding: 14 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 800, color: "var(--text-primary)" }}>
                  {isZh ? "2D 战术球场实况" : "2D THEATER STAGE"}
                </span>
                <span style={{ fontSize: 11, padding: "2px 6px", borderRadius: 4, background: "rgba(16, 185, 129, 0.15)", color: "var(--turf-emerald)", fontWeight: 700 }}>
                  {isZh ? "实时球权与动作" : "LIVE BALL & ACTIONS"}
                </span>
              </div>

              {selectedSeq && (
                <button
                  type="button"
                  onClick={() =>
                    onOpenInspector({
                      type: "sequence",
                      sequence: selectedSeq,
                      title: `Possession Sequence ${selectedSeq.sequence_id}`,
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
                  {isZh ? `在抽屉中拆解序列 ${selectedSeq.sequence_id} →` : `Inspect ${selectedSeq.sequence_id} In Drawer →`}
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
              onSelectZone={(zid) => onSelectZone(zid)}
            />
          </div>

          {/* Attacking Channel Penetration Overview */}
          <AttackingChannelAnalysis
            data={state.attacking_channels}
            onSelectChannel={(ch) => onSelectChannel(ch)}
            selectedChannel={selectedChannel}
            locale={locale}
          />
        </div>

        {/* Right Column: Live Event Feed & Highlights */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Highlight Locator Candidates */}
          {state.highlights && state.highlights.length > 0 && (
            <HighlightLocator
              highlights={state.highlights}
              locale={locale}
              onSelectHighlight={(hl) => {
                onSelectHighlight(hl);
                onSeek(Math.round(hl.peak_t));
                if (hl.associated_sequence_ids[0]) {
                  onSelectSequence(hl.associated_sequence_ids[0]);
                  const sq = state.sequences?.find((s) => s.sequence_id === hl.associated_sequence_ids[0]);
                  if (sq) {
                    onOpenInspector({
                      type: "sequence",
                      sequence: sq,
                      title: `Highlight: ${hl.title || hl.highlight_id}`,
                    });
                  }
                }
              }}
              selectedHighlightId={selectedHighlightId}
              homeTeamName="Harbor FC"
              awayTeamName="Northbridge United"
            />
          )}

          {/* Real-time Event Feed */}
          <EventFeed
            events={state.events}
            selectedId={selectedEventId}
            players={state.players}
            locale={locale}
            onSelectEvent={(id) => {
              onSelectEvent(id);
              const foundSeq = state.sequences?.find((sq) => sq.event_ids.includes(id));
              if (foundSeq) {
                onSelectSequence(foundSeq.sequence_id);
              }
            }}
          />
        </div>
      </div>
    </div>
  );
};

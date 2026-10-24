"use client";

import React, { useMemo } from "react";
import { CockpitState, PerspectiveId, InspectorPayload } from "./types";
import { Scoreboard } from "../Scoreboard";
import { OAAITimeline, buildPeriodBands } from "../OAAITimeline";
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
  onInvestigateMoment: (payload: {
    focus_type: "oaai_point";
    focus_id: string;
    at: number;
    team: "H" | "N";
  }) => void;
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
  onInvestigateMoment,
}) => {
  const t = getTranslation(locale);
  const isZh = locale === "zh";

  const clockText = clock(state.at || 0);
  const rawPossession = state.receipts?.["H.possession.current"]?.value;
  const posValue =
    typeof rawPossession === "number" && state.receipts?.["H.possession.current"]?.status !== "unobserved"
      ? rawPossession
      : null;
  const activeMoment = state.active_moment;
  const selectedEvent =
    state.events?.find((e) => e.id === selectedEventId) || null;
  const selectedSeq =
    state.sequences?.find((sq) => sq.sequence_id === selectedSeqId) || null;

  const homeTeam = state.teams?.H || "Harbor FC";
  const awayTeam = state.teams?.N || "Northbridge United";

  // The period structure is read from the event stream, so a match that went
  // to extra time shows the extra time as its own stretch of momentum.
  const periodBands = useMemo(
    () => buildPeriodBands(state.events, isZh),
    [state.events, isZh]
  );

  // xG is shown only when a receipt actually exists. No per-shot 0.12 default.
  const receiptXgH = state.receipts?.["H.xg.cumulative"]?.value;
  const receiptXgN = state.receipts?.["N.xg.cumulative"]?.value;
  const xgH = typeof receiptXgH === "number" ? receiptXgH.toFixed(2) : "—";
  const xgN = typeof receiptXgN === "number" ? receiptXgN.toFixed(2) : "—";

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
          officialScore={state.official_score}
          teams={state.teams}
          coverage={state.coverage}
          competition={state.match_context?.competition || null}
          season={state.match_context?.season || null}
          locale={locale}
        />
      </div>

      <div className="match-quickstats" role="group" aria-label={isZh ? "核心指标" : "Key metrics"}>
        <span>
          {t.possession}{" "}
          <b>{posValue === null ? (isZh ? "未观测" : "Unknown") : `${posValue.toFixed(0)}%`}</b>
        </span>
        <span>
          {isZh ? "射门" : "Shots"}{" "}
          <b>
            {state.receipts?.["H.shots.current"]?.value ?? "—"} / {state.receipts?.["N.shots.current"]?.value ?? "—"}
          </b>
        </span>
        <span>
          {isZh ? "进球" : "Goals"}{" "}
          <b>
            {state.receipts?.["H.goals.current"]?.value ?? "—"} / {state.receipts?.["N.goals.current"]?.value ?? "—"}
          </b>
        </span>
        <span>
          {isZh ? "事件" : "Events"} <b>{state.events?.length || 0}</b>
        </span>
        {(typeof receiptXgH === "number" || typeof receiptXgN === "number") && (
          <span>
            xG <b>{xgH} / {xgN}</b>
          </span>
        )}
      </div>

      {/* 2. OAAI Momentum Wave Chart (Full Width Card) */}
      <OAAITimeline
        data={state.oaai}
        currentTime={state.at}
        homeTeamName={homeTeam}
        awayTeamName={awayTeam}
        matchDuration={state.coverage?.format_seconds}
        periods={periodBands}
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
        onInvestigateChangePoint={(cp) =>
          onInvestigateMoment({
            focus_type: "oaai_point",
            focus_id: cp.change_point_id,
            at: Math.round(cp.at),
            team: cp.leading_team === "N" ? "N" : cp.leading_team === "H" ? "H" : state.focus_team || "H",
          })
        }
      />

      {/* 3. Core Match Stage & Event Stream Split */}
      <div className="match-split-grid">
        {/* Left Column: 2D Pitch Stage & Corridors */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="glass-panel" style={{ padding: 14 }}>
            {selectedSeq && (
              <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
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
                    fontSize: 12,
                    fontWeight: 700,
                    padding: "3px 8px",
                    borderRadius: 6,
                    background: "color-mix(in srgb, var(--cyan-9) 15%, transparent)",
                    border: "0.5px solid color-mix(in srgb, var(--cyan-9) 40%, transparent)",
                    color: "var(--text-cyan)",
                    cursor: "pointer",
                  }}
                >
                  {isZh ? `在抽屉中拆解序列 ${selectedSeq.sequence_id} →` : `Inspect ${selectedSeq.sequence_id} In Drawer →`}
                </button>
              </div>
            )}

            <MatchStage
              events={state.events.filter((e) => e.start && e.end) as any}
              selectedEvent={selectedEvent as any}
              selectedSequence={selectedSeq}
              ball={state.ball}
              players={state.players}
              teamNames={state.teams}
              clockText={clockText}
              locale={locale}
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
              homeTeamName={homeTeam}
              awayTeamName={awayTeam}
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
            />
          )}

          {/* Real-time Event Feed */}
          <EventFeed
            events={state.events.filter((e) => e.start && e.end) as any}
            teamNames={state.teams}
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

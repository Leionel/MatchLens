"use client";

import React, { useMemo, useState } from "react";
import { CockpitState, PerspectiveId, InspectorPayload } from "./types";
import { Scoreboard } from "../Scoreboard";
import { OAAITimeline, buildPeriodBands } from "../OAAITimeline";
import { MatchStage } from "../MatchStage";
import { EventFeed } from "../EventFeed";
import { AttackingChannelAnalysis } from "../AttackingChannelAnalysis";
import { HighlightLocator } from "../HighlightLocator";
import { MatchRecap } from "../MatchRecap";
import { ReplayDock } from "./ReplayDock";
import { MatchInsightRail } from "./MatchInsightRail";
import { MatchKeyEvents } from "./MatchKeyEvents";
import { MobileTabs } from "./MobileTabs";
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
  busy?: boolean;
  onSeek: (t: number) => void;
  onControl: (body: object) => void;
  onSelectEvent: (id: string) => void;
  onSelectSequence: (seqId: string) => void;
  onSelectPlayer: (pid: string | null) => void;
  onSelectZone: (zid: string | null) => void;
  onSelectHighlight: (hl: any) => void;
  onSelectChannel: (ch: string | null) => void;
  onToggleSmoothingMode: (mode: "causal" | "bilateral") => void;
  onOpenInspector: (payload: InspectorPayload) => void;
  onSelectPerspective: (perspective: PerspectiveId) => void;
  onOpenIntelligence: () => void;
  onInspectReceipt: (receiptId: string, snapshotId?: string) => void;
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
  busy = false,
  onSeek,
  onControl,
  onSelectEvent,
  onSelectSequence,
  onSelectPlayer,
  onSelectZone,
  onSelectHighlight,
  onSelectChannel,
  onToggleSmoothingMode,
  onOpenInspector,
  onSelectPerspective,
  onOpenIntelligence,
  onInspectReceipt,
  onInvestigateMoment,
}) => {
  const t = getTranslation(locale);
  const isZh = locale === "zh";
  const [mobileSection, setMobileSection] = useState<"overview" | "tactical" | "events" | "more">("overview");

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
  const periodBands = useMemo(() => {
    // Provider state carries only a bounded replay window, so its events are
    // not a complete period index. The match context owns the period clock.
    const clockPeriods = state.match_context?.periods;
    if (Array.isArray(clockPeriods) && clockPeriods.length > 0) {
      const labels: Record<string, { zh: string; en: string }> = {
        first_half: { zh: "上半场", en: "1st half" },
        second_half: { zh: "下半场", en: "2nd half" },
        extra_time_1: { zh: "加时上半场", en: "ET 1" },
        extra_time_2: { zh: "加时下半场", en: "ET 2" },
        shootout: { zh: "点球大战", en: "Shoot-out" },
      };
      return clockPeriods.map((period: any) => ({
        period: Number(period.period),
        start: Number(period.observed_start ?? 0),
        end: Number(period.observed_end ?? 0),
        label:
          labels[String(period.label)]?.[isZh ? "zh" : "en"] ??
          String(period.label ?? period.period),
      }));
    }
    return buildPeriodBands(state.events, isZh);
  }, [state.match_context?.periods, state.events, isZh]);

  // xG is shown only when a receipt actually exists. No per-shot 0.12 default.
  const receiptXgH = state.receipts?.["H.xg.cumulative"]?.value;
  const receiptXgN = state.receipts?.["N.xg.cumulative"]?.value;
  const xgH = typeof receiptXgH === "number" ? receiptXgH.toFixed(2) : "—";
  const xgN = typeof receiptXgN === "number" ? receiptXgN.toFixed(2) : "—";

  return (
    <div
      className="workspace-pane-fade r6-detail-page"
      data-testid="match-detail-page"
      data-mobile-section={mobileSection}
      style={{ display: "flex", flexDirection: "column", gap: 16 }}
    >
      <header className="r6-page-head">
        <div>
          <span className="r6-kicker">{isZh ? "比赛详情" : "Match detail"}</span>
          <h1>
            {homeTeam} <span>vs</span> {awayTeam}
          </h1>
          <p>
            {state.match_context?.competition || (isZh ? "比赛" : "Match")}
            {state.match_context?.season ? ` · ${state.match_context.season}` : ""}
            {" · "}
            {isZh ? "比分、活动趋势与可按证据展开的 AI 洞察" : "Score, activity trend and evidence-led AI insight"}
          </p>
        </div>
        <div className="r6-page-actions">
          <label className="r6-perspective">
            <span>{isZh ? "叙述视角" : "Perspective"}</span>
            <select value={perspective} onChange={(event) => onSelectPerspective(event.target.value as PerspectiveId)}>
              <option value="coach">{isZh ? "教练" : "Coach"}</option>
              <option value="media">{isZh ? "转播" : "Media"}</option>
              <option value="fan">{isZh ? "球迷" : "Fan"}</option>
            </select>
          </label>
          <span className={`r6-status-pill ${state.coverage?.continuous ? "ok" : "warn"}`}>
            {state.coverage?.continuous ? (isZh ? "覆盖已验证" : "Coverage verified") : state.match_context?.completeness_status || (isZh ? "部分覆盖" : "Partial")}
          </span>
          <button type="button" className="r6-primary-action" onClick={onOpenIntelligence}>
            {isZh ? "询问这场比赛" : "Ask about this match"}
          </button>
        </div>
      </header>

      <ReplayDock state={state} busy={busy} locale={locale} onSeek={onSeek} onControl={onControl} />

      {/* 1. Scoreboard Header Bar */}
      <div className="glass-panel r6-score-shell" style={{ padding: 12 }}>
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

      <div className="match-quickstats" data-mobile-panel="overview" role="group" aria-label={isZh ? "核心指标" : "Key metrics"}>
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
        <span
          title={
            state.provider_data_boundary
              ? isZh
                ? `公开视图仅携带当前 ${state.provider_data_boundary.state_window?.window_seconds ?? 0}s 回放窗口；完整事件流需数据访问权限。`
                : `Public view carries the current ${state.provider_data_boundary.state_window?.window_seconds ?? 0}s replay window; the full event stream requires data access.`
              : undefined
          }
        >
          {isZh ? "事件" : "Events"} <b>{state.coverage?.event_count ?? state.events?.length ?? 0}</b>
        </span>
        {(typeof receiptXgH === "number" || typeof receiptXgN === "number") && (
          <span>
            xG <b>{xgH} / {xgN}</b>
          </span>
        )}
      </div>

      <MobileTabs
        tabs={[
          { id: "overview", label: isZh ? "概览" : "Overview" },
          { id: "tactical", label: isZh ? "战术" : "Tactical" },
          { id: "events", label: isZh ? "事件" : "Events", count: state.coverage?.event_count ?? state.events?.length },
          { id: "more", label: isZh ? "更多" : "More" },
        ]}
        active={mobileSection}
        onChange={setMobileSection}
        label={isZh ? "比赛详情分区" : "Match detail sections"}
      />

      <div className="r6-detail-layout">
        <div className="r6-detail-main">
      <div
        data-mobile-panel="overview"
        id="r6-panel-overview"
        role="tabpanel"
        aria-labelledby="r6-tab-overview"
      >
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

      <MatchKeyEvents
        events={state.events}
        teams={state.teams}
        locale={locale}
        onOpenAll={() => setMobileSection("events")}
        onSelectEvent={onSelectEvent}
        onSeek={onSeek}
      />
      </div>

      {/* 3. Core Match Stage & Event Stream Split */}
      <div className="match-split-grid">
        {/* Left Column: 2D Pitch Stage & Corridors */}
        <div
          data-mobile-panel="tactical"
          id="r6-panel-tactical"
          role="tabpanel"
          aria-labelledby="r6-tab-tactical"
          style={{ display: "flex", flexDirection: "column", gap: 14 }}
        >
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
                  className="mz-btn mz-btn-cyan"
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
        <div
          data-mobile-panel="events"
          id="r6-panel-events"
          role="tabpanel"
          aria-labelledby="r6-tab-events"
          style={{ display: "flex", flexDirection: "column", gap: 14 }}
        >
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

      <div
        data-mobile-panel="more"
        id="r6-panel-more"
        role="tabpanel"
        aria-labelledby="r6-tab-more"
      >
        {state.ended ? (
          <div className="r6-recap-slot">
            <MatchRecap
              score={state.score}
              homeTeam={homeTeam}
              awayTeam={awayTeam}
              history={state.history}
              locale={locale}
              onInspect={(receiptId, snapshotId) => onInspectReceipt(receiptId, snapshotId)}
            />
          </div>
        ) : (
          <div className="r6-more-empty">
            <h3>{isZh ? "完整复盘尚未生成" : "Full-time dossier not available yet"}</h3>
            <p>
              {isZh
                ? "比赛结束后会在这里展示逐条门禁结论与可回放证据；回放期间请先使用概览中的 AI 洞察和关键事件。"
                : "Gate-verified conclusions and replayable evidence appear here after full time. During replay, use the overview insight and key events first."}
            </p>
          </div>
        )}
      </div>
        </div>

        <MatchInsightRail
          state={state}
          locale={locale}
          onInvestigateChangePoint={onInvestigateMoment}
          onAsk={onOpenIntelligence}
          onSelectEvent={onSelectEvent}
          onOpenInspector={onOpenInspector}
        />
      </div>
    </div>
  );
};

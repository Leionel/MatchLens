"use client";

import React, { useId, useMemo, useState } from "react";
import { Locale, getTranslation } from "../lib/i18n";

export type OAAITimelinePoint = {
  t: number;
  home_intensity: number;
  away_intensity: number;
  oaai_raw: number;
  oaai_value: number;
  home_smoothed: number;
  away_smoothed: number;
  smoothing_mode: "causal" | "bilateral";
  causal_event_count?: number;
};

export type OAAIContributor = {
  event_id: string;
  t: number;
  team: "H" | "N" | string;
  actor: string;
  kind: string;
  outcome: string;
  contribution: number;
  magnitude: number;
  explanation: string;
};

export type OAAIChangePoint = {
  change_point_id: string;
  at: number;
  oaai_amplitude: number;
  leading_team: "H" | "N" | "neutral" | string;
  change_type: string;
  claim_level: number;
  disclaimer: string;
  window_seconds: number;
  top_contributors: OAAIContributor[];
  top_contributors_truncated?: number;
};

export type OAAIRegistryObservation = {
  metric_id: string;
  team: string;
  window: string;
  window_start_s: number;
  window_end_s: number;
  value: number | null;
  status: string;
  unit: string;
  peak_at: number | null;
  value_basis: string;
  event_ids: string[];
  event_count: number;
  metric_version: string;
  computation_version: string;
  model_version: string | null;
  coverage_status: string;
  dataset_revision: string | null;
  snapshot_id: string;
};

export type OAAIRegistryComparison = {
  metric_id: string;
  registry_comparable: boolean;
  reason: string | null;
  chart_smoothing_mode: string;
  registry_smoothing_mode: string;
  snapshot_id: string;
  snapshot_as_of: number;
  value_basis: string;
  observations: Record<string, Record<string, OAAIRegistryObservation>>;
  disclaimer: string;
};

export type OAAIData = {
  model_version: string;
  smoothing_mode: "causal" | "bilateral";
  sample_step_seconds: number;
  half_life_seconds: number;
  timeline: OAAITimelinePoint[];
  change_points: OAAIChangePoint[];
  disclaimer: string;
  registry_comparison?: OAAIRegistryComparison;
  chart_sampling?: {
    timeline_points_full: number;
    timeline_points_chart: number;
    max_points: number;
  };
};

/** A stretch of the match that belongs to one period of play. */
export type OAAIPeriodBand = {
  period: number;
  start: number;
  end: number;
  label: string;
  minuteLabel?: string;
};

type EventWithPeriod = {
  t?: number;
  period?: number;
  provider_minute?: number;
};

const PERIOD_LABELS_ZH: Record<number, string> = {
  1: "上半场",
  2: "下半场",
  3: "加时 · 上半场",
  4: "加时 · 下半场",
  5: "点球大战",
};

const PERIOD_LABELS_EN: Record<number, string> = {
  1: "First half",
  2: "Second half",
  3: "Extra time · 1st",
  4: "Extra time · 2nd",
  5: "Penalty shoot-out",
};

/**
 * The period structure of a match, read from the event stream itself.
 *
 * The provider annotates every event with the period it belongs to, so the
 * bands are evidence rather than an assumption about how long a half lasts.
 * A match that went to extra time therefore shows the extra time as its own
 * stretch of momentum instead of hiding it inside one long second half.
 */
export function buildPeriodBands(
  events: EventWithPeriod[] | undefined,
  isZh: boolean,
): OAAIPeriodBand[] {
  if (!events || events.length === 0) return [];
  const byPeriod = new Map<number, { start: number; end: number; minute: number | null }>();
  for (const event of events) {
    const t = Number(event?.t);
    if (!Number.isFinite(t)) continue;
    const period = Number.isFinite(Number(event?.period)) ? Number(event?.period) : 1;
    const minute = Number.isFinite(Number(event?.provider_minute))
      ? Number(event?.provider_minute)
      : null;
    const current = byPeriod.get(period);
    if (!current) {
      byPeriod.set(period, { start: t, end: t, minute });
    } else {
      current.start = Math.min(current.start, t);
      current.end = Math.max(current.end, t);
    }
  }
  const labels = isZh ? PERIOD_LABELS_ZH : PERIOD_LABELS_EN;
  return Array.from(byPeriod.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([period, value]) => ({
      period,
      start: value.start,
      end: value.end,
      label: labels[period] ?? (isZh ? `第 ${period} 节` : `Period ${period}`),
      minuteLabel: value.minute === null ? undefined : `${value.minute}'`,
    }));
}

/** Axis steps in minutes, coarse enough that the labels never collide. */
const AXIS_STEPS_MINUTES = [1, 2, 5, 10, 15, 20, 30, 45, 60];

function formatClock(seconds: number): string {
  const safe = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(safe / 60);
  const rest = safe % 60;
  return `${minutes}:${String(rest).padStart(2, "0")}`;
}

function pickAxisStep(durationSeconds: number, maxTicks: number): number {
  const minutes = Math.max(1, Math.round(durationSeconds / 60));
  for (const step of AXIS_STEPS_MINUTES) {
    if (minutes / step <= maxTicks) return step * 60;
  }
  return (AXIS_STEPS_MINUTES[AXIS_STEPS_MINUTES.length - 1] || 30) * 60;
}

/** How many change points may carry a label before the curve stops being readable. */
const MAX_LABELLED_CHANGE_POINTS = 6;

interface OAAITimelineProps {
  data?: OAAIData | null;
  currentTime?: number;
  homeTeamName?: string;
  awayTeamName?: string;
  /** The full length of the match, so the axis does not rescale while replaying. */
  matchDuration?: number;
  /** The period structure of the match, read from its event stream. */
  periods?: OAAIPeriodBand[];
  onSeek?: (t: number) => void;
  onSelectEvent?: (eventId: string) => void;
  onInvestigateChangePoint?: (changePoint: OAAIChangePoint) => void;
  onToggleSmoothingMode?: (mode: "causal" | "bilateral") => void;
  activeSmoothingMode?: "causal" | "bilateral";
  locale?: Locale;
}

export const OAAITimeline: React.FC<OAAITimelineProps> = ({
  data,
  currentTime = 0,
  homeTeamName = "Harbor FC",
  awayTeamName = "Northbridge United",
  matchDuration,
  periods = [],
  onSeek,
  onSelectEvent,
  onInvestigateChangePoint,
  onToggleSmoothingMode,
  activeSmoothingMode = "causal",
  locale = "zh",
}) => {
  const gradientId = useId();
  const t = getTranslation(locale);
  const isZh = locale === "zh";

  const [selectedChangePoint, setSelectedChangePoint] = useState<OAAIChangePoint | null>(null);
  const [hoverTime, setHoverTime] = useState<number | null>(null);

  const timeline = data?.timeline ?? [];
  const changePoints = data?.change_points ?? [];

  // The change points of a full match outnumber what the curve can show, so
  // every one of them is drawn on a rug below the axis and only the strongest
  // keep a label on the curve itself.
  const strongestChangePoints = useMemo(() => {
    return [...changePoints]
      .sort((a, b) => Math.abs(b.oaai_amplitude || 0) - Math.abs(a.oaai_amplitude || 0))
      .slice(0, MAX_LABELLED_CHANGE_POINTS)
      .map((cp) => cp.change_point_id);
  }, [changePoints]);
  const labelledChangePoints = new Set(strongestChangePoints);

  // Labels of clustered change points would overlap at chart scale, so each
  // labelled point takes a vertical lane on its side of the curve: the first
  // label sits closest to the curve, later ones inside ~34 units step further
  // away. The pass is deterministic (sorted by time), never animated.
  const labelledPointLayout = useMemo(() => {
    const layout = new Map<string, number>();
    const labelled = changePoints
      .filter((cp) => labelledChangePoints.has(cp.change_point_id))
      .sort((a, b) => a.at - b.at);
    let lastAboveX = -Infinity;
    let lastBelowX = -Infinity;
    let aboveSteps = 0;
    let belowSteps = 0;
    for (const cp of labelled) {
      const above = cp.leading_team !== "N";
      const base = above ? 9 : -16;
      if (above) {
        if (cp.at - lastAboveX < 46 && aboveSteps < 3) aboveSteps += 1;
        else if (cp.at - lastAboveX >= 70) aboveSteps = 0;
        layout.set(cp.change_point_id, base - aboveSteps * 11);
        lastAboveX = cp.at;
      } else {
        if (cp.at - lastBelowX < 46 && belowSteps < 3) belowSteps += 1;
        else if (cp.at - lastBelowX >= 70) belowSteps = 0;
        layout.set(cp.change_point_id, base + belowSteps * 11);
        lastBelowX = cp.at;
      }
    }
    return layout;
  }, [changePoints]);

  // Hover readout
  const hoverPoint = useMemo(() => {
    if (hoverTime === null) return null;
    let best: OAAITimelinePoint | null = null;
    let bestDistance = Number.POSITIVE_INFINITY;
    for (const point of timeline) {
      const distance = Math.abs(point.t - hoverTime);
      if (distance < bestDistance) {
        bestDistance = distance;
        best = point;
      }
    }
    return best;
  }, [hoverTime, timeline]);

  if (!data || !data.timeline || data.timeline.length === 0) {
    return (
      <div
        style={{
          background: "color-mix(in srgb, var(--slate-1) 70%, transparent)",
          border: "0.5px solid var(--glass-border)",
          borderRadius: "var(--radius-panel)",
          padding: "24px",
          textAlign: "center",
          color: "var(--text-tertiary)",
        }}
      >
        <div style={{ fontSize: 14 }}>
          {isZh ? "正在加载进攻活动指数 (OAAI) 动量曲线..." : "Loading Observed Attacking Activity Index (OAAI)..."}
        </div>
      </div>
    );
  }

  const observedEnd = timeline.length ? timeline[timeline.length - 1].t : 0;
  // The axis spans the whole match so the curve does not rescale on every
  // tick; the part that has not been observed yet stays empty.
  const axisEnd = Math.max(
    observedEnd,
    Number.isFinite(matchDuration) && Number(matchDuration) > 0 ? Number(matchDuration) : 0,
  );
  const maxT = axisEnd || Math.max(observedEnd, 720);

  const amplitudeOf = (point: OAAITimelinePoint) => Math.abs(point.oaai_value ?? point.oaai_raw ?? 0);
  const maxAmp = Math.max(
    ...timeline.map(amplitudeOf),
    ...(data.change_points || []).map((cp) => Math.abs(cp.oaai_amplitude || 0)),
    0.8
  );

  // SVG dimensions
  const svgWidth = 840;
  const svgHeight = 220;
  const padLeft = 45;
  const padRight = 20;
  const padTop = 20;
  const padBottom = 30;
  const plotWidth = svgWidth - padLeft - padRight;
  const plotHeight = svgHeight - padTop - padBottom;
  const zeroY = padTop + plotHeight / 2;

  const scaleX = (valT: number) => padLeft + (valT / maxT) * plotWidth;
  const scaleY = (val: number) => zeroY - (val / (maxAmp * 1.15)) * (plotHeight / 2);

  const points = timeline.map((pt) => ({
    x: scaleX(pt.t),
    y: scaleY(pt.oaai_value ?? pt.oaai_raw ?? 0),
  }));

  const linePath = points.reduce(
    (acc, pt, i) => `${acc} ${i === 0 ? "M" : "L"} ${pt.x.toFixed(1)} ${pt.y.toFixed(1)}`,
    ""
  );

  const areaPath = `${linePath} L ${scaleX(observedEnd)} ${zeroY} L ${scaleX(0)} ${zeroY} Z`;
  const currentX = scaleX(currentTime);

  // Current point
  const currentPoint = timeline.find((p) => Math.abs(p.t - currentTime) <= 4) || timeline[timeline.length - 1];
  const currentVal = currentPoint?.oaai_value ?? currentPoint?.oaai_raw ?? 0;
  const isCurrentHomeLead = currentVal > 0.05;
  const isCurrentAwayLead = currentVal < -0.05;

  // The change points of a full match outnumber what the curve can show, so
  // every one of them is drawn on a rug below the axis and only the strongest
  // keep a label on the curve itself.
  const hoverValue = hoverPoint?.oaai_value ?? hoverPoint?.oaai_raw ?? 0;

  // Axis ticks
  const axisStep = pickAxisStep(maxT, 12);
  const axisTicks: number[] = [];
  for (let stamp = 0; stamp <= maxT + 1; stamp += axisStep) axisTicks.push(stamp);

  // Registry consistency statement (DEF-11 / B-04). The backend publishes the
  // registry observation for the same snapshot; when the chart and the
  // registry use a different口径 the difference is stated, never hidden.
  const registry = data.registry_comparison;
  const registryHome = registry?.observations?.["H"]?.["current"];
  const registryAway = registry?.observations?.["N"]?.["current"];
  const registryText = (obs?: OAAIRegistryObservation) =>
    !obs ? "-" : obs.value === null ? (isZh ? "未观测" : "not observed") : obs.value.toFixed(4);

  const strongestChangePoint = changePoints.reduce<OAAIChangePoint | null>((best, cp) => {
    if (!best) return cp;
    return Math.abs(cp.oaai_amplitude || 0) > Math.abs(best.oaai_amplitude || 0) ? cp : best;
  }, null);

  return (
    <div
      style={{
        background: "color-mix(in srgb, var(--slate-1) 75%, transparent)",
        border: "0.5px solid var(--glass-border)",
        borderRadius: "var(--radius-panel)",
        padding: "18px 20px",
        boxShadow: "none",
        backdropFilter: "blur(12px)",
        display: "flex",
        flexDirection: "column",
        gap: "14px",
      }}
    >
      {/* Top Header Row */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <h3 style={{ fontSize: 18, fontWeight: 800, color: "var(--text-primary)", margin: 0 }}>
              {t.oaaiTitle}
            </h3>
          </div>
          <p style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 4 }}>
            {t.oaaiSubtitle}
          </p>
        </div>

        {/* Live Momentum Pill & Smoothing Mode Controls */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          {/* Live Momentum Pill */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "4px 10px",
              borderRadius: 6,
              background: isCurrentHomeLead
                ? "color-mix(in srgb, var(--green-9) 15%, transparent)"
                : isCurrentAwayLead
                ? "color-mix(in srgb, var(--cyan-9) 15%, transparent)"
                : "color-mix(in srgb, var(--slate-12) 5%, transparent)",
              border: `0.5px solid ${
                isCurrentHomeLead
                  ? "color-mix(in srgb, var(--green-9) 35%, transparent)"
                  : isCurrentAwayLead
                  ? "color-mix(in srgb, var(--cyan-9) 35%, transparent)"
                  : "color-mix(in srgb, var(--slate-12) 8%, transparent)"
              }`,
              fontSize: 12,
              fontWeight: 700,
              color: isCurrentHomeLead
                ? "var(--turf-emerald)"
                : isCurrentAwayLead
                ? "var(--tech-cyan)"
                : "var(--text-secondary)",
            }}
          >
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: isCurrentHomeLead ? "var(--turf-emerald)" : isCurrentAwayLead ? "var(--tech-cyan)" : "var(--slate-11)",
                boxShadow: isCurrentHomeLead ? "0 0 6px var(--turf-emerald)" : "none",
              }}
            />
            <span>
              {isCurrentHomeLead
                ? `${homeTeamName} +${currentVal.toFixed(2)}`
                : isCurrentAwayLead
                ? `${awayTeamName} ${currentVal.toFixed(2)}`
                : isZh
                ? "攻防平衡 (0.00)"
                : "Balanced (0.00)"}
            </span>
          </div>

          {/* Smoothing Mode Toggle */}
          <div
            style={{
              display: "flex",
              background: "var(--black-a5)",
              padding: 2,
              borderRadius: 8,
              border: "0.5px solid color-mix(in srgb, var(--slate-12) 8%, transparent)",
            }}
          >
            <button
              type="button"
              onClick={() => onToggleSmoothingMode?.("causal")}
              style={{
                minHeight: "auto",
                padding: "4px 10px",
                fontSize: 12,
                fontWeight: activeSmoothingMode === "causal" ? 700 : 500,
                borderRadius: 6,
                border: "none",
                background: activeSmoothingMode === "causal" ? "var(--turf-emerald)" : "transparent",
                color: activeSmoothingMode === "causal" ? "var(--green-3)" : "var(--text-secondary)",
                cursor: "pointer",
              }}
              title={isZh ? "因果单边滤波（仅依赖 <= t 历史事件，符合实时直播规范）" : "Causal filter (uses only past events <= t)"}
            >
              {t.causalSmoothing}
            </button>
            <button
              type="button"
              onClick={() => onToggleSmoothingMode?.("bilateral")}
              style={{
                minHeight: "auto",
                padding: "4px 10px",
                fontSize: 12,
                fontWeight: activeSmoothingMode === "bilateral" ? 700 : 500,
                borderRadius: 6,
                border: "none",
                background: activeSmoothingMode === "bilateral" ? "var(--tech-cyan)" : "transparent",
                color: activeSmoothingMode === "bilateral" ? "var(--green-3)" : "var(--text-secondary)",
                cursor: "pointer",
              }}
              title={isZh ? "赛后双边平滑（前后对称平滑核，仅限赛后复盘使用）" : "Bilateral smoothing (symmetric filter for post-match)"}
            >
              {t.bilateralSmoothing}
            </button>
          </div>
        </div>
      </div>

      {/* Match extent: how much of the match the curve actually covers */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "6px 14px",
          fontSize: 11,
          color: "var(--text-tertiary)",
          alignItems: "center",
        }}
      >
        <span data-testid="oaai-observed-span">
          {isZh ? "已观测" : "Observed"}: {formatClock(observedEnd)}
          {maxT > observedEnd + 1 ? ` / ${formatClock(maxT)}` : ""}
        </span>
        {periods.length > 0 && (
          <span data-testid="oaai-period-strip" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {periods.map((band) => (
              <span
                key={band.period}
                style={{
                  padding: "1px 7px",
                  borderRadius: 4,
                  border: "0.5px solid color-mix(in srgb, var(--slate-12) 14%, transparent)",
                  background: "color-mix(in srgb, var(--slate-12) 6%, transparent)",
                }}
              >
                {band.label}
                {band.minuteLabel ? ` (${band.minuteLabel})` : ""}
              </span>
            ))}
          </span>
        )}
        {changePoints.length > 0 && (
          <span data-testid="oaai-change-point-summary">
            {isZh
              ? `指标拐点 ${changePoints.length} 处`
              : `${changePoints.length} metric change points`}
            {strongestChangePoint
              ? ` · ${isZh ? "最强" : "strongest"} ${
                  strongestChangePoint.leading_team === "H" ? homeTeamName : strongestChangePoint.leading_team === "N" ? awayTeamName : isZh ? "中立" : "neutral"
                } ${strongestChangePoint.oaai_amplitude > 0 ? "+" : ""}${strongestChangePoint.oaai_amplitude.toFixed(2)} @ ${Math.floor(
                  strongestChangePoint.at / 60
                )}'`
              : ""}
          </span>
        )}
        {data.chart_sampling && data.chart_sampling.timeline_points_full > data.chart_sampling.timeline_points_chart && (
          <span title={isZh ? "图表按像素分辨率抽样，峰值保留；指标本身未做抽样" : "Chart samples the timeline to pixel resolution; peaks are kept, the metric is not sampled"}>
            {isZh
              ? `曲线采样 ${data.chart_sampling.timeline_points_chart}/${data.chart_sampling.timeline_points_full} 点（峰值保留）`
              : `curve ${data.chart_sampling.timeline_points_chart}/${data.chart_sampling.timeline_points_full} samples (peaks kept)`}
          </span>
        )}
      </div>

      {/* Registry consistency statement (same snapshot, same metric) */}
      {registry ? (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: 8,
            padding: "6px 10px",
            borderRadius: 6,
            fontSize: 11,
            color: "var(--text-tertiary)",
            background: registry.registry_comparable
              ? "color-mix(in srgb, var(--green-9) 8%, transparent)"
              : "color-mix(in srgb, var(--amber-9) 10%, transparent)",
            border: `0.5px solid ${
              registry.registry_comparable
                ? "color-mix(in srgb, var(--green-9) 25%, transparent)"
                : "color-mix(in srgb, var(--amber-9) 30%, transparent)"
            }`,
          }}
        >
          <span>
            {registry.registry_comparable
              ? isZh
                ? `与 Registry 同一快照口径一致（因果平滑，as_of ${registry.snapshot_as_of}s）· current 窗口：${homeTeamName} ${registryText(registryHome)} / ${awayTeamName} ${registryText(registryAway)}`
                : `Same metric as the registry for this snapshot (causal smoothing, as_of ${registry.snapshot_as_of}s) · current window: ${homeTeamName} ${registryText(registryHome)} / ${awayTeamName} ${registryText(registryAway)}`
              : isZh
              ? `与 Registry 口径不同，本图数值不可与 Registry 直接对比：${registry.reason ?? "unknown reason"}`
              : `Different definition from the registry; these chart values are not directly comparable: ${registry.reason ?? "unknown reason"}`}
          </span>
        </div>
      ) : null}

      {/* SVG Momentum Chart Container */}
      <div
        style={{
          position: "relative",
          width: "100%",
          overflow: "hidden",
          background: "var(--slate-1)",
          borderRadius: "10px",
          border: "0.5px solid color-mix(in srgb, var(--slate-12) 6%, transparent)",
          padding: "8px",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "2px 12px 0", fontSize: 11 }}>
          <span style={{ color: "var(--text-emerald)", fontWeight: 650, letterSpacing: 0.2 }}>
            {t.homeAdvantage.replace("Harbor FC", homeTeamName).replace("Northbridge United", awayTeamName)}
          </span>
          <span style={{ color: "var(--text-gold)", fontWeight: 650, letterSpacing: 0.2 }}>
            {t.awayAdvantage.replace("Northbridge United", awayTeamName).replace("Harbor FC", homeTeamName)}
          </span>
        </div>

        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          role="img"
          aria-label={
            isZh
              ? `进攻活动指数动量曲线，已观测 ${formatClock(observedEnd)}，${changePoints.length} 处指标拐点`
              : `Attacking activity momentum curve, ${formatClock(observedEnd)} observed, ${changePoints.length} metric change points`
          }
          style={{ width: "100%", height: "auto", cursor: "crosshair", userSelect: "none" }}
          onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const clickRatio = (e.clientX - rect.left - (padLeft / svgWidth) * rect.width) / ((plotWidth / svgWidth) * rect.width);
            const clickedT = Math.max(0, Math.min(maxT, clickRatio * maxT));
            onSeek?.(clickedT);
          }}
          onMouseMove={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const ratio = (e.clientX - rect.left - (padLeft / svgWidth) * rect.width) / ((plotWidth / svgWidth) * rect.width);
            setHoverTime(Math.max(0, Math.min(maxT, ratio * maxT)));
          }}
          onMouseLeave={() => setHoverTime(null)}
        >
          <defs>
            <linearGradient id={`${gradientId}-signed`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--green-9)" stopOpacity="0.35" />
              <stop offset={`${(zeroY / svgHeight) * 100 - 0.01}%`} stopColor="var(--green-9)" stopOpacity="0.08" />
              <stop offset={`${(zeroY / svgHeight) * 100 + 0.01}%`} stopColor="var(--amber-9)" stopOpacity="0.08" />
              <stop offset="100%" stopColor="var(--amber-9)" stopOpacity="0.35" />
            </linearGradient>
          </defs>

          {/* Period bands: the periods the provider annotated on the events */}
          {periods.map((band) => {
            const x0 = scaleX(band.start);
            const x1 = scaleX(band.end);
            const isLast = band.period === periods[periods.length - 1]?.period;
            return (
              <g key={band.period}>
                <rect
                  x={x0}
                  y={padTop}
                  width={Math.max(0, x1 - x0)}
                  height={plotHeight}
                  fill={band.period % 2 === 0 ? "color-mix(in srgb, var(--slate-12) 5%, transparent)" : "transparent"}
                />
                {!isLast && (
                  <line
                    x1={x1}
                    y1={padTop}
                    x2={x1}
                    y2={svgHeight - padBottom}
                    stroke="color-mix(in srgb, var(--slate-12) 22%, transparent)"
                    strokeWidth="1"
                    strokeDasharray="3 3"
                  />
                )}
                <text
                  x={x0 + 4}
                  y={padTop + 10}
                  fill="var(--text-tertiary)"
                  fontSize="9"
                  fontWeight="600"
                >
                  {band.label}
                </text>
              </g>
            );
          })}

          {/* Grid lines */}
          <line
            x1={padLeft}
            y1={zeroY}
            x2={svgWidth - padRight}
            y2={zeroY}
            stroke="color-mix(in srgb, var(--slate-12) 20%, transparent)"
            strokeWidth="1.2"
            strokeDasharray="4 4"
          />

          {/* Time axis marks */}
          {axisTicks.map((tVal) => {
            const xPos = scaleX(tVal);
            return (
              <g key={`t-mark-${tVal}`}>
                <line
                  x1={xPos}
                  y1={padTop}
                  x2={xPos}
                  y2={svgHeight - padBottom}
                  stroke="color-mix(in srgb, var(--slate-12) 6%, transparent)"
                  strokeWidth="0.8"
                />
                <text
                  x={xPos}
                  y={svgHeight - padBottom + 14}
                  fill="var(--text-tertiary)"
                  fontSize="8.5"
                  textAnchor="middle"
                  fontFamily="monospace"
                >
                  {Math.floor(tVal / 60)}'
                </text>
              </g>
            );
          })}

          {/* Y Axis labels */}
          <text x={padLeft - 8} y={padTop + 10} fill="var(--green-9)" fontSize="8.5" textAnchor="end" fontWeight="600">
            +{maxAmp.toFixed(1)}
          </text>
          <text x={padLeft - 8} y={zeroY + 3} fill="var(--slate-11)" fontSize="8.5" textAnchor="end">
            0
          </text>
          <text x={padLeft - 8} y={svgHeight - padBottom - 2} fill="var(--amber-9)" fontSize="8.5" textAnchor="end" fontWeight="600">
            -{maxAmp.toFixed(1)}
          </text>

          {/* Area fill: green above the zero line, amber below */}
          <path d={areaPath} fill={`url(#${gradientId}-signed)`} />

          {/* Wave Curve Line */}
          <path
            d={linePath}
            fill="none"
            stroke="var(--green-9)"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
          />

          {/* Change point rug: every metric change point of the match */}
          {changePoints.length > 0 && (
            <g data-testid="oaai-change-point-rug">
              {changePoints.map((cp) => {
                const rugX = scaleX(cp.at);
                const height = 4 + Math.min(10, Math.abs(cp.oaai_amplitude || 0) * 6);
                const isHome = cp.leading_team === "H";
                const isSelected = selectedChangePoint?.change_point_id === cp.change_point_id;
                return (
                  <line
                    key={cp.change_point_id}
                    x1={rugX}
                    y1={svgHeight - padBottom - height}
                    x2={rugX}
                    y2={svgHeight - padBottom}
                    stroke={isHome ? "var(--green-9)" : "var(--amber-9)"}
                    strokeWidth={isSelected ? 2.2 : 1.1}
                    opacity={isSelected ? 1 : 0.65}
                    vectorEffect="non-scaling-stroke"
                    style={{ cursor: "pointer" }}
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedChangePoint(isSelected ? null : cp);
                      onSeek?.(cp.at);
                    }}
                  >
                    <title>
                      {cp.change_point_id} · {Math.floor(cp.at / 60)}' · {(cp.oaai_amplitude > 0 ? "+" : "") + cp.oaai_amplitude.toFixed(2)}
                    </title>
                  </line>
                );
              })}
            </g>
          )}

          {/* Current playback time vertical cursor */}
          <line
            x1={currentX}
            y1={padTop - 5}
            x2={currentX}
            y2={svgHeight - padBottom + 5}
            stroke="var(--white)"
            strokeWidth="1.5"
            strokeDasharray="2 2"
          />
          <circle
            cx={currentX}
            cy={scaleY(currentVal)}
            r="4.5"
            fill="var(--white)"
            stroke="var(--green-9)"
            strokeWidth="2.5"
          />

          {/* Hover crosshair and readout */}
          {hoverPoint && hoverTime !== null && (
            <g pointerEvents="none">
              <line
                x1={scaleX(hoverPoint.t)}
                y1={padTop}
                x2={scaleX(hoverPoint.t)}
                y2={svgHeight - padBottom}
                stroke="color-mix(in srgb, var(--white) 45%, transparent)"
                strokeWidth="1"
              />
              <circle
                cx={scaleX(hoverPoint.t)}
                cy={scaleY(hoverValue)}
                r="3.5"
                fill="var(--white)"
                opacity="0.9"
              />
              <g transform={`translate(${Math.min(svgWidth - 122, Math.max(padLeft + 4, scaleX(hoverPoint.t) + 8))}, ${padTop + 4})`}>
                <rect
                  x="0"
                  y="0"
                  width="114"
                  height="34"
                  rx="7"
                  fill="color-mix(in srgb, var(--slate-2) 94%, transparent)"
                  stroke="color-mix(in srgb, var(--slate-12) 16%, transparent)"
                />
                <text x="8" y="13" fill="var(--text-tertiary)" fontSize="8" fontFamily="monospace">
                  {Math.floor(hoverPoint.t / 60)}'{String(Math.floor(hoverPoint.t % 60)).padStart(2, "0")}"
                </text>
                <text
                  x="8"
                  y="26"
                  fill={hoverValue >= 0 ? "var(--text-emerald)" : "var(--text-gold)"}
                  fontSize="9.5"
                  fontWeight="700"
                  fontFamily="monospace"
                >
                  {hoverValue >= 0 ? "+" : ""}
                  {hoverValue.toFixed(3)}
                </text>
                <text x="48" y="26" fill="var(--text-secondary)" fontSize="7.5">
                  {hoverValue > 0.05 ? homeTeamName : hoverValue < -0.05 ? awayTeamName : isZh ? "平衡" : "balanced"}
                </text>
              </g>
            </g>
          )}

          {/* Change Points / Inflection Markers: only the strongest ones are labelled */}
          {changePoints.map((cp) => {
            if (!labelledChangePoints.has(cp.change_point_id)) return null;
            const cpX = scaleX(cp.at);
            const cpY = scaleY(cp.oaai_amplitude);
            const isSelected = selectedChangePoint?.change_point_id === cp.change_point_id;
            const isHome = cp.leading_team === "H";

            return (
              <g
                key={cp.change_point_id}
                style={{ cursor: "pointer" }}
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedChangePoint(isSelected ? null : cp);
                  onSeek?.(cp.at);
                }}
              >
                <circle
                  cx={cpX}
                  cy={cpY}
                  r={isSelected ? "6" : "4"}
                  fill={isHome ? "var(--green-9)" : "var(--amber-9)"}
                  stroke="var(--slate-1)"
                  strokeWidth={isSelected ? "2" : "1.2"}
                  vectorEffect="non-scaling-stroke"
                />
                {!isSelected && (
                  <circle
                    cx={cpX}
                    cy={cpY}
                    r="8"
                    fill="none"
                    stroke={isHome ? "var(--green-9)" : "var(--amber-9)"}
                    strokeWidth="0.8"
                    strokeDasharray="2 2"
                    opacity="0.55"
                    vectorEffect="non-scaling-stroke"
                  />
                )}
                <text
                  x={cpX}
                  y={cpY - (labelledPointLayout.get(cp.change_point_id) ?? (isHome ? 9 : -16))}
                  fill={isHome ? "var(--green-9)" : "var(--amber-9)"}
                  fontSize="7.5"
                  fontWeight="700"
                  textAnchor="middle"
                  fontFamily="var(--font-mono, monospace)"
                  paintOrder="stroke"
                  stroke="var(--slate-1)"
                  strokeWidth="2.5"
                >
                  {cp.change_point_id} · {Math.floor(cp.at / 60)}'
                </text>
                <title>
                  {cp.change_point_id} · {Math.floor(cp.at / 60)}' · {(cp.oaai_amplitude > 0 ? "+" : "") + cp.oaai_amplitude.toFixed(2)}
                </title>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Level 2 Attribution Drawer when an Inflection Point is clicked */}
      {selectedChangePoint && (
        <div
          style={{
            background: "color-mix(in srgb, var(--slate-1) 90%, transparent)",
            border: "0.5px solid color-mix(in srgb, var(--green-9) 40%, transparent)",
            borderRadius: "10px",
            padding: "14px",
            display: "flex",
            flexDirection: "column",
            gap: 10,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 800,
                    color: "var(--white)",
                    background: "color-mix(in srgb, var(--green-9) 30%, transparent)",
                    padding: "2px 6px",
                    borderRadius: 4,
                    border: "0.5px solid color-mix(in srgb, var(--green-9) 50%, transparent)",
                  }}
                >
                  {selectedChangePoint.change_point_id}
                </span>
                <span style={{ fontSize: 14, fontWeight: 700, color: "var(--white)" }}>
                  {isZh
                    ? `拐点时段指标归因分析 (t = ${Math.floor(selectedChangePoint.at / 60)}分${Math.floor(selectedChangePoint.at % 60)}秒)`
                    : `Inflection Attribution Analysis (${Math.floor(selectedChangePoint.at / 60)}m ${Math.floor(selectedChangePoint.at % 60)}s)`}
                </span>
                <span style={{ fontSize: 12, color: "var(--text-emerald)", fontWeight: 700 }}>
                  {isZh ? "优势方" : "Lead"}: {selectedChangePoint.leading_team === "H" ? homeTeamName : awayTeamName} ({selectedChangePoint.oaai_amplitude > 0 ? `+${selectedChangePoint.oaai_amplitude.toFixed(2)}` : selectedChangePoint.oaai_amplitude.toFixed(2)})
                </span>
              </div>
              <p style={{ fontSize: 12, color: "var(--text-gold)", marginTop: 4 }}>
                ⚠️ {selectedChangePoint.disclaimer} ({isZh ? `回顾窗口 ${selectedChangePoint.window_seconds}s 内贡献最高的事件` : `Top contributing events in ${selectedChangePoint.window_seconds}s window`})
              </p>
            </div>

            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <button
                type="button"
                className="mz-btn mz-btn-primary"
                onClick={() => onInvestigateChangePoint?.(selectedChangePoint)}
              >
                {isZh ? "调查这个峰值" : "Investigate this peak"}
              </button>
              <button type="button" className="mz-btn" onClick={() => setSelectedChangePoint(null)}>
                {isZh ? "关闭" : "Close"}
              </button>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 8 }}>
            {selectedChangePoint.top_contributors.map((contrib, idx) => (
              <div
                key={`${contrib.event_id}-${idx}`}
                onClick={() => onSelectEvent?.(contrib.event_id)}
                className="mz-card mz-card-hover"
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "8px 12px",
                  cursor: "pointer",
                }}
              >
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ fontSize: 12, fontFamily: "monospace", fontWeight: 700, color: "var(--text-emerald)" }}>
                      #{contrib.event_id}
                    </span>
                    <span style={{ fontSize: 12, fontWeight: 700, color: "var(--white)" }}>{contrib.actor}</span>
                    <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
                      ({Math.floor(contrib.t / 60)}'{Math.floor(contrib.t % 60)}")
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 2 }}>{contrib.explanation}</div>
                </div>

                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: 12, fontWeight: 800, fontFamily: "monospace", color: "var(--text-emerald)" }}>
                    {contrib.contribution > 0 ? `+${contrib.contribution.toFixed(3)}` : contrib.contribution.toFixed(3)}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>{isZh ? "公式贡献" : "Weight"}</div>
                </div>
              </div>
            ))}
          </div>
          {selectedChangePoint.top_contributors_truncated ? (
            <p style={{ fontSize: 11, color: "var(--text-tertiary)", margin: 0 }}>
              {isZh
                ? `另有 ${selectedChangePoint.top_contributors_truncated} 个贡献事件未随图表下发，可在事件流中按时间检索。`
                : `${selectedChangePoint.top_contributors_truncated} further contributing events were not shipped with the chart; look them up in the event stream by time.`}
            </p>
          ) : null}
        </div>
      )}
    </div>
  );
};

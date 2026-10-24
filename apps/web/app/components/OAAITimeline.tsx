"use client";

import React, { useId, useState } from "react";
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
};

export type OAAIData = {
  model_version: string;
  smoothing_mode: "causal" | "bilateral";
  sample_step_seconds: number;
  half_life_seconds: number;
  timeline: OAAITimelinePoint[];
  change_points: OAAIChangePoint[];
  disclaimer: string;
};

interface OAAITimelineProps {
  data?: OAAIData | null;
  currentTime?: number;
  homeTeamName?: string;
  awayTeamName?: string;
  onSeek?: (t: number) => void;
  onSelectEvent?: (eventId: string) => void;
  onToggleSmoothingMode?: (mode: "causal" | "bilateral") => void;
  activeSmoothingMode?: "causal" | "bilateral";
  locale?: Locale;
}

export const OAAITimeline: React.FC<OAAITimelineProps> = ({
  data,
  currentTime = 0,
  homeTeamName = "Harbor FC",
  awayTeamName = "Northbridge United",
  onSeek,
  onSelectEvent,
  onToggleSmoothingMode,
  activeSmoothingMode = "causal",
  locale = "zh",
}) => {
  const gradientId = useId();
  const t = getTranslation(locale);
  const isZh = locale === "zh";

  const [selectedChangePoint, setSelectedChangePoint] = useState<OAAIChangePoint | null>(null);

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

  const timeline = data.timeline;
  const maxT = Math.max(...timeline.map((p) => p.t), 720);
  const maxAmp = Math.max(
    ...timeline.map((p) => Math.abs(p.oaai_value ?? p.oaai_raw ?? 0)),
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

  // Construct SVG points
  const points = timeline.map((pt) => ({
    x: scaleX(pt.t),
    y: scaleY(pt.oaai_value ?? pt.oaai_raw ?? 0),
  }));

  const linePath = points.reduce(
    (acc, pt, i) => `${acc} ${i === 0 ? "M" : "L"} ${pt.x.toFixed(1)} ${pt.y.toFixed(1)}`,
    ""
  );

  const areaPath = `${linePath} L ${scaleX(maxT)} ${zeroY} L ${scaleX(0)} ${zeroY} Z`;
  const currentX = scaleX(currentTime);

  // Current point
  const currentPoint = timeline.find((p) => Math.abs(p.t - currentTime) <= 4) || timeline[timeline.length - 1];
  const currentVal = currentPoint?.oaai_value ?? currentPoint?.oaai_raw ?? 0;
  const isCurrentHomeLead = currentVal > 0.05;
  const isCurrentAwayLead = currentVal < -0.05;

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
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
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
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "4px 12px", fontSize: 12 }}>
          <span style={{ color: "var(--text-emerald)", fontWeight: 700 }}>
            {t.homeAdvantage.replace("Harbor FC", homeTeamName).replace("Northbridge United", awayTeamName)}
          </span>
          <span style={{ color: "var(--text-gold)", fontWeight: 700 }}>
            {t.awayAdvantage.replace("Northbridge United", awayTeamName).replace("Harbor FC", homeTeamName)}
          </span>
        </div>

        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          style={{ width: "100%", height: "auto", cursor: "crosshair", userSelect: "none" }}
          onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const clickRatio = (e.clientX - rect.left - (padLeft / svgWidth) * rect.width) / ((plotWidth / svgWidth) * rect.width);
            const clickedT = Math.max(0, Math.min(maxT, clickRatio * maxT));
            onSeek?.(clickedT);
          }}
        >
          <defs>
            <linearGradient id={`${gradientId}-home`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--green-9)" stopOpacity="0.35" />
              <stop offset="100%" stopColor="var(--green-9)" stopOpacity="0.0" />
            </linearGradient>
            <linearGradient id={`${gradientId}-away`} x1="0" y1="1" x2="0" y2="0">
              <stop offset="0%" stopColor="var(--amber-9)" stopOpacity="0.35" />
              <stop offset="100%" stopColor="var(--amber-9)" stopOpacity="0.0" />
            </linearGradient>
          </defs>

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
          {Array.from({ length: Math.floor(maxT / 120) + 1 }).map((_, idx) => {
            const tVal = idx * 120;
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
                  y={svgHeight - padBottom + 16}
                  fill="var(--text-tertiary)"
                  fontSize="12"
                  textAnchor="middle"
                  fontFamily="monospace"
                >
                  {Math.floor(tVal / 60)}'
                </text>
              </g>
            );
          })}

          {/* Y Axis labels */}
          <text x={padLeft - 8} y={padTop + 10} fill="var(--green-9)" fontSize="12" textAnchor="end" fontWeight="bold">
            +{maxAmp.toFixed(1)}
          </text>
          <text x={padLeft - 8} y={zeroY + 3} fill="var(--slate-11)" fontSize="12" textAnchor="end">
            0
          </text>
          <text x={padLeft - 8} y={svgHeight - padBottom - 2} fill="var(--amber-9)" fontSize="12" textAnchor="end" fontWeight="bold">
            -{maxAmp.toFixed(1)}
          </text>

          {/* Area fill */}
          <path d={areaPath} fill={`url(#${gradientId}-home)`} />

          {/* Wave Curve Line */}
          <path
            d={linePath}
            fill="none"
            stroke="var(--green-9)"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

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

          {/* Change Points / Inflection Markers */}
          {data.change_points.map((cp) => {
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
                  r={isSelected ? "7" : "5"}
                  fill={isHome ? "var(--green-9)" : "var(--amber-9)"}
                  stroke="var(--white)"
                  strokeWidth={isSelected ? "2.5" : "1.5"}
                />
                <circle
                  cx={cpX}
                  cy={cpY}
                  r="10"
                  fill="none"
                  stroke={isHome ? "var(--green-9)" : "var(--amber-9)"}
                  strokeWidth="1"
                  strokeDasharray="2 2"
                  opacity="0.6"
                />
                <text
                  x={cpX}
                  y={cpY - (isHome ? 9 : -16)}
                  fill="var(--slate-12)"
                  fontSize="12"
                  fontWeight="bold"
                  textAnchor="middle"
                >
                  {cp.change_point_id}
                </text>
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

            <button
              type="button"
              onClick={() => setSelectedChangePoint(null)}
              style={{
                minHeight: "auto",
                padding: "3px 8px",
                fontSize: 12,
                background: "color-mix(in srgb, var(--slate-12) 8%, transparent)",
                border: "none",
                borderRadius: 4,
                color: "var(--text-secondary)",
                cursor: "pointer",
              }}
            >
              ✕
            </button>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 8 }}>
            {selectedChangePoint.top_contributors.map((contrib, idx) => (
              <div
                key={`${contrib.event_id}-${idx}`}
                onClick={() => onSelectEvent?.(contrib.event_id)}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "8px 12px",
                  borderRadius: 6,
                  background: "color-mix(in srgb, var(--slate-1) 70%, transparent)",
                  border: "0.5px solid color-mix(in srgb, var(--slate-12) 6%, transparent)",
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
        </div>
      )}
    </div>
  );
};

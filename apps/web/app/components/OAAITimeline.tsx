"use client";

import { useId, useState } from "react";

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
}

export function OAAITimeline({
  data,
  currentTime = 0,
  homeTeamName = "Harbor FC",
  awayTeamName = "Northbridge United",
  onSeek,
  onSelectEvent,
  onToggleSmoothingMode,
  activeSmoothingMode = "causal",
}: OAAITimelineProps) {
  const gradientId = useId();
  const [selectedChangePoint, setSelectedChangePoint] = useState<OAAIChangePoint | null>(null);
  const [hoveredPoint, setHoveredPoint] = useState<OAAITimelinePoint | null>(null);

  if (!data || !data.timeline || data.timeline.length === 0) {
    return (
      <div className="oaai-card bg-[#151e2e] border border-[rgba(255,255,255,0.09)] rounded-xl p-6 text-center text-slate-400">
        <div className="animate-pulse">Loading Observed Attacking Activity Index (OAAI)...</div>
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
  const svgWidth = 800;
  const svgHeight = 220;
  const padLeft = 45;
  const padRight = 20;
  const padTop = 20;
  const padBottom = 30;
  const plotWidth = svgWidth - padLeft - padRight;
  const plotHeight = svgHeight - padTop - padBottom;
  const zeroY = padTop + plotHeight / 2;

  const scaleX = (t: number) => padLeft + (t / maxT) * plotWidth;
  const scaleY = (val: number) => zeroY - (val / (maxAmp * 1.15)) * (plotHeight / 2);

  // Construct SVG polygon / path
  const points = timeline.map((pt) => ({
    x: scaleX(pt.t),
    y: scaleY(pt.oaai_value ?? pt.oaai_raw ?? 0),
  }));

  // Build upper area path (Home advantage > 0)
  const linePath = points.reduce(
    (acc, pt, i) => `${acc} ${i === 0 ? "M" : "L"} ${pt.x.toFixed(1)} ${pt.y.toFixed(1)}`,
    ""
  );

  const areaPath = `${linePath} L ${scaleX(maxT)} ${zeroY} L ${scaleX(0)} ${zeroY} Z`;

  const currentX = scaleX(currentTime);

  return (
    <div className="oaai-container bg-[#151e2e] border border-[rgba(255,255,255,0.09)] rounded-xl p-5 shadow-lg space-y-4">
      {/* Header with Title, Mode Switcher & Disclaimers */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[rgba(255,255,255,0.08)] pb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold tracking-wider uppercase px-2 py-0.5 rounded bg-[#00b074]/20 text-[#00b074] border border-[#00b074]/30">
              BL-02 · OAAI
            </span>
            <span className="text-[10px] font-bold tracking-wider uppercase px-2 py-0.5 rounded bg-blue-500/20 text-blue-400 border border-blue-500/30">
              Level 2 指标归因
            </span>
            <h3 className="text-base font-bold text-white tracking-wide">
              Observed Attacking Activity Index (进攻活动指数)
            </h3>
          </div>
          <p className="text-xs text-slate-400 mt-1 max-w-2xl">
            自主三层架构因果聚合，度量已记录事件反映的进攻强度（非心理动量或胜率因果预测）。
          </p>
        </div>

        {/* Smoothing Mode Toggle */}
        <div className="flex items-center bg-[#0e1420] p-1 rounded-lg border border-[rgba(255,255,255,0.08)]">
          <button
            type="button"
            onClick={() => onToggleSmoothingMode?.("causal")}
            className={`px-3 py-1 rounded text-xs font-semibold transition-colors ${
              activeSmoothingMode === "causal"
                ? "bg-[#00b074] text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
            title="因果单边滤波（仅依赖 <= t 历史事件，符合实时直播规范）"
          >
            实时因果滤波 (Causal)
          </button>
          <button
            type="button"
            onClick={() => onToggleSmoothingMode?.("bilateral")}
            className={`px-3 py-1 rounded text-xs font-semibold transition-colors ${
              activeSmoothingMode === "bilateral"
                ? "bg-blue-600 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
            title="赛后双边平滑（前后对称平滑核，仅限赛后复盘使用）"
          >
            赛后双边平滑 (Bilateral)
          </button>
        </div>
      </div>

      {/* SVG Momentum Chart */}
      <div className="relative w-full overflow-hidden bg-[#0e1420] rounded-lg border border-[rgba(255,255,255,0.06)] p-2">
        <div className="flex justify-between items-center px-3 pt-1 text-[11px] font-medium text-slate-400">
          <span className="text-[#00b074] flex items-center gap-1.5 font-semibold">
            ▲ {homeTeamName} 进攻优势区 (+)
          </span>
          <span className="text-amber-400 flex items-center gap-1.5 font-semibold">
            ▼ {awayTeamName} 进攻优势区 (-)
          </span>
        </div>

        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="w-full h-auto cursor-crosshair select-none"
          onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const clickRatio = (e.clientX - rect.left - (padLeft / svgWidth) * rect.width) / ((plotWidth / svgWidth) * rect.width);
            const clickedT = Math.max(0, Math.min(maxT, clickRatio * maxT));
            onSeek?.(clickedT);
          }}
        >
          <defs>
            <linearGradient id={`${gradientId}-home`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#00b074" stopOpacity="0.45" />
              <stop offset="100%" stopColor="#00b074" stopOpacity="0.0" />
            </linearGradient>
            <linearGradient id={`${gradientId}-away`} x1="0" y1="1" x2="0" y2="0">
              <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.45" />
              <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          <line
            x1={padLeft}
            y1={zeroY}
            x2={svgWidth - padRight}
            y2={zeroY}
            stroke="rgba(255,255,255,0.25)"
            strokeWidth="1.2"
            strokeDasharray="3 3"
          />

          {/* Time axis marks (every 120s / 2min) */}
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
                  stroke="rgba(255,255,255,0.06)"
                  strokeWidth="0.8"
                />
                <text
                  x={xPos}
                  y={svgHeight - padBottom + 16}
                  fill="#64748b"
                  fontSize="10"
                  textAnchor="middle"
                  fontFamily="monospace"
                >
                  {Math.floor(tVal / 60)}'
                </text>
              </g>
            );
          })}

          {/* Y Axis labels */}
          <text x={padLeft - 8} y={padTop + 10} fill="#00b074" fontSize="10" textAnchor="end" fontWeight="bold">
            +{maxAmp.toFixed(1)}
          </text>
          <text x={padLeft - 8} y={zeroY + 3} fill="#94a3b8" fontSize="10" textAnchor="end">
            0
          </text>
          <text x={padLeft - 8} y={svgHeight - padBottom - 2} fill="#f59e0b" fontSize="10" textAnchor="end" fontWeight="bold">
            -{maxAmp.toFixed(1)}
          </text>

          {/* Area fill */}
          <path d={areaPath} fill={`url(#${gradientId}-home)`} />

          {/* Wave Curve Line */}
          <path
            d={linePath}
            fill="none"
            stroke="#00e599"
            strokeWidth="2.0"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Current playback time vertical cursor */}
          <line
            x1={currentX}
            y1={padTop - 5}
            x2={currentX}
            y2={svgHeight - padBottom + 5}
            stroke="#ffffff"
            strokeWidth="1.5"
            strokeDasharray="2 2"
          />
          <circle cx={currentX} cy={scaleY(timeline.find((p) => Math.abs(p.t - currentTime) <= 3)?.oaai_value ?? 0)} r="4" fill="#ffffff" stroke="#00e599" strokeWidth="2" />

          {/* Change Points / Inflection Markers */}
          {data.change_points.map((cp) => {
            const cpX = scaleX(cp.at);
            const cpY = scaleY(cp.oaai_amplitude);
            const isSelected = selectedChangePoint?.change_point_id === cp.change_point_id;
            const isHome = cp.leading_team === "H";

            return (
              <g
                key={cp.change_point_id}
                className="cursor-pointer transition-transform hover:scale-125"
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
                  fill={isHome ? "#00b074" : "#f59e0b"}
                  stroke="#ffffff"
                  strokeWidth={isSelected ? "2.5" : "1.5"}
                />
                <circle
                  cx={cpX}
                  cy={cpY}
                  r="10"
                  fill="none"
                  stroke={isHome ? "#00b074" : "#f59e0b"}
                  strokeWidth="1"
                  strokeDasharray="2 2"
                  className="animate-ping opacity-60"
                />
                <text
                  x={cpX}
                  y={cpY - (isHome ? 9 : -16)}
                  fill="#f8fafc"
                  fontSize="9"
                  fontWeight="bold"
                  textAnchor="middle"
                  className="bg-black/60 px-1 rounded pointer-events-none"
                >
                  {cp.change_point_id}
                </text>
              </g>
            );
          })}
        </svg>

        <div className="flex items-center justify-between text-[11px] text-slate-500 px-3 pb-1">
          <span>单击波形任意位置跳转比赛时钟 · 点击圆圈图标查看拐点归因 (Level 2)</span>
          <span>当前滤波半衰期: {data.half_life_seconds}s</span>
        </div>
      </div>

      {/* Level 2 Attribution Drawer when an Inflection Point is clicked */}
      {selectedChangePoint && (
        <div className="change-point-drawer bg-[#091522] border border-[#00b074]/40 rounded-xl p-4 shadow-xl animate-fadeIn">
          <div className="flex items-start justify-between gap-3 border-b border-[rgba(255,255,255,0.08)] pb-2 mb-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-white bg-[#00b074]/30 px-2 py-0.5 rounded border border-[#00b074]/50">
                  {selectedChangePoint.change_point_id}
                </span>
                <h4 className="text-sm font-bold text-white">
                  拐点时段指标归因分析 (t = {Math.floor(selectedChangePoint.at / 60)}分{Math.floor(selectedChangePoint.at % 60)}秒)
                </h4>
                <span className="text-[11px] text-[#00b074] font-semibold">
                  优势方: {selectedChangePoint.leading_team === "H" ? homeTeamName : awayTeamName} (峰值: {selectedChangePoint.oaai_amplitude > 0 ? `+${selectedChangePoint.oaai_amplitude.toFixed(2)}` : selectedChangePoint.oaai_amplitude.toFixed(2)})
                </span>
              </div>
              <p className="text-xs text-amber-300/80 mt-1">
                ⚠️ {selectedChangePoint.disclaimer}（回顾窗口 {selectedChangePoint.window_seconds}s 内公式贡献最高的关键事件）
              </p>
            </div>
            <button
              type="button"
              onClick={() => setSelectedChangePoint(null)}
              className="text-xs text-slate-400 hover:text-white px-2 py-1 rounded bg-slate-800"
            >
              关闭 ✕
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {selectedChangePoint.top_contributors.map((contrib, idx) => (
              <div
                key={`${contrib.event_id}-${idx}`}
                onClick={() => onSelectEvent?.(contrib.event_id)}
                className="p-2.5 rounded-lg bg-[#151e2e] border border-[rgba(255,255,255,0.07)] hover:border-[#00b074]/60 cursor-pointer transition-all flex items-center justify-between"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-bold text-[#00b074]">{contrib.event_id}</span>
                    <span className="text-xs font-bold text-white">{contrib.actor}</span>
                    <span className="text-[11px] text-slate-400">({Math.floor(contrib.t / 60)}'{Math.floor(contrib.t % 60)}")</span>
                  </div>
                  <div className="text-xs text-slate-300 mt-0.5">{contrib.explanation}</div>
                </div>
                <div className="text-right">
                  <div className="text-xs font-mono font-bold text-[#00e599]">
                    {contrib.contribution > 0 ? `+${contrib.contribution.toFixed(3)}` : contrib.contribution.toFixed(3)}
                  </div>
                  <div className="text-[10px] text-slate-400">Layer A 权重</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

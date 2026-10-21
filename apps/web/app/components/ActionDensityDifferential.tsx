"use client";

export type DifferentialZoneCell = {
  cell_id: string;
  name: string;
  x_min: number;
  x_max: number;
  y_min: number;
  y_max: number;
  home_actions_count: number;
  away_actions_count: number;
  home_action_share: number;
  away_action_share: number;
  delta_density: number;
  delta_density_pct: number;
  advantage: "home" | "away" | "neutral";
  is_high_density_overlap: boolean;
};

export type ActionDensityDifferentialData = {
  home_total_actions: number;
  away_total_actions: number;
  overlap_threshold_pct: number;
  overlap_zones_count: number;
  zones: DifferentialZoneCell[];
  disclaimer: string;
};

interface ActionDensityDifferentialProps {
  data?: ActionDensityDifferentialData | null;
  homeTeamName?: string;
  awayTeamName?: string;
  onSelectZone?: (cellId: string) => void;
  selectedZoneId?: string | null;
}

export function ActionDensityDifferential({
  data,
  homeTeamName = "Harbor FC",
  awayTeamName = "Northbridge United",
  onSelectZone,
  selectedZoneId,
}: ActionDensityDifferentialProps) {
  if (!data || !data.zones || data.zones.length === 0) {
    return (
      <div className="bg-[#151e2e] border border-[rgba(255,255,255,0.09)] rounded-xl p-5 text-slate-400">
        正在计算球队行动密度差分...
      </div>
    );
  }

  return (
    <div className="bg-[#151e2e] border border-[rgba(255,255,255,0.09)] rounded-xl p-5 shadow-lg space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[rgba(255,255,255,0.08)] pb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold tracking-wider uppercase px-2 py-0.5 rounded bg-[#00b074]/20 text-[#00b074] border border-[#00b074]/30">
              BL-04 · 行动密度差分
            </span>
            <span className="text-[10px] font-bold tracking-wider uppercase px-2 py-0.5 rounded bg-blue-500/20 text-blue-400 border border-blue-500/30">
              Level 1 观察统计
            </span>
            <h3 className="text-base font-bold text-white tracking-wide">
              Team Action Density Differential (场区行动占比差分)
            </h3>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            计算公式：ΔD(z) = n_home(z)/N_home - n_away(z)/N_away。标注高密度重叠区域。
          </p>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-3 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-[#00b074]" />
            <span className="text-slate-300 font-medium">{homeTeamName} 占优 (+)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-[#f59e0b]" />
            <span className="text-slate-300 font-medium">{awayTeamName} 占优 (-)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-xs bg-rose-500/30 text-rose-300 border border-rose-500/50 px-1 rounded font-mono font-bold">
              OVERLAP
            </span>
            <span className="text-slate-400">重叠区域 ({data.overlap_zones_count}个)</span>
          </div>
        </div>
      </div>

      {/* 9-Zone Grid Matrix */}
      <div className="grid grid-cols-3 gap-2.5">
        {data.zones.map((cell) => {
          const isSelected = selectedZoneId === cell.cell_id;
          const isHome = cell.advantage === "home";
          const isAway = cell.advantage === "away";

          let borderStyle = "border-[rgba(255,255,255,0.08)]";
          let bgStyle = "bg-[#0e1420]";

          if (isHome) {
            borderStyle = "border-[#00b074]/40";
            bgStyle = "bg-emerald-950/20";
          } else if (isAway) {
            borderStyle = "border-amber-500/40";
            bgStyle = "bg-amber-950/20";
          }

          if (isSelected) {
            borderStyle = "border-2 border-[#00e599] shadow-md shadow-[#00b074]/20 ring-1 ring-[#00e599]";
          }

          return (
            <div
              key={cell.cell_id}
              onClick={() => onSelectZone?.(cell.cell_id)}
              className={`p-3 rounded-lg border ${borderStyle} ${bgStyle} cursor-pointer hover:border-[#00b074] transition-all relative flex flex-col justify-between`}
            >
              <div className="flex items-start justify-between">
                <span className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider">
                  {cell.name}
                </span>
                {cell.is_high_density_overlap && (
                  <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-400 border border-rose-500/40 animate-pulse">
                    OVERLAP
                  </span>
                )}
              </div>

              <div className="my-2 text-center">
                <div
                  className={`text-xl font-mono font-extrabold ${
                    cell.delta_density_pct > 0
                      ? "text-[#00e599]"
                      : cell.delta_density_pct < 0
                      ? "text-amber-400"
                      : "text-slate-400"
                  }`}
                >
                  {cell.delta_density_pct > 0 ? `+${cell.delta_density_pct}%` : `${cell.delta_density_pct}%`}
                </div>
                <div className="text-[10px] text-slate-400 uppercase mt-0.5">
                  ΔD 净差分
                </div>
              </div>

              {/* Home vs Away Share Breakdown */}
              <div className="border-t border-[rgba(255,255,255,0.06)] pt-2 grid grid-cols-2 text-[10px]">
                <div>
                  <span className="text-slate-500">主: </span>
                  <span className="font-mono font-bold text-emerald-400">{cell.home_action_share}%</span>
                  <span className="text-slate-500 text-[9px]"> ({cell.home_actions_count})</span>
                </div>
                <div className="text-right">
                  <span className="text-slate-500">客: </span>
                  <span className="font-mono font-bold text-amber-400">{cell.away_action_share}%</span>
                  <span className="text-slate-500 text-[9px]"> ({cell.away_actions_count})</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Strict Disclaimer */}
      <div className="p-2.5 rounded bg-blue-950/20 border border-blue-500/30 text-[11px] text-blue-300/90 flex items-center gap-2">
        <span>ℹ️</span>
        <span>
          <b>口径约束 (BL-04)</b>：两队在球场各区域的行动占比差分；不标记真实争夺或物理对抗强度，严禁表述为 Pitch Control (控场能力)。
        </span>
      </div>
    </div>
  );
}

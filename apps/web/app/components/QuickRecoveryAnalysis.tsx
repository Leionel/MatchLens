"use client";

import { useState } from "react";

export type QuickRecoveryItem = {
  recovery_event_id: string;
  loss_event_id: string;
  loss_t: number;
  recovery_t: number;
  elapsed_seconds: number;
  actor: string;
  actor_name?: string;
  location: [number, number];
  attack_x: number;
  channel: string;
  third: string;
  is_high_recovery: boolean;
};

export type TeamRecoveryData = {
  team: string;
  team_name: string;
  window_seconds: number;
  total_possession_losses: number;
  quick_recoveries_count: number;
  quick_recovery_rate: number;
  spatial_distribution_thirds: { attacking: number; middle: number; defensive: number };
  spatial_distribution_channels: { left: number; center: number; right: number };
  recoveries: QuickRecoveryItem[];
  high_recoveries_count: number;
};

export type QuickRecoveriesData = {
  window_seconds: number;
  teams: Record<string, TeamRecoveryData>;
  disclaimer: string;
};

interface QuickRecoveryAnalysisProps {
  data?: QuickRecoveriesData | null;
  focusTeam?: string;
  onWindowChange?: (newWindow: number) => void;
  onSelectEvent?: (eventId: string) => void;
}

export function QuickRecoveryAnalysis({
  data,
  focusTeam = "H",
  onWindowChange,
  onSelectEvent,
}: QuickRecoveryAnalysisProps) {
  const [windowSec, setWindowSec] = useState<number>(data?.window_seconds ?? 6.0);
  const teamData = data?.teams?.[focusTeam] || Object.values(data?.teams || {})[0];

  if (!teamData) {
    return (
      <div className="bg-[#151e2e] border border-[rgba(255,255,255,0.09)] rounded-xl p-5 text-slate-400">
        正在统计失去球权后快速球权恢复数据...
      </div>
    );
  }

  const handleSliderChange = (val: number) => {
    setWindowSec(val);
    onWindowChange?.(val);
  };

  const thirds = teamData.spatial_distribution_thirds || { attacking: 0, middle: 0, defensive: 0 };
  const channels = teamData.spatial_distribution_channels || { left: 0, center: 0, right: 0 };
  const totalRec = Math.max(1, teamData.quick_recoveries_count);

  return (
    <div className="bg-[#151e2e] border border-[rgba(255,255,255,0.09)] rounded-xl p-5 shadow-lg space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[rgba(255,255,255,0.08)] pb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold tracking-wider uppercase px-2 py-0.5 rounded bg-[#00b074]/20 text-[#00b074] border border-[#00b074]/30">
              BL-03 · 快速球权恢复
            </span>
            <span className="text-[10px] font-bold tracking-wider uppercase px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
              Level 1 观察事实
            </span>
            <h3 className="text-base font-bold text-white tracking-wide">
              失去球权后快速恢复分析 ({teamData.team_name})
            </h3>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            统计失去球权后指定时间窗口内的球权重新夺回发生率与场区分布。
          </p>
        </div>

        {/* Window Slider */}
        <div className="flex items-center gap-2 bg-[#0e1420] px-3 py-1.5 rounded-lg border border-[rgba(255,255,255,0.08)]">
          <span className="text-xs text-slate-400">统计窗口:</span>
          <input
            type="range"
            min="3"
            max="10"
            step="0.5"
            value={windowSec}
            onChange={(e) => handleSliderChange(parseFloat(e.target.value))}
            className="w-20 accent-[#00b074] cursor-pointer"
          />
          <span className="text-xs font-mono font-bold text-[#00e599] w-8 text-right">
            {windowSec.toFixed(1)}s
          </span>
        </div>
      </div>

      {/* Metric Cards Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-[#0e1420] p-3 rounded-lg border border-[rgba(255,255,255,0.06)]">
          <div className="text-[11px] text-slate-400 uppercase font-semibold">快速恢复率 ({windowSec}s内)</div>
          <div className="text-2xl font-mono font-bold text-[#00e599] mt-1">
            {teamData.quick_recovery_rate}%
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            {teamData.quick_recoveries_count} / {teamData.total_possession_losses} 次失球
          </div>
        </div>

        <div className="bg-[#0e1420] p-3 rounded-lg border border-[rgba(255,255,255,0.06)]">
          <div className="text-[11px] text-slate-400 uppercase font-semibold">前场高位恢复</div>
          <div className="text-2xl font-mono font-bold text-emerald-400 mt-1">
            {teamData.high_recoveries_count}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            进攻三区 (ax ≥ 70m)
          </div>
        </div>

        <div className="bg-[#0e1420] p-3 rounded-lg border border-[rgba(255,255,255,0.06)]">
          <div className="text-[11px] text-slate-400 uppercase font-semibold">中场区域恢复</div>
          <div className="text-2xl font-mono font-bold text-blue-400 mt-1">
            {thirds.middle}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            占比 {Math.round((thirds.middle / totalRec) * 100)}%
          </div>
        </div>

        <div className="bg-[#0e1420] p-3 rounded-lg border border-[rgba(255,255,255,0.06)]">
          <div className="text-[11px] text-slate-400 uppercase font-semibold">后场保护恢复</div>
          <div className="text-2xl font-mono font-bold text-slate-300 mt-1">
            {thirds.defensive}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            占比 {Math.round((thirds.defensive / totalRec) * 100)}%
          </div>
        </div>
      </div>

      {/* Spatial Breakdown: Thirds & Channels */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
        {/* Longitudinal Thirds Bar */}
        <div className="bg-[#0e1420] p-3 rounded-lg border border-[rgba(255,255,255,0.06)]">
          <div className="text-xs font-semibold text-slate-300 mb-2">纵向场区分布 (Thirds)</div>
          <div className="space-y-1.5">
            <div>
              <div className="flex justify-between text-[11px] text-slate-400">
                <span>进攻三区 (Attacking)</span>
                <span className="font-mono text-emerald-400 font-bold">{thirds.attacking} 次</span>
              </div>
              <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden mt-1">
                <div
                  className="bg-[#00b074] h-full rounded-full transition-all"
                  style={{ width: `${(thirds.attacking / totalRec) * 100}%` }}
                />
              </div>
            </div>
            <div>
              <div className="flex justify-between text-[11px] text-slate-400">
                <span>中场三区 (Middle)</span>
                <span className="font-mono text-blue-400 font-bold">{thirds.middle} 次</span>
              </div>
              <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden mt-1">
                <div
                  className="bg-blue-500 h-full rounded-full transition-all"
                  style={{ width: `${(thirds.middle / totalRec) * 100}%` }}
                />
              </div>
            </div>
            <div>
              <div className="flex justify-between text-[11px] text-slate-400">
                <span>防守三区 (Defensive)</span>
                <span className="font-mono text-slate-300 font-bold">{thirds.defensive} 次</span>
              </div>
              <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden mt-1">
                <div
                  className="bg-slate-500 h-full rounded-full transition-all"
                  style={{ width: `${(thirds.defensive / totalRec) * 100}%` }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Lateral Channels Bar */}
        <div className="bg-[#0e1420] p-3 rounded-lg border border-[rgba(255,255,255,0.06)]">
          <div className="text-xs font-semibold text-slate-300 mb-2">横向通道分布 (Channels)</div>
          <div className="grid grid-cols-3 gap-2 text-center pt-2">
            <div className="bg-[#151e2e] p-2 rounded border border-[rgba(255,255,255,0.05)]">
              <div className="text-[10px] text-slate-400 uppercase">左路走廊</div>
              <div className="text-lg font-mono font-bold text-white mt-1">{channels.left}</div>
              <div className="text-[10px] text-slate-500">{Math.round((channels.left / totalRec) * 100)}%</div>
            </div>
            <div className="bg-[#151e2e] p-2 rounded border border-[rgba(255,255,255,0.05)]">
              <div className="text-[10px] text-slate-400 uppercase">中路中枢</div>
              <div className="text-lg font-mono font-bold text-[#00e599] mt-1">{channels.center}</div>
              <div className="text-[10px] text-slate-500">{Math.round((channels.center / totalRec) * 100)}%</div>
            </div>
            <div className="bg-[#151e2e] p-2 rounded border border-[rgba(255,255,255,0.05)]">
              <div className="text-[10px] text-slate-400 uppercase">右路走廊</div>
              <div className="text-lg font-mono font-bold text-white mt-1">{channels.right}</div>
              <div className="text-[10px] text-slate-500">{Math.round((channels.right / totalRec) * 100)}%</div>
            </div>
          </div>
        </div>
      </div>

      {/* Recoveries List Snippet */}
      {teamData.recoveries.length > 0 && (
        <div className="space-y-1.5 pt-1">
          <div className="text-xs font-semibold text-slate-400">快速恢复事件明细（点击定位）：</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
            {teamData.recoveries.slice(0, 6).map((rec) => (
              <div
                key={rec.recovery_event_id}
                onClick={() => onSelectEvent?.(rec.recovery_event_id)}
                className="bg-[#0e1420] p-2 rounded border border-[rgba(255,255,255,0.06)] hover:border-[#00b074]/60 cursor-pointer flex items-center justify-between text-xs transition-all"
              >
                <div>
                  <div className="font-bold text-white">
                    {rec.actor_name || rec.actor}{" "}
                    {rec.is_high_recovery && (
                      <span className="text-[9px] bg-emerald-500/30 text-emerald-300 px-1 py-0.2 rounded font-mono">
                        HIGH
                      </span>
                    )}
                  </div>
                  <div className="text-[10px] text-slate-400">
                    {Math.floor(rec.recovery_t / 60)}'{Math.floor(rec.recovery_t % 60)}" · {rec.third}
                  </div>
                </div>
                <div className="text-right font-mono font-bold text-[#00e599]">
                  +{rec.elapsed_seconds}s
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Strict Level 1 Disclaimer */}
      <div className="p-2.5 rounded bg-amber-950/20 border border-amber-600/30 text-[11px] text-amber-300/90 flex items-center gap-2">
        <span>⚠️</span>
        <span>
          <b>口径约束 (BL-03)</b>：严格作为失去球权后的可观察统计，严禁宣称“有组织反抢 (Counter-Pressing)”或推断主观战术意图。
        </span>
      </div>
    </div>
  );
}

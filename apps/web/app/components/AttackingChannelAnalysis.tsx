"use client";

import { useState } from "react";

export type ChannelMetric = {
  channel: "left" | "center" | "right";
  attacks_count: number;
  total_progression_meters: number;
  final_third_entries_count: number;
  final_third_penetration_rate: number;
  penalty_box_entries_count: number;
  box_conversion_rate: number;
  shots_count: number;
};

export type AttackingChannelsData = {
  team: string;
  team_name: string;
  attack_direction: "right" | "left";
  channels: Record<"left" | "center" | "right", ChannelMetric>;
  disclaimer: string;
};

interface AttackingChannelAnalysisProps {
  data?: AttackingChannelsData | null;
  onSelectChannel?: (channel: "left" | "center" | "right") => void;
  selectedChannel?: string | null;
}

export function AttackingChannelAnalysis({
  data,
  onSelectChannel,
  selectedChannel,
}: AttackingChannelAnalysisProps) {
  if (!data || !data.channels) {
    return (
      <div className="bg-[#151e2e] border border-[rgba(255,255,255,0.09)] rounded-xl p-5 text-slate-400">
        正在分析进攻通道向前渗透度与禁区触球转化率...
      </div>
    );
  }

  const channels: ("left" | "center" | "right")[] = ["left", "center", "right"];
  const channelLabels: Record<"left" | "center" | "right", string> = {
    left: "左路走廊 (Left Flank)",
    center: "中路通道 (Central Core)",
    right: "右路走廊 (Right Flank)",
  };

  return (
    <div className="bg-[#151e2e] border border-[rgba(255,255,255,0.09)] rounded-xl p-5 shadow-lg space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[rgba(255,255,255,0.08)] pb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold tracking-wider uppercase px-2 py-0.5 rounded bg-[#00b074]/20 text-[#00b074] border border-[#00b074]/30">
              BL-08 · 进攻通道
            </span>
            <span className="text-[10px] font-bold tracking-wider uppercase px-2 py-0.5 rounded bg-blue-500/20 text-blue-400 border border-blue-500/30">
              Level 1 观察统计
            </span>
            <h3 className="text-base font-bold text-white tracking-wide">
              进攻通道渗透度与禁区转化率 ({data.team_name})
            </h3>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            区分左路、中路、右路走廊向前推进渗透度与禁区触球转化率（进攻方向：{data.attack_direction === "right" ? "左至右 →" : "← 右至左"}）。
          </p>
        </div>
      </div>

      {/* 3 Channels Comparison Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {channels.map((chKey) => {
          const ch = data.channels[chKey];
          if (!ch) return null;
          const isSelected = selectedChannel === chKey;

          return (
            <div
              key={chKey}
              onClick={() => onSelectChannel?.(chKey)}
              className={`p-4 rounded-xl border ${
                isSelected
                  ? "border-[#00e599] bg-[#091f1a] ring-1 ring-[#00e599]"
                  : "border-[rgba(255,255,255,0.08)] bg-[#0e1420] hover:border-[#00b074]/60"
              } cursor-pointer transition-all space-y-3`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white tracking-wider">
                  {channelLabels[chKey]}
                </span>
                <span className="text-[10px] font-mono text-[#00e599] bg-[#00b074]/20 px-1.5 py-0.5 rounded">
                  {ch.attacks_count} 次发起
                </span>
              </div>

              {/* Final Third Penetration Rate */}
              <div>
                <div className="flex justify-between text-xs text-slate-400 mb-1">
                  <span>三区渗透度 (Final 3rd):</span>
                  <span className="font-mono font-bold text-white">{ch.final_third_penetration_rate}%</span>
                </div>
                <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-[#00b074] h-full rounded-full transition-all"
                    style={{ width: `${ch.final_third_penetration_rate}%` }}
                  />
                </div>
                <div className="text-[10px] text-slate-500 mt-0.5 text-right">
                  {ch.final_third_entries_count} 次进入前场三区
                </div>
              </div>

              {/* Penalty Box Conversion Rate */}
              <div>
                <div className="flex justify-between text-xs text-slate-400 mb-1">
                  <span>禁区转化率 (Box Touch/Shot):</span>
                  <span className="font-mono font-bold text-amber-400">{ch.box_conversion_rate}%</span>
                </div>
                <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-amber-500 h-full rounded-full transition-all"
                    style={{ width: `${ch.box_conversion_rate}%` }}
                  />
                </div>
                <div className="text-[10px] text-slate-500 mt-0.5 text-right">
                  {ch.penalty_box_entries_count} 次触球 · {ch.shots_count} 次射门
                </div>
              </div>

              {/* Cumulative Progression Distance */}
              <div className="border-t border-[rgba(255,255,255,0.06)] pt-2 flex justify-between text-xs">
                <span className="text-slate-400">总推进净增:</span>
                <span className="font-mono font-bold text-[#00e599]">
                  {ch.total_progression_meters}m
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Level 1 Disclaimer */}
      <div className="p-2.5 rounded bg-emerald-950/20 border border-[#00b074]/30 text-[11px] text-emerald-300/90 flex items-center gap-2">
        <span>⚽</span>
        <span>
          <b>通道定义 (BL-08)</b>：左右方向严格以该进攻队伍的球门向对方球门的视角划分，渗透度与转化率按已记录有效事件归纳。
        </span>
      </div>
    </div>
  );
}

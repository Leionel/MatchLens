"use client";

import React from "react";
import { Locale, getTranslation } from "../lib/i18n";

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
  locale?: Locale;
}

export const AttackingChannelAnalysis: React.FC<AttackingChannelAnalysisProps> = ({
  data,
  onSelectChannel,
  selectedChannel,
  locale = "zh",
}) => {
  const t = getTranslation(locale);
  const isZh = locale === "zh";

  if (!data || !data.channels) {
    return (
      <div
        style={{
          background: "rgba(15, 23, 42, 0.7)",
          border: "1px solid var(--glass-border)",
          borderRadius: "14px",
          padding: "20px",
          color: "var(--text-tertiary)",
          fontSize: "13px",
          textAlign: "center",
        }}
      >
        {isZh ? "正在分析进攻通道向前渗透度与禁区触球转化率..." : "Analyzing attacking corridor penetration and box conversion..."}
      </div>
    );
  }

  const channels: ("left" | "center" | "right")[] = ["left", "center", "right"];
  const channelMeta: Record<
    "left" | "center" | "right",
    { label: string; icon: string; desc: string }
  > = {
    left: {
      label: t.leftFlank,
      icon: "⇖",
      desc: isZh ? "边锋与套上边卫" : "Wingers & Overlaps",
    },
    center: {
      label: t.centralCore,
      icon: "⇑",
      desc: isZh ? "前腰与中路渗透" : "Central Penetration",
    },
    right: {
      label: t.rightFlank,
      icon: "⇗",
      desc: isZh ? "弱侧转移与传中" : "Switches & Crosses",
    },
  };

  return (
    <div
      style={{
        background: "rgba(15, 23, 42, 0.75)",
        border: "1px solid var(--glass-border)",
        borderRadius: "14px",
        padding: "18px 20px",
        boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.5)",
        backdropFilter: "blur(12px)",
        display: "flex",
        flexDirection: "column",
        gap: "14px",
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 10 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span
              style={{
                fontSize: 10,
                fontWeight: 800,
                padding: "2px 6px",
                borderRadius: 4,
                background: "rgba(16, 185, 129, 0.15)",
                color: "var(--turf-emerald)",
                border: "1px solid rgba(16, 185, 129, 0.3)",
              }}
            >
              BL-08 · CORRIDORS
            </span>
            <span
              style={{
                fontSize: 10,
                fontWeight: 800,
                padding: "2px 6px",
                borderRadius: 4,
                background: "rgba(56, 189, 248, 0.15)",
                color: "var(--tech-cyan)",
                border: "1px solid rgba(56, 189, 248, 0.3)",
              }}
            >
              LEVEL 1 OBSERVED
            </span>
            <h3 style={{ fontSize: 16, fontWeight: 800, color: "var(--text-primary)", margin: 0 }}>
              {t.corridorTitle} ({data.team_name})
            </h3>
          </div>
          <p style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 4 }}>
            {t.corridorSubtitle} · {isZh ? "进攻方向" : "Attack Dir"}: {data.attack_direction === "right" ? "左至右 →" : "← 右至左"}
          </p>
        </div>
      </div>

      {/* 3 Channels Tactical Cards Grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: "14px",
        }}
      >
        {channels.map((chKey) => {
          const ch = data.channels[chKey];
          if (!ch) return null;
          const isSelected = selectedChannel === chKey;
          const meta = channelMeta[chKey];

          const penetrationPct = Math.round(ch.final_third_penetration_rate * 100);
          const conversionPct = Math.round(ch.box_conversion_rate * 100);

          return (
            <div
              key={chKey}
              onClick={() => onSelectChannel?.(chKey)}
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 12,
                padding: "16px",
                borderRadius: "12px",
                cursor: "pointer",
                background: isSelected
                  ? "rgba(16, 185, 129, 0.12)"
                  : "rgba(11, 15, 25, 0.7)",
                border: isSelected
                  ? "1px solid var(--turf-emerald)"
                  : "1px solid rgba(255, 255, 255, 0.08)",
                boxShadow: isSelected ? "0 0 16px rgba(16, 185, 129, 0.25)" : "none",
                transition: "all 0.2s ease",
              }}
            >
              {/* Card Top: Title, Icon & Attacks Count */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ fontSize: 16, color: "var(--turf-emerald)" }}>{meta.icon}</span>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 800, color: "var(--text-primary)" }}>
                      {meta.label}
                    </div>
                    <div style={{ fontSize: 10, color: "var(--text-tertiary)" }}>
                      {meta.desc}
                    </div>
                  </div>
                </div>

                <span
                  style={{
                    fontSize: 11,
                    fontFamily: "monospace",
                    fontWeight: 700,
                    padding: "2px 8px",
                    borderRadius: 6,
                    background: "rgba(16, 185, 129, 0.15)",
                    color: "var(--turf-emerald)",
                    border: "1px solid rgba(16, 185, 129, 0.3)",
                  }}
                >
                  {ch.attacks_count} {isZh ? "次发起" : "attacks"}
                </span>
              </div>

              {/* Metric 1: Final Third Penetration Rate */}
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 4 }}>
                  <span style={{ color: "var(--text-secondary)" }}>{t.finalThirdPenetration}</span>
                  <span style={{ fontWeight: 700, color: "var(--text-primary)", fontFamily: "monospace" }}>
                    {penetrationPct}% ({ch.final_third_entries_count} {isZh ? "次进入" : "entries"})
                  </span>
                </div>
                <div style={{ width: "100%", height: 6, background: "rgba(255, 255, 255, 0.08)", borderRadius: 3, overflow: "hidden" }}>
                  <div
                    style={{
                      width: `${penetrationPct}%`,
                      height: "100%",
                      background: "linear-gradient(90deg, #0284c7 0%, #38bdf8 100%)",
                      borderRadius: 3,
                      transition: "width 0.4s ease",
                    }}
                  />
                </div>
              </div>

              {/* Metric 2: Penalty Box Conversion Rate */}
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 4 }}>
                  <span style={{ color: "var(--text-secondary)" }}>{t.boxConversionRate}</span>
                  <span style={{ fontWeight: 700, color: "var(--turf-emerald)", fontFamily: "monospace" }}>
                    {conversionPct}% ({ch.penalty_box_entries_count} {isZh ? "触球" : "touches"} / {ch.shots_count} {isZh ? "射门" : "shots"})
                  </span>
                </div>
                <div style={{ width: "100%", height: 6, background: "rgba(255, 255, 255, 0.08)", borderRadius: 3, overflow: "hidden" }}>
                  <div
                    style={{
                      width: `${conversionPct}%`,
                      height: "100%",
                      background: "linear-gradient(90deg, #10b981 0%, #34d399 100%)",
                      borderRadius: 3,
                      transition: "width 0.4s ease",
                    }}
                  />
                </div>
              </div>

              {/* Metric 3: Progressive Territory Gain */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "6px 10px",
                  borderRadius: 6,
                  background: "rgba(255, 255, 255, 0.03)",
                  border: "1px solid rgba(255, 255, 255, 0.05)",
                  fontSize: 11,
                }}
              >
                <span style={{ color: "var(--text-tertiary)" }}>{t.progressiveGainMeters}</span>
                <span style={{ fontWeight: 800, color: "var(--text-primary)", fontFamily: "monospace" }}>
                  +{ch.total_progression_meters.toFixed(1)}m
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer Definition Note */}
      <div
        style={{
          fontSize: 11,
          color: "var(--text-tertiary)",
          paddingTop: 8,
          borderTop: "1px solid rgba(255, 255, 255, 0.06)",
          display: "flex",
          alignItems: "center",
          gap: 6,
        }}
      >
        <span>⚽</span>
        <span>{t.channelDefinitionNote}</span>
      </div>
    </div>
  );
};

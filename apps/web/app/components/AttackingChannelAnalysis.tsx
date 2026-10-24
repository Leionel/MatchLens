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
  attack_direction: "right" | "left" | "team_relative";
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
          background: "color-mix(in srgb, var(--slate-1) 70%, transparent)",
          border: "0.5px solid var(--glass-border)",
          borderRadius: "var(--radius-panel)",
          padding: "20px",
          color: "var(--text-tertiary)",
          fontSize: "var(--text-body)",
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
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 10 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <h3 style={{ fontSize: 18, fontWeight: 800, color: "var(--text-primary)", margin: 0 }}>
              {t.corridorTitle} ({data.team_name})
            </h3>
          </div>
          <p style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 4 }}>
            
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

          const penetrationPct = Math.round(ch.final_third_penetration_rate);
          const conversionPct = Math.round(ch.box_conversion_rate);

          return (
            <div
              key={chKey}
              onClick={() => onSelectChannel?.(chKey)}
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 12,
                padding: "16px",
                borderRadius: "var(--radius-panel)",
                cursor: "pointer",
                background: isSelected
                  ? "color-mix(in srgb, var(--green-9) 12%, transparent)"
                  : "color-mix(in srgb, var(--slate-1) 70%, transparent)",
                border: isSelected
                  ? "0.5px solid var(--turf-emerald)"
                  : "0.5px solid color-mix(in srgb, var(--slate-12) 8%, transparent)",
                boxShadow: isSelected ? "0 0 16px color-mix(in srgb, var(--green-9) 25%, transparent)" : "none",
                transition: "none",
              }}
            >
              {/* Card Top: Title, Icon & Attacks Count */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ fontSize: 18, color: "var(--text-emerald)" }}>{meta.icon}</span>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 800, color: "var(--text-primary)" }}>
                      {meta.label}
                    </div>
                    <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
                      {meta.desc}
                    </div>
                  </div>
                </div>

                <span
                  style={{
                    fontSize: 12,
                    fontFamily: "monospace",
                    fontWeight: 700,
                    padding: "2px 8px",
                    borderRadius: 6,
                    background: "color-mix(in srgb, var(--green-9) 15%, transparent)",
                    color: "var(--text-emerald)",
                    border: "0.5px solid color-mix(in srgb, var(--green-9) 30%, transparent)",
                  }}
                >
                  {ch.attacks_count} {isZh ? "次发起" : "attacks"}
                </span>
              </div>

              {/* Metric 1: Final Third Penetration Rate */}
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
                  <span style={{ color: "var(--text-secondary)" }}>{t.finalThirdPenetration}</span>
                  <span style={{ fontWeight: 700, color: "var(--text-primary)", fontFamily: "monospace" }}>
                    {penetrationPct}% ({ch.final_third_entries_count} {isZh ? "次进入" : "entries"})
                  </span>
                </div>
                <div style={{ width: "100%", height: 6, background: "color-mix(in srgb, var(--slate-12) 8%, transparent)", borderRadius: 3, overflow: "hidden" }}>
                  <div
                    style={{
                      width: `${penetrationPct}%`,
                      height: "100%",
                      background: "var(--cyan-9)",
                      borderRadius: 3,
                      transition: "none",
                    }}
                  />
                </div>
              </div>

              {/* Metric 2: Penalty Box Conversion Rate */}
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
                  <span style={{ color: "var(--text-secondary)" }}>{t.boxConversionRate}</span>
                  <span style={{ fontWeight: 700, color: "var(--text-emerald)", fontFamily: "monospace" }}>
                    {conversionPct}% ({ch.penalty_box_entries_count} {isZh ? "触球" : "touches"} / {ch.shots_count} {isZh ? "射门" : "shots"})
                  </span>
                </div>
                <div style={{ width: "100%", height: 6, background: "color-mix(in srgb, var(--slate-12) 8%, transparent)", borderRadius: 3, overflow: "hidden" }}>
                  <div
                    style={{
                      width: `${conversionPct}%`,
                      height: "100%",
                      background: "var(--green-9)",
                      borderRadius: 3,
                      transition: "none",
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
                  background: "color-mix(in srgb, var(--slate-12) 3%, transparent)",
                  border: "0.5px solid color-mix(in srgb, var(--slate-12) 5%, transparent)",
                  fontSize: 12,
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
    </div>
  );
};

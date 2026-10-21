"use client";

import React, { useState } from "react";
import { Locale, getTranslation } from "../lib/i18n";

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
  locale?: Locale;
}

export const QuickRecoveryAnalysis: React.FC<QuickRecoveryAnalysisProps> = ({
  data,
  focusTeam = "H",
  onWindowChange,
  onSelectEvent,
  locale = "zh",
}) => {
  const t = getTranslation(locale);
  const isZh = locale === "zh";

  const [windowSec, setWindowSec] = useState<number>(data?.window_seconds ?? 6.0);
  const teamData = data?.teams?.[focusTeam] || Object.values(data?.teams || {})[0];

  if (!teamData) {
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
        {isZh ? "正在统计失去球权后快速球权恢复数据..." : "Computing post-turnover quick recovery data..."}
      </div>
    );
  }

  const recoveryPct = Math.round(teamData.quick_recovery_rate * 100);
  const thirds = teamData.spatial_distribution_thirds || { attacking: 0, middle: 0, defensive: 0 };
  const channels = teamData.spatial_distribution_channels || { left: 0, center: 0, right: 0 };
  const totalRec = teamData.quick_recoveries_count || 1;

  const handleSlider = (val: number) => {
    setWindowSec(val);
    onWindowChange?.(val);
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
              BL-03 · 6s RECOVERY
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
              {t.recoveryAnalysisTitle} ({teamData.team_name})
            </h3>
          </div>
          <p style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 4 }}>
            {t.recoveryAnalysisSubtitle}
          </p>
        </div>
      </div>

      {/* KPI Cards Row */}
      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr 1fr", gap: 10 }}>
        {/* Card 1: Recovery Rate */}
        <div
          style={{
            padding: "12px 14px",
            borderRadius: "10px",
            background: "rgba(16, 185, 129, 0.08)",
            border: "1px solid rgba(16, 185, 129, 0.25)",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>
            {windowSec.toFixed(1)}{t.quickRecoveryRate}
          </span>
          <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
            <span style={{ fontSize: 24, fontWeight: 900, color: "var(--turf-emerald)", fontFamily: "monospace" }}>
              {recoveryPct}%
            </span>
            <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
              ({teamData.quick_recoveries_count} / {teamData.total_possession_losses} {t.totalPossessionLosses})
            </span>
          </div>
        </div>

        {/* Card 2: High Press Recoveries */}
        <div
          style={{
            padding: "12px 14px",
            borderRadius: "10px",
            background: "rgba(56, 189, 248, 0.08)",
            border: "1px solid rgba(56, 189, 248, 0.25)",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>
            {t.highPressRecoveries}
          </span>
          <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
            <span style={{ fontSize: 24, fontWeight: 900, color: "var(--tech-cyan)", fontFamily: "monospace" }}>
              {teamData.high_recoveries_count}
            </span>
            <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
              {isZh ? "进攻三区反抢" : "attacking 3rd"}
            </span>
          </div>
        </div>

        {/* Card 3: Interactive Window Slider */}
        <div
          style={{
            padding: "12px 14px",
            borderRadius: "10px",
            background: "rgba(11, 15, 25, 0.7)",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
            <span style={{ color: "var(--text-secondary)" }}>{t.recoveryWindowSlider}</span>
            <span style={{ fontWeight: 800, color: "var(--amber-gold)", fontFamily: "monospace" }}>
              {windowSec.toFixed(1)}s
            </span>
          </div>
          <input
            type="range"
            min={3.0}
            max={10.0}
            step={0.5}
            value={windowSec}
            onChange={(e) => handleSlider(parseFloat(e.target.value))}
            style={{ width: "100%", accentColor: "var(--turf-emerald)" }}
          />
        </div>
      </div>

      {/* Spatial Distributions Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        {/* Thirds Distribution */}
        <div
          style={{
            padding: "12px 14px",
            borderRadius: "10px",
            background: "rgba(11, 15, 25, 0.7)",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)" }}>
            {t.spatialDistributionThirds}
          </span>
          {[
            { label: isZh ? "进攻三区 (Attacking)" : "Attacking Third", count: thirds.attacking, color: "var(--turf-emerald)" },
            { label: isZh ? "中场三区 (Middle)" : "Middle Third", count: thirds.middle, color: "var(--tech-cyan)" },
            { label: isZh ? "防守三区 (Defensive)" : "Defensive Third", count: thirds.defensive, color: "var(--amber-gold)" },
          ].map((item) => {
            const pct = Math.round((item.count / totalRec) * 100);
            return (
              <div key={item.label}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 2 }}>
                  <span style={{ color: "var(--text-secondary)" }}>{item.label}</span>
                  <span style={{ fontWeight: 700, color: "var(--text-primary)", fontFamily: "monospace" }}>
                    {item.count} {isZh ? "次" : "recoveries"} ({pct}%)
                  </span>
                </div>
                <div style={{ width: "100%", height: 5, background: "rgba(255, 255, 255, 0.08)", borderRadius: 2 }}>
                  <div style={{ width: `${pct}%`, height: "100%", background: item.color, borderRadius: 2 }} />
                </div>
              </div>
            );
          })}
        </div>

        {/* Channels Distribution */}
        <div
          style={{
            padding: "12px 14px",
            borderRadius: "10px",
            background: "rgba(11, 15, 25, 0.7)",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)" }}>
            {t.spatialDistributionChannels}
          </span>
          {[
            { label: t.leftFlank, count: channels.left, color: "var(--tech-cyan)" },
            { label: t.centralCore, count: channels.center, color: "var(--turf-emerald)" },
            { label: t.rightFlank, count: channels.right, color: "var(--tech-cyan)" },
          ].map((item) => {
            const pct = Math.round((item.count / totalRec) * 100);
            return (
              <div key={item.label}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 2 }}>
                  <span style={{ color: "var(--text-secondary)" }}>{item.label}</span>
                  <span style={{ fontWeight: 700, color: "var(--text-primary)", fontFamily: "monospace" }}>
                    {item.count} {isZh ? "次" : "recoveries"} ({pct}%)
                  </span>
                </div>
                <div style={{ width: "100%", height: 5, background: "rgba(255, 255, 255, 0.08)", borderRadius: 2 }}>
                  <div style={{ width: `${pct}%`, height: "100%", background: item.color, borderRadius: 2 }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

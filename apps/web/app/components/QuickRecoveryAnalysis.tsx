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

export type QuickRecoveriesRegistryObservation = {
  metric_id: string;
  team: string;
  window: string;
  window_start_s: number;
  window_end_s: number;
  value: number | null;
  status: string;
  unit: string;
  definition: string;
  event_count: number;
  event_ids: string[];
  metric_version: string;
  computation_version: string;
  coverage_status: string;
  dataset_revision: string | null;
  snapshot_id: string;
};

export type QuickRecoveriesRegistryComparison = {
  metric_id: string;
  registry_comparable: boolean;
  reason: string | null;
  chart_metric: {
    metric_id: string;
    window_seconds: number;
    focus_team: string;
    interval: string;
  };
  snapshot_id: string;
  snapshot_as_of: number;
  observations: Record<string, Record<string, QuickRecoveriesRegistryObservation>>;
  disclaimer: string;
};

export type QuickRecoveriesData = {
  window_seconds: number;
  teams: Record<string, TeamRecoveryData>;
  disclaimer: string;
  registry_comparison?: QuickRecoveriesRegistryComparison;
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
          background: "color-mix(in srgb, var(--slate-1) 70%, transparent)",
          border: "0.5px solid var(--glass-border)",
          borderRadius: "var(--radius-panel)",
          padding: "20px",
          color: "var(--text-tertiary)",
          fontSize: "14px",
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

  // Registry consistency statement (DEF-11 / B-04): the BL-03 quick-recovery
  // count has no registry counterpart, so the backend states the difference
  // instead of pretending the two numbers are the same metric.
  const registry = data?.registry_comparison;
  const registryTeam = registry?.observations?.[teamData.team] || registry?.observations?.[focusTeam];
  const registryRecoveries = registryTeam?.["recoveries"];
  const registryHigh = registryTeam?.["high_recoveries"];
  const registryValue = (obs?: QuickRecoveriesRegistryObservation) =>
    !obs ? "-" : obs.value === null ? (isZh ? "未观测" : "not observed") : String(obs.value);

  const handleSlider = (val: number) => {
    setWindowSec(val);
    onWindowChange?.(val);
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
            <span
              style={{
                fontSize: 12,
                fontWeight: 800,
                padding: "2px 6px",
                borderRadius: 4,
                background: "color-mix(in srgb, var(--green-9) 15%, transparent)",
                color: "var(--text-emerald)",
                border: "0.5px solid color-mix(in srgb, var(--green-9) 30%, transparent)",
              }}
            >
              BL-03 6s RECOVERY
            </span>
            <h3 style={{ fontSize: 18, fontWeight: 800, color: "var(--text-primary)", margin: 0 }}>
              {t.recoveryAnalysisTitle} ({teamData.team_name})
            </h3>
          </div>
          <p style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 4 }}>
            {t.recoveryAnalysisSubtitle}
          </p>
        </div>
      </div>

      {/* Registry consistency statement (same snapshot, different definition) */}
      {registry ? (
        <div
          style={{
            padding: "6px 10px",
            borderRadius: 6,
            fontSize: 11,
            lineHeight: 1.5,
            color: "var(--text-tertiary)",
            background: "color-mix(in srgb, var(--amber-9) 10%, transparent)",
            border: "0.5px solid color-mix(in srgb, var(--amber-9) 30%, transparent)",
          }}
        >
          {registry.registry_comparable ? (
            isZh ? "本图数值与 Registry 同一快照口径一致。" : "These chart values match the registry metric for this snapshot."
          ) : (
            <>
              {isZh ? "本图与 Registry 口径不同，数值不可直接对比：" : "Different definition from the registry; these chart values are not directly comparable: "}
              <span style={{ fontFamily: "monospace" }}>{registry.reason ?? "unknown reason"}</span>
              {isZh ? "。同快照 Registry 参考值：" : ". Registry reference for the same snapshot: "}
              <span style={{ fontFamily: "monospace" }}>
                recoveries {registryValue(registryRecoveries)} / high_recoveries {registryValue(registryHigh)}
              </span>
            </>
          )}
        </div>
      ) : null}

      {/* KPI Cards Row */}
      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr 1fr", gap: 10 }}>
        {/* Card 1: Recovery Rate */}
        <div
          style={{
            padding: "12px 14px",
            borderRadius: "10px",
            background: "color-mix(in srgb, var(--green-9) 8%, transparent)",
            border: "0.5px solid color-mix(in srgb, var(--green-9) 25%, transparent)",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>
            {windowSec.toFixed(1)}{t.quickRecoveryRate}
          </span>
          <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
            <span style={{ fontSize: 24, fontWeight: 900, color: "var(--text-emerald)", fontFamily: "monospace" }}>
              {recoveryPct}%
            </span>
            <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
              ({teamData.quick_recoveries_count} / {teamData.total_possession_losses} {t.totalPossessionLosses})
            </span>
          </div>
        </div>

        {/* Card 2: High Press Recoveries */}
        <div
          style={{
            padding: "12px 14px",
            borderRadius: "10px",
            background: "color-mix(in srgb, var(--cyan-9) 8%, transparent)",
            border: "0.5px solid color-mix(in srgb, var(--cyan-9) 25%, transparent)",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>
            {t.highPressRecoveries}
          </span>
          <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
            <span style={{ fontSize: 24, fontWeight: 900, color: "var(--text-cyan)", fontFamily: "monospace" }}>
              {teamData.high_recoveries_count}
            </span>
            <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
              {isZh ? "进攻三区反抢" : "attacking 3rd"}
            </span>
          </div>
        </div>

        {/* Card 3: Interactive Window Slider */}
        <div
          style={{
            padding: "12px 14px",
            borderRadius: "10px",
            background: "color-mix(in srgb, var(--slate-1) 70%, transparent)",
            border: "0.5px solid color-mix(in srgb, var(--slate-12) 8%, transparent)",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
            <span style={{ color: "var(--text-secondary)" }}>{t.recoveryWindowSlider}</span>
            <span style={{ fontWeight: 800, color: "var(--text-gold)", fontFamily: "monospace" }}>
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
            background: "color-mix(in srgb, var(--slate-1) 70%, transparent)",
            border: "0.5px solid color-mix(in srgb, var(--slate-12) 8%, transparent)",
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)" }}>
            {t.spatialDistributionThirds}
          </span>
          {[
            { label: isZh ? "进攻三区 (Attacking)" : "Attacking Third", count: thirds.attacking, color: "var(--text-emerald)" },
            { label: isZh ? "中场三区 (Middle)" : "Middle Third", count: thirds.middle, color: "var(--text-cyan)" },
            { label: isZh ? "防守三区 (Defensive)" : "Defensive Third", count: thirds.defensive, color: "var(--text-gold)" },
          ].map((item) => {
            const pct = Math.round((item.count / totalRec) * 100);
            return (
              <div key={item.label}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 2 }}>
                  <span style={{ color: "var(--text-secondary)" }}>{item.label}</span>
                  <span style={{ fontWeight: 700, color: "var(--text-primary)", fontFamily: "monospace" }}>
                    {item.count} {isZh ? "次" : "recoveries"} ({pct}%)
                  </span>
                </div>
                <div style={{ width: "100%", height: 5, background: "color-mix(in srgb, var(--slate-12) 8%, transparent)", borderRadius: 2 }}>
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
            background: "color-mix(in srgb, var(--slate-1) 70%, transparent)",
            border: "0.5px solid color-mix(in srgb, var(--slate-12) 8%, transparent)",
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)" }}>
            {t.spatialDistributionChannels}
          </span>
          {[
            { label: t.leftFlank, count: channels.left, color: "var(--text-cyan)" },
            { label: t.centralCore, count: channels.center, color: "var(--text-emerald)" },
            { label: t.rightFlank, count: channels.right, color: "var(--text-cyan)" },
          ].map((item) => {
            const pct = Math.round((item.count / totalRec) * 100);
            return (
              <div key={item.label}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 2 }}>
                  <span style={{ color: "var(--text-secondary)" }}>{item.label}</span>
                  <span style={{ fontWeight: 700, color: "var(--text-primary)", fontFamily: "monospace" }}>
                    {item.count} {isZh ? "次" : "recoveries"} ({pct}%)
                  </span>
                </div>
                <div style={{ width: "100%", height: 5, background: "color-mix(in srgb, var(--slate-12) 8%, transparent)", borderRadius: 2 }}>
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

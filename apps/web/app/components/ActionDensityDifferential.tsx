"use client";

import React from "react";
import { Locale, getTranslation } from "../lib/i18n";

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
  locale?: Locale;
}

export const ActionDensityDifferential: React.FC<ActionDensityDifferentialProps> = ({
  data,
  homeTeamName = "Harbor FC",
  awayTeamName = "Northbridge United",
  onSelectZone,
  selectedZoneId,
  locale = "zh",
}) => {
  const t = getTranslation(locale);
  const isZh = locale === "zh";

  if (!data || !data.zones || data.zones.length === 0) {
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
        {isZh ? "正在计算球队场区行动密度差分 ΔD(z)..." : "Computing team action density differential ΔD(z)..."}
      </div>
    );
  }

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
              BL-04 DENSITY ΔD(z)
            </span>
            <h3 style={{ fontSize: 18, fontWeight: 800, color: "var(--text-primary)", margin: 0 }}>
              {t.densityTitle}
            </h3>
          </div>
          <p style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 4 }}>
            {t.densitySubtitle}
          </p>
        </div>

        {/* Legend */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
          <span style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--text-emerald)", fontWeight: 700 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--turf-emerald)" }} />
            {homeTeamName} (+)
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--text-cyan)", fontWeight: 700 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--tech-cyan)" }} />
            {awayTeamName} (-)
          </span>
          {data.overlap_zones_count > 0 && (
            <span
              style={{
                fontSize: 12,
                fontWeight: 700,
                background: "color-mix(in srgb, var(--amber-9) 15%, transparent)",
                color: "var(--text-gold)",
                padding: "2px 6px",
                borderRadius: 4,
                border: "0.5px solid color-mix(in srgb, var(--amber-9) 30%, transparent)",
              }}
            >
              {data.overlap_zones_count} {t.overlapZonesCount}
            </span>
          )}
        </div>
      </div>

      {/* 3x3 Tactical Pitch Zones Matrix */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: "8px",
          background: "color-mix(in srgb, var(--slate-1) 60%, transparent)",
          padding: "10px",
          borderRadius: "var(--radius-panel)",
          border: "0.5px solid color-mix(in srgb, var(--slate-12) 6%, transparent)",
        }}
      >
        {data.zones.map((zone) => {
          const isSelected = selectedZoneId === zone.cell_id;
          const isHomeAdv = zone.advantage === "home";
          const isAwayAdv = zone.advantage === "away";
          const diffPct = zone.delta_density_pct;

          let cellBorder = "color-mix(in srgb, var(--slate-12) 6%, transparent)";
          let cellBg = "color-mix(in srgb, var(--slate-1) 50%, transparent)";
          let accentColor = "var(--text-tertiary)";

          if (isHomeAdv) {
            cellBg = "color-mix(in srgb, var(--green-9) 8%, transparent)";
            cellBorder = "color-mix(in srgb, var(--green-9) 25%, transparent)";
            accentColor = "var(--turf-emerald)";
          } else if (isAwayAdv) {
            cellBg = "color-mix(in srgb, var(--cyan-9) 8%, transparent)";
            cellBorder = "color-mix(in srgb, var(--cyan-9) 25%, transparent)";
            accentColor = "var(--tech-cyan)";
          }

          if (isSelected) {
            cellBorder = "var(--turf-emerald)";
            cellBg = "color-mix(in srgb, var(--green-9) 16%, transparent)";
          }

          const homeShare = Math.round(zone.home_action_share * 100);
          const awayShare = Math.round(zone.away_action_share * 100);

          return (
            <div
              key={zone.cell_id}
              onClick={() => onSelectZone?.(zone.cell_id)}
              style={{
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                gap: 6,
                padding: "10px",
                borderRadius: "8px",
                cursor: "pointer",
                background: cellBg,
                border: `0.5px solid ${cellBorder}`,
                boxShadow: isSelected ? "0 0 12px color-mix(in srgb, var(--green-9) 30%, transparent)" : "none",
                transition: "none",
              }}
            >
              {/* Zone Top: Name & Overlap Badge */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)" }}>
                  {zone.name}
                </span>

                {zone.is_high_density_overlap && (
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 800,
                      color: "var(--text-gold)",
                      background: "color-mix(in srgb, var(--amber-9) 20%, transparent)",
                      padding: "1px 4px",
                      borderRadius: 3,
                    }}
                    title="Both teams contested high action volume here"
                  >
                    OVERLAP
                  </span>
                )}
              </div>

              {/* Delta Density Value */}
              <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
                <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>ΔD:</span>
                <span
                  style={{
                    fontSize: 14,
                    fontWeight: 850,
                    fontFamily: "monospace",
                    color: accentColor,
                  }}
                >
                  {diffPct > 0 ? `+${diffPct.toFixed(1)}%` : `${diffPct.toFixed(1)}%`}
                </span>
              </div>

              {/* Share Compare Bar */}
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--text-tertiary)", marginBottom: 2 }}>
                  <span>HAR {homeShare}% ({zone.home_actions_count})</span>
                  <span>NOR {awayShare}% ({zone.away_actions_count})</span>
                </div>
                <div style={{ width: "100%", height: 4, background: "color-mix(in srgb, var(--slate-12) 8%, transparent)", borderRadius: 2, display: "flex", overflow: "hidden" }}>
                  <div style={{ width: `${homeShare}%`, height: "100%", background: "var(--turf-emerald)" }} />
                  <div style={{ width: `${awayShare}%`, height: "100%", background: "var(--tech-cyan)" }} />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

"use client";

import React from "react";
import { Locale, getTranslation } from "../lib/i18n";

export type HighlightCandidate = {
  highlight_id: string;
  title: string;
  team: string;
  start_t: number;
  end_t: number;
  peak_t: number;
  impact_score: number;
  category: "goal" | "shot" | "oaai_surge" | string;
  associated_sequence_ids: string[];
  key_event_ids: string[];
  claim_level: number;
  description: string;
};

interface HighlightLocatorProps {
  highlights?: HighlightCandidate[] | null;
  onSelectHighlight?: (highlight: HighlightCandidate) => void;
  selectedHighlightId?: string | null;
  homeTeamName?: string;
  awayTeamName?: string;
  locale?: Locale;
}

export const HighlightLocator: React.FC<HighlightLocatorProps> = ({
  highlights,
  onSelectHighlight,
  selectedHighlightId,
  homeTeamName = "Harbor FC",
  awayTeamName = "Northbridge United",
  locale = "zh",
}) => {
  const t = getTranslation(locale);
  const isZh = locale === "zh";

  if (!highlights || highlights.length === 0) {
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
        {isZh ? "正在基于 OAAI 变化点及 S2 序列扫描核心攻防高光波次..." : "Scanning tactical highlights based on OAAI change-points and S2 sequences..."}
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
            <h3 style={{ fontSize: 18, fontWeight: 800, color: "var(--text-primary)", margin: 0 }}>
              {t.highlightLocatorTitle}
            </h3>
          </div>
        </div>

        <span
          style={{
            fontSize: 12,
            fontWeight: 700,
            fontFamily: "monospace",
            color: "var(--text-secondary)",
            background: "color-mix(in srgb, var(--slate-12) 5%, transparent)",
            padding: "3px 8px",
            borderRadius: 6,
            border: "0.5px solid color-mix(in srgb, var(--slate-12) 8%, transparent)",
          }}
        >
          {highlights.length} {isZh ? "个波次" : "surges detected"}
        </span>
      </div>

      {/* Highlights Grid of Cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: "12px",
          maxHeight: "360px",
          overflowY: "auto",
          paddingRight: 4,
        }}
      >
        {highlights.map((hl) => {
          const isSelected = selectedHighlightId === hl.highlight_id;
          const isGoal = hl.category === "goal";
          const isShot = hl.category === "shot";
          const isHome = hl.team === "H";
          const teamLabel = isHome ? homeTeamName : awayTeamName;

          let badgeBg = "color-mix(in srgb, var(--cyan-9) 15%, transparent)";
          let badgeColor = "var(--text-cyan)";
          let badgeBorder = "color-mix(in srgb, var(--cyan-9) 30%, transparent)";
          let catLabel = t.waveCategorySurge;

          if (isGoal) {
            badgeBg = "color-mix(in srgb, var(--green-9) 20%, transparent)";
            badgeColor = "var(--text-emerald)";
            badgeBorder = "color-mix(in srgb, var(--green-9) 40%, transparent)";
            catLabel = t.waveCategoryGoal;
          } else if (isShot) {
            badgeBg = "color-mix(in srgb, var(--amber-9) 20%, transparent)";
            badgeColor = "var(--text-gold)";
            badgeBorder = "color-mix(in srgb, var(--amber-9) 40%, transparent)";
            catLabel = t.waveCategoryShot;
          }

          const startMin = Math.floor(hl.start_t / 60);
          const endMin = Math.floor(hl.end_t / 60);

          return (
            <div
              key={hl.highlight_id}
              onClick={() => onSelectHighlight?.(hl)}
              style={{
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                gap: 10,
                padding: "14px",
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
              {/* Row 1: Category Badge, Time span & Impact Score */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 800,
                      padding: "2px 6px",
                      borderRadius: 4,
                      background: badgeBg,
                      color: badgeColor,
                      border: `0.5px solid ${badgeBorder}`,
                      letterSpacing: "0.3px",
                    }}
                  >
                    {catLabel}
                  </span>
                  <span
                    style={{
                      fontSize: 12,
                      fontFamily: "monospace",
                      color: "var(--text-secondary)",
                      background: "color-mix(in srgb, var(--slate-12) 4%, transparent)",
                      padding: "2px 6px",
                      borderRadius: 4,
                    }}
                  >
                    {startMin}' - {endMin}'
                  </span>
                </div>

                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 800,
                    color: "var(--text-gold)",
                    background: "color-mix(in srgb, var(--amber-9) 15%, transparent)",
                    padding: "2px 7px",
                    borderRadius: 5,
                    border: "0.5px solid color-mix(in srgb, var(--amber-9) 30%, transparent)",
                  }}
                >
                  ★ {hl.impact_score.toFixed(1)}
                </span>
              </div>

              {/* Row 2: Title & Narrative */}
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", marginBottom: 3 }}>
                  {hl.title}
                </div>
                <div style={{ fontSize: 12, color: "var(--text-tertiary)", lineHeight: 1.5 }}>
                  {hl.description}
                </div>
              </div>

              {/* Row 3: Dominant Team & Action Button */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  paddingTop: 8,
                  borderTop: "0.5px solid color-mix(in srgb, var(--slate-12) 6%, transparent)",
                }}
              >
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: isHome ? "var(--text-emerald)" : "var(--tech-cyan)",
                  }}
                >
                  {t.dominantTeam}: {teamLabel}
                </span>

                <button
                  type="button"
                  style={{
                    minHeight: "auto",
                    padding: "3px 10px",
                    fontSize: 12,
                    fontWeight: 700,
                    borderRadius: 6,
                    background: isSelected ? "var(--turf-emerald)" : "color-mix(in srgb, var(--cyan-9) 15%, transparent)",
                    color: isSelected ? "var(--green-3)" : "var(--tech-cyan)",
                    border: isSelected ? "none" : "0.5px solid color-mix(in srgb, var(--cyan-9) 30%, transparent)",
                    cursor: "pointer",
                  }}
                >
                  {t.jumpToReplay}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

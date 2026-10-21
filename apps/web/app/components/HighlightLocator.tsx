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
          background: "rgba(15, 23, 42, 0.7)",
          border: "1px solid var(--glass-border)",
          borderRadius: "14px",
          padding: "20px",
          color: "var(--text-tertiary)",
          fontSize: "13px",
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
              BL-12 · HIGHLIGHT LOCATOR
            </span>
            <span
              style={{
                fontSize: 10,
                fontWeight: 800,
                padding: "2px 6px",
                borderRadius: 4,
                background: "rgba(168, 85, 247, 0.15)",
                color: "#c084fc",
                border: "1px solid rgba(168, 85, 247, 0.3)",
              }}
            >
              WAVE INDEX
            </span>
            <h3 style={{ fontSize: 16, fontWeight: 800, color: "var(--text-primary)", margin: 0 }}>
              {t.highlightLocatorTitle}
            </h3>
          </div>
          <p style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 4 }}>
            {t.highlightLocatorSubtitle}
          </p>
        </div>

        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            fontFamily: "monospace",
            color: "var(--text-secondary)",
            background: "rgba(255, 255, 255, 0.05)",
            padding: "3px 8px",
            borderRadius: 6,
            border: "1px solid rgba(255, 255, 255, 0.08)",
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

          let badgeBg = "rgba(56, 189, 248, 0.15)";
          let badgeColor = "var(--tech-cyan)";
          let badgeBorder = "rgba(56, 189, 248, 0.3)";
          let catLabel = t.waveCategorySurge;

          if (isGoal) {
            badgeBg = "rgba(16, 185, 129, 0.2)";
            badgeColor = "var(--turf-emerald)";
            badgeBorder = "rgba(16, 185, 129, 0.4)";
            catLabel = t.waveCategoryGoal;
          } else if (isShot) {
            badgeBg = "rgba(245, 158, 11, 0.2)";
            badgeColor = "var(--amber-gold)";
            badgeBorder = "rgba(245, 158, 11, 0.4)";
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
              {/* Row 1: Category Badge, Time span & Impact Score */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 800,
                      padding: "2px 6px",
                      borderRadius: 4,
                      background: badgeBg,
                      color: badgeColor,
                      border: `1px solid ${badgeBorder}`,
                      letterSpacing: "0.3px",
                    }}
                  >
                    {catLabel}
                  </span>
                  <span
                    style={{
                      fontSize: 11,
                      fontFamily: "monospace",
                      color: "var(--text-secondary)",
                      background: "rgba(255, 255, 255, 0.04)",
                      padding: "2px 6px",
                      borderRadius: 4,
                    }}
                  >
                    {startMin}' - {endMin}'
                  </span>
                </div>

                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 800,
                    color: "var(--amber-gold)",
                    background: "rgba(245, 158, 11, 0.15)",
                    padding: "2px 7px",
                    borderRadius: 5,
                    border: "1px solid rgba(245, 158, 11, 0.3)",
                  }}
                >
                  ★ {hl.impact_score.toFixed(1)}
                </span>
              </div>

              {/* Row 2: Title & Narrative */}
              <div>
                <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", marginBottom: 3 }}>
                  {hl.title}
                </div>
                <div style={{ fontSize: 11, color: "var(--text-tertiary)", lineHeight: 1.5 }}>
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
                  borderTop: "1px solid rgba(255, 255, 255, 0.06)",
                }}
              >
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: isHome ? "var(--turf-emerald)" : "var(--tech-cyan)",
                  }}
                >
                  {t.dominantTeam}: {teamLabel}
                </span>

                <button
                  type="button"
                  style={{
                    minHeight: "auto",
                    padding: "3px 10px",
                    fontSize: 11,
                    fontWeight: 700,
                    borderRadius: 6,
                    background: isSelected ? "var(--turf-emerald)" : "rgba(56, 189, 248, 0.15)",
                    color: isSelected ? "#052e16" : "var(--tech-cyan)",
                    border: isSelected ? "none" : "1px solid rgba(56, 189, 248, 0.3)",
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

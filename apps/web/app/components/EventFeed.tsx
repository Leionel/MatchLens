"use client";

import React, { useMemo, useState } from "react";
import { Locale, getTranslation } from "../lib/i18n";

export type FootballEvent = {
  id: string;
  seq: number;
  t: number;
  kind: string;
  team: "H" | "N";
  actor: string;
  receiver: string | null;
  start: [number, number];
  end: [number, number];
  outcome: string;
  possession_id: number;
};

interface EventFeedProps {
  events: FootballEvent[];
  selectedId: string;
  players: Record<string, Record<string, string>>;
  onSelectEvent: (eventId: string) => void;
  locale?: Locale;
}

const clock = (s: number) =>
  `${Math.floor(s / 60).toString().padStart(2, "0")}:${Math.floor(s % 60).toString().padStart(2, "0")}`;

export const EventFeed: React.FC<EventFeedProps> = ({
  events,
  selectedId,
  players,
  onSelectEvent,
  locale = "zh",
}) => {
  const t = getTranslation(locale);
  const isZh = locale === "zh";

  const [filter, setFilter] = useState<"all" | "shots" | "passes" | "recoveries" | "turnovers">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [teamFilter, setTeamFilter] = useState<"all" | "H" | "N">("all");

  const filteredEvents = useMemo(() => {
    let list = [...events].reverse();

    if (teamFilter !== "all") {
      list = list.filter((e) => e.team === teamFilter);
    }

    if (filter === "shots") {
      list = list.filter((e) => e.kind === "shot");
    } else if (filter === "passes") {
      list = list.filter((e) => e.kind === "pass");
    } else if (filter === "recoveries") {
      list = list.filter((e) => e.kind === "recovery");
    } else if (filter === "turnovers") {
      list = list.filter((e) => e.outcome === "turnover" || e.kind === "turnover" || e.outcome === "incomplete");
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      list = list.filter((e) => {
        const actorName = (players[e.team]?.[e.actor] || e.actor).toLowerCase();
        const receiverName = e.receiver ? (players[e.team]?.[e.receiver] || e.receiver).toLowerCase() : "";
        const idMatch = e.id.toLowerCase().includes(q);
        const kindMatch = e.kind.toLowerCase().includes(q);
        return actorName.includes(q) || receiverName.includes(q) || idMatch || kindMatch;
      });
    }

    return list;
  }, [events, filter, teamFilter, searchQuery, players]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        background: "rgba(15, 23, 42, 0.75)",
        border: "1px solid var(--glass-border)",
        borderRadius: "14px",
        padding: "16px",
        boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.5)",
        backdropFilter: "blur(12px)",
        height: "100%",
        minHeight: "480px",
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
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
                letterSpacing: "0.5px",
              }}
            >
              LIVE STREAM
            </span>
            <h3 style={{ fontSize: 15, fontWeight: 800, color: "var(--text-primary)", margin: 0 }}>
              {t.eventLogTitle}
            </h3>
          </div>
          <p style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 2 }}>
            {t.eventLogSubtitle}
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
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
            {filteredEvents.length} / {events.length} {t.eventTotalSuffix}
          </span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 12 }}>
        {/* Team & Category Filter Chips */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {/* Team Switcher */}
          <div style={{ display: "flex", background: "rgba(0, 0, 0, 0.25)", padding: 2, borderRadius: 6, border: "1px solid rgba(255, 255, 255, 0.06)" }}>
            <button
              type="button"
              onClick={() => setTeamFilter("all")}
              style={{
                minHeight: "auto",
                padding: "3px 8px",
                fontSize: 11,
                fontWeight: 700,
                borderRadius: 4,
                border: "none",
                background: teamFilter === "all" ? "rgba(255, 255, 255, 0.15)" : "transparent",
                color: teamFilter === "all" ? "#fff" : "var(--text-secondary)",
                cursor: "pointer",
              }}
            >
              {isZh ? "双队" : "Both"}
            </button>
            <button
              type="button"
              onClick={() => setTeamFilter("H")}
              style={{
                minHeight: "auto",
                padding: "3px 8px",
                fontSize: 11,
                fontWeight: 700,
                borderRadius: 4,
                border: "none",
                background: teamFilter === "H" ? "rgba(16, 185, 129, 0.25)" : "transparent",
                color: teamFilter === "H" ? "var(--turf-emerald)" : "var(--text-secondary)",
                cursor: "pointer",
              }}
            >
              Harbor
            </button>
            <button
              type="button"
              onClick={() => setTeamFilter("N")}
              style={{
                minHeight: "auto",
                padding: "3px 8px",
                fontSize: 11,
                fontWeight: 700,
                borderRadius: 4,
                border: "none",
                background: teamFilter === "N" ? "rgba(56, 189, 248, 0.25)" : "transparent",
                color: teamFilter === "N" ? "var(--tech-cyan)" : "var(--text-secondary)",
                cursor: "pointer",
              }}
            >
              Northbridge
            </button>
          </div>

          {/* Action Categories */}
          {[
            { id: "all", label: t.filterAll },
            { id: "shots", label: t.filterShots },
            { id: "passes", label: t.filterPasses },
            { id: "recoveries", label: t.filterRecoveries },
            { id: "turnovers", label: t.filterTurnovers },
          ].map((cat) => (
            <button
              key={cat.id}
              type="button"
              onClick={() => setFilter(cat.id as any)}
              style={{
                minHeight: "auto",
                padding: "3px 9px",
                fontSize: 11,
                fontWeight: filter === cat.id ? 700 : 500,
                borderRadius: 6,
                border: filter === cat.id ? "1px solid var(--turf-emerald)" : "1px solid rgba(255, 255, 255, 0.08)",
                background: filter === cat.id ? "rgba(16, 185, 129, 0.2)" : "rgba(255, 255, 255, 0.03)",
                color: filter === cat.id ? "var(--turf-emerald)" : "var(--text-secondary)",
                cursor: "pointer",
              }}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* Search Input */}
        <div>
          <input
            type="text"
            placeholder={t.searchEventsPlaceholder}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: "100%",
              background: "rgba(0, 0, 0, 0.3)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: 6,
              padding: "6px 12px",
              color: "var(--text-primary)",
              fontSize: 12,
              outline: "none",
            }}
          />
        </div>
      </div>

      {/* Modern Event Stream Scroll View */}
      <div
        style={{
          flex: 1,
          maxHeight: "440px",
          overflowY: "auto",
          paddingRight: 4,
          display: "flex",
          flexDirection: "column",
          gap: 7,
        }}
      >
        {filteredEvents.length === 0 ? (
          <div
            style={{
              padding: "32px 16px",
              textAlign: "center",
              color: "var(--text-tertiary)",
              fontSize: 13,
            }}
          >
            {t.noEventsFound}
          </div>
        ) : (
          filteredEvents.map((e) => {
            const isSelected = selectedId === e.id;
            const isHome = e.team === "H";
            const isGoal = e.kind === "shot" && e.outcome === "goal";
            const isShot = e.kind === "shot";
            const isRecovery = e.kind === "recovery";
            const isTurnover = e.outcome === "turnover" || e.kind === "turnover" || e.outcome === "incomplete";

            const actorName = players[e.team]?.[e.actor] || e.actor;
            const receiverName = e.receiver ? players[e.team]?.[e.receiver] || e.receiver : null;

            // Badges colors
            let badgeBg = "rgba(56, 189, 248, 0.15)";
            let badgeColor = "var(--tech-cyan)";
            let badgeBorder = "rgba(56, 189, 248, 0.3)";
            let badgeText = t.passBadge;

            if (isGoal) {
              badgeBg = "rgba(16, 185, 129, 0.25)";
              badgeColor = "var(--turf-emerald)";
              badgeBorder = "rgba(16, 185, 129, 0.5)";
              badgeText = t.goalBadge;
            } else if (isShot) {
              badgeBg = "rgba(245, 158, 11, 0.2)";
              badgeColor = "var(--amber-gold)";
              badgeBorder = "rgba(245, 158, 11, 0.4)";
              badgeText = t.shotBadge;
            } else if (isRecovery) {
              badgeBg = "rgba(168, 85, 247, 0.2)";
              badgeColor = "#c084fc";
              badgeBorder = "rgba(168, 85, 247, 0.4)";
              badgeText = t.recoveryBadge;
            } else if (isTurnover) {
              badgeBg = "rgba(244, 63, 94, 0.15)";
              badgeColor = "var(--crimson-warn)";
              badgeBorder = "rgba(244, 63, 94, 0.3)";
              badgeText = t.turnoverBadge;
            }

            return (
              <div
                key={e.id}
                onClick={() => onSelectEvent(e.id)}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  padding: "8px 12px",
                  borderRadius: 8,
                  cursor: "pointer",
                  background: isSelected
                    ? "rgba(16, 185, 129, 0.12)"
                    : isGoal
                    ? "rgba(16, 185, 129, 0.06)"
                    : "rgba(15, 23, 42, 0.5)",
                  border: isSelected
                    ? "1px solid var(--turf-emerald)"
                    : isGoal
                    ? "1px solid rgba(16, 185, 129, 0.4)"
                    : "1px solid rgba(255, 255, 255, 0.05)",
                  boxShadow: isSelected ? "0 0 12px rgba(16, 185, 129, 0.25)" : "none",
                  transition: "all 0.15s ease",
                }}
              >
                {/* Row 1: Time, Type Badge, Team Indicator & ID */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                    <span
                      style={{
                        fontFamily: "monospace",
                        fontSize: 11,
                        fontWeight: 700,
                        color: "var(--text-secondary)",
                      }}
                    >
                      {clock(e.t)}
                    </span>

                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 800,
                        padding: "1px 6px",
                        borderRadius: 4,
                        background: badgeBg,
                        color: badgeColor,
                        border: `1px solid ${badgeBorder}`,
                        letterSpacing: "0.3px",
                      }}
                    >
                      {badgeText}
                    </span>

                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        padding: "1px 5px",
                        borderRadius: 3,
                        background: isHome ? "rgba(16, 185, 129, 0.15)" : "rgba(56, 189, 248, 0.15)",
                        color: isHome ? "var(--turf-emerald)" : "var(--tech-cyan)",
                      }}
                    >
                      {isHome ? "HAR" : "NOR"}
                    </span>
                  </div>

                  <span
                    style={{
                      fontFamily: "monospace",
                      fontSize: 10,
                      color: "var(--text-tertiary)",
                    }}
                  >
                    #{e.id}
                  </span>
                </div>

                {/* Row 2: Player Movement (Actor → Receiver) */}
                <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, fontWeight: 600 }}>
                  <span style={{ color: "var(--text-primary)" }}>{actorName}</span>
                  {receiverName && (
                    <>
                      <span style={{ color: "var(--text-tertiary)", fontSize: 11 }}>→</span>
                      <span style={{ color: "var(--text-secondary)" }}>{receiverName}</span>
                    </>
                  )}
                </div>

                {/* Row 3: Meta details */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 11, color: "var(--text-tertiary)" }}>
                  <span>
                    {e.outcome === "saved"
                      ? t.outcomeSaved
                      : e.outcome === "blocked"
                      ? t.outcomeBlocked
                      : e.outcome === "goal"
                      ? "Score Change"
                      : e.outcome}
                  </span>
                  {e.possession_id !== undefined && (
                    <span style={{ fontSize: 10, fontFamily: "monospace" }}>
                      Seq #{e.possession_id}
                    </span>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

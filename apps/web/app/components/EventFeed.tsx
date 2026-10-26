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
  start?: [number, number] | null;
  end?: [number, number] | null;
  located?: boolean;
  outcome: string;
  possession_id: number;
};

interface EventFeedProps {
  events: FootballEvent[];
  selectedId: string;
  players: Record<string, Record<string, string>>;
  teamNames?: { H?: string; N?: string };
  onSelectEvent: (eventId: string) => void;
  locale?: Locale;
}

const clock = (s: number) =>
  `${Math.floor(s / 60).toString().padStart(2, "0")}:${Math.floor(s % 60).toString().padStart(2, "0")}`;

export const EventFeed: React.FC<EventFeedProps> = ({
  events,
  selectedId,
  players,
  teamNames,
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
        background: "color-mix(in srgb, var(--slate-1) 75%, transparent)",
        border: "0.5px solid var(--glass-border)",
        borderRadius: "var(--radius-panel)",
        padding: "16px",
        boxShadow: "none",
        backdropFilter: "blur(12px)",
        height: "100%",
        minHeight: "480px",
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <h3 style={{ fontSize: 18, fontWeight: 800, color: "var(--text-primary)", margin: 0 }}>
              {t.eventLogTitle}
            </h3>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
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
            {filteredEvents.length} / {events.length} {t.eventTotalSuffix}
          </span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 12 }}>
        {/* Team & Category Filter Chips */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {/* Team Switcher */}
          <div style={{ display: "flex", background: "var(--black-a4)", padding: 2, borderRadius: 6, border: "0.5px solid color-mix(in srgb, var(--slate-12) 6%, transparent)" }}>
            <button
              type="button"
              onClick={() => setTeamFilter("all")}
              style={{
                minHeight: "auto",
                padding: "3px 8px",
                fontSize: 12,
                fontWeight: 700,
                borderRadius: 4,
                border: "none",
                background: teamFilter === "all" ? "color-mix(in srgb, var(--slate-12) 15%, transparent)" : "transparent",
                color: teamFilter === "all" ? "var(--white)" : "var(--text-secondary)",
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
                fontSize: 12,
                fontWeight: 700,
                borderRadius: 4,
                border: "none",
                background: teamFilter === "H" ? "color-mix(in srgb, var(--green-9) 25%, transparent)" : "transparent",
                color: teamFilter === "H" ? "var(--text-emerald)" : "var(--text-secondary)",
                cursor: "pointer",
              }}
            >
              {teamNames?.H || "Harbor"}
            </button>
            <button
              type="button"
              onClick={() => setTeamFilter("N")}
              style={{
                minHeight: "auto",
                padding: "3px 8px",
                fontSize: 12,
                fontWeight: 700,
                borderRadius: 4,
                border: "none",
                background: teamFilter === "N" ? "color-mix(in srgb, var(--cyan-9) 25%, transparent)" : "transparent",
                color: teamFilter === "N" ? "var(--tech-cyan)" : "var(--text-secondary)",
                cursor: "pointer",
              }}
            >
              {teamNames?.N || "Northbridge"}
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
                fontSize: 12,
                fontWeight: filter === cat.id ? 700 : 500,
                borderRadius: 6,
                border: filter === cat.id ? "0.5px solid var(--turf-emerald)" : "0.5px solid color-mix(in srgb, var(--slate-12) 8%, transparent)",
                background: filter === cat.id ? "color-mix(in srgb, var(--green-9) 20%, transparent)" : "color-mix(in srgb, var(--slate-12) 3%, transparent)",
                color: filter === cat.id ? "var(--text-emerald)" : "var(--text-secondary)",
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
              background: "var(--black-a5)",
              border: "0.5px solid color-mix(in srgb, var(--slate-12) 8%, transparent)",
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
        tabIndex={0}
        role="region"
        aria-label={isZh ? "比赛事件流" : "Match event stream"}
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
              fontSize: 14,
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
            let badgeBg = "color-mix(in srgb, var(--cyan-9) 15%, transparent)";
            let badgeColor = "var(--tech-cyan)";
            let badgeBorder = "color-mix(in srgb, var(--cyan-9) 30%, transparent)";
            let badgeText = t.passBadge;

            if (isGoal) {
              badgeBg = "color-mix(in srgb, var(--green-9) 25%, transparent)";
              badgeColor = "var(--turf-emerald)";
              badgeBorder = "color-mix(in srgb, var(--green-9) 50%, transparent)";
              badgeText = t.goalBadge;
            } else if (isShot) {
              badgeBg = "color-mix(in srgb, var(--amber-9) 20%, transparent)";
              badgeColor = "var(--amber-gold)";
              badgeBorder = "color-mix(in srgb, var(--amber-9) 40%, transparent)";
              badgeText = t.shotBadge;
            } else if (isRecovery) {
              badgeBg = "color-mix(in srgb, var(--violet-9) 20%, transparent)";
              badgeColor = "var(--violet-10)";
              badgeBorder = "color-mix(in srgb, var(--violet-9) 40%, transparent)";
              badgeText = t.recoveryBadge;
            } else if (isTurnover) {
              badgeBg = "color-mix(in srgb, var(--red-9) 15%, transparent)";
              badgeColor = "var(--crimson-warn)";
              badgeBorder = "color-mix(in srgb, var(--red-9) 30%, transparent)";
              badgeText = t.turnoverBadge;
            }

            return (
              <div
                key={e.id}
                data-testid="event-feed-row"
                data-event-kind={e.kind}
                onClick={() => onSelectEvent(e.id)}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  padding: "8px 12px",
                  borderRadius: 8,
                  cursor: "pointer",
                  background: isSelected
                    ? "color-mix(in srgb, var(--green-9) 12%, transparent)"
                    : isGoal
                    ? "color-mix(in srgb, var(--green-9) 6%, transparent)"
                    : "color-mix(in srgb, var(--slate-1) 50%, transparent)",
                  border: isSelected
                    ? "0.5px solid var(--turf-emerald)"
                    : isGoal
                    ? "0.5px solid color-mix(in srgb, var(--green-9) 40%, transparent)"
                    : "0.5px solid color-mix(in srgb, var(--slate-12) 5%, transparent)",
                  boxShadow: isSelected ? "0 0 12px color-mix(in srgb, var(--green-9) 25%, transparent)" : "none",
                  transition: "none",
                }}
              >
                {/* Row 1: Time, Type Badge, Team Indicator & ID */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                    <span
                      style={{
                        fontFamily: "monospace",
                        fontSize: 12,
                        fontWeight: 700,
                        color: "var(--text-secondary)",
                      }}
                    >
                      {clock(e.t)}
                    </span>

                    <span
                      style={{
                        fontSize: 12,
                        fontWeight: 800,
                        padding: "1px 6px",
                        borderRadius: 4,
                        background: badgeBg,
                        color: badgeColor,
                        border: `0.5px solid ${badgeBorder}`,
                        letterSpacing: "0.3px",
                      }}
                    >
                      {badgeText}
                    </span>

                    <span
                      style={{
                        fontSize: 12,
                        fontWeight: 700,
                        padding: "1px 5px",
                        borderRadius: 3,
                        background: isHome ? "color-mix(in srgb, var(--green-9) 15%, transparent)" : "color-mix(in srgb, var(--cyan-9) 15%, transparent)",
                        color: isHome ? "var(--text-emerald)" : "var(--tech-cyan)",
                      }}
                    >
                      {isHome ? (teamNames?.H || "HAR").slice(0, 3).toUpperCase() : (teamNames?.N || "NOR").slice(0, 3).toUpperCase()}
                    </span>
                  </div>

                  <span
                    style={{
                      fontFamily: "monospace",
                      fontSize: 12,
                      color: "var(--text-tertiary)",
                    }}
                  >
                    #{e.id}
                  </span>
                </div>

                {/* Row 2: Player Movement (Actor → Receiver) */}
                <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 14, fontWeight: 600 }}>
                  <span style={{ color: "var(--text-primary)" }}>{actorName}</span>
                  {receiverName && (
                    <>
                      <span style={{ color: "var(--text-tertiary)", fontSize: 12 }}>→</span>
                      <span style={{ color: "var(--text-secondary)" }}>{receiverName}</span>
                    </>
                  )}
                </div>

                {/* Row 3: Meta details */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12, color: "var(--text-tertiary)" }}>
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
                    <span style={{ fontSize: 12, fontFamily: "monospace" }}>
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

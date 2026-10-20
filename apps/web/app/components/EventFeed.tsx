"use client";

import { useState } from "react";

type FootballEvent = {
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

type EventFeedProps = {
  events: FootballEvent[];
  selectedId: string;
  players: Record<string, Record<string, string>>;
  onSelectEvent: (eventId: string) => void;
};

const clock = (s: number) =>
  `${Math.floor(s / 60).toString().padStart(2, "0")}:${Math.floor(s % 60).toString().padStart(2, "0")}`;

export function EventFeed({
  events,
  selectedId,
  players,
  onSelectEvent,
}: EventFeedProps) {
  const [filter, setFilter] = useState<"all" | "shots" | "recoveries">("all");

  const filteredEvents = events.filter((e) => {
    if (filter === "shots") return e.kind === "shot";
    if (filter === "recoveries") return e.kind === "recovery";
    return true;
  });

  return (
    <aside className="event-feed-card" aria-label="Live on-ball event log">
      <div className="feed-header">
        <div className="feed-title-wrap">
          <span className="feed-tag">EVENT LOG</span>
          <h3 className="feed-title">On-Ball Action Stream</h3>
        </div>
        <span className="event-count-badge">{events.length} total</span>
      </div>

      <div className="feed-filter-bar">
        {(["all", "shots", "recoveries"] as const).map((f) => (
          <button
            key={f}
            type="button"
            className={`feed-filter-btn ${filter === f ? "active" : ""}`}
            onClick={() => setFilter(f)}
          >
            {f === "all" ? "All" : f === "shots" ? "Shots ⚽" : "Turnovers ⚡"}
          </button>
        ))}
      </div>

      <ol className="feed-list" reversed>
        {filteredEvents
          .slice(-10)
          .reverse()
          .map((e) => {
            const isSelected = selectedId === e.id;
            const isHarbor = e.team === "H";
            const teamClass = isHarbor ? "team-h" : "team-n";
            const isGoal = e.kind === "shot" && e.outcome === "goal";

            return (
              <li key={e.id} className="feed-item">
                <button
                  type="button"
                  className={`feed-event-btn ${isSelected ? "selected" : ""} ${isGoal ? "goal-event" : ""}`}
                  onClick={() => onSelectEvent(e.id)}
                  aria-pressed={isSelected}
                >
                  <time className="event-timestamp">{clock(e.t)}</time>
                  <span className={`event-team-pip ${teamClass}`} />
                  <div className="event-main-info">
                    <span className="event-action-name">
                      {isGoal ? "GOAL!" : e.kind === "recovery" ? "Ball recovery" : e.kind.toUpperCase()}
                      {e.outcome === "saved" && " (Saved)"}
                    </span>
                    <span className="event-player-names">
                      {players[e.team]?.[e.actor] || e.actor}
                      {e.receiver && ` → ${players[e.team]?.[e.receiver] || e.receiver}`}
                    </span>
                  </div>
                  <span className="event-id-tag">{e.id}</span>
                </button>
              </li>
            );
          })}
      </ol>
      <div className="feed-footer-note">
        <span>Click any event to spotlight spatial coordinates on the radar.</span>
      </div>
    </aside>
  );
}

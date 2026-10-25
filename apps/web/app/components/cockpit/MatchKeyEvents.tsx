"use client";

import React, { useMemo } from "react";
import { CockpitState, FootballEvent } from "./types";
import { Locale } from "../../lib/i18n";

interface MatchKeyEventsProps {
  events: CockpitState["events"];
  teams?: CockpitState["teams"];
  locale?: Locale;
  onOpenAll: () => void;
  onSelectEvent: (eventId: string) => void;
  onSeek: (at: number) => void;
}

const clock = (value: number) => {
  const safe = Math.max(0, Math.round(value));
  return `${Math.floor(safe / 60).toString().padStart(2, "0")}:${(safe % 60).toString().padStart(2, "0")}`;
};

/**
 * The phone overview shows a shortlist of recorded key events. The complete
 * feed remains on its own section instead of turning Match Detail into a log.
 */
export const MatchKeyEvents: React.FC<MatchKeyEventsProps> = ({
  events,
  teams,
  locale = "zh",
  onOpenAll,
  onSelectEvent,
  onSeek,
}) => {
  const isZh = locale === "zh";
  const shown = useMemo(() => {
    const replayable = (events || []).filter((event: FootballEvent) => event.start && event.end);
    const notable = replayable.filter((event: FootballEvent) =>
      /shot|goal|save|recover|intercept|tackle/i.test(`${event.kind} ${event.outcome}`),
    );
    return [...(notable.length ? notable : replayable)].sort((a, b) => b.t - a.t).slice(0, 5);
  }, [events]);
  const teamName = (team: string) =>
    team === "N" ? teams?.N || (isZh ? "客队" : "Away") : team === "H" ? teams?.H || (isZh ? "主队" : "Home") : isZh ? "中立" : "Neutral";

  return (
    <section className="r6-mobile-key-events" aria-labelledby="r6-key-events-title">
      <div className="r6-mobile-key-head">
        <h3 id="r6-key-events-title">{isZh ? "近期关键事件" : "Recent key events"}</h3>
        <button type="button" className="r6-text-action" onClick={onOpenAll}>
          {isZh ? "全部事件 →" : "All events →"}
        </button>
      </div>
      <div className="r6-mobile-key-list">
        {shown.length === 0 ? (
          <p className="r6-mobile-key-empty">{isZh ? "当前快照还没有可回放事件。" : "No replayable events at this snapshot."}</p>
        ) : (
          shown.map((event) => (
            <button
              key={event.id}
              type="button"
              onClick={() => {
                onSelectEvent(event.id);
                onSeek(Math.round(event.t));
              }}
            >
              <span className="r6-mobile-key-time">{clock(event.t)}</span>
              <span className="r6-mobile-key-team">{teamName(event.team)}</span>
              <span className="r6-mobile-key-copy">
                <b>{event.actor_name || event.actor || "—"}</b>
                <small>{event.kind}{event.outcome ? ` · ${event.outcome}` : ""}</small>
              </span>
            </button>
          ))
        )}
      </div>
    </section>
  );
};

"use client";

import React, { useMemo } from "react";
import { CockpitState, FootballEvent } from "./types";
import { Locale } from "../../lib/i18n";
import { displayableEvents, isLocatable } from "../../lib/eventValidity";

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
 * Importance is a property of what was recorded, not of whether the provider
 * happened to attach coordinates. A goal is a goal. Only the "can the pitch
 * draw it" question reads coordinates, and that is a separate badge.
 */
const weight = (event: FootballEvent): number => {
  const kind = `${event.kind || ""}`.toLowerCase();
  const outcome = `${event.outcome || ""}`.toLowerCase();
  if (kind === "shot" && outcome === "goal") return 100;
  if (kind === "goal") return 100;
  if (kind === "penalty") return 90;
  if (kind === "shot") return 80;
  if (kind === "foul" || kind === "card") return 55;
  if (kind === "save") return 50;
  if (kind === "recovery" || kind === "interception") return 40;
  if (kind === "tackle" || kind === "block" || kind === "clearance") return 35;
  if (kind === "turnover" || outcome === "turnover") return 30;
  if (kind === "miscontrol") return 25;
  if (kind === "off_ball" || kind === "other") return 0;
  return 5;
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
    const readable = displayableEvents(events);
    const notable = readable.filter((event) => weight(event) >= 25);
    const pool = notable.length ? notable : readable;
    return [...pool]
      .sort((a, b) => weight(b) - weight(a) || b.t - a.t)
      .slice(0, 5);
  }, [events]);
  const teamName = (team: string) =>
    team === "N" ? teams?.N || (isZh ? "客队" : "Away") : team === "H" ? teams?.H || (isZh ? "主队" : "Home") : isZh ? "中立" : "Neutral";

  return (
    <section className="r6-mobile-key-events" aria-labelledby="r6-key-events-title" data-testid="match-key-events">
      <div className="r6-mobile-key-head">
        <h3 id="r6-key-events-title">{isZh ? "近期关键事件" : "Recent key events"}</h3>
        <button type="button" className="r6-text-action" onClick={onOpenAll}>
          {isZh ? "全部事件 →" : "All events →"}
        </button>
      </div>
      <div className="r6-mobile-key-list">
        {shown.length === 0 ? (
          <p className="r6-mobile-key-empty">
            {isZh ? "当前快照还没有可读取的事件记录。" : "No readable recorded events at this snapshot."}
          </p>
        ) : (
          shown.map((event) => {
            // A point-only action is still placeable on the pitch; only a fully
            // unlocated event needs the honesty marker.
            const placeable = isLocatable(event);
            return (
              <button
                key={event.id}
                type="button"
                data-testid="match-key-event"
                data-located={placeable ? "true" : "false"}
                onClick={() => {
                  onSelectEvent(event.id);
                  onSeek(Math.round(event.t));
                }}
              >
                <span className="r6-mobile-key-time">{clock(event.t)}</span>
                <span className="r6-mobile-key-team">{teamName(event.team)}</span>
                <span className="r6-mobile-key-copy">
                  <b>{event.actor_name || event.actor || "—"}</b>
                  <small>
                    {event.kind}
                    {event.outcome ? ` · ${event.outcome}` : ""}
                    {!placeable && (
                      <em className="r6-noloc-tag" title={isZh ? "该事件未附带坐标，无法在球场绘制，但仍计入列表与统计。" : "No coordinates recorded: the pitch cannot draw it, but it still counts in the list and the totals."}>
                        {isZh ? "无坐标" : "no coords"}
                      </em>
                    )}
                  </small>
                </span>
              </button>
            );
          })
        )}
      </div>
    </section>
  );
};

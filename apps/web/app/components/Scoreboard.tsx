"use client";

import React from "react";
import { Locale, getTranslation } from "../lib/i18n";

type ScoreboardProps = {
  score: { H: number; N: number };
  clock: string;
  seconds: number;
  speed: number;
  paused: boolean;
  ended: boolean;
  focus: string | null;
  activeMomentBadge?: string | null;
  possessionH?: number;
  locale?: Locale;
};

export function Scoreboard({
  score,
  clock,
  seconds,
  speed,
  paused,
  ended,
  focus,
  activeMomentBadge,
  possessionH = 50,
  locale = "zh",
}: ScoreboardProps) {
  const t = getTranslation(locale);
  const isZh = locale === "zh";

  const statusLabel = focus
    ? focus.length === 1 ? (isZh ? `关键波次 ${focus}` : `FOCUS MOMENT ${focus}`) : (isZh ? "聚焦波次" : "FOCUSED MOMENT")
    : ended
      ? t.statusFullTime
      : activeMomentBadge
        ? activeMomentBadge
        : paused
          ? t.statusPaused
          : `${t.statusLiveReplay} · ${speed}×`;

  return (
    <section className="broadcast-scoreboard" aria-label="Synthetic match scoreboard">
      <div className="scoreboard-top-bar">
        <div className="competition-tag">
          <span className="live-dot" aria-hidden="true" />
          <span className="league-title">{t.competitionTag}</span>
          <span className="format-badge">{t.matchFormatTag}</span>
        </div>
        <div className={`status-pill ${focus ? "focus" : activeMomentBadge ? "moment" : ended ? "ended" : "live"}`}>
          {statusLabel}
        </div>
      </div>

      <div className="scoreboard-fixture">
        <div className="team-cell team-home">
          <div className="team-crest crest-harbor">
            <span>HFC</span>
          </div>
          <div className="team-info">
            <h1 className="team-name">Harbor FC</h1>
            <span className="team-meta">{t.homeTeamMeta}</span>
          </div>
        </div>

        <div className="score-pod">
          <div className="digits-wrap">
            <span className="digit digit-home">{score.H}</span>
            <span className="digit-separator">:</span>
            <span className="digit digit-away">{score.N}</span>
          </div>
          <div className="clock-wrap">
            <span className="match-time">{clock}</span>
            <span className="clock-state">
              {focus ? t.statusFrozen : paused ? t.statusHold : `${speed}×`}
            </span>
          </div>
        </div>

        <div className="team-cell team-away">
          <div className="team-info">
            <h2 className="team-name">Northbridge Utd</h2>
            <span className="team-meta">{t.awayTeamMeta}</span>
          </div>
          <div className="team-crest crest-northbridge">
            <span>NBU</span>
          </div>
        </div>
      </div>

      <div className="possession-gauge-wrap" title={isZh ? "当前时间窗口控球率（死球不计入）" : "Current-window controlled possession; dead-ball time excluded"}>
        <div className="gauge-label-left">HFC {seconds ? `${possessionH.toFixed(0)}%` : "—"}</div>
        <div className="gauge-track">
          <div className="gauge-fill-h" style={{ width: `${possessionH}%` }} />
          <div className="gauge-fill-n" style={{ width: `${100 - possessionH}%` }} />
        </div>
        <div className="gauge-label-right">{seconds ? `${(100 - possessionH).toFixed(0)}%` : "—"} NBU</div>
      </div>
    </section>
  );
}

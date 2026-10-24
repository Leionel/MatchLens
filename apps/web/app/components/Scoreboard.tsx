"use client";

import React from "react";
import { Locale, getTranslation } from "../lib/i18n";

type ScoreboardProps = {
  score: { H: number; N: number };
  officialScore?: { H: number | null; N: number | null } | null;
  teams?: { H?: string; N?: string };
  coverage?: { continuous: boolean; observed_end: number | null; format_seconds: number; time_coverage?: number } | null;
  competition?: string | null;
  season?: string | null;
  clock: string;
  seconds: number;
  speed: number;
  paused: boolean;
  ended: boolean;
  focus: string | null;
  activeMomentBadge?: string | null;
  possessionH?: number | null;
  locale?: Locale;
};

function initials(name: string): string {
  const words = name.split(/\s+/).filter(Boolean);
  if (words.length === 1) return words[0].slice(0, 3).toUpperCase();
  return words.slice(0, 3).map((w) => w[0]).join("").toUpperCase();
}

export function Scoreboard({
  score,
  officialScore,
  teams,
  coverage,
  competition,
  season,
  clock,
  seconds,
  speed,
  paused,
  ended,
  focus,
  activeMomentBadge,
  possessionH,
  locale = "zh",
}: ScoreboardProps) {
  const t = getTranslation(locale);
  const isZh = locale === "zh";
  const homeTeam = teams?.H || "Harbor FC";
  const awayTeam = teams?.N || "Northbridge United";
  const hasPossession = typeof possessionH === "number" && Number.isFinite(possessionH) && seconds > 0;
  const officialVisible =
    officialScore &&
    officialScore.H !== null &&
    officialScore.N !== null &&
    (officialScore.H !== score.H || officialScore.N !== score.N);

  const statusLabel = focus
    ? focus.length === 1 ? (isZh ? `关键波次 ${focus}` : `FOCUS MOMENT ${focus}`) : (isZh ? "聚焦波次" : "FOCUSED MOMENT")
    : ended
      ? t.statusFullTime
      : activeMomentBadge
        ? activeMomentBadge
        : paused
          ? t.statusPaused
          : `${t.statusLiveReplay} ${speed}×`;

  return (
    <section className="broadcast-scoreboard" aria-label={`${homeTeam} vs ${awayTeam} scoreboard`}>
      <div className="scoreboard-top-bar">
        <div className="competition-tag">
          <span className="live-dot" aria-hidden="true" />
          <span className="league-title">{[competition, season].filter(Boolean).join(" ") || t.competitionTag}</span>
          <span className="format-badge">
            {coverage
              ? isZh
                ? `覆盖${coverage.continuous ? "连续" : "有缺口"} · 已观测 ${Math.round((coverage.time_coverage || 0) * 100)}%`
                : `${coverage.continuous ? "Continuous" : "Gapped"} coverage · ${Math.round((coverage.time_coverage || 0) * 100)}% observed`
              : t.matchFormatTag}
          </span>
        </div>
        <div className={`status-pill ${focus ? "focus" : activeMomentBadge ? "moment" : ended ? "ended" : "live"}`}>
          {statusLabel}
        </div>
      </div>

      <div className="scoreboard-fixture">
        <div className="team-cell team-home">
          <div className="team-crest crest-harbor">
            <span>{initials(homeTeam)}</span>
          </div>
          <div className="team-info">
            <h1 className="team-name">{homeTeam}</h1>
            <span className="team-meta">{isZh ? "主队" : "Home"}</span>
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
          {officialVisible && (
            <div className="score-official" title={isZh ? "官方最终比分，不代表当前回放时刻" : "Official final score, not the current replay moment"}>
              {isZh ? "官方终场" : "OFFICIAL FT"} {officialScore!.H}–{officialScore!.N}
            </div>
          )}
        </div>

        <div className="team-cell team-away">
          <div className="team-info">
            <h2 className="team-name">{awayTeam}</h2>
            <span className="team-meta">{isZh ? "客队" : "Away"}</span>
          </div>
          <div className="team-crest crest-northbridge">
            <span>{initials(awayTeam)}</span>
          </div>
        </div>
      </div>

      <div
        className="possession-gauge-wrap"
        title={isZh ? "当前窗口已观测控球率；未观测不等于 0" : "Observed controlled possession in the current window; unobserved is not zero"}
      >
        <div className="gauge-label-left">{initials(homeTeam)} {hasPossession ? `${possessionH!.toFixed(0)}%` : "—"}</div>
        <div className="gauge-track" aria-hidden="true">
          {hasPossession ? (
            <>
              <div className="gauge-fill-h" style={{ width: `${possessionH}%` }} />
              <div className="gauge-fill-n" style={{ width: `${100 - possessionH!}%` }} />
            </>
          ) : (
            <div className="gauge-unobserved" />
          )}
        </div>
        <div className="gauge-label-right">{hasPossession ? `${(100 - possessionH!).toFixed(0)}%` : "—"} {initials(awayTeam)}</div>
      </div>
    </section>
  );
}

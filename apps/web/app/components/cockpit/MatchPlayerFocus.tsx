"use client";

import React, { useMemo } from "react";
import { CockpitState, PlayerSpotlight } from "./types";
import { Locale } from "../../lib/i18n";

interface MatchPlayerFocusProps {
  state: CockpitState;
  locale?: Locale;
  selectedPlayerId?: string | null;
  onSelectPlayer: (playerId: string | null) => void;
  onInvestigatePlayer: (player: PlayerSpotlight) => void;
}

/**
 * Match Detail reuses the player spotlight the backend already computes from
 * recorded events. It is deliberately not a second statistics system: the card
 * shows the same counts the pitch highlight and the tactical explorer use, and
 * every row leads back to the recorded actions or into an investigation.
 */
export const MatchPlayerFocus: React.FC<MatchPlayerFocusProps> = ({
  state,
  locale = "zh",
  selectedPlayerId,
  onSelectPlayer,
  onInvestigatePlayer,
}) => {
  const isZh = locale === "zh";
  const homeName = state.teams?.H || (isZh ? "主队" : "Home");
  const awayName = state.teams?.N || (isZh ? "客队" : "Away");

  const top = useMemo(() => {
    const players = state.player_spotlight || [];
    return [...players]
      // An unattributed bucket ("Unknown") with zero recorded actions carries
      // no information; showing it reads as a broken card. Named players with
      // recorded actions always win the slots.
      .filter(
        (p) =>
          p.name &&
          p.name !== "Unknown" &&
          p.progressive_passes + p.shots + p.recoveries + (p.touches || 0) > 0,
      )
      .sort(
        (a, b) =>
          b.progressive_passes + b.shots * 3 + b.recoveries - (a.progressive_passes + a.shots * 3 + a.recoveries),
      )
      .slice(0, 4);
  }, [state.player_spotlight]);

  if (top.length === 0) return null;

  return (
    <section className="r6-player-focus" aria-labelledby="r6-player-focus-title" data-testid="match-player-focus">
      <div className="r6-player-focus-head">
        <h3 id="r6-player-focus-title">{isZh ? "关键球员 · 已记录动作" : "Key players · recorded actions"}</h3>
        <p>
          {isZh
            ? "数据来自本场事件流的前锋与推进计数，不含无球跑动。"
            : "Counts come from this match's recorded events; off-ball movement is not measured."}
        </p>
      </div>
      <div className="r6-player-grid">
        {top.map((player) => {
          const active = selectedPlayerId === player.player_id;
          return (
            <article
              key={player.player_id}
              className={`r6-player-card ${active ? "selected" : ""}`}
              data-testid="match-player-card"
              data-team={player.team}
            >
              <header>
                <span className="r6-player-team" data-team={player.team}>
                  {player.team === "H" ? homeName : awayName}
                </span>
                <button
                  type="button"
                  className="r6-player-name"
                  onClick={() => onSelectPlayer(active ? null : player.player_id)}
                  aria-pressed={active}
                >
                  {player.name || player.player_id}
                </button>
              </header>
              <dl>
                <div>
                  <dt>{isZh ? "推进传球" : "Prog. passes"}</dt>
                  <dd>{player.progressive_passes}</dd>
                </div>
                <div>
                  <dt>{isZh ? "射门" : "Shots"}</dt>
                  <dd>{player.shots}</dd>
                </div>
                <div>
                  <dt>{isZh ? "夺回" : "Recoveries"}</dt>
                  <dd>{player.recoveries}</dd>
                </div>
              </dl>
              <button
                type="button"
                className="r6-text-action"
                data-testid="match-player-investigate"
                onClick={() => onInvestigatePlayer(player)}
              >
                {isZh ? "调查这名球员 →" : "Investigate player →"}
              </button>
            </article>
          );
        })}
      </div>
    </section>
  );
};

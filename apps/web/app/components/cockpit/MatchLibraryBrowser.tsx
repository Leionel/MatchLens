"use client";

import React, { useState } from "react";
import { Locale } from "../../lib/i18n";
import {
  CompetitionGroup,
  LibraryMatch,
  StageGroup,
  competitionLabel,
  isComplete,
  provenanceLabel,
  stageLabel,
} from "./matchLibrary";

interface MatchLibraryBrowserProps {
  competitions: CompetitionGroup[];
  stageGroups: StageGroup[];
  competition: string;
  season: string;
  seasons: { key: string; count: number }[];
  selectedId: string | null;
  currentMatchId?: string;
  locale?: Locale;
  onSelectCompetition: (competition: string) => void;
  onSelectSeason: (season: string) => void;
  onSelectMatch: (matchId: string) => void;
}

const shortDate = (value?: string | null): string => {
  if (!value) return "";
  const parts = value.split("-");
  if (parts.length !== 3) return value;
  return `${parts[2]}.${parts[1]}`;
};

export const MatchLibraryBrowser: React.FC<MatchLibraryBrowserProps> = ({
  competitions,
  stageGroups,
  competition,
  season,
  seasons,
  selectedId,
  currentMatchId,
  locale = "zh",
  onSelectCompetition,
  onSelectSeason,
  onSelectMatch,
}) => {
  const isZh = locale === "zh";
  const active = competitions.find((c) => c.key === competition);
  const [folded, setFolded] = useState<string[]>([]);

  // The year axis stays available in the "all competitions" view, where it
  // covers every season in the corpus.
  const seasonOptions = active ? active.seasons : seasons;
  const toggle = (key: string) =>
    setFolded((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));

  return (
    <div className="ml-browser">
      <nav className="ml-rail" aria-label={isZh ? "赛事类型" : "Competition"}>
        <p className="ml-rail-title">{isZh ? "赛事类型" : "Competition"}</p>
        <button
          type="button"
          className={`ml-rail-item ${competition === "" ? "active" : ""}`}
          data-testid="match-library-competition"
          data-competition=""
          aria-current={competition === "" ? "true" : undefined}
          onClick={() => onSelectCompetition("")}
        >
          <span className="ml-rail-name">{isZh ? "全部赛事" : "All competitions"}</span>
          <span className="ml-rail-count">
            {competitions.reduce((sum, c) => sum + c.count, 0)}
          </span>
        </button>
        {competitions.map((group) => (
          <button
            key={group.key}
            type="button"
            className={`ml-rail-item ${competition === group.key ? "active" : ""}`}
            data-testid="match-library-competition"
            data-competition={group.key}
            aria-current={competition === group.key ? "true" : undefined}
            onClick={() => onSelectCompetition(group.key)}
          >
            <span className="ml-rail-name">{competitionLabel(group.key, isZh)}</span>
            <span className="ml-rail-provider">{group.key}</span>
            <span className="ml-rail-count">{group.count}</span>
          </button>
        ))}
      </nav>

      <div className="ml-list">
        <div className="ml-season-row" role="group" aria-label={isZh ? "年份" : "Season"}>
          <span className="ml-season-label">{isZh ? "年份" : "Season"}</span>
          <div className="ml-season-scroll">
            <button
              type="button"
              className={`ml-season-chip ${season === "" ? "active" : ""}`}
              data-testid="match-library-season"
              data-season=""
              onClick={() => onSelectSeason("")}
            >
              {isZh ? "全部" : "All"}
            </button>
            {seasonOptions.map((entry) => (
              <button
                key={entry.key}
                type="button"
                className={`ml-season-chip ${season === entry.key ? "active" : ""}`}
                data-testid="match-library-season"
                data-season={entry.key}
                onClick={() => onSelectSeason(entry.key)}
              >
                {entry.key}
                <span className="ml-season-count">{entry.count}</span>
              </button>
            ))}
          </div>
        </div>

        {stageGroups.length === 0 && (
          <p className="ml-empty">{isZh ? "没有匹配的比赛。" : "No matches match this filter."}</p>
        )}

        {stageGroups.map((group) => {
          const isFolded = folded.includes(group.key);
          return (
            <section key={group.key} className="ml-stage">
              <h3 className="ml-stage-title">
                <button
                  type="button"
                  className="ml-stage-toggle"
                  data-testid="match-library-stage-toggle"
                  data-stage={group.key}
                  aria-expanded={!isFolded}
                  onClick={() => toggle(group.key)}
                >
                  <span className={`ml-stage-caret ${isFolded ? "folded" : ""}`} aria-hidden="true">
                    ▾
                  </span>
                  {stageLabel(group.key, isZh)}
                  <span className="ml-stage-count">{group.matches.length}</span>
                </button>
              </h3>
              {!isFolded && (
                <div className="ml-stage-rows">
                  {group.matches.map((match: LibraryMatch) => {
                    const complete = isComplete(match.completeness_status);
                    const provenance = provenanceLabel(match.provenance_kind, isZh);
                    const isSelected = match.match_id === selectedId;
                    const isCurrent = match.match_id === currentMatchId;
                    return (
                      <button
                        key={match.match_id}
                        type="button"
                        className={`ml-row ${isSelected ? "selected" : ""}`}
                        data-testid="match-card"
                        data-match-id={match.match_id}
                        data-provenance={match.provenance_kind || "synthetic"}
                        aria-current={isSelected ? "true" : undefined}
                        onClick={() => onSelectMatch(match.match_id)}
                      >
                        <span className="ml-row-date">{shortDate(match.match_date)}</span>
                        <span className="ml-row-teams">
                          <span className="ml-row-team">{match.home_team}</span>
                          <span className="ml-row-score">
                            {match.home_score ?? "-"} : {match.away_score ?? "-"}
                          </span>
                          <span className="ml-row-team">{match.away_team}</span>
                        </span>
                        <span className="ml-row-meta">
                          <span
                            data-testid="match-provenance"
                            style={{ color: provenance.color, fontWeight: 650 }}
                            title={provenance.title}
                          >
                            {provenance.text}
                          </span>
                          <span className="ml-row-events">
                            {match.events_count ?? 0} {isZh ? "事件" : "events"}
                          </span>
                          <span
                            className={`rail-chip ${complete ? "verified" : "unknown"}`}
                            title={match.completeness_status || match.coverage_level}
                          >
                            {complete
                              ? isZh ? "完整" : "Complete"
                              : isZh ? "部分样本" : "Partial"}
                          </span>
                          {isCurrent && <span className="ml-row-current">{isZh ? "当前" : "Current"}</span>}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </section>
          );
        })}
      </div>
    </div>
  );
};

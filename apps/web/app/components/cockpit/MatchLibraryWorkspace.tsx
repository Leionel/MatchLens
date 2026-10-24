"use client";

import React, { useEffect, useMemo, useState } from "react";
import { Locale } from "../../lib/i18n";
import { MatchDetailPanel } from "./MatchDetailPanel";
import { MatchLibraryBrowser } from "./MatchLibraryBrowser";
import { MatchLibraryDetail } from "./MatchLibraryDetail";
import {
  LibraryMatch,
  allSeasons,
  groupByStage,
  groupCompetitions,
} from "./matchLibrary";

interface MatchLibraryWorkspaceProps {
  currentMatchId?: string;
  locale?: Locale;
  onSelectMatch: (matchId: string) => void;
}

export const MatchLibraryWorkspace: React.FC<MatchLibraryWorkspaceProps> = ({
  currentMatchId,
  locale = "zh",
  onSelectMatch,
}) => {
  const isZh = locale === "zh";
  const [matches, setMatches] = useState<LibraryMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [competition, setCompetition] = useState("");
  const [season, setSeason] = useState("");
  // Slice C-4 combinable filters: team, provenance, coverage and date range
  // compose with the competition/season axis and the free-text search.
  const [team, setTeam] = useState("");
  const [provenance, setProvenance] = useState("");
  const [coverage, setCoverage] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detailMatchId, setDetailMatchId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetch("/api/matches")
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load matches (${res.status})`);
        return res.json();
      })
      .then((data) => {
        if (active) setMatches(data.matches || []);
      })
      .catch((e) => {
        if (active) setError((e as Error).message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  // The detail page follows the match the session is holding, so a deep link
  // into a match opens on its own record.
  useEffect(() => {
    if (currentMatchId) setSelectedId(currentMatchId);
  }, [currentMatchId]);

  const competitions = useMemo(() => groupCompetitions(matches), [matches]);
  const seasons = useMemo(() => allSeasons(matches), [matches]);

  const teamOptions = useMemo(() => {
    const seen = new Set<string>();
    for (const match of matches) {
      seen.add(match.home_team);
      seen.add(match.away_team);
    }
    return Array.from(seen).filter(Boolean).sort();
  }, [matches]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return matches.filter((match) => {
      if (competition && match.competition !== competition) return false;
      if (season && match.season !== season) return false;
      if (team && match.home_team !== team && match.away_team !== team) return false;
      if (provenance && (match.provenance_kind || "synthetic") !== provenance) return false;
      if (coverage === "complete" && match.completeness_status !== "COMPLETE_VERIFIED") return false;
      if (coverage === "partial" && match.completeness_status === "COMPLETE_VERIFIED") return false;
      if (dateFrom && (!match.match_date || match.match_date < dateFrom)) return false;
      if (dateTo && (!match.match_date || match.match_date > dateTo)) return false;
      if (!q) return true;
      return [match.label, match.home_team, match.away_team, match.competition, match.season, match.match_date || "", match.match_id]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(q);
    });
  }, [matches, competition, season, team, provenance, coverage, dateFrom, dateTo, query]);

  const hasAdvancedFilters = Boolean(team || provenance || coverage || dateFrom || dateTo);

  const stageGroups = useMemo(() => groupByStage(visible), [visible]);
  const selected = useMemo(
    () => matches.find((match) => match.match_id === selectedId) ?? null,
    [matches, selectedId],
  );

  const selectCompetition = (value: string) => {
    setCompetition(value);
    const group = competitions.find((c) => c.key === value);
    setSeason(group && !group.seasons.some((s) => s.key === season) ? "" : season);
  };

  const selectSeason = (value: string) => {
    setSeason(value);
  };

  return (
    <div className="workspace-pane-fade ml-shell">
      <section className="ml-header">
        <div className="ml-header-text">
          <h2 className="ml-title">{isZh ? "比赛库" : "Match Library"}</h2>
          <p className="ml-subtitle">
            {isZh
              ? "按赛事类型和年份进入比赛。覆盖不足的比赛会明确标注。"
              : "Enter a match by competition and year. Incomplete coverage is labeled explicitly."}
          </p>
        </div>
        <label className="ml-search">
          <span className="ml-search-label">{isZh ? "搜索球队、赛事或赛季" : "Search team, competition or season"}</span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={isZh ? "例如 France 或 2022" : "e.g. France or 2022"}
            className="ml-search-input"
          />
        </label>
      </section>

      <div className="ml-filter-row" role="group" aria-label={isZh ? "组合筛选" : "Filters"} style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "end" }}>
        <label style={{ display: "grid", gap: 4, fontSize: 12, color: "var(--text-secondary)" }}>
          {isZh ? "球队" : "Team"}
          <select
            value={team}
            onChange={(e) => setTeam(e.target.value)}
            data-testid="match-hub-team-filter"
            style={{ minHeight: 32, background: "var(--input-bg)", color: "var(--input-text)", border: "0.5px solid var(--pitch-border)", borderRadius: 6, padding: "4px 8px" }}
          >
            <option value="">{isZh ? "全部球队" : "All teams"}</option>
            {teamOptions.map((name) => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
        </label>
        <label style={{ display: "grid", gap: 4, fontSize: 12, color: "var(--text-secondary)" }}>
          {isZh ? "数据来源" : "Provenance"}
          <select
            value={provenance}
            onChange={(e) => setProvenance(e.target.value)}
            data-testid="match-hub-provenance-filter"
            style={{ minHeight: 32, background: "var(--input-bg)", color: "var(--input-text)", border: "0.5px solid var(--pitch-border)", borderRadius: 6, padding: "4px 8px" }}
          >
            <option value="">{isZh ? "全部来源" : "All provenance"}</option>
            <option value="provider_payload">{isZh ? "真实数据" : "Provider data"}</option>
            <option value="synthetic">{isZh ? "合成数据" : "Synthetic"}</option>
            <option value="provider_schema_excerpt">{isZh ? "样本摘录" : "Excerpt"}</option>
          </select>
        </label>
        <label style={{ display: "grid", gap: 4, fontSize: 12, color: "var(--text-secondary)" }}>
          {isZh ? "覆盖" : "Coverage"}
          <select
            value={coverage}
            onChange={(e) => setCoverage(e.target.value)}
            data-testid="match-hub-coverage-filter"
            style={{ minHeight: 32, background: "var(--input-bg)", color: "var(--input-text)", border: "0.5px solid var(--pitch-border)", borderRadius: 6, padding: "4px 8px" }}
          >
            <option value="">{isZh ? "全部覆盖" : "All coverage"}</option>
            <option value="complete">{isZh ? "完整" : "Complete"}</option>
            <option value="partial">{isZh ? "部分" : "Partial"}</option>
          </select>
        </label>
        <label style={{ display: "grid", gap: 4, fontSize: 12, color: "var(--text-secondary)" }}>
          {isZh ? "日期从" : "From"}
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            data-testid="match-hub-date-from"
            style={{ minHeight: 32, background: "var(--input-bg)", color: "var(--input-text)", border: "0.5px solid var(--pitch-border)", borderRadius: 6, padding: "4px 8px" }}
          />
        </label>
        <label style={{ display: "grid", gap: 4, fontSize: 12, color: "var(--text-secondary)" }}>
          {isZh ? "到" : "To"}
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            data-testid="match-hub-date-to"
            style={{ minHeight: 32, background: "var(--input-bg)", color: "var(--input-text)", border: "0.5px solid var(--pitch-border)", borderRadius: 6, padding: "4px 8px" }}
          />
        </label>
        {hasAdvancedFilters && (
          <button
            type="button"
            onClick={() => {
              setTeam("");
              setProvenance("");
              setCoverage("");
              setDateFrom("");
              setDateTo("");
            }}
            style={{ minHeight: 32, fontSize: 12 }}
          >
            {isZh ? "清除筛选" : "Clear filters"}
          </button>
        )}
      </div>

      {loading && (
        <div role="status" className="ml-empty">
          {isZh ? "正在加载比赛目录..." : "Loading match catalog..."}
        </div>
      )}
      {error && (
        <div role="alert" className="ml-error">
          {error}
        </div>
      )}

      {!loading && !error && (
        <>
          <p className="ml-count" data-testid="match-hub-count">
            {isZh
              ? `显示 ${visible.length} / ${matches.length} 场比赛`
              : `Showing ${visible.length} of ${matches.length} matches`}
          </p>

          <div className="ml-layout">
            <MatchLibraryBrowser
              competitions={competitions}
              stageGroups={stageGroups}
              competition={competition}
              season={season}
              seasons={seasons}
              selectedId={selectedId}
              currentMatchId={currentMatchId}
              locale={locale}
              onSelectCompetition={selectCompetition}
              onSelectSeason={selectSeason}
              onSelectMatch={setSelectedId}
            />
            <MatchLibraryDetail
              match={selected}
              currentMatchId={currentMatchId}
              locale={locale}
              onEnter={onSelectMatch}
              onOpenDetail={setDetailMatchId}
            />
          </div>

          {detailMatchId && (
            <section className="ml-deep-panel" data-testid="match-library-deep">
              <header className="ml-deep-head">
                <h3 className="ml-deep-title">
                  {isZh ? "比赛详情、画像与跨场对比" : "Match detail, profiles and cross-match compare"}
                </h3>
                <button
                  type="button"
                  className="ml-secondary-action"
                  data-testid="match-library-deep-close"
                  onClick={() => setDetailMatchId(null)}
                >
                  {isZh ? "收起" : "Close"}
                </button>
              </header>
              <MatchDetailPanel
                matchId={detailMatchId}
                locale={locale}
                onOpenMatch={(id) => void onSelectMatch(id)}
                onClose={() => setDetailMatchId(null)}
              />
            </section>
          )}

          <section className="ml-footnote">
            <p>
              {isZh
                ? "“完整”= 通过来源声明、分 Period 覆盖与完整性校验；跨场画像与 per-90 只统计完整覆盖的真实 provider 场次。"
                : "Complete = source declaration, period coverage and integrity checks all pass. Profiles and per-90 rates use complete-coverage provider matches only."}
            </p>
          </section>
        </>
      )}
    </div>
  );
};

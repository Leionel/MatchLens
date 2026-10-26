"use client";

import React, { useEffect, useMemo, useState } from "react";
import { Locale } from "../../lib/i18n";
import { MatchDetailPanel } from "./MatchDetailPanel";
import { MatchLibraryBrowser } from "./MatchLibraryBrowser";
import { MatchLibraryDetail } from "./MatchLibraryDetail";
import {
  LibraryMatch,
  allSeasons,
  competitionLabel,
  groupByStage,
  groupCompetitions,
  stageLabel,
} from "./matchLibrary";

interface MatchLibraryWorkspaceProps {
  currentMatchId?: string;
  locale?: Locale;
  initialQuery?: string;
  onQueryChange?: (query: string) => void;
  onSelectMatch: (matchId: string) => void;
  onInvestigateShot?: (input: { matchId: string; eventId: string; team: "H" | "N"; at: number }) => void;
  onInvestigateCrossMatch?: (input: { matchId: string; otherMatchId: string }) => void;
  onInvestigateMoment?: (input: {
    matchId: string;
    focusId: string;
    at: number;
    team: "H" | "N";
    question: string;
  }) => void;
}

interface FeaturedPayload {
  featured: {
    match_id: string;
    label: string;
    competition: string;
    season: string;
    stage?: string | null;
    match_date?: string | null;
    home_team: string;
    away_team: string;
    home_score?: number | null;
    away_score?: number | null;
    provenance_kind: string;
    data_provider: string;
    attribution_text?: string | null;
    moment: {
      change_point_id: string;
      at: number;
      minute: number;
      leading_team: "H" | "N";
      team_name: string;
      oaai_amplitude: number;
      claim_level?: number;
      disclaimer?: string;
    };
    what_changed: string;
    why_investigate: string;
    question: string;
    supporting_events: {
      event_id: string;
      minute: number;
      team: string;
      actor?: string;
      kind: string;
      outcome?: string;
      explanation?: string;
    }[];
    source: string;
  } | null;
  fallback: boolean;
  fallback_reason?: string | null;
  algorithm: string;
}

export const MatchLibraryWorkspace: React.FC<MatchLibraryWorkspaceProps> = ({
  currentMatchId,
  locale = "zh",
  initialQuery = "",
  onQueryChange,
  onSelectMatch,
  onInvestigateShot,
  onInvestigateCrossMatch,
  onInvestigateMoment,
}) => {
  const isZh = locale === "zh";
  const [matches, setMatches] = useState<LibraryMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [featured, setFeatured] = useState<FeaturedPayload | null>(null);
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
    // The featured moment is independent of the catalog list: a slow or failed
    // recommendation must never block the catalog behind it.
    fetch("/api/featured")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (active && data) setFeatured(data);
      })
      .catch(() => {
        if (active) setFeatured(null);
      });
    return () => {
      active = false;
    };
  }, []);

  // The global header search lands here with its query already applied.
  useEffect(() => {
    setQuery(initialQuery);
  }, [initialQuery]);

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
  const activeFilterCount = [team, provenance, coverage, dateFrom, dateTo].filter(Boolean).length;
  const recommended = useMemo(
    () =>
      visible
        .filter((match) => match.analysis_ready !== false)
        // A real provider payload is a stronger demo than a synthetic fixture,
        // whatever their relative event counts. Synthetic matches stay
        // available, but they never outrank a real one that is ready to open.
        .sort((a, b) => {
          const realA = (a.provenance_kind ?? "synthetic") === "provider_payload" ? 1 : 0;
          const realB = (b.provenance_kind ?? "synthetic") === "provider_payload" ? 1 : 0;
          if (realA !== realB) return realB - realA;
          return (b.events_count ?? 0) - (a.events_count ?? 0);
        })
        .slice(0, 4),
    [visible],
  );

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
      <header className="r6-page-head r6-hub-head">
        <div>
          <span className="r6-kicker">{isZh ? "MatchLens" : "MatchLens"}</span>
          <h1 className="r6-hub-value">
            {isZh ? (
              <>
                可以被质疑的足球智能。
              </>
            ) : (
              <>Football intelligence you can challenge.</>
            )}
          </h1>
          <p className="r6-hub-value-sub">
            {isZh
              ? "看清比赛时刻 · 检视每一条证据 · 质疑每一个结论。"
              : "Understand the moment. Inspect the evidence. Challenge the conclusion."}
          </p>
        </div>
        <div className="r6-hub-facts">
          <span data-testid="hub-count-real">
            <b>{loading ? "—" : matches.filter((m) => m.analysis_ready !== false && (m.provenance_kind ?? "synthetic") === "provider_payload").length}</b>
            <small>{isZh ? "真实比赛 · 可分析" : "Real matches ready"}</small>
          </span>
          <span data-testid="hub-count-synthetic">
            <b>{loading ? "—" : matches.filter((m) => m.analysis_ready !== false && (m.provenance_kind ?? "synthetic") === "synthetic").length}</b>
            <small>{isZh ? "合成情景" : "Simulated scenarios"}</small>
          </span>
          <span data-testid="hub-count-catalogued">
            <b>{loading ? "—" : matches.length}</b>
            <small>{isZh ? "已登记" : "Catalogued"}</small>
          </span>
          {currentMatchId && (
            <button type="button" className="r6-text-action" onClick={() => onSelectMatch(currentMatchId)}>
              {isZh ? "继续当前比赛 →" : "Continue current match →"}
            </button>
          )}
        </div>
      </header>

      <FeaturedInvestigation
        featured={featured}
        currentMatchId={currentMatchId}
        locale={locale}
        onExplore={(input) =>
          onInvestigateMoment?.({
            matchId: input.matchId,
            focusId: input.focusId,
            at: input.at,
            team: input.team,
            question: input.question,
          })
        }
        onOpenMatch={onSelectMatch}
      />

      <section className="r6-hub-tools" aria-label={isZh ? "搜索与筛选" : "Search and filters"}>
        <div className="r6-hub-tool-line">
          {query.trim() ? (
            <div className="r6-hub-query-chip" data-testid="match-hub-query">
              <span>{isZh ? "搜索" : "Search"}</span>
              <b>{query}</b>
              <button
                type="button"
                aria-label={isZh ? "清除搜索" : "Clear search"}
                onClick={() => {
                  setQuery("");
                  onQueryChange?.("");
                }}
              >
                ×
              </button>
            </div>
          ) : (
            <p className="r6-hub-search-hint">
              {isZh ? "使用顶部搜索框查找比赛、球队或赛事；筛选只影响下方目录。" : "Use the header search for matches, teams or competitions; filters only scope the catalog below."}
            </p>
          )}
          <details className="r6-hub-advanced" data-testid="match-hub-advanced">
            <summary>
              {isZh ? "高级筛选" : "Advanced filters"}
              {activeFilterCount > 0 ? ` (${activeFilterCount})` : ""}
            </summary>
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
          </details>
        </div>
      </section>

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
          <section className="r6-recommended" aria-labelledby="r6-recommended-title" data-testid="match-hub-recommended">
            <div className="r6-recommended-head">
              <div>
                <span className="r6-kicker">{isZh ? "推荐开始" : "Recommended"}</span>
                <h2 id="r6-recommended-title">{isZh ? "已安装、可直接分析的比赛" : "Installed and ready to analyse"}</h2>
              </div>
              <p>
                {isZh
                  ? "这些比赛的数据已就绪；已登记但未安装的场次仍保留在下方目录中。"
                  : "These datasets are installed. Catalogued matches without local data stay browsable in the full catalog below."}
              </p>
            </div>
            {recommended.length === 0 ? (
              <p className="r6-recommended-empty">
                {isZh ? "当前筛选下没有已安装的分析就绪比赛。" : "No installed, analysis-ready matches under the current filters."}
              </p>
            ) : (
              <div className="r6-recommended-grid">
                {recommended.map((match) => {
                  const isCurrent = match.match_id === currentMatchId;
                  const isDemo = (match.provenance_kind ?? "synthetic") !== "provider_payload";
                  return (
                    <article
                      key={match.match_id}
                      className={`r6-recommended-card ${isCurrent ? "current" : ""}`}
                      data-testid="match-recommended"
                      data-provenance={match.provenance_kind ?? "synthetic"}
                    >
                      <span className="r6-rec-comp">
                        {competitionLabel(match.competition, isZh)} · {match.season} · {match.stage ? stageLabel(match.stage, isZh) : "—"}
                        {isCurrent ? ` · ${isZh ? "当前" : "current"}` : ""}
                      </span>
                      <h3>
                        {match.home_team} <strong>{match.home_score ?? "-"} : {match.away_score ?? "-"}</strong> {match.away_team}
                      </h3>
                      <div className="r6-rec-meta">
                        <span className={`r6-rec-badge ${isDemo ? "demo" : ""}`}>
                          {isDemo ? (isZh ? "Demo · 合成" : "Demo · synthetic") : isZh ? "真实数据" : "Real data"}
                        </span>
                        <span>{match.events_count ?? 0} {isZh ? "事件" : "events"}</span>
                        <span>{match.match_date || "—"}</span>
                      </div>
                      <div className="r6-rec-actions">
                        <button type="button" className="r6-primary-action" onClick={() => onSelectMatch(match.match_id)}>
                          {isZh ? "进入比赛 →" : "Open match →"}
                        </button>
                        <button type="button" className="r6-text-action" onClick={() => setSelectedId(match.match_id)}>
                          {isZh ? "查看详情" : "View details"}
                        </button>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </section>

          <div className="r6-hub-catalog-head">
            <h2>{isZh ? "全部比赛目录" : "Full match catalog"}</h2>
            <p className="ml-count" data-testid="match-hub-count">
              {isZh
                ? `显示 ${visible.length} / ${matches.length} 场比赛`
                : `Showing ${visible.length} of ${matches.length} matches`}
            </p>
          </div>

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
                onInvestigateShot={onInvestigateShot}
                onInvestigateCrossMatch={onInvestigateCrossMatch}
              />
            </section>
          )}

          <section className="ml-footnote">
            <p>
              {isZh
                ? "“完整”= 通过来源声明、分 Period 覆盖与完整性校验；跨场画像与 per-90 只统计完整覆盖的真实 provider 场次。精选语料是功能验收样本，不代表无偏足球总体。"
                : "Complete = source declaration, period coverage and integrity checks all pass. Profiles and per-90 rates use complete-coverage provider matches only. The curated corpus is a functional-acceptance sample, not an unbiased football population."}
            </p>
          </section>
        </>
      )}
    </div>
  );
};

interface FeaturedInvestigationProps {
  featured: FeaturedPayload | null;
  currentMatchId?: string;
  locale?: Locale;
  onExplore: (input: { matchId: string; focusId: string; at: number; team: "H" | "N"; question: string }) => void;
  onOpenMatch: (matchId: string) => void;
}

/**
 * The first screen's one true entry point. The moment comes from
 * `/api/featured` — a deterministic pick over installed matches, not a
 * hardcoded highlight and not a model output — so the CTA always lands on a
 * real, in-clock, investigable moment.
 */
const FeaturedInvestigation: React.FC<FeaturedInvestigationProps> = ({
  featured,
  currentMatchId,
  locale = "zh",
  onExplore,
  onOpenMatch,
}) => {
  const isZh = locale === "zh";
  const moment = featured?.featured?.moment;
  const match = featured?.featured;
  const isDemo = Boolean(match && (match.provenance_kind || "synthetic") !== "provider_payload");
  const isCurrent = Boolean(match && match.match_id === currentMatchId);

  if (!featured) {
    return (
      <div className="r6-featured r6-featured-loading" aria-hidden="true">
        <span className="r6-kicker">{isZh ? "精选时刻" : "Featured investigation"}</span>
        <p>{isZh ? "正在从已安装比赛中挑选一个值得调查的时刻…" : "Selecting an investigable moment from the installed matches…"}</p>
      </div>
    );
  }

  if (!match || !moment) {
    return (
      <div className="r6-featured r6-featured-empty">
        <span className="r6-kicker">{isZh ? "精选时刻" : "Featured investigation"}</span>
        <p>
          {isZh
            ? "暂时没有可推荐的已安装时刻；请直接在下方目录中选择一场比赛。"
            : "No installed moment to recommend right now; pick a match from the catalog below."}
          {featured.fallback_reason && featured.fallback
            ? isZh
              ? `（原因：${featured.fallback_reason}）`
              : ` (Reason: ${featured.fallback_reason})`
            : ""}
        </p>
      </div>
    );
  }

  return (
    <section
      className="r6-featured"
      data-testid="featured-investigation"
      data-provenance={match.provenance_kind}
      aria-label={isZh ? "精选调查时刻" : "Featured investigation"}
    >
      <div className="r6-featured-head">
        <span className="r6-kicker">{isZh ? "精选时刻 · 一次有证据的调查" : "Featured investigation"}</span>
        <span
          className={`r6-rec-badge ${isDemo ? "demo" : ""}`}
          title={match.attribution_text || undefined}
        >
          {isDemo
            ? isZh
              ? "合成演示"
              : "Synthetic demo"
            : isZh
              ? "真实数据"
              : "Real data"}
        </span>
      </div>
      <div className="r6-featured-grid">
        <div className="r6-featured-match">
          <span className="r6-featured-comp">
            {match.competition}
            {match.stage ? ` · ${match.stage.replace(/_/g, " ")}` : ""}
            {match.match_date ? ` · ${match.match_date}` : ""}
          </span>
          <h2>
            {match.home_team} <strong>{match.home_score ?? "-"} : {match.away_score ?? "-"}</strong> {match.away_team}
          </h2>
          <p className="r6-featured-when">
            {isZh ? "时刻" : "Moment"} {moment.minute}′ · OAAI {moment.oaai_amplitude > 0 ? "+" : ""}
            {moment.oaai_amplitude.toFixed(2)} · {moment.team_name}
          </p>
        </div>
        <div className="r6-featured-story">
          <p className="r6-featured-what" data-testid="featured-what-changed">{match.what_changed}</p>
          <p className="r6-featured-why">{match.why_investigate}</p>
          {match.supporting_events.length > 0 && (
            <ul className="r6-featured-events" aria-label={isZh ? "支持事件" : "Supporting events"}>
              {match.supporting_events.map((event) => (
                <li key={event.event_id}>
                  <span className="r6-featured-event-minute">{event.minute}′</span>
                  <b>{event.actor || (isZh ? "未知球员" : "Unattributed")}</b>
                  <span>{event.kind}{event.outcome ? ` · ${event.outcome}` : ""}</span>
                </li>
              ))}
            </ul>
          )}
          <div className="r6-featured-actions">
            <button
              type="button"
              className="r6-primary-action r6-featured-cta"
              data-testid="featured-explore"
              onClick={() =>
                onExplore({
                  matchId: match.match_id,
                  focusId: "",
                  at: Math.round(moment.at),
                  team: moment.leading_team === "N" ? "N" : "H",
                  question: match.question,
                })
              }
            >
              {isZh ? `调查这个时刻 →` : "Explore this moment →"}
            </button>
            {!isCurrent && (
              <button type="button" className="r6-text-action" onClick={() => onOpenMatch(match.match_id)}>
                {isZh ? "打开比赛" : "Open match"}
              </button>
            )}
          </div>
        </div>
      </div>
      <p className="r6-featured-note">{match.source}</p>
    </section>
  );
};

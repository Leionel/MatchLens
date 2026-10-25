export type LibraryMatch = {
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
  coverage_level: string;
  completeness_status?: string | null;
  data_provider: string;
  provenance_kind?: "synthetic" | "provider_payload" | "provider_schema_excerpt";
  events_count?: number | null;
  format_seconds?: number | null;
  description?: string;
  license_ref?: string;
  attribution_text?: string | null;
  capabilities?: string[];
  continuous_coverage?: boolean;
  availability_status?: "CATALOGUED" | "MATERIALIZED" | "ANALYSIS_READY" | null;
  dataset_installed?: boolean;
  analysis_ready?: boolean;
  availability_reason?: string | null;
  install_hint?: string | null;
  verification_basis?: string | null;
  dataset_sha256?: string | null;
  dataset_path?: string | null;
  official_score_note?: string | null;
  score_reconciliation?: {
    provider_score?: string;
    recorded_goals?: string;
    consistent?: boolean;
    note?: string;
  } | null;
  completeness?: {
    status?: string;
    raw_event_count?: number;
    normalized_event_count?: number;
    conversion_drop_count?: number;
    drop_reasons?: string[];
    observed_periods?: number[];
    expected_periods?: number[];
    coverage_by_period?: {
      period: number;
      expected_start: number;
      expected_end: number;
      observed_start: number | null;
      observed_end: number | null;
      event_count: number;
      coverage: number;
      event_density_ok?: boolean;
      completeness_rule?: string;
      shootout_kicks_ok?: boolean;
    }[];
    expected_duration?: number;
    observed_start?: number | null;
    observed_end?: number | null;
    known_missing_segments?: string[];
    provider_consistency?: boolean;
    integrity_checks?: { check: string; passed: boolean; detail?: string }[];
    confidence?: number;
    notes?: string[];
  } | null;
};

/** The order rounds are shown in, from the earliest to the deciding match. */
export const STAGE_ORDER = [
  "group_stage",
  "round_of_32",
  "round_of_16",
  "quarter_final",
  "semi_final",
  "third_place",
  "final",
  "scenario",
  "other",
];

const STAGE_LABELS: Record<string, { zh: string; en: string }> = {
  group_stage: { zh: "小组赛", en: "Group stage" },
  round_of_32: { zh: "三十二强", en: "Round of 32" },
  round_of_16: { zh: "十六强", en: "Round of 16" },
  quarter_final: { zh: "八强赛", en: "Quarter-finals" },
  semi_final: { zh: "半决赛", en: "Semi-finals" },
  third_place: { zh: "三四名决赛", en: "Third place" },
  final: { zh: "决赛", en: "Final" },
  scenario: { zh: "情景", en: "Scenario" },
  other: { zh: "其他", en: "Other" },
};

export const stageLabel = (stage: string | null | undefined, isZh: boolean): string => {
  const key = stage && STAGE_LABELS[stage] ? stage : "other";
  const entry = STAGE_LABELS[key];
  return isZh ? entry.zh : entry.en;
};

/**
 * The provider's own competition name is the authoritative label. A Chinese
 * reading is offered next to it because the library is read in Chinese, but
 * the provider name is never replaced by it.
 */
const COMPETITION_LABELS: Record<string, string> = {
  "FIFA World Cup": "世界杯",
  "Copa America": "美洲杯",
  "UEFA Euro": "欧洲杯",
  "Champions League": "欧冠",
  "MatchLens Simulation League": "合成情景",
};

export const competitionLabel = (competition: string, isZh: boolean): string =>
  isZh ? COMPETITION_LABELS[competition] ?? competition : competition;

/** The leading year of a season label, so "2018/2019" sorts with 2018. */
const seasonYear = (value: string): number | null => {
  const found = value.match(/\d{4}/);
  return found ? Number(found[0]) : null;
};

/** Sort seasons newest first; a season without a year sorts last. */
export const sortSeasons = (a: string, b: string): number => {
  const na = seasonYear(a);
  const nb = seasonYear(b);
  if (na !== null && nb !== null) return nb - na;
  if (na !== null) return -1;
  if (nb !== null) return 1;
  return b.localeCompare(a);
};

export type CompetitionGroup = {
  key: string;
  count: number;
  seasons: { key: string; count: number }[];
};

/**
 * Every season in the catalog, newest first. The library offers the year axis
 * even before a competition is chosen, because the corpus spans five
 * tournaments and the year is the quickest way into it.
 */
export const allSeasons = (matches: LibraryMatch[]): { key: string; count: number }[] => {
  const counts = new Map<string, number>();
  for (const match of matches) {
    counts.set(match.season, (counts.get(match.season) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([key, count]) => ({ key, count }))
    .sort((a, b) => sortSeasons(a.key, b.key));
};

export const groupCompetitions = (matches: LibraryMatch[]): CompetitionGroup[] => {
  const byCompetition = new Map<string, LibraryMatch[]>();
  for (const match of matches) {
    const list = byCompetition.get(match.competition) ?? [];
    list.push(match);
    byCompetition.set(match.competition, list);
  }
  return Array.from(byCompetition.entries())
    .map(([key, list]) => ({
      key,
      count: list.length,
      seasons: Array.from(new Set(list.map((m) => m.season)))
        .sort(sortSeasons)
        .map((season) => ({
          key: season,
          count: list.filter((m) => m.season === season).length,
        })),
    }))
    .sort((a, b) => b.count - a.count || a.key.localeCompare(b.key));
};

export type StageGroup = { key: string; matches: LibraryMatch[] };

export const groupByStage = (matches: LibraryMatch[]): StageGroup[] => {
  const buckets = new Map<string, LibraryMatch[]>();
  for (const match of matches) {
    const key = match.stage && STAGE_LABELS[match.stage] ? match.stage : "other";
    const list = buckets.get(key) ?? [];
    list.push(match);
    buckets.set(key, list);
  }
  return Array.from(buckets.entries())
    .map(([key, list]) => ({
      key,
      matches: [...list].sort(
        (a, b) => (a.match_date ?? "").localeCompare(b.match_date ?? "") || a.match_id.localeCompare(b.match_id),
      ),
    }))
    .sort((a, b) => STAGE_ORDER.indexOf(a.key) - STAGE_ORDER.indexOf(b.key));
};

export const isComplete = (status?: string | null): boolean => status === "COMPLETE_VERIFIED";

/** How the event stream was obtained. An excerpt is never a full match. */
export const provenanceLabel = (
  kind: LibraryMatch["provenance_kind"],
  isZh: boolean,
): { text: string; color: string; title: string } => {
  if (kind === "provider_payload") {
    return {
      text: isZh ? "真实数据" : "Provider data",
      color: "var(--text-emerald)",
      title: isZh
        ? "来自数据提供方的完整比赛事件流，已通过完整性校验"
        : "Full provider event stream, verified for completeness",
    };
  }
  if (kind === "provider_schema_excerpt") {
    return {
      text: isZh ? "样本摘录" : "Sample excerpt",
      color: "var(--text-gold)",
      title: isZh
        ? "按提供方事件结构手写的片段，仅用于协议与模式校验，不是完整比赛"
        : "Hand-authored excerpt in the provider's event schema; a protocol fixture, not a full match",
    };
  }
  return {
    text: isZh ? "合成数据" : "Synthetic",
    color: "var(--text-tertiary)",
    title: isZh
      ? "由 MatchLens 合成引擎生成，用于情景推演"
      : "Generated by the MatchLens synthetic engine for scenario testing",
  };
};

export const formatClock = (seconds?: number | null): string => {
  if (!seconds || !Number.isFinite(seconds)) return "-";
  const total = Math.round(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
};

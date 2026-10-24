"use client";

import React, { useEffect, useMemo, useState } from "react";
import { Locale } from "../../lib/i18n";

/**
 * Complete Match Detail panel (Slice C-4).
 * Sections: overview / lineups / stats / shots / tactics / profiles / investigations.
 * All data comes from /api/matches/{id}/detail plus the profile endpoints; the
 * panel never invents numbers and relays every coverage/heuristic caveat.
 */

type DetailShot = {
  event_id: string;
  team: string;
  player_name?: string | null;
  minute?: number | null;
  period_label?: string | null;
  outcome?: string | null;
  is_own_goal: boolean;
  x?: number | null;
  y?: number | null;
  pre_shot_xg_heuristic?: number | null;
};

type PlayerRow = {
  player_id: string;
  player_name?: string | null;
  jersey_number?: number | null;
  position?: string | null;
};

type MatchDetail = {
  match_id: string;
  overview: {
    metadata: {
      label: string;
      competition: string;
      season: string;
      match_date?: string | null;
      home_team: string;
      away_team: string;
      home_score?: number | null;
      away_score?: number | null;
      data_provider: string;
      provenance_kind?: string;
      license_ref: string;
      events_count?: number | null;
    };
    context: {
      duration: number;
      observed_end: number;
      period: number;
      continuous_coverage: boolean;
      completeness_status?: string | null;
      dataset_revision?: string | null;
      partial_notice?: string | null;
      provenance_kind?: string;
    };
  };
  lineups: {
    home_team: string;
    away_team: string;
    starters: Record<string, PlayerRow[]>;
    substitutes: Record<string, PlayerRow[]>;
    note: string;
  };
  shots: { shots: DetailShot[]; count: number; note: string };
  stats: { as_of: number; teams: Record<string, Record<string, { value: number | string | null; status: string; unit: string }>> };
  tactics: {
    attacking_channels: Record<string, { channels: Record<string, { attacks_count: number; final_third_entries_count: number; shots_count: number; total_progression_meters: number }> }>;
    density_top_zones: { cell_id: string; name: string; home_actions_count: number; away_actions_count: number; delta_density: number; advantage: string }[];
    sequence_count: number;
  };
  events_summary: { total: number; by_action_type: Record<string, number>; full_events_endpoint: string };
  ai_insights: {
    saved_investigations: { investigation_id: string; state: string; focus_type: string; focus_id?: string | null; question: string; gate_status: string }[];
    story_endpoint: string;
    note: string;
  };
};

type ProfileMatchRow = {
  match_id: string;
  label: string;
  match_date?: string | null;
  side: string;
  opponent_name: string;
  minutes_basis_seconds: number;
  continuous_coverage: boolean;
  provenance_kind: string;
  clock_bounded_at_duration: boolean;
  metrics: Record<string, { value: number | null; status: string; unit: string; event_count: number }>;
};

type ProfileAggregate = {
  metric_id: string;
  label: string;
  unit: string;
  formula: string;
  absolute_total: number | null;
  per_90: number | null;
  per_90_basis: Record<string, unknown>;
  sample_size: number;
  per_match_mean: number | null;
  per_match_median: number | null;
  per_match_min: number | null;
  per_match_max: number | null;
  rate_status: string;
  per_match_values: { match_id: string; value: number | null; status: string }[];
};

type TeamProfile = {
  profile_kind: "team";
  team: { requested: string; provider_team_ids: string[] };
  scope: { included_matches: number; excluded: { match_id: string; reason: string }[]; window: string };
  provenance_kinds: Record<string, number>;
  matches: ProfileMatchRow[];
  aggregates: Record<string, ProfileAggregate>;
  style_dimensions: { key: string; label: string; value: number; unit: string; formula: string }[];
  style_tags: { tag: string; rule: string; basis_metric_ids: string[] }[];
  uncertainty_note: string;
  limitations: string[];
};

type PlayerProfile = {
  profile_kind: "player";
  player: { requested_id: string; name?: string | null; name_variants: Record<string, number> };
  scope: { included_matches: number; excluded: { match_id: string; reason: string }[] };
  matches: ProfileMatchRow[];
  aggregates: Record<string, ProfileAggregate>;
  minutes: { total_minutes: number; methods: Record<string, number>; method_legend: Record<string, string>; limitation: string };
  uncertainty_note: string;
  limitations: string[];
};

type InvestigationRow = {
  investigation_id: string;
  state: string;
  focus_type: string;
  focus_id?: string | null;
  question: string;
  intent: string;
  gate_status: string;
  execution_mode?: string;
  as_of: number;
  dataset_revision?: string | null;
};

type CompareResponse = {
  compared_matches: string[];
  batch_summary: {
    per_match: Record<string, {
      match_id: string;
      match_date?: string | null;
      label?: string;
      competition?: string;
      home_team: string;
      away_team: string;
      coverage: string;
      continuous_coverage: boolean;
      passes: number;
      shots: number;
      goals: number;
      passes_per_90: number | null;
      shots_per_90: number | null;
      rate_status: string;
      load_status?: string | null;
    }>;
    comparable: boolean;
    warnings: string[];
    comparability_note: string;
    metric_version: string;
  };
};

/** Cross-match compare entry: same corpus, raw totals + gated per-90 rates. */
const CompareView = ({ matchId, isZh }: { matchId: string; isZh: boolean }) => {
  const [matches, setMatches] = useState<{ match_id: string; label: string; provenance_kind?: string }[]>([]);
  const [other, setOther] = useState("");
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    fetch("/api/matches")
      .then((res) => res.json())
      .then((d) => {
        if (active) setMatches(d.matches || []);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  const runCompare = () => {
    if (!other || other === matchId) return;
    setLoading(true);
    setError("");
    setResult(null);
    fetch(`/api/matches/compare?match_ids=${encodeURIComponent(matchId)},${encodeURIComponent(other)}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(`Compare failed (${res.status})`);
        return res.json();
      })
      .then((d) => setResult(d))
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  };

  return (
    <div style={{ display: "grid", gap: 8 }}>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "end" }}>
        <label style={{ display: "grid", gap: 4, fontSize: 12, color: "var(--text-secondary)" }}>
          {isZh ? "对比另一场比赛" : "Compare with"}
          <select
            value={other}
            onChange={(e) => setOther(e.target.value)}
            data-testid="compare-match-select"
            style={{ minHeight: 32, minWidth: 260, background: "var(--input-bg)", color: "var(--input-text)", border: "0.5px solid var(--pitch-border)", borderRadius: 6, padding: "4px 8px" }}
          >
            <option value="">{isZh ? "选择比赛…" : "Select a match…"}</option>
            {matches.filter((m) => m.match_id !== matchId).map((m) => (
              <option key={m.match_id} value={m.match_id}>
                {m.label}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="mz-btn" disabled={!other || loading} onClick={runCompare}>
          {isZh ? "对比" : "Compare"}
        </button>
      </div>
      {loading && <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>{isZh ? "对比中..." : "Comparing..."}</div>}
      {error && <div role="alert" style={{ fontSize: 12, color: "var(--red-11)" }}>{error}</div>}
      {result && (
        <div style={{ display: "grid", gap: 6 }} data-testid="compare-result">
          <div style={{ fontSize: 12, color: result.batch_summary.comparable ? "var(--text-emerald)" : "var(--text-gold)" }}>
            {result.batch_summary.comparability_note}
          </div>
          {result.batch_summary.warnings.length > 0 && (
            <div style={{ fontSize: 12, color: "var(--text-gold)" }}>{result.batch_summary.warnings.join(" · ")}</div>
          )}
          <table className="tactical-table mz-table">
            <thead>
              <tr style={{ color: "var(--text-tertiary)", textAlign: "left" }}>
                <th style={{ padding: "4px 6px" }}>{isZh ? "比赛" : "Match"}</th>
                <th style={{ padding: "4px 6px" }}>{isZh ? "覆盖" : "Coverage"}</th>
                <th style={{ padding: "4px 6px" }}>{isZh ? "传球" : "Passes"}</th>
                <th style={{ padding: "4px 6px" }}>{isZh ? "射门" : "Shots"}</th>
                <th style={{ padding: "4px 6px" }}>passes/90</th>
                <th style={{ padding: "4px 6px" }}>shots/90</th>
              </tr>
            </thead>
            <tbody>
              {Object.values(result.batch_summary.per_match).map((m) => (
                <tr key={m.match_id} style={{ borderTop: "0.5px solid var(--glass-border)" }}>
                  <td style={{ padding: "4px 6px" }}>{m.match_date || m.match_id} {m.home_team}-{m.away_team}</td>
                  <td style={{ padding: "4px 6px", color: m.continuous_coverage ? "var(--text-emerald)" : "var(--text-gold)" }}>{m.coverage}</td>
                  <td style={{ padding: "4px 6px" }}>{m.passes}</td>
                  <td style={{ padding: "4px 6px" }}>{m.shots}</td>
                  <td style={{ padding: "4px 6px" }}>{m.passes_per_90 ?? "—"}</td>
                  <td style={{ padding: "4px 6px" }}>{m.shots_per_90 ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

const TABS = ["overview", "lineups", "stats", "shots", "tactics", "profiles", "investigations"] as const;
type TabId = (typeof TABS)[number];

const tabLabel = (tab: TabId, isZh: boolean): string => {
  switch (tab) {
    case "overview": return isZh ? "概览" : "Overview";
    case "lineups": return isZh ? "阵容" : "Lineups";
    case "stats": return isZh ? "统计" : "Stats";
    case "shots": return isZh ? "射门" : "Shots";
    case "tactics": return isZh ? "战术" : "Tactics";
    case "profiles": return isZh ? "跨场画像" : "Profiles";
    case "investigations": return isZh ? "已保存调查" : "Investigations";
  }
};

const valueOrUnobserved = (v: { value: number | string | null; status: string }, isZh: boolean): string => {
  if (v.value === null || v.value === undefined) {
    return v.status === "ok" ? "—" : (isZh ? "未观测" : `unobserved (${v.status})`);
  }
  return String(v.value);
};

const Section = ({ title, children, note }: { title: string; children: React.ReactNode; note?: string }) => (
  <div style={{ display: "grid", gap: 8 }}>
    <h4 style={{ margin: 0, fontSize: 13, fontWeight: 750, color: "var(--text-primary)" }}>{title}</h4>
    {children}
    {note && <p style={{ margin: 0, fontSize: 11, color: "var(--text-tertiary)", lineHeight: 1.5 }}>{note}</p>}
  </div>
);

const chipStyle: React.CSSProperties = {
  fontSize: 11,
  padding: "2px 8px",
  borderRadius: 999,
  border: "0.5px solid var(--glass-border)",
  color: "var(--text-secondary)",
};

/** Aggregate table shared by team and player profiles. */
const ProfileAggregates = ({ profile, isZh }: { profile: TeamProfile | PlayerProfile; isZh: boolean }) => {
  const rows = Object.values(profile.aggregates);
  return (
    <div style={{ display: "grid", gap: 10 }}>
      <div style={{ overflowX: "auto" }}>
        <table className="tactical-table mz-table" data-testid="profile-aggregates">
          <thead>
            <tr style={{ color: "var(--text-tertiary)", textAlign: "left" }}>
              <th style={{ padding: "4px 8px" }}>{isZh ? "指标" : "Metric"}</th>
              <th style={{ padding: "4px 8px" }}>{isZh ? "总量" : "Total"}</th>
              <th style={{ padding: "4px 8px" }}>Per 90</th>
              <th style={{ padding: "4px 8px" }}>{isZh ? "场均" : "Per match"}</th>
              <th style={{ padding: "4px 8px" }}>{isZh ? "样本" : "n"}</th>
              <th style={{ padding: "4px 8px" }}>{isZh ? "口径状态" : "Rate status"}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => (
              <tr key={a.metric_id} style={{ borderTop: "0.5px solid var(--glass-border)" }}>
                <td style={{ padding: "4px 8px", color: "var(--text-primary)" }}>
                  {a.label}
                  <span style={{ color: "var(--text-tertiary)" }}> ({a.metric_id})</span>
                </td>
                <td style={{ padding: "4px 8px" }}>
                  {a.absolute_total === null ? (isZh ? "未观测" : "unobserved") : `${a.absolute_total} ${a.unit}`}
                </td>
                <td style={{ padding: "4px 8px" }}>
                  {a.per_90 === null ? "—" : a.per_90}
                  {a.per_90 !== null && (
                    <span
                      title={JSON.stringify(a.per_90_basis)}
                      style={{ color: "var(--text-tertiary)", marginLeft: 4, cursor: "help" }}
                    >
                      ⓘ
                    </span>
                  )}
                </td>
                <td style={{ padding: "4px 8px" }}>{a.per_match_mean === null ? "—" : a.per_match_mean}</td>
                <td style={{ padding: "4px 8px" }}>{a.sample_size}</td>
                <td style={{ padding: "4px 8px", color: a.rate_status === "comparable" || a.rate_status === "comparable_mean_of_match_shares" ? "var(--text-emerald)" : "var(--text-gold)" }}>
                  {a.rate_status}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        <span style={{ ...chipStyle, color: "var(--text-gold)" }}>
          {isZh ? "无置信区间/p值：仅报告逐场分布" : "No CI / p-value: per-match distribution only"}
        </span>
        {("style_tags" in profile) && profile.style_tags.map((t) => (
          <span key={t.tag} style={chipStyle} title={t.rule}>
            {t.tag}
          </span>
        ))}
        {("minutes" in profile) && (
          <span style={chipStyle}>
            {isZh ? "总分钟" : "Minutes"}: {profile.minutes.total_minutes}
            {" · "}
            {Object.entries(profile.minutes.methods).map(([k, v]) => `${k}=${v}`).join(", ")}
          </span>
        )}
      </div>
      <details className="mz-enter-late" style={{ fontSize: 12, color: "var(--text-secondary)" }}>
        <summary className="mz-summary" style={{ fontWeight: 650 }}>
          {isZh ? "口径与限制（展开）" : "Basis and limitations (expand)"}
        </summary>
        <ul style={{ margin: "6px 0 0", paddingLeft: 18, lineHeight: 1.6 }}>
          {profile.limitations.map((l, i) => <li key={i}>{l}</li>)}
          <li>{profile.uncertainty_note}</li>
        </ul>
      </details>
    </div>
  );
};

const ProfileView = ({ detail, isZh }: { detail: MatchDetail; isZh: boolean }) => {
  const teams = useMemo(
    () => [
      { name: detail.overview.metadata.home_team },
      { name: detail.overview.metadata.away_team },
    ],
    [detail],
  );
  const [team, setTeam] = useState(teams[0].name);
  const [profile, setProfile] = useState<TeamProfile | null>(null);
  const [playerProfile, setPlayerProfile] = useState<PlayerProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    setProfile(null);
    setPlayerProfile(null);
    fetch(`/api/profiles/team?team=${encodeURIComponent(team)}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(await res.text() || `Profile failed (${res.status})`);
        return res.json();
      })
      .then((data) => {
        if (active) setProfile(data);
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
  }, [team]);

  const openPlayer = async (playerId: string) => {
    if (!profile) return;
    setLoading(true);
    setError("");
    setPlayerProfile(null);
    try {
      const matchIds = profile.matches.map((m) => m.match_id).join(",");
      const res = await fetch(`/api/profiles/player?player_id=${encodeURIComponent(playerId)}&match_ids=${encodeURIComponent(matchIds)}`);
      if (!res.ok) throw new Error(await res.text() || `Player profile failed (${res.status})`);
      setPlayerProfile(await res.json());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  // Top players across the profiled matches (by event volume) as navigation
  // into player profiles; names and ids come from the provider payloads.
  const [players, setPlayers] = useState<{ player_id: string; name: string; event_count: number }[] | null>(null);
  useEffect(() => {
    if (playerProfile) return;
    let active = true;
    const matchIds = profile?.matches.map((m) => m.match_id).join(",");
    setPlayers(null);
    if (!matchIds) return;
    fetch(`/api/profiles/players?match_ids=${encodeURIComponent(matchIds)}&limit=12`)
      .then((res) => (res.ok ? res.json() : null))
      .then((d) => {
        if (active && d) setPlayers(d.players || []);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [profile, playerProfile]);

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
          {isZh ? "选择球队（仅统计真实 provider 场次）" : "Team (provider matches only)"}
        </span>
        {teams.map((t) => (
          <button
            key={t.name}
            type="button"
            data-testid="profile-team-switch"
            onClick={() => setTeam(t.name)}
            className={`mz-tab ${team === t.name ? "active" : ""}`}
          >
            {t.name}
          </button>
        ))}
      </div>
      {loading && <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>{isZh ? "聚合中（首场加载较慢）..." : "Aggregating (first load is slower)..."}</div>}
      {error && <div role="alert" style={{ fontSize: 12, color: "var(--red-11)" }}>{error}</div>}
      {profile && !playerProfile && (
        <>
          <ProfileAggregates profile={profile} isZh={isZh} />
          {players && players.length > 0 && (
            <div style={{ display: "grid", gap: 6 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)" }}>
                {isZh ? "球员画像入口（按事件量排序）" : "Player profiles (by event volume)"}
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {players.map((p) => (
                  <button
                    key={p.player_id}
                    type="button"
                    data-testid="profile-player-entry"
                    onClick={() => void openPlayer(p.player_id)}
                    className="mz-btn"
                    title={`${p.event_count} events`}
                  >
                    {p.name}
                  </button>
                ))}
              </div>
            </div>
          )}
          <div style={{ display: "grid", gap: 6 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)" }}>
              {isZh ? "逐场明细" : "Per-match rows"}
            </div>
            {profile.matches.map((m) => (
              <details key={m.match_id} style={{ border: "0.5px solid var(--glass-border)", borderRadius: 6, padding: 8, fontSize: 12 }}>
                <summary style={{ cursor: "pointer", display: "flex", gap: 8, flexWrap: "wrap", alignItems: "baseline" }}>
                  <b>{m.match_date || m.match_id}</b>
                  <span style={{ color: "var(--text-secondary)" }}>{m.label}</span>
                  <span style={{ color: m.continuous_coverage ? "var(--text-emerald)" : "var(--text-gold)" }}>
                    {m.continuous_coverage ? (isZh ? "覆盖完整" : "complete") : (isZh ? "部分覆盖" : "partial")}
                  </span>
                  {m.clock_bounded_at_duration && (
                    <span style={{ color: "var(--text-gold)" }} title={isZh ? "快照冻结于名义时长，加时/补时未计入" : "frozen at nominal duration; ET/stoppage excluded"}>
                      {isZh ? "时钟有界" : "clock bounded"}
                    </span>
                  )}
                </summary>
                <div style={{ display: "grid", gap: 4, marginTop: 6 }}>
                  {Object.entries(m.metrics).map(([metricId, mv]) => (
                    <div key={metricId} style={{ display: "flex", justifyContent: "space-between", gap: 8, color: "var(--text-secondary)" }}>
                      <span>{metricId}</span>
                      <span style={{ fontFamily: "var(--font-mono)" }}>
                        {mv.value === null ? mv.status : `${mv.value} ${mv.unit}`} ({mv.event_count} ev)
                      </span>
                    </div>
                  ))}
                </div>
              </details>
            ))}
          </div>
        </>
      )}
      {playerProfile && (
        <div style={{ display: "grid", gap: 8 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <b style={{ fontSize: 13 }}>
              {isZh ? "球员画像" : "Player profile"}: {playerProfile.player.name || playerProfile.player.requested_id}
            </b>
            <button type="button" className="mz-btn" onClick={() => setPlayerProfile(null)}>
              {isZh ? "返回球队画像" : "Back to team"}
            </button>
          </div>
          <ProfileAggregates profile={playerProfile} isZh={isZh} />
        </div>
      )}
    </div>
  );
};

const InvestigationsView = ({ matchId, isZh }: { matchId: string; isZh: boolean }) => {
  const [rows, setRows] = useState<InvestigationRow[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    fetch(`/api/investigations?match_id=${encodeURIComponent(matchId)}&limit=50`)
      .then(async (res) => {
        if (!res.ok) throw new Error(`Failed (${res.status})`);
        return res.json();
      })
      .then((d) => {
        if (active) setRows(d.investigations || []);
      })
      .catch((e) => {
        if (active) setError((e as Error).message);
      });
    return () => {
      active = false;
    };
  }, [matchId]);

  if (error) return <div role="alert" style={{ fontSize: 12, color: "var(--red-11)" }}>{error}</div>;
  if (!rows) return <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>{isZh ? "加载中..." : "Loading..."}</div>;
  if (rows.length === 0) {
    return (
      <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
        {isZh ? "该比赛还没有已保存的调查。在比赛中发起调查后会出现在这里。" : "No saved investigations for this match yet."}
      </div>
    );
  }
  return (
    <div style={{ display: "grid", gap: 6 }}>
      {rows.map((r) => (
        <div key={r.investigation_id} style={{ border: "0.5px solid var(--glass-border)", borderRadius: 6, padding: 10, display: "grid", gap: 4, fontSize: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
            <b style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>{r.investigation_id}</b>
            <span style={{ color: r.state === "APPROVED" ? "var(--text-emerald)" : r.state === "WITHHELD" || r.state === "FAILED" ? "var(--red-11)" : "var(--text-gold)" }}>
              {r.state} · gate {r.gate_status} · {r.execution_mode || "deterministic"}
            </span>
          </div>
          <div style={{ color: "var(--text-secondary)" }}>
            {r.focus_type}{r.focus_id ? `: ${r.focus_id}` : ""} · @{r.as_of}s · {r.intent}
          </div>
          {r.question && <div style={{ color: "var(--text-secondary)", lineHeight: 1.5 }}>{r.question}</div>}
        </div>
      ))}
    </div>
  );
};

interface MatchDetailPanelProps {
  matchId: string;
  locale?: Locale;
  onOpenMatch: (matchId: string) => void;
  onClose: () => void;
}

export const MatchDetailPanel: React.FC<MatchDetailPanelProps> = ({ matchId, locale = "zh", onOpenMatch, onClose }) => {
  const isZh = locale === "zh";
  const [detail, setDetail] = useState<MatchDetail | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<TabId>("overview");

  useEffect(() => {
    let active = true;
    setDetail(null);
    setError("");
    setTab("overview");
    fetch(`/api/matches/${encodeURIComponent(matchId)}/detail`)
      .then(async (res) => {
        if (!res.ok) throw new Error(await res.text() || `Detail failed (${res.status})`);
        return res.json();
      })
      .then((d) => {
        if (active) setDetail(d);
      })
      .catch((e) => {
        if (active) setError((e as Error).message);
      });
    return () => {
      active = false;
    };
  }, [matchId]);

  const meta = detail?.overview.metadata;
  const ctx = detail?.overview.context;

  return (
    <div
      className="mz-enter"
      data-testid="match-detail-panel"
      style={{
        border: "1px solid var(--turf-emerald)",
        borderRadius: 10,
        background: "color-mix(in srgb, var(--slate-1) 88%, transparent)",
        padding: 16,
        display: "grid",
        gap: 12,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "baseline" }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 800 }}>{meta ? meta.label : matchId}</h3>
          {meta && (
            <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 4 }}>
              {meta.competition} {meta.season} · {meta.match_date || "—"} · {meta.home_team} {meta.home_score ?? "-"} : {meta.away_score ?? "-"} {meta.away_team}
            </div>
          )}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button type="button" className="mz-btn mz-btn-primary" onClick={() => onOpenMatch(matchId)}>
            {isZh ? "进入比赛分析" : "Open in cockpit"}
          </button>
          <button type="button" className="mz-btn" onClick={onClose} aria-label={isZh ? "关闭详情" : "Close detail"}>
            ✕
          </button>
        </div>
      </div>

      {error && <div role="alert" style={{ fontSize: 12, color: "var(--red-11)" }}>{error}</div>}
      {!detail && !error && <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>{isZh ? "加载比赛详情..." : "Loading match detail..."}</div>}

      {detail && (
        <>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {TABS.map((t) => (
              <button
                key={t}
                type="button"
                className={`mz-tab ${tab === t ? "active" : ""}`}
                data-testid={`detail-tab-${t}`}
                onClick={() => setTab(t)}
              >
                {tabLabel(t, isZh)}
              </button>
            ))}
          </div>

          {ctx && (
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              <span style={{ ...chipStyle, color: ctx.continuous_coverage ? "var(--text-emerald)" : "var(--text-gold)" }}>
                {ctx.continuous_coverage ? (isZh ? "覆盖已验证" : "coverage verified") : (ctx.completeness_status || "partial")}
              </span>
              <span style={chipStyle}>
                {isZh ? "观测至" : "observed to"} {Math.round(ctx.observed_end)}s / {ctx.duration}s
              </span>
              <span style={chipStyle}>{detail.events_summary.total} {isZh ? "事件" : "events"}</span>
              <span style={chipStyle} title={ctx.dataset_revision || ""}>
                {isZh ? "数据版本" : "revision"}: {(ctx.dataset_revision || "—").slice(0, 12)}…
              </span>
            </div>
          )}
          {ctx?.partial_notice && (
            <div style={{ fontSize: 12, color: "var(--text-gold)", lineHeight: 1.5 }}>{ctx.partial_notice}</div>
          )}

          <div style={{ display: "grid", gap: 14 }}>
            {tab === "overview" && meta && ctx && (
              <Section title={isZh ? "概览" : "Overview"} note={meta.license_ref}>
                <div style={{ display: "grid", gap: 4, fontSize: 12, color: "var(--text-secondary)" }}>
                  <span>{isZh ? "数据来源" : "Data provider"}: {meta.data_provider} ({meta.provenance_kind})</span>
                  <span>{isZh ? "完整度" : "Completeness"}: {ctx.completeness_status || "—"}</span>
                  <span>{isZh ? "License" : "License"}: {meta.license_ref}</span>
                </div>
              </Section>
            )}

            {tab === "lineups" && detail && (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 12 }}>
                {(["H", "N"] as const).map((side) => (
                  <div key={side} style={{ border: "0.5px solid var(--glass-border)", borderRadius: 8, padding: 10, display: "grid", gap: 6 }}>
                    <b style={{ fontSize: 13 }}>{side === "H" ? detail.lineups.home_team : detail.lineups.away_team}</b>
                    <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>{isZh ? "首发" : "Starters"}</div>
                    {detail.lineups.starters[side].map((p) => (
                      <div key={p.player_id} style={{ display: "flex", justifyContent: "space-between", gap: 6, fontSize: 12 }}>
                        <span>{p.jersey_number ? `${p.jersey_number}. ` : ""}{p.player_name}</span>
                        <span style={{ color: "var(--text-tertiary)" }}>{p.position || ""}</span>
                      </div>
                    ))}
                    <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 4 }}>{isZh ? "替补" : "Substitutes"}</div>
                    {detail.lineups.substitutes[side].map((p) => (
                      <div key={p.player_id} style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                        {p.jersey_number ? `${p.jersey_number}. ` : ""}{p.player_name}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            )}

            {tab === "stats" && detail && (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 12 }}>
                {(["H", "N"] as const).map((side) => (
                  <div key={side} style={{ border: "0.5px solid var(--glass-border)", borderRadius: 8, padding: 10, display: "grid", gap: 6 }}>
                    <b style={{ fontSize: 13 }}>{side === "H" ? detail.lineups.home_team : detail.lineups.away_team}</b>
                    {Object.entries(detail.stats.teams[side]).map(([mid, v]) => (
                      <div key={mid} style={{ display: "flex", justifyContent: "space-between", gap: 6, fontSize: 12 }}>
                        <span style={{ color: "var(--text-secondary)" }}>{mid}</span>
                        <span style={{ fontFamily: "var(--font-mono)" }}>
                          {valueOrUnobserved(v, isZh)} {v.value !== null ? v.unit : ""}
                        </span>
                      </div>
                    ))}
                    <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
                      {isZh ? "口径：全观测前缀 (0, as_of]，Registry 公式" : "Basis: observed prefix (0, as_of], registry formulas"}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {tab === "shots" && detail && (
              <Section title={`${isZh ? "射门" : "Shots"} (${detail.shots.count})`} note={detail.shots.note}>
                <div style={{ overflowX: "auto" }}>
                  <table className="tactical-table mz-table">
                    <thead>
                      <tr style={{ color: "var(--text-tertiary)", textAlign: "left" }}>
                        <th style={{ padding: "4px 6px" }}>min</th>
                        <th style={{ padding: "4px 6px" }}>{isZh ? "球员" : "Player"}</th>
                        <th style={{ padding: "4px 6px" }}>{isZh ? "球队" : "Team"}</th>
                        <th style={{ padding: "4px 6px" }}>{isZh ? "结果" : "Outcome"}</th>
                        <th style={{ padding: "4px 6px" }}>(x, y)</th>
                        <th style={{ padding: "4px 6px" }}>{isZh ? "几何 xG*" : "Geom. xG*"}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.shots.shots.map((s) => (
                        <tr key={s.event_id} style={{ borderTop: "0.5px solid var(--glass-border)" }}>
                          <td style={{ padding: "4px 6px" }}>{s.minute ?? "—"}</td>
                          <td style={{ padding: "4px 6px" }}>{s.player_name || "—"}{s.is_own_goal ? (isZh ? "（乌龙）" : " (OG)") : ""}</td>
                          <td style={{ padding: "4px 6px" }}>{s.team === "H" ? detail.lineups.home_team : detail.lineups.away_team}</td>
                          <td style={{ padding: "4px 6px", color: s.outcome === "goal" ? "var(--text-emerald)" : "var(--text-secondary)" }}>{s.outcome || "—"}</td>
                          <td style={{ padding: "4px 6px", fontFamily: "var(--font-mono)" }}>{s.x != null ? `(${s.x}, ${s.y})` : "—"}</td>
                          <td style={{ padding: "4px 6px", fontFamily: "var(--font-mono)" }}>{s.pre_shot_xg_heuristic ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Section>
            )}

            {tab === "tactics" && detail && (
              <div style={{ display: "grid", gap: 12 }}>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 12 }}>
                  {(["H", "N"] as const).map((side) => (
                    <div key={side} style={{ border: "0.5px solid var(--glass-border)", borderRadius: 8, padding: 10 }}>
                      <b style={{ fontSize: 13 }}>{side === "H" ? detail.lineups.home_team : detail.lineups.away_team}</b>
                      <table className="tactical-table mz-table" style={{ marginTop: 6 }}>
                        <thead>
                          <tr style={{ color: "var(--text-tertiary)", textAlign: "left" }}>
                            <th style={{ padding: "3px 6px" }}>{isZh ? "通道" : "Channel"}</th>
                            <th style={{ padding: "3px 6px" }}>{isZh ? "进攻" : "Attacks"}</th>
                            <th style={{ padding: "3px 6px" }}>{isZh ? "进入三区" : "Final 3rd"}</th>
                            <th style={{ padding: "3px 6px" }}>{isZh ? "射门" : "Shots"}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(detail.tactics.attacking_channels[side].channels).map(([ch, data]) => (
                            <tr key={ch} style={{ borderTop: "0.5px solid var(--glass-border)" }}>
                              <td style={{ padding: "3px 6px" }}>{ch}</td>
                              <td style={{ padding: "3px 6px" }}>{data.attacks_count}</td>
                              <td style={{ padding: "3px 6px" }}>{data.final_third_entries_count}</td>
                              <td style={{ padding: "3px 6px" }}>{data.shots_count}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ))}
                </div>
                <Section title={isZh ? "密度差分最大的区域" : "Largest density differentials"} note={isZh ? "占比差分描述空间倾向，不代表真实争夺强度。" : "Share differentials describe spatial tendency, not contest intensity."}>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {detail.tactics.density_top_zones.map((z) => (
                      <span key={z.cell_id} style={chipStyle}>
                        {z.name}: Δ{z.delta_density > 0 ? "+" : ""}{z.delta_density} ({z.advantage})
                      </span>
                    ))}
                  </div>
                </Section>
              </div>
            )}

            {tab === "profiles" && detail && (
              <div style={{ display: "grid", gap: 16 }}>
                <ProfileView detail={detail} isZh={isZh} />
                <Section
                  title={isZh ? "跨场对比" : "Cross-match compare"}
                  note={isZh ? "原始总量始终列出；per-90 仅在覆盖与时长可比时给出。" : "Raw totals always shown; per-90 only when coverage and duration align."}
                >
                  <CompareView matchId={detail.match_id} isZh={isZh} />
                </Section>
              </div>
            )}

            {tab === "investigations" && detail && <InvestigationsView matchId={detail.match_id} isZh={isZh} />}
          </div>
        </>
      )}
    </div>
  );
};

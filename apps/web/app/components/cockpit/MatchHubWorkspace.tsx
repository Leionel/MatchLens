"use client";

import React, { useEffect, useMemo, useState } from "react";
import { Locale } from "../../lib/i18n";

type MatchSummary = {
  match_id: string;
  label: string;
  competition: string;
  season: string;
  home_team: string;
  away_team: string;
  home_score?: number | null;
  away_score?: number | null;
  coverage_level: string;
  completeness_status?: string | null;
  data_provider: string;
  events_count?: number | null;
  description?: string;
};

interface MatchHubWorkspaceProps {
  currentMatchId?: string;
  locale?: Locale;
  onSelectMatch: (matchId: string) => void;
}

const isComplete = (status?: string | null) => status === "COMPLETE_VERIFIED";

export const MatchHubWorkspace: React.FC<MatchHubWorkspaceProps> = ({
  currentMatchId,
  locale = "zh",
  onSelectMatch,
}) => {
  const isZh = locale === "zh";
  const [matches, setMatches] = useState<MatchSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");

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

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return matches;
    return matches.filter((match) =>
      [match.label, match.home_team, match.away_team, match.competition, match.season]
        .join(" ")
        .toLowerCase()
        .includes(q)
    );
  }, [matches, query]);

  return (
    <div className="workspace-pane-fade" style={{ display: "grid", gap: 16 }}>
      <section className="glass-panel" style={{ padding: 18, display: "grid", gap: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap", alignItems: "end" }}>
          <div>
            <h2 style={{ fontSize: 18, fontWeight: 800, margin: 0 }}>
              {isZh ? "比赛库" : "Match Hub"}
            </h2>
            <p style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 4 }}>
              {isZh
                ? "从比赛列表进入分析。覆盖不足的比赛会明确标注。"
                : "Enter a match from the list. Incomplete coverage is labeled explicitly."}
            </p>
          </div>
          <label style={{ display: "grid", gap: 4, fontSize: 12, color: "var(--text-secondary)", minWidth: 240 }}>
            {isZh ? "搜索球队、赛事或赛季" : "Search team, competition or season"}
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={isZh ? "例如 France 或 2022" : "e.g. France or 2022"}
              style={{
                minHeight: 34,
                background: "var(--input-bg)",
                color: "var(--input-text)",
                border: "0.5px solid var(--pitch-border)",
                borderRadius: 6,
                padding: "4px 8px",
              }}
            />
          </label>
        </div>

        {loading && (
          <div role="status" style={{ padding: 24, color: "var(--text-tertiary)", fontSize: 14 }}>
            {isZh ? "正在加载比赛目录..." : "Loading match catalog..."}
          </div>
        )}
        {error && (
          <div role="alert" style={{ padding: 12, color: "var(--red-11)", fontSize: 12 }}>
            {error}
          </div>
        )}
        {!loading && !error && filtered.length === 0 && (
          <div style={{ padding: 24, color: "var(--text-tertiary)", fontSize: 14 }}>
            {isZh ? "没有匹配的比赛。" : "No matches match this search."}
          </div>
        )}

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(min(300px, 100%), 1fr))",
            gap: 12,
          }}
        >
          {filtered.map((match) => {
            const active = match.match_id === currentMatchId;
            const complete = isComplete(match.completeness_status);
            return (
              <button
                key={match.match_id}
                type="button"
                onClick={() => onSelectMatch(match.match_id)}
                style={{
                  textAlign: "left",
                  minHeight: 132,
                  padding: 14,
                  borderRadius: 8,
                  border: active
                    ? "1px solid var(--turf-emerald)"
                    : "0.5px solid var(--glass-border)",
                  background: active
                    ? "color-mix(in srgb, var(--green-9) 8%, var(--slate-1))"
                    : "color-mix(in srgb, var(--slate-1) 70%, transparent)",
                  color: "var(--text-primary)",
                  cursor: "pointer",
                  display: "grid",
                  gap: 8,
                  alignContent: "start",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "baseline" }}>
                  <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
                    {match.competition} {match.season}
                  </span>
                  <span
                    className={`rail-chip ${complete ? "verified" : "unknown"}`}
                    style={{ fontSize: 12 }}
                    title={match.completeness_status || match.coverage_level}
                  >
                    {complete
                      ? isZh ? "完整" : "Complete"
                      : isZh ? "部分样本" : "Partial"}
                  </span>
                </div>
                <div style={{ fontSize: 18, fontWeight: 750, lineHeight: 1.25 }}>
                  {match.home_team} {match.home_score ?? "-"} : {match.away_score ?? "-"} {match.away_team}
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8, fontSize: 12, color: "var(--text-tertiary)" }}>
                  <span>{match.data_provider}</span>
                  <span>{match.events_count ?? 0} {isZh ? "事件" : "events"}</span>
                </div>
                <span style={{ fontSize: 12, color: active ? "var(--text-emerald)" : "var(--text-secondary)", fontWeight: 700 }}>
                  {active ? (isZh ? "当前比赛" : "Current match") : isZh ? "进入比赛" : "Open match"}
                </span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="glass-panel" style={{ padding: 14, display: "grid", gap: 6 }}>
        <h3 style={{ fontSize: 14, fontWeight: 750, margin: 0 }}>
          {isZh ? "数据完整性提示" : "Data completeness"}
        </h3>
        <p style={{ fontSize: 12, color: "var(--text-secondary)", margin: 0, lineHeight: 1.5 }}>
          {isZh
            ? "只有通过来源声明、分 Period 覆盖和完整性检查的比赛才标记为完整。稀疏样本不会被当作完整比赛。"
            : "Only datasets that pass source declaration, period coverage and integrity checks are marked complete. Sparse samples are never treated as full matches."}
        </p>
      </section>
    </div>
  );
};

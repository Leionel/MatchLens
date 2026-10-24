"use client";

import React, { useEffect, useState } from "react";
import { Locale } from "../../lib/i18n";
import {
  LibraryMatch,
  competitionLabel,
  formatClock,
  isComplete,
  provenanceLabel,
  stageLabel,
} from "./matchLibrary";

type DetailTab = "overview" | "coverage" | "source";

interface MatchLibraryDetailProps {
  match: LibraryMatch | null;
  currentMatchId?: string;
  locale?: Locale;
  onEnter: (matchId: string) => void;
  onOpenDetail: (matchId: string) => void;
}

const Row: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div className="ml-detail-row">
    <span className="ml-detail-label">{label}</span>
    <span className="ml-detail-value">{value}</span>
  </div>
);

export const MatchLibraryDetail: React.FC<MatchLibraryDetailProps> = ({
  match,
  currentMatchId,
  locale = "zh",
  onEnter,
  onOpenDetail,
}) => {
  const isZh = locale === "zh";
  const [tab, setTab] = useState<DetailTab>("overview");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setCopied(false);
  }, [match?.match_id]);

  if (!match) {
    return (
      <aside
        className="ml-detail glass-panel"
        aria-label={isZh ? "比赛详情" : "Match detail"}
        data-testid="match-library-detail"
      >
        <p className="ml-empty">
          {isZh
            ? "从左侧选择一场比赛，这里会显示它的完整档案。"
            : "Pick a match on the left to open its full record."}
        </p>
      </aside>
    );
  }

  const complete = isComplete(match.completeness_status);
  const provenance = provenanceLabel(match.provenance_kind, isZh);
  const report = match.completeness ?? null;
  const isCurrent = match.match_id === currentMatchId;

  const copyLink = async () => {
    const url = `${window.location.origin}/?workspace=match_center&match=${encodeURIComponent(match.match_id)}&at=0`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  const tabs: { id: DetailTab; label: string }[] = [
    { id: "overview", label: isZh ? "概览" : "Overview" },
    { id: "coverage", label: isZh ? "覆盖" : "Coverage" },
    { id: "source", label: isZh ? "来源" : "Source" },
  ];

  return (
    <aside
      className="ml-detail glass-panel"
      aria-label={isZh ? "比赛详情" : "Match detail"}
      data-testid="match-library-detail"
    >
      <header className="ml-detail-head">
        <span className="ml-detail-kicker">
          {competitionLabel(match.competition, isZh)} · {match.season} ·{" "}
          {stageLabel(match.stage, isZh)}
        </span>
        <h3 className="ml-detail-title">
          {match.home_team} {match.home_score ?? "-"} : {match.away_score ?? "-"} {match.away_team}
        </h3>
        <div className="ml-detail-head-meta">
          <span
            data-testid="match-provenance"
            style={{ color: provenance.color, fontWeight: 650 }}
            title={provenance.title}
          >
            {provenance.text}
          </span>
          <span className={`rail-chip ${complete ? "verified" : "unknown"}`}>
            {match.completeness_status || match.coverage_level}
          </span>
          {match.match_date && <span className="ml-detail-date">{match.match_date}</span>}
        </div>
      </header>

      <div className="ml-detail-tabs" role="tablist">
        {tabs.map((entry) => (
          <button
            key={entry.id}
            type="button"
            role="tab"
            aria-selected={tab === entry.id}
            className={`ml-detail-tab ${tab === entry.id ? "active" : ""}`}
            data-testid={`match-library-tab-${entry.id}`}
            onClick={() => setTab(entry.id)}
          >
            {entry.label}
          </button>
        ))}
      </div>

      <div className="ml-detail-body" role="tabpanel">
        {tab === "overview" && (
          <>
            <Row
              label={isZh ? "事件数" : "Events"}
              value={`${match.events_count ?? 0}`}
            />
            <Row
              label={isZh ? "标称时长" : "Nominal length"}
              value={formatClock(match.format_seconds)}
            />
            {match.official_score_note && (
              <p className="ml-detail-note">{match.official_score_note}</p>
            )}
            {match.description && <p className="ml-detail-text">{match.description}</p>}
          </>
        )}

        {tab === "coverage" && (
          <>
            {!report && (
              <p className="ml-detail-text">
                {isZh
                  ? "这场比赛没有完整性报告：它不是提供方的完整载荷。"
                  : "This match carries no completeness report: it is not a full provider payload."}
              </p>
            )}
            {report && (
              <>
                <Row
                  label={isZh ? "状态" : "Status"}
                  value={report.status || match.completeness_status || "-"}
                />
                <Row
                  label={isZh ? "原始 / 转换后事件" : "Raw / normalized events"}
                  value={`${report.raw_event_count ?? 0} / ${report.normalized_event_count ?? 0}`}
                />
                <Row
                  label={isZh ? "转换丢弃" : "Conversion drops"}
                  value={`${report.conversion_drop_count ?? 0}`}
                />
                <Row
                  label={isZh ? "观察到的半场" : "Observed periods"}
                  value={(report.observed_periods ?? []).join(", ") || "-"}
                />
                <Row
                  label={isZh ? "观测跨度" : "Observed span"}
                  value={`${formatClock(report.observed_start)} → ${formatClock(report.observed_end)}`}
                />
                <table className="ml-detail-table">
                  <thead>
                    <tr>
                      <th>{isZh ? "半场" : "Period"}</th>
                      <th>{isZh ? "事件" : "Events"}</th>
                      <th>{isZh ? "覆盖率" : "Coverage"}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(report.coverage_by_period ?? []).map((row) => (
                      <tr key={row.period}>
                        <td>{row.period}</td>
                        <td>{row.event_count}</td>
                        <td>
                          {Math.round((row.coverage ?? 0) * 100)}%
                          {row.event_density_ok === false && (
                            <span className="ml-detail-warn"> · {isZh ? "密度偏低" : "low density"}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {(report.known_missing_segments ?? []).length > 0 && (
                  <p className="ml-detail-note">
                    {(report.known_missing_segments ?? []).join("; ")}
                  </p>
                )}
                {(report.integrity_checks ?? []).length > 0 && (
                  <ul className="ml-detail-checks">
                    {(report.integrity_checks ?? []).map((check) => (
                      <li key={check.check} className={check.passed ? "passed" : "failed"}>
                        <span className="ml-check-mark">{check.passed ? "✓" : "✗"}</span>
                        <span className="ml-check-name">{check.check}</span>
                        {check.detail && <span className="ml-check-detail">{check.detail}</span>}
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </>
        )}

        {tab === "source" && (
          <>
            <Row label={isZh ? "数据提供方" : "Provider"} value={match.data_provider} />
            <Row
              label={isZh ? "获取方式" : "Obtained as"}
              value={
                <span style={{ color: provenance.color, fontWeight: 650 }}>{provenance.text}</span>
              }
            />
            <Row label="match_id" value={<code>{match.match_id}</code>} />
            {match.score_reconciliation && (
              <Row
                label={isZh ? "比分核对" : "Score reconciliation"}
                value={
                  <>
                    {match.score_reconciliation.provider_score} /{" "}
                    {match.score_reconciliation.recorded_goals}
                    <span className="ml-detail-sub">
                      {match.score_reconciliation.consistent
                        ? isZh ? "提供方与事件流一致" : "provider and event stream agree"
                        : isZh ? "提供方与事件流不一致" : "provider and event stream disagree"}
                    </span>
                  </>
                }
              />
            )}
            {(match.capabilities ?? []).length > 0 && (
              <Row
                label={isZh ? "能力" : "Capabilities"}
                value={(match.capabilities ?? []).join(" · ")}
              />
            )}
            {match.license_ref && (
              <p className="ml-detail-text">
                <strong>{isZh ? "许可" : "Licence"}: </strong>
                {match.license_ref}
              </p>
            )}
            {match.attribution_text && (
              <p className="ml-detail-text">
                <strong>{isZh ? "署名要求" : "Attribution"}: </strong>
                {match.attribution_text}
              </p>
            )}
          </>
        )}
      </div>

      <footer className="ml-detail-actions">
        <button
          type="button"
          className="ml-primary-action"
          data-testid="match-library-enter"
          disabled={isCurrent}
          onClick={() => onEnter(match.match_id)}
        >
          {isCurrent
            ? isZh ? "当前比赛" : "Current match"
            : isZh ? "进入分析" : "Open in analysis"}
        </button>
        <button
          type="button"
          className="ml-secondary-action"
          data-testid="match-library-detail-toggle"
          onClick={() => onOpenDetail(match.match_id)}
        >
          {isZh ? "详情 / 画像 / 对比" : "Detail / profiles / compare"}
        </button>
        <button type="button" className="ml-secondary-action" onClick={copyLink}>
          {copied ? isZh ? "已复制链接" : "Link copied" : isZh ? "复制链接" : "Copy link"}
        </button>
      </footer>
    </aside>
  );
};

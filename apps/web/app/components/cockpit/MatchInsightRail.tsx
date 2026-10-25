"use client";

import React, { useMemo } from "react";
import { CockpitState, InspectorPayload } from "./types";
import { EvidenceRail } from "./EvidenceRail";
import { Locale } from "../../lib/i18n";

interface MatchInsightRailProps {
  state: CockpitState;
  locale?: Locale;
  onInvestigateChangePoint: (payload: {
    focus_type: "oaai_point";
    focus_id: string;
    at: number;
    team: "H" | "N";
  }) => void;
  onAsk: () => void;
  onSelectEvent: (eventId: string) => void;
  onOpenInspector?: (payload: InspectorPayload) => void;
}

const clock = (value: number) => {
  const safe = Math.max(0, Math.round(value));
  return `${Math.floor(safe / 60).toString().padStart(2, "0")}:${(safe % 60).toString().padStart(2, "0")}`;
};

/**
 * Match Detail's AI column. It leads with the strongest recorded OAAI change,
 * states the evidence level, and keeps the full context behind a disclosure.
 */
export const MatchInsightRail: React.FC<MatchInsightRailProps> = ({
  state,
  locale = "zh",
  onInvestigateChangePoint,
  onAsk,
  onSelectEvent,
  onOpenInspector,
}) => {
  const isZh = locale === "zh";
  const points = useMemo(
    () =>
      [...(state.oaai?.change_points || [])]
        .sort((a, b) => Math.abs(b.oaai_amplitude || 0) - Math.abs(a.oaai_amplitude || 0))
        .slice(0, 3),
    [state.oaai?.change_points]
  );
  const top = points[0];
  const accepted = state.result?.accepted?.length ?? 0;
  const rejected = state.result?.rejected?.length ?? 0;
  const ctx = state.match_context || {};
  const teamName = (team: string | undefined) =>
    team === "N" ? state.teams?.N || "Away" : team === "H" ? state.teams?.H || "Home" : isZh ? "中立" : "Neutral";
  const continuous = Boolean(ctx.continuous_coverage);
  const modelState = state.model_configured ? (isZh ? "已配置 · 本场未运行" : "Configured · not run") : isZh ? "未运行" : "Not run";
  const contributor = top?.top_contributors?.[0];
  const contributorSequence = contributor
    ? (state.sequences || []).find((sequence) => sequence.event_ids.includes(contributor.event_id))
    : null;

  return (
    <aside className="r6-insight-rail" aria-label={isZh ? "AI 洞察与证据" : "AI insights and evidence"}>
      <header className="r6-rail-head">
        <div>
          <span className="r6-kicker">{isZh ? "AI 洞察" : "AI insights"}</span>
          <h2>{isZh ? "这场比赛发生了什么" : "What changed in this match"}</h2>
        </div>
        <span className={`r6-status-dot ${continuous ? "ok" : "warn"}`} title={continuous ? "coverage verified" : ctx.completeness_status || "partial"} />
      </header>

      {top ? (
        <article className="r6-insight-card" data-testid="match-insight-primary">
          <div className="r6-insight-meta">
            <span className="r6-time">{clock(top.at)}</span>
            <span className="r6-level">{isZh ? "Level 2 · 指标归因" : "Level 2 · metric attribution"}</span>
          </div>
          <h3>
            {teamName(top.leading_team)}
            {isZh ? " 的活动在此时段上升" : " activity rose in this spell"}
          </h3>
          <p>
            {isZh
              ? `OAAI 变化幅度 ${top.oaai_amplitude > 0 ? "+" : ""}${Number(top.oaai_amplitude).toFixed(2)}。这是公式分解，不是战术因果。`
              : `OAAI amplitude ${top.oaai_amplitude > 0 ? "+" : ""}${Number(top.oaai_amplitude).toFixed(2)}. Formula attribution, not tactical causation.`}
          </p>
          {contributor && (
            <p className="r6-insight-evidence">
              {isZh ? "最强记录动作" : "Top recorded action"}:{" "}
              <b>{contributor.actor || "Unknown"}</b> · {contributor.kind} · {clock(contributor.t)}
            </p>
          )}
          <div className="r6-insight-actions">
            <button
              type="button"
              className="r6-primary-action"
              onClick={() =>
                onInvestigateChangePoint({
                  focus_type: "oaai_point",
                  focus_id: top.change_point_id,
                  at: Math.round(top.at),
                  team: top.leading_team === "N" ? "N" : "H",
                })
              }
            >
              {isZh ? "调查这次变化" : "Investigate this change"}
            </button>
            {contributor && (
              <button
                type="button"
                className="r6-text-action"
                onClick={() => {
                  onSelectEvent(contributor.event_id);
                  if (contributorSequence && onOpenInspector) {
                    onOpenInspector({
                      type: "sequence",
                      sequence: contributorSequence,
                      title: `Sequence ${contributorSequence.sequence_id}`,
                    });
                  }
                }}
              >
                {isZh ? "查看事件证据 →" : "Trace event →"}
              </button>
            )}
          </div>
        </article>
      ) : (
        <div className="r6-empty-insight">
          <h3>{isZh ? "当前快照还没有指标拐点" : "No metric change point at this snapshot"}</h3>
          <p>
            {isZh
              ? "继续回放或选择另一个时间点。没有拐点不等于比赛没有战术变化，只表示当前有球事件未触发指标阈值。"
              : "Keep replaying or choose another moment. No change point does not mean no tactical change; it means recorded events have not crossed the metric threshold."}
          </p>
        </div>
      )}

      {points.length > 1 && (
        <div className="r6-insight-list" aria-label={isZh ? "其他变化点" : "Other change points"}>
          {points.slice(1).map((point) => (
            <button
              key={point.change_point_id}
              type="button"
              onClick={() =>
                onInvestigateChangePoint({
                  focus_type: "oaai_point",
                  focus_id: point.change_point_id,
                  at: Math.round(point.at),
                  team: point.leading_team === "N" ? "N" : "H",
                })
              }
            >
              <span>{clock(point.at)}</span>
              <b>{teamName(point.leading_team)}</b>
              <em>
                {point.oaai_amplitude > 0 ? "+" : ""}
                {Number(point.oaai_amplitude).toFixed(2)}
              </em>
            </button>
          ))}
        </div>
      )}

      <button type="button" className="r6-ask-button" onClick={onAsk}>
        {isZh ? "向 MatchLens 提问" : "Ask MatchLens"}
        <span aria-hidden="true">↗</span>
      </button>

      <div className="r6-rail-facts">
        <div>
          <span>{isZh ? "证据覆盖" : "Coverage"}</span>
          <b>{continuous ? (isZh ? "连续已验证" : "Continuous") : ctx.completeness_status || (isZh ? "部分" : "Partial")}</b>
        </div>
        <div>
          <span>{isZh ? "模型" : "Model"}</span>
          <b>{modelState}</b>
        </div>
        <div>
          <span>{isZh ? "门禁结论" : "Gate claims"}</span>
          <b>
            {accepted} / {accepted + rejected}
          </b>
        </div>
      </div>

      <details className="r6-evidence-details">
        <summary>{isZh ? "证据与数据版本" : "Evidence & data version"}</summary>
        <EvidenceRail state={state} locale={locale} />
      </details>
    </aside>
  );
};

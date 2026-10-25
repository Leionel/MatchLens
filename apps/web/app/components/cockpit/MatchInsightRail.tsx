"use client";

import React, { useEffect, useMemo, useState } from "react";
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

type AgentRunSummary = {
  run_id: string;
  match_id: string;
  state: string;
  origin: string;
  requests: number;
  updated_at: number;
  error?: string | null;
};

const clock = (value: number) => {
  const safe = Math.max(0, Math.round(value));
  return `${Math.floor(safe / 60).toString().padStart(2, "0")}:${(safe % 60).toString().padStart(2, "0")}`;
};

const signed = (value: number) => `${value > 0 ? "+" : ""}${Number(value).toFixed(2)}`;

/**
 * The signed OAAI level names which side held the activity advantage. A
 * zero-crossing is a lead change, not a surge, so it must not be attributed to
 * a default team. `leading_team` is the backend's frozen direction.
 */
const pointDirection = (point: any): { team: "H" | "N" | null; turn: boolean } => {
  const team = point?.leading_team === "H" ? "H" : point?.leading_team === "N" ? "N" : null;
  return { team, turn: point?.change_type === "lead_turn" };
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
  const homeName = state.teams?.H || (isZh ? "主队" : "Home");
  const awayName = state.teams?.N || (isZh ? "客队" : "Away");
  const continuous = Boolean(ctx.continuous_coverage);

  const [runs, setRuns] = useState<AgentRunSummary[]>([]);
  const [runsState, setRunsState] = useState<"loading" | "ok" | "error">("loading");

  useEffect(() => {
    if (!state.match_id) {
      setRuns([]);
      setRunsState("ok");
      return;
    }
    const controller = new AbortController();
    setRunsState("loading");
    fetch("/api/agent-runs?limit=50", { signal: controller.signal })
      .then((res) => {
        if (!res.ok) throw new Error(`agent runs unavailable (${res.status})`);
        return res.json();
      })
      .then((data) => {
        const all: AgentRunSummary[] = Array.isArray(data?.runs) ? data.runs : [];
        setRuns(all.filter((run) => run.match_id === state.match_id).slice(0, 3));
        setRunsState("ok");
      })
      .catch((error) => {
        if ((error as Error).name !== "AbortError") setRunsState("error");
      });
    return () => controller.abort();
  }, [state.match_id, state.result?.run_id]);

  const currentOrigin = state.result?.origin || null;
  const currentIsLive = currentOrigin === "live_model";
  const recent = runs[0] || null;
  const originLabel = (origin: string | null | undefined) => {
    if (origin === "live_model") return isZh ? "真实模型" : "live model";
    if (origin === "deterministic") return isZh ? "确定性引擎" : "deterministic";
    if (origin === "not_run") return isZh ? "未调用模型" : "not run";
    return origin || (isZh ? "未知" : "unknown");
  };
  const currentLine = state.result
    ? `${currentIsLive ? (isZh ? "真实模型" : "live model") : isZh ? "确定性引擎" : "deterministic engine"}${
        state.result.reused ? (isZh ? " · 复用已有结果" : " · reused result") : ""
      } · ${state.result.requests ?? 0} ${isZh ? "次模型请求" : "model requests"}`
    : isZh
      ? "当前快照尚无 AI 分析结果"
      : "No AI result for the current snapshot";
  const recentLine = recent
    ? `${recent.state} · ${originLabel(recent.origin)} · ${recent.requests ?? 0} ${
        isZh ? "次模型请求" : "model requests"
      }`
    : runsState === "loading"
      ? isZh
        ? "正在查询本场运行记录…"
        : "Loading this match's runs…"
      : runsState === "error"
        ? isZh
          ? "运行记录暂不可用（不影响当前分析）"
          : "Run history unavailable (current analysis unaffected)"
        : isZh
          ? "本场尚无 Agent 运行记录"
          : "No agent run recorded for this match";
  const modelFact = currentIsLive
    ? isZh
      ? "本快照 · 真实模型"
      : "This snapshot · live model"
    : recent
      ? `${!state.model_configured ? (isZh ? "模型未配置" : "Model not configured") : isZh ? "模型可用" : "Model available"} · ${isZh ? "最近" : "Latest"} ${recent.state}`
      : !state.model_configured
        ? isZh
          ? "模型未配置"
          : "Model not configured"
        : runsState === "loading"
          ? isZh
            ? "查询运行记录…"
            : "Loading runs…"
          : runsState === "error"
            ? isZh
              ? "运行记录不可用"
              : "Runs unavailable"
            : isZh
              ? "本场未运行"
              : "Not run this match";

  const describePoint = (point: any) => {
    const direction = pointDirection(point);
    if (direction.team === "H") {
      return direction.turn
        ? isZh
          ? `${homeName} 取得活动主导`
          : `${homeName} took the activity lead`
        : isZh
          ? `${homeName} 活动达到本时段峰值`
          : `${homeName} activity peaked in this spell`;
    }
    if (direction.team === "N") {
      return direction.turn
        ? isZh
          ? `${awayName} 取得活动主导`
          : `${awayName} took the activity lead`
        : isZh
          ? `${awayName} 活动达到本时段峰值`
          : `${awayName} activity peaked in this spell`;
    }
    return isZh ? "攻防活动主导权发生转换" : "The activity lead changed hands";
  };

  const investigatePoint = (point: any, team: "H" | "N") =>
    onInvestigateChangePoint({
      focus_type: "oaai_point",
      focus_id: point.change_point_id,
      at: Math.round(point.at),
      team,
    });

  const contributor = top?.top_contributors?.[0];
  const contributorSequence = contributor
    ? (state.sequences || []).find((sequence) => sequence.event_ids.includes(contributor.event_id))
    : null;
  const primaryDirection = top ? pointDirection(top) : null;

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
        <article className="r6-insight-card" data-testid="match-insight-primary" data-direction={primaryDirection?.team || "neutral"}>
          <div className="r6-insight-meta">
            <span className="r6-time">{clock(top.at)}</span>
            <span className="r6-level">{isZh ? "Level 2 · 指标归因" : "Level 2 · metric attribution"}</span>
          </div>
          <h3 data-testid="match-insight-title">{describePoint(top)}</h3>
          <p>
            {isZh
              ? `OAAI 平滑值 ${signed(Number(top.oaai_amplitude || 0))}（正值 = 主队活动占优，负值 = 客队活动占优）。这是公式分解，不是战术因果。`
              : `Smoothed OAAI ${signed(Number(top.oaai_amplitude || 0))} (positive = home activity lead, negative = away). Formula attribution, not tactical causation.`}
          </p>
          {contributor && (
            <p className="r6-insight-evidence">
              {isZh ? "最强记录动作" : "Top recorded action"}:{" "}
              <b>{contributor.actor || "Unknown"}</b> · {contributor.kind} · {clock(contributor.t)}
            </p>
          )}
          <div className="r6-insight-actions">
            {primaryDirection?.team ? (
              <button
                type="button"
                className="r6-primary-action"
                onClick={() => investigatePoint(top, primaryDirection.team as "H" | "N")}
              >
                {isZh ? "调查这次变化" : "Investigate this change"}
              </button>
            ) : (
              <div className="r6-team-choice" role="group" aria-label={isZh ? "选择调查球队" : "Choose a team to investigate"}>
                <span>{isZh ? "选择调查球队" : "Investigate for"}</span>
                <button type="button" className="r6-primary-action" onClick={() => investigatePoint(top, "H")}>
                  {homeName}
                </button>
                <button type="button" className="r6-primary-action" onClick={() => investigatePoint(top, "N")}>
                  {awayName}
                </button>
              </div>
            )}
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
          {points.slice(1).map((point) => {
            const direction = pointDirection(point);
            if (direction.team) {
              return (
                <button
                  key={point.change_point_id}
                  type="button"
                  onClick={() => investigatePoint(point, direction.team as "H" | "N")}
                >
                  <span>{clock(point.at)}</span>
                  <b>{describePoint(point)}</b>
                  <em>{signed(Number(point.oaai_amplitude || 0))}</em>
                </button>
              );
            }
            return (
              <div key={point.change_point_id} className="r6-insight-neutral-row">
                <span>{clock(point.at)}</span>
                <b>{describePoint(point)}</b>
                <em>{signed(Number(point.oaai_amplitude || 0))}</em>
                <div className="r6-team-choice" role="group" aria-label={isZh ? `选择 ${clock(point.at)} 的调查球队` : `Choose a team at ${clock(point.at)}`}>
                  <button type="button" onClick={() => investigatePoint(point, "H")}>
                    {homeName}
                  </button>
                  <button type="button" onClick={() => investigatePoint(point, "N")}>
                    {awayName}
                  </button>
                </div>
              </div>
            );
          })}
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
        <div data-testid="match-model-fact">
          <span>{isZh ? "模型" : "Model"}</span>
          <b>{modelFact}</b>
        </div>
        <div>
          <span>{isZh ? "门禁结论" : "Gate claims"}</span>
          <b>
            {accepted} / {accepted + rejected}
          </b>
        </div>
      </div>

      <details
        className="r6-model-details"
        data-testid="match-model-status"
        data-model-configured={state.model_configured ? "true" : "false"}
        data-current-origin={currentOrigin || "none"}
        data-recent-run-state={recent?.state || "none"}
      >
        <summary>{isZh ? "模型与运行状态" : "Model and run status"}</summary>
        <dl>
          <div>
            <dt>{isZh ? "模型配置" : "Model configured"}</dt>
            <dd data-testid="match-model-availability">
              {state.model_configured ? (isZh ? "已配置，可用" : "Configured and available") : isZh ? "未配置" : "Not configured"}
            </dd>
          </div>
          <div>
            <dt>{isZh ? "当前洞察来源" : "Current insight source"}</dt>
            <dd data-testid="match-model-current">{currentLine}</dd>
          </div>
          <div>
            <dt>{isZh ? "本场最近运行" : "Latest run for this match"}</dt>
            <dd data-testid="match-model-recent">{recentLine}</dd>
          </div>
        </dl>
        <p>
          {isZh
            ? "“已配置”只表示模型可用，不等于本场已经运行；最近运行也可能来自另一个时间点。"
            : "Configured only means the model is available; it does not mean this match has run. The latest run may also belong to another moment."}
        </p>
      </details>

      <details className="r6-evidence-details">
        <summary>{isZh ? "证据与数据版本" : "Evidence & data version"}</summary>
        <EvidenceRail state={state} locale={locale} />
      </details>
    </aside>
  );
};

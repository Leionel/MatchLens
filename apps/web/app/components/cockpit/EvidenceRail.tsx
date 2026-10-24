"use client";

import React from "react";
import { CockpitState } from "./types";
import { Locale } from "../../lib/i18n";

interface EvidenceRailProps {
  state: CockpitState;
  locale?: Locale;
}

const clock = (value: number | null | undefined) => {
  if (value === null || value === undefined) return "—";
  const s = Math.max(0, Math.floor(value));
  return `${Math.floor(s / 60).toString().padStart(2, "0")}:${(s % 60).toString().padStart(2, "0")}`;
};

export const EvidenceRail: React.FC<EvidenceRailProps> = ({ state, locale = "zh" }) => {
  const isZh = locale === "zh";
  const coverage = state.coverage;
  const observedPct = coverage ? Math.max(0, Math.min(100, coverage.time_coverage * 100)) : 0;
  const official = state.official_score;
  const officialDiffers =
    official &&
    official.H !== null &&
    official.N !== null &&
    (official.H !== state.score.H || official.N !== state.score.N);
  const gateVerified = state.result?.accepted?.length ?? 0;
  const rejected = state.result?.rejected?.length ?? 0;
  const ctx = state.match_context || {};

  return (
    <section className="evidence-rail" aria-label={isZh ? "证据与覆盖状态" : "Evidence and coverage status"}>
      <div className="rail-cell rail-cell-coverage">
        <div className="rail-label">
          <span>{isZh ? "观测覆盖" : "Observed coverage"}</span>
          <span className={`rail-chip ${coverage?.continuous ? "verified" : "unknown"}`}>
            {coverage?.continuous ? (isZh ? "连续" : "Continuous") : isZh ? "部分" : "Partial"}
          </span>
        </div>
        <div className="rail-bar" role="img" aria-label={`${observedPct.toFixed(1)}% observed coverage`}>
          <span className="rail-bar-fill" style={{ width: `${observedPct}%` }} />
          <span className="rail-bar-unknown" style={{ width: `${100 - observedPct}%` }} />
        </div>
        <div className="rail-meta">
          <span>{observedPct.toFixed(1)}% {isZh ? "已观测" : "observed"}</span>
          <span>
            {clock(coverage?.observed_end)} / {clock(coverage?.format_seconds)}
          </span>
        </div>
      </div>

      <div className="rail-cell">
        <div className="rail-label">
          <span>{isZh ? "比分口径" : "Score basis"}</span>
          <span className="rail-chip neutral">AS OF {clock(state.at)}</span>
        </div>
        <div className="rail-score">
          <b>{state.score.H}</b>
          <span>–</span>
          <b>{state.score.N}</b>
        </div>
        <div className="rail-meta">
          {officialDiffers ? (
            <span className="rail-warning">
              {isZh ? "官方终场" : "OFFICIAL FT"} {official!.H}–{official!.N}
            </span>
          ) : (
            <span>{isZh ? "与官方终场一致或未提供" : "Matches official score or not supplied"}</span>
          )}
        </div>
      </div>

      <div className="rail-cell">
        <div className="rail-label">
          <span>{isZh ? "数据版本" : "Data version"}</span>
          <span className="rail-chip neutral">{ctx.data_coverage || "—"}</span>
        </div>
        <div className="rail-strong" title={ctx.dataset_revision || ctx.data_version || undefined}>
          {ctx.dataset_revision ? `${String(ctx.dataset_revision).slice(0, 12)}…` : ctx.data_version || "—"}
        </div>
        <div className="rail-meta">
          <span>
            {coverage?.event_count ?? state.events?.length ?? 0} {isZh ? "条事件" : ((coverage?.event_count ?? state.events?.length ?? 0) === 1 ? "event" : "events")} {" "}
            {ctx.coordinate_frame === "team_relative" ? (isZh ? "进攻方向标准化" : "attack-relative") : isZh ? "固定坐标" : "fixed frame"}
          </span>
        </div>
      </div>

      <div className="rail-cell">
        <div className="rail-label">
          <span>{isZh ? "发布门禁" : "Publication"}</span>
          <span className={`rail-chip ${gateVerified > 0 ? "verified" : "unknown"}`}>
            {gateVerified > 0 ? (isZh ? "已过门禁" : "Gate passed") : isZh ? "无已审声明" : "No gate claim"}
          </span>
        </div>
        <div className="rail-strong">
          {gateVerified} <small>{isZh ? "通过" : "approved"}</small> / {rejected} <small>{isZh ? "驳回" : "rejected"}</small>
        </div>
        <div className="rail-meta">
          <span>
            {isZh
              ? "门禁verified ≠ 编辑批准"
              : "Gate verified ≠ editorial approval"}
          </span>
        </div>
      </div>
    </section>
  );
};

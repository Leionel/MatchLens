"use client";

import { Locale } from "../lib/i18n";

type Card = {
  claim_id: string;
  assertion: string;
  verdict: string;
  fan: string;
  analyst: string;
  refs: string[];
  scope: string;
  reason: string;
  limitations: string[];
  snapshot_id: string;
  as_of: number;
  historical?: boolean;
};

type MatchRecapProps = {
  score: { H: number; N: number };
  history: Card[];
  locale?: Locale;
  onInspect: (receiptId: string, snapshotId: string) => void;
};

const clock = (s: number) =>
  `${Math.floor(s / 60).toString().padStart(2, "0")}:${Math.floor(s % 60).toString().padStart(2, "0")}`;

export function MatchRecap({ score, history, locale = "zh", onInspect }: MatchRecapProps) {
  const isZh = locale === "zh";
  const sorted = [...history].sort((a, b) => a.as_of - b.as_of);

  return (
    <section className="fulltime-recap-section" aria-label="Full-time match recap and verified narrative">
      <div className="recap-header">
        <div className="recap-tag-group">
          <span className="recap-badge">
            {isZh ? "全场终局 · 认证事实研报" : "FULL-TIME · APPROVED FINDINGS"}
          </span>
          <span className="final-score-pill">
            Harbor FC {score.H} – {score.N} Northbridge United
          </span>
        </div>
        <h2 className="recap-title">
          {isZh ? "全场核心战术论据与事实研报" : "The match, through its key findings"}
        </h2>
        <p className="recap-intro">
          {isZh
            ? "回顾各个时刻经由 Gate 2.0 门禁严苛认证的战术论断。每条论断均可一键回溯至对应时刻的确定性事件序列与数学收据。"
            : "Revisit approved findings at their original analysis times. Each opens the exact events and metrics used in its review."}
        </p>
      </div>

      <div className="recap-cards-list">
        {sorted.map((item, idx) => (
          <div key={`${item.snapshot_id}-${item.claim_id}`} className="recap-milestone-card">
            <div className="milestone-time-col">
              <span className="milestone-glyph">
                {item.assertion === "goal_sequence" ? "⚽" : item.assertion === "recoveries_followed_by_shots" ? "⚡" : "🔍"}
              </span>
              <span className="milestone-clock">{clock(item.as_of)}</span>
              <span className="milestone-step">#{idx + 1}</span>
            </div>

            <div className="milestone-content">
              <div className="milestone-status-row">
                <span className={`milestone-verdict ${item.verdict}`}>
                  {item.verdict === "qualify" ? (isZh ? "限制合格" : "QUALIFIED") : (isZh ? "核验通过" : "VERIFIED")}
                </span>
                <span className="milestone-assertion">
                  {item.historical ? (isZh ? "历史真实分析 · " : "HISTORICAL REAL ANALYSIS · ") : ""}{item.assertion.replaceAll("_", " ").toUpperCase()}
                </span>
              </div>
              <p className="milestone-fan-text">{item.fan}</p>
            </div>

            <div className="milestone-action">
              <button
                type="button"
                className="btn-recap-inspect"
                onClick={() => onInspect(item.refs[0], item.snapshot_id)}
                title={isZh ? "查验此项论断所引用的事实收据与计算依据" : "Inspect source receipts for this insight"}
              >
                <span>{isZh ? "查验凭据" : "View evidence"}</span>
                <span>↗</span>
              </button>
            </div>
          </div>
        ))}

        {sorted.length === 0 && (
          <div className="recap-empty-box">
            <p>
              {isZh
                ? "推演比赛或聚焦特定比赛赛段，即可在此自动建立完整的终场事实研报卷宗。"
                : "Replay the match or focus chapters to build a verified match dossier."}
            </p>
          </div>
        )}
      </div>
    </section>
  );
}

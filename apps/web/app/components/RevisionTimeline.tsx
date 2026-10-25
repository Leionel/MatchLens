"use client";

type RevisionEntry = {
  revision_id: string;
  at: number;
  claim_id: string;
  challenge_type: string;
  outcome: "maintained" | "narrowed" | "withdrawn" | "inconclusive";
  summary: string;
  counterevidence_checked?: string[];
  timestamp: number;
};

import { Locale } from "../lib/i18n";

type Props = {
  revisions: RevisionEntry[];
  onOpenChallengeModal: () => void;
  canChallenge: boolean;
  locale?: Locale;
};

const challengeLabels: Record<string, { zh: string; en: string }> = {
  challenge_causal_interpretation: { zh: "因果解释审查", en: "Causal interpretation scrutiny" },
  check_counterevidence: { zh: "反证审查", en: "Counterevidence audit" },
  check_sample_sufficiency: { zh: "样本充分性检查", en: "Sample sufficiency check" },
  check_comparison_window: { zh: "基线窗口对比", en: "Baseline window comparison" },
  examine_sequence: { zh: "序列连续性检查", en: "Sequence continuity check" },
};

const clock = (s: number) =>
  `${Math.floor(s / 60).toString().padStart(2, "0")}:${Math.floor(s % 60).toString().padStart(2, "0")}`;

export function RevisionTimeline({ revisions, onOpenChallengeModal, canChallenge, locale = "zh" }: Props) {
  const isZh = locale === "zh";
  return (
    <div className="revision-timeline-panel">
      <div className="timeline-header-row">
        <div>
          <span className="timeline-badge">{isZh ? "质疑与修订时间线" : "CHALLENGE & REVISION TIMELINE"}</span>
          <h4 className="timeline-heading">{isZh ? "判断演进审计" : "Judgment evolution audit"}</h4>
        </div>
        {canChallenge && (
          <button
            type="button"
            className="btn-new-challenge"
            onClick={onOpenChallengeModal}
            title={isZh ? "对当前结论发起对抗性审查" : "Challenge the current claim with adversarial scrutiny"}
          >
            ⚡ {isZh ? "质疑当前结论" : "Challenge current insight"}
          </button>
        )}
      </div>

      {revisions.length === 0 ? (
        <div className="timeline-empty-card">
          <p>
            No user challenges initiated yet. Click <b>&quot;Challenge Current Insight&quot;</b> to trigger an independent adversarial audit against causal overreach or sample size.
          </p>
        </div>
      ) : (
        <div className="revision-events-list">
          {revisions.map((rev, idx) => {
            const outcomeClass =
              rev.outcome === "maintained"
                ? "outcome-maintained"
                : rev.outcome === "narrowed"
                  ? "outcome-narrowed"
                  : "outcome-withdrawn";

            return (
              <div key={rev.revision_id || idx} className={`revision-event-item ${outcomeClass}`}>
                <div className="rev-point-line">
                  <span className="rev-dot" />
                  {idx < revisions.length - 1 && <span className="rev-connector" />}
                </div>

                <div className="rev-content-card">
                  <div className="rev-meta-bar">
                    <span className="rev-id">{rev.revision_id}</span>
                    <span className="rev-type">
                      {(challengeLabels[rev.challenge_type]?.[isZh ? 'zh' : 'en']) || rev.challenge_type}
                    </span>
                    <span className="rev-time">Match Time {clock(rev.at)}</span>
                    <span className={`rev-outcome-badge ${outcomeClass}`}>
                      {rev.outcome.toUpperCase()}
                    </span>
                  </div>

                  <p className="rev-summary">{rev.summary}</p>

                  {rev.counterevidence_checked && rev.counterevidence_checked.length > 0 && (
                    <div className="rev-checked-refs">
                      <span className="refs-label">Audited Receipts:</span>
                      <span className="refs-chips">{rev.counterevidence_checked.join(", ")}</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

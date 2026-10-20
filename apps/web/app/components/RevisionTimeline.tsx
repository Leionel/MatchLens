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

type Props = {
  revisions: RevisionEntry[];
  onOpenChallengeModal: () => void;
  canChallenge: boolean;
};

const challengeLabels: Record<string, string> = {
  challenge_causal_interpretation: "Causal Interpretation Scrutiny",
  check_counterevidence: "Counterevidence Audit",
  check_sample_sufficiency: "Sample Sufficiency Verification",
  check_comparison_window: "Baseline Window Comparison",
  examine_sequence: "Sequence Continuity Check",
};

const clock = (s: number) =>
  `${Math.floor(s / 60).toString().padStart(2, "0")}:${Math.floor(s % 60).toString().padStart(2, "0")}`;

export function RevisionTimeline({ revisions, onOpenChallengeModal, canChallenge }: Props) {
  return (
    <div className="revision-timeline-panel">
      <div className="timeline-header-row">
        <div>
          <span className="timeline-badge">CHALLENGE & REVISION TIMELINE</span>
          <h4 className="timeline-heading">Judgment Evolution Audit</h4>
        </div>
        {canChallenge && (
          <button
            type="button"
            className="btn-new-challenge"
            onClick={onOpenChallengeModal}
            title="Challenge the current claim with adversarial scrutiny"
          >
            ⚡ Challenge Current Insight
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
                      {challengeLabels[rev.challenge_type] || rev.challenge_type}
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

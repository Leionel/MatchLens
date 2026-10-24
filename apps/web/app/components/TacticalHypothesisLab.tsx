"use client";

type Hypothesis = {
  id: string;
  title: string;
  hypothesis_type: "surface" | "alternative" | "causal_overreach";
  claim_assertion: string;
  team: "H" | "N";
  status: "supported" | "qualified" | "rejected" | "insufficient_evidence";
  supporting_evidence: string[];
  counterevidence: string[];
  reason: string;
  limitations: string[];
};

type HypothesisLabMatrix = {
  snapshot_id: string;
  as_of: number;
  team: "H" | "N";
  topic: string;
  hypotheses: Hypothesis[];
  disclaimer: string;
};

type Props = {
  matrix: HypothesisLabMatrix | null;
  onInspectReceipt: (receiptId: string) => void;
};

const typeLabels: Record<string, string> = {
  surface: "Surface / Apparent Hypothesis",
  alternative: "Alternative / Deep Hypothesis",
  causal_overreach: "Causal Overreach (Counterfactual)",
};

export function TacticalHypothesisLab({ matrix, onInspectReceipt }: Props) {
  if (!matrix || matrix.hypotheses.length === 0) {
    return (
      <div className="hypothesis-lab-empty">
        <p>Focus or play the match to generate competing tactical hypotheses for this snapshot.</p>
      </div>
    );
  }

  return (
    <div className="hypothesis-lab-container">
      <div className="lab-header">
        <div className="lab-title-row">
          <span className="lab-badge">COMPETING HYPOTHESIS LAB</span>
          <span className="lab-team-tag">{matrix.team === "N" ? "Northbridge Utd" : "Harbor FC"}</span>
        </div>
        <h4 className="lab-topic">{matrix.topic}</h4>
        <p className="lab-desc">
          Multiple competing interpretations evaluated simultaneously against immutable event receipts.
        </p>
      </div>

      <div className="hypothesis-cards-grid">
        {matrix.hypotheses.map((hyp) => {
          const statusClass =
            hyp.status === "supported"
              ? "status-supported"
              : hyp.status === "qualified"
                ? "status-qualified"
                : hyp.status === "rejected"
                  ? "status-rejected"
                  : "status-insufficient";

          return (
            <div key={hyp.id} className={`hypothesis-card ${statusClass}`}>
              <div className="hyp-card-top">
                <span className="hyp-type-badge">{typeLabels[hyp.hypothesis_type]}</span>
                <span className={`hyp-verdict-pill ${statusClass}`}>
                  {hyp.status.replace("_", " ").toUpperCase()}
                </span>
              </div>

              <h5 className="hyp-title">{hyp.title}</h5>
              <p className="hyp-reason">{hyp.reason}</p>

              <div className="hyp-evidence-section">
                {hyp.supporting_evidence.length > 0 && (
                  <div className="hyp-evidence-group">
                    <span className="hyp-evidence-label">Supporting:</span>
                    <div className="hyp-chips-wrap">
                      {hyp.supporting_evidence.map((ref) => (
                        <button
                          key={ref}
                          type="button"
                          className="hyp-evidence-chip support"
                          onClick={() => onInspectReceipt(ref)}
                          title="Click to inspect verified receipt"
                        >
                          ✓ {ref}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {hyp.counterevidence.length > 0 && (
                  <div className="hyp-evidence-group">
                    <span className="hyp-evidence-label">Counterevidence:</span>
                    <div className="hyp-chips-wrap">
                      {hyp.counterevidence.map((ref) => (
                        <button
                          key={ref}
                          type="button"
                          className="hyp-evidence-chip counter"
                          onClick={() => onInspectReceipt(ref)}
                          title="Click to inspect counterevidence receipt"
                        >
                          ✗ {ref}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {hyp.limitations.length > 0 && (
                <div className="hyp-limitations-row">
                  <span className="limit-icon">ℹ</span>
                  <span>{hyp.limitations.join(" ")}</span>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="lab-footer-disclaimer">
        <span>{matrix.disclaimer}</span>
      </div>
    </div>
  );
}

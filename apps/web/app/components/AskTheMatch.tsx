"use client";

import { useState } from "react";

type EvidenceChip = {
  id: string;
  label: string;
};

type GapAdvisor = {
  topic: string;
  available_evidence: string[];
  missing_data: string[];
  unsupported_inference: string;
  supported_narrower_conclusion: string;
};

type AskResult = {
  intent_id: string;
  question: string;
  answer: string;
  evidence_chips: EvidenceChip[];
  gap_advisor?: GapAdvisor;
};

type Props = {
  team: "H" | "N";
  onInspectReceipt: (receiptId: string) => void;
};

const queryPresets = [
  {
    id: "possession_vs_penetration",
    label: "Did possession create threat?",
    desc: "Test if ball dominance produced shots or box entries",
  },
  {
    id: "scoring_sequence_breakdown",
    label: "How was the goal sequence built?",
    desc: "Breakdown of the unbroken sequence ending in a goal",
  },
  {
    id: "window_delta_comparison",
    label: "What changed across 3m windows?",
    desc: "Inspect metric deltas between prior and current periods",
  },
];

export function AskTheMatch({ team, onInspectReceipt }: Props) {
  const [activeQuery, setActiveQuery] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AskResult | null>(null);
  const [error, setError] = useState("");

  const handleQuery = async (intentId: string) => {
    setActiveQuery(intentId);
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ intent_id: intentId, team }),
      });
      if (!res.ok) throw new Error(`Query failed (${res.status})`);
      const data: AskResult = await res.json();
      setResult(data);
    } catch (err: any) {
      setError(err.message || "Failed to query match facts.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ask-match-container">
      <div className="ask-match-header">
        <span className="ask-badge">ASK THE MATCH CONSTRAINED INTENTS</span>
        <h4 className="ask-heading">Constrained Tactical Query Engine</h4>
        <p className="ask-sub">
          Ask verifiable questions grounded exclusively in immutable event receipts and spatial invariants.
        </p>
      </div>

      <div className="ask-presets-row">
        {queryPresets.map((q) => (
          <button
            key={q.id}
            type="button"
            className={`ask-preset-btn ${activeQuery === q.id ? "active" : ""}`}
            onClick={() => handleQuery(q.id)}
            disabled={loading}
          >
            <span className="preset-label">{q.label}</span>
            <span className="preset-desc">{q.desc}</span>
          </button>
        ))}
      </div>

      {loading && (
        <div className="ask-loading-box">
          <span className="ask-spinner">⚙</span>
          <span>Resolving intent against verified snapshot receipts...</span>
        </div>
      )}

      {error && <div className="ask-error-box">{error}</div>}

      {result && !loading && (
        <div className="ask-result-card">
          <div className="ask-result-header">
            <span className="ask-result-tag">GROUNDED ANSWER</span>
            <h5 className="ask-result-q">{result.question}</h5>
          </div>

          <p className="ask-result-text">{result.answer}</p>

          {result.evidence_chips.length > 0 && (
            <div className="ask-chips-section">
              <span className="chips-title">Proof Receipts:</span>
              <div className="chips-list">
                {result.evidence_chips.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    className="ask-evidence-chip"
                    onClick={() => onInspectReceipt(c.id)}
                    title="Inspect calculation in Evidence Drawer"
                  >
                    🔍 {c.label} ↗
                  </button>
                ))}
              </div>
            </div>
          )}

          {result.gap_advisor && (
            <div className="evidence-gap-advisor-box">
              <div className="gap-header">
                <span className="gap-icon">⚖️</span>
                <b>Evidence Gap Advisor ({result.gap_advisor.topic})</b>
              </div>
              <div className="gap-grid">
                <div className="gap-cell available">
                  <span className="gap-col-title">✓ Available Evidence</span>
                  <ul>
                    {result.gap_advisor.available_evidence.map((item, idx) => (
                      <li key={idx}>{item}</li>
                    ))}
                  </ul>
                </div>
                <div className="gap-cell missing">
                  <span className="gap-col-title">✗ Missing Data</span>
                  <ul>
                    {result.gap_advisor.missing_data.map((item, idx) => (
                      <li key={idx}>{item}</li>
                    ))}
                  </ul>
                </div>
              </div>
              <div className="gap-inference-row">
                <div className="gap-unsupported">
                  <b>Unsupported Inference:</b> {result.gap_advisor.unsupported_inference}
                </div>
                <div className="gap-supported">
                  <b>Supported Conclusion:</b> {result.gap_advisor.supported_narrower_conclusion}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

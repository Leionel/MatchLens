"use client";

import { useEffect, useState } from "react";

type ChallengeType =
  | "challenge_causal_interpretation"
  | "check_counterevidence"
  | "check_sample_sufficiency"
  | "check_comparison_window"
  | "examine_sequence"
  | "withdraw_claim";

type ChallengeableClaim = {
  claim_id: string;
  assertion: string;
  gate_status: string;
  claim_level: number;
  lifecycle_status: string;
  editorial_status: string;
  statement: string;
};

type ChallengeModalProps = {
  claimId: string;
  snapshotId: string;
  team: "H" | "N";
  isOpen: boolean;
  onClose: () => void;
  onChallengeSubmitted: (result: any) => void;
};

const challengeOptions: { type: ChallengeType; title: string; desc: string }[] = [
  {
    type: "challenge_causal_interpretation",
    title: "1. Challenge Causal Interpretation",
    desc: "Allege that the insight confuses a chronological sequence with a tactical cause or coach instruction.",
  },
  {
    type: "check_counterevidence",
    title: "2. Audit Negative / Counterevidence",
    desc: "Verify whether the gate actively audited contradictory metrics (e.g. 0 shots or 0 box entries).",
  },
  {
    type: "check_sample_sufficiency",
    title: "3. Check Sample Size & Window Sufficiency",
    desc: "Question whether a short 180s sample is sufficient to generalize beyond isolated events.",
  },
  {
    type: "check_comparison_window",
    title: "4. Test Baseline Window Comparison",
    desc: "Cross-check against the preceding 180s window to verify that delta calculations hold true.",
  },
  {
    type: "examine_sequence",
    title: "5. Examine On-Ball Sequence Continuity",
    desc: "Audit the chain of events leading up to the action for ball possession continuity.",
  },
  {
    type: "withdraw_claim",
    title: "6. Withdraw This Claim",
    desc: "Retire the claim from publication. The original statement and evidence stay in the revision history.",
  },
];

export function ChallengeModal({
  claimId,
  snapshotId,
  team,
  isOpen,
  onClose,
  onChallengeSubmitted,
}: ChallengeModalProps) {
  const [selectedType, setSelectedType] = useState<ChallengeType>("challenge_causal_interpretation");
  const [concern, setConcern] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [claims, setClaims] = useState<ChallengeableClaim[]>([]);
  const [targetClaim, setTargetClaim] = useState(claimId);
  const [loadingClaims, setLoadingClaims] = useState(false);

  useEffect(() => {
    if (!isOpen || !snapshotId) return;
    let active = true;
    setLoadingClaims(true);
    setError("");
    fetch(`/api/challengeable-claims?snapshot_id=${encodeURIComponent(snapshotId)}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(`Claim list failed (${res.status})`);
        return res.json();
      })
      .then((data) => {
        if (!active) return;
        const list: ChallengeableClaim[] = data.claims || [];
        setClaims(list);
        // Prefer the claim the caller already holds; otherwise target the
        // first registered one so the challenge is never sent against a
        // placeholder the registry does not know.
        const known = list.find((c) => c.claim_id === claimId);
        setTargetClaim(known ? known.claim_id : list[0]?.claim_id || claimId);
      })
      .catch((e) => {
        if (active) setError((e as Error).message);
      })
      .finally(() => {
        if (active) setLoadingClaims(false);
      });
    return () => {
      active = false;
    };
  }, [isOpen, snapshotId, claimId]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const res = await fetch("/api/challenge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          claim_id: targetClaim,
          snapshot_id: snapshotId,
          challenge_type: selectedType,
          user_concern: concern || undefined,
          team,
        }),
      });
      if (!res.ok) throw new Error(`Challenge submission failed (${res.status})`);
      const data = await res.json();
      onChallengeSubmitted(data);
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to submit challenge.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="challenge-modal-backdrop" role="dialog" aria-modal="true">
      <div className="challenge-modal-panel">
        <div className="modal-header">
          <div>
            <span className="modal-badge">ADVERSARIAL SCRUTINY</span>
            <h3 className="modal-title">Challenge Published Insight</h3>
          </div>
          <button type="button" className="btn-modal-close" onClick={onClose} aria-label="Close modal">
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          <p className="modal-intro">
            Select an adversarial angle to test whether this conclusion overreaches, lacks sample size, or ignores counterevidence.
          </p>

          <div className="challenge-types-list">
            {challengeOptions.map((opt) => (
              <label
                key={opt.type}
                className={`challenge-option-card ${selectedType === opt.type ? "selected" : ""}`}
              >
                <input
                  type="radio"
                  name="challengeType"
                  value={opt.type}
                  checked={selectedType === opt.type}
                  onChange={() => setSelectedType(opt.type)}
                />
                <div className="opt-text">
                  <span className="opt-title">{opt.title}</span>
                  <span className="opt-desc">{opt.desc}</span>
                </div>
              </label>
            ))}
          </div>

          <div className="user-concern-group">
            <label htmlFor="challenge-claim-select" className="concern-label">
              Claim under review:
            </label>
            <select
              id="challenge-claim-select"
              className="challenge-claim-select"
              value={targetClaim}
              disabled={loadingClaims || claims.length === 0}
              onChange={(e) => setTargetClaim(e.target.value)}
            >
              {claims.length === 0 && <option value={targetClaim}>{targetClaim}</option>}
              {claims.map((c) => (
                <option key={c.claim_id} value={c.claim_id}>
                  {c.claim_id} — {c.assertion.replace(/_/g, " ")} ({c.gate_status})
                </option>
              ))}
            </select>
            {claims.length > 0 && (
              <div className="challenge-claim-detail">
                {claims.find((c) => c.claim_id === targetClaim)?.statement}
              </div>
            )}
          </div>

          <div className="user-concern-group">
            <label htmlFor="concern-input" className="concern-label">
              Specific user note (optional):
            </label>
            <input
              id="concern-input"
              type="text"
              className="concern-input"
              placeholder="e.g. Did the opponent intentionally concede possession?"
              value={concern}
              onChange={(e) => setConcern(e.target.value)}
              maxLength={140}
            />
          </div>

          {error && <div className="modal-error">{error}</div>}

          <div className="modal-actions-bar">
            <button type="button" className="btn-modal-cancel" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button type="submit" className="btn-modal-submit" disabled={submitting}>
              {submitting ? "Verifier Re-Evaluating..." : "Execute Adversarial Challenge ↗"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

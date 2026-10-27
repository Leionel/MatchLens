"use client";

import { useEffect, useState } from "react";
import { Locale } from "../lib/i18n";

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
  locale?: Locale;
};

const challengeOptions: {
  type: ChallengeType;
  zh: string;
  en: string;
  descZh: string;
  descEn: string;
}[] = [
  {
    type: "challenge_causal_interpretation",
    zh: "质疑因果解释",
    en: "Challenge causal interpretation",
    descZh: "指出结论把时间先后顺序误当成战术原因或教练指令。",
    descEn: "Allege that the insight confuses a chronological sequence with a tactical cause or coach instruction.",
  },
  {
    type: "check_counterevidence",
    zh: "审查反证与负面指标",
    en: "Audit counterevidence",
    descZh: "核查门禁是否真的检查了相反指标（例如 0 射门或 0 禁区进入）。",
    descEn: "Verify whether the gate actively audited contradictory metrics (e.g. 0 shots or 0 box entries).",
  },
  {
    type: "check_sample_sufficiency",
    zh: "检查样本与窗口充分性",
    en: "Check sample sufficiency",
    descZh: "质疑 180 秒窗口是否足以支持跨事件、跨时段的结论。",
    descEn: "Question whether a short 180s sample is sufficient to generalize beyond isolated events.",
  },
  {
    type: "check_comparison_window",
    zh: "检验基线窗口对比",
    en: "Test baseline comparison",
    descZh: "与前一窗口交叉核对，确认差值计算是否成立。",
    descEn: "Cross-check against the preceding 180s window to verify that delta calculations hold true.",
  },
  {
    type: "examine_sequence",
    zh: "检查有球序列连续性",
    en: "Examine sequence continuity",
    descZh: "审计动作之前的控球链，确认球权归属连续。",
    descEn: "Audit the chain of events leading up to the action for ball possession continuity.",
  },
  {
    type: "withdraw_claim",
    zh: "撤回这条结论",
    en: "Withdraw this claim",
    descZh: "从发布队列撤回结论；原始陈述与证据仍保留在修订历史中。",
    descEn: "Retire the claim from publication. The original statement and evidence stay in the revision history.",
  },
];

export function ChallengeModal({
  claimId,
  snapshotId,
  team,
  isOpen,
  onClose,
  onChallengeSubmitted,
  locale = "zh",
}: ChallengeModalProps) {
  const isZh = locale === "zh";
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

  // Dialog contract: Escape closes, clicking the backdrop closes. The panel
  // itself stops the propagation so a stray click inside never dismisses.
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [isOpen, onClose]);

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
      setError(err.message || (isZh ? "提交审查失败。" : "Failed to submit challenge."));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="challenge-modal-backdrop"
      role="dialog"
      aria-modal="true"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="challenge-modal-panel">
        <div className="modal-header">
          <div>
            <span className="modal-badge">{isZh ? "对抗性审查" : "ADVERSARIAL SCRUTINY"}</span>
            <h3 className="modal-title">{isZh ? "质疑已发布结论" : "Challenge published insight"}</h3>
          </div>
          <button type="button" className="btn-modal-close" onClick={onClose} aria-label={isZh ? "关闭对话框" : "Close modal"}>
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          <p className="modal-intro">
            {isZh
              ? "选择一个对抗角度，检验结论是否过度推断、样本不足或忽略反证。"
              : "Select an adversarial angle to test whether this conclusion overreaches, lacks sample size, or ignores counterevidence."}
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
                  <span className="opt-title">{isZh ? opt.zh : opt.en}</span>
                  <span className="opt-desc">{isZh ? opt.descZh : opt.descEn}</span>
                </div>
              </label>
            ))}
          </div>

          <div className="user-concern-group">
            <label htmlFor="challenge-claim-select" className="concern-label">
              {isZh ? "待审查结论：" : "Claim under review:"}
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
              {isZh ? "补充说明（可选）：" : "Specific user note (optional):"}
            </label>
            <input
              id="concern-input"
              type="text"
              className="concern-input"
              placeholder={isZh ? "例如：对手是否主动放弃控球？" : "e.g. Did the opponent intentionally concede possession?"}
              value={concern}
              onChange={(e) => setConcern(e.target.value)}
              maxLength={140}
            />
          </div>

          {error && <div className="modal-error">{error}</div>}

          <div className="modal-actions-bar">
            <button type="button" className="btn-modal-cancel" onClick={onClose} disabled={submitting}>
              {isZh ? "取消" : "Cancel"}
            </button>
            <button type="submit" className="btn-modal-submit" disabled={submitting}>
              {submitting ? (isZh ? "核验员重新评估中…" : "Verifier re-evaluating…") : isZh ? "执行对抗审查 ↗" : "Execute adversarial challenge ↗"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

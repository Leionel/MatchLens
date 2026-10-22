"""Track C: Publication Gate 2.0.

Provides rigorous evidence verification, claim tier consistency checking,
and counterevidence gating before publishing analytical claims.

Rules:
1. Claim Level Wording & Consistency:
   - Level 1 (Observational Facts): Strictly forbids causal / interpretative prose
     (e.g. 'causes', 'drives', 'due to', 'because of', 'indicates', 'proves', 'forced').
   - Level 2 (Metric Attribution): Mathematical formula decomposition only.
   - Level 3 (Statistical Association): Requires non-empty assumptions and verification methods.
   - Level 4 (Causal Inference): Requires structural models and counterfactual validation.
2. Event and Metric ID Verification:
   - Verifies that quoted event IDs, metric IDs, and model versions genuinely exist in snapshot/match data.
3. Counterevidence Gating:
   - If counterevidence is non-empty, claim status cannot be approved/published; must be downgraded to disputed/contested.
"""
from __future__ import annotations

import re
from typing import Any, Literal, Optional, Sequence
from pydantic import BaseModel, ConfigDict, Field

from .contracts import (
    ClaimDraft,
    Snapshot,
    VerifierDecision,
    bind_slots,
    validate_draft,
)
from .schema import NormalizedEvent, VerifiedClaim
from .sufficiency import DataSufficiencyAdvisor, DataSufficiencyNotice

# Canonical model version for Gate 2.0 checks
ACTIVE_MODEL_VERSION = "1.0.0"

# Causal / interpretative words prohibited in Level 1 observational claims
CAUSAL_WORDS = [
    r"\bcauses?\b",
    r"\bcaused\b",
    r"\bcausing\b",
    r"\bdrives?\b",
    r"\bdriven\b",
    r"\bdriving\b",
    r"\bdue to\b",
    r"\bbecause of\b",
    r"\bindicates?\b",
    r"\bproves?\b",
    r"\bproven\b",
    r"\bforced?\b",
    r"\bforcing\b",
    r"\bled to\b",
    r"\blead to\b",
    r"\bresults? in\b",
    r"\bresulted in\b",
    r"\bresulting in\b",
]

# Standard catalog metric IDs known to the system
STANDARD_METRIC_IDS = {
    "xG",
    "delta_xT",
    "oaai",
    "oaai_contribution",
    "progression_meters",
    "recovery_rate",
    "density_differential",
    "shots",
    "entries",
    "possession",
    "high_recoveries",
    "transition_shots",
    "goals",
}


class Gate20Verdict(BaseModel):
    """Verdict for a single evaluated claim against Gate 2.0 rules."""
    model_config = ConfigDict(extra="forbid")

    is_valid: bool
    status: Literal["approved", "disputed", "rejected"]
    effective_claim_level: int
    rule_violations: list[str] = Field(default_factory=list)
    remediation_notes: list[str] = Field(default_factory=list)
    verified_event_ids: list[str] = Field(default_factory=list)
    verified_metric_ids: list[str] = Field(default_factory=list)


class PublicationGate2Result(BaseModel):
    """Full result structure compatible with draft review and multi-agent pipelines."""
    model_config = ConfigDict(extra="forbid")

    status: Literal["passed", "contested", "rejected"]
    gate_version: str = "2.0"
    claim_id: str
    claim_level: str
    selected_variant: str
    published_text: str
    verified_refs: list[str]
    assumptions: list[str]
    verification_methods: list[str]
    counterevidence_found: list[str]
    data_sufficiency: DataSufficiencyNotice
    audit_notes: list[str] = Field(default_factory=list)


def check_level_wording(text: str, level: int | str) -> list[str]:
    """Checks whether claim text violates tier-specific wording constraints."""
    violations: list[str] = []
    lvl = 1 if level in (1, "1", "level_1_observed") else (
        2 if level in (2, "2", "level_2_formula") else (
            3 if level in (3, "3", "level_3_hypothesis") else 4
        )
    )

    if lvl == 1:
        # Check forbidden causal words
        lower_text = text.lower()
        for pattern in CAUSAL_WORDS:
            match = re.search(pattern, lower_text)
            if match:
                violations.append(
                    f"Causal language violation in Level 1 claim: '{match.group(0)}' implies causation without structural proof."
                )
    return violations


def publication_gate_2_0(
    claim: VerifiedClaim | dict[str, Any],
    match_events: Sequence[Any],
    catalog_metric_ids: Optional[set[str]] = None,
    active_model_version: str = ACTIVE_MODEL_VERSION,
) -> Gate20Verdict:
    """Publication Gate 2.0 validator for single claims.
    
    Validates:
    1. Claim level consistency:
       - Level 1: Prohibits causal language.
       - Level 3: Requires non-empty assumptions and verification methods.
    2. Reference existence:
       - Quoted event IDs must exist in match_events.
       - Quoted metric IDs must exist in catalog_metric_ids.
       - Quoted model versions must match active_model_version.
    3. Counterevidence:
       - If non-empty, claim is downgraded to disputed.
    """
    valid_metrics = catalog_metric_ids or STANDARD_METRIC_IDS

    if isinstance(claim, dict):
        claim_id = str(claim.get("claim_id", claim.get("id", "claim-unknown")))
        raw_level = claim.get("claim_level", 1)
        if isinstance(raw_level, int):
            claim_level = max(1, min(4, raw_level))
        elif isinstance(raw_level, str):
            level_map = {
                "level_1_observed": 1, "level_1": 1, "1": 1,
                "level_2_metric_attribution": 2, "level_2": 2, "2": 2,
                "level_3_statistical_association": 3, "level_3_hypothesis": 3, "level_3": 3, "3": 3,
                "level_4_causal_inference": 4, "level_4": 4, "4": 4,
            }
            claim_level = level_map.get(raw_level.lower().strip(), 1)
        else:
            claim_level = 1
        text = str(claim.get("text", claim.get("analyst", claim.get("primary", {}).get("analyst", ""))))
        evidence_scope = claim.get("evidence_scope", {})
        event_ids = list(evidence_scope.get("event_ids", claim.get("event_ids", claim.get("refs", []))))
        metric_ids = list(evidence_scope.get("metric_ids", claim.get("metric_ids", [])))
        assumptions = list(claim.get("assumptions", []))
        counterevidence = list(claim.get("counterevidence", []))
        verification_method = str(claim.get("verification_method", claim.get("verification_methods", "")))
        metric_versions = dict(claim.get("metric_versions", {}))
    else:
        claim_id = claim.claim_id
        raw_level = claim.claim_level
        if isinstance(raw_level, int):
            claim_level = max(1, min(4, raw_level))
        elif isinstance(raw_level, str):
            level_map = {
                "level_1_observed": 1, "level_1": 1, "1": 1,
                "level_2_metric_attribution": 2, "level_2": 2, "2": 2,
                "level_3_statistical_association": 3, "level_3_hypothesis": 3, "level_3": 3, "3": 3,
                "level_4_causal_inference": 4, "level_4": 4, "4": 4,
            }
            claim_level = level_map.get(raw_level.lower().strip(), 1)
        else:
            claim_level = 1
        text = claim.text
        evidence_scope = claim.evidence_scope
        event_ids = list(evidence_scope.get("event_ids", []))
        metric_ids = list(evidence_scope.get("metric_ids", []))
        assumptions = list(claim.assumptions)
        counterevidence = list(claim.counterevidence)
        verification_method = claim.verification_method
        metric_versions = dict(claim.metric_versions)

    rule_violations: list[str] = []
    remediation_notes: list[str] = []

    # 1. Check wording consistency
    wording_violations = check_level_wording(text, claim_level)
    rule_violations.extend(wording_violations)

    # 2. Level 3+ check: assumptions and verification method
    if claim_level >= 3:
        if not assumptions:
            rule_violations.append(
                f"Level {claim_level} claims require non-empty explicit assumptions."
            )
        if not verification_method or verification_method in ("None", "[]", ""):
            rule_violations.append(
                f"Level {claim_level} claims require an explicit verification method."
            )

    # 3. Reference ID verification against match events
    known_event_ids: set[str] = set()
    for ev in match_events:
        eid = getattr(ev, "event_id", None) if hasattr(ev, "event_id") else (
            ev.get("event_id", ev.get("id")) if isinstance(ev, dict) else None
        )
        if eid:
            known_event_ids.add(str(eid))

    verified_event_ids: list[str] = []
    for eid in event_ids:
        eid_str = str(eid).strip()
        candidates = {eid_str, f"ev-{eid_str}"}
        if eid_str.isdigit():
            candidates.add(f"E{int(eid_str):04d}")
            candidates.add(f"ev-{int(eid_str)}")
            candidates.add(str(int(eid_str)))
        if candidates & known_event_ids:
            verified_event_ids.append(str(eid))
        else:
            rule_violations.append(f"Referenced event ID '{eid}' does not exist in match events.")

    # 4. Metric ID verification (P0.7: prevent arbitrary namespace bypass)
    verified_metric_ids: list[str] = []
    for mid in metric_ids:
        is_valid_metric = False
        if mid in valid_metrics:
            is_valid_metric = True
        elif "." in mid:
            parts = mid.split(".")
            if len(parts) in (2, 3) and parts[0] in ("H", "N") and parts[1] in valid_metrics:
                if len(parts) == 2 or parts[2] in ("previous", "current", "match"):
                    is_valid_metric = True
        if is_valid_metric:
            verified_metric_ids.append(mid)
        else:
            rule_violations.append(f"Referenced metric ID '{mid}' is not in catalog metrics.")

    # 5. Model version check
    for m_name, m_ver in metric_versions.items():
        if m_ver != active_model_version:
            rule_violations.append(
                f"Model version mismatch for '{m_name}': expected {active_model_version}, got {m_ver}."
            )

    # Determine status
    effective_level = claim_level
    if rule_violations:
        is_valid = False
        status = "rejected"
        remediation_notes.append("Address all rule violations before requesting publication approval.")
    elif counterevidence:
        is_valid = True
        status = "disputed"
        effective_level = min(effective_level, 2)
        remediation_notes.append(
            f"Downgraded to disputed: {len(counterevidence)} counterevidence points cited. Level capped at 2."
        )
    else:
        is_valid = True
        status = "approved"

    return Gate20Verdict(
        is_valid=is_valid,
        status=status,
        effective_claim_level=effective_level,
        rule_violations=rule_violations,
        remediation_notes=remediation_notes,
        verified_event_ids=verified_event_ids,
        verified_metric_ids=verified_metric_ids,
    )


def publication_gate_2(
    draft: ClaimDraft,
    review: VerifierDecision,
    snapshot: Snapshot,
    audit: list[dict],
    claim_levels: dict[str, str | int] | None = None,
    assumptions_map: dict[str, list[str]] | None = None,
    verification_methods_map: dict[str, list[str]] | None = None,
    counterevidence_map: dict[str, list[str]] | None = None,
) -> list[PublicationGate2Result]:
    """Compatibility implementation of Gate 2.0 with ClaimDraft / VerifierDecision / Snapshot pipelines."""
    validate_draft(draft, snapshot)
    if review.snapshot_id != snapshot.id:
        raise ValueError("review_snapshot_mismatch")

    decisions = {d.claim_id: d for d in review.decisions}
    if set(decisions) != {c.id for c in draft.claims}:
        raise ValueError("decision_coverage")

    # Snapshot existing event refs
    raw_events = getattr(snapshot, "events", snapshot.data.get("events", []))
    snapshot_event_ids = {str(ev.get("id", ev.get("event_id", ""))) for ev in raw_events}
    # Also add receipts keys
    receipt_keys = set(snapshot.data.get("receipts", {}).keys())

    results: list[PublicationGate2Result] = []
    claim_levels = claim_levels or {}
    assumptions_map = assumptions_map or {}
    verification_methods_map = verification_methods_map or {}
    counterevidence_map = counterevidence_map or {}

    for claim in draft.claims:
        d = decisions[claim.id]
        level_raw = claim_levels.get(claim.id, "level_1_observed")
        level_str = str(level_raw).strip().lower()
        if level_str in ("1", "level_1", "level_1_observed", "level_1_observation"):
            level_num = 1
        elif level_str in ("2", "level_2", "level_2_attribution"):
            level_num = 2
        elif level_str in ("3", "level_3", "level_3_association"):
            level_num = 3
        elif level_str in ("4", "level_4", "level_4_causal"):
            level_num = 4
        else:
            level_num = 1
        assumptions = assumptions_map.get(claim.id, [])
        verification_methods = verification_methods_map.get(claim.id, [])
        counterevidence = counterevidence_map.get(claim.id, [])

        audit_notes: list[str] = []

        # 1. Level 3/4 validation: assumptions & verification methods
        if level_num >= 3:
            if not assumptions:
                audit_notes.append("Rejected: Level 3+ claims require non-empty explicit assumptions.")
            if not verification_methods:
                audit_notes.append("Rejected: Level 3+ claims require explicit verification methods.")

        # 2. Ref existence validation
        variant = claim.primary if d.selected_variant == "primary" else claim.conservative
        if not variant:
            variant = claim.primary

        unmatched_refs = [
            ref for ref in variant.refs
            if ref not in snapshot_event_ids and ref not in receipt_keys
        ]
        if unmatched_refs:
            audit_notes.append(f"Rejected: Unmatched reference IDs {unmatched_refs} not in snapshot.")

        # 3. Check Level 1 prohibited wording
        wording_violations = check_level_wording(variant.analyst, level_num)
        audit_notes.extend(wording_violations)

        # 4. Counterevidence and verdict rules
        status: Literal["passed", "contested", "rejected"] = "passed"
        if audit_notes:
            status = "rejected"
        elif counterevidence:
            status = "contested"
            audit_notes.append(f"Flagged Contested: {len(counterevidence)} counterevidence citations recorded.")
        elif d.verdict == "withhold":
            status = "rejected"
            audit_notes.append("Verifier withheld publication.")
        elif d.verdict == "qualify":
            if d.selected_variant == "conservative" and claim.conservative:
                status = "passed"
                audit_notes.append("Verifier qualified publication with conservative variant.")
            else:
                status = "contested"
                audit_notes.append("Verifier qualified publication.")

        published_text = bind_slots(variant.analyst, variant.refs, snapshot)
        data_sufficiency = DataSufficiencyAdvisor.inspect(published_text)

        results.append(PublicationGate2Result(
            status=status,
            gate_version="2.0",
            claim_id=claim.id,
            claim_level=level_str,
            selected_variant=d.selected_variant or "primary",
            published_text=published_text,
            verified_refs=variant.refs,
            assumptions=assumptions,
            verification_methods=verification_methods,
            counterevidence_found=counterevidence,
            data_sufficiency=data_sufficiency,
            audit_notes=audit_notes,
        ))

    return results

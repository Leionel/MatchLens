"""Bounded claims and independently enforced publication rules."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .football import Snapshot

Assertion = Literal["possession_without_penetration", "attacking_threat_increased", "recoveries_followed_by_shots", "recoveries_caused_shots", "goal_sequence"]


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Variant(ClosedModel):
    id: Literal["primary", "conservative"]
    scope: Literal["window", "match", "causal"]
    refs: list[str] = Field(min_length=1, max_length=12)
    fan: str = Field(min_length=15, max_length=350)
    analyst: str = Field(min_length=25, max_length=650)


class Claim(ClosedModel):
    id: str = Field(pattern=r"^claim-[a-z-]{1,32}$")
    assertion: Assertion
    primary: Variant
    conservative: Variant | None = None

    @model_validator(mode="after")
    def variant_ids(self):
        if self.primary.id != "primary" or self.conservative and self.conservative.id != "conservative":
            raise ValueError("variant_id")
        return self


class ClaimDraft(ClosedModel):
    snapshot_id: str
    claims: list[Claim] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def unique_ids(self):
        if len({c.id for c in self.claims}) != len(self.claims):
            raise ValueError("duplicate_claim_id")
        return self


class Decision(ClosedModel):
    claim_id: str
    verdict: Literal["publish", "qualify", "withhold"]
    selected_variant: Literal["primary", "conservative"] | None
    reason: str = Field(min_length=8, max_length=500)
    limitations: list[str] = Field(max_length=4)


class VerifierDecision(ClosedModel):
    snapshot_id: str
    decisions: list[Decision] = Field(min_length=1, max_length=2)


REQUIRED = {
    "possession_without_penetration": {f"H.{m}.{w}" for m in ("possession", "shots", "entries") for w in ("previous", "current")},
    "attacking_threat_increased": {f"H.{m}.{w}" for m in ("shots", "entries") for w in ("previous", "current")},
    "recoveries_followed_by_shots": {"H.high_recoveries.current", "H.transition_shots.current"},
    "recoveries_caused_shots": {"H.high_recoveries.current", "H.transition_shots.current"},
    "goal_sequence": {"H.goals.match"},
}
SLOT = re.compile(r"\{\{([HN]\.[a-z_]+\.(?:previous|current|match))\}\}")
UNSUPPORTED = re.compile(r"\bxg\b|\bpress(?:ing|ed)?\b|\bformation\b|\bfatigue\b|\bcoach(?:ing)?\b|\bcaus(?:e[ds]?|ed|ation)\b|\bbecause\b|\bforced\b|\bproves?\b|\bguarantee|\bhalf[- ]?time\b|\bafter the break\b|\b(?:first|second) half\b", re.I)


def assertion_supported(assertion: str, snapshot: Snapshot) -> bool:
    r = snapshot.data["receipts"]
    def v(metric: str, window: str = "current") -> float:
        return r[f"H.{metric}.{window}"]["value"]
    if assertion == "possession_without_penetration":
        return (v("possession") > v("possession", "previous") and v("shots") <= v("shots", "previous")
                and v("entries") <= v("entries", "previous"))
    if assertion == "attacking_threat_increased":
        return v("shots") > v("shots", "previous") and v("entries") > v("entries", "previous")
    if assertion == "recoveries_followed_by_shots":
        return v("transition_shots") >= 2 and v("high_recoveries") >= 1
    if assertion == "goal_sequence":
        return r["H.goals.match"]["value"] > 0 and bool(r["H.goals.match"]["chains"])
    return False  # Temporal association cannot establish recoveries_caused_shots.


def validate_draft(draft: ClaimDraft, snapshot: Snapshot) -> None:
    if draft.snapshot_id != snapshot.id:
        raise ValueError("draft_snapshot_mismatch")
    known = snapshot.data["receipts"]
    for claim in draft.claims:
        for variant in (claim.primary, claim.conservative):
            if variant and (len(set(variant.refs)) != len(variant.refs) or any(r not in known for r in variant.refs)):
                raise ValueError("unknown_or_duplicate_reference")


def bind_slots(text: str, refs: list[str], snapshot: Snapshot) -> str:
    receipts = snapshot.data["receipts"]
    for key in SLOT.findall(text):
        if key not in refs or key not in receipts:
            raise ValueError("unreferenced_fact_slot")
        if receipts[key]["unit"] == "%" and "{{"+key+"}}%" in text:
            raise ValueError("percentage_slot_already_has_unit")
    stripped = SLOT.sub("", text)
    if re.search(r"[0-9]", stripped) or "{{" in stripped or "}}" in stripped:
        raise ValueError("unbound_numeric_prose")
    def replace(match):
        receipt = receipts[match.group(1)]
        number = f"{receipt['value']:g}"
        return number+"%" if receipt["unit"] == "%" else number
    return SLOT.sub(replace, text)


def render_text(text: str, refs: list[str], snapshot: Snapshot) -> str:
    # A valid limitation ("cannot show that pressing was the method") is not
    # an asserted tactic. Split contrast clauses so a disclaimer cannot hide a
    # positive unsupported claim after "but" or "however".
    for clause in re.split(r"[.;!?]|\bbut\b|\bhowever\b", SLOT.sub("", text), flags=re.I):
        negative = re.search(r"\b(?:cannot (?:show|establish|demonstrate|explain)|does not (?:show|establish|demonstrate)|no evidence (?:of|for)|not evidence (?:of|for))\b", clause, re.I)
        if UNSUPPORTED.search(clause) and not negative:
            raise ValueError("unsupported_prose_concept")
    return bind_slots(text, refs, snapshot)


def publication_gate(draft: ClaimDraft, review: VerifierDecision, snapshot: Snapshot, audit: list[dict]) -> dict:
    validate_draft(draft, snapshot)
    if review.snapshot_id != snapshot.id:
        raise ValueError("review_snapshot_mismatch")
    decisions = {d.claim_id: d for d in review.decisions}
    if len(decisions) != len(review.decisions) or set(decisions) != {c.id for c in draft.claims}:
        raise ValueError("decision_coverage")
    # Tool results must have been returned to each model, not merely executed locally.
    for role in ("Analyst", "Verifier"):
        if not any(e.get("type") == "tool" and e.get("role") == role and e.get("snapshot_id") == snapshot.id for e in audit):
            raise ValueError("missing_evidence_tool")
        if not any(e.get("type") == "tool_receipt" and e.get("role") == role for e in audit):
            raise ValueError("missing_tool_receipt_roundtrip")
    if not any(e.get("type") == "handoff" and e.get("snapshot_id") == snapshot.id for e in audit):
        raise ValueError("missing_handoff")
    accepted, rejected = [], []
    for claim in draft.claims:
        d = decisions[claim.id]
        # Public review prose obeys the same numeric binding rule; unlike an
        # accepted claim it may discuss why a causal assertion was rejected.
        refs = list(set(claim.primary.refs + (claim.conservative.refs if claim.conservative else [])))
        public_reason = bind_slots(d.reason, refs, snapshot)
        public_limitations = [bind_slots(text, refs, snapshot) for text in d.limitations]
        reason = None
        variant = claim.primary if d.selected_variant == "primary" else claim.conservative
        if d.verdict == "withhold":
            if d.selected_variant is not None:
                raise ValueError("withhold_has_variant")
            reason = "verifier_withheld"
        elif not assertion_supported(claim.assertion, snapshot):
            reason = "unsupported_core_assertion"
        elif d.verdict == "publish" and d.selected_variant != "primary" or d.verdict == "qualify" and d.selected_variant != "conservative":
            reason = "verdict_variant_mismatch"
        elif variant is None:
            reason = "missing_variant"
        elif variant.scope != ("match" if claim.assertion == "goal_sequence" else "window"):
            reason = "unsupported_scope"
        elif not REQUIRED[claim.assertion].issubset(variant.refs):
            reason = "missing_supporting_receipts"
        if reason is None:
            try:
                fan = render_text(variant.fan, variant.refs, snapshot)
                analyst = render_text(variant.analyst, variant.refs, snapshot)
                if len(fan.split()) > 45 or len(analyst.split()) > 100:
                    raise ValueError("audience_word_limit")
            except ValueError as exc:
                reason = str(exc)
        if reason:
            rejected.append({"claim_id": claim.id, "assertion": claim.assertion, "verdict": d.verdict,
                             "gate": reason, "reason": public_reason})
        else:
            accepted.append({"claim_id": claim.id, "assertion": claim.assertion, "verdict": d.verdict,
                             "selected_variant": variant.id, "scope": variant.scope, "refs": variant.refs,
                             "fan": fan, "analyst": analyst, "reason": public_reason,
                             "limitations": public_limitations, "snapshot_id": snapshot.id, "as_of": snapshot.data["as_of"]})
    return {"accepted": accepted, "rejected": rejected}

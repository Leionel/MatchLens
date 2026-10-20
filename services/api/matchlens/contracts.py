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
QUANTITATIVE_WORDS = re.compile(
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|dozen|once|twice|thrice)\b",
    re.I,
)
PREVIOUS_WINDOW_REFERENCE = re.compile(
    r"\b(?:previous|prior|earlier)\b.*\bwindow\b|\bprevious[- ]window\b|\bearlier window\b",
    re.I,
)


def required_refs(assertion: str, team: str = "H") -> set[str]:
    return {r.replace("H.", f"{team}.", 1) for r in REQUIRED[assertion]}


def infer_team_from_refs(refs: list[str]) -> str:
    return "N" if refs and all(r.startswith("N.") for r in refs) else "H"


def assertion_supported(assertion: str, snapshot: Snapshot, team: str = "H") -> bool:
    r = snapshot.data["receipts"]
    def v(metric: str, window: str = "current") -> float:
        return r.get(f"{team}.{metric}.{window}", {}).get("value", 0)
    if assertion == "possession_without_penetration":
        return (v("possession") > v("possession", "previous") and v("shots") <= v("shots", "previous")
                and v("entries") <= v("entries", "previous"))
    if assertion == "attacking_threat_increased":
        return v("shots") > v("shots", "previous") and v("entries") > v("entries", "previous")
    if assertion == "recoveries_followed_by_shots":
        return v("transition_shots") >= 2 and (v("high_recoveries") >= 1 or team == "N")
    if assertion == "goal_sequence":
        goal_rec = r.get(f"{team}.goals.match", {"value": 0, "chains": []})
        return goal_rec["value"] > 0 and bool(goal_rec["chains"])
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
    stripped = SLOT.sub("", text)
    if QUANTITATIVE_WORDS.search(stripped):
        raise ValueError("unbound_spelled_number")
    if PREVIOUS_WINDOW_REFERENCE.search(text) and not any(r.endswith(".previous") for r in refs):
        raise ValueError("unreferenced_previous_window_fact")
    for sentence in re.split(r"[!?;]|\.(?=\s|$)", text):
        if PREVIOUS_WINDOW_REFERENCE.search(sentence) and not re.search(r"\bcurrent\b", SLOT.sub("", sentence), re.I):
            if any(key.endswith(".current") for key in SLOT.findall(sentence)):
                raise ValueError("fact_window_mismatch")
    for clause in re.split(r"[.;!?]|\bbut\b|\bhowever\b", stripped, flags=re.I):
        negative = re.search(r"\b(?:cannot (?:show|establish|demonstrate|explain)|does not (?:show|establish|demonstrate)|no evidence (?:of|for)|not evidence (?:of|for))\b", clause, re.I)
        if UNSUPPORTED.search(clause) and not negative:
            raise ValueError("unsupported_prose_concept")
    return bind_slots(text, refs, snapshot)


def evidence_summary(assertion: str, snapshot: Snapshot, team: str = "H") -> tuple[str, str]:
    """Finite public fact rendering after model selection/review, never a repair
    of a false core. Free-form drafts remain in the operator run receipt only.
    The renderer binds metric names, periods and values as a single fact.
    """
    r = snapshot.data["receipts"]
    team_name = "Northbridge" if team == "N" else "Harbor"
    def value(metric, period="current"):
        return f"{r.get(f'{team}.{metric}.{period}', {'value': 0})['value']:g}"
    at = snapshot.data["as_of"]
    start = max(0, at-180)
    window = f"{start//60:02d}:{start%60:02d}–{at//60:02d}:{at%60:02d}"
    if assertion == "possession_without_penetration":
        fan = f"More of the ball, no extra shots or entries: {team_name}'s controlled possession rose from {value('possession', 'previous')}% to {value('possession')}%, while shots and attacking-third entries did not increase."
        analyst = f"Window {window}. Controlled possession: {value('possession', 'previous')}% → {value('possession')}%. Shots: {value('shots', 'previous')} → {value('shots')}. Attacking-third entries: {value('entries', 'previous')} → {value('entries')}. Greater controlled time did not coincide with greater activity on these measures."
    elif assertion == "attacking_threat_increased":
        fan = f"{team_name}'s attacking activity grew: shots increased from {value('shots', 'previous')} to {value('shots')}, and attacking-third entries from {value('entries', 'previous')} to {value('entries')}."
        analyst = f"Window {window}. Both recorded shot attempts and attacking-third entries increased against the preceding window. These activity counts do not measure chance quality or establish a tactical cause."
    elif assertion == "recoveries_followed_by_shots":
        fan = f"Quick attacks after winning the ball: {value('transition_shots')} recovery-to-shot chains in this window. {team_name} also recorded {value('high_recoveries')} high recoveries."
        analyst = f"Window {window}. High recoveries: {value('high_recoveries')}. Recovery-to-shot chains within 10 seconds without a loss of possession: {value('transition_shots')}. Inspect each chain's recovery location and elapsed time. This is a short-window association, not evidence of pressing or causation."
    else:
        chain = r[f"{team}.goals.match"]["chains"][-1]
        fan = f"{team_name} scored. Follow the {len(chain)} recorded on-ball events in the scoring move, ending with the goal."
        analyst = f"As of {at//60:02d}:{at%60:02d}: {team_name} has {value('goals', 'match')} recorded goal(s). The latest uninterrupted scoring chain contains {len(chain)} events, from {chain[0]} to {chain[-1]}. The sequence establishes what happened on the ball; it does not explain off-ball tactics or why the goal occurred."
    return fan, analyst


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
        claim_team = infer_team_from_refs(variant.refs if variant else claim.primary.refs)
        if d.verdict == "withhold":
            if d.selected_variant is not None:
                raise ValueError("withhold_has_variant")
            reason = "verifier_withheld"
        elif not assertion_supported(claim.assertion, snapshot, claim_team):
            reason = "unsupported_core_assertion"
        elif d.verdict == "publish" and d.selected_variant != "primary" or d.verdict == "qualify" and d.selected_variant != "conservative":
            reason = "verdict_variant_mismatch"
        elif variant is None:
            reason = "missing_variant"
        elif variant.scope != ("match" if claim.assertion == "goal_sequence" else "window"):
            reason = "unsupported_scope"
        elif not required_refs(claim.assertion, claim_team).issubset(variant.refs):
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
            # Typed assertion + frozen receipts own public facts, including the
            # period and metric label. Do not render incidental model prose.
            fan, analyst = evidence_summary(claim.assertion, snapshot, claim_team)
            accepted.append({"claim_id": claim.id, "assertion": claim.assertion, "verdict": d.verdict,
                             "selected_variant": variant.id, "scope": variant.scope, "refs": variant.refs,
                             "fan": fan, "analyst": analyst,
                             "reason": f"Verifier decision: {d.verdict}. The core assertion, scope and required receipt references passed publication checks.",
                             "limitations": ["Synthetic on-ball events; no off-ball tracking or causal-effect evidence.", "A short window does not establish a whole-match trend."] if variant.scope == "window" else ["Recorded scoring sequence only; no off-ball tracking or tactical cause."],
                             "render_contract": "bound-facts-v1", "snapshot_id": snapshot.id, "as_of": snapshot.data["as_of"]})
    return {"accepted": accepted, "rejected": rejected}

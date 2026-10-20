import pytest

from matchlens.contracts import ClaimDraft, REQUIRED, VerifierDecision, publication_gate
from matchlens.football import freeze, generate_match


@pytest.fixture
def snap():
    return freeze(generate_match(), 360)


def draft(snap, assertion="possession_without_penetration", primary_scope="window"):
    variant = {"id": "primary", "scope": primary_scope, "refs": sorted(REQUIRED[assertion]),
               "fan": "More of the ball, but no extra shots or entries in this window.",
               "analyst": "Harbor's controlled possession rose to {{H.possession.current}}, with no increase in the observed shot or entry counts."}
    return ClaimDraft.model_validate({"snapshot_id": snap.id, "claims": [{"id": "claim-possession", "assertion": assertion,
           "primary": variant, "conservative": {**variant, "id": "conservative", "scope": "window"}}]})


def review(snap, verdict="publish", selected="primary"):
    return VerifierDecision.model_validate({"snapshot_id": snap.id, "decisions": [{"claim_id": "claim-possession",
        "verdict": verdict, "selected_variant": selected, "reason": "Window receipts support the comparison.", "limitations": ["Short sample; no causal claim."]}]})


def audit(snap):
    return [{"type": t, "role": role, "snapshot_id": snap.id} for t in ("tool", "tool_receipt") for role in ("Analyst", "Verifier")]+[{"type": "handoff", "snapshot_id": snap.id}]


def test_supported_publish_and_bound_numeric_slots(snap):
    result = publication_gate(draft(snap), review(snap), snap, audit(snap))
    assert "83.33%" in result["accepted"][0]["analyst"]


def test_qualify_only_narrows_same_true_core(snap):
    result = publication_gate(draft(snap, primary_scope="match"), review(snap, "qualify", "conservative"), snap, audit(snap))
    assert result["accepted"][0]["scope"] == "window"


@pytest.mark.parametrize("assertion", ["attacking_threat_increased", "recoveries_caused_shots"])
def test_disclaimer_cannot_repair_false_core_or_causality(snap, assertion):
    result = publication_gate(draft(snap, assertion), review(snap, "qualify", "conservative"), snap, audit(snap))
    assert not result["accepted"]
    assert result["rejected"][0]["gate"] == "unsupported_core_assertion"


def test_contradictory_receipts_override_verifier(snap):
    result = publication_gate(draft(snap, "attacking_threat_increased"), review(snap), snap, audit(snap))
    assert result["rejected"][0]["gate"] == "unsupported_core_assertion"


def test_withhold_and_no_free_revision(snap):
    result = publication_gate(draft(snap), review(snap, "withhold", None), snap, audit(snap))
    assert not result["accepted"]
    assert result["rejected"][0]["gate"] == "verifier_withheld"
    with pytest.raises(ValueError, match="withhold_has_variant"):
        publication_gate(draft(snap), review(snap, "withhold", "conservative"), snap, audit(snap))


@pytest.mark.parametrize("prose", ["Harbor recorded 900 shots in this window.", "Pressing forced Harbor's attacking improvement.", "The figure is {{H.goals.match}} goals.", "Harbor dominated possession after the break."])
def test_unbound_numbers_unavailable_concepts_and_unreferenced_slots(snap, prose):
    claim = draft(snap)
    claim.claims[0].primary.fan = prose
    result = publication_gate(claim, review(snap), snap, audit(snap))
    assert not result["accepted"]


def test_unknown_reference_wrong_snapshot_and_missing_tool_fail(snap):
    claim = draft(snap)
    claim.claims[0].primary.refs.append("H.xg.current")
    with pytest.raises(ValueError, match="reference"):
        publication_gate(claim, review(snap), snap, audit(snap))
    r = review(snap)
    r.snapshot_id = "another-snapshot"
    with pytest.raises(ValueError, match="snapshot"):
        publication_gate(draft(snap), r, snap, audit(snap))
    with pytest.raises(ValueError, match="tool"):
        publication_gate(draft(snap), review(snap), snap, [])


def test_explicit_limitation_is_allowed_but_cannot_hide_positive_tactic(snap):
    claim = draft(snap)
    claim.claims[0].primary.analyst = "Possession rose without more shots or entries. These events cannot show that pressing was the method."
    assert publication_gate(claim, review(snap), snap, audit(snap))["accepted"]
    claim.claims[0].primary.analyst += " But pressing forced an improvement."
    assert not publication_gate(claim, review(snap), snap, audit(snap))["accepted"]


@pytest.mark.parametrize("spelled", [
    "Harbor had zero shots in this window.",
    "Harbor attacked twice in the final third.",
    "Harbor registered two shots without penetration.",
    "Four recoveries were won high up the pitch.",
    "Harbor recorded eleven shots in this window.",
    "Harbor recorded four successful shots in this window.",
    "Harbor recorded one hundred shots in this window.",
])
def test_spelled_numeric_quantifiers_rejected(snap, spelled):
    claim = draft(snap)
    claim.claims[0].primary.fan = spelled
    result = publication_gate(claim, review(snap), snap, audit(snap))
    assert not result["accepted"]
    assert result["rejected"][0]["gate"] == "unbound_spelled_number"


def test_unreferenced_previous_window_fact_rejected():
    snap_b = freeze(generate_match(), 540)
    variant = {
        "id": "primary",
        "scope": "window",
        "refs": ["H.high_recoveries.current", "H.transition_shots.current"],
        "fan": "Harbor won the ball high up the pitch and produced quick transition shots.",
        "analyst": "Harbor recorded high recoveries, but previous window values were different without citing previous receipts."
    }
    claim = ClaimDraft.model_validate({
        "snapshot_id": snap_b.id,
        "claims": [{
            "id": "claim-recovery-shots",
            "assertion": "recoveries_followed_by_shots",
            "primary": variant,
            "conservative": None
        }]
    })
    rev = VerifierDecision.model_validate({
        "snapshot_id": snap_b.id,
        "decisions": [{
            "claim_id": "claim-recovery-shots",
            "verdict": "publish",
            "selected_variant": "primary",
            "reason": "Receipts support transition shots.",
            "limitations": []
        }]
    })
    result = publication_gate(claim, rev, snap_b, audit(snap_b))
    assert not result["accepted"]
    assert result["rejected"][0]["gate"] == "unreferenced_previous_window_fact"


def test_a_previous_receipt_cannot_launder_current_value_into_previous_window():
    snap = freeze(generate_match(), 540)
    claim = draft(snap, "recoveries_followed_by_shots")
    claim.claims[0].primary.refs += ["H.possession.previous", "H.shots.current"]
    claim.claims[0].primary.fan = "Harbor's previous window had {{H.shots.current}} shots."
    claim.claims[0].primary.analyst = "Recovery and shot receipts establish a short-window association only."
    result = publication_gate(claim, review(snap), snap, audit(snap))
    assert result["rejected"][0]["gate"] == "fact_window_mismatch"


def test_public_facts_are_rendered_from_typed_assertion_and_exact_receipts(snap):
    claim = draft(snap)
    claim.claims[0].primary.fan = "Harbor's fans celebrated a magnificent tactical masterclass."
    result = publication_gate(claim, review(snap), snap, audit(snap))
    card = result["accepted"][0]
    assert "masterclass" not in card["fan"]
    assert "83.33%" in card["fan"] and "44.44%" in card["fan"]
    assert "Shots: 2 → 0" in card["analyst"]
    assert card["render_contract"] == "bound-facts-v1"

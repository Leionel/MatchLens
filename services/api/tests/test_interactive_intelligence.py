import pytest
from matchlens.football import freeze, generate_match
from matchlens.contracts import (
    ChallengeRequest,
    ChallengeResult,
    HypothesisLabMatrix,
    TypedClaimPlan,
    ask_the_match,
    evaluate_hypotheses,
    generate_evidence_gap_report,
    resolve_challenge,
)


def test_typed_claim_plan_contract():
    plan = TypedClaimPlan(
        claim_id="plan-001",
        subject_team="H",
        assertion="possession_without_penetration",
        scope="window",
        time_window=(180, 360),
        supporting_refs=["H.possession.current", "H.possession.previous"],
        counterevidence_refs=["H.shots.current", "H.entries.current"],
        quantitative_facts={"possession": 83.33, "shots": 0},
        interpretation="Greater possession without penetration.",
        limitations=["180s observation window only."],
    )
    assert plan.claim_id == "plan-001"
    assert plan.subject_team == "H"
    assert len(plan.supporting_refs) == 2
    assert len(plan.counterevidence_refs) == 2


def test_competing_hypotheses_evaluation_across_match_states():
    events = generate_match(seed=17, scenario="default")
    
    # 1. At 360s: Possession Dominance vs Lack of Penetration
    snap_360 = freeze(events, 360)
    matrix_360 = evaluate_hypotheses(snap_360, "H")
    assert isinstance(matrix_360, HypothesisLabMatrix)
    assert matrix_360.as_of == 360
    assert len(matrix_360.hypotheses) >= 2
    # Check that surface hypothesis claiming increased threat was rejected
    h1 = next(h for h in matrix_360.hypotheses if h.id == "hyp-1")
    assert h1.status in ("rejected", "qualified")
    # Alternative hypothesis (possession without penetration) is supported
    h2 = next(h for h in matrix_360.hypotheses if h.id == "hyp-2")
    assert h2.status in ("supported", "qualified")

    # 2. At 540s: High recovery & transition burst
    snap_540 = freeze(events, 540)
    matrix_540 = evaluate_hypotheses(snap_540, "H")
    assert matrix_540.as_of == 540
    # Causal overreach claiming "coordinated press systematically forced turnovers" is rejected
    overreach = next((h for h in matrix_540.hypotheses if h.hypothesis_type == "causal_overreach"), None)
    if overreach:
        assert overreach.status == "rejected"

    # 3. At 720s: Goal breakthrough
    snap_720 = freeze(events, 720)
    matrix_720 = evaluate_hypotheses(snap_720, "H")
    assert matrix_720.as_of == 720
    assert any(h.claim_assertion == "goal_sequence" and h.status == "supported" for h in matrix_720.hypotheses)

    # 4. Away team Northbridge hypotheses
    ca_events = generate_match(seed=17, scenario="counterattack")
    ca_snap = freeze(ca_events, 720)
    ca_matrix = evaluate_hypotheses(ca_snap, "N")
    assert ca_matrix.team == "N"
    assert any(h.team == "N" and h.status == "supported" for h in ca_matrix.hypotheses)


def test_interactive_challenge_resolution():
    events = generate_match(seed=17, scenario="default")
    snap_360 = freeze(events, 360)

    # Challenge 1: Causal interpretation
    res_causal = resolve_challenge(
        snap_360,
        ChallengeRequest(
            claim_id="claim-possession",
            snapshot_id=snap_360.id,
            challenge_type="challenge_causal_interpretation",
            team="H",
        ),
    )
    assert res_causal.outcome == "narrowed"
    assert "observational finding" in res_causal.resolution_summary
    assert res_causal.evidence_gap is not None

    # Challenge 2: Counterevidence check
    res_counter = resolve_challenge(
        snap_360,
        ChallengeRequest(
            claim_id="claim-possession",
            snapshot_id=snap_360.id,
            challenge_type="check_counterevidence",
            team="H",
        ),
    )
    assert res_counter.outcome == "maintained"
    assert len(res_counter.counterevidence_checked) >= 2

    # Challenge 3: Sample sufficiency at early stage (<360s) vs mature stage (>=360s)
    snap_180 = freeze(events, 180)
    res_sample_early = resolve_challenge(
        snap_180,
        ChallengeRequest(
            claim_id="claim-early",
            snapshot_id=snap_180.id,
            challenge_type="check_sample_sufficiency",
            team="H",
        ),
    )
    assert res_sample_early.outcome == "narrowed"

    res_sample_mature = resolve_challenge(
        snap_360,
        ChallengeRequest(
            claim_id="claim-mature",
            snapshot_id=snap_360.id,
            challenge_type="check_sample_sufficiency",
            team="H",
        ),
    )
    assert res_sample_mature.outcome == "maintained"

    # Challenge 4: Comparison window & sequence
    res_win = resolve_challenge(
        snap_360,
        ChallengeRequest(
            claim_id="claim-window",
            snapshot_id=snap_360.id,
            challenge_type="check_comparison_window",
            team="H",
        ),
    )
    assert res_win.outcome == "maintained"


def test_evidence_gap_advisor_honest_boundaries():
    events = generate_match(seed=17)
    snap = freeze(events, 540)

    # Pressing / formation boundary
    press_report = generate_evidence_gap_report("pressing tactics", snap, "H")
    assert any("22-player off-ball" in item for item in press_report.missing_data)
    assert "coordinated high press" in press_report.unsupported_inference
    assert len(press_report.available_evidence) >= 1

    # xG chance quality boundary
    xg_report = generate_evidence_gap_report("xg quality", snap, "H")
    assert "Goalkeeper position" in xg_report.missing_data[0]
    assert "expected goals (xG)" in xg_report.unsupported_inference


def test_ask_the_match_constrained_query_engine():
    events = generate_match(seed=17)
    snap_360 = freeze(events, 360)

    ans_poss = ask_the_match(snap_360, "possession_vs_penetration", "H")
    assert "controlled possession" in ans_poss["answer"]
    assert len(ans_poss["evidence_chips"]) == 3
    assert "gap_advisor" in ans_poss

    snap_720 = freeze(events, 720)
    ans_goal = ask_the_match(snap_720, "scoring_sequence_breakdown", "H")
    assert "scoring sequence spanned" in ans_goal["answer"]
    assert len(ans_goal["evidence_chips"]) >= 1

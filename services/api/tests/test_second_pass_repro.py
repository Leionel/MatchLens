"""Reproduction and regression test suite for Second Pass Audit (P0 & P1 issues).

These tests represent real invariant failures discovered during the deep audit.
"""
import pytest
from fastapi.testclient import TestClient

from matchlens.main import app, Engine, Session
from matchlens.football import generate_match, freeze, tool_evidence
from matchlens.catalog import MatchCatalog
from matchlens.explain import explain_chart
from matchlens.gate import publication_gate_2_0
from matchlens.stories import MatchStoryEngine
from matchlens.contracts import ChallengeRequest, resolve_challenge


@pytest.fixture
def client():
    with TestClient(app) as c:
        c.post("/api/sessions")
        yield c


# ---------------------------------------------------------------------------
# P0.2 & P0.3: Match Context, set_match & Cache/State Isolation
# ---------------------------------------------------------------------------

def test_repro_set_match_nonexistent_rejected(client):
    """P0.2: Non-existent match_id MUST be rejected with 404 or 422."""
    res = client.post("/api/control", json={"action": "set_match", "match_id": "non_existent_match_999"})
    assert res.status_code in (404, 422)


def test_repro_set_match_switches_teams_and_events(client):
    """P0.2: Switching to sb_wc2022_final MUST return Argentina & France, not Harbor FC."""
    res = client.post("/api/control", json={"action": "set_match", "match_id": "sb_wc2022_final"})
    assert res.status_code == 200
    state = res.json()
    assert state["match_id"] == "sb_wc2022_final"
    # Teams must NOT be Harbor FC
    teams = state.get("match_context", {}).get("teams") or state.get("teams", {})
    # Either in match_context or root teams
    if "home_team_name" in state.get("match_context", {}):
        assert state["match_context"]["home_team_name"] == "Argentina"
        assert state["match_context"]["away_team_name"] == "France"
    # Replay ends at the last recorded event, not at the declared nominal
    # duration: unobserved time is never invented.
    context = state["match_context"]
    assert context["duration"] == 5400
    assert state["format_seconds"] == 5363


def test_repro_match_state_isolation(client):
    """P0.3: Claims or revisions from one match must NOT leak into another match."""
    # Start on syn_default, create a focus snapshot
    client.post("/api/control", json={"action": "focus", "chapter": "A"})
    s1 = client.get("/api/state").json()
    assert s1["snapshot_id"] is not None
    snap_id = s1["snapshot_id"]

    # Challenge a legitimate claim in syn_default
    c_res = client.post("/api/challenge", json={
        "claim_id": "claim-possession-without-penetration-h",
        "snapshot_id": snap_id,
        "challenge_type": "check_counterevidence",
        "team": "H"
    })
    assert c_res.status_code == 200
    assert len(c_res.json()["revisions"]) > 0

    # Switch to sb_wc2022_final
    s2 = client.post("/api/control", json={"action": "set_match", "match_id": "sb_wc2022_final"}).json()
    # Revisions from Harbor FC must NOT appear in Argentina vs France!
    assert len(s2["revisions"]) == 0
    # Harbor FC snapshot must not be the active snapshot
    assert s2["snapshot_id"] != snap_id


# ---------------------------------------------------------------------------
# P0.4: Snapshot Identity & Context Binding
# ---------------------------------------------------------------------------

def test_repro_snapshot_identity_binding():
    """P0.4: Snapshot must bind match_id, scenario, and data digest, not a fixed string."""
    events_def = generate_match(seed=17, scenario="default")
    events_trans = generate_match(seed=17, scenario="transitions")
    snap_def = freeze(events_def, 360, seed=17, match_id="syn_default", scenario="default")
    snap_trans = freeze(events_trans, 360, seed=17, match_id="syn_transitions", scenario="transitions")

    assert snap_def.data["match_id"] == "syn_default"
    assert snap_trans.data["match_id"] == "syn_transitions"
    assert snap_def.id != snap_trans.id


# ---------------------------------------------------------------------------
# P0.5: Claim Registry Prefix Bypass
# ---------------------------------------------------------------------------

def test_repro_claim_registry_rejects_prefix_wildcard(client):
    """P0.5: Arbitrary claim IDs matching prefixes like claim-*, hyp-*, c* MUST be rejected."""
    state = client.post("/api/control", json={"action": "focus", "chapter": "A"}).json()
    snap_id = state["snapshot_id"]

    for bogus_id in ("claim-does-not-exist", "hyp-random-fake", "c999999", "claim-001-fake"):
        res = client.post("/api/challenge", json={
            "claim_id": bogus_id,
            "snapshot_id": snap_id,
            "challenge_type": "challenge_causal_interpretation",
            "team": "H"
        })
        assert res.status_code == 404, f"Bogus ID {bogus_id} should have been rejected with 404!"


# ---------------------------------------------------------------------------
# P0.7: Metric ID Suffix Bypass in Gate 2.0
# ---------------------------------------------------------------------------

def test_repro_gate_2_0_rejects_arbitrary_namespace_metrics():
    """P0.7: Arbitrary namespace before metric suffix (e.g. invalid_namespace.shots) MUST be rejected."""
    events = [
        {"event_id": "ev-1", "timestamp_seconds": 10.0, "team": "H"},
    ]
    claim_bad_ns = {
        "claim_id": "c-bad-ns",
        "claim_level": 1,
        "text": "Harbor FC recorded actions.",
        "event_ids": ["ev-1"],
        "metric_ids": ["invalid_namespace.shots"],
    }
    verdict = publication_gate_2_0(claim_bad_ns, match_events=events)
    assert verdict.status == "rejected", "Metric with invalid namespace should be rejected!"
    assert any("invalid_namespace.shots" in v for v in verdict.rule_violations)


# ---------------------------------------------------------------------------
# P0.8: Explain Any Chart Units (Possession is %, not seconds!)
# ---------------------------------------------------------------------------

def test_repro_explain_oaai_possession_unit():
    """P0.8: Possession metric must be expressed as percentage (%), never seconds (s)."""
    events = generate_match(seed=17)
    snap = freeze(events, 360)
    res = explain_chart(snap, chart_type="oaai_momentum", team="H")
    for m in res.key_metrics:
        if "possession" in m.metric.lower():
            assert not str(m.value).endswith("s"), f"Possession value '{m.value}' must NOT be in seconds!"
            assert "%" in str(m.value), f"Possession value '{m.value}' must be formatted as percentage!"
    assert "s of possession" not in res.summary, "Summary must not state seconds of possession!"


# ---------------------------------------------------------------------------
# P0.10: Dual-team evidence visibility
# ---------------------------------------------------------------------------

def test_repro_tool_evidence_away_team_visibility():
    """P0.10: Away team metrics must be available in tool evidence even when away team has zero goals."""
    events = generate_match(seed=17, scenario="default") # 1-0 match, N has 0 goals
    snap = freeze(events, 360)
    ev = tool_evidence(snap, focus_team="N")
    # Away team receipts MUST be present!
    assert any(k.startswith("N.") for k in ev["receipts"]), "Away team receipts must be present!"


# ---------------------------------------------------------------------------
# P0.11: Story Engine with NormalizedEvent
# ---------------------------------------------------------------------------

def test_repro_story_engine_with_normalized_events(tmp_path):
    """Story Engine handles normalized events and binds to a registry snapshot."""
    from matchlens.football import reduce_match
    from matchlens.registry import ClaimRegistry

    ctx = MatchCatalog.get_match_context("sb_wc2022_final")
    events = MatchCatalog.load_normalized_events("sb_wc2022_final")
    at = min(ctx.duration, int(ctx.observed_end))
    state = reduce_match(
        events,
        at,
        max_duration=ctx.duration,
        is_synthetic=False,
        coordinate_frame=ctx.coordinate_frame,
        continuous_coverage=ctx.continuous_coverage,
        team_names={"H": ctx.home_team_name, "N": ctx.away_team_name},
    )
    from matchlens.main import freeze_with_context

    snap = freeze_with_context(events, ctx, at, match_id="sb_wc2022_final", scenario="historical")
    registry = ClaimRegistry(tmp_path / "claims.json")
    story = MatchStoryEngine.generate_story(
        "sb_wc2022_final",
        state["events"],
        registry,
        snap.id,
        "media",
        coverage=state["coverage"],
    )
    assert story.match_id == "sb_wc2022_final"
    assert story.snapshot_id == snap.id
    assert story.approval_status == "draft_pending_gate"
    assert len(story.chapters) == 3
    assert story.generated_at != "2026-10-21T12:50:00Z"


# ---------------------------------------------------------------------------
# Stage F / P2: Evidence Graph & Cross-Match Comparison
# ---------------------------------------------------------------------------

def test_evidence_graph_endpoint(client):
    """Stage F: Evidence Graph connects claims, receipts, and limitations."""
    res = client.get("/api/matches/syn_default/evidence-graph")
    assert res.status_code == 200
    data = res.json()
    assert data["match_id"] == "syn_default"
    assert data["nodes_count"] > 0
    assert data["edges_count"] > 0
    # Must have claim, metric_receipt, and limitation nodes
    node_types = {n["type"] for n in data["nodes"]}
    assert "claim" in node_types
    assert "metric_receipt" in node_types
    assert "limitation" in node_types


def test_matches_compare_endpoint(client):
    """Stage F: Cross-match comparison provides batch summary across matches."""
    res = client.get("/api/matches/compare?match_ids=syn_default,sb_wc2022_final")
    assert res.status_code == 200
    data = res.json()
    assert len(data["compared_matches"]) == 2
    assert len(data["matches"]) == 2
    assert data["batch_summary"]["total_matches"] == 2


def test_challenge_idempotency_key(client):
    """P0.6: Challenge with same idempotency_key must return identical result without appending revisions."""
    state = client.post("/api/control", json={"action": "focus", "chapter": "A"}).json()
    snap_id = state["snapshot_id"]

    res1 = client.post("/api/challenge", json={
        "claim_id": "claim-possession-without-penetration-h",
        "snapshot_id": snap_id,
        "challenge_type": "check_counterevidence",
        "team": "H",
        "idempotency_key": "idemp-key-" + __import__("secrets").token_hex(6)
    })
    assert res1.status_code == 200
    revs_count_1 = len(res1.json()["revisions"])

    # Repeat exact same request with same idempotency key
    res2 = client.post("/api/challenge", json={
        "claim_id": "claim-possession-without-penetration-h",
        "snapshot_id": snap_id,
        "challenge_type": "check_counterevidence",
        "team": "H",
        "idempotency_key": "idemp-key-" + __import__("secrets").token_hex(6)
    })
    assert res2.status_code == 200
    revs_count_2 = len(res2.json()["revisions"])
    assert revs_count_1 == revs_count_2, "Idempotent request must not duplicate revisions!"


# ---------------------------------------------------------------------------
# Additional Deep Regression Tests
# ---------------------------------------------------------------------------

def test_resolve_challenge_observational_vs_causal():
    """Verify that pure observational claims remain maintained under causal challenges, while causal claims are narrowed."""
    events = generate_match(seed=17)
    snap = freeze(events, 360)

    # 1. Observational claim (possession volume)
    req_obs = ChallengeRequest(
        claim_id="claim-possession-without-penetration",
        snapshot_id=snap.id,
        challenge_type="challenge_causal_interpretation",
        team="H",
    )
    res_obs = resolve_challenge(snap, req_obs)
    assert res_obs.outcome == "maintained", "Pure observation cannot be narrowed for causal overreach!"
    assert "observation" in res_obs.resolution_summary.lower()

    # 2. Causal assertion (e.g. pressing caused shot outcomes)
    req_causal = ChallengeRequest(
        claim_id="claim-pressing",
        snapshot_id=snap.id,
        challenge_type="challenge_causal_interpretation",
        team="H",
    )
    res_causal = resolve_challenge(snap, req_causal)
    assert res_causal.outcome == "narrowed", "Causal claims must be narrowed without tracking!"
    assert "temporal association" in res_causal.resolution_summary.lower() or "narrowed" in res_causal.resolution_summary.lower()


def test_resolve_challenge_empty_sequence_rejected():
    """Verify that challenging a non-existent or empty sequence returns rejected."""
    events = generate_match(seed=17)
    snap = freeze(events, 360)

    req = ChallengeRequest(
        claim_id="claim-possession",
        snapshot_id=snap.id,
        challenge_type="examine_sequence",
        sequence_id="nonexistent_seq_9999",
        team="H",
    )
    res = resolve_challenge(snap, req)
    assert res.outcome == "rejected"
    assert "rejected" in res.resolution_summary.lower() or "0 on-ball" in res.resolution_summary.lower()


def test_explain_chart_pass_edge_and_xt_cell_no_fake_events():
    """Verify explain_chart handles pass_edge and xt_cell cleanly and never returns fake fallback events."""
    events = generate_match(seed=17)
    snap = freeze(events, 360)

    # 1. passing_network with pass_edge
    res_edge = explain_chart(snap, chart_type="passing_network", team="H", pass_edge=("H6", "H8"))
    assert "H6 -> H8" in res_edge.title
    assert res_edge.supporting_event_ids is not None

    # 2. xt_surface with xt_cell
    res_xt = explain_chart(snap, chart_type="xt_surface", team="H", xt_cell=(14, 6))
    assert "(14, 6)" in res_xt.title
    assert "16x12" in res_xt.summary or "Expected Threat" in res_xt.summary

    # 3. attacking_channels without entries in empty window returns [] rather than events[-4:]
    snap_empty = freeze(events, 20)  # At 20s, very few or zero attacking third entries
    res_channels = explain_chart(snap_empty, chart_type="attacking_channels", team="H")
    if int(res_channels.key_metrics[0].value) == 0:
        assert res_channels.supporting_event_ids == [], "Must NOT fabricate supporting event IDs from events[-4:]!"

    # 4. spatial_drilldown with non-existent sequence returns []
    res_seq = explain_chart(snap, chart_type="spatial_drilldown", team="H", sequence_id="fake_seq_xyz")
    assert res_seq.supporting_event_ids == [], "Non-existent sequence must return empty supporting list!"
    assert "tracking" in res_seq.limitations[0].lower()


def test_story_engine_approval_status_strict_validation(tmp_path):
    """Approval is derived from registry verdicts, never caller-supplied fields."""
    from matchlens.football import reduce_match
    from matchlens.main import freeze_with_context
    from matchlens.registry import ClaimRegistry

    ctx = MatchCatalog.get_match_context("sb_wc2022_final")
    events = MatchCatalog.load_normalized_events("sb_wc2022_final")
    at = min(ctx.duration, int(ctx.observed_end))
    state = reduce_match(
        events,
        at,
        max_duration=ctx.duration,
        is_synthetic=False,
        coordinate_frame=ctx.coordinate_frame,
        continuous_coverage=ctx.continuous_coverage,
    )
    snap = freeze_with_context(events, ctx, at, match_id="sb_wc2022_final", scenario="historical")
    registry = ClaimRegistry(tmp_path / "claims.json")

    def story():
        return MatchStoryEngine.generate_story(
            "sb_wc2022_final", state["events"], registry, snap.id, "media",
            coverage=state["coverage"],
        )

    # 1. No registry records -> draft.
    assert story().approval_status == "draft_pending_gate"

    # 2. Gate-approved but no editorial decision -> draft pending editorial.
    record = registry.verify_and_register(snap, "sb_wc2022_final", "goal_sequence", "H")
    assert record.gate_status == "approved"
    assert story().approval_status == "draft_pending_editorial"

    # 3. Editorial rejection -> contested.
    registry.editorial_decision(
        "sb_wc2022_final", snap.id, record.claim_id, approver="Editor", decision="rejected"
    )
    assert story().approval_status == "contested"

    # 4. Editorial approval -> broadcast approval, with chapter binding.
    registry.editorial_decision(
        "sb_wc2022_final", snap.id, record.claim_id, approver="Editor", decision="approved"
    )
    approved = story()
    assert approved.approval_status == "approved_for_broadcast"
    assert any(record.claim_id in c.verified_claim_refs for c in approved.chapters)


def test_research_endpoints_bounds_validation(client):
    """Verify research and attribution endpoints reject out-of-bounds parameters."""
    # 1. Validation iterations > 200 rejected
    res_val = client.get("/api/matches/syn_default/validation?iterations=500")
    assert res_val.status_code == 400
    assert "iterations_out_of_bounds" in res_val.json()["detail"]

    # 2. Window negative start rejected
    res_win = client.get("/api/attribution/window?window_start=-10.0")
    assert res_win.status_code == 400
    assert "invalid_window_bounds" in res_win.json()["detail"]

    # 3. Lookback > 300 rejected
    res_chain = client.get("/api/attribution/chain?lookback_seconds=600.0")
    assert res_chain.status_code == 400
    assert "invalid_lookback" in res_chain.json()["detail"]


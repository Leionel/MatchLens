"""Track D: registry-bound broadcast stories (no caller-supplied approval)."""
import pytest

from matchlens.football import freeze, generate_match, reduce_match
from matchlens.registry import ClaimRegistry
from matchlens.stories import (
    MatchStory,
    MatchStoryEngine,
    PerspectiveManager,
    StoryExportEngine,
)


@pytest.fixture
def snap():
    return freeze(generate_match(), 720)


@pytest.fixture
def state_events(snap):
    return reduce_match(generate_match(), 720)["events"]


@pytest.fixture
def registry(tmp_path):
    return ClaimRegistry(tmp_path / "claims.json")


def _story(registry, snap, state_events, perspective="media"):
    return MatchStoryEngine.generate_story(
        "syn_default",
        state_events,
        registry,
        snap.id,
        perspective,
        coverage=snap.data["coverage"],
    )


def test_gate_verdict_is_required_and_editorial_approval_is_separate(registry, snap, state_events):
    record = registry.verify_and_register(snap, "syn_default", "goal_sequence", "H")
    assert record.gate_status == "approved"

    story = _story(registry, snap, state_events)
    assert isinstance(story, MatchStory)
    assert story.approval_status == "draft_pending_editorial"
    assert story.approved_claims_count == 0
    assert story.gate_verified_claims_count == 1
    assert "editorial approval" in story.summary_verdict
    assert [c.minute_span for c in story.chapters] == ["0'–4'", "4'–8'", "8'–12'"]

    registry.editorial_decision(
        "syn_default", snap.id, record.claim_id, approver="Editor A", decision="approved"
    )
    approved = _story(registry, snap, state_events)
    assert approved.approval_status == "approved_for_broadcast"
    assert approved.approved_claims_count == 1


def test_no_claims_gives_descriptive_draft_without_star_or_tactical_fabrication(registry, snap, state_events):
    story = _story(registry, snap, state_events, "coach")
    assert story.approval_status == "draft_pending_gate"
    assert story.approved_claims_count == 0
    joined = " ".join(c.narrative for c in story.chapters)
    assert "off-ball" in joined.lower()
    assert "star" not in joined.lower()
    assert "KeyShift" not in story.chapters[0].tactical_tags
    assert all(tag.startswith(("recorded", "progression", "recovery", "broadcast", "shots", "goals")) for c in story.chapters for tag in c.tactical_tags)


def test_cross_match_claims_do_not_leak_into_story(registry, snap, state_events):
    registry.verify_and_register(snap, "another_match", "goal_sequence", "H")
    story = _story(registry, snap, state_events)
    assert story.gate_verified_claims_count == 0
    assert story.approval_status == "draft_pending_gate"
    assert all(not c.verified_claim_refs for c in story.chapters)


def test_rejected_gate_verdict_cannot_be_editorially_approved(registry, snap):
    record = registry.verify_and_register(snap, "syn_default", "recoveries_caused_shots", "H")
    assert record.gate_status == "rejected"
    with pytest.raises(ValueError, match="gate_not_approved"):
        registry.editorial_decision(
            "syn_default", snap.id, record.claim_id, approver="Editor A", decision="approved"
        )


def test_perspective_manager_profiles():
    coach_view = PerspectiveManager.get_perspective_view("coach", "match-01")
    assert coach_view.perspective == "coach"
    assert any("recovery" in m["label"].lower() for m in coach_view.primary_metrics)
    assert coach_view.highlighted_sequences == []

    fan_view = PerspectiveManager.get_perspective_view("fan", "match-01")
    assert fan_view.perspective == "fan"
    assert any("goals" in m["label"].lower() for m in fan_view.primary_metrics)

    media_view = PerspectiveManager.get_perspective_view("media", "match-01")
    assert media_view.perspective == "media"
    assert any("OAAI" in m["label"] for m in media_view.primary_metrics)


def test_story_export_formats_do_not_claim_unearned_verification(registry, snap, state_events):
    story = _story(registry, snap, state_events, "fan")

    pkg_json = StoryExportEngine.export_story_package(story, "json")
    assert pkg_json.export_format == "json"
    assert pkg_json.filename.endswith(".json")
    assert "syn_default" in pkg_json.payload
    assert pkg_json.signature.startswith("sha256-evidence-")

    pkg_md = StoryExportEngine.export_story_package(story, "markdown")
    assert "# Match summary" in pkg_md.payload
    assert "FAN" in pkg_md.payload

    pkg_svg = StoryExportEngine.export_story_package(story, "svg")
    assert "<svg" in pkg_svg.payload
    assert "GATE 2.0 VERIFIED" not in pkg_svg.payload
    assert "NOT APPROVED" in pkg_svg.payload

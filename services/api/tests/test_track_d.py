"""
Track D Tests: Broadcast, Multi-Perspective, and Match Story Engine (BL-06).
"""
import pytest
from matchlens.football import generate_match
from matchlens.stories import (
    MatchStoryEngine,
    PerspectiveManager,
    StoryExportEngine,
    MatchStory,
)


@pytest.fixture
def sample_match_events():
    events = generate_match(seed=42)
    # Convert tuples or dicts to event dicts
    event_dicts = []
    for idx, ev in enumerate(events):
        event_dicts.append({
            "id": f"ev-{idx}",
            "event_id": f"ev-{idx}",
            "timestamp_seconds": float(getattr(ev, "t", idx * 10)),
            "second": float(getattr(ev, "t", idx * 10)),
            "team": getattr(ev, "team", "H"),
            "kind": getattr(ev, "kind", "pass"),
            "action": getattr(ev, "kind", "pass"),
            "start": getattr(ev, "start", [50, 34]),
            "end": getattr(ev, "end", [60, 34]),
            "outcome": getattr(ev, "outcome", "complete"),
        })
    return event_dicts


def test_story_engine_generation_with_verified_claims(sample_match_events):
    claims = [
        {"claim_id": "claim-001", "assertion": "High territorial dominance", "verdict": "verified"},
        {"claim_id": "claim-002", "assertion": "Rapid 6s recovery rate", "verdict": "verified"},
    ]
    story = MatchStoryEngine.generate_story(
        match_id="test-match-101",
        events=sample_match_events,
        verified_claims=claims,
        perspective="media",
    )
    assert isinstance(story, MatchStory)
    assert story.match_id == "test-match-101"
    assert story.perspective == "media"
    assert story.approval_status == "approved_for_broadcast"
    assert story.approved_claims_count == 2
    assert len(story.chapters) == 3
    # 12-minute synthetic match correctly segments into 4-minute chapters
    assert story.chapters[0].minute_span == "0'–4'"
    assert story.chapters[1].minute_span == "4'–8'"
    assert story.chapters[2].minute_span == "8'–12'"
    assert any("KeyShift" in c.tactical_tags or "TurningPoint" in c.tactical_tags for c in story.chapters)


def test_story_engine_90min_match_minute_span():
    # 90-minute match (5400s) segments into 30-minute chapters
    events_90m = [
        {"event_id": "ev-0", "timestamp_seconds": 0.0, "team": "H", "action": "pass"},
        {"event_id": "ev-1", "timestamp_seconds": 2700.0, "team": "N", "action": "shot"},
        {"event_id": "ev-2", "timestamp_seconds": 5400.0, "team": "H", "action": "goal"},
    ]
    story = MatchStoryEngine.generate_story(
        match_id="test-match-90m",
        events=events_90m,
        perspective="media",
    )
    assert story.chapters[0].minute_span == "0'–30'"
    assert story.chapters[1].minute_span == "30'–60'"
    assert story.chapters[2].minute_span == "60'–90'+"


def test_story_engine_draft_when_no_claims(sample_match_events):
    story = MatchStoryEngine.generate_story(
        match_id="test-match-unverified",
        events=sample_match_events,
        verified_claims=[],
        perspective="coach",
    )
    assert story.approval_status == "draft_pending_gate"
    assert story.approved_claims_count == 0
    assert story.perspective == "coach"
    assert any("CorridorProgression" in c.tactical_tags for c in story.chapters)


def test_perspective_manager_profiles():
    coach_view = PerspectiveManager.get_perspective_view("coach", "match-01")
    assert coach_view.perspective == "coach"
    assert any("6s Recovery" in m["label"] for m in coach_view.primary_metrics)

    fan_view = PerspectiveManager.get_perspective_view("fan", "match-01")
    assert fan_view.perspective == "fan"
    assert any("Expected Goals" in m["label"] for m in fan_view.primary_metrics)

    media_view = PerspectiveManager.get_perspective_view("media", "match-01")
    assert media_view.perspective == "media"
    assert any("OAAI Momentum Pulse" in m["label"] for m in media_view.primary_metrics)


def test_story_export_formats(sample_match_events):
    story = MatchStoryEngine.generate_story(
        match_id="match-export-test",
        events=sample_match_events,
        verified_claims=[{"claim_id": "c-1"}],
        perspective="fan",
    )

    # JSON export
    pkg_json = StoryExportEngine.export_story_package(story, "json")
    assert pkg_json.export_format == "json"
    assert pkg_json.filename.endswith(".json")
    assert "match-export-test" in pkg_json.payload
    assert pkg_json.signature.startswith("sha256-verified-matchlens")

    # Markdown export
    pkg_md = StoryExportEngine.export_story_package(story, "markdown")
    assert pkg_md.export_format == "markdown"
    assert pkg_md.filename.endswith(".md")
    assert "# Tactical Chronicle" in pkg_md.payload
    assert "FAN" in pkg_md.payload

    # SVG export
    pkg_svg = StoryExportEngine.export_story_package(story, "svg")
    assert pkg_svg.export_format == "svg"
    assert pkg_svg.filename.endswith(".svg")
    assert "<svg" in pkg_svg.payload
    assert "GATE 2.0 VERIFIED" in pkg_svg.payload

"""The chart payload of a full match must stay renderable and lossless where it matters.

A provider match samples the activity index every two seconds for the whole
match, which is thousands of samples. The cockpit sends that timeline with
every state push, so the chart copy is size-bounded - but the peaks it hides
must never disappear and the registry comparison must not change.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matchlens.oaai import (  # noqa: E402
    chart_oaai_payload,
    downsample_oaai_timeline,
    trim_change_point_contributors,
)


def _timeline(count: int = 3000):
    return [
        {
            "t": float(i * 2),
            "home_intensity": 0.1,
            "away_intensity": 0.2,
            "oaai_raw": 0.0,
            "oaai_value": float(i % 97) / 97.0,
            "home_smoothed": 0.1,
            "away_smoothed": 0.2,
            "smoothing_mode": "causal",
            "causal_event_count": i,
        }
        for i in range(count)
    ]


def test_a_timeline_within_the_budget_is_returned_unchanged():
    timeline = _timeline(120)
    result = downsample_oaai_timeline(timeline, max_points=600)
    assert result == timeline


def test_downsampling_bounds_the_chart_payload():
    timeline = _timeline(3000)
    result = downsample_oaai_timeline(timeline, max_points=600)
    assert len(result) <= 602
    assert len(result) < len(timeline)


def test_downsampling_keeps_the_extreme_samples():
    timeline = _timeline(3000)
    result = downsample_oaai_timeline(timeline, max_points=600)
    values = [p["oaai_value"] for p in result]
    assert max(values) == max(p["oaai_value"] for p in timeline)
    assert min(values) == min(p["oaai_value"] for p in timeline)


def test_downsampling_keeps_the_first_and_last_sample():
    timeline = _timeline(3000)
    result = downsample_oaai_timeline(timeline, max_points=600)
    assert result[0]["t"] == timeline[0]["t"]
    assert result[-1]["t"] == timeline[-1]["t"]


def test_downsampling_keeps_the_timeline_ordered_in_time():
    timeline = _timeline(3000)
    result = downsample_oaai_timeline(timeline, max_points=600)
    stamps = [p["t"] for p in result]
    assert stamps == sorted(stamps)


def test_a_spike_is_never_averaged_away():
    timeline = _timeline(3000)
    timeline[1234]["oaai_value"] = 99.0
    result = downsample_oaai_timeline(timeline, max_points=600)
    assert any(p["oaai_value"] == 99.0 for p in result)


def test_contributors_are_trimmed_without_dropping_change_points():
    change_points = [
        {
            "change_point_id": f"CP-{index:02d}",
            "at": float(index * 30),
            "oaai_amplitude": 0.5,
            "leading_team": "H",
            "top_contributors": [
                {"event_id": f"e{index}-{c}", "contribution": 0.1} for c in range(4)
            ],
        }
        for index in range(20)
    ]
    trimmed = trim_change_point_contributors(change_points, max_contributors=2)
    assert len(trimmed) == len(change_points)
    assert all(len(cp["top_contributors"]) == 2 for cp in trimmed)
    assert trimmed[0]["top_contributors_truncated"] == 2
    assert trimmed[0]["change_point_id"] == "CP-00"


def test_the_chart_payload_keeps_the_registry_comparison():
    oaai = {
        "model_version": "oaai-1.0.0",
        "smoothing_mode": "causal",
        "timeline": _timeline(3000),
        "change_points": [
            {
                "change_point_id": "CP-01",
                "at": 12.0,
                "oaai_amplitude": -0.48,
                "leading_team": "N",
                "top_contributors": [{"event_id": f"e{c}"} for c in range(4)],
            }
        ],
        "registry_comparison": {"registry_comparable": True, "observations": {}},
    }
    payload = chart_oaai_payload(oaai, max_points=600, max_contributors=2)
    assert payload["registry_comparison"] == oaai["registry_comparison"]
    assert payload["chart_sampling"]["timeline_points_full"] == 3000
    assert payload["chart_sampling"]["timeline_points_chart"] == len(payload["timeline"])
    assert len(payload["timeline"]) <= 602

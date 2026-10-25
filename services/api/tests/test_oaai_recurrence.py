"""The OAAI recurrence must equal the per-sample causal fold exactly.

The fast path changed from rescanning every event at every sample to folding
events once in effective play time. This test keeps the old definition as an
independent oracle and compares every sample, including dead-time freezing.
"""
from __future__ import annotations

import math

from matchlens.football import generate_match, reduce_match
from matchlens.oaai import (
    OAAIConfig,
    _DeadTimeIndex,
    _infer_home_team,
    _normalize_event_view,
    aggregate_oaai_timeline,
    compute_event_contribution,
)


def _slow_reference(events, *, t_end: float, dead_intervals, config: OAAIConfig) -> list[dict]:
    views = [_normalize_event_view(event) for event in events]
    home = _infer_home_team(views)
    normalized = sorted(
        (_normalize_event_view(event, home_team=home) for event in events),
        key=lambda event: (event["t"], event["id"]),
    )
    decay = math.log(2) / config.half_life_seconds
    contributions = []
    for event in normalized:
        signed, magnitude, _ = compute_event_contribution(
            event, config, xt_model=None, home_team=home
        )
        contributions.append({
            "t": event["t"],
            "signed_c": signed,
            "mag": magnitude,
            "is_home": event["team"] == "H" or event.get("team_id") == home,
        })
    dead = _DeadTimeIndex(dead_intervals)
    pointer = 0
    out: list[dict] = []
    for index in range(int(math.floor(t_end / config.sample_step_seconds)) + 1):
        t = round(index * config.sample_step_seconds, 2)
        while pointer < len(contributions) and contributions[pointer]["t"] <= t:
            pointer += 1
        home_intensity = away_intensity = net = 0.0
        for item in contributions[:pointer]:
            dt = t - item["t"] - dead.seconds_between(item["t"], t)
            weight = math.exp(-decay * max(0.0, dt))
            net += item["signed_c"] * weight
            if item["is_home"]:
                if item["signed_c"] > 0:
                    home_intensity += item["mag"] * weight
                else:
                    home_intensity = max(0.0, home_intensity - item["mag"] * weight)
            else:
                if item["signed_c"] < 0:
                    away_intensity += item["mag"] * weight
                else:
                    away_intensity = max(0.0, away_intensity - item["mag"] * weight)
        out.append({
            "t": t,
            "home_intensity": round(home_intensity, 4),
            "away_intensity": round(away_intensity, 4),
            "oaai_raw": round(net, 4),
            "causal_event_count": pointer,
        })
    return out


def test_recurrence_matches_causal_fold_with_dead_time():
    events = generate_match()
    state = reduce_match(events, 720, is_synthetic=True)
    sample = state["events"][:250]
    dead = state["dead_intervals"][:30]
    config = OAAIConfig()

    fast = aggregate_oaai_timeline(
        sample,
        config=config,
        t_end=480,
        dead_intervals=dead,
        xt_model=None,
    )
    slow = _slow_reference(sample, t_end=480, dead_intervals=dead, config=config)

    assert len(fast) == len(slow) > 0
    for fast_point, slow_point in zip(fast, slow):
        assert fast_point["t"] == slow_point["t"]
        assert fast_point["causal_event_count"] == slow_point["causal_event_count"]
        assert abs(fast_point["home_intensity"] - slow_point["home_intensity"]) <= 1e-9
        assert abs(fast_point["away_intensity"] - slow_point["away_intensity"]) <= 1e-9
        assert abs(fast_point["oaai_raw"] - slow_point["oaai_raw"]) <= 1e-9

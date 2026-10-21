"""StatsBomb Open Data Ingestion & Normalization Adapter (BL-01).

Implements requirements from FOOTBALL_INTELLIGENCE_PLATFORMS_2026.md:
- Affine coordinate transformation from 120x80 yards to 105x68 meters.
- Missing field handling, clock time parsing, and possession change semantics.
- Attribution and licensing records conforming to StatsBomb Open Data terms.
- Emits standardized NormalizedEvent objects conforming to schema.py.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from ..schema import ActionType, DataCoverageLevel, NormalizedEvent, RawSourceRecord

STATSBOMB_LICENSE_REF = "StatsBomb Open Data (https://github.com/statsbomb/open-data) - CC BY-NC-SA 4.0"
STATSBOMB_ATTRIBUTION_TEXT = "Match event data provided by StatsBomb Open Data (https://statsbomb.com/)"
STATSBOMB_LOGO_REQUIREMENT = "Visualizations derived from this data must display the StatsBomb logo per the Open Data User Agreement."


class StatsBombAdapter:
    """Ingests and converts StatsBomb Open Data JSON events into NormalizedEvent stream."""

    SB_PITCH_LENGTH_YARDS = 120.0
    SB_PITCH_WIDTH_YARDS = 80.0
    TARGET_PITCH_LENGTH_METERS = 105.0
    TARGET_PITCH_WIDTH_METERS = 68.0

    SCALE_X = TARGET_PITCH_LENGTH_METERS / SB_PITCH_LENGTH_YARDS  # 105 / 120 = 0.875
    SCALE_Y = TARGET_PITCH_WIDTH_METERS / SB_PITCH_WIDTH_YARDS    # 68 / 80 = 0.85

    def __init__(self, match_id: str = "sb_match"):
        self.match_id = match_id

    @classmethod
    def transform_coordinates(
        cls, x: Optional[float], y: Optional[float]
    ) -> tuple[Optional[float], Optional[float]]:
        """Affine transform from StatsBomb 120x80 yd to standard 105x68 m."""
        if x is None or y is None:
            return None, None
        # Clamp to bounds and scale
        clamped_x = max(0.0, min(cls.SB_PITCH_LENGTH_YARDS, float(x)))
        clamped_y = max(0.0, min(cls.SB_PITCH_WIDTH_YARDS, float(y)))
        return round(clamped_x * cls.SCALE_X, 2), round(clamped_y * cls.SCALE_Y, 2)

    @classmethod
    def parse_clock_seconds(cls, period: int, minute: int, second: int, timestamp: Optional[str] = None) -> float:
        """Compute match-elapsed clock in seconds.
        
        Period 1: regular 0-45m (+ injury time)
        Period 2: regular 45-90m (+ injury time)
        Period 3: Extra time 1st half (90-105m)
        Period 4: Extra time 2nd half (105-120m)
        Period 5: Penalty shootout
        """
        period_secs = float(minute * 60 + second)
        if timestamp:
            try:
                parts = timestamp.split(":")
                if len(parts) >= 3:
                    h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
                    period_secs = h * 3600 + m * 60 + s
            except Exception:
                pass

        if period == 1:
            return round(period_secs, 2)
        elif period == 2:
            return round(45.0 * 60.0 + period_secs, 2)
        elif period == 3:
            return round(90.0 * 60.0 + period_secs, 2)
        elif period == 4:
            return round(105.0 * 60.0 + period_secs, 2)
        else:
            return round(120.0 * 60.0 + period_secs, 2)

    @classmethod
    def map_action_type(cls, sb_type_name: str) -> ActionType:
        """Map StatsBomb event type string to standard ActionType enum."""
        mapping = {
            "Pass": ActionType.PASS,
            "Shot": ActionType.SHOT,
            "Carry": ActionType.CARRY,
            "Ball Recovery": ActionType.RECOVERY,
            "Interception": ActionType.INTERCEPTION,
            "Clearance": ActionType.CLEARANCE,
            "Dispossessed": ActionType.DISPOSSESSED,
            "Duel": ActionType.DUEL,
            "Foul Committed": ActionType.FOUL,
            "Foul Won": ActionType.FOUL,
            "Goal Keeper": ActionType.GOALKEEPER,
            "Starting XI": ActionType.RESTART,
            "Half Start": ActionType.RESTART,
            "Half End": ActionType.RESTART,
        }
        return mapping.get(sb_type_name, ActionType.OTHER)

    @classmethod
    def parse_outcome(cls, raw: dict[str, Any], action_type: ActionType) -> str:
        """Extract outcome description from nested StatsBomb dictionaries."""
        if action_type == ActionType.PASS:
            pass_info = raw.get("pass", {})
            outcome = pass_info.get("outcome")
            return outcome.get("name").lower() if outcome else "complete"
        elif action_type == ActionType.SHOT:
            shot_info = raw.get("shot", {})
            outcome = shot_info.get("outcome", {})
            name = outcome.get("name", "Shot")
            return "goal" if name.lower() == "goal" else name.lower()
        elif action_type == ActionType.DUEL:
            duel_info = raw.get("duel", {})
            outcome = duel_info.get("outcome")
            return outcome.get("name").lower() if outcome else "success"
        elif action_type == ActionType.INTERCEPTION:
            int_info = raw.get("interception", {})
            outcome = int_info.get("outcome")
            return outcome.get("name").lower() if outcome else "won"
        return "complete"

    def normalize_event(
        self,
        raw: dict[str, Any],
        prev_team_id: Optional[str] = None,
    ) -> NormalizedEvent:
        """Converts a single raw StatsBomb JSON event into NormalizedEvent."""
        raw_id = str(raw.get("id", "unknown"))
        idx = int(raw.get("index", 1))
        period = int(raw.get("period", 1))
        minute = int(raw.get("minute", 0))
        second = int(raw.get("second", 0))
        timestamp = raw.get("timestamp")

        clock_sec = self.parse_clock_seconds(period, minute, second, timestamp)

        team = raw.get("team", {})
        team_id = str(team.get("name") or team.get("id") or "Team")

        player = raw.get("player") or {}
        player_id = str(player.get("id")) if player.get("id") is not None else None
        player_name = str(player.get("name")) if player.get("name") is not None else None

        type_dict = raw.get("type", {})
        type_name = type_dict.get("name", "Other")
        action_type = self.map_action_type(type_name)
        outcome = self.parse_outcome(raw, action_type)

        # Coordinate extraction
        loc = raw.get("location")
        start_x, start_y = (loc[0], loc[1]) if loc and len(loc) >= 2 else (None, None)
        x_m, y_m = self.transform_coordinates(start_x, start_y)

        # End coordinates (pass.end_location, shot.end_location, carry.end_location)
        end_loc = None
        if action_type == ActionType.PASS:
            end_loc = raw.get("pass", {}).get("end_location")
        elif action_type == ActionType.SHOT:
            end_loc = raw.get("shot", {}).get("end_location")
        elif action_type == ActionType.CARRY:
            end_loc = raw.get("carry", {}).get("end_location")

        end_x, end_y = (end_loc[0], end_loc[1]) if end_loc and len(end_loc) >= 2 else (None, None)
        end_x_m, end_y_m = self.transform_coordinates(end_x, end_y)

        # Possession change flag
        possession_id = str(raw.get("possession", "")) or None
        possession_changed = (prev_team_id is not None and prev_team_id != team_id)

        source = RawSourceRecord(
            provider="statsbomb_open_data",
            provider_event_id=raw_id,
            schema_version="1.1",
            license_ref=STATSBOMB_LICENSE_REF,
            payload_ref=f"match_{self.match_id}_event_{idx}",
        )

        return NormalizedEvent(
            event_id=f"sb_{self.match_id}_{idx:05d}",
            match_id=self.match_id,
            source=source,
            period=period,
            clock_seconds=clock_sec,
            clock_basis="match_elapsed",
            team_id=team_id,
            attack_direction="left_to_right",  # StatsBomb standardizes attack L-to-R for all events
            possession_id=possession_id,
            possession_changed=possession_changed,
            player_id=player_id,
            player_name=player_name,
            action_type=action_type,
            outcome=outcome,
            x=x_m,
            y=y_m,
            end_x=end_x_m,
            end_y=end_y_m,
        )

    def load_events(self, raw_events: list[dict[str, Any]]) -> list[NormalizedEvent]:
        """Convert a full list of raw StatsBomb events into NormalizedEvent stream."""
        normalized: list[NormalizedEvent] = []
        prev_team_id: Optional[str] = None

        for raw in raw_events:
            ev = self.normalize_event(raw, prev_team_id=prev_team_id)
            normalized.append(ev)
            prev_team_id = ev.team_id

        return normalized

    @classmethod
    def get_attribution(cls) -> dict[str, str]:
        """Return legal attribution and logo requirements for frontend and exports."""
        return {
            "license": STATSBOMB_LICENSE_REF,
            "attribution": STATSBOMB_ATTRIBUTION_TEXT,
            "logo_requirement": STATSBOMB_LOGO_REQUIREMENT,
        }

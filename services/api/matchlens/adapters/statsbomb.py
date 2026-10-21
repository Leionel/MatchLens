"""StatsBomb Open Data Ingestion & Normalization Adapter (BL-01).

Implements requirements from FOOTBALL_INTELLIGENCE_PLATFORMS_2026.md:
- Affine coordinate transformation from 120x80 yards to 105x68 meters.
- Missing field handling, clock time parsing, and possession change semantics.
- Attribution and licensing records conforming to StatsBomb Open Data terms.
- Emits standardized NormalizedEvent objects conforming to schema.py.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
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
        self.team_player_counts: dict[str, int] = {}
        self.red_cards: list[dict[str, Any]] = []
        self.yellow_cards: list[dict[str, Any]] = []
        self.expulsions: list[dict[str, Any]] = []
        self.own_goals: list[dict[str, Any]] = []
        self.shootout_kicks: list[dict[str, Any]] = []

    @classmethod
    def transform_coordinates(
        cls, x: Any, y: Any
    ) -> tuple[Optional[float], Optional[float]]:
        """Affine transform from StatsBomb 120x80 yd to standard 105x68 m."""
        if x is None or y is None:
            return None, None
        try:
            fx = float(x)
            fy = float(y)
            if math.isnan(fx) or math.isnan(fy) or math.isinf(fx) or math.isinf(fy):
                return None, None
        except (ValueError, TypeError):
            return None, None

        # Clamp to bounds and scale
        clamped_x = max(0.0, min(cls.SB_PITCH_LENGTH_YARDS, fx))
        clamped_y = max(0.0, min(cls.SB_PITCH_WIDTH_YARDS, fy))
        return round(clamped_x * cls.SCALE_X, 2), round(clamped_y * cls.SCALE_Y, 2)

    @classmethod
    def extract_location(cls, loc: Any) -> tuple[Optional[float], Optional[float]]:
        """Safely extract and transform 2D or 3D location coordinates."""
        if not loc or not isinstance(loc, (list, tuple)) or len(loc) < 2:
            return None, None
        return cls.transform_coordinates(loc[0], loc[1])

    @classmethod
    def parse_clock_seconds(
        cls, period: int, minute: int, second: int, timestamp: Optional[str] = None
    ) -> float:
        """Compute match-elapsed clock in seconds.
        
        Period 1: regular 0-45m (+ injury time)
        Period 2: regular 45-90m (+ injury time)
        Period 3: Extra time 1st half (90-105m)
        Period 4: Extra time 2nd half (105-120m)
        Period 5+: Standard & non-standard penalty shootouts, sudden death
        """
        period_secs = float(minute * 60 + second)
        has_parsed_ts = False
        if timestamp:
            try:
                parts = str(timestamp).split(":")
                if len(parts) >= 3:
                    h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
                    period_secs = h * 3600 + m * 60 + s
                    has_parsed_ts = True
            except Exception:
                pass

        if period == 1:
            return round(period_secs, 2)
        elif period == 2:
            if has_parsed_ts or minute < 45:
                return round(45.0 * 60.0 + period_secs, 2)
            return round(period_secs, 2)
        elif period == 3:
            if has_parsed_ts or minute < 90:
                return round(90.0 * 60.0 + period_secs, 2)
            return round(period_secs, 2)
        elif period == 4:
            if has_parsed_ts or minute < 105:
                return round(105.0 * 60.0 + period_secs, 2)
            return round(period_secs, 2)
        else:
            # Period 5+: Shootout kicks
            if has_parsed_ts or minute < 120:
                return round(120.0 * 60.0 + period_secs, 2)
            return round(period_secs, 2)

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
            "Own Goal Against": ActionType.OWN_GOAL,
            "Own Goal For": ActionType.OWN_GOAL,
            "Bad Behaviour": ActionType.BAD_BEHAVIOUR,
            "Substitution": ActionType.OTHER,
            "Player Off": ActionType.OTHER,
            "Player On": ActionType.OTHER,
            "Tactical Shift": ActionType.OTHER,
            "Injury Stoppage": ActionType.OTHER,
            "Referee Ball-Drop": ActionType.OTHER,
            "Card": ActionType.FOUL,
        }
        return mapping.get(sb_type_name, ActionType.OTHER)

    @classmethod
    def parse_card(cls, raw: dict[str, Any]) -> Optional[str]:
        """Detect and standardize red/yellow card sanctions."""
        # 1. foul_committed.card
        foul_info = raw.get("foul_committed")
        if isinstance(foul_info, dict) and foul_info.get("card"):
            card_obj = foul_info.get("card")
            card_name = (card_obj.get("name") if isinstance(card_obj, dict) else str(card_obj)).lower()
            if "second" in card_name:
                return "second_yellow"
            elif "red" in card_name:
                return "red_card"
            elif "yellow" in card_name:
                return "yellow_card"

        # 2. bad_behaviour.card
        bb_info = raw.get("bad_behaviour")
        if isinstance(bb_info, dict) and bb_info.get("card"):
            card_obj = bb_info.get("card")
            card_name = (card_obj.get("name") if isinstance(card_obj, dict) else str(card_obj)).lower()
            if "second" in card_name:
                return "second_yellow"
            elif "red" in card_name:
                return "red_card"
            elif "yellow" in card_name:
                return "yellow_card"

        # 3. top-level card
        if raw.get("card"):
            card_obj = raw.get("card")
            card_name = (card_obj.get("name") if isinstance(card_obj, dict) else str(card_obj)).lower()
            if "second" in card_name:
                return "second_yellow"
            elif "red" in card_name:
                return "red_card"
            elif "yellow" in card_name:
                return "yellow_card"

        return None

    @classmethod
    def parse_outcome(cls, raw: dict[str, Any], action_type: ActionType) -> str:
        """Extract outcome description from nested StatsBomb dictionaries."""
        type_dict = raw.get("type", {})
        type_name = type_dict.get("name", "") if isinstance(type_dict, dict) else str(type_dict)

        if type_name in ("Own Goal Against", "Own Goal For") or action_type == ActionType.OWN_GOAL:
            return "own_goal"

        if action_type == ActionType.PASS:
            pass_info = raw.get("pass", {})
            outcome = pass_info.get("outcome") if isinstance(pass_info, dict) else None
            return outcome.get("name").lower() if isinstance(outcome, dict) else "complete"
        elif action_type == ActionType.SHOT:
            shot_info = raw.get("shot", {})
            if isinstance(shot_info, dict):
                shot_type = shot_info.get("type", {})
                shot_type_name = shot_type.get("name", "") if isinstance(shot_type, dict) else ""
                if shot_type_name.lower() == "own goal":
                    return "own_goal"
                outcome = shot_info.get("outcome", {})
                name = outcome.get("name", "Shot") if isinstance(outcome, dict) else str(outcome)
                if name.lower() == "own goal":
                    return "own_goal"
                return "goal" if name.lower() == "goal" else name.lower()
            return "shot"
        elif action_type == ActionType.DUEL:
            duel_info = raw.get("duel", {})
            outcome = duel_info.get("outcome") if isinstance(duel_info, dict) else None
            return outcome.get("name").lower() if isinstance(outcome, dict) else "success"
        elif action_type == ActionType.INTERCEPTION:
            int_info = raw.get("interception", {})
            outcome = int_info.get("outcome") if isinstance(int_info, dict) else None
            return outcome.get("name").lower() if isinstance(outcome, dict) else "won"
        elif action_type == ActionType.BAD_BEHAVIOUR:
            card_info = raw.get("bad_behaviour", {}).get("card")
            if isinstance(card_info, dict):
                return card_info.get("name", "warning").lower()
            return "warning"
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
        if team_id not in self.team_player_counts:
            self.team_player_counts[team_id] = 11

        player = raw.get("player") or {}
        player_id = str(player.get("id")) if player.get("id") is not None else None
        player_name = str(player.get("name")) if player.get("name") is not None else None

        type_dict = raw.get("type", {})
        type_name = type_dict.get("name", "Other")
        action_type = self.map_action_type(type_name)
        outcome = self.parse_outcome(raw, action_type)

        # Coordinate extraction
        x_m, y_m = self.extract_location(raw.get("location"))

        # End coordinates (pass.end_location, shot.end_location, carry.end_location)
        end_loc = None
        if action_type == ActionType.PASS and isinstance(raw.get("pass"), dict):
            end_loc = raw.get("pass", {}).get("end_location")
        elif action_type == ActionType.SHOT and isinstance(raw.get("shot"), dict):
            end_loc = raw.get("shot", {}).get("end_location")
        elif action_type == ActionType.CARRY and isinstance(raw.get("carry"), dict):
            end_loc = raw.get("carry", {}).get("end_location")

        end_x_m, end_y_m = self.extract_location(end_loc)

        # Card & discipline tracking
        card = self.parse_card(raw)
        if card:
            card_record = {
                "event_id": f"sb_{self.match_id}_{idx:05d}",
                "clock_seconds": clock_sec,
                "team_id": team_id,
                "player_id": player_id,
                "player_name": player_name,
                "card": card,
            }
            if card == "yellow_card":
                self.yellow_cards.append(card_record)
            elif card in ("red_card", "second_yellow"):
                self.red_cards.append(card_record)
                self.expulsions.append(card_record)
                current_count = self.team_player_counts.get(team_id, 11)
                self.team_player_counts[team_id] = max(7, current_count - 1)

        # Own goal tracking
        is_og = (
            action_type == ActionType.OWN_GOAL
            or outcome == "own_goal"
            or bool(raw.get("is_own_goal"))
        )
        if is_og:
            outcome = "own_goal"
            self.own_goals.append({
                "event_id": f"sb_{self.match_id}_{idx:05d}",
                "clock_seconds": clock_sec,
                "team_id": team_id,
                "player_name": player_name,
                "location": (x_m, y_m),
            })

        # Penalty shootout tracking
        if period >= 5 and action_type == ActionType.SHOT:
            kick_idx = len(self.shootout_kicks) + 1
            is_sudden_death = (kick_idx > 10)
            self.shootout_kicks.append({
                "kick_index": kick_idx,
                "period": period,
                "clock_seconds": clock_sec,
                "team_id": team_id,
                "player_name": player_name,
                "outcome": outcome,
                "is_sudden_death": is_sudden_death,
            })

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
            card=card,
            is_own_goal=True if is_og else None,
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

    def get_discipline_summary(self) -> dict[str, Any]:
        """Return match disciplinary summary including active player counts and man advantage."""
        teams = list(self.team_player_counts.keys())
        man_advantage = None
        if len(teams) >= 2:
            t1, t2 = teams[0], teams[1]
            c1, c2 = self.team_player_counts[t1], self.team_player_counts[t2]
            if c1 > c2:
                man_advantage = {"advantaged_team": t1, "disadvantaged_team": t2, "difference": c1 - c2}
            elif c2 > c1:
                man_advantage = {"advantaged_team": t2, "disadvantaged_team": t1, "difference": c2 - c1}
        return {
            "team_player_counts": dict(self.team_player_counts),
            "yellow_cards_count": len(self.yellow_cards),
            "red_cards_count": len(self.red_cards),
            "expulsions": list(self.expulsions),
            "man_advantage": man_advantage,
        }

    def get_shootout_summary(self) -> dict[str, Any]:
        """Return structured summary of penalty shootout including sudden death."""
        if not self.shootout_kicks:
            return {"is_shootout": False, "total_kicks": 0}

        team_goals: dict[str, int] = {}
        for kick in self.shootout_kicks:
            t = kick["team_id"]
            if t not in team_goals:
                team_goals[t] = 0
            if kick["outcome"] == "goal":
                team_goals[t] += 1

        sudden_death = any(k.get("is_sudden_death") for k in self.shootout_kicks)
        return {
            "is_shootout": True,
            "total_kicks": len(self.shootout_kicks),
            "team_shootout_goals": team_goals,
            "sudden_death_reached": sudden_death,
            "kicks": list(self.shootout_kicks),
        }

    @classmethod
    def load_multiple_matches(
        cls,
        matches_data: list[dict[str, Any]],
    ) -> dict[str, list[NormalizedEvent]]:
        """Batch load multiple raw match payloads with per-match error boundary."""
        results: dict[str, list[NormalizedEvent]] = {}
        for idx, match_dict in enumerate(matches_data):
            try:
                meta = match_dict.get("metadata", {})
                match_id = str(meta.get("match_id") or match_dict.get("match_id") or f"batch_match_{idx}")
                raw_events = match_dict.get("events", [])
                adapter = cls(match_id=match_id)
                results[match_id] = adapter.load_events(raw_events)
            except Exception:
                match_id = f"error_match_{idx}"
                results[match_id] = []
        return results

    @classmethod
    def load_matches_from_directory(
        cls,
        dir_path: str | Path,
    ) -> tuple[dict[str, list[NormalizedEvent]], dict[str, str]]:
        """Scan directory and load all JSON match files with error isolation."""
        directory = Path(dir_path)
        if not directory.exists():
            return {}, {"directory": f"Path not found: {directory}"}

        matches: dict[str, list[NormalizedEvent]] = {}
        errors: dict[str, str] = {}

        for file_path in sorted(directory.glob("*.json")):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                meta = data.get("metadata", {})
                match_id = str(meta.get("match_id") or file_path.stem)
                raw_events = data.get("events", [])
                adapter = cls(match_id=match_id)
                matches[match_id] = adapter.load_events(raw_events)
            except Exception as exc:
                errors[str(file_path.name)] = str(exc)

        return matches, errors

    @classmethod
    def get_attribution(cls) -> dict[str, str]:
        """Return legal attribution and logo requirements for frontend and exports."""
        return {
            "license": STATSBOMB_LICENSE_REF,
            "attribution": STATSBOMB_ATTRIBUTION_TEXT,
            "logo_requirement": STATSBOMB_LOGO_REQUIREMENT,
        }

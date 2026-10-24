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

from ..provider_terms import (
    STATSBOMB_ATTRIBUTION_TEXT,
    STATSBOMB_LICENSE_REF,
    STATSBOMB_LOGO_REQUIREMENT,
)
from ..schema import ActionType, DataCoverageLevel, NormalizedEvent, RawSourceRecord

# StatsBomb timestamps are period-relative (they reset to 00:00:00.000 at every
# period start) while the provider's ``minute``/``second`` fields carry the
# conventional match minute. The nominal anchors below are the football
# boundaries; the observed overrun of each period (added stoppage time) is
# carried forward so the match clock stays monotonic across half-time breaks.
NOMINAL_PERIOD_START_MINUTES: dict[int, int] = {1: 0, 2: 45, 3: 90, 4: 105, 5: 120}
NOMINAL_PERIOD_START_SECONDS: dict[int, float] = {
    period: minute * 60.0 for period, minute in NOMINAL_PERIOD_START_MINUTES.items()
}
SHOOTOUT_FIRST_PERIOD = 5

PERIOD_LABELS: dict[int, str] = {
    1: "first_half",
    2: "second_half",
    3: "extra_time_1",
    4: "extra_time_2",
    5: "shootout",
}

SET_PIECE_BY_PLAY_PATTERN: dict[str, str] = {
    "From Corner": "corner",
    "From Free Kick": "free_kick",
    "Free Kick (Penalty)": "penalty",
    "From Throw In": "throw_in",
    "From Goal Kick": "goal_kick",
    "From Kick Off": "kick_off",
    "Kick Off": "kick_off",
    "From Penalty": "penalty",
}

# StatsBomb position names are free-form; the role is derived from the name so
# that squad-wide positions remain usable for cross-match comparisons.
POSITION_ROLE_BY_NAME: tuple[tuple[str, str], ...] = (
    ("goalkeeper", "goalkeeper"),
    ("back", "defender"),
    ("wing", "forward"),
    ("forward", "forward"),
)


def position_role(position_name: str | None) -> str | None:
    if not position_name:
        return None
    lowered = str(position_name).lower()
    for needle, role in POSITION_ROLE_BY_NAME:
        if needle in lowered:
            return role
    return "midfielder"



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
        # Avoid "sb_sb_wc2022_final_..." double prefixes.
        self.event_prefix = match_id if match_id.startswith("sb_") else f"sb_{match_id}"
        self.team_player_counts: dict[str, int] = {}
        self.red_cards: list[dict[str, Any]] = []
        self.yellow_cards: list[dict[str, Any]] = []
        self.expulsions: list[dict[str, Any]] = []
        self.own_goals: list[dict[str, Any]] = []
        self.shootout_kicks: list[dict[str, Any]] = []
        self.reordered_events: list[dict[str, Any]] = []

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
    def period_elapsed_seconds(cls, raw: dict[str, Any]) -> float:
        """Seconds elapsed inside the event's own period.

        The provider's ``timestamp`` resets at every period start and is the
        most precise source. ``minute``/``second`` are the conventional match
        minute, so they are only used when no timestamp is present.
        """
        period = int(raw.get("period", 1) or 1)
        timestamp = raw.get("timestamp")
        if timestamp:
            try:
                parts = str(timestamp).split(":")
                if len(parts) >= 3:
                    hours, minutes, seconds = int(parts[0]), int(parts[1]), float(parts[2])
                    return round(hours * 3600 + minutes * 60 + seconds, 3)
            except (TypeError, ValueError):
                pass
        minute = int(raw.get("minute", 0) or 0)
        second = int(raw.get("second", 0) or 0)
        if period >= SHOOTOUT_FIRST_PERIOD:
            # Every shootout period shares the 120-minute anchor so the
            # shootout timeline stays continuous across sudden death.
            base = NOMINAL_PERIOD_START_SECONDS[SHOOTOUT_FIRST_PERIOD]
        else:
            base = NOMINAL_PERIOD_START_MINUTES.get(period, 0) * 60
        return round(max(0.0, minute * 60 + second - base), 3)

    @classmethod
    def compute_period_offsets(cls, raw_events: list[dict[str, Any]]) -> dict[int, float]:
        """Cumulative match-clock anchors that keep the clock monotonic.

        Each period starts at the later of its nominal football boundary and
        the end of the previous period, so the added stoppage time of a half
        is carried into the next one instead of being silently dropped.
        """
        period_last: dict[int, float] = {}
        for raw in raw_events:
            period = int(raw.get("period", 1) or 1)
            elapsed = cls.period_elapsed_seconds(raw)
            if elapsed > period_last.get(period, 0.0):
                period_last[period] = elapsed

        offsets: dict[int, float] = {}
        previous_end = 0.0
        match_end = 0.0
        for period in sorted(period_last):
            if period >= SHOOTOUT_FIRST_PERIOD:
                # A shootout is a separate phase: it restarts from the
                # nominal 120-minute anchor, after the match proper.
                anchor = max(NOMINAL_PERIOD_START_SECONDS[SHOOTOUT_FIRST_PERIOD], match_end)
            else:
                anchor = max(NOMINAL_PERIOD_START_SECONDS.get(period, previous_end), previous_end)
            offsets[period] = anchor
            end = anchor + period_last[period]
            previous_end = end
            if period < SHOOTOUT_FIRST_PERIOD:
                match_end = end
        return offsets

    @classmethod
    def match_clock_seconds(
        cls, period: int, elapsed_seconds: float, offsets: dict[int, float] | None = None
    ) -> float:
        """Monotonic match-elapsed clock for an event inside a period."""
        anchor = (offsets or {}).get(period)
        if anchor is None:
            anchor = NOMINAL_PERIOD_START_SECONDS.get(period, 0.0)
        return round(anchor + float(elapsed_seconds), 3)

    @classmethod
    def map_action_type(cls, sb_type_name: str) -> ActionType:
        """Map StatsBomb event type string to standard ActionType enum."""
        mapping = {
            "Pass": ActionType.PASS,
            "Shot": ActionType.SHOT,
            "Carry": ActionType.CARRY,
            "Dribble": ActionType.CARRY,
            "Ball Receipt": ActionType.RECEIPT,
            "Ball Receipt*": ActionType.RECEIPT,
            "Miscontrol": ActionType.MISCONTROL,
            "Ball Recovery": ActionType.RECOVERY,
            "Interception": ActionType.INTERCEPTION,
            "Clearance": ActionType.CLEARANCE,
            "Dispossessed": ActionType.DISPOSSESSED,
            "Duel": ActionType.DUEL,
            "50/50": ActionType.DUEL,
            "Foul Committed": ActionType.FOUL,
            "Foul Won": ActionType.FOUL,
            "Goal Keeper": ActionType.GOALKEEPER,
            "Starting XI": ActionType.RESTART,
            "Half Start": ActionType.RESTART,
            "Half End": ActionType.PERIOD_END,
            "Period End": ActionType.PERIOD_END,
            "Own Goal Against": ActionType.OWN_GOAL,
            "Own Goal For": ActionType.OWN_GOAL,
            "Bad Behaviour": ActionType.BAD_BEHAVIOUR,
            "Card": ActionType.FOUL,
            # Off-ball events: the actor is not in possession of the ball and
            # must never move the possession state machine.
            "Pressure": ActionType.OFF_BALL,
            "Block": ActionType.OFF_BALL,
            "Shield": ActionType.OFF_BALL,
            "Dribbled Past": ActionType.OFF_BALL,
            "Tactical Shift": ActionType.OFF_BALL,
            "Injury Stoppage": ActionType.OFF_BALL,
            "Substitution": ActionType.OFF_BALL,
            "Player Off": ActionType.OFF_BALL,
            "Player On": ActionType.OFF_BALL,
            "Offside": ActionType.OFF_BALL,
            "Referee Ball-Drop": ActionType.OFF_BALL,
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

        if type_name == "Own Goal For":
            # The recorded team is the beneficiary, so the goal is credited to it.
            return "own_goal_for"
        if type_name == "Own Goal Against" or action_type == ActionType.OWN_GOAL:
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
            if not isinstance(duel_info, dict):
                duel_info = raw.get("50/50", {})
            outcome = duel_info.get("outcome") if isinstance(duel_info, dict) else None
            name = str(outcome.get("name")).lower() if isinstance(outcome, dict) else ""
            if name.startswith("won") or name.startswith("success"):
                return "won"
            if name.startswith("lost"):
                return "lost"
            return name or "success"
        elif action_type == ActionType.INTERCEPTION:
            int_info = raw.get("interception", {})
            outcome = int_info.get("outcome") if isinstance(int_info, dict) else None
            return outcome.get("name").lower() if isinstance(outcome, dict) else "won"
        elif action_type == ActionType.GOALKEEPER:
            keeper_info = raw.get("goalkeeper", {})
            keeper_type = keeper_info.get("type", {}) if isinstance(keeper_info, dict) else {}
            name = keeper_type.get("name") if isinstance(keeper_type, dict) else None
            if name:
                return str(name).lower().replace(" ", "_")
            return "keeper_action"
        elif action_type == ActionType.MISCONTROL:
            return "miscontrol"
        elif action_type == ActionType.RECEIPT:
            return "control"
        elif action_type == ActionType.OFF_BALL:
            type_name_lower = type_name.lower()
            if type_name_lower == "foul won":
                foul_won = raw.get("foul_won", {})
                if isinstance(foul_won, dict) and foul_won.get("defensive"):
                    return "foul_won_defensive"
                return "foul_won"
            return type_name_lower.replace(" ", "_")
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
        *,
        offsets: Optional[dict[int, float]] = None,
        player_index: Optional[dict[str, dict[str, Any]]] = None,
    ) -> NormalizedEvent:
        """Converts a single raw StatsBomb JSON event into NormalizedEvent."""
        raw_id = str(raw.get("id", "unknown"))
        idx = int(raw.get("index", 1))
        period = int(raw.get("period", 1))
        minute = int(raw.get("minute", 0))
        second = int(raw.get("second", 0))
        timestamp = raw.get("timestamp")

        elapsed = self.period_elapsed_seconds(raw)
        clock_sec = self.match_clock_seconds(period, elapsed, offsets)

        team = raw.get("team", {})
        provider_team_id = str(team.get("id")) if team.get("id") is not None else None
        provider_team_name = str(team.get("name")) if team.get("name") is not None else None
        # Canonical provider identity is the numeric ID. Display names are
        # retained separately and never used to infer home/away.
        team_id = provider_team_id or provider_team_name or "unknown_team"
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
        if end_loc is None and isinstance(raw.get("dribble"), dict):
            end_loc = raw.get("dribble", {}).get("end_location")

        end_x_m, end_y_m = self.extract_location(end_loc)

        # --- squad / set-piece / substitution context --------------------------------
        index_entry = (player_index or {}).get(player_id or "", {})
        position_name = index_entry.get("position")
        if position_name is None:
            raw_position = raw.get("position")
            if isinstance(raw_position, dict) and raw_position.get("name"):
                position_name = str(raw_position["name"])
        jersey_number = index_entry.get("jersey_number")
        if jersey_number is None:
            raw_position = raw.get("position")
            jersey_number = raw_position.get("jersey_number") if isinstance(raw_position, dict) else None

        play_pattern = raw.get("play_pattern")
        play_pattern_name = str(play_pattern.get("name")) if isinstance(play_pattern, dict) else None
        set_piece = SET_PIECE_BY_PLAY_PATTERN.get(play_pattern_name or "") or None
        if set_piece is None and action_type == ActionType.PASS:
            pass_info = raw.get("pass")
            pass_type = pass_info.get("type", {}) if isinstance(pass_info, dict) else {}
            pass_type_name = str(pass_type.get("name")) if isinstance(pass_type, dict) else ""
            if "corner" in pass_type_name.lower():
                set_piece = "corner"
            elif "free kick" in pass_type_name.lower():
                set_piece = "free_kick"
            elif "throw" in pass_type_name.lower():
                set_piece = "throw_in"
            elif "goal kick" in pass_type_name.lower():
                set_piece = "goal_kick"

        substitution = raw.get("substitution")
        substitution_on_id = substitution_on_name = None
        substitution_off_id = substitution_off_name = None
        if isinstance(substitution, dict):
            replacement = substitution.get("replacement")
            if isinstance(replacement, dict):
                substitution_on_id = str(replacement.get("id")) if replacement.get("id") is not None else None
                substitution_on_name = (
                    str(replacement.get("name")) if replacement.get("name") is not None else None
                )
            # In the provider payload the actor of a Substitution event is the
            # player leaving the pitch; the replacement is the one entering.
            if player_id:
                substitution_off_id = player_id
                substitution_off_name = player_name
        if type_name == "Player On" and player_id and substitution_on_id is None:
            substitution_on_id, substitution_on_name = player_id, player_name
        if type_name == "Player Off" and player_id and substitution_off_id is None:
            substitution_off_id, substitution_off_name = player_id, player_name

        lineup_role = index_entry.get("lineup_role")
        if lineup_role is None and type_name == "Starting XI":
            lineup_role = "starter"

        # Card & discipline tracking
        card = self.parse_card(raw)
        if card:
            card_record = {
                "event_id": f"{self.event_prefix}_{idx:05d}",
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
            or outcome in ("own_goal", "own_goal_for")
            or bool(raw.get("is_own_goal"))
        )
        if is_og and outcome != "own_goal_for":
            outcome = "own_goal"
            self.own_goals.append({
                "event_id": f"{self.event_prefix}_{idx:05d}",
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
            event_id=f"{self.event_prefix}_{idx:05d}",
            match_id=self.match_id,
            source=source,
            period=period,
            clock_seconds=clock_sec,
            clock_basis="match_elapsed",
            provider_minute=minute,
            provider_second=second,
            team_id=team_id,
            provider_team_id=provider_team_id,
            provider_team_name=provider_team_name,
            attack_direction="left_to_right",  # StatsBomb standardizes attack L-to-R for all events
            possession_id=possession_id,
            possession_changed=possession_changed,
            is_shootout=bool(period >= 5),
            player_id=player_id,
            player_name=player_name,
            jersey_number=int(jersey_number) if isinstance(jersey_number, int) else None,
            action_type=action_type,
            outcome=outcome,
            card=card,
            is_own_goal=True if is_og else None,
            x=x_m,
            y=y_m,
            end_x=end_x_m,
            end_y=end_y_m,
            period_label=PERIOD_LABELS.get(period, f"period_{period}"),
            play_pattern=play_pattern_name,
            set_piece=set_piece,
            position=position_name,
            position_role=position_role(position_name),
            lineup_role=lineup_role,
            substitution_off_player_id=substitution_off_id,
            substitution_off_player_name=substitution_off_name,
            substitution_on_player_id=substitution_on_id,
            substitution_on_player_name=substitution_on_name,
        )

    @staticmethod
    def build_player_index(raw_events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Map provider player id -> jersey number, position and lineup role.

        Jersey numbers only exist in the provider's lineup payloads, so they
        are harvested from the Starting XI event and the substitutions that
        follow it.
        """
        index: dict[str, dict[str, Any]] = {}
        for raw in raw_events:
            tactics = raw.get("tactics")
            if not isinstance(tactics, dict):
                continue
            lineup = tactics.get("lineup")
            if not isinstance(lineup, list):
                continue
            for entry in lineup:
                if not isinstance(entry, dict):
                    continue
                player = entry.get("player")
                if not isinstance(player, dict) or player.get("id") is None:
                    continue
                pid = str(player["id"])
                position = entry.get("position")
                index[pid] = {
                    "jersey_number": entry.get("jersey_number"),
                    "position": str(position.get("name")) if isinstance(position, dict) else None,
                    "lineup_role": "starter",
                }
        for raw in raw_events:
            substitution = raw.get("substitution")
            if not isinstance(substitution, dict):
                continue
            replacement = substitution.get("replacement")
            if not isinstance(replacement, dict) or replacement.get("id") is None:
                continue
            pid = str(replacement["id"])
            entry = index.setdefault(pid, {"jersey_number": None, "position": None, "lineup_role": "substitute"})
            entry["lineup_role"] = "substitute"
        return index

    @classmethod
    def sort_events_by_period_clock(
        cls, raw_events: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Order each period by its own timestamps, keeping the provider index.

        StatsBomb occasionally appends an event to the end of a period whose
        timestamp belongs to the start of that period. The timestamp and the
        provider minute agree with each other, only the index position is
        wrong, so the period is re-ordered by time and the moved events are
        reported to the caller instead of being silently dropped.
        """
        by_period: dict[int, list[tuple[int, dict[str, Any]]]] = {}
        for position, raw in enumerate(raw_events):
            by_period.setdefault(int(raw.get("period", 1) or 1), []).append((position, raw))

        ordered: list[dict[str, Any]] = []
        moved: list[dict[str, Any]] = []
        for period in sorted(by_period):
            bucket = by_period[period]
            elapsed_by_event = [
                (cls.period_elapsed_seconds(raw), int(raw.get("index", 0) or 0), raw)
                for _global, raw in bucket
            ]
            for position, (elapsed, index, raw) in enumerate(elapsed_by_event):
                if position and elapsed < elapsed_by_event[position - 1][0]:
                    moved.append(
                        {
                            "provider_event_id": str(raw.get("id", "")),
                            "index": index,
                            "period": period,
                            "clock_seconds": elapsed,
                            "reason": "out_of_order_period_timestamp",
                        }
                    )
            ordered.extend(raw for _elapsed, _index, raw in sorted(
                elapsed_by_event, key=lambda item: (item[0], item[1])
            ))
        return ordered, moved

    def load_events(self, raw_events: list[dict[str, Any]]) -> list[NormalizedEvent]:
        """Convert a full list of raw StatsBomb events into NormalizedEvent stream."""
        normalized: list[NormalizedEvent] = []
        prev_team_id: Optional[str] = None
        ordered, moved = self.sort_events_by_period_clock(raw_events)
        self.reordered_events = moved
        offsets = self.compute_period_offsets(ordered)
        player_index = self.build_player_index(ordered)

        for raw in ordered:
            ev = self.normalize_event(
                raw,
                prev_team_id=prev_team_id,
                offsets=offsets,
                player_index=player_index,
            )
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

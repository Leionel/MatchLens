"""One continuous synthetic match. Every fact is derived from validated events."""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Team = Literal["H", "N"]
TEAMS = {"H": "Harbor FC", "N": "Northbridge United"}
PLAYERS = {
    "H": {"H1": "Leo Vale", "H6": "Owen Reed", "H8": "Eli Park", "H9": "Kai Stone"},
    "N": {"N1": "Finn Cole", "N6": "Noah Bell", "N8": "Max Lane", "N9": "Alex West"},
}
CHAPTERS = [
    {"id": "A", "at": 360, "title": "Possession without penetration", "question": "Has more of the ball meant more threat?"},
    {"id": "B", "at": 540, "title": "Recoveries to transition shots", "question": "What followed Harbor's ball recoveries?"},
    {"id": "C", "at": 720, "title": "Goal and match recap", "question": "Which sequence ended with the goal?"},
]
SCENARIOS: dict[str, dict] = {
    "default": {
        "id": "default",
        "label": "Possession Dominance (1–0)",
        "archetype": "Possession Dominance",
        "description": "Harbor dominates middle-window possession without penetration, then wins high recoveries and scores late.",
    },
    "counterattack": {
        "id": "counterattack",
        "label": "Fast Counterattack (0–1)",
        "archetype": "Fast Counterattacking",
        "description": "Harbor holds territorial possession, while Northbridge absorbs pressure and strikes via rapid vertical counters.",
    },
    "transitions": {
        "id": "transitions",
        "label": "High Transition Activity (1–1)",
        "archetype": "High Transition Activity",
        "description": "Frequent midfield and high turnovers trigger end-to-end transition shots and goals for both teams.",
    },
    "balanced": {
        "id": "balanced",
        "label": "Balanced Competitive (1–1)",
        "archetype": "Balanced Competitive Match",
        "description": "Evenly matched possession, alternating final-third entries and traded goals across both periods.",
    },
    "stalemate": {
        "id": "stalemate",
        "label": "Defensive Stalemate (0–0)",
        "archetype": "Low-Event / Defensive Stalemate",
        "description": "High middle-third circulation and saved efforts with no breakthrough goal.",
    },
    "comeback": {
        "id": "comeback",
        "label": "Momentum Comeback (2–1)",
        "archetype": "Comeback / Momentum Reversal",
        "description": "Northbridge scores early on the break before Harbor reverses momentum with two second-half goals.",
    },
}


def other(team: str) -> str:
    return "N" if team == "H" else "H"


def attack_x(team: str, x: float) -> float:
    return x if team == "H" else 105 - x


class Event(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    seq: int = Field(ge=1)
    t: int = Field(ge=0, le=720)
    kind: Literal["restart", "pass", "recovery", "shot", "end"]
    team: Team
    actor: str
    receiver: str | None = None
    start: tuple[float, float]
    end: tuple[float, float]
    outcome: Literal["complete", "saved", "goal"] = "complete"


def generate_match(seed: int = 17, scenario: str = "default") -> tuple[Event, ...]:
    """Controlled possession lengths; seeded pass paths, no AI claims or verdicts."""
    if scenario not in SCENARIOS:
        raise ValueError("unknown_scenario")
    rng = random.Random(seed)
    result: list[Event] = []
    owner, holder, ball = "H", "H6", (52.5, 34.0)

    def add(t: int, kind: str, team: str, actor: str, end: tuple[float, float],
            receiver: str | None = None, outcome: str = "complete") -> None:
        nonlocal owner, holder, ball
        e = Event(id=f"E{len(result)+1:04d}", seq=len(result)+1, t=t, kind=kind,
                  team=team, actor=actor, receiver=receiver, start=ball, end=end, outcome=outcome)
        result.append(e)
        ball = end
        if kind == "shot":
            owner, holder = (other(team), other(team)+"1") if outcome == "saved" else ("", "")
        else:
            owner, holder = team, receiver or actor

    def passes(start: int, stop: int, mode: str) -> None:
        for t in range(start+5, stop, 5):
            teammates = [owner+n for n in ("6", "8", "9") if owner+n != holder]
            receiver = rng.choice(teammates)
            ax = {"safe": (28, 59), "back": (20, 30), "attack": (76, 91)}[mode]
            x = round(rng.uniform(*ax), 1)
            if owner == "N":
                x = round(105-x, 1)
            add(t, "pass", owner, holder, (x, round(rng.uniform(17, 51), 1)), receiver)

    add(0, "restart", "H", "H6", ball)
    if scenario in ("default", "stalemate"):
        final_action = "saved" if scenario == "stalemate" else "goal"
        # (end time, pass profile, ending action). All are one continuous prefix.
        phases = [
            (50, "attack", "saved"), (100, "attack", "recover"),
            (130, "attack", "saved"), (180, "attack", "recover"),
            (330, "safe", "recover"), (370, "back", "recover"),
            (378, "attack", "saved"), (400, "back", "recover"),
            (408, "attack", "saved"), (470, "back", "recover"),
            (520, "attack", "saved"), (540, "back", "recover"),
            (580, "safe", "recover"), (630, "back", "recover"),
            (690, "attack", final_action),
        ]
        start = 0
        for stop, mode, action in phases:
            passes(start, stop, mode)
            if action == "recover":
                gaining = other(owner)
                add(stop, "recovery", gaining, gaining+"8", ball)
            else:
                team = owner
                end_x = (105.0 if team == "H" else 0.0) if action == "goal" else (104.0 if team == "H" else 1.0)
                add(stop, "shot", team, holder, (end_x, 34.0), outcome=action)
            start = stop
        if scenario == "stalemate":
            passes(690, 720, "safe")
        else:
            add(692, "restart", "N", "N6", (52.5, 34.0))
            passes(692, 720, "safe")
    else:
        scenario_phases: dict[str, list[tuple[int, str, str]]] = {
            "counterattack": [
                (90, "safe", "recover"), (125, "attack", "saved"),
                (175, "safe", "recover"), (180, "back", "recover"),
                (315, "safe", "recover"), (345, "back", "recover"),
                (390, "back", "recover"), (398, "attack", "saved"),
                (445, "back", "recover"), (453, "attack", "saved"),
                (535, "safe", "recover"), (565, "back", "recover"),
                (635, "safe", "recover"), (665, "attack", "goal"),
            ],
            "transitions": [
                (45, "attack", "saved"), (75, "back", "recover"),
                (83, "attack", "saved"), (140, "back", "recover"),
                (148, "attack", "saved"), (210, "back", "recover"),
                (218, "attack", "goal"), (310, "back", "recover"),
                (318, "attack", "saved"), (395, "back", "recover"),
                (403, "attack", "saved"), (480, "safe", " saved".strip()),
                (535, "back", "recover"), (543, "attack", "goal"),
                (640, "safe", "recover"),
            ],
            "balanced": [
                (60, "attack", "saved"), (120, "attack", "saved"),
                (180, "safe", "recover"), (240, "attack", "goal"),
                (320, "safe", "recover"), (360, "attack", "saved"),
                (495, "attack", "goal"), (565, "safe", "recover"),
                (630, "attack", "saved"),
            ],
            "comeback": [
                (70, "safe", "recover"), (135, "attack", "goal"),
                (230, "safe", "recover"), (290, "safe", "recover"),
                (360, "back", "recover"), (368, "attack", "saved"),
                (415, "back", "recover"), (423, "attack", "saved"),
                (475, "safe", "recover"), (515, "back", "recover"),
                (525, "attack", "goal"), (585, "back", "recover"),
                (660, "attack", "goal"),
            ],
        }
        start = 0
        for stop, mode, action in scenario_phases[scenario]:
            passes(start, stop, mode)
            if action == "recover":
                gaining = other(owner)
                add(stop, "recovery", gaining, gaining+"8", ball)
                start = stop
            else:
                team = owner
                end_x = (105.0 if team == "H" else 0.0) if action == "goal" else (104.0 if team == "H" else 1.0)
                add(stop, "shot", team, holder, (end_x, 34.0), outcome=action)
                if action == "goal":
                    kickoff_team = other(team)
                    add(stop+2, "restart", kickoff_team, kickoff_team+"6", (52.5, 34.0))
                    start = stop+2
                else:
                    start = stop
        passes(start, 720, "safe")
    add(720, "end", owner, holder, ball)
    reduce_match(tuple(result), 720)  # Generation and ingestion use the same legality checks.
    return tuple(result)


def _field(e: Any, name: str, default: Any = None) -> Any:
    if isinstance(e, dict):
        return e.get(name, default)
    return getattr(e, name, default)


def _location_pair(e: Any, start_name: str, end_name: str) -> tuple[float | None, float | None]:
    """Return a coordinate pair without ever substituting a synthetic centre."""
    x = _field(e, start_name)
    y = _field(e, "y" if start_name == "x" else "end_y")
    if x is None or y is None:
        return None, None
    try:
        fx, fy = float(x), float(y)
    except (TypeError, ValueError):
        return None, None
    if not (0.0 <= fx <= 105.0 and 0.0 <= fy <= 68.0):
        raise ValueError("coordinate_bounds")
    return fx, fy


def _normalized_kind(raw_action: str, outcome: str) -> str:
    action = raw_action.lower().replace("actiontype.", "").replace("_", " ")
    outcome = outcome.lower().replace("_", " ")
    if "own goal" in action or "own goal" in outcome:
        return "own_goal"
    if "ball receipt" in action:
        return "receipt"
    if "miscontrol" in action:
        return "miscontrol"
    if "shot" in action:
        return "shot"
    if "pass" in action:
        return "pass"
    if "carry" in action:
        return "carry"
    if any(k in action for k in ("recovery", "interception", "tackle")):
        return "recovery"
    if "duel" in action or "50/50" in action:
        # A contested ball is a possession event: won means a gain, lost a loss.
        return "recovery" if outcome.startswith("won") else "turnover"
    if "goal keeper" in action:
        # A conceded goal leaves the ball dead; the restart opens the next phase.
        return "off_ball" if outcome in ("goal conceded", "penalty conceded") else "recovery"
    if any(k in action for k in ("starting xi", "half start", "kick off", "restart")):
        return "restart"
    if any(k in action for k in ("half end", "period end", "match end")):
        return "period_end"
    if any(k in action for k in ("dispossessed", "clearance")):
        return "turnover"
    if any(k in action for k in ("off ball", "pressure", "block", "shield", "dribbled past",
                                 "tactical shift", "injury stoppage", "substitution",
                                 "player on", "player off", "offside", "referee ball-drop")):
        return "off_ball"
    if "foul" in action or "bad behaviour" in action or "card" in action:
        return "foul"
    return "other"


def _map_provider_team(
    raw: str,
    *,
    team_map: dict[str, str] | None,
    home_team_id: str | None,
    away_team_id: str | None,
) -> str:
    # Already-canonical events (synthetic or catalog-canonicalized provider
    # events) keep their code; provider IDs are never literally "H"/"N".
    if raw in ("H", "N"):
        return raw
    if team_map and raw in team_map:
        return team_map[raw]
    if home_team_id is not None and raw == home_team_id:
        return "H"
    if away_team_id is not None and raw == away_team_id:
        return "N"
    raise ValueError(f"unmapped_provider_team: {raw}")


def reduce_match(
    events: tuple[Event, ...] | list[Any],
    at: int,
    max_duration: int = 720,
    is_synthetic: bool = True,
    team_names: dict[str, str] | None = None,
    *,
    team_map: dict[str, str] | None = None,
    home_team_id: str | None = None,
    away_team_id: str | None = None,
    coordinate_frame: Literal["fixed", "team_relative"] | None = None,
    continuous_coverage: bool | None = None,
    max_gap_seconds: float = 15.0,
    official_score: dict[str, int] | None = None,
) -> dict:
    """Reduce events to an observable as-of match state.

    The reducer is a possession state machine. Controlled time belongs to the
    possession that owns it; a new possession ID is only minted at a restart,
    an observed turnover, a goal restart, a provider possession change, or a
    data discontinuity. Missing coordinates stay missing (never 52.5/34.0).
    """
    if not 0 <= at <= max(720, max_duration):
        raise ValueError("clock_out_of_bounds")
    frame: Literal["fixed", "team_relative"] = coordinate_frame or (
        "fixed" if is_synthetic else "team_relative"
    )
    continuous = (is_synthetic and max_duration == 720) if continuous_coverage is None else continuous_coverage
    team_names = team_names or dict(TEAMS)

    owner: str | None = None
    holder: str | None = None
    ball: tuple[float, float] | None = (52.5, 34.0) if is_synthetic else None
    score = {"H": 0, "N": 0}
    shootout_score = {"H": 0, "N": 0}
    goals: list[dict] = []
    own_goal_records: dict[tuple[int, float], dict] = {}
    last_t: float = -1.0
    last_period: int | None = None
    pending_restart: str | None = "H" if is_synthetic else None
    pending_after_shot = False
    ended = False
    enriched: list[dict] = []
    intervals: list[dict] = []
    possessions: list[dict] = []
    unobserved: list[dict] = []
    current: dict | None = None
    possession_no = 0

    def open_possession(team: str, t: float, reason: str) -> None:
        nonlocal current, possession_no
        possession_no += 1
        current = {
            "possession_id": possession_no,
            "team": team,
            "start_t": t,
            "end_t": t,
            "event_ids": [],
            "start_reason": reason,
            "provider_possession_ids": [],
        }
        possessions.append(current)

    def close_possession(t: float, reason: str) -> None:
        nonlocal current
        if not current:
            return
        end = max(current["start_t"], t)
        current["end_t"] = end
        current["end_reason"] = reason
        intervals.append({
            "start": current["start_t"],
            "end": end,
            "team": current["team"],
            "event_id": current["event_ids"][-1] if current["event_ids"] else None,
            "possession_id": current["possession_id"],
            "basis": "possession_state_machine",
        })
        current = None

    def mark_unobserved(start: float, end: float, reason: str) -> None:
        if end > start:
            unobserved.append({"start": start, "end": end, "reason": reason})

    for e in events:
        t_raw = _field(e, "t")
        if t_raw is None:
            t_raw = _field(e, "clock_seconds", 0)
        t_val = float(t_raw) if t_raw is not None else 0.0
        if t_val > at:
            break

        if is_synthetic and isinstance(e, Event):
            if e.seq != len(enriched) + 1 or e.id != f"E{e.seq:04d}" or e.t <= last_t or ended:
                raise ValueError("event_order_or_id")
            for x, y in (e.start, e.end):
                if not (0 <= x <= 105 and 0 <= y <= 68):
                    raise ValueError("coordinate_bounds")
            if e.actor not in PLAYERS[e.team] or e.start != ball:
                raise ValueError("actor_or_ball_discontinuity")
            if e.kind != "pass" and e.receiver is not None or e.kind != "shot" and e.outcome != "complete":
                raise ValueError("illegal_event_payload")
            kind = e.kind
            raw_action = e.kind
            t_mapped = e.team
            raw_actor = e.actor
            raw_outcome = e.outcome
            start = [float(e.start[0]), float(e.start[1])]
            end = [float(e.end[0]), float(e.end[1])]
            located = True
            provider_pid = None
            is_shootout = False
            row = {
                **e.model_dump(mode="json"),
                "actor_name": PLAYERS[e.team].get(e.actor, e.actor),
                "located": True,
                "period": 1,
                "is_shootout": False,
                "provider_team_id": None,
                "provider_possession_id": None,
            }
        else:
            eid = str(_field(e, "event_id") or _field(e, "id") or f"E{len(enriched)+1:04d}")
            raw_action = str(_field(e, "action_type") or _field(e, "kind") or "")
            raw_outcome = str(_field(e, "outcome") or "complete")
            raw_team = str(_field(e, "team_id") or _field(e, "team") or "")
            t_mapped = _map_provider_team(
                raw_team, team_map=team_map, home_team_id=home_team_id, away_team_id=away_team_id
            )
            raw_actor = str(_field(e, "player_name") or _field(e, "actor") or "Unknown")
            x, y = _location_pair(e, "x", "end_x")
            end_x, end_y = _location_pair(e, "end_x", "end_y")
            start = [x, y] if x is not None and y is not None else None
            end = [end_x, end_y] if end_x is not None and end_y is not None else None
            located = start is not None
            kind = _normalized_kind(raw_action, raw_outcome)
            provider_pid = _field(e, "possession_id")
            period = int(_field(e, "period") or 1)
            is_shootout = bool(_field(e, "is_shootout")) or period >= 5
            row = {
                "id": eid,
                "seq": len(enriched) + 1,
                "t": int(t_val) if float(t_val).is_integer() else t_val,
                "kind": kind,
                "team": t_mapped,
                "actor": raw_actor,
                "actor_name": raw_actor,
                "receiver": _field(e, "receiver"),
                "start": start,
                "end": end,
                "outcome": raw_outcome,
                "period": period,
                "attack_direction": (
                    "left_to_right" if frame == "team_relative"
                    else ("left_to_right" if t_mapped == "H" else "right_to_left")
                ),
                "located": located,
                "provider_team_id": _field(e, "provider_team_id") or raw_team,
                "provider_possession_id": provider_pid,
                "is_shootout": is_shootout,
                "source": _field(e, "source").model_dump(mode="json") if hasattr(_field(e, "source"), "model_dump") else _field(e, "source"),
                "player_id": _field(e, "player_id"),
                "jersey_number": _field(e, "jersey_number"),
                "position": _field(e, "position"),
                "position_role": _field(e, "position_role"),
                "set_piece": _field(e, "set_piece"),
                "play_pattern": _field(e, "play_pattern"),
                "period_label": _field(e, "period_label"),
                "provider_minute": _field(e, "provider_minute"),
                "card": _field(e, "card"),
                "is_own_goal": _field(e, "is_own_goal"),
            }

        period = int(row.get("period") or _field(e, "period") or 1)
        # --- order / coverage guards -------------------------------------------------
        if not is_synthetic and t_val < last_t:
            raise ValueError("event_order")
        if is_synthetic and ended:
            raise ValueError("event_order_or_id")

        # --- explicit period transition closes control; break is unobserved -------
        if last_period is not None and period != last_period:
            close_possession(last_t, "period_end")
            mark_unobserved(last_t, t_val, "period_break")
            owner = holder = None
            pending_after_shot = False
            pending_restart = None

        gap = t_val - last_t if last_t >= 0 else 0.0
        data_gap = gap > max_gap_seconds
        period_changed = last_period is not None and period != last_period
        if period_changed:
            # The break between periods is already accounted for above; it must
            # not be counted a second time as a data discontinuity.
            pass
        elif data_gap:
            if current:
                close_possession(last_t, "data_gap")
            mark_unobserved(last_t, t_val, "data_gap")
            owner = holder = None
            pending_after_shot = False
        elif gap > 0 and current is None and last_t >= 0:
            # Dead ball or uncovered transition between two states.
            mark_unobserved(last_t, t_val, "dead_ball")

        # --- synthetic legality checks ----------------------------------------------
        if is_synthetic and isinstance(e, Event):
            if pending_restart:
                if e.kind != "restart" or e.team != pending_restart or e.end != (52.5, 34.0):
                    raise ValueError("illegal_restart")
                pending_restart = None
            elif e.kind == "restart":
                raise ValueError("unexpected_restart")
            elif e.kind == "recovery":
                if e.team != other(owner) or e.start != e.end or e.receiver or e.outcome != "complete":
                    raise ValueError("illegal_recovery")
            elif e.kind != "end":
                if e.team != owner or (holder is not None and e.actor != holder):
                    raise ValueError("non_owner_action")
                if e.kind == "pass":
                    if e.receiver not in PLAYERS[e.team] or e.receiver == holder or e.outcome != "complete":
                        raise ValueError("illegal_pass")
                elif e.kind == "shot":
                    if e.outcome not in ("saved", "goal") or e.receiver:
                        raise ValueError("illegal_shot")
                    if e.outcome == "goal" and (
                        attack_x(e.team, e.end[0]) != 105 or abs(e.end[1] - 34) > 3.66
                    ):
                        raise ValueError("goal_outside_goal_mouth")
                elif e.kind == "end":
                    if e.t != 720 or e.start != e.end:
                        raise ValueError("illegal_end")

        # --- possession boundary decision -------------------------------------------
        terminal = kind in ("period_end", "foul", "turnover", "end")
        if terminal:
            close_possession(t_val, kind)
            owner = holder = None
            if kind == "end":
                ended = True
                owner, holder = t_mapped, raw_actor
            if kind == "period_end":
                pending_after_shot = False
        elif kind == "shot":
            if current is None:
                open_possession(t_mapped, t_val, "shot_without_buildup")
            owner, holder = t_mapped, raw_actor
        elif kind == "restart":
            close_possession(t_val, "restart")
            open_possession(t_mapped, t_val, "goal_restart" if pending_restart else "restart")
            owner, holder = t_mapped, raw_actor
            pending_restart = None
            pending_after_shot = False
        elif kind == "recovery":
            if current is not None and current["team"] != t_mapped:
                close_possession(t_val, "turnover")
                open_possession(t_mapped, t_val, "observed_gain")
            elif current is None:
                open_possession(t_mapped, t_val, "observed_gain")
            elif provider_pid is not None and current["provider_possession_ids"] and str(provider_pid) != str(current["provider_possession_ids"][-1]):
                close_possession(t_val, "provider_possession_change")
                open_possession(t_mapped, t_val, "provider_possession_change")
            owner, holder = t_mapped, raw_actor
        elif kind == "off_ball":
            # Off-ball actions (pressure, block, shield, off-ball substitutions,
            # tactical shifts, a conceded goal) leave the possession state
            # machine untouched: they are not part of a possession sequence.
            pass
        else:  # pass / carry / receipt / miscontrol / other
            boundary = None
            if current is None:
                boundary = "after_shot" if pending_after_shot else "observed_event"
            elif t_mapped != current["team"]:
                boundary = "observed_team_change"
            elif provider_pid is not None and current["provider_possession_ids"] and str(provider_pid) != str(current["provider_possession_ids"][-1]):
                boundary = "provider_possession_change"
            if boundary:
                close_possession(t_val, boundary)
                open_possession(t_mapped, t_val, boundary)
            owner, holder = t_mapped, (_field(e, "receiver") or raw_actor if kind == "pass" else raw_actor)
            pending_after_shot = False

        event_possession_id = (
            current["possession_id"] if current is not None
            else (possessions[-1]["possession_id"] if possessions else None)
        )
        if kind == "off_ball":
            event_possession_id = None
        elif current is not None:
            current["event_ids"].append(row["id"])
            if provider_pid is not None:
                current["provider_possession_ids"].append(str(provider_pid))

        # --- score / state transition ------------------------------------------------
        if kind == "own_goal":
            own_goal_for = "own goal for" in raw_outcome.lower().replace("_", " ")
            credited = t_mapped if own_goal_for else other(t_mapped)
            # A provider records one own goal twice: once for the beneficiary
            # ("Own Goal For") and once for the conceding side ("Own Goal
            # Against"). Both carry the same clock and the same scorer, so the
            # goal is counted once and the event that names the scorer becomes
            # its evidence.
            own_goal_key = (period, round(t_val, 3))
            if own_goal_key in own_goal_records:
                record = own_goal_records[own_goal_key]
                if record.get("actor") in (None, "", "Unknown") and raw_actor not in (None, "", "Unknown"):
                    record["event_id"] = row["id"]
                    record["actor"] = raw_actor
                    record["actor_name"] = raw_actor
            else:
                own_goal_records[own_goal_key] = {
                    "event_id": row["id"],
                    "team": credited,
                    "t": t_val,
                    "own_goal": True,
                    "actor": raw_actor,
                    "actor_name": raw_actor,
                }
                if not is_shootout:
                    score[credited] += 1
                    goals.append(own_goal_records[own_goal_key])
                close_possession(t_val, "own_goal")
                owner = holder = None
                pending_restart = credited
        elif kind == "shot":
            goal = "goal" in raw_outcome.lower()
            if goal and is_shootout:
                shootout_score[t_mapped] += 1
            elif goal:
                score[t_mapped] += 1
                goals.append({"event_id": row["id"], "team": t_mapped, "t": t_val, "own_goal": False})
            close_possession(t_val, "goal" if goal else "shot")
            # A saved/missed shot does not hand control to the shooter. Under
            # continuous coverage the goalkeeper side takes over from the save
            # instant; with partial coverage that interval stays unknown until
            # the next recorded touch.
            if not goal and continuous:
                open_possession(other(t_mapped), t_val, "shot_rebound")
            owner = other(t_mapped) if not goal else None
            holder = None
            pending_restart = other(t_mapped) if goal and not is_shootout else None
            pending_after_shot = False if (not goal and continuous) else not goal

        row["possession_id"] = event_possession_id
        row["possessor_after"] = current["team"] if current is not None else None
        row["owner_after"] = owner
        row["holder_after"] = holder
        row["coordinate_frame"] = frame
        enriched.append(row)

        if located and end is not None:
            ball = (end[0], end[1])
        last_t = t_val
        last_period = period

    # --- tail handling ------------------------------------------------------------
    if current is not None:
        if continuous:
            close_possession(max(last_t, min(at, max_duration)), "observation_end")
        else:
            close_possession(last_t, "last_observed_event")
    if last_t >= 0 and at > last_t:
        if current is None and not continuous:
            mark_unobserved(last_t, at, "coverage_end")
        elif continuous and not ended:
            mark_unobserved(last_t, at, "coverage_end")

    controlled = sum(i["end"] - i["start"] for i in intervals)
    dead = [g for g in unobserved if g["reason"] in ("dead_ball", "period_break")]
    duration = max(1, max_duration)
    first_t = float(enriched[0]["t"]) if enriched else 0.0
    observed_span = max(0.0, last_t - first_t) if enriched else 0.0
    if continuous:
        time_coverage = round(min(1.0, (controlled + sum(g["end"] - g["start"] for g in dead)) / max(1, at or 1)), 4)
    else:
        time_coverage = round(min(1.0, observed_span / duration), 4)
    return {
        "at": at,
        "score": score,
        "score_basis": "observed_prefix",
        "official_score": official_score,
        "shootout_score": shootout_score,
        "goals": goals,
        "owner": owner,
        "holder": holder,
        "ball": list(ball) if ball is not None else None,
        "events": enriched,
        "intervals": intervals,
        "possessions": possessions,
        "unobserved_intervals": unobserved,
        "dead_intervals": dead,
        "coverage": {
            "format_seconds": max_duration,
            "observed_start": first_t if enriched else None,
            "observed_end": last_t if enriched else None,
            "observed_span_seconds": round(observed_span, 2),
            "controlled_seconds": round(controlled, 2),
            "unobserved_seconds": round(sum(g["end"] - g["start"] for g in unobserved), 2),
            "continuous": bool(continuous),
            "time_coverage": time_coverage,
            "event_coverage": 1.0 if continuous else None,
            "event_coverage_status": "complete" if continuous else "unknown",
            "event_count": len(enriched),
            "score_status": "partial_prefix" if not continuous else ("complete" if ended or at >= max_duration else "prefix"),
        },
        "team_names": dict(team_names),
        "coordinate_frame": frame,
        "team_players": (
            {k: list(v) for k, v in PLAYERS.items()} if is_synthetic else _team_players(enriched)
        ),
        "ended": ended,
    }


def _team_players(events: list[dict]) -> dict[str, list[str]]:
    players: dict[str, list[str]] = {"H": [], "N": []}
    for e in events:
        team = e.get("team")
        if team not in players:
            players[team] = []
        for pid in (e.get("actor"), e.get("receiver")):
            if pid and pid not in players[team]:
                players[team].append(pid)
    if not players["H"]:
        players["H"] = list(PLAYERS["H"])
    if not players["N"]:
        players["N"] = list(PLAYERS["N"])
    return players


def _window_assets(state: dict) -> dict:
    """Collect the window-independent metric assets.

    Entries, recovery-to-shot transitions and goal chains are properties of the
    event stream itself (a possession-level entry is de-duplicated globally, a
    transition is a temporal relation between two events). They are therefore
    computed once and filtered by window afterwards, so that every window
    flavour (previous/current/match or an arbitrary range) shares one formula.
    """
    events = state["events"]
    # End of a controlled possession is the next gain, goal or final whistle.
    entries, transition, gains = [], [], {}
    goal_chains_by_team: dict[str, list[list[str]]] = {"H": [], "N": []}
    goal_events_by_team: dict[str, list[dict]] = {"H": [], "N": []}
    seen_entries: set[tuple[str, int]] = set()
    for idx, e in enumerate(events):
        if e["kind"] == "recovery":
            gains[(e["team"], e["possession_id"])] = e
        if e["kind"] == "pass" and e.get("located"):
            ax_s = event_attacking_x(e, point="start")
            ax_e = event_attacking_x(e, point="end")
            if ax_s is not None and ax_e is not None and ax_s <= 70 < ax_e:
                key = e["team"], e["possession_id"]
                if key not in seen_entries:
                    entries.append(e)
                    seen_entries.add(key)
        if e["kind"] == "shot":
            gain = gains.get((e["team"], e["possession_id"]))
            if gain and 0 <= e["t"]-gain["t"] <= 10:
                transition.append({"shot": e, "gain": gain, "seconds": e["t"]-gain["t"]})
            if e["outcome"] in ("goal", "own_goal", "own_goal_for"):
                is_og = e["outcome"].startswith("own_goal")
                credited = e["team"] if e["outcome"] == "own_goal_for" else (
                    other(e["team"]) if is_og else e["team"]
                )
                if is_og:
                    chain = [e["id"]]
                    goal_chains_by_team[credited].append(chain)
                    goal_events_by_team[credited].append({"event": e, "chain": chain})
                    continue
                chain = []
                for before in reversed(events[:idx+1]):
                    if before["team"] != e["team"] or before["kind"] == "shot" and before is not e:
                        break
                    chain.append(before["id"])
                    if before["kind"] in ("recovery", "restart"):
                        break
                ordered_chain = list(reversed(chain))
                goal_chains_by_team[e["team"]].append(ordered_chain)
                goal_events_by_team[e["team"]].append({"event": e, "chain": ordered_chain})
    return {
        "entries": entries,
        "transition": transition,
        "goal_chains_by_team": goal_chains_by_team,
        "goal_events_by_team": goal_events_by_team,
    }


def _window_receipts(state: dict, name: str, start: float, end: float, assets: dict) -> dict[str, dict]:
    """Metric receipts for one explicit [start, end] second window.

    This is the single formula used by every window flavour: the registry's
    previous/current windows and any arbitrary range requested by the story
    engine or the agent tools.
    """
    receipts: dict[str, dict] = {}
    events = state["events"]
    entries = assets["entries"]
    transition = assets["transition"]
    goal_events_by_team = assets["goal_events_by_team"]

    def receipt(key: str, value: float | int | None, unit: str, sources: list[str], definition: str, **details) -> None:
        receipts[key] = {
            "id": key,
            "value": value,
            "unit": unit,
            "event_ids": sorted({str(s) for s in sources if s is not None}),
            "definition": definition,
            "status": details.pop("status", "ok" if value is not None else "unobserved"),
            **details,
        }

    window = [e for e in events if start < e["t"] <= end]
    # A window that contains no event at all was not observed: counting zero
    # shots in it would publish a measurement nobody made. A window that does
    # contain events but none of the counted kind is a genuine zero.
    window_observed = bool(window)
    durations = {t: 0 for t in TEAMS}
    sources = []
    for interval in state["intervals"]:
        duration = max(0, min(end, interval["end"])-max(start, interval["start"]))
        if duration:
            durations[interval["team"]] += duration
            sources.append(interval["event_id"])
    denominator = sum(durations.values())
    for team in TEAMS:
        receipt(
            f"{team}.possession.{name}",
            round(100*durations[team]/denominator, 2) if denominator else None,
            "%",
            sources,
            "Controlled seconds / controlled seconds of both teams; dead-ball time excluded.",
            numerator=durations[team],
            denominator=denominator,
            status="ok" if denominator else "unobserved",
            start=start,
            end=end,
        )
        shots = [e for e in window if e["team"] == team and e["kind"] == "shot"]
        crossing = [e for e in entries if e["team"] == team and start < e["t"] <= end]
        high = [
            e for e in window
            if e["kind"] == "recovery" and e["team"] == team and e.get("located")
            and (ax := event_attacking_x(e, point="start")) is not None and ax >= 70
        ]
        quick = [s for s in transition if s["shot"]["team"] == team and start < s["shot"]["t"] <= end]
        count_status = "ok" if window_observed else "unobserved"
        receipt(f"{team}.shots.{name}", len(shots) if window_observed else None, "shots", [e["id"] for e in shots], "All shot events, including saved shots and goals.", status=count_status, start=start, end=end)
        receipt(f"{team}.entries.{name}", len(crossing) if window_observed else None, "entries", [e["id"] for e in crossing], "First completed pass crossing attacking x=70m per possession; no tracking or xG.", status=count_status, start=start, end=end)
        receipt(f"{team}.high_recoveries.{name}", len(high) if window_observed else None, "recoveries", [e["id"] for e in high], "Opponent possession gained at attacking x >= 70m; not proof of pressing.", status=count_status, start=start, end=end)
        receipt(f"{team}.transition_shots.{name}", len(quick) if window_observed else None, "shots", [e["id"] for s in quick for e in (s["gain"], s["shot"])],
                "Shot <=10s after a recovery with no intervening loss; a temporal association, not causation.",
                chains=[{"event_ids": [s["gain"]["id"], s["shot"]["id"]], "seconds": s["seconds"]} for s in quick],
                status=count_status, start=start, end=end)
        window_goals = [
            g for g in goal_events_by_team[team]
            if start < g["event"]["t"] <= end
        ]
        goal_sources = [x for g in window_goals for x in g["chain"]]
        receipt(f"{team}.goals.{name}", len(window_goals) if window_observed else None, "goals", goal_sources,
                "Credited goals in the requested window; shootout goals excluded.",
                chains=[g["chain"] for g in window_goals], status=count_status, start=start, end=end)
    return receipts


def receipt_number(receipt: dict | None, default: float = 0.0) -> float:
    """Numeric value of a receipt, or `default` when the receipt holds no measurement.

    A receipt whose status is not "ok" carries `value: None` on purpose: the
    window was never observed, so there is no number to read. Internal
    branching may fall back to a default, but it must never mistake an
    unobserved receipt for a measured zero.
    """
    if not isinstance(receipt, dict):
        return default
    value = receipt.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return value


def metric_receipts(state: dict) -> dict[str, dict]:
    at = state["at"]
    assets = _window_assets(state)
    receipts: dict[str, dict] = {}
    for name, start, end in (("previous", max(0, at-360), max(0, at-180)), ("current", max(0, at-180), at)):
        receipts.update(_window_receipts(state, name, start, end, assets))
    # The match window is the same formula over the whole frozen prefix, so a
    # metric never has a window-specific variant with different semantics.
    receipts.update(_window_receipts(state, "match", 0, at, assets))
    return receipts


def metric_receipts_for_range(state: dict, start: float, end: float, name: str = "range") -> dict[str, dict]:
    """Metric receipts for an arbitrary [start, end] second range.

    Same formulas as the previous/current/match windows (see
    `_window_receipts`); only the interval boundaries differ. The recorded
    `start`/`end` are the real boundaries of the requested range.
    """
    assets = _window_assets(state)
    return _window_receipts(state, name, start, end, assets)


def both_team_receipts(state: dict) -> dict[str, dict]:
    """Ensure both H.goals.match and N.goals.match are always present for UI inspection."""
    receipts = dict(metric_receipts(state))
    if "N.goals.match" not in receipts:
        receipts["N.goals.match"] = {
            "id": "N.goals.match",
            "value": state["score"]["N"],
            "unit": "goals",
            "event_ids": [],
            "definition": "Northbridge goals and the uninterrupted on-ball event sequence ending in each goal.",
            "chains": [],
            "start": 0,
            "end": state["at"],
        }
    return receipts


@dataclass(frozen=True)
class SnapshotContext:
    match_id: str
    scenario: str
    seed: int
    source_data_digest: str
    as_of: int
    metric_version: str = "football-v2"
    schema_version: str = "evidence-v2"
    match_clock_basis: str = "match_elapsed"
    data_version: str = "1.0.0"
    format_seconds: int = 720
    coordinate_frame: str = "fixed"
    continuous_coverage: bool = False
    score_basis: str = "observed_prefix"
    observed_end: float = 0.0
    event_count: int = 0


@dataclass(frozen=True)
class Snapshot:
    id: str
    canonical: str

    @property
    def data(self) -> dict:
        # Callers receive a copy; tools cannot mutate the frozen source.
        return json.loads(self.canonical)

    @property
    def context(self) -> SnapshotContext | None:
        d = self.data
        if d.get("schema") == "evidence-v2":
            return SnapshotContext(
                match_id=d.get("match_id", ""),
                scenario=d.get("scenario", "default"),
                seed=d.get("seed", 17),
                source_data_digest=d.get("source_data_digest", ""),
                as_of=d.get("as_of", 0),
                metric_version=d.get("metric_version", "football-v2"),
                schema_version=d.get("schema", "evidence-v2"),
                match_clock_basis=d.get("match_clock_basis", "match_elapsed"),
                data_version=d.get("data_version", "1.0.0"),
                format_seconds=d.get("format_seconds", 720),
                coordinate_frame=d.get("coordinate_frame", "fixed"),
                continuous_coverage=bool(d.get("coverage", {}).get("continuous", False)),
                score_basis=d.get("score_basis", "observed_prefix"),
                observed_end=float(d.get("coverage", {}).get("observed_end") or 0.0),
                event_count=int(d.get("coverage", {}).get("event_count") or 0),
            )
        return None


def freeze(
    events: tuple[Event, ...] | list[Any],
    at: int,
    seed: int = 17,
    match_id: str | None = None,
    scenario: str = "default",
    data_version: str = "1.0.0",
    clock_basis: str = "match_elapsed",
    teams: dict[str, str] | None = None,
    format_seconds: int = 720,
    limitations: list[str] | None = None,
    *,
    team_map: dict[str, str] | None = None,
    home_team_id: str | None = None,
    away_team_id: str | None = None,
    coordinate_frame: Literal["fixed", "team_relative"] | None = None,
    continuous_coverage: bool | None = None,
    official_score: dict[str, int] | None = None,
    dataset_revision: str | None = None,
    completeness: dict | None = None,
) -> Snapshot:
    is_syn = (match_id is None or match_id.startswith("syn_")) and scenario in SCENARIOS
    max_d = format_seconds if format_seconds else (720 if is_syn else 5400)
    if at > max_d:
        raise ValueError("clock_out_of_bounds")
    state = reduce_match(
        events,
        at,
        max_duration=max_d,
        is_synthetic=is_syn,
        team_names=teams,
        team_map=team_map,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        coordinate_frame=coordinate_frame,
        continuous_coverage=continuous_coverage if continuous_coverage is not None else is_syn,
        official_score=official_score,
    )
    receipts = metric_receipts(state)
    actual_teams = teams or state.get("team_names") or TEAMS
    candidate = "Compare Harbor's possession, shots and entries in the two windows. Look for contrary evidence."
    if receipt_number(receipts.get("H.transition_shots.current")) >= 2:
        candidate = "Investigate what followed Harbor's recoveries. Inspect the linked timings and sample size."
    if state["score"].get("H", 0) > 0:
        candidate = "Explain the goal's recorded on-ball sequence. Separate observed sequence from tactical cause."

    # Backward-compatible canonical hash for default synthetic match:
    if match_id is None or (match_id == f"harbor-northbridge-{seed}" and scenario == "default" and seed == 17):
        content = {
            "schema": "evidence-v1",
            "metric_version": "football-v1",
            "generator_version": "controlled-r01-3",
            "match_id": f"harbor-northbridge-{seed}",
            "seed": seed,
            "format_seconds": 720,
            "as_of": at,
            "teams": TEAMS,
            "score": state["score"],
            "score_basis": state["score_basis"],
            "dataset_revision": dataset_revision,
            "official_score": state["official_score"],
            "shootout_score": state["shootout_score"],
            "coverage": state["coverage"],
            "coordinate_frame": state["coordinate_frame"],
            "candidate": candidate,
            "receipts": receipts,
            "events": state["events"],
            "intervals": state["intervals"],
            "possessions": state["possessions"],
            "unobserved_intervals": state["unobserved_intervals"],
            "dead_intervals": state["dead_intervals"],
            **({"completeness": completeness} if completeness is not None else {}),
            "limitations": [
                "Synthetic 12-minute demonstration match.",
                "On-ball events only; no off-ball tracking, pressure, xG or coaching intent."
            ],
        }
    else:
        # Versioned Snapshot Context (P0.4)
        ev_ids = [
            getattr(e, "id", None) or getattr(e, "event_id", None) or (e.get("id") if isinstance(e, dict) else "")
            for e in events
        ]
        source_digest = hashlib.sha256("".join(str(i) for i in ev_ids).encode()).hexdigest()[:16]
        content = {
            "schema": "evidence-v2",
            "metric_version": "football-v2",
            "generator_version": "controlled-r02-1",
            "match_id": match_id,
            "scenario": scenario,
            "seed": seed,
            "source_data_digest": dataset_revision or source_digest,
            "dataset_revision": dataset_revision,
            "data_version": data_version,
            "match_clock_basis": clock_basis,
            "format_seconds": max_d,
            "as_of": at,
            "teams": actual_teams,
            "score": state["score"],
            "score_basis": state["score_basis"],
            "dataset_revision": dataset_revision,
            "official_score": state["official_score"],
            "shootout_score": state["shootout_score"],
            "coverage": state["coverage"],
            "coordinate_frame": state["coordinate_frame"],
            "candidate": candidate,
            "receipts": receipts,
            "events": state["events"],
            "intervals": state["intervals"],
            "possessions": state["possessions"],
            "unobserved_intervals": state["unobserved_intervals"],
            "dead_intervals": state["dead_intervals"],
            **({"completeness": completeness} if completeness is not None else {}),
            "limitations": limitations or (
                [
                    "Synthetic 12-minute demonstration match.",
                    "On-ball events only; no off-ball tracking, pressure, xG or coaching intent."
                ]
                if match_id.startswith("syn_") else
                [
                    "Historical / partial event sequence; coverage level bounded.",
                    "On-ball events only; no off-ball tracking, pressure, xG or coaching intent."
                ]
            ),
        }
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return Snapshot("snap-"+hashlib.sha256(canonical.encode()).hexdigest()[:20], canonical)


def tool_evidence(snapshot: Snapshot, focus_team: Literal["H", "N"] | str = "H") -> dict:
    data = snapshot.data
    # P0.10: Support dual-team visibility for both Analyst and Verifier
    receipts = dict(data.get("receipts", {}))
    relevant = set()
    for v in receipts.values():
        if isinstance(v, dict) and "possession" not in v.get("id", ""):
            relevant.update(v.get("event_ids", []))
    events = data.get("events", [])
    return {
        "snapshot_id": snapshot.id,
        "focus_team": focus_team,
        **{k: data[k] for k in ("as_of", "teams", "score", "candidate", "limitations") if k in data},
        "receipts": receipts,
        "selected_events": [e for e in events if e.get("id") in relevant],
    }


def detect_moments(state: dict) -> list[dict]:
    """Detect candidate tactical moments dynamically from reduced match state."""
    at, events = state["at"], state["events"]
    receipts = metric_receipts(state)
    moments = []

    team_names = state.get("team_names") or TEAMS
    # Two complete comparison windows are required; timestamps are detection
    # times, never chapter timestamps or an assumed future final whistle.
    def observed(key: str) -> float | int | None:
        """Receipt value only when the window it was measured over was observed.

        An unobserved window yields no number at all, so a moment must never
        claim "shots: zero" for a window nobody recorded.
        """
        receipt = receipts.get(key)
        if not isinstance(receipt, dict) or receipt.get("status") != "ok":
            return None
        value = receipt.get("value")
        return value if isinstance(value, (int, float)) else None

    for team in ("H", "N"):
        t_name = team_names.get(team, TEAMS[team]).split()[0]
        suffix = "" if team == "H" else "-n"
        if at >= 360:
            pos_curr = observed(f"{team}.possession.current")
            pos_prev = observed(f"{team}.possession.previous")
            shots_curr = observed(f"{team}.shots.current")
            entries_curr = observed(f"{team}.entries.current")
            if (
                pos_curr is not None and pos_prev is not None
                and pos_curr > pos_prev and shots_curr == 0 and entries_curr == 0
            ):
                moments.append({
                    "id": f"moment-possession{suffix}",
                    "team": team,
                    "chapter_id": "A",
                    "at": at,
                    "window": [max(0, at - 360), at],
                    "trigger_type": "possession_divergence",
                    "badge": "TACTICAL DIVERGENCE",
                    "title": "Possession Without Penetration" if team == "H" else f"{t_name} Possession Without Penetration",
                    "question": "Has more of the ball meant more threat?" if team == "H" else f"Has {t_name}'s extra possession created threat?",
                    "assertion": "possession_without_penetration",
                    "summary": f"Controlled possession: {pos_prev:g}% → {pos_curr:g}%. Current shots and attacking-third entries: zero.",
                    "priority": 3,
                    "metric_keys": [f"{team}.possession.current", f"{team}.possession.previous", f"{team}.shots.current", f"{team}.entries.current"],
                })

        # Association question, not a prescribed answer. Align with gate support.
        if at >= 180:
            high_rec = observed(f"{team}.high_recoveries.current")
            trans_shots = observed(f"{team}.transition_shots.current")
            if high_rec is not None and trans_shots is not None and (
                high_rec >= 2 and trans_shots >= 2 or (team == "N" and trans_shots >= 2)
            ):
                moments.append({
                    "id": f"moment-transition{suffix}",
                    "team": team,
                    "chapter_id": "B",
                    "at": at,
                    "window": [max(0, at - 180), at],
                    "trigger_type": "transition_burst",
                    "badge": "TRANSITION BURST",
                    "title": "High Recovery to Shot Chains" if team == "H" else f"{t_name} Counterattack Chains",
                    "question": f"What followed {t_name}'s high recoveries?" if team == "H" else f"What followed {t_name}'s ball recoveries?",
                    "assertion": "recoveries_followed_by_shots",
                    "summary": f"{t_name} won {int(high_rec)} high recoveries leading to {int(trans_shots)} quick transition shots.",
                    "priority": 2,
                    "metric_keys": [f"{team}.high_recoveries.current", f"{team}.transition_shots.current"],
                })

        shots_curr = observed(f"{team}.shots.current")
        shots_prev = observed(f"{team}.shots.previous")
        entries_curr = observed(f"{team}.entries.current")
        entries_prev = observed(f"{team}.entries.previous")
        if (
            at >= 360
            and shots_curr is not None and shots_prev is not None
            and entries_curr is not None and entries_prev is not None
            and shots_curr >= 2 and shots_curr > shots_prev and entries_curr > entries_prev
        ):
            moments.append({
                "id": f"moment-activity{suffix}",
                "team": team,
                "chapter_id": "B",
                "at": at,
                "window": [max(0, at - 360), at],
                "trigger_type": "attacking_surge",
                "badge": "ATTACKING ACTIVITY",
                "title": "Attacking activity changed" if team == "H" else f"{t_name} attacking surge",
                "question": f"What changed in {t_name}'s shot and entry counts?",
                "assertion": "attacking_surge",
                "summary": "Both shot attempts and attacking-third entries increased against the preceding window.",
                "priority": 4,
                "metric_keys": [f"{team}.{metric}.{period}" for metric in ("shots", "entries") for period in ("previous", "current")],
            })

    # T3: Breakthrough Goal Sequences (evaluated for all recorded goals)
    goals = [e for e in events if e.get("kind") == "shot" and e.get("outcome") in ("goal", "own_goal")]
    for g in goals:
        g_team = other(g["team"]) if g.get("outcome") == "own_goal" else g["team"]
        scorer = g.get("actor_name") or g.get("actor") or "Unknown player"
        moments.append({
            "id": "moment-goal-" + g["id"],
            "team": g_team,
            "chapter_id": "C",
            "at": g["t"],
            "window": [max(0, g["t"] - 60), g["t"]],
            "trigger_type": "goal_breakthrough",
            "badge": "GOAL BREAKTHROUGH",
            "title": f"{team_names.get(g_team, g_team)} goal · {scorer}",
            "question": "Which sequence ended with the breakthrough goal?",
            "assertion": "goal_sequence",
            "summary": "A scoring shot is recorded. Inspect the possession chain leading to it.",
            "priority": 1,
            "metric_keys": [f"{g_team}.goals.match"],
        })

    return moments


def channel_name(team: str, y: float) -> str:
    """Classify y coordinate into left, center, or right channel relative to attack direction."""
    if 22.67 <= y <= 45.33:
        return "center"
    if team == "H":
        return "left" if y > 45.33 else "right"
    else:
        return "left" if y < 22.67 else "right"


def event_attacking_x(event: dict, team: str | None = None, point: str = "start") -> float | None:
    """Longitudinal coordinate in the event's own attacking frame.

    Synthetic events use a fixed physical frame (H attacks right, N left);
    normalized provider events are already standardized to the attacking
    team's direction at every event, including after half-time.
    """
    coords = event.get(point)
    if not coords or coords[0] is None:
        return None
    team = team or event.get("team", "H")
    if event.get("coordinate_frame") == "team_relative":
        return float(coords[0])
    return attack_x(team, float(coords[0]))


def event_channel(event: dict, team: str | None = None, point: str = "start") -> str | None:
    coords = event.get(point)
    if not coords or coords[1] is None:
        return None
    team = team or event.get("team", "H")
    y = float(coords[1])
    if 22.67 <= y <= 45.33:
        return "center"
    if event.get("coordinate_frame") == "team_relative":
        return "left" if y > 45.33 else "right"
    return channel_name(team, y)


def build_sequences(state: dict, team: str | None = None) -> list[dict]:
    """Organize discrete on-ball events into continuous possession sequences with step details."""
    events = state["events"]
    grouped: dict[int, list[dict]] = {}
    for e in events:
        if e["kind"] == "end":
            continue
        if e.get("possession_id") is None:
            continue
        grouped.setdefault(e["possession_id"], []).append(e)

    sequences: list[dict] = []
    for pid, seq_events in sorted(grouped.items()):
        if not seq_events:
            continue
        seq_team = seq_events[0]["team"]
        if team in ("H", "N") and seq_team != team:
            continue
        same_team_events = [e for e in seq_events if e["team"] == seq_team]
        if not same_team_events:
            continue
        passes = [e for e in same_team_events if e["kind"] == "pass" and e.get("located")]
        prog_dist = 0.0
        for e in passes:
            ax_s = event_attacking_x(e, point="start")
            ax_e = event_attacking_x(e, point="end")
            if ax_s is not None and ax_e is not None:
                prog_dist += max(0.0, ax_e - ax_s)
        entered_final_third = any(
            (ax_s := event_attacking_x(e, point="start")) is not None
            and (ax_e := event_attacking_x(e, point="end")) is not None
            and ax_s <= 70 < ax_e
            for e in passes
        )
        last_ev = same_team_events[-1]
        outcome = (
            "goal"
            if last_ev["kind"] == "shot" and last_ev["outcome"] == "goal"
            else "own_goal"
            if last_ev["kind"] == "shot" and last_ev["outcome"] == "own_goal"
            else "shot_saved"
            if last_ev["kind"] == "shot"
            else "in_play"
            if last_ev is events[-1]
            else "turnover"
        )
        players_involved = []
        for e in same_team_events:
            for p in (e["actor"], e.get("receiver")):
                if p and p not in players_involved:
                    players_involved.append(p)

        start_pt = same_team_events[0]["start"]
        end_pt = last_ev["end"]
        ax_start = event_attacking_x(same_team_events[0], seq_team, point="start")
        ax_end = event_attacking_x(last_ev, seq_team, point="end")
        territory_gained = (
            round(ax_end - ax_start, 1) if ax_start is not None and ax_end is not None else None
        )
        event_details: list[dict] = []
        for idx, e in enumerate(same_team_events):
            ax_s = event_attacking_x(e, seq_team, point="start")
            ax_e = event_attacking_x(e, seq_team, point="end")
            event_details.append({
                "seq_step": idx + 1,
                "id": e["id"],
                "kind": e["kind"],
                "team": seq_team,
                "actor": e["actor"],
                "actor_name": e.get("actor_name") or PLAYERS.get(seq_team, {}).get(e["actor"], e["actor"]),
                "receiver": e.get("receiver"),
                "receiver_name": e.get("receiver"),
                "start": e["start"],
                "end": e["end"],
                "outcome": e.get("outcome", "success"),
                "t": e["t"],
                "gain_m": round(ax_e - ax_s, 1) if ax_s is not None and ax_e is not None else None,
                "channel": event_channel(e, seq_team, point="start"),
            })
        events_detail = event_details

        sequences.append({
            "sequence_id": f"SEQ-{pid:03d}",
            "possession_id": pid,
            "team": seq_team,
            "coordinate_frame": state.get("coordinate_frame", "fixed"),
            "start_t": same_team_events[0]["t"],
            "end_t": last_ev["t"],
            "duration": max(0, last_ev["t"] - same_team_events[0]["t"]),
            "origin_kind": same_team_events[0]["kind"],
            "pass_count": len(passes),
            "progressive_distance": round(prog_dist, 1),
            "territory_gained": territory_gained,
            "start_coords": list(start_pt) if start_pt else None,
            "end_coords": list(end_pt) if end_pt else None,
            "entered_final_third": entered_final_third,
            "outcome": outcome,
            "players": players_involved,
            "event_ids": [e["id"] for e in same_team_events],
            "events_detail": events_detail,
        })
    return sequences


def build_tactical_explorer(state: dict, team: str = "H") -> dict:
    """Compute event-grounded passing network, progressive passes, recoveries, channels and zones."""
    team = "N" if team == "N" else "H"
    all_team_events = [e for e in state["events"] if e["team"] == team and e["kind"] != "end"]
    events = [e for e in all_team_events if e.get("located")]
    roster = list((state.get("team_players") or {}).get(team) or PLAYERS.get(team, {}))
    node_touches: dict[str, list[tuple[float, float]]] = {p: [] for p in roster}
    edges_map: dict[tuple[str, str], dict] = {}
    progressive_passes: list[dict] = []
    recoveries: list[dict] = []
    zone_counts = {"defensive_third": 0, "middle_third": 0, "attacking_third": 0}
    channel_counts = {"left": 0, "center": 0, "right": 0}
    attacking_channel_counts = {"left": 0, "center": 0, "right": 0}
    frame = state.get("coordinate_frame", "fixed")

    def add_touch(player: str | None, point: list[float] | None) -> None:
        if player and point and player in node_touches:
            node_touches[player].append((float(point[0]), float(point[1])))

    for e in events:
        ax_start = event_attacking_x(e, team, point="start")
        ch_start = event_channel(e, team, point="start")
        if ax_start is None or ch_start is None:
            continue
        channel_counts[ch_start] += 1

        if ax_start < 35:
            zone_counts["defensive_third"] += 1
        elif ax_start <= 70:
            zone_counts["middle_third"] += 1
        else:
            zone_counts["attacking_third"] += 1
            attacking_channel_counts[ch_start] += 1

        add_touch(e.get("actor"), e.get("start"))
        if e["kind"] == "pass" and e.get("receiver"):
            add_touch(e.get("receiver"), e.get("end"))
            pair = (e["actor"], e["receiver"])
            edge = edges_map.setdefault(pair, {"from": pair[0], "to": pair[1], "count": 0, "event_ids": []})
            edge["count"] += 1
            edge["event_ids"].append(e["id"])
            ax_end = event_attacking_x(e, team, point="end")
            if ax_end is None:
                continue
            gain_m = round(ax_end - ax_start, 1)
            is_entry = ax_start <= 70 < ax_end
            if gain_m >= 12.0 or is_entry:
                progressive_passes.append({
                    "id": e["id"],
                    "t": e["t"],
                    "actor": e["actor"],
                    "actor_name": e.get("actor_name") or e["actor"],
                    "receiver": e["receiver"],
                    "receiver_name": e["receiver"],
                    "start": e["start"],
                    "end": e["end"],
                    "gain_m": gain_m,
                    "is_entry": is_entry,
                    "channel": ch_start,
                    "entry_channel": event_channel(e, team, point="end") if is_entry else None,
                })
        elif e["kind"] == "recovery":
            recoveries.append({
                "id": e["id"],
                "t": e["t"],
                "actor": e["actor"],
                "actor_name": e.get("actor_name") or e["actor"],
                "location": e["start"],
                "attack_x": round(ax_start, 1),
                "is_high": ax_start >= 70,
                "channel": ch_start,
            })

    nodes = []
    for pid in roster:
        pts = node_touches[pid]
        avg_x = round(sum(p[0] for p in pts) / len(pts), 1) if pts else None
        avg_y = round(sum(p[1] for p in pts) / len(pts), 1) if pts else None
        nodes.append({
            "player_id": pid,
            "name": pid if frame == "team_relative" else PLAYERS.get(team, {}).get(pid, pid),
            "touches": len(pts),
            "avg_x": avg_x,
            "avg_y": avg_y,
        })

    total_ev = max(1, len(events))
    zones = {k: round(100.0 * v / total_ev, 1) for k, v in zone_counts.items()}
    channels = {
        "left": round(100.0 * channel_counts["left"] / total_ev, 1),
        "center": round(100.0 * channel_counts["center"] / total_ev, 1),
        "right": round(100.0 * channel_counts["right"] / total_ev, 1),
        "left_count": channel_counts["left"],
        "center_count": channel_counts["center"],
        "right_count": channel_counts["right"],
    }
    total_att = max(1, sum(attacking_channel_counts.values()))
    attacking_channels = {
        "left": round(100.0 * attacking_channel_counts["left"] / total_att, 1),
        "center": round(100.0 * attacking_channel_counts["center"] / total_att, 1),
        "right": round(100.0 * attacking_channel_counts["right"] / total_att, 1),
        "left_count": attacking_channel_counts["left"],
        "center_count": attacking_channel_counts["center"],
        "right_count": attacking_channel_counts["right"],
    }
    final_third_entries = [p for p in progressive_passes if p["is_entry"]]

    territorial_progression = {
        "total_progressive_passes": len(progressive_passes),
        "final_third_entries_count": len(final_third_entries),
        "avg_progressive_gain_m": round(sum(p["gain_m"] for p in progressive_passes) / len(progressive_passes), 1) if progressive_passes else 0.0,
        "high_recoveries_count": len([r for r in recoveries if r["is_high"]]),
        "total_recoveries_count": len(recoveries),
        "high_recovery_threshold_x": 70.0 if (frame == "team_relative" or team == "H") else 35.0,
    }

    # 9-zone spatial distribution (3 thirds x 3 channels on pitch)
    zone_cells = []
    cell_specs = [
        (0, (0.0, 35.0), 0, (0.0, 22.67)),
        (0, (0.0, 35.0), 1, (22.67, 45.33)),
        (0, (0.0, 35.0), 2, (45.33, 68.0)),
        (1, (35.0, 70.0), 0, (0.0, 22.67)),
        (1, (35.0, 70.0), 1, (22.67, 45.33)),
        (1, (35.0, 70.0), 2, (45.33, 68.0)),
        (2, (70.0, 105.0), 0, (0.0, 22.67)),
        (2, (70.0, 105.0), 1, (22.67, 45.33)),
        (2, (70.0, 105.0), 2, (45.33, 68.0)),
    ]
    for x_idx, (x_min, x_max), y_idx, (y_min, y_max) in cell_specs:
        y_mid = (y_min + y_max) / 2
        if frame == "team_relative":
            ch = "center" if 22.67 <= y_mid <= 45.33 else ("left" if y_mid > 45.33 else "right")
        else:
            ch = channel_name(team, y_mid)
        if frame == "team_relative" or team == "H":
            th = "defensive" if x_idx == 0 else ("middle" if x_idx == 1 else "attacking")
        else:
            th = "attacking" if x_idx == 0 else ("middle" if x_idx == 1 else "defensive")

        c_events = [
            e for e in events
            if x_min <= e["start"][0] <= x_max and y_min <= e["start"][1] <= y_max
        ]
        count = len(c_events)
        pct = round(100.0 * count / total_ev, 1)
        name = f"{th.capitalize()} {ch.capitalize()}"
        zone_cells.append({
            "cell_id": f"zone-{x_idx}-{y_idx}",
            "name": name,
            "third": th,
            "channel": ch,
            "x_min": x_min,
            "x_max": x_max,
            "y_min": y_min,
            "y_max": y_max,
            "count": count,
            "percentage": pct,
            "event_ids": [e["id"] for e in c_events],
        })

    return {
        "team": team,
        "team_name": (state.get("team_names") or TEAMS).get(team, team),
        "attack_direction": "forward" if frame == "team_relative" else ("right" if team == "H" else "left"),
        "nodes": nodes,
        "edges": list(edges_map.values()),
        "progressive_passes": progressive_passes,
        "final_third_entries": final_third_entries,
        "recoveries": recoveries,
        "zones": zones,
        "channels": channels,
        "attacking_channels": attacking_channels,
        "zone_cells": zone_cells,
        "territorial_progression": territorial_progression,
        "disclaimer": "Derived strictly from recorded on-ball events; does not represent off-ball formation or pitch control.",
    }


def build_player_spotlight(state: dict, team: str | None = None) -> list[dict]:
    """Observable on-ball player contributions with no subjective rating formulas."""
    sequences = build_sequences(state)
    seq_by_player: dict[str, list[str]] = {}
    for seq in sequences:
        for pid in seq["players"]:
            seq_by_player.setdefault(pid, []).append(seq["sequence_id"])

    spotlight = []
    teams = [team] if team in ("H", "N") else ["H", "N"]
    team_names = state.get("team_names") or TEAMS
    rosters = state.get("team_players") or PLAYERS
    for t_code in teams:
        for pid in rosters.get(t_code) or []:
            actor_events = [e for e in state["events"] if e["team"] == t_code and e["actor"] == pid and e["kind"] != "end"]
            passes = [e for e in actor_events if e["kind"] == "pass" and e.get("located")]
            prog_passes, entries = [], []
            prog_dist = 0.0
            for e in passes:
                ax_s = event_attacking_x(e, t_code, point="start")
                ax_e = event_attacking_x(e, t_code, point="end")
                if ax_s is None or ax_e is None:
                    continue
                if ax_e - ax_s >= 12.0 or ax_s <= 70 < ax_e:
                    prog_passes.append(e)
                if ax_s <= 70 < ax_e:
                    entries.append(e)
                prog_dist += max(0.0, ax_e - ax_s)
            recs = [e for e in actor_events if e["kind"] == "recovery"]
            shots = [e for e in actor_events if e["kind"] == "shot"]
            goals = [e for e in shots if e["outcome"] == "goal"]
            total_touches = len(actor_events)
            located_touches = [e for e in actor_events if e.get("located")]
            attack_coords = [
                ax for e in located_touches
                if (ax := event_attacking_x(e, t_code, point="start")) is not None
            ]
            avg_x_pos = sum(attack_coords) / len(attack_coords) if attack_coords else None
            cohort = (
                "Unknown"
                if avg_x_pos is None
                else "Forward" if avg_x_pos > 72.0 else ("Midfielder" if avg_x_pos >= 38.0 else "Defender")
            )
            spotlight.append({
                "player_id": pid,
                "name": pid if state.get("coordinate_frame") == "team_relative" else PLAYERS.get(t_code, {}).get(pid, pid),
                "team": t_code,
                "team_name": team_names.get(t_code, t_code),
                "touches": total_touches,
                "position_cohort": cohort,
                "sample_sufficiency": "sufficient" if total_touches >= 10 else "low_sample_uncalibrated",
                "percentile_disclaimer": "单场小样本绝对计数，不换算全联盟位置百分位排名以防小样本方差失真。",
                "passes": len(passes),
                "progressive_passes": len(prog_passes),
                "progressive_distance": round(prog_dist, 1),
                "final_third_entries": len(entries),
                "recoveries": len(recs),
                "shots": len(shots),
                "goals": len(goals),
                "sequences_involved": len(seq_by_player.get(pid, [])),
                "touch_points": [e["start"] for e in located_touches],
                "progressive_pass_ids": [e["id"] for e in prog_passes],
                "recovery_ids": [e["id"] for e in recs],
                "event_ids": [e["id"] for e in actor_events],
            })
    return spotlight


def compare_windows(
    events: tuple[Event, ...] | list[Event] | list[dict] | dict,
    w1_start: int,
    w1_end: int,
    w2_start: int,
    w2_end: int,
    team: str = "H",
) -> dict:
    """Compare team tactical metrics between two arbitrary legal time windows.

    Returns structured metrics, deltas, denominators, and insufficient sample warnings.
    """
    team = "N" if team == "N" else "H"
    max_t = max(w1_end, w2_end, 1)

    if isinstance(events, dict) and "intervals" in events:
        state = events
    elif isinstance(events, (tuple, list)) and events and not isinstance(events[0], dict):
        state = reduce_match(tuple(events), max_t)
    elif isinstance(events, (tuple, list)) and events and isinstance(events[0], dict):
        raw = tuple(Event(**e) for e in events)
        state = reduce_match(raw, max_t)
    else:
        state = reduce_match(generate_match(), max_t)

    all_evs = state["events"]

    def compute_window_stats(start: int, end: int) -> dict:
        duration = max(0, end - start)
        window_events = [e for e in all_evs if start < e["t"] <= end]
        durations = {"H": 0, "N": 0}
        for interval in state["intervals"]:
            d = max(0, min(end, interval["end"]) - max(start, interval["start"]))
            if d:
                durations[interval["team"]] += d
        total_controlled = sum(durations.values())
        team_controlled = durations[team]
        possession_pct = round(100 * team_controlled / total_controlled, 2) if total_controlled else 0.0

        passes = [e for e in window_events if e["team"] == team and e["kind"] == "pass" and e.get("located")]
        prog_passes, entries = [], []
        for e in passes:
            ax_s = event_attacking_x(e, team, point="start")
            ax_e = event_attacking_x(e, team, point="end")
            if ax_s is None or ax_e is None:
                continue
            if ax_e - ax_s >= 12.0 or ax_s <= 70 < ax_e:
                prog_passes.append(e)
            if ax_s <= 70 < ax_e:
                entries.append(e)
        shots = [e for e in window_events if e["team"] == team and e["kind"] == "shot"]
        goals = [e for e in shots if e["outcome"] == "goal"]
        high_recs = [
            e for e in window_events
            if e["team"] == team and e["kind"] == "recovery" and e.get("located")
            and (ax := event_attacking_x(e, team, point="start")) is not None and ax >= 70
        ]

        warnings = []
        if duration < 60:
            warnings.append("short_window_duration")
        if total_controlled < 30:
            warnings.append("insufficient_controlled_seconds")
        if len(window_events) < 5:
            warnings.append("low_event_sample")

        return {
            "start": start,
            "end": end,
            "duration": duration,
            "team": team,
            "total_controlled_seconds": total_controlled,
            "team_controlled_seconds": team_controlled,
            "possession_pct": possession_pct,
            "passes_completed": len(passes),
            "progressive_passes": len(prog_passes),
            "final_third_entries": len(entries),
            "high_recoveries": len(high_recs),
            "shots": len(shots),
            "goals": len(goals),
            "warnings": warnings,
        }

    w1 = compute_window_stats(w1_start, w1_end)
    w2 = compute_window_stats(w2_start, w2_end)

    deltas = {
        "possession_pct": round(w2["possession_pct"] - w1["possession_pct"], 2),
        "passes_completed": w2["passes_completed"] - w1["passes_completed"],
        "progressive_passes": w2["progressive_passes"] - w1["progressive_passes"],
        "final_third_entries": w2["final_third_entries"] - w1["final_third_entries"],
        "high_recoveries": w2["high_recoveries"] - w1["high_recoveries"],
        "shots": w2["shots"] - w1["shots"],
        "goals": w2["goals"] - w1["goals"],
    }

    return {
        "team": team,
        "team_name": (state.get("team_names") or TEAMS).get(team, team),
        "window_1": w1,
        "window_2": w2,
        "deltas": deltas,
    }

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
    if scenario not in ("default", "stalemate"):
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
    add(720, "end", owner, holder, ball)
    reduce_match(tuple(result), 720)  # Generation and ingestion use the same legality checks.
    return tuple(result)


def reduce_match(events: tuple[Event, ...], at: int) -> dict:
    if not 0 <= at <= 720:
        raise ValueError("clock_out_of_bounds")
    owner = holder = None
    ball = (52.5, 34.0)
    score = {"H": 0, "N": 0}
    possession = 0
    last_t = -1
    pending_restart: str | None = "H"
    ended = False
    enriched, intervals = [], []
    for e in events:
        if e.t > at:
            break
        if e.seq != len(enriched)+1 or e.id != f"E{e.seq:04d}" or e.t <= last_t or ended:
            raise ValueError("event_order_or_id")
        for x, y in (e.start, e.end):
            if not (0 <= x <= 105 and 0 <= y <= 68):
                raise ValueError("coordinate_bounds")
        if e.actor not in PLAYERS[e.team] or e.start != ball:
            raise ValueError("actor_or_ball_discontinuity")
        if e.kind != "pass" and e.receiver is not None or e.kind != "shot" and e.outcome != "complete":
            raise ValueError("illegal_event_payload")
        if enriched and owner is not None:
            intervals.append({"start": last_t, "end": e.t, "team": owner,
                              "event_id": enriched[-1]["id"]})
        if pending_restart:
            if e.kind != "restart" or e.team != pending_restart or e.end != (52.5, 34.0):
                raise ValueError("illegal_restart")
            pending_restart = None
            owner, holder = e.team, e.actor
            possession += 1
        elif e.kind == "restart":
            raise ValueError("unexpected_restart")
        elif e.kind == "recovery":
            if e.team != other(owner) or e.start != e.end or e.receiver or e.outcome != "complete":
                raise ValueError("illegal_recovery")
            owner, holder = e.team, e.actor
            possession += 1
        else:
            if e.team != owner or e.actor != holder:
                raise ValueError("non_owner_action")
            if e.kind == "pass":
                if e.receiver not in PLAYERS[e.team] or e.receiver == holder or e.outcome != "complete":
                    raise ValueError("illegal_pass")
                holder = e.receiver
            elif e.kind == "shot":
                if e.outcome not in ("saved", "goal") or e.receiver:
                    raise ValueError("illegal_shot")
                if e.outcome == "goal":
                    if attack_x(e.team, e.end[0]) != 105 or abs(e.end[1]-34) > 3.66:
                        raise ValueError("goal_outside_goal_mouth")
                    score[e.team] += 1
                    pending_restart = other(e.team)
                    owner = holder = None
                else:
                    owner = other(e.team)
                    holder = owner+"1"
                    possession += 1
            elif e.kind == "end":
                if e.t != 720 or e.start != e.end:
                    raise ValueError("illegal_end")
                ended = True
        ball, last_t = e.end, e.t
        enriched.append({**e.model_dump(mode="json"), "possession_id": possession,
                         "owner_after": owner, "holder_after": holder})
    if enriched and last_t < at and owner:
        intervals.append({"start": last_t, "end": at, "team": owner, "event_id": enriched[-1]["id"]})
    return {"at": at, "score": score, "owner": owner, "holder": holder, "ball": list(ball),
            "events": enriched, "intervals": intervals, "ended": ended}


def metric_receipts(state: dict) -> dict[str, dict]:
    at, events = state["at"], state["events"]
    receipts: dict[str, dict] = {}
    # End of a controlled possession is the next gain, goal or final whistle.
    entries, transition, gains, goal_chains = [], [], {}, []
    seen_entries: set[tuple[str, int]] = set()
    for idx, e in enumerate(events):
        if e["kind"] == "recovery":
            gains[(e["team"], e["possession_id"])] = e
        if e["kind"] == "pass" and attack_x(e["team"], e["start"][0]) <= 70 < attack_x(e["team"], e["end"][0]):
            key = e["team"], e["possession_id"]
            if key not in seen_entries:
                entries.append(e)
                seen_entries.add(key)
        if e["kind"] == "shot":
            gain = gains.get((e["team"], e["possession_id"] - (1 if e["outcome"] == "saved" else 0)))
            if gain and 0 <= e["t"]-gain["t"] <= 10:
                transition.append({"shot": e, "gain": gain, "seconds": e["t"]-gain["t"]})
            if e["outcome"] == "goal":
                chain = []
                for before in reversed(events[:idx+1]):
                    if before["team"] != e["team"] or before["kind"] == "shot" and before is not e:
                        break
                    chain.append(before["id"])
                    if before["kind"] in ("recovery", "restart"):
                        break
                goal_chains.append(list(reversed(chain)))

    def receipt(key: str, value: float | int, unit: str, sources: list[str], definition: str, **details) -> None:
        receipts[key] = {"id": key, "value": value, "unit": unit, "event_ids": sorted(set(sources)),
                         "definition": definition, **details}

    for name, start, end in (("previous", max(0, at-360), max(0, at-180)), ("current", max(0, at-180), at)):
        window = [e for e in events if start < e["t"] <= end]
        durations = {t: 0 for t in TEAMS}
        sources = []
        for interval in state["intervals"]:
            duration = max(0, min(end, interval["end"])-max(start, interval["start"]))
            if duration:
                durations[interval["team"]] += duration
                sources.append(interval["event_id"])
        denominator = sum(durations.values())
        for team in TEAMS:
            receipt(f"{team}.possession.{name}", round(100*durations[team]/denominator, 2) if denominator else 0,
                    "%", sources, "Controlled seconds / controlled seconds of both teams; dead-ball time excluded.",
                    numerator=durations[team], denominator=denominator, start=start, end=end)
            shots = [e for e in window if e["team"] == team and e["kind"] == "shot"]
            crossing = [e for e in entries if e["team"] == team and start < e["t"] <= end]
            high = [e for e in window if e["kind"] == "recovery" and e["team"] == team and attack_x(team, e["start"][0]) >= 70]
            quick = [s for s in transition if s["shot"]["team"] == team and start < s["shot"]["t"] <= end]
            receipt(f"{team}.shots.{name}", len(shots), "shots", [e["id"] for e in shots], "All shot events, including saved shots and goals.", start=start, end=end)
            receipt(f"{team}.entries.{name}", len(crossing), "entries", [e["id"] for e in crossing], "First completed pass crossing attacking x=70m per possession; no tracking or xG.", start=start, end=end)
            receipt(f"{team}.high_recoveries.{name}", len(high), "recoveries", [e["id"] for e in high], "Opponent possession gained at attacking x >= 70m; not proof of pressing.", start=start, end=end)
            receipt(f"{team}.transition_shots.{name}", len(quick), "shots", [e["id"] for s in quick for e in (s["gain"], s["shot"])],
                    "Shot <=10s after a recovery with no intervening loss; a temporal association, not causation.",
                    chains=[{"event_ids": [s["gain"]["id"], s["shot"]["id"]], "seconds": s["seconds"]} for s in quick], start=start, end=end)
    goal_ids = [x for chain in goal_chains for x in chain]
    receipt("H.goals.match", state["score"]["H"], "goals", goal_ids,
            "Harbor goals and the uninterrupted on-ball event sequence ending in each goal.", chains=goal_chains, start=0, end=at)
    return receipts


@dataclass(frozen=True)
class Snapshot:
    id: str
    canonical: str

    @property
    def data(self) -> dict:
        # Callers receive a copy; tools cannot mutate the frozen source.
        return json.loads(self.canonical)


def freeze(events: tuple[Event, ...], at: int, seed: int = 17) -> Snapshot:
    state = reduce_match(events, at)
    receipts = metric_receipts(state)
    candidate = "Compare Harbor's possession, shots and entries in the two windows. Look for contrary evidence."
    if receipts["H.transition_shots.current"]["value"] >= 2:
        candidate = "Investigate what followed Harbor's recoveries. Inspect the linked timings and sample size."
    if state["score"]["H"]:
        candidate = "Explain the goal's recorded on-ball sequence. Separate observed sequence from tactical cause."
    content = {"schema": "evidence-v1", "metric_version": "football-v1", "generator_version": "controlled-r01-3", "match_id": f"harbor-northbridge-{seed}",
               "seed": seed, "format_seconds": 720, "as_of": at, "teams": TEAMS, "score": state["score"],
               "candidate": candidate, "receipts": receipts, "events": state["events"], "intervals": state["intervals"],
               "limitations": ["Synthetic 12-minute demonstration match.", "On-ball events only; no off-ball tracking, pressure, xG or coaching intent."]}
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return Snapshot("snap-"+hashlib.sha256(canonical.encode()).hexdigest()[:20], canonical)


def tool_evidence(snapshot: Snapshot) -> dict:
    data = snapshot.data
    receipts = {k: v for k, v in data["receipts"].items() if k.startswith("H.")}
    relevant = set()
    for v in receipts.values():
        if "possession" not in v["id"]:
            relevant.update(v["event_ids"])
    return {"snapshot_id": snapshot.id, **{k: data[k] for k in ("as_of", "teams", "score", "candidate", "limitations")},
            "receipts": receipts, "selected_events": [e for e in data["events"] if e["id"] in relevant]}


def detect_moments(state: dict) -> list[dict]:
    """Detect candidate tactical moments dynamically from reduced match state."""
    at, events = state["at"], state["events"]
    receipts = metric_receipts(state)
    moments = []

    # Two complete comparison windows are required; timestamps are detection
    # times, never chapter timestamps or an assumed future final whistle.
    if at >= 360:
        h_pos_curr = receipts.get("H.possession.current", {}).get("value", 0)
        h_pos_prev = receipts.get("H.possession.previous", {}).get("value", 0)
        h_shots_curr = receipts.get("H.shots.current", {}).get("value", 0)
        h_entries_curr = receipts.get("H.entries.current", {}).get("value", 0)
        if h_pos_curr > h_pos_prev and h_shots_curr <= 0 and h_entries_curr <= 0:
            moments.append({
                "id": "moment-possession",
                "chapter_id": "A",
                "at": at,
                "badge": "TACTICAL DIVERGENCE",
                "title": "Possession Without Penetration",
                "question": "Has more of the ball meant more threat?",
                "assertion": "possession_without_penetration",
                "summary": f"Controlled possession: {h_pos_prev:g}% → {h_pos_curr:g}%. Current shots and attacking-third entries: zero.",
                "priority": 3,
                "metric_keys": ["H.possession.current", "H.possession.previous", "H.shots.current", "H.entries.current"],
            })

    # Association question, not a prescribed answer. Align with gate support.
    if at >= 180:
        high_rec = receipts.get("H.high_recoveries.current", {}).get("value", 0)
        trans_shots = receipts.get("H.transition_shots.current", {}).get("value", 0)
        if high_rec >= 2 and trans_shots >= 2:
            moments.append({
                "id": "moment-transition",
                "chapter_id": "B",
                "at": at,
                "badge": "TRANSITION BURST",
                "title": "High Recovery to Shot Chains",
                "question": "What followed Harbor's high recoveries?",
                "assertion": "recoveries_followed_by_shots",
                "summary": f"Harbor won {int(high_rec)} high recoveries leading to {int(trans_shots)} quick transition shots.",
                "priority": 2,
                "metric_keys": ["H.high_recoveries.current", "H.transition_shots.current"],
            })

    if at >= 360 and receipts["H.shots.current"]["value"] >= 2 and all(
        receipts[f"H.{metric}.current"]["value"] > receipts[f"H.{metric}.previous"]["value"] for metric in ("shots", "entries")
    ):
        moments.append({"id": "moment-activity", "chapter_id": "B", "at": at, "badge": "ATTACKING ACTIVITY", "title": "Attacking activity changed", "question": "What changed in Harbor's shot and entry counts?", "summary": "Both shot attempts and attacking-third entries increased against the preceding window.", "priority": 4, "metric_keys": [f"H.{metric}.{period}" for metric in ("shots", "entries") for period in ("previous", "current")]})

    # T3: Breakthrough Goal Sequence (evaluated if goal present)
    goals = [e for e in events if e.get("kind") == "shot" and e.get("outcome") == "goal"]
    if goals:
        g = goals[0]
        moments.append({
            "id": "moment-goal-" + g["id"],
            "chapter_id": "C",
            "at": g["t"],
            "badge": "GOAL BREAKTHROUGH",
            "title": f"{TEAMS[g['team']]} goal · {PLAYERS[g['team']][g['actor']]}",
            "question": "Which sequence ended with the breakthrough goal?",
            "assertion": "goal_sequence",
            "summary": "A scoring shot is recorded. Inspect the possession chain leading to it.",
            "priority": 1,
            "metric_keys": ["H.goals.match"],
        })

    return moments

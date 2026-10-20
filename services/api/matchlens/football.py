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
    entries, transition, gains = [], [], {}
    goal_chains_by_team: dict[str, list[list[str]]] = {"H": [], "N": []}
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
                goal_chains_by_team[e["team"]].append(list(reversed(chain)))

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
    goal_chains = goal_chains_by_team["H"]
    goal_ids = [x for chain in goal_chains for x in chain]
    receipt("H.goals.match", state["score"]["H"], "goals", goal_ids,
            "Harbor goals and the uninterrupted on-ball event sequence ending in each goal.", chains=goal_chains, start=0, end=at)
    if state["score"]["N"] > 0:
        n_chains = goal_chains_by_team["N"]
        n_goal_ids = [x for chain in n_chains for x in chain]
        receipt("N.goals.match", state["score"]["N"], "goals", n_goal_ids,
                "Northbridge goals and the uninterrupted on-ball event sequence ending in each goal.", chains=n_chains, start=0, end=at)
    return receipts


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
    has_away_goals = "N.goals.match" in data["receipts"]
    receipts = {k: v for k, v in data["receipts"].items() if k.startswith("H.") or has_away_goals}
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
    for team in ("H", "N"):
        t_name = TEAMS[team].split()[0]
        suffix = "" if team == "H" else "-n"
        if at >= 360:
            pos_curr = receipts.get(f"{team}.possession.current", {}).get("value", 0)
            pos_prev = receipts.get(f"{team}.possession.previous", {}).get("value", 0)
            shots_curr = receipts.get(f"{team}.shots.current", {}).get("value", 0)
            entries_curr = receipts.get(f"{team}.entries.current", {}).get("value", 0)
            if pos_curr > pos_prev and shots_curr <= 0 and entries_curr <= 0:
                moments.append({
                    "id": f"moment-possession{suffix}",
                    "team": team,
                    "chapter_id": "A",
                    "at": at,
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
            high_rec = receipts.get(f"{team}.high_recoveries.current", {}).get("value", 0)
            trans_shots = receipts.get(f"{team}.transition_shots.current", {}).get("value", 0)
            if high_rec >= 2 and trans_shots >= 2 or (team == "N" and trans_shots >= 2):
                moments.append({
                    "id": f"moment-transition{suffix}",
                    "team": team,
                    "chapter_id": "B",
                    "at": at,
                    "badge": "TRANSITION BURST",
                    "title": "High Recovery to Shot Chains" if team == "H" else f"{t_name} Counterattack Chains",
                    "question": f"What followed {t_name}'s high recoveries?" if team == "H" else f"What followed {t_name}'s ball recoveries?",
                    "assertion": "recoveries_followed_by_shots",
                    "summary": f"{t_name} won {int(high_rec)} high recoveries leading to {int(trans_shots)} quick transition shots.",
                    "priority": 2,
                    "metric_keys": [f"{team}.high_recoveries.current", f"{team}.transition_shots.current"],
                })

        if at >= 360 and receipts[f"{team}.shots.current"]["value"] >= 2 and all(
            receipts[f"{team}.{metric}.current"]["value"] > receipts[f"{team}.{metric}.previous"]["value"] for metric in ("shots", "entries")
        ):
            moments.append({
                "id": f"moment-activity{suffix}",
                "team": team,
                "chapter_id": "B",
                "at": at,
                "badge": "ATTACKING ACTIVITY",
                "title": "Attacking activity changed" if team == "H" else f"{t_name} attacking surge",
                "question": f"What changed in {t_name}'s shot and entry counts?",
                "summary": "Both shot attempts and attacking-third entries increased against the preceding window.",
                "priority": 4,
                "metric_keys": [f"{team}.{metric}.{period}" for metric in ("shots", "entries") for period in ("previous", "current")],
            })

    # T3: Breakthrough Goal Sequences (evaluated for all recorded goals)
    goals = [e for e in events if e.get("kind") == "shot" and e.get("outcome") == "goal"]
    for g in goals:
        g_team = g["team"]
        moments.append({
            "id": "moment-goal-" + g["id"],
            "team": g_team,
            "chapter_id": "C",
            "at": g["t"],
            "badge": "GOAL BREAKTHROUGH",
            "title": f"{TEAMS[g_team]} goal · {PLAYERS[g_team][g['actor']]}",
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


def build_sequences(state: dict, team: str | None = None) -> list[dict]:
    """Organize discrete on-ball events into continuous possession sequences with step details."""
    events = state["events"]
    grouped: dict[int, list[dict]] = {}
    for e in events:
        if e["kind"] == "end":
            continue
        # A saved shot's possession_id was incremented to the keeper's new possession;
        # attach the shot to the attacking sequence that produced it.
        pid = e["possession_id"] - (1 if e["kind"] == "shot" and e["outcome"] == "saved" else 0)
        grouped.setdefault(pid, []).append(e)

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
        passes = [e for e in same_team_events if e["kind"] == "pass"]
        prog_dist = sum(
            max(0.0, attack_x(seq_team, e["end"][0]) - attack_x(seq_team, e["start"][0]))
            for e in passes
        )
        entered_final_third = any(
            attack_x(seq_team, e["start"][0]) <= 70 < attack_x(seq_team, e["end"][0])
            for e in passes
        )
        last_ev = same_team_events[-1]
        outcome = (
            "goal"
            if last_ev["kind"] == "shot" and last_ev["outcome"] == "goal"
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
        territory_gained = round(attack_x(seq_team, end_pt[0]) - attack_x(seq_team, start_pt[0]), 1)
        events_detail = [
            {
                "seq_step": idx + 1,
                "id": e["id"],
                "kind": e["kind"],
                "team": seq_team,
                "actor": e["actor"],
                "actor_name": PLAYERS.get(seq_team, {}).get(e["actor"], e["actor"]),
                "receiver": e.get("receiver"),
                "receiver_name": PLAYERS.get(seq_team, {}).get(e.get("receiver"), e.get("receiver")) if e.get("receiver") else None,
                "start": e["start"],
                "end": e["end"],
                "outcome": e.get("outcome", "success"),
                "t": e["t"],
                "gain_m": round(attack_x(seq_team, e["end"][0]) - attack_x(seq_team, e["start"][0]), 1),
                "channel": channel_name(seq_team, e["start"][1]),
            }
            for idx, e in enumerate(same_team_events)
        ]

        sequences.append({
            "sequence_id": f"SEQ-{pid:03d}",
            "possession_id": pid,
            "team": seq_team,
            "start_t": same_team_events[0]["t"],
            "end_t": last_ev["t"],
            "duration": max(0, last_ev["t"] - same_team_events[0]["t"]),
            "origin_kind": same_team_events[0]["kind"],
            "pass_count": len(passes),
            "progressive_distance": round(prog_dist, 1),
            "territory_gained": territory_gained,
            "start_coords": list(start_pt),
            "end_coords": list(end_pt),
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
    events = [e for e in state["events"] if e["team"] == team and e["kind"] != "end"]
    node_touches: dict[str, list[tuple[float, float]]] = {p: [] for p in PLAYERS[team]}
    edges_map: dict[tuple[str, str], dict] = {}
    progressive_passes: list[dict] = []
    recoveries: list[dict] = []
    zone_counts = {"defensive_third": 0, "middle_third": 0, "attacking_third": 0}
    channel_counts = {"left": 0, "center": 0, "right": 0}
    attacking_channel_counts = {"left": 0, "center": 0, "right": 0}

    for e in events:
        ax_start = attack_x(team, e["start"][0])
        ch_start = channel_name(team, e["start"][1])
        channel_counts[ch_start] += 1

        if ax_start < 35:
            zone_counts["defensive_third"] += 1
        elif ax_start <= 70:
            zone_counts["middle_third"] += 1
        else:
            zone_counts["attacking_third"] += 1
            attacking_channel_counts[ch_start] += 1

        if e["actor"] in node_touches:
            node_touches[e["actor"]].append(tuple(e["start"]))
        if e["kind"] == "pass" and e["receiver"] in node_touches:
            node_touches[e["receiver"]].append(tuple(e["end"]))
            pair = (e["actor"], e["receiver"])
            edge = edges_map.setdefault(pair, {"from": pair[0], "to": pair[1], "count": 0, "event_ids": []})
            edge["count"] += 1
            edge["event_ids"].append(e["id"])
            gain_m = round(attack_x(team, e["end"][0]) - ax_start, 1)
            is_entry = ax_start <= 70 < attack_x(team, e["end"][0])
            if gain_m >= 12.0 or is_entry:
                progressive_passes.append({
                    "id": e["id"],
                    "t": e["t"],
                    "actor": e["actor"],
                    "actor_name": PLAYERS[team].get(e["actor"], e["actor"]),
                    "receiver": e["receiver"],
                    "receiver_name": PLAYERS[team].get(e["receiver"], e["receiver"]),
                    "start": e["start"],
                    "end": e["end"],
                    "gain_m": gain_m,
                    "is_entry": is_entry,
                    "channel": ch_start,
                    "entry_channel": channel_name(team, e["end"][1]) if is_entry else None,
                })
        elif e["kind"] == "recovery":
            recoveries.append({
                "id": e["id"],
                "t": e["t"],
                "actor": e["actor"],
                "actor_name": PLAYERS[team].get(e["actor"], e["actor"]),
                "location": e["start"],
                "attack_x": round(ax_start, 1),
                "is_high": ax_start >= 70,
                "channel": ch_start,
            })

    nodes = []
    for pid, name in PLAYERS[team].items():
        pts = node_touches[pid]
        avg_x = round(sum(p[0] for p in pts) / len(pts), 1) if pts else (30.0 if team == "H" else 75.0)
        avg_y = round(sum(p[1] for p in pts) / len(pts), 1) if pts else 34.0
        nodes.append({"player_id": pid, "name": name, "touches": len(pts), "avg_x": avg_x, "avg_y": avg_y})

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
        "high_recovery_threshold_x": 70.0 if team == "H" else 35.0,
    }

    return {
        "team": team,
        "team_name": TEAMS[team],
        "attack_direction": "right" if team == "H" else "left",
        "nodes": nodes,
        "edges": list(edges_map.values()),
        "progressive_passes": progressive_passes,
        "final_third_entries": final_third_entries,
        "recoveries": recoveries,
        "zones": zones,
        "channels": channels,
        "attacking_channels": attacking_channels,
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
    for t_code in teams:
        for pid, name in PLAYERS[t_code].items():
            actor_events = [e for e in state["events"] if e["team"] == t_code and e["actor"] == pid and e["kind"] != "end"]
            passes = [e for e in actor_events if e["kind"] == "pass"]
            prog_passes = [
                e for e in passes
                if (attack_x(t_code, e["end"][0]) - attack_x(t_code, e["start"][0])) >= 12.0
                or (attack_x(t_code, e["start"][0]) <= 70 < attack_x(t_code, e["end"][0]))
            ]
            entries = [
                e for e in passes
                if attack_x(t_code, e["start"][0]) <= 70 < attack_x(t_code, e["end"][0])
            ]
            prog_dist = sum(
                max(0.0, attack_x(t_code, e["end"][0]) - attack_x(t_code, e["start"][0]))
                for e in passes
            )
            recs = [e for e in actor_events if e["kind"] == "recovery"]
            shots = [e for e in actor_events if e["kind"] == "shot"]
            goals = [e for e in shots if e["outcome"] == "goal"]
            spotlight.append({
                "player_id": pid,
                "name": name,
                "team": t_code,
                "team_name": TEAMS[t_code],
                "passes": len(passes),
                "progressive_passes": len(prog_passes),
                "progressive_distance": round(prog_dist, 1),
                "final_third_entries": len(entries),
                "recoveries": len(recs),
                "shots": len(shots),
                "goals": len(goals),
                "sequences_involved": len(seq_by_player.get(pid, [])),
                "event_ids": [e["id"] for e in actor_events],
            })
    return spotlight

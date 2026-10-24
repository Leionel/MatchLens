"""Evidence graph builder.

Every node ID is a content hash so the graph is reproducible across processes
(Python's hash() is intentionally not used). The graph only contains claims
that exist in the durable registry, receipts that actually exist, and events
that are present in the frozen snapshot.
"""
from __future__ import annotations

import hashlib
from typing import Any

from .football import Snapshot
from .registry import ClaimRegistry


def _stable(prefix: str, key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}-{digest}"


def build_evidence_graph(
    *,
    match_id: str,
    match_context: Any,
    snapshot: Snapshot,
    registry: ClaimRegistry,
    team: str = "H",
    max_event_nodes: int = 400,
) -> dict:
    data = snapshot.data
    receipts = data.get("receipts", {})
    events = data.get("events", [])
    data_version = getattr(match_context, "data_version", "unknown")
    coverage = data.get("coverage", {})

    nodes: list[dict] = []
    edges: list[dict] = []
    node_ids: set[str] = set()

    def add_node(node_id: str, node_type: str, label: str, source: str, **fields) -> None:
        if node_id in node_ids:
            return
        node_ids.add(node_id)
        nodes.append({
            "id": node_id,
            "type": node_type,
            "label": label,
            "source": source,
            "data_version": data_version,
            **fields,
        })

    def add_edge(source_id: str, target_id: str, relation: str) -> None:
        edges.append({
            "source": source_id,
            "target": target_id,
            "relation": relation,
            "data_version": data_version,
        })

    match_node = _stable("match", match_id)
    add_node(
        match_node,
        "match",
        f"{match_context.home_team_name} vs {match_context.away_team_name}",
        getattr(match_context, "provider", "unknown"),
        match_id=match_id,
        coverage=getattr(match_context, "data_coverage", None),
        mode=getattr(match_context, "mode", None),
        official_score={
            "H": getattr(match_context, "official_home_score", None),
            "N": getattr(match_context, "official_away_score", None),
        },
    )

    snapshot_node = _stable("snapshot", snapshot.id)
    add_node(
        snapshot_node,
        "snapshot",
        f"Snapshot @ {data.get('as_of')}s",
        "frozen_snapshot",
        snapshot_id=snapshot.id,
        as_of=data.get("as_of"),
        score=data.get("score"),
        score_basis=data.get("score_basis"),
        coverage=coverage,
        coordinate_frame=data.get("coordinate_frame"),
        evidence_hash=hashlib.sha256(snapshot.canonical.encode("utf-8")).hexdigest(),
    )
    add_edge(match_node, snapshot_node, "observes_at")

    # --- real event nodes -------------------------------------------------------
    event_nodes: dict[str, str] = {}
    for ev in events[:max_event_nodes]:
        eid = ev.get("id") or ev.get("event_id")
        if not eid:
            continue
        node_id = _stable("event", f"{snapshot.id}:{eid}")
        event_nodes[str(eid)] = node_id
        add_node(
            node_id,
            "event",
            f"{ev.get('kind', 'event')} · {ev.get('t')}s · {ev.get('actor_name') or ev.get('actor') or 'unknown'}",
            "recorded_event",
            event_id=str(eid),
            clock_seconds=ev.get("t"),
            period=ev.get("period"),
            team=ev.get("team"),
            action=ev.get("kind"),
            actor=ev.get("actor_name") or ev.get("actor"),
            start=ev.get("start"),
            end=ev.get("end"),
            located=ev.get("located", ev.get("start") is not None),
            possession_id=ev.get("possession_id"),
            is_shootout=ev.get("is_shootout", False),
        )
        add_edge(snapshot_node, node_id, "records")

    # --- metric receipts (existence is mandatory; absence becomes a gap) ---------
    receipt_nodes: dict[str, str] = {}
    for key, receipt in receipts.items():
        if not isinstance(receipt, dict):
            continue
        value = receipt.get("value")
        node_id = _stable("receipt", f"{snapshot.id}:{key}")
        receipt_nodes[key] = node_id
        add_node(
            node_id,
            "metric_receipt",
            key,
            "derived_metric",
            metric_id=key,
            value=value,
            status=receipt.get("status", "ok" if value is not None else "unobserved"),
            unit=receipt.get("unit"),
            numerator=receipt.get("numerator"),
            denominator=receipt.get("denominator"),
            event_ids=receipt.get("event_ids", []),
            definition=receipt.get("definition"),
        )
        add_edge(snapshot_node, node_id, "computes")
        for eid in receipt.get("event_ids", []):
            target = event_nodes.get(str(eid))
            if target:
                add_edge(node_id, target, "evidence_from")

    # --- claims, gate verdicts, challenges, revisions ---------------------------
    records = registry.records_for(match_id, snapshot.id)
    challenge_records = [
        c for c in registry.challenges.values()
        if c.match_id == match_id and c.snapshot_id == snapshot.id
    ]
    claims_by_id: dict[str, str] = {}
    for record in records:
        claim_node = _stable("claim", record.record_id)
        claims_by_id[record.claim_id] = claim_node
        published = record.gate_status == "approved" and record.editorial_status == "approved"
        add_node(
            claim_node,
            "claim",
            record.claim_id,
            "claim_registry",
            claim_id=record.claim_id,
            assertion=record.assertion,
            claim_level=record.claim_level,
            subject_team=record.subject_team,
            gate_status=record.gate_status,
            editorial_status=record.editorial_status,
            published=published,
            gate_verified=record.gate_status == "approved",
            evidence_hash=record.evidence_hash,
            source_run=record.source_run,
            as_of=record.as_of,
            statement=record.statement,
        )
        add_edge(snapshot_node, claim_node, "evaluates")

        gate_node = _stable("gate", f"{record.record_id}:{record.gate_version}")
        add_node(
            gate_node,
            "gate_verdict",
            f"Gate {record.gate_version}: {record.gate_status}",
            "publication_gate",
            gate_version=record.gate_version,
            status=record.gate_status,
            violations=record.gate_violations,
            evidence_hash=record.evidence_hash,
        )
        add_edge(claim_node, gate_node, "gated_by")

        limitation_node = _stable("limitation", f"{record.record_id}:off_ball")
        add_node(
            limitation_node,
            "limitation",
            "On-ball event data only; no off-ball positioning or tactical intent.",
            "claim_registry",
            limitation_type="off_ball_unobserved",
        )
        add_edge(claim_node, limitation_node, "bounded_by")
        if not coverage.get("continuous", False):
            coverage_node = _stable("limitation", f"{record.record_id}:coverage")
            add_node(
                coverage_node,
                "limitation",
                "Partial observed coverage; unobserved intervals are Unknown, not zero.",
                "claim_registry",
                limitation_type="partial_coverage",
                coverage=coverage,
            )
            add_edge(claim_node, coverage_node, "bounded_by")

        for ref in record.evidence_scope.get("metric_ids", []):
            receipt_node = receipt_nodes.get(ref)
            if receipt_node is None:
                gap_node = _stable("gap", f"{record.record_id}:{ref}")
                add_node(
                    gap_node,
                    "evidence_gap",
                    f"Missing receipt: {ref}",
                    "claim_registry",
                    metric_id=ref,
                    reason="receipt_missing",
                    value=None,
                )
                add_edge(claim_node, gap_node, "has_evidence_gap")
            else:
                add_edge(claim_node, receipt_node, "supported_by")
        for eid in record.evidence_scope.get("event_ids", []):
            event_node = event_nodes.get(str(eid))
            if event_node is None:
                gap_node = _stable("gap", f"{record.record_id}:event:{eid}")
                add_node(
                    gap_node,
                    "evidence_gap",
                    f"Event outside snapshot prefix: {eid}",
                    "claim_registry",
                    event_id=str(eid),
                    reason="event_not_in_snapshot",
                    value=None,
                )
                add_edge(claim_node, gap_node, "has_evidence_gap")
            else:
                add_edge(claim_node, event_node, "supported_by")

        for challenge in challenge_records:
            if challenge.claim_id != record.claim_id:
                continue
            challenge_node = _stable("challenge", challenge.request_hash)
            add_node(
                challenge_node,
                "challenge",
                challenge.challenge_type,
                "challenge_registry",
                challenge_type=challenge.challenge_type,
                idempotency_key=challenge.idempotency_key,
                request_hash=challenge.request_hash,
                outcome=challenge.result.get("outcome"),
                created_at=challenge.created_at,
            )
            add_edge(claim_node, challenge_node, "challenged_by")
            revision_node = _stable("revision", challenge.request_hash)
            add_node(
                revision_node,
                "revision",
                f"Revision: {challenge.result.get('outcome', 'unknown')}",
                "challenge_registry",
                outcome=challenge.result.get("outcome"),
                summary=challenge.result.get("resolution_summary"),
                request_hash=challenge.request_hash,
            )
            add_edge(challenge_node, revision_node, "produced")

    published_ids = {n["claim_id"] for n in nodes if n["type"] == "claim" and n.get("published")}
    return {
        "match_id": match_id,
        "snapshot_id": snapshot.id,
        "as_of": data.get("as_of"),
        "team": team,
        "data_version": data_version,
        "nodes": nodes,
        "edges": edges,
        "nodes_count": len(nodes),
        "edges_count": len(edges),
        "claim_count": len(records),
        "published_claim_count": len(published_ids),
        "unpublished_claim_count": len(records) - len(published_ids),
        "challenge_count": len(challenge_records),
        "events_truncated": len(events) > max_event_nodes,
        "event_nodes_count": len(event_nodes),
        "coverage": coverage,
    }

"""Slice C-4 acceptance: Broadcast review lifecycle.

Covers the withdrawn-then-re-reviewed editorial contract (a rejected claim is
unbroadcastable, a rundown carrying it turns stale, and a later approval makes
it valid again without weakening server authority), plus the bounded export
manifest history and its producer-only access boundary.
"""
from __future__ import annotations

import pytest
from matchlens.broadcast import BroadcastStore, ExportManifest
from matchlens.football import freeze, generate_match
from matchlens.registry import ClaimRegistry


@pytest.fixture()
def registry_with_claim():
    snap = freeze(generate_match(), 720)
    registry = ClaimRegistry()
    record = registry.verify_and_register(snap, "syn_default", "goal_sequence", "H")
    assert record.gate_status == "approved"
    return registry, snap, record


def _manifest(claim_id: str, match_id: str = "m1", snapshot_id: str = "s1", valid: bool = True) -> ExportManifest:
    from matchlens.broadcast import ExportManifestItem

    return ExportManifest(
        manifest_id=f"manifest-{claim_id}-{valid}",
        match_id=match_id,
        snapshot_id=snapshot_id,
        generated_by="tester",
        valid=valid,
        items=[
            ExportManifestItem(
                claim_id=claim_id,
                revision_id="rev1",
                statement="s",
                evidence_hash="h",
                gate_status="approved",
                editorial_status="approved",
                valid=valid,
            )
        ],
    )


def test_withdrawn_claim_is_unbroadcastable_until_re_reviewed(registry_with_claim):
    registry, snap, record = registry_with_claim

    # A rundown requires the editorial approval first; then it is built while
    # the claim is fully publishable.
    approved = registry.editorial_decision(
        "syn_default", snap.id, record.claim_id,
        approver="producer-a", role="producer", decision="approved",
    )
    assert approved.broadcastable is True
    store = BroadcastStore()
    rundown = store.build(
        match_id="syn_default",
        snapshot_id=snap.id,
        claims=[approved],
        claim_ids=[record.claim_id],
        dataset_revision=None,
        actor="producer-a",
    )
    assert store.validate(rundown, claims=[approved], dataset_revision=None).valid

    # The store refuses to build a rundown from an already-withdrawn claim.
    rejected = registry.editorial_decision(
        "syn_default", snap.id, record.claim_id,
        approver="producer-a", role="producer", decision="rejected", note="withdrawn",
    )
    assert rejected.editorial_status == "rejected"
    assert rejected.broadcastable is False
    with pytest.raises(ValueError, match="claim_not_broadcastable"):
        store.build(
            match_id="syn_default",
            snapshot_id=snap.id,
            claims=[rejected],
            claim_ids=[record.claim_id],
            dataset_revision=None,
            actor="producer-a",
        )
    validity = registry.claim_validity(rejected, dataset_revision=None, require_editorial=True)
    assert validity["valid"] is False
    assert "editorial_rejected" in validity["reasons"]

    # The previously built rundown goes stale at read time — it is kept, not
    # silently cleaned into an empty panel.
    validation_after_withdraw = store.validate(rundown, claims=[rejected], dataset_revision=None)
    assert validation_after_withdraw.valid is False
    assert record.claim_id in validation_after_withdraw.stale_items
    # editorial_decision mutates and returns the same record, so the version
    # must be captured before the re-approval.
    rejected_version = rejected.editorial_version

    # Re-review approves the claim again: broadcastable once more. Because an
    # editorial decision mints a new revision, the previously built rundown is
    # still stale until the producer rebuilds it — server authority stays
    # ahead of any cached artifact.
    reinstated = registry.editorial_decision(
        "syn_default", snap.id, record.claim_id,
        approver="producer-b", role="producer", decision="approved", note="re-reviewed",
    )
    assert reinstated.editorial_status == "approved"
    assert reinstated.broadcastable is True
    assert reinstated.editorial_version > rejected_version
    validation_after_review = store.validate(rundown, claims=[reinstated], dataset_revision=None)
    assert validation_after_review.valid is False
    assert "rundown_revision_mismatch" in validation_after_review.items[0].reasons
    rebuilt = store.build(
        match_id="syn_default",
        snapshot_id=snap.id,
        claims=[reinstated],
        claim_ids=[record.claim_id],
        dataset_revision=None,
        actor="producer-b",
    )
    validation_after_rebuild = store.validate(rebuilt, claims=[reinstated], dataset_revision=None)
    assert validation_after_rebuild.valid is True
    assert validation_after_rebuild.stale_items == []
    history = reinstated.editorial_history
    decisions = [h["decision"] for h in history if isinstance(h, dict) and "decision" in h]
    assert "rejected" in decisions and "approved" in decisions


def test_manifest_history_is_bounded_and_persisted(tmp_path):
    path = tmp_path / "broadcast.json"
    store = BroadcastStore(path)
    for i in range(60):
        store.record_manifest(_manifest(f"c{i}", valid=bool(i % 2)))
    assert len(store.manifests) == BroadcastStore.MANIFEST_HISTORY_MAX
    assert store.manifests[0].items[0].claim_id == "c59"  # newest first

    reopened = BroadcastStore(path)
    assert len(reopened.manifests) == BroadcastStore.MANIFEST_HISTORY_MAX
    assert reopened.manifests[0].manifest_id == store.manifests[0].manifest_id

    scoped = reopened.manifest_history("m1", "s1")
    assert len(scoped) == BroadcastStore.MANIFEST_HISTORY_MAX
    assert reopened.manifest_history("other", "s1") == []


def test_manifest_history_endpoint_is_producer_only(client):
    denied = client.get("/api/broadcast/manifests", params={"match_id": "syn_default", "snapshot_id": "none"})
    # No producer boundary configured in tests -> editorial actions are closed.
    assert denied.status_code in (401, 403, 503)

    # With a configured producer token the endpoint opens for that principal.
    import os

    os.environ["MATCHLENS_PRODUCER_TOKEN"] = "slice-c-producer"
    try:
        ok = client.get(
            "/api/broadcast/manifests",
            params={"match_id": "syn_default", "snapshot_id": "none"},
            headers={"X-MatchLens-Token": "slice-c-producer"},
        )
        assert ok.status_code == 200
        assert ok.json()["projection"] == "producer"
        assert ok.json()["manifests"] == []
    finally:
        del os.environ["MATCHLENS_PRODUCER_TOKEN"]


def test_export_refuses_without_broadcastable_claims(client, monkeypatch):
    """Server authority stays intact: no registered broadcastable claim, no export."""
    monkeypatch.setenv("MATCHLENS_PRODUCER_TOKEN", "slice-c-producer")
    headers = {"X-MatchLens-Token": "slice-c-producer"}

    assert client.post("/api/control", json={"action": "seek", "at": 719}).status_code == 200
    # An investigation freezes and persists the snapshot the export flow needs.
    inv = client.post(
        "/api/investigate",
        json={"match_id": "syn_default", "at": 719, "focus_type": "metric", "focus_id": "shots", "question": ""},
    )
    assert inv.status_code == 200
    snapshot_id = inv.json().get("snapshot_id")
    if not snapshot_id:
        pytest.skip("investigation produced no persisted snapshot")
    res = client.post(
        "/api/broadcast/export",
        headers=headers,
        json={"match_id": "syn_default", "snapshot_id": snapshot_id, "perspective": "media", "export_format": "json"},
    )
    assert res.status_code == 409
    assert "no_broadcastable_claims" in res.text

    # And without a producer token the same call stays closed.
    monkeypatch.delenv("MATCHLENS_PRODUCER_TOKEN")
    denied = client.post(
        "/api/broadcast/export",
        json={"match_id": "syn_default", "snapshot_id": snapshot_id, "perspective": "media", "export_format": "json"},
    )
    assert denied.status_code in (401, 403, 503)

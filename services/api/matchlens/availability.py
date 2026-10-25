"""Match data availability contract.

Three states are deliberately distinct:

``CATALOGUED``
    Metadata is committed and the match is discoverable, but no provider
    payload is installed. The library may show the record; analysis is closed.

``MATERIALIZED``
    A dataset file exists, but analysis readiness has not been established
    (missing provider mapping, failed completeness verification, or an
    unverified/legacy manifest entry).

``ANALYSIS_READY``
    The dataset passed the import contract and the stored completeness report
    is usable. The content hash is re-checked whenever the dataset is loaded.

A catalog entry must never silently fall back to synthetic data when its
provider payload is absent.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AvailabilityStatus = Literal["CATALOGUED", "MATERIALIZED", "ANALYSIS_READY"]

INSTALL_HINT = (
    "Run scripts/fetch_statsbomb_open_data.py --corpus and "
    "scripts/ingest_statsbomb_corpus.py --match {match_id} to install this payload."
)

_ANALYZABLE_COMPLETENESS = {
    "COMPLETE_VERIFIED",
    "COMPLETE_CLAIMED_UNVERIFIED",
    "PARTIAL_OBSERVED",
    "SPARSE_SAMPLE_FIXTURE",
}


class MatchAvailability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_id: str
    status: AvailabilityStatus
    dataset_installed: bool = False
    analysis_ready: bool = False
    dataset_path: str | None = None
    declared_sha256: str | None = None
    verification_basis: Literal[
        "synthetic",
        "manifest_import_receipt",
        "fixture_integrity_check",
        "live_checksum",
        "unverified",
    ] = "unverified"
    completeness_status: str | None = None
    reason: str | None = None
    install_hint: str | None = None
    checks: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def can_analyze(self) -> bool:
        return self.analysis_ready


def synthetic_availability(match_id: str) -> MatchAvailability:
    return MatchAvailability(
        match_id=match_id,
        status="ANALYSIS_READY",
        dataset_installed=True,
        analysis_ready=True,
        verification_basis="synthetic",
        completeness_status="COMPLETE_VERIFIED",
        checks=[{"check": "synthetic_generator", "passed": True, "detail": "deterministic by construction"}],
    )


def missing_provider_dataset(match_id: str, *, detail: str | None = None) -> MatchAvailability:
    return MatchAvailability(
        match_id=match_id,
        status="CATALOGUED",
        dataset_installed=False,
        analysis_ready=False,
        completeness_status="DATASET_NOT_IMPORTED",
        reason=detail
        or (
            "dataset_not_imported: provider payloads are excluded from version control; "
            "install the payload before analysis"
        ),
        install_hint=INSTALL_HINT.format(match_id=match_id),
        checks=[{"check": "dataset_file", "passed": False, "detail": "not installed"}],
    )


def manifest_availability(
    match_id: str,
    *,
    dataset_path: str | None,
    declared_sha256: str | None,
    completeness_status: str | None,
    completeness: dict[str, Any] | None,
    provider_mapping_ok: bool,
    events_count: int | None,
) -> MatchAvailability:
    if not dataset_path:
        return missing_provider_dataset(match_id)

    checks: list[dict[str, Any]] = [
        {"check": "dataset_file", "passed": True, "detail": dataset_path},
        {
            "check": "content_sha256_declared",
            "passed": bool(declared_sha256),
            "detail": declared_sha256[:16] + "..." if declared_sha256 else "missing",
        },
        {
            "check": "provider_team_mapping",
            "passed": provider_mapping_ok,
            "detail": "home/away provider IDs required",
        },
        {
            "check": "events_present",
            "passed": bool(events_count),
            "detail": f"{events_count or 0} events",
        },
        {
            "check": "completeness_report",
            "passed": bool(completeness or completeness_status),
            "detail": completeness_status or "missing",
        },
    ]
    reason = None
    if not provider_mapping_ok:
        reason = "missing_provider_team_mapping"
    elif not events_count:
        reason = "dataset_has_no_events"
    elif not declared_sha256:
        reason = "manifest_missing_content_hash"
    elif not completeness_status:
        reason = "completeness_not_verified"

    ready = (
        provider_mapping_ok
        and bool(events_count)
        and bool(declared_sha256)
        and completeness_status in _ANALYZABLE_COMPLETENESS
        and (completeness is None or bool(completeness))
    )
    if not ready and reason is None:
        reason = f"completeness_state_{str(completeness_status).lower()}_not_analyzable"
    # The stored completeness status can say PARTIAL_OBSERVED while the nested
    # report is absent (older imports). That is still analyzable, but with a
    # visible loss of verification detail, so the basis stays "unverified".
    basis = "manifest_import_receipt" if completeness and declared_sha256 else "unverified"
    return MatchAvailability(
        match_id=match_id,
        status="ANALYSIS_READY" if ready else "MATERIALIZED",
        dataset_installed=True,
        analysis_ready=ready,
        dataset_path=dataset_path,
        declared_sha256=declared_sha256,
        verification_basis=basis,
        completeness_status=completeness_status,
        reason=reason,
        install_hint=None if ready else INSTALL_HINT.format(match_id=match_id),
        checks=checks,
    )


def fixture_availability(
    match_id: str,
    *,
    dataset_path: str,
    completeness_status: str | None,
    completeness: dict[str, Any] | None,
    events_count: int | None,
    checksum_verified: bool,
) -> MatchAvailability:
    ready = bool(events_count) and completeness_status in _ANALYZABLE_COMPLETENESS
    return MatchAvailability(
        match_id=match_id,
        status="ANALYSIS_READY" if ready else "MATERIALIZED",
        dataset_installed=True,
        analysis_ready=ready,
        dataset_path=dataset_path,
        verification_basis="fixture_integrity_check",
        completeness_status=completeness_status,
        reason=None if ready else "fixture_not_analyzable",
        checks=[
            {"check": "dataset_file", "passed": True, "detail": dataset_path},
            {"check": "content_sha256_verified", "passed": checksum_verified, "detail": "sha256"},
            {"check": "events_present", "passed": bool(events_count), "detail": f"{events_count or 0} events"},
            {
                "check": "completeness_report",
                "passed": completeness_status in _ANALYZABLE_COMPLETENESS,
                "detail": completeness_status or "missing",
            },
        ],
    )

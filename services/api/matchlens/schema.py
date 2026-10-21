"""Core data architecture: Four orthogonal, isolated data objects.

RawSourceRecord -> NormalizedEvent -> DerivedMetric -> VerifiedClaim

Conforms to Section 3.2.2 & 6.3.1 of FOOTBALL_INTELLIGENCE_PLATFORMS_2026.md:
- NormalizedEvent strictly contains observed event facts (pitch scaled to 105m x 68m).
- Models/derived values (e.g. delta_xT, xG) are stored separately in DerivedMetric.
- Missing values are explicitly distinguished from real zero via Optional + status flags.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class DataCoverageLevel(str, Enum):
    C0_SYNTHETIC = "C0"  # Synthetic scenarios for regression and UI demos
    C1_OPEN_EVENTS = "C1"  # Open public event data (e.g. StatsBomb Open Data)
    C2_EVENTS_AND_360 = "C2"  # Event data with freeze-frame spatial context
    C3_COMMERCIAL_LIVE = "C3"  # Commercial real-time event feeds
    C4_OPTICAL_TRACKING = "C4"  # Continuous 25Hz optical tracking
    C5_VIDEO = "C5"  # Video / broadcast footage with timestamps


class ActionType(str, Enum):
    PASS = "Pass"
    SHOT = "Shot"
    CARRY = "Carry"
    TACKLE = "Tackle"
    INTERCEPTION = "Interception"
    RECOVERY = "Ball Recovery"
    DISPOSSESSED = "Dispossessed"
    CLEARANCE = "Clearance"
    FOUL = "Foul"
    DUEL = "Duel"
    GOALKEEPER = "Goal Keeper"
    RESTART = "Restart"
    OTHER = "Other"


class RawSourceRecord(BaseModel):
    """Raw data provider lineage and provenance record."""
    model_config = ConfigDict(extra="forbid")

    provider: str  # e.g. "statsbomb_open_data", "synthetic"
    provider_event_id: str
    schema_version: str
    license_ref: str
    payload_ref: Optional[str] = None


class NormalizedEvent(BaseModel):
    """Unified standardized pitch event with meter-scale coordinates (105m x 68m).
    
    Contains ONLY observed event properties.
    Model derivations (e.g. delta_xT, xG) MUST NOT be embedded here.
    """
    model_config = ConfigDict(extra="forbid")

    event_id: str
    match_id: str
    source: RawSourceRecord
    period: int
    clock_seconds: float
    clock_basis: Literal["period_elapsed", "match_elapsed"] = "match_elapsed"
    team_id: str
    attack_direction: Literal["left_to_right", "right_to_left"] = "left_to_right"
    possession_id: Optional[str] = None
    possession_changed: Optional[bool] = None
    player_id: Optional[str] = None
    player_name: Optional[str] = None
    jersey_number: Optional[int] = None
    action_type: ActionType
    outcome: Optional[str] = None  # e.g. "complete", "incomplete", "goal", "saved", "blocked"
    x: Optional[float] = Field(default=None, ge=0.0, le=105.0)
    y: Optional[float] = Field(default=None, ge=0.0, le=68.0)
    end_x: Optional[float] = Field(default=None, ge=0.0, le=105.0)
    end_y: Optional[float] = Field(default=None, ge=0.0, le=68.0)


class DerivedMetric(BaseModel):
    """Analytical metric computed by statistical or machine learning models.
    
    Explicitly distinguishes missing/not-applicable from a true numeric 0.0 value.
    """
    model_config = ConfigDict(extra="forbid")

    metric_id: str
    event_id: str  # References NormalizedEvent.event_id
    name: Literal["xG", "delta_xT", "oaai_contribution", "progression_meters"]
    value: Optional[float] = None
    status: Literal["ok", "not_applicable", "missing_input"] = "ok"
    model_version: str
    uncertainty: Optional[dict] = None


class VerifiedClaim(BaseModel):
    """Structured tactical assertion with explicit reasoning tier and evidence bindings.
    
    Tiers (claim_level):
    1 = Observable Facts (Deterministic, computed directly from raw events)
    2 = Metric Attribution (Mathematical decomposition of metric, NOT ground-truth causality)
    3 = Statistical Association (Multi-match sample correlation with baseline & uncertainty)
    4 = Causal Inference (Requires structural assumptions, counterfactuals & validation)
    """
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    claim_level: Literal[1, 2, 3, 4]
    text: str
    evidence_scope: dict = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    counterevidence: list[str] = Field(default_factory=list)
    verification_method: str = "deterministic_rule"
    metric_versions: dict[str, str] = Field(default_factory=dict)
    verified: bool = True

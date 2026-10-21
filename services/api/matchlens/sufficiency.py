"""Track C: Data Sufficiency Notification System & Observable Proxies.

Conforms to Section 6.3.1 of FOOTBALL_INTELLIGENCE_PLATFORMS_2026.md and Track C R1:
- Explicit identification boundaries for event-only streams (C0 synthetic, C1 open events).
- Emits mandatory disclaimer regarding lack of continuous 22-player off-ball tracking.
- Restricts maximum allowed claim_level to Level 2 (formula decomposition) for C0/C1.
- Computes observable proxies: 6-second post-turnover recovery rate and 9-zone density differential.
"""
from __future__ import annotations

from typing import Any, Literal, Optional, Sequence
from pydantic import BaseModel, ConfigDict, Field

from .exploration import (
    analyze_quick_recoveries,
    analyze_action_density_differential,
)


class DataSufficiencyNotice(BaseModel):
    """Notice summarizing optical tracking availability and observational bounds."""
    model_config = ConfigDict(extra="forbid")

    has_optical_tracking: bool = False
    has_360_freeze_frame: bool = False
    limitations: list[str] = Field(default_factory=list)
    observable_proxies: list[str] = Field(default_factory=list)
    disclaimer: str


class DataSufficiencyReport(BaseModel):
    """Formal assessment report for data sufficiency and maximum allowed claim tier."""
    model_config = ConfigDict(extra="forbid")

    coverage_level: str
    tracking_available: bool
    has_360_freeze_frame: bool = False
    disclaimer: str
    allowed_claim_levels: list[int]
    limitations: list[str]
    observable_proxies: dict[str, Any]


def assess_data_sufficiency(
    events: Sequence[Any],
    coverage_level: str = "C0",
) -> DataSufficiencyReport:
    """Evaluates data stream capabilities and bounds tactical reasoning.
    
    If coverage_level is C0 (Synthetic) or C1 (Open Events):
    - Alerts that continuous off-ball tracking is missing.
    - Limits claims strictly to Level 1 (observations) and Level 2 (metric decompositions).
    - Automatically calculates observable proxy metrics (6s recoveries, 9-zone density differential).
    """
    coverage = str(coverage_level).upper()
    if coverage in ("C0", "C1"):
        tracking_available = False
        has_360 = False
        allowed_levels = [1, 2]
        disclaimer = (
            "常规事件流缺乏连续无球防守阵型位置，无法支持全场 22 人防守结构推演。"
            "分析结论严格限制在可观察事件序列及确定性指标公式分解（Level 1–2）。"
        )
        limitations = [
            "Continuous optical tracking is absent; positions of 20+ off-ball players are unobserved.",
            "Defensive compactness, line height, and pressing shapes cannot be mathematically verified from on-ball events alone.",
            "Turnovers cannot be definitively attributed to team-wide pressing directives without off-ball coordination data.",
        ]
        # Calculate real observable proxies
        quick_rec = analyze_quick_recoveries(events, window_seconds=6.0)
        density_diff = analyze_action_density_differential(events)
        proxies = {
            "quick_recoveries_6s": quick_rec,
            "density_differential_9zones": density_diff,
        }
    elif coverage in ("C2", "C3"):
        tracking_available = False
        has_360 = True
        allowed_levels = [1, 2, 3]
        disclaimer = "具备 360 定格阵型帧，支持局部防守压力估算，但仍缺乏连续追踪。"
        limitations = [
            "360 freeze-frames provide snapshot context but lack velocity/acceleration vectors.",
        ]
        proxies = {
            "quick_recoveries_6s": analyze_quick_recoveries(events, window_seconds=6.0),
            "density_differential_9zones": analyze_action_density_differential(events),
        }
    else:  # C4 optical tracking or higher
        tracking_available = True
        has_360 = True
        allowed_levels = [1, 2, 3, 4]
        disclaimer = "全场 25Hz 高频追踪数据已就绪，支持空间压迫及反事实结构因果推演。"
        limitations = []
        proxies = {
            "quick_recoveries_6s": analyze_quick_recoveries(events, window_seconds=6.0),
            "density_differential_9zones": analyze_action_density_differential(events),
        }

    return DataSufficiencyReport(
        coverage_level=coverage,
        tracking_available=tracking_available,
        has_360_freeze_frame=has_360,
        disclaimer=disclaimer,
        allowed_claim_levels=allowed_levels,
        limitations=limitations,
        observable_proxies=proxies,
    )


class DataSufficiencyAdvisor:
    """Enforces strict observational and identifiability boundaries on event streams."""

    @staticmethod
    def inspect(context_description: str = "") -> DataSufficiencyNotice:
        """Determines whether context touches off-ball/pressing bounds and attaches formal caveats."""
        limitations = [
            "Continuous optical tracking is absent; positions of 20+ off-ball players are unobserved.",
            "Defensive compactness, line height, and pressing shapes cannot be mathematically verified from on-ball events alone.",
        ]
        observable_proxies = [
            "Quick post-turnover ball recoveries within W=6 seconds window (BL-03)",
            "Observed action density differential across 9 pitch zones ΔD(z) (BL-04)",
            "Attacking corridor progression & box conversion rates (BL-08)",
        ]
        disclaimer = (
            "Data Sufficiency Notice: The current data stream consists of discrete event coordinates. "
            "Continuous off-ball defensive lines cannot be uniquely identified. Conclusions are strictly bounded to "
            "observable on-ball events and formula decompositions."
        )

        return DataSufficiencyNotice(
            has_optical_tracking=False,
            has_360_freeze_frame=False,
            limitations=limitations,
            observable_proxies=observable_proxies,
            disclaimer=disclaimer,
        )

    @staticmethod
    def assess(events: Sequence[Any], coverage_level: str = "C0") -> DataSufficiencyReport:
        return assess_data_sufficiency(events, coverage_level)

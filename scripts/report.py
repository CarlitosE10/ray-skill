"""
Pydantic models for Ray's output: the RayDecision.

Ray is the decision agent in the three-agent pipeline. It consumes
SnowballReport (quantitative) + CharlieReport (qualitative) and produces
the final BUY/HOLD/SELL decision with fair value, margin of safety,
conviction, and position sizing.

Schema version 1.0.0 — same major-version line as Snowball and Charlie.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0.0"

# ─────────────────────────────────────────────────────────────────────────────
# RATING / DECISION TYPES
# ─────────────────────────────────────────────────────────────────────────────

Decision = Literal["BUY", "HOLD", "SELL", "INSUFFICIENT_DATA"]

ConvictionLevel = Literal["very_low", "low", "moderate", "high", "very_high"]

RiskProfile = Literal["conservative", "moderate", "aggressive"]

TimeHorizon = Literal["short_term", "1-3y", "3-5y", "5-10y", "long_term"]

ScenarioName = Literal["pessimistic", "base", "optimistic"]


# ─────────────────────────────────────────────────────────────────────────────
# DCF SCENARIO
# ─────────────────────────────────────────────────────────────────────────────


class DCFScenario(BaseModel):
    name: ScenarioName
    growth_phase1_pct: float = Field(..., description="Annual FCF growth, years 1-5 (decimal, e.g. 0.08)")
    growth_phase2_pct: float = Field(..., description="Annual FCF growth, years 6-10 (fade to terminal)")
    terminal_growth_pct: float = Field(..., description="Perpetual growth in Gordon terminal (decimal)")
    wacc_pct: float = Field(..., description="Discount rate used (decimal)")
    fair_value_per_share: Optional[float] = None
    enterprise_value: Optional[float] = None
    weight: float = Field(..., description="Weight applied when blending scenarios (sums to 1.0)")


class DCFResult(BaseModel):
    fcf_starting_point: Optional[float] = Field(None, description="Latest FCF used as starting cash flow")
    shares_outstanding: Optional[float] = None
    net_debt: Optional[float] = Field(None, description="Total debt minus cash; subtracted from EV")
    scenarios: list[DCFScenario] = Field(default_factory=list)
    weighted_fair_value_per_share: Optional[float] = None
    sensitivity_notes: list[str] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# MARGIN OF SAFETY
# ─────────────────────────────────────────────────────────────────────────────


class MarginOfSafety(BaseModel):
    moat_input: Literal["very_weak", "weak", "neutral", "strong", "very_strong", "unknown"] = "unknown"
    base_mos_pct: float = Field(..., description="MOS before any adjustments (decimal, e.g. 0.20)")
    applied_mos_pct: float = Field(..., description="Final MOS after MOAT and risk-profile adjustments")
    sell_premium_pct: float = Field(0.25, description="Premium above fair value triggering SELL")
    buy_below: Optional[float] = None
    sell_above: Optional[float] = None
    reasoning: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# SYNC GATE — conflict detection between Snowball and Charlie
# ─────────────────────────────────────────────────────────────────────────────


class SyncGateConflict(BaseModel):
    pattern: str = Field(..., description="Short canonical name of the conflict pattern")
    description: str = Field(..., description="Human-readable explanation of the conflict")
    severity: Literal["info", "warning", "critical"] = "warning"
    conviction_penalty_pp: float = Field(0.0, description="Percentage points subtracted from conviction score")


# ─────────────────────────────────────────────────────────────────────────────
# CONVICTION
# ─────────────────────────────────────────────────────────────────────────────


class ConvictionBreakdown(BaseModel):
    quantitative_confidence: float = Field(..., description="Component from Snowball completeness (0-100)")
    qualitative_score: float = Field(..., description="Component from Charlie qualitative_score (0-100)")
    distance_to_threshold: float = Field(
        ..., description="Component reflecting price gap to buy/sell threshold (0-100)"
    )
    coherence: float = Field(..., description="Component reflecting Snowball/Charlie agreement (0-100)")
    weighted_score: float = Field(..., description="Final 0-100 conviction score")
    level: ConvictionLevel = "low"


# ─────────────────────────────────────────────────────────────────────────────
# POSITION SIZING
# ─────────────────────────────────────────────────────────────────────────────


class PositionSizing(BaseModel):
    suggested_pct_of_portfolio: Optional[float] = Field(
        None, description="Recommended position size as % of portfolio"
    )
    suggested_dollar_amount: Optional[float] = Field(
        None, description="Recommended dollars to allocate (if portfolio total provided)"
    )
    risk_profile: RiskProfile = "moderate"
    cap_pct: float = Field(..., description="Hard cap applied (e.g. 5.0 means 5% max)")
    kelly_raw_pct: Optional[float] = Field(None, description="Raw Kelly fraction before profile cap (pct)")
    rationale: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# DATA QUALITY
# ─────────────────────────────────────────────────────────────────────────────


class DataQuality(BaseModel):
    snowball_completeness_pct: Optional[float] = None
    charlie_completeness_pct: Optional[float] = None
    snowball_schema_version: Optional[str] = None
    charlie_schema_version: Optional[str] = None
    schema_compatible: bool = True
    warnings: list[str] = Field(default_factory=list)
    blocking_issues: list[str] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# THE FINAL DECISION
# ─────────────────────────────────────────────────────────────────────────────


class RayDecision(BaseModel):
    """Top-level output. Ray's verdict on a single ticker."""

    schema_version: str = SCHEMA_VERSION
    ticker: str
    company_name: Optional[str] = None
    sector: Optional[str] = None
    decision_timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Headline
    decision: Decision
    decision_reasoning: str = ""

    # Pricing
    current_price: Optional[float] = None
    fair_value_per_share: Optional[float] = None
    upside_pct: Optional[float] = Field(
        None, description="(fair_value - current_price) / current_price, in pct"
    )

    # The DCF block
    dcf: Optional[DCFResult] = None

    # Margin of safety
    margin_of_safety: Optional[MarginOfSafety] = None

    # Sync gate
    sync_gate_conflicts: list[SyncGateConflict] = Field(default_factory=list)

    # Conviction
    conviction: Optional[ConvictionBreakdown] = None

    # Time horizon
    time_horizon: TimeHorizon = "3-5y"
    time_horizon_reasoning: str = ""

    # Position sizing
    position_sizing: Optional[PositionSizing] = None

    # Narrative components for Ray's user-facing output
    key_drivers: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)

    # Data provenance
    data_quality: DataQuality = Field(default_factory=DataQuality)

    # Always present
    disclaimer: str = (
        "Not financial advice. For informational purposes only. This output is the "
        "product of an automated pipeline and should be reviewed by a licensed "
        "financial advisor before any investment action."
    )

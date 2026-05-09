"""
Input loaders for Ray.

Ray consumes two JSON files: a Snowball report and a Charlie report. This
module defines the minimal subset of fields Ray actually reads from each,
with lenient parsing — every field is Optional so partial reports still
let Ray run (with appropriate warnings).

The full Snowball/Charlie schemas have many more fields; Ray only needs the
ones below.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────────────────────────────────────────────────────────────
# SNOWBALL (subset Ray uses)
# ─────────────────────────────────────────────────────────────────────────────


class SnowballDCFInputs(BaseModel):
    """Minimal DCF inputs Ray reads from Snowball's `dcf-inputs` block."""

    model_config = ConfigDict(extra="ignore")

    free_cash_flow: Optional[float] = None
    revenue_cagr_3y: Optional[float] = None
    fcf_cagr_3y: Optional[float] = None
    beta: Optional[float] = None
    shares_outstanding: Optional[float] = None
    net_debt: Optional[float] = None
    total_debt: Optional[float] = None
    cash: Optional[float] = None
    market_cap: Optional[float] = None


class SnowballDataQuality(BaseModel):
    model_config = ConfigDict(extra="ignore")

    completeness_pct: Optional[float] = None
    warnings: list[str] = Field(default_factory=list)


class SnowballInput(BaseModel):
    """The slice of SnowballReport that Ray needs."""

    model_config = ConfigDict(extra="ignore")

    schema_version: Optional[str] = None
    ticker: str
    company_name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None

    current_price: Optional[float] = None

    # Custom ratios (Snowball's headline numbers)
    pe_ratio: Optional[float] = None
    ev_ebitda: Optional[float] = None
    pkt: Optional[float] = None  # price/free cash flow proxy
    pci: Optional[float] = None  # price/cash flow improvement
    debt_to_ebitda: Optional[float] = None
    interest_coverage: Optional[float] = None

    # Margin / growth profile
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    revenue_growth_yoy: Optional[float] = None
    fcf_yield: Optional[float] = None

    # Technical
    rsi_14: Optional[float] = None
    pct_from_52w_high: Optional[float] = None
    pct_from_52w_low: Optional[float] = None

    # Sentiment
    fear_greed_index: Optional[float] = None
    insider_net_buy_3m: Optional[float] = None  # net insider transaction value, 3m

    # DCF inputs
    dcf_inputs: SnowballDCFInputs = Field(default_factory=SnowballDCFInputs)

    # Provenance
    data_quality: SnowballDataQuality = Field(default_factory=SnowballDataQuality)


# ─────────────────────────────────────────────────────────────────────────────
# CHARLIE (subset Ray uses)
# ─────────────────────────────────────────────────────────────────────────────


class CharlieMoat(BaseModel):
    model_config = ConfigDict(extra="ignore")

    moat_strength: Optional[str] = None  # very_weak..very_strong
    moat_types: list[str] = Field(default_factory=list)
    moat_durability_years: Optional[int] = None
    moat_reasoning: Optional[str] = None


class CharlieGrowthAdjustment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    signal: Optional[str] = None  # decelerate/maintain/accelerate
    suggested_adjustment_pct: Optional[float] = None
    reasoning: Optional[str] = None


class CharlieSectorOutlook(BaseModel):
    model_config = ConfigDict(extra="ignore")

    outlook: Optional[str] = None
    sector_maturity: Optional[str] = None
    relative_strength_vs_spy_3m: Optional[float] = None


class CharlieMacro(BaseModel):
    model_config = ConfigDict(extra="ignore")

    cyclicality: Optional[str] = None
    overall_macro_tailwind: Optional[str] = None
    interest_rate_sensitivity: Optional[str] = None


class CharlieCatalyst(BaseModel):
    model_config = ConfigDict(extra="ignore")

    description: str
    horizon: Optional[str] = None
    likelihood: Optional[str] = None
    impact: Optional[str] = None


class CharlieRisk(BaseModel):
    model_config = ConfigDict(extra="ignore")

    description: str
    severity: Optional[str] = None
    likelihood: Optional[str] = None
    category: Optional[str] = None


class CharlieDataQuality(BaseModel):
    model_config = ConfigDict(extra="ignore")

    completeness_pct: Optional[float] = None
    warnings: list[str] = Field(default_factory=list)


class CharlieInput(BaseModel):
    """The slice of CharlieReport that Ray needs."""

    model_config = ConfigDict(extra="ignore")

    schema_version: Optional[str] = None
    ticker: str
    company_name: Optional[str] = None
    sector: Optional[str] = None

    moat: CharlieMoat = Field(default_factory=CharlieMoat)
    sector_outlook: CharlieSectorOutlook = Field(default_factory=CharlieSectorOutlook)
    macro_environment: CharlieMacro = Field(default_factory=CharlieMacro)
    growth_adjustment: CharlieGrowthAdjustment = Field(default_factory=CharlieGrowthAdjustment)

    catalysts: list[CharlieCatalyst] = Field(default_factory=list)
    qualitative_risks: list[CharlieRisk] = Field(default_factory=list)

    qualitative_score: Optional[int] = None

    data_quality: CharlieDataQuality = Field(default_factory=CharlieDataQuality)


# ─────────────────────────────────────────────────────────────────────────────
# OPTIONAL USER INPUTS — portfolio
# ─────────────────────────────────────────────────────────────────────────────


class PortfolioHolding(BaseModel):
    ticker: str
    market_value: Optional[float] = Field(None, description="Current $ value of the position")
    weight_pct: Optional[float] = Field(None, description="% of portfolio (alternative to market_value)")


class PortfolioInput(BaseModel):
    """Optional portfolio context for position sizing."""

    model_config = ConfigDict(extra="ignore")

    total_value: Optional[float] = None
    cash_available: Optional[float] = None
    holdings: list[PortfolioHolding] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# LOADERS
# ─────────────────────────────────────────────────────────────────────────────


def _load_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Input file not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def load_snowball(path: str | Path) -> SnowballInput:
    raw = _load_json(path)
    # Snowball may nest dcf-inputs differently; normalize
    if "dcf-inputs" in raw and "dcf_inputs" not in raw:
        raw["dcf_inputs"] = raw.pop("dcf-inputs")
    return SnowballInput.model_validate(raw)


def load_charlie(path: str | Path) -> CharlieInput:
    raw = _load_json(path)
    return CharlieInput.model_validate(raw)


def load_portfolio(path: str | Path) -> PortfolioInput:
    raw = _load_json(path)
    return PortfolioInput.model_validate(raw)


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: net debt resolver
# ─────────────────────────────────────────────────────────────────────────────


def resolve_net_debt(s: SnowballInput) -> Optional[float]:
    """Prefer explicit net_debt; fall back to total_debt - cash."""
    d = s.dcf_inputs
    if d.net_debt is not None:
        return d.net_debt
    if d.total_debt is not None and d.cash is not None:
        return d.total_debt - d.cash
    if d.total_debt is not None:
        return d.total_debt
    return None

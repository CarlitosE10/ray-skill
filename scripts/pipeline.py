"""
Pipeline orchestrator for Ray.

Flow:
  1. Load Snowball + Charlie JSONs (and optional portfolio).
  2. Validate ticker match and schema compatibility.
  3. Run DCF 3-scenarios → fair value.
  4. Compute MOS thresholds (MOAT-adjusted) → buy_below / sell_above.
  5. Run sync gate → list of conflicts.
  6. Compute conviction score.
  7. Determine BUY/HOLD/SELL.
  8. Compute time horizon and position sizing.
  9. Aggregate into RayDecision.
"""

from __future__ import annotations

from typing import Optional

from conviction import calc_conviction
from dcf import run_dcf
from decision import (
    determine_decision,
    determine_time_horizon,
    extract_key_drivers,
    extract_key_risks,
)
from inputs import (
    CharlieInput,
    PortfolioInput,
    SnowballInput,
)
from margin_of_safety import calc_margin_of_safety
from position_sizing import calc_position_sizing
from report import (
    DataQuality,
    RayDecision,
    RiskProfile,
    SCHEMA_VERSION,
)
from sync_gate import detect_conflicts


# Schema versions Ray accepts on the input side
ACCEPTED_SCHEMA_PREFIXES = ("1.",)  # any 1.x version


def _schema_compatible(version: Optional[str]) -> bool:
    if not version:
        return False
    return any(version.startswith(p) for p in ACCEPTED_SCHEMA_PREFIXES)


def run_pipeline(
    snowball: SnowballInput,
    charlie: CharlieInput,
    portfolio: Optional[PortfolioInput] = None,
    risk_profile: RiskProfile = "moderate",
) -> RayDecision:
    """The full Ray decision pipeline."""

    blocking_issues: list[str] = []
    warnings: list[str] = []

    # 1. Sanity checks
    if snowball.ticker.upper() != charlie.ticker.upper():
        blocking_issues.append(
            f"Ticker mismatch: Snowball='{snowball.ticker}', Charlie='{charlie.ticker}'"
        )

    snowball_compat = _schema_compatible(snowball.schema_version)
    charlie_compat = _schema_compatible(charlie.schema_version)
    schema_ok = snowball_compat and charlie_compat
    if not snowball_compat:
        warnings.append(
            f"Snowball schema_version '{snowball.schema_version}' is unrecognized "
            f"or missing — Ray expects 1.x.x"
        )
    if not charlie_compat:
        warnings.append(
            f"Charlie schema_version '{charlie.schema_version}' is unrecognized "
            f"or missing — Ray expects 1.x.x"
        )

    # If we have blocking issues, return early with INSUFFICIENT_DATA
    if blocking_issues:
        return RayDecision(
            ticker=snowball.ticker,
            company_name=snowball.company_name or charlie.company_name,
            sector=snowball.sector or charlie.sector,
            decision="INSUFFICIENT_DATA",
            decision_reasoning="Pipeline blocked: " + "; ".join(blocking_issues),
            current_price=snowball.current_price,
            data_quality=DataQuality(
                snowball_completeness_pct=snowball.data_quality.completeness_pct,
                charlie_completeness_pct=charlie.data_quality.completeness_pct,
                snowball_schema_version=snowball.schema_version,
                charlie_schema_version=charlie.schema_version,
                schema_compatible=schema_ok,
                warnings=warnings,
                blocking_issues=blocking_issues,
            ),
        )

    # 2. DCF
    dcf = run_dcf(snowball, charlie)
    fair_value = dcf.weighted_fair_value_per_share

    # 3. MOS
    mos = calc_margin_of_safety(charlie, fair_value, risk_profile=risk_profile)

    # 4. Sync gate
    conflicts = detect_conflicts(snowball, charlie)

    # 5. Conviction
    conviction = calc_conviction(
        snowball=snowball,
        charlie=charlie,
        conflicts=conflicts,
        current_price=snowball.current_price,
        fair_value=fair_value,
        buy_below=mos.buy_below,
        sell_above=mos.sell_above,
    )

    # 6. Decision
    decision, decision_reasoning = determine_decision(
        current_price=snowball.current_price,
        mos=mos,
        conviction=conviction,
    )

    # 7. Upside
    upside_pct: Optional[float] = None
    if snowball.current_price and fair_value and snowball.current_price > 0:
        upside_pct = (fair_value - snowball.current_price) / snowball.current_price * 100

    # 8. Time horizon
    horizon, horizon_reasoning = determine_time_horizon(charlie, upside_pct)

    # 9. Position sizing
    sizing = calc_position_sizing(
        decision=decision,
        upside_pct=upside_pct,
        conviction_score=conviction.weighted_score,
        portfolio=portfolio,
        risk_profile=risk_profile,
    )

    # 10. Drivers & risks
    drivers = extract_key_drivers(charlie)
    risks = extract_key_risks(snowball, charlie, conflicts)

    return RayDecision(
        ticker=snowball.ticker,
        company_name=snowball.company_name or charlie.company_name,
        sector=snowball.sector or charlie.sector,
        decision=decision,
        decision_reasoning=decision_reasoning,
        current_price=snowball.current_price,
        fair_value_per_share=fair_value,
        upside_pct=round(upside_pct, 2) if upside_pct is not None else None,
        dcf=dcf,
        margin_of_safety=mos,
        sync_gate_conflicts=conflicts,
        conviction=conviction,
        time_horizon=horizon,
        time_horizon_reasoning=horizon_reasoning,
        position_sizing=sizing,
        key_drivers=drivers,
        key_risks=risks,
        data_quality=DataQuality(
            snowball_completeness_pct=snowball.data_quality.completeness_pct,
            charlie_completeness_pct=charlie.data_quality.completeness_pct,
            snowball_schema_version=snowball.schema_version,
            charlie_schema_version=charlie.schema_version,
            schema_compatible=schema_ok,
            warnings=warnings,
            blocking_issues=[],
        ),
    )

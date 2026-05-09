"""
Position sizing.

Approach: a Kelly-fractional sizing, hard-capped by risk profile.

The Kelly criterion suggests bet size proportional to edge / odds. We
approximate edge as upside_pct (fair_value vs current_price) and apply a
quarter-Kelly factor (full Kelly is too aggressive for equity investing
with non-binary outcomes). Then we multiply by conviction/100 and clip at
a profile-specific cap.

Risk-profile caps (% of portfolio):
  conservative → 3.0%
  moderate     → 5.0%   (default)
  aggressive   → 8.0%

The output is a *suggestion*, not a prescription. Concentration risk,
existing exposure, and tax considerations are ignored — the user's
financial advisor should weigh those.

If the ticker already appears in the portfolio holdings, the sizing
recommendation is interpreted as the *target* total weight, with a
note explaining the implied buy/trim.
"""

from __future__ import annotations

from typing import Optional

from inputs import PortfolioInput
from report import PositionSizing, RiskProfile

# ─────────────────────────────────────────────────────────────────────────────
# Profile parameters
# ─────────────────────────────────────────────────────────────────────────────

CAP_BY_PROFILE_PCT = {
    "conservative": 3.0,
    "moderate": 5.0,
    "aggressive": 8.0,
}

KELLY_FRACTION = 0.25  # quarter-Kelly


def _kelly_pct(upside_decimal: float) -> float:
    """
    Approximation: assume upside_decimal is the expected return; assume an
    equally probable downside of equivalent magnitude (symmetric). Kelly
    with these is roughly upside_decimal × 0.5 (very loose proxy).
    Multiply by KELLY_FRACTION and convert to %.
    """
    if upside_decimal <= 0:
        return 0.0
    raw = upside_decimal * 0.5  # rough Kelly with symmetric outcome assumption
    return raw * KELLY_FRACTION * 100.0


def calc_position_sizing(
    decision: str,
    upside_pct: Optional[float],
    conviction_score: float,
    portfolio: Optional[PortfolioInput] = None,
    risk_profile: RiskProfile = "moderate",
) -> PositionSizing:
    """Compute the suggested position size."""

    cap = CAP_BY_PROFILE_PCT.get(risk_profile, 5.0)

    if decision != "BUY" or upside_pct is None or upside_pct <= 0:
        # No new position recommended
        return PositionSizing(
            risk_profile=risk_profile,
            cap_pct=cap,
            kelly_raw_pct=None,
            suggested_pct_of_portfolio=0.0,
            rationale=(
                "Decision is not BUY, or upside is non-positive — no new allocation suggested. "
                "If currently held, see the decision section for trim/hold guidance."
            ),
        )

    # Convert upside from pct (e.g., 12.5) to decimal (0.125)
    upside_decimal = upside_pct / 100.0

    kelly_raw = _kelly_pct(upside_decimal)

    # Apply conviction scaling
    conviction_factor = max(0.0, min(1.0, conviction_score / 100.0))
    suggested = kelly_raw * conviction_factor

    # Apply hard cap
    suggested_clipped = min(suggested, cap)

    rationale_parts = [
        f"Quarter-Kelly raw: {kelly_raw:.2f}%",
        f"× conviction {conviction_score:.0f}/100 = {suggested:.2f}%",
    ]
    if suggested > cap:
        rationale_parts.append(
            f"capped at {cap:.1f}% by '{risk_profile}' profile"
        )

    suggested_dollars = None
    if portfolio and portfolio.total_value:
        suggested_dollars = portfolio.total_value * (suggested_clipped / 100.0)
        rationale_parts.append(
            f"≈ ${suggested_dollars:,.0f} on a ${portfolio.total_value:,.0f} portfolio"
        )

    return PositionSizing(
        risk_profile=risk_profile,
        cap_pct=cap,
        kelly_raw_pct=round(kelly_raw, 2),
        suggested_pct_of_portfolio=round(suggested_clipped, 2),
        suggested_dollar_amount=round(suggested_dollars, 2) if suggested_dollars else None,
        rationale="; ".join(rationale_parts) + ".",
    )

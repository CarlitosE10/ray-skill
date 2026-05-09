"""
Margin of Safety calculator with MOAT adjustment.

Buffett's central idea: the price you pay must be materially below your
estimate of fair value, to absorb being wrong. The size of that cushion
depends on how confident you are about the durability of the business —
which is what Charlie's MOAT rating captures.

Mapping:
  very_strong  → MOS 10%   (exceptional moats; smaller cushion needed)
  strong       → MOS 15%
  neutral      → MOS 20%   (default)
  weak         → MOS 25%
  very_weak    → MOS 30%   (no moat / disappearing moat; need a large cushion)
  unknown      → MOS 25%   (when MOAT couldn't be assessed, lean conservative)

The risk profile (conservative / moderate / aggressive) adds an additional
adjustment of +5pp / 0 / -3pp respectively. Conservative investors want a
bigger cushion across the board; aggressive investors accept a smaller one.

Sell premium is symmetric in concept: how much above fair value before we
declare overvaluation. Default 25%; not MOAT-adjusted because the trigger
to sell is broadly the same regardless of moat (a great business at 30%
above fair value is still rich).
"""

from __future__ import annotations

from typing import Optional

from inputs import CharlieInput
from report import MarginOfSafety, RiskProfile

# ─────────────────────────────────────────────────────────────────────────────
# Mappings
# ─────────────────────────────────────────────────────────────────────────────

MOS_BY_MOAT = {
    "very_strong": 0.10,
    "strong": 0.15,
    "neutral": 0.20,
    "weak": 0.25,
    "very_weak": 0.30,
}

DEFAULT_MOS = 0.20  # used when moat is missing
DEFAULT_SELL_PREMIUM = 0.25

RISK_PROFILE_ADJUSTMENT_PP = {
    "conservative": 5,  # +5pp on top of moat-derived MOS
    "moderate": 0,
    "aggressive": -3,
}


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def calc_margin_of_safety(
    charlie: CharlieInput,
    fair_value: Optional[float],
    risk_profile: RiskProfile = "moderate",
    sell_premium: float = DEFAULT_SELL_PREMIUM,
) -> MarginOfSafety:
    """Compute MOS thresholds from MOAT + risk profile."""

    moat = (charlie.moat.moat_strength or "unknown").lower()
    base_mos = MOS_BY_MOAT.get(moat, DEFAULT_MOS)

    adj_pp = RISK_PROFILE_ADJUSTMENT_PP.get(risk_profile, 0)
    applied_mos = _clip(base_mos + adj_pp / 100.0, 0.05, 0.45)

    buy_below = fair_value * (1 - applied_mos) if fair_value else None
    sell_above = fair_value * (1 + sell_premium) if fair_value else None

    reasoning_parts = []
    if moat in MOS_BY_MOAT:
        reasoning_parts.append(f"MOAT '{moat}' → base MOS {base_mos * 100:.0f}%")
    else:
        reasoning_parts.append(
            f"MOAT '{moat}' (unrecognized or missing) → default MOS {DEFAULT_MOS * 100:.0f}%"
        )
    if adj_pp != 0:
        sign = "+" if adj_pp > 0 else ""
        reasoning_parts.append(f"risk profile '{risk_profile}': {sign}{adj_pp}pp")
    reasoning_parts.append(f"applied MOS = {applied_mos * 100:.0f}%")

    return MarginOfSafety(
        moat_input=moat if moat in MOS_BY_MOAT else "unknown",  # type: ignore
        base_mos_pct=base_mos,
        applied_mos_pct=applied_mos,
        sell_premium_pct=sell_premium,
        buy_below=buy_below,
        sell_above=sell_above,
        reasoning="; ".join(reasoning_parts),
    )

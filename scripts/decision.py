"""
Decision logic — convert price + thresholds + conviction into BUY/HOLD/SELL.

Rules (in order):

1. If conviction is very_low → INSUFFICIENT_DATA, regardless of price.
   (We don't pretend to know the answer when the inputs don't support one.)

2. If current_price <= buy_below → BUY.
3. If current_price >= sell_above → SELL.
4. Otherwise → HOLD.

The decision is also annotated with a time horizon recommendation, derived
from MOAT durability + sector maturity + valuation gap.
"""

from __future__ import annotations

from typing import Optional

from inputs import CharlieInput
from report import (
    ConvictionBreakdown,
    Decision,
    MarginOfSafety,
    TimeHorizon,
)


def determine_decision(
    current_price: Optional[float],
    mos: Optional[MarginOfSafety],
    conviction: Optional[ConvictionBreakdown],
) -> tuple[Decision, str]:
    """Return (decision, reasoning)."""

    if conviction is not None and conviction.level == "very_low":
        return (
            "INSUFFICIENT_DATA",
            "Conviction score is very low — input data quality or coherence "
            "issues prevent a defensible recommendation. Review the warnings "
            "in data_quality and the sync gate conflicts before acting.",
        )

    if current_price is None or mos is None or mos.buy_below is None or mos.sell_above is None:
        return (
            "INSUFFICIENT_DATA",
            "Missing price or fair value — cannot determine buy/sell zones.",
        )

    if current_price <= mos.buy_below:
        gap_pct = (mos.buy_below - current_price) / mos.buy_below * 100
        return (
            "BUY",
            f"Current price ${current_price:.2f} is {gap_pct:.1f}% below the buy "
            f"threshold of ${mos.buy_below:.2f} (fair value × (1 - "
            f"{mos.applied_mos_pct * 100:.0f}% MOS)).",
        )

    if current_price >= mos.sell_above:
        gap_pct = (current_price - mos.sell_above) / mos.sell_above * 100
        return (
            "SELL",
            f"Current price ${current_price:.2f} is {gap_pct:.1f}% above the sell "
            f"threshold of ${mos.sell_above:.2f} (fair value × (1 + "
            f"{mos.sell_premium_pct * 100:.0f}% premium)).",
        )

    return (
        "HOLD",
        f"Current price ${current_price:.2f} sits within the HOLD band "
        f"[${mos.buy_below:.2f}, ${mos.sell_above:.2f}]. Wait for entry below "
        f"the buy threshold.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Time horizon
# ─────────────────────────────────────────────────────────────────────────────


def determine_time_horizon(
    charlie: CharlieInput,
    upside_pct: Optional[float],
) -> tuple[TimeHorizon, str]:
    """
    Time horizon is the period over which the thesis is expected to play out.
    Heuristics:
      - Very strong moat (>15y durability) + larger upside → 5-10y
      - Strong moat + growth/mature sector → 3-5y
      - Weak moat → 1-3y (regardless of upside; wait for value to emerge sooner)
      - Highly cyclical → 1-3y (tied to cycle)
      - Default → 3-5y
    """
    moat_strength = (charlie.moat.moat_strength or "").lower()
    durability = charlie.moat.moat_durability_years
    maturity = (charlie.sector_outlook.sector_maturity or "").lower()
    cyclicality = (charlie.macro_environment.cyclicality or "").lower()

    if cyclicality == "highly_cyclical":
        return (
            "1-3y",
            "Highly cyclical business — thesis tied to commodity / capex cycle; medium-horizon framing.",
        )

    if moat_strength in ("weak", "very_weak"):
        return (
            "1-3y",
            "Weak moat — value should be realized in the medium term, not held for compounding.",
        )

    if moat_strength == "very_strong" and durability and durability >= 15:
        return (
            "5-10y",
            f"Very strong moat with ~{durability}y durability — long-horizon compounder.",
        )

    if moat_strength == "strong":
        return (
            "3-5y",
            "Strong moat — typical multi-year compounding horizon.",
        )

    if maturity == "growth":
        return ("3-5y", "Sector in growth phase — multi-year horizon to capture expansion.")

    return ("3-5y", "Default horizon. No specific signal pulling shorter or longer.")


# ─────────────────────────────────────────────────────────────────────────────
# Drivers and risks for the user-facing summary
# ─────────────────────────────────────────────────────────────────────────────


def extract_key_drivers(charlie: CharlieInput, max_items: int = 4) -> list[str]:
    """Pick the top forward-looking drivers from Charlie's catalysts."""
    out = []
    for c in charlie.catalysts[:max_items]:
        likelihood = c.likelihood or "neutral"
        out.append(f"[{likelihood}] {c.description}")
    if not out and charlie.moat.moat_reasoning:
        out.append(f"Moat thesis: {charlie.moat.moat_reasoning}")
    return out


def extract_key_risks(
    snowball, charlie: CharlieInput, sync_conflicts, max_items: int = 5
) -> list[str]:
    """Aggregate qualitative risks + Snowball-specific risks + sync conflicts."""
    out = []
    # Charlie's qualitative risks
    for r in charlie.qualitative_risks[:max_items]:
        cat = r.category or "other"
        sev = r.severity or "neutral"
        out.append(f"[{cat}|{sev}] {r.description}")

    # Sync gate criticals always make the cut
    for c in sync_conflicts:
        if c.severity == "critical":
            out.append(f"[sync_critical] {c.pattern}: {c.description[:120]}")

    return out[:max_items]

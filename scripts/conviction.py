"""
Conviction scoring.

Conviction is Ray's confidence in the decision. It is NOT the strength of
the signal — a strong BUY signal with low conviction means "the math says
buy but I'm not sure I trust the inputs enough to size aggressively."

Composition (weights):
  40% — Quantitative confidence (Snowball completeness)
  30% — Qualitative score (Charlie qualitative_score)
  15% — Distance to threshold (how decisively the price is below buy_below
        or above sell_above; HOLD decisions inherently have lower this
        component)
  15% — Coherence (inverse of sync gate penalties; agreement between
        Snowball and Charlie)

Final score 0-100, mapped to 5 buckets:
  >= 85   very_high
  70-84   high
  50-69   moderate
  30-49   low
  < 30    very_low (treated as INSUFFICIENT_DATA in the decision layer)
"""

from __future__ import annotations

from typing import Optional

from inputs import CharlieInput, SnowballInput
from report import ConvictionBreakdown, ConvictionLevel, SyncGateConflict


# ─────────────────────────────────────────────────────────────────────────────
# Component weights (must sum to 1.0)
# ─────────────────────────────────────────────────────────────────────────────

W_QUANT = 0.40
W_QUAL = 0.30
W_DISTANCE = 0.15
W_COHERENCE = 0.15


def _bucket(score: float) -> ConvictionLevel:
    if score >= 85:
        return "very_high"
    if score >= 70:
        return "high"
    if score >= 50:
        return "moderate"
    if score >= 30:
        return "low"
    return "very_low"


def _distance_score(
    current_price: Optional[float],
    fair_value: Optional[float],
    buy_below: Optional[float],
    sell_above: Optional[float],
) -> float:
    """
    100 = price decisively below buy_below or above sell_above (clear signal).
    50  = price exactly at fair_value (HOLD by default).
    0   = price exactly at the threshold edge (ambiguous).
    """
    if not current_price or not fair_value:
        return 50.0  # neutral

    # If clearly in BUY zone (price below buy_below) or SELL zone (above sell_above)
    if buy_below is not None and current_price <= buy_below:
        # Score scales with how far below — 50 at threshold, 100 at half of buy_below
        depth = (buy_below - current_price) / buy_below
        return min(100.0, 50.0 + depth * 200.0)
    if sell_above is not None and current_price >= sell_above:
        depth = (current_price - sell_above) / sell_above
        return min(100.0, 50.0 + depth * 200.0)

    # In HOLD zone — proximity to nearest threshold matters less; cap at 50
    distances = []
    if buy_below is not None:
        distances.append(abs(current_price - buy_below) / fair_value)
    if sell_above is not None:
        distances.append(abs(current_price - sell_above) / fair_value)
    if not distances:
        return 50.0
    # Closer to a threshold = lower distance score (less decisive HOLD)
    nearest = min(distances)
    return max(20.0, 50.0 - nearest * 200.0)


def _coherence_score(conflicts: list[SyncGateConflict]) -> float:
    """100 = no conflicts; falls 1pt per pp of penalty."""
    total_penalty = sum(c.conviction_penalty_pp for c in conflicts)
    return max(0.0, 100.0 - total_penalty * 1.5)


def calc_conviction(
    snowball: SnowballInput,
    charlie: CharlieInput,
    conflicts: list[SyncGateConflict],
    current_price: Optional[float],
    fair_value: Optional[float],
    buy_below: Optional[float],
    sell_above: Optional[float],
) -> ConvictionBreakdown:
    """Compute the full conviction breakdown."""

    # 1. Quantitative confidence
    quant_raw = snowball.data_quality.completeness_pct
    quant = quant_raw if quant_raw is not None else 50.0

    # 2. Qualitative score
    qual = charlie.qualitative_score if charlie.qualitative_score is not None else 50.0

    # 3. Distance to threshold
    distance = _distance_score(current_price, fair_value, buy_below, sell_above)

    # 4. Coherence (inverse of sync gate)
    coherence = _coherence_score(conflicts)

    # Weighted
    weighted = quant * W_QUANT + qual * W_QUAL + distance * W_DISTANCE + coherence * W_COHERENCE

    # If either source is missing significant data, downweight
    if quant_raw is None or charlie.qualitative_score is None:
        weighted *= 0.85

    weighted = max(0.0, min(100.0, weighted))

    return ConvictionBreakdown(
        quantitative_confidence=round(quant, 1),
        qualitative_score=round(qual, 1),
        distance_to_threshold=round(distance, 1),
        coherence=round(coherence, 1),
        weighted_score=round(weighted, 1),
        level=_bucket(weighted),
    )

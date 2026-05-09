"""
Sync Gate — detect conflicts between Snowball and Charlie.

The two analyses are complementary, not redundant. When they disagree, the
disagreement itself is information. Ray flags these patterns, attaches a
conviction penalty, and surfaces them to the user.

Patterns detected (v1):

1. VALUE TRAP: Snowball says cheap valuation + good ratios, Charlie says
   weak moat + cautious sector.
   → "Quantitative looks attractive but qualitative is weak. Classic
       value-trap setup."

2. QUALITY OVERPRICED: Snowball says expensive valuation + overbought
   technicals, Charlie says very_strong moat + bullish sector.
   → "Excellent business but rich price. Wait for pullback."

3. MOAT EROSION: Snowball says deteriorating margins (margin compression,
   declining ROE), Charlie says strong/very_strong moat.
   → "Margin trends suggest moat may be eroding faster than the qualitative
       assessment captures. Re-examine the moat thesis."

4. INSIDER DISCONNECT: Charlie says strong moat + constructive outlook,
   but Snowball shows large insider net selling.
   → "Insiders are selling into apparent quality. Possible dilution,
       internal information, or scheduled liquidation."

5. SECTOR HEADWIND vs COMPANY STRENGTH: Snowball says strong fundamentals,
   Charlie says cautious/bearish sector outlook.
   → "Company-level strength against a soft sector. Elevated execution risk."

6. CYCLICAL TRAP: Charlie says highly_cyclical + late cycle (sector
   underperforming), Snowball shows record-high margins.
   → "Highly cyclical business at peak margins — earnings may have already
       peaked."

Each pattern carries a conviction penalty. Total penalty caps at 30pp so a
single ticker with multiple conflicts doesn't drop to zero conviction
mechanically — multiple conflicts justify a manual review, not a forced HOLD.
"""

from __future__ import annotations

from inputs import CharlieInput, SnowballInput
from report import SyncGateConflict


# ─────────────────────────────────────────────────────────────────────────────
# Helper predicates
# ─────────────────────────────────────────────────────────────────────────────


def _is_strong_moat(charlie: CharlieInput) -> bool:
    return (charlie.moat.moat_strength or "").lower() in ("strong", "very_strong")


def _is_weak_moat(charlie: CharlieInput) -> bool:
    return (charlie.moat.moat_strength or "").lower() in ("weak", "very_weak")


def _sector_negative(charlie: CharlieInput) -> bool:
    return (charlie.sector_outlook.outlook or "").lower() in ("cautious", "bearish")


def _sector_positive(charlie: CharlieInput) -> bool:
    return (charlie.sector_outlook.outlook or "").lower() in ("constructive", "bullish")


def _looks_cheap(snowball: SnowballInput) -> bool:
    """Rough heuristic. Cheap if multiple of these fire:
    P/E < 15, EV/EBITDA < 10, FCF yield > 6%."""
    flags = 0
    if snowball.pe_ratio is not None and 0 < snowball.pe_ratio < 15:
        flags += 1
    if snowball.ev_ebitda is not None and 0 < snowball.ev_ebitda < 10:
        flags += 1
    if snowball.fcf_yield is not None and snowball.fcf_yield > 0.06:
        flags += 1
    return flags >= 2


def _looks_expensive(snowball: SnowballInput) -> bool:
    flags = 0
    if snowball.pe_ratio is not None and snowball.pe_ratio > 30:
        flags += 1
    if snowball.ev_ebitda is not None and snowball.ev_ebitda > 20:
        flags += 1
    if snowball.fcf_yield is not None and 0 < snowball.fcf_yield < 0.025:
        flags += 1
    return flags >= 2


def _technicals_overbought(snowball: SnowballInput) -> bool:
    if snowball.rsi_14 is not None and snowball.rsi_14 > 70:
        return True
    if snowball.pct_from_52w_high is not None and snowball.pct_from_52w_high > -0.03:
        return True
    return False


def _margins_deteriorating(snowball: SnowballInput) -> bool:
    """Approximation: low operating margin AND negative revenue growth.
    A real implementation would diff margins YoY; we approximate from the
    Snowball summary fields."""
    if snowball.operating_margin is None:
        return False
    if snowball.revenue_growth_yoy is None:
        return False
    return snowball.operating_margin < 0.08 and snowball.revenue_growth_yoy < 0.0


def _insiders_dumping(snowball: SnowballInput) -> bool:
    """Net insider selling materially negative."""
    if snowball.insider_net_buy_3m is None:
        return False
    return snowball.insider_net_buy_3m < -1_000_000  # > $1m net selling


def _is_highly_cyclical(charlie: CharlieInput) -> bool:
    return (charlie.macro_environment.cyclicality or "").lower() == "highly_cyclical"


def _peak_margins(snowball: SnowballInput) -> bool:
    """Approximation: very high operating margin (>20%) for a cyclical."""
    return snowball.operating_margin is not None and snowball.operating_margin > 0.20


# ─────────────────────────────────────────────────────────────────────────────
# Rule engine
# ─────────────────────────────────────────────────────────────────────────────


PATTERNS = [
    {
        "name": "value_trap",
        "predicate": lambda s, c: _looks_cheap(s) and _is_weak_moat(c) and _sector_negative(c),
        "description": (
            "Snowball flags cheap valuation but Charlie shows weak moat and a cautious sector "
            "outlook. Classic value-trap setup — the cheapness may be deserved."
        ),
        "severity": "warning",
        "penalty_pp": 12,
    },
    {
        "name": "quality_overpriced",
        "predicate": lambda s, c: _looks_expensive(s) and _is_strong_moat(c) and _sector_positive(c),
        "description": (
            "Excellent business by qualitative measures, but Snowball flags expensive valuation. "
            "Quality at a price — likely no margin of safety; consider waiting for a pullback."
        ),
        "severity": "info",
        "penalty_pp": 5,
    },
    {
        "name": "moat_erosion_signal",
        "predicate": lambda s, c: _is_strong_moat(c) and _margins_deteriorating(s),
        "description": (
            "Charlie rates the moat as strong, but Snowball shows margin compression with "
            "negative revenue growth. The qualitative thesis may be lagging the data — re-examine "
            "the moat assessment."
        ),
        "severity": "critical",
        "penalty_pp": 15,
    },
    {
        "name": "insider_disconnect",
        "predicate": lambda s, c: _is_strong_moat(c) and _insiders_dumping(s),
        "description": (
            "Charlie flags a strong moat, but insiders have been net sellers in the last 3 months. "
            "Possible benign explanations (scheduled, diversification) but worth verifying."
        ),
        "severity": "warning",
        "penalty_pp": 8,
    },
    {
        "name": "sector_headwind_vs_strength",
        "predicate": lambda s, c: not _looks_expensive(s)
        and _sector_negative(c)
        and not _is_weak_moat(c),
        "description": (
            "Company-level strength against a cautious / bearish sector backdrop. Even good "
            "operators face structural headwinds — execution risk is elevated."
        ),
        "severity": "info",
        "penalty_pp": 4,
    },
    {
        "name": "cyclical_peak_trap",
        "predicate": lambda s, c: _is_highly_cyclical(c) and _peak_margins(s),
        "description": (
            "Charlie classifies the business as highly cyclical, while Snowball shows operating "
            "margins above 20%. Earnings may be at a cyclical peak — normalize before valuing."
        ),
        "severity": "warning",
        "penalty_pp": 10,
    },
]

PENALTY_CAP_PP = 30


def detect_conflicts(snowball: SnowballInput, charlie: CharlieInput) -> list[SyncGateConflict]:
    """Run every pattern and return all that fire."""
    conflicts: list[SyncGateConflict] = []
    for p in PATTERNS:
        try:
            fires = bool(p["predicate"](snowball, charlie))
        except Exception:
            fires = False
        if fires:
            conflicts.append(
                SyncGateConflict(
                    pattern=p["name"],
                    description=p["description"],
                    severity=p["severity"],  # type: ignore
                    conviction_penalty_pp=p["penalty_pp"],
                )
            )
    return conflicts


def total_penalty(conflicts: list[SyncGateConflict]) -> float:
    """Sum penalties, capped."""
    raw = sum(c.conviction_penalty_pp for c in conflicts)
    return min(raw, PENALTY_CAP_PP)

"""
DCF engine — three-scenario fair value with Gordon-Shapiro terminal.

The DCF flow:
  1. Compute WACC from beta (Snowball), live risk-free rate (^TNX), and
     equity risk premium (5.0% default).
  2. For each of three scenarios (pessimistic / base / optimistic), discount
     a 10-year FCF stream + Gordon terminal value back to present.
  3. Subtract net debt to get equity value, divide by shares outstanding
     to get fair value per share.
  4. Weight the three scenarios (default 25/50/25) to get the blended
     fair value.

Growth assumptions:
  - Phase 1 (years 1-5): base = Snowball revenue/FCF CAGR + Charlie's
    suggested_adjustment_pct (in pp).
  - Phase 2 (years 6-10): linear fade from phase-1 rate down to terminal.
  - Terminal: 2.5% base (~long-run nominal GDP).

Pessimistic / optimistic deltas applied to base:
  - Pessimistic: phase 1 × 0.50, terminal 2.0%, WACC × 1.10
  - Optimistic:  phase 1 × 1.30 (capped at 25%), terminal 3.0%, WACC × 0.95
"""

from __future__ import annotations

from typing import Optional

import yfinance as yf

from inputs import CharlieInput, SnowballInput, resolve_net_debt
from report import DCFResult, DCFScenario


# ─────────────────────────────────────────────────────────────────────────────
# WACC
# ─────────────────────────────────────────────────────────────────────────────


DEFAULT_RISK_FREE = 0.043  # fallback if ^TNX fetch fails
EQUITY_RISK_PREMIUM = 0.050
DEFAULT_BETA = 1.0


def fetch_risk_free_rate() -> float:
    """Fetch the 10Y Treasury yield via ^TNX. Falls back to a sensible default."""
    try:
        tk = yf.Ticker("^TNX")
        hist = tk.history(period="5d", auto_adjust=False)
        if hist is not None and not hist.empty and "Close" in hist.columns:
            # ^TNX is quoted as the yield × 10 (e.g., 43.0 = 4.30%)
            latest = float(hist["Close"].iloc[-1])
            return latest / 100.0
    except Exception:
        pass
    return DEFAULT_RISK_FREE


def calc_wacc(beta: Optional[float], rf: Optional[float] = None, erp: float = EQUITY_RISK_PREMIUM) -> float:
    """
    Cost of equity via CAPM. We use cost of equity as a proxy for WACC for
    typical-leverage firms — a simplification. Companies with very high debt
    weights would warrant a full debt-weighted WACC; the sensitivity notes
    flag this.
    """
    rf = rf if rf is not None else fetch_risk_free_rate()
    b = beta if beta is not None and beta > 0 else DEFAULT_BETA
    return rf + b * erp


# ─────────────────────────────────────────────────────────────────────────────
# Growth assumptions
# ─────────────────────────────────────────────────────────────────────────────


# Hard caps to keep the DCF from blowing up on outliers
MAX_PHASE1_GROWTH = 0.25
MIN_PHASE1_GROWTH = -0.05
TERMINAL_BASE = 0.025
TERMINAL_PESSIMISTIC = 0.020
TERMINAL_OPTIMISTIC = 0.030


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def derive_base_growth(snowball: SnowballInput, charlie: CharlieInput) -> float:
    """
    Compose the base-case growth rate from Snowball CAGRs + Charlie adjustment.
    Prefers FCF CAGR over revenue CAGR; falls back to revenue growth YoY.
    """
    d = snowball.dcf_inputs
    base = d.fcf_cagr_3y or d.revenue_cagr_3y or snowball.revenue_growth_yoy or 0.05

    adj_pp = charlie.growth_adjustment.suggested_adjustment_pct or 0.0
    base += adj_pp / 100.0  # adjustment is in pp; convert to decimal

    return _clip(base, MIN_PHASE1_GROWTH, MAX_PHASE1_GROWTH)


# ─────────────────────────────────────────────────────────────────────────────
# Single-scenario DCF
# ─────────────────────────────────────────────────────────────────────────────


def _run_scenario(
    fcf0: float,
    growth_phase1: float,
    growth_terminal: float,
    wacc: float,
    net_debt: float,
    shares: float,
    years_phase1: int = 5,
    years_phase2: int = 5,
) -> tuple[float, float]:
    """
    Run one DCF scenario.
    Returns: (enterprise_value, fair_value_per_share)
    """
    # WACC must exceed terminal growth or Gordon explodes
    if wacc <= growth_terminal + 0.005:
        wacc = growth_terminal + 0.01

    # Phase 1: constant growth
    fcf_t = fcf0
    pv = 0.0
    for t in range(1, years_phase1 + 1):
        fcf_t = fcf_t * (1 + growth_phase1)
        pv += fcf_t / ((1 + wacc) ** t)

    # Phase 2: linear fade from phase1 down to terminal
    if years_phase2 > 0:
        for t in range(1, years_phase2 + 1):
            frac = t / years_phase2
            fade_growth = growth_phase1 * (1 - frac) + growth_terminal * frac
            fcf_t = fcf_t * (1 + fade_growth)
            pv += fcf_t / ((1 + wacc) ** (years_phase1 + t))

    # Terminal value at end of horizon
    fcf_terminal_next = fcf_t * (1 + growth_terminal)
    terminal_value = fcf_terminal_next / (wacc - growth_terminal)
    pv_terminal = terminal_value / ((1 + wacc) ** (years_phase1 + years_phase2))

    enterprise_value = pv + pv_terminal
    equity_value = enterprise_value - net_debt
    fair_value = equity_value / shares if shares > 0 else 0.0
    return enterprise_value, fair_value


# ─────────────────────────────────────────────────────────────────────────────
# Three-scenario DCF
# ─────────────────────────────────────────────────────────────────────────────


def run_dcf(
    snowball: SnowballInput,
    charlie: CharlieInput,
    weights: tuple[float, float, float] = (0.25, 0.50, 0.25),
) -> DCFResult:
    """Run all three DCF scenarios and produce the combined result."""

    d = snowball.dcf_inputs
    fcf0 = d.free_cash_flow
    shares = d.shares_outstanding
    net_debt = resolve_net_debt(snowball) or 0.0

    notes: list[str] = []

    # If we can't run DCF, return a stub
    if not fcf0 or fcf0 <= 0:
        notes.append("FCF unavailable or non-positive — DCF skipped.")
        return DCFResult(
            fcf_starting_point=fcf0,
            shares_outstanding=shares,
            net_debt=net_debt,
            sensitivity_notes=notes,
        )
    if not shares or shares <= 0:
        notes.append("Shares outstanding unavailable — fair value per share cannot be computed.")
        return DCFResult(
            fcf_starting_point=fcf0,
            shares_outstanding=shares,
            net_debt=net_debt,
            sensitivity_notes=notes,
        )

    rf = fetch_risk_free_rate()
    base_wacc = calc_wacc(d.beta, rf)
    base_growth = derive_base_growth(snowball, charlie)

    notes.append(
        f"WACC (base): {base_wacc * 100:.2f}% | risk-free {rf * 100:.2f}% | beta "
        f"{d.beta if d.beta else f'default {DEFAULT_BETA}'}"
    )
    notes.append(f"Phase-1 growth (base): {base_growth * 100:.2f}%")

    # Scenario configs
    configs = [
        {
            "name": "pessimistic",
            "g1": _clip(base_growth * 0.50, MIN_PHASE1_GROWTH, MAX_PHASE1_GROWTH),
            "gt": TERMINAL_PESSIMISTIC,
            "wacc": base_wacc * 1.10,
            "weight": weights[0],
        },
        {
            "name": "base",
            "g1": base_growth,
            "gt": TERMINAL_BASE,
            "wacc": base_wacc,
            "weight": weights[1],
        },
        {
            "name": "optimistic",
            "g1": _clip(base_growth * 1.30, MIN_PHASE1_GROWTH, MAX_PHASE1_GROWTH),
            "gt": TERMINAL_OPTIMISTIC,
            "wacc": base_wacc * 0.95,
            "weight": weights[2],
        },
    ]

    scenarios: list[DCFScenario] = []
    weighted_fv = 0.0
    for cfg in configs:
        g1 = cfg["g1"]
        gt = cfg["gt"]
        wacc = cfg["wacc"]
        ev, fv = _run_scenario(fcf0, g1, gt, wacc, net_debt, shares)
        weighted_fv += fv * cfg["weight"]
        # Phase 2 growth midpoint for display
        g2_avg = (g1 + gt) / 2.0
        scenarios.append(
            DCFScenario(
                name=cfg["name"],  # type: ignore
                growth_phase1_pct=g1,
                growth_phase2_pct=g2_avg,
                terminal_growth_pct=gt,
                wacc_pct=wacc,
                fair_value_per_share=fv,
                enterprise_value=ev,
                weight=cfg["weight"],
            )
        )

    # Sensitivity flag
    if d.beta is None:
        notes.append("Beta unavailable — used default β=1.0; consider widening MOS.")
    if abs(net_debt) < 1:
        notes.append("Net debt is zero — DCF treats equity value = enterprise value.")
    if base_growth >= MAX_PHASE1_GROWTH - 0.001:
        notes.append(
            f"Phase-1 growth capped at {MAX_PHASE1_GROWTH * 100:.0f}% — historical "
            "CAGR exceeded the cap, indicating high-growth profile."
        )

    return DCFResult(
        fcf_starting_point=fcf0,
        shares_outstanding=shares,
        net_debt=net_debt,
        scenarios=scenarios,
        weighted_fair_value_per_share=weighted_fv,
        sensitivity_notes=notes,
    )

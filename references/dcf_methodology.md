# DCF Methodology

Ray uses a **three-scenario DCF with Gordon-Shapiro terminal**. The valuation flow is built to be transparent and reproducible — every assumption is documented and surfaced in the output.

## Why three scenarios

A single point estimate gives a false sense of precision. Three scenarios force explicit thinking about distribution:

- **Pessimistic (25% weight)** — what if growth disappoints, the moat erodes, or competition compresses margins?
- **Base (50% weight)** — the central estimate, anchored on Snowball's CAGRs adjusted for Charlie's qualitative judgment.
- **Optimistic (25% weight)** — what if catalysts fire, the moat deepens, or sector tailwinds accelerate?

The blended fair value is a probability-weighted average. The user can read the spread to gauge how reliant the valuation is on any single scenario.

## Inputs Ray uses

From **Snowball** (the quantitative agent):
- `dcf_inputs.free_cash_flow` — the starting FCF (most recent annual)
- `dcf_inputs.revenue_cagr_3y` and `dcf_inputs.fcf_cagr_3y` — historical growth
- `dcf_inputs.beta` — for WACC calculation
- `dcf_inputs.shares_outstanding` — for per-share fair value
- `dcf_inputs.net_debt` (or `total_debt - cash`) — to convert EV to equity value

From **Charlie** (the qualitative agent):
- `growth_adjustment.suggested_adjustment_pct` — pp delta to apply to base growth
- `moat.moat_strength` — used downstream for MOS, not directly in DCF

From **live data** (yfinance):
- 10-year Treasury yield (`^TNX`) — the risk-free rate

## WACC

Ray uses **CAPM cost of equity as a proxy for WACC**:

```
cost_of_equity = risk_free + beta × equity_risk_premium
```

- `risk_free` = current 10Y Treasury yield (live; fallback 4.3%)
- `equity_risk_premium` = 5.0% (standard academic estimate; 4.5–6.0% is the common range)
- `beta` = from Snowball; default 1.0 if missing

For typical-leverage firms, cost of equity ≈ WACC. For very high-debt or very low-debt firms this is a simplification; a sensitivity note flags it. A future v2 may compute a fully debt-weighted WACC.

## Growth assumptions

### Phase 1 (years 1–5)

```
base_growth = max(MIN, min(MAX,
    (Snowball.fcf_cagr_3y or revenue_cagr_3y or revenue_growth_yoy or 0.05)
    + Charlie.growth_adjustment.suggested_adjustment_pct / 100
))
```

- Min cap: −5% (no business is modeled with permanent decline in the base case)
- Max cap: +25% (no business sustains 30%+ growth in a 5-year DCF without distortion)

### Phase 2 (years 6–10)

Linear fade from `phase_1_growth` down to `terminal_growth`. This reflects the empirical reality that high growth is rarely sustained for a full decade.

### Terminal (perpetual)

Gordon-Shapiro:

```
TV = FCF_year_11 / (WACC − terminal_growth)
```

The base case uses 2.5% terminal growth — anchored on long-run nominal GDP. WACC must exceed terminal growth or the formula explodes; Ray adds 1pp guard if needed.

## Scenario deltas

| Parameter | Pessimistic | Base | Optimistic |
|---|---|---|---|
| Phase-1 growth | base × 0.50 | base | base × 1.30 (capped at 25%) |
| Terminal growth | 2.0% | 2.5% | 3.0% |
| WACC | base × 1.10 | base | base × 0.95 |
| Weight | 25% | 50% | 25% |

Why these deltas? They reflect plausible but not extreme outcomes. The optimistic case is bounded by the same 25% cap as the base case, so it can't compound a high-growth assumption further.

## Per-share fair value

For each scenario:

```
PV_FCFs = sum( FCF_t / (1 + WACC)^t  for t in 1..10 )
TV      = FCF_11 / (WACC − terminal_growth)
PV_TV   = TV / (1 + WACC)^10
EV      = PV_FCFs + PV_TV
Equity  = EV − net_debt
FV/sh   = Equity / shares_outstanding
```

The blended fair value is `Σ (FV/sh × weight)` across scenarios.

## What Ray does NOT do (yet)

- **No reverse-DCF.** Ray does not back-solve for the implied growth rate at the current price. (v2 candidate.)
- **No Monte Carlo.** Three discrete scenarios, not a distribution. (v2 candidate.)
- **No multi-stage WACC.** WACC is constant across all 10 years.
- **No tax adjustment for FCF.** Ray uses Snowball's reported FCF as-is, assuming it's already after-tax.
- **No goodwill amortization or operating-lease adjustments.** Out of scope; Snowball's FCF should already reflect cash reality.

## When the DCF should NOT be trusted

- **Negative or near-zero FCF.** Pre-profitability companies. Ray's DCF skips and the report flags it.
- **Highly cyclical at peak earnings.** The base case extrapolates from a peak that may not repeat. The sync gate's `cyclical_peak_trap` rule catches this.
- **Banks and insurers.** Their economics are balance-sheet-driven, not FCF-driven. Out of scope for v1.
- **Pre-revenue or hypergrowth.** A 5-year FCF projection on $0 of FCF is mathematically arbitrary.

For these cases the conviction will collapse via the data-quality channel and Ray returns INSUFFICIENT_DATA.

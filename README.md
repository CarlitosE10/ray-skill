# Ray

> **Decision agent** — closes the three-agent investment pipeline by producing BUY/HOLD/SELL with fair value, margin of safety, conviction, and position sizing.

Ray takes the JSON outputs of Snowball (quantitative) + Charlie (qualitative) and produces a final `RayDecision` JSON. It runs DCF 3-scenarios, applies a MOAT-adjusted margin of safety, detects conflicts between the two upstream agents (sync gate), computes conviction, and recommends position sizing.

---

## Three-agent architecture

```
        ┌───────────────────────────────────────────┐
        │ INPUTS: ticker (+ optional portfolio,     │
        │ horizon, risk profile)                    │
        └────────────────────┬──────────────────────┘
                             │
                       ┌─────▼─────┐
                       │  Router   │  ← classifies asset type
                       └─────┬─────┘
                             │
                ┌────────────┴────────────┐
                ▼                         ▼
        ┌───────────────┐         ┌───────────────┐
        │   Snowball    │         │    Charlie    │
        │ (quantitative)│         │ (qualitative) │
        └───────┬───────┘         └───────┬───────┘
                └────────────┬────────────┘
                             ▼
                       ┌───────────┐
                       │ ★ Ray ★   │  ← this skill
                       │ • DCF     │
                       │ • MOS     │
                       │ • sync    │
                       │ • convict │
                       │ • size    │
                       │ • DECIDE  │
                       └───────────┘
```

---

## Quick start

```bash
# Run Snowball + Charlie first; save their JSON outputs
uv run ../snowball/scripts/snowball.py analyze AAPL > aapl_snowball.json
uv run ../charlie/scripts/charlie.py analyze AAPL > aapl_charlie.json

# Then Ray
cd scripts/
uv run ray.py decide --snowball aapl_snowball.json --charlie aapl_charlie.json --format text

# With portfolio for $-amount sizing
uv run ray.py decide \
    --snowball aapl_snowball.json \
    --charlie aapl_charlie.json \
    --portfolio my_portfolio.json \
    --risk-profile moderate \
    --format text
```

---

## What Ray computes

### 1. DCF — three scenarios

Discounted cash flow with Gordon-Shapiro terminal, three scenarios (pessimistic / base / optimistic) blended at 25/50/25 weights. Live risk-free rate from `^TNX`. WACC via CAPM.

### 2. MOAT-adjusted Margin of Safety

| MOAT (from Charlie) | MOS |
|---|---|
| very_strong | 10% |
| strong | 15% |
| neutral | 20% |
| weak | 25% |
| very_weak | 30% |

Plus risk-profile shift: conservative +5pp, moderate 0, aggressive −3pp. Sell premium flat 25%.

### 3. Sync gate — conflict detection

Six patterns where Snowball and Charlie disagree:
1. Value trap (cheap + weak moat + cautious sector)
2. Quality overpriced (expensive + strong moat + bullish sector)
3. Moat erosion signal (strong moat + margin compression)
4. Insider disconnect (strong moat + heavy insider selling)
5. Sector headwind vs strength
6. Cyclical peak trap (highly cyclical + peak margins)

Each fires a conviction penalty; total caps at 30pp.

### 4. Conviction score (0-100)

| Component | Weight |
|---|---|
| Snowball completeness | 40% |
| Charlie qualitative score | 30% |
| Distance to threshold | 15% |
| Coherence (inverse of sync gate) | 15% |

Levels: very_low (< 30, → INSUFFICIENT_DATA), low, moderate, high, very_high.

### 5. Decision

```
if conviction.level == very_low → INSUFFICIENT_DATA
elif current_price ≤ buy_below → BUY
elif current_price ≥ sell_above → SELL
else → HOLD
```

### 6. Time horizon

| Horizon | Trigger |
|---|---|
| 1-3y | Highly cyclical OR weak moat |
| 3-5y | Default; strong moat or growth sector |
| 5-10y | Very strong moat with ≥15y durability |

### 7. Position sizing — quarter-Kelly with profile caps

```
suggested_pct = upside × 0.5 × 0.25 × (conviction / 100), capped by profile
```

| Profile | Cap (% per position) |
|---|---|
| Conservative | 3.0% |
| Moderate (default) | 5.0% |
| Aggressive | 8.0% |

---

## Commands

| Command | Purpose |
|---|---|
| `decide` | Full pipeline → RayDecision JSON (default) |
| `dcf` | DCF 3-scenarios only |
| `mos` | Margin of safety thresholds (given a fair value) |
| `sync` | Sync-gate conflict detection only |
| `conviction` | Conviction breakdown only |

Common flags:
- `--snowball PATH` (required for most): Snowball JSON
- `--charlie PATH` (required for most): Charlie JSON
- `--portfolio PATH` (optional): for $-amount sizing
- `--risk-profile {conservative|moderate|aggressive}` (default `moderate`)
- `--format {json|text}` (default `json`)

---

## Inputs

### Snowball JSON (required)

Ray reads ~25 fields from Snowball's report. The most important:
- `current_price`
- `dcf_inputs.{free_cash_flow, beta, shares_outstanding, net_debt, revenue_cagr_3y, fcf_cagr_3y}`
- `pe_ratio`, `ev_ebitda`, `fcf_yield`, `operating_margin`, `revenue_growth_yoy` (sync gate)
- `rsi_14`, `pct_from_52w_high`, `insider_net_buy_3m` (sync gate)
- `data_quality.completeness_pct` (conviction)

Full contract in `references/input_contracts.md`.

### Charlie JSON (required)

Ray reads ~10 fields from Charlie's report:
- `moat.moat_strength` — drives MOS
- `moat.moat_durability_years` — drives time horizon
- `growth_adjustment.suggested_adjustment_pct` — adjusts DCF base growth
- `qualitative_score` — drives conviction (30%)
- `sector_outlook.outlook`, `sector_outlook.sector_maturity`
- `macro_environment.cyclicality`
- `catalysts[]`, `qualitative_risks[]` — surfaced as key_drivers / key_risks

### Portfolio JSON (optional)

```json
{
  "total_value": 500000,
  "cash_available": 50000,
  "holdings": [
    {"ticker": "MSFT", "market_value": 25000},
    {"ticker": "GOOGL", "weight_pct": 4.2}
  ]
}
```

In v1, only `total_value` is used (for displaying $ amounts in position sizing). Holdings array is parsed but not used yet.

---

## Output

Default: JSON. Schema documented in `references/output_schema.md`. Top-level fields:

- `decision`: BUY / HOLD / SELL / INSUFFICIENT_DATA
- `decision_reasoning`: human-readable
- `current_price`, `fair_value_per_share`, `upside_pct`
- `dcf`: scenarios, weighted FV, sensitivity notes
- `margin_of_safety`: applied MOS, buy_below, sell_above
- `sync_gate_conflicts`: array
- `conviction`: 0-100 score with breakdown
- `time_horizon`: 1-3y / 3-5y / 5-10y / etc.
- `position_sizing`: % of portfolio + $ amount + rationale
- `key_drivers`, `key_risks`: human-readable arrays
- `data_quality`: completeness from each upstream agent + warnings
- `disclaimer`: always present

For human review, use `--format text`.

---

## File layout

```
ray/
├── SKILL.md                        ← skill definition (the "brain")
├── README.md                       ← this file
├── requirements.txt                ← yfinance, pandas, pydantic
├── scripts/
│   ├── ray.py                      ← CLI entrypoint
│   ├── pipeline.py                 ← orchestrator
│   ├── dcf.py                      ← DCF + WACC
│   ├── margin_of_safety.py         ← MOAT-adjusted MOS
│   ├── sync_gate.py                ← conflict detection
│   ├── conviction.py               ← conviction scoring
│   ├── position_sizing.py          ← Kelly + caps
│   ├── decision.py                 ← BUY/HOLD/SELL logic
│   ├── inputs.py                   ← Pydantic loaders
│   └── report.py                   ← Pydantic models (output)
└── references/
    ├── dcf_methodology.md          ← three-scenario DCF explained
    ├── margin_of_safety.md         ← MOAT-keyed MOS table
    ├── conviction_framework.md     ← conviction composition
    ├── sync_gate_rules.md          ← six conflict patterns
    ├── position_sizing.md          ← Kelly fractional explained
    ├── decision_logic.md           ← BUY/HOLD/SELL rules
    ├── input_contracts.md          ← what Ray reads
    └── output_schema.md            ← JSON contract
```

---

## What Ray does NOT do

1. ❌ Does not fetch raw company data — that's Snowball.
2. ❌ Does not do qualitative analysis — that's Charlie.
3. ❌ Does not run without both Snowball and Charlie outputs.
4. ❌ Does not pretend to a recommendation when conviction is `very_low`.
5. ❌ Does not execute trades or interact with brokerages.

---

## Out-of-scope (v1)

- **Banks, insurers, REITs, BDCs** — balance-sheet-driven economics; DCF is unsuitable.
- **ETFs** — multi-name vehicles need different valuation framing.
- **Crypto** — no FCF; different valuation framework.
- **Pre-revenue / pre-FCF companies** — DCF degenerates.
- **Reverse-DCF** — back-solving for implied growth at current price.

---

## Disclaimer

Ray's output is for **informational purposes only**. It does not constitute financial advice. The DCF assumes inputs that may be wrong; the qualitative judgments in Charlie's output may be miscalibrated; the sync gate may miss real conflicts or flag spurious ones; position sizing ignores existing exposure, correlation, and tax considerations.

All investment decisions should be made in consultation with a licensed financial advisor who knows your full financial picture, tax situation, and personal risk tolerance.

---

## Roadmap

**v1 (current):** Stocks only. Three-scenario DCF. Six sync-gate patterns. Kelly fractional sizing.

**v2 (planned):**
- Reverse-DCF (back-solve for implied growth)
- Portfolio-aware sizing (delta vs current holdings)
- Sector concentration check
- Two-stage WACC
- Banks: NIM-driven valuation framework
- Strict mode (`--strict` refuses to run on missing required fields)

**v3 (aspirational):**
- Monte Carlo over the 3 scenarios with input distributions
- Earnings quality / accruals divergence sync gate rule
- Tax-aware trim/sell suggestions
- Multi-ticker portfolio rebalance recommendations

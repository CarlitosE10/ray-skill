---
name: ray
description: Decision agent that produces BUY/HOLD/SELL verdicts on stocks. Use this skill whenever the user wants a final investment decision, fair value, target buy/sell prices, position sizing, or conviction analysis. Trigger on phrases like "comprar o vender", "decisión de inversión", "DCF", "precio objetivo", "valor justo", "margin of safety", "conviction", "qué tan grande la posición", or any request to combine quantitative + qualitative inputs into an actionable recommendation. Ray is the third agent in a three-agent pipeline (Snowball → Charlie → Ray) and consumes the JSON outputs of the other two; never run Ray without first running Snowball and Charlie on the same ticker.
version: 1.0.0
commands:
  - /ray - Full decision pipeline (default)
  - /ray_dcf - DCF 3-scenarios only
  - /ray_mos - Margin of safety thresholds
  - /ray_sync - Sync gate (Snowball↔Charlie conflict detection)
  - /ray_conviction - Conviction score breakdown
metadata: {"requires":{"bins":["uv","python3"]}}
---

# Ray — Decision Agent

Ray is the **decision agent** that closes the three-agent investment pipeline:

```
Router → [Snowball ⊕ Charlie] → Ray → BUY / HOLD / SELL
                                  ↑ this skill
```

- **Snowball**: numbers — ratios, technicals, sentiment, insider data, DCF inputs
- **Charlie**: qualitative — MOAT, sector, competition, macro, products
- **Ray (this skill)**: decision — DCF 3-scenarios, MOAT-adjusted MOS, sync gate, conviction, position sizing, BUY/HOLD/SELL

## Core Responsibility

Given **Snowball.json + Charlie.json + optional portfolio + optional risk profile**, produce a `RayDecision` JSON containing:

1. **Decision**: `BUY` / `HOLD` / `SELL` / `INSUFFICIENT_DATA`
2. **Fair value per share** (probability-weighted across 3 DCF scenarios)
3. **Buy and sell thresholds** (MOAT-adjusted margin of safety)
4. **Conviction score** with breakdown
5. **Sync gate conflicts** (where Snowball and Charlie disagree)
6. **Time horizon recommendation**
7. **Position sizing** (Kelly fractional, profile-capped)
8. **Key drivers and risks**

## What Ray NEVER Does

- ❌ Does NOT fetch raw financial data — that's Snowball's job (consume its JSON)
- ❌ Does NOT do qualitative analysis — that's Charlie's job (consume its JSON)
- ❌ Does NOT run without both Snowball and Charlie outputs
- ❌ Does NOT pretend to a recommendation when conviction is `very_low` (returns `INSUFFICIENT_DATA`)
- ❌ Does NOT execute trades, place orders, or interact with brokerages

## When to Use This Skill

Trigger Ray whenever the user:

- Asks for a final decision on a ticker after running Snowball + Charlie
- Wants a fair value, target price, or DCF
- Asks "should I buy [TICKER]?" or "is [TICKER] overvalued?"
- Asks about margin of safety, position sizing, or conviction
- Wants a buy/sell threshold

## Inputs

Ray reads:

1. **Snowball JSON** (required) — quantitative report from the Snowball skill
2. **Charlie JSON** (required) — qualitative report from the Charlie skill
3. **Portfolio JSON** (optional) — for $-amount position sizing
4. **Risk profile** (optional, default `moderate`) — `conservative` / `moderate` / `aggressive`

The full input contract is documented in `references/input_contracts.md`. Both inputs must:
- Refer to the **same ticker** (case-insensitive). Mismatch → `INSUFFICIENT_DATA`.
- Have `schema_version` starting with `1.` (warning otherwise; doesn't block).

## How to Use

### Quick decision tree

| User intent | Command |
|---|---|
| Full decision (most cases) | `decide --snowball s.json --charlie c.json` |
| Just the DCF | `dcf --snowball s.json --charlie c.json` |
| Just MOS thresholds | `mos --charlie c.json --fair-value 235.50` |
| Just sync gate | `sync --snowball s.json --charlie c.json` |
| Just conviction | `conviction --snowball s.json --charlie c.json` |

### Full pipeline (default)

```bash
uv run scripts/ray.py decide \
    --snowball aapl_snowball.json \
    --charlie aapl_charlie.json \
    --risk-profile moderate
```

With portfolio:

```bash
uv run scripts/ray.py decide \
    --snowball aapl_snowball.json \
    --charlie aapl_charlie.json \
    --portfolio my_portfolio.json \
    --risk-profile aggressive
```

### Output format

JSON by default (consumable downstream). For human-readable:

```bash
uv run scripts/ray.py decide --snowball s.json --charlie c.json --format text
```

## DCF — three scenarios

Ray runs three DCF scenarios with different growth, terminal, and WACC assumptions:

| Scenario | Phase 1 growth | Terminal growth | WACC | Weight |
|---|---|---|---|---|
| Pessimistic | base × 0.50 | 2.0% | base × 1.10 | 25% |
| Base | Snowball CAGR + Charlie adjustment | 2.5% | CAPM with live Rf | 50% |
| Optimistic | base × 1.30 (cap 25%) | 3.0% | base × 0.95 | 25% |

The blended fair value is the probability-weighted average. See `references/dcf_methodology.md`.

## MOAT-adjusted Margin of Safety

The MOS varies with Charlie's MOAT rating:

| MOAT | MOS |
|---|---|
| very_strong | 10% |
| strong | 15% |
| neutral | 20% |
| weak | 25% |
| very_weak | 30% |

Plus risk-profile adjustment: conservative +5pp, aggressive −3pp.

`buy_below = fair_value × (1 − MOS)`. `sell_above = fair_value × 1.25` (flat).

See `references/margin_of_safety.md`.

## Sync gate

Ray detects conflicts between Snowball and Charlie. Six patterns in v1:

1. **Value trap** (cheap valuation + weak moat + cautious sector)
2. **Quality overpriced** (expensive valuation + strong moat + bullish sector)
3. **Moat erosion signal** (strong moat + margin compression)
4. **Insider disconnect** (strong moat + heavy insider selling)
5. **Sector headwind vs strength** (good company + cautious sector)
6. **Cyclical peak trap** (highly cyclical + peak margins)

Each conflict reduces the conviction score. Total penalty caps at 30pp. See `references/sync_gate_rules.md`.

## Conviction

Composite 0-100 score:
- 40% Snowball's data completeness
- 30% Charlie's qualitative score
- 15% distance to buy/sell threshold
- 15% coherence (inverse of sync gate penalties)

Levels: very_low (< 30, → INSUFFICIENT_DATA), low (30-49), moderate (50-69), high (70-84), very_high (≥85).

See `references/conviction_framework.md`.

## Position sizing

Quarter-Kelly with profile caps:

```
suggested_pct = upside × 0.5 × 0.25 × (conviction/100), capped by profile
```

Profile caps: conservative 3%, moderate 5%, aggressive 8%.

See `references/position_sizing.md`.

## Output Schema (RayDecision v1.0.0)

```json
{
  "schema_version": "1.0.0",
  "ticker": "AAPL",
  "decision": "BUY",
  "decision_reasoning": "...",
  "current_price": 175.50,
  "fair_value_per_share": 235.50,
  "upside_pct": 34.2,
  "dcf": { "scenarios": [...], "weighted_fair_value_per_share": ... },
  "margin_of_safety": { "applied_mos_pct": 0.10, "buy_below": ..., "sell_above": ... },
  "sync_gate_conflicts": [...],
  "conviction": { "weighted_score": 84.6, "level": "high", ... },
  "time_horizon": "5-10y",
  "position_sizing": { "suggested_pct_of_portfolio": 3.45, ... },
  "key_drivers": [...],
  "key_risks": [...],
  "data_quality": {...},
  "disclaimer": "Not financial advice. ..."
}
```

Full schema in `references/output_schema.md`.

## File Map

```
ray/
├── SKILL.md                          ← this file
├── README.md                         ← human-facing docs
├── requirements.txt                  ← Python dependencies
├── scripts/
│   ├── ray.py                        ← main entrypoint (subcommands)
│   ├── pipeline.py                   ← orchestrator for `decide`
│   ├── dcf.py                        ← DCF 3-scenarios + WACC
│   ├── margin_of_safety.py           ← MOAT-adjusted MOS
│   ├── sync_gate.py                  ← Snowball↔Charlie conflict detection
│   ├── conviction.py                 ← conviction scoring
│   ├── position_sizing.py            ← Kelly + profile caps
│   ├── decision.py                   ← BUY/HOLD/SELL logic
│   ├── inputs.py                     ← Pydantic loaders for Snowball/Charlie
│   └── report.py                     ← Pydantic models for RayDecision
└── references/
    ├── dcf_methodology.md            ← DCF approach + assumptions
    ├── margin_of_safety.md           ← MOAT-keyed MOS table
    ├── conviction_framework.md       ← conviction composition
    ├── sync_gate_rules.md            ← conflict patterns
    ├── position_sizing.md            ← Kelly fractional + caps
    ├── decision_logic.md             ← BUY/HOLD/SELL rules
    ├── input_contracts.md            ← what Ray reads from Snowball/Charlie
    └── output_schema.md              ← full JSON schema
```

## Important Rules for the Skill

1. **Always run with both Snowball and Charlie outputs.** Refusing to run is correct behavior if either is missing.

2. **Never invent inputs.** If Snowball didn't compute FCF, Ray's DCF is skipped — don't substitute a guess.

3. **Conviction = very_low → INSUFFICIENT_DATA.** Don't override the rule. The integrity of the pipeline depends on Ray refusing to recommend when the inputs don't justify a recommendation.

4. **Default to JSON output.** Downstream consumers parse it. Use `--format text` only when the user explicitly wants human-readable.

5. **Always include the disclaimer.** "Not financial advice. For informational purposes only." is hardcoded in the schema.

6. **Risk profile defaults to `moderate`.** Don't change without explicit user direction.

7. **Schema mismatches produce warnings, not errors.** Ray accepts `1.x.x` schema versions on either input; missing or non-1.x produces a warning but doesn't block.

8. **Ticker mismatches are blocking.** If `snowball.ticker != charlie.ticker`, Ray returns `INSUFFICIENT_DATA`.

9. **Banks, insurers, ETFs, crypto: out of scope.** Ray's DCF is unsuitable for balance-sheet-driven businesses. (Same scope as Snowball/Charlie v1.)

10. **For text output, render the institutional format.** Sections, no emojis except in the BUY/HOLD/SELL badge, anchored claims, disclaimer at the end.

## Disclaimer

Ray produces decisions for **informational purposes only**. It does not constitute financial advice, investment advice, or a solicitation to trade. The DCF assumes inputs that may be wrong; the qualitative judgments in Charlie's output may be miscalibrated; the sync gate may miss real conflicts or flag spurious ones. All investment decisions should be made in consultation with a licensed financial advisor who knows your full financial picture, tax situation, and personal risk tolerance.

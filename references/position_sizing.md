# Position Sizing

Ray's position sizing is **quarter-Kelly with profile caps**. The output is a *suggestion* — concentration, tax, and rebalancing decisions belong to the user.

## Why quarter-Kelly?

The full Kelly criterion bets the size that maximizes the geometric growth rate of capital. For investing, full Kelly is too aggressive in practice because:

1. The edge is **uncertain** (we don't know the real win probability).
2. Outcomes are **continuous, not binary** — a "loss" is rarely 100% loss.
3. Drawdowns matter psychologically and practically; full Kelly produces large interim drawdowns that most investors won't tolerate.

Quarter-Kelly (multiplier 0.25) is a common rule of thumb in real-money portfolios — it captures most of the long-run edge with much smaller drawdowns.

## The formula

```
upside_decimal     = (fair_value - current_price) / current_price
raw_kelly_pct      = upside_decimal × 0.5 × KELLY_FRACTION × 100
                                       ↑ 0.25 = quarter-Kelly
suggested_pct      = raw_kelly_pct × (conviction_score / 100)
suggested_capped   = min(suggested_pct, profile_cap)
```

The `× 0.5` factor approximates Kelly under the assumption of symmetric outcomes (upside and downside equally probable). This is itself a simplification; a more sophisticated Kelly would model the outcome distribution explicitly, but the simplification is consistent with the use of quarter-Kelly: we'd rather under-size than over-size.

## Profile caps

| Profile | Cap (% of portfolio per position) |
|---|---|
| `conservative` | 3.0% |
| `moderate` (default) | 5.0% |
| `aggressive` | 8.0% |

These are **hard caps**, applied after Kelly + conviction scaling. They reflect:
- **Conservative:** wider diversification (~30+ positions); minimize single-name risk.
- **Moderate:** standard portfolio construction (~20 positions).
- **Aggressive:** higher concentration (~12-15 positions); accept more single-name volatility.

## Worked example

Setup: a BUY recommendation with **15% upside** and **75 conviction** on a moderate profile.

```
upside_decimal = 0.15
raw_kelly_pct  = 0.15 × 0.5 × 0.25 × 100  = 1.875%
× conviction   = 1.875% × 0.75            = 1.41%
× profile cap  = min(1.41%, 5.0%)         = 1.41%
```

Recommended size: **~1.4% of the portfolio**. On a $500k portfolio, that's ~$7,000.

## Worked example — high conviction, high upside

Setup: 40% upside (deep value), 90 conviction, moderate profile.

```
upside_decimal = 0.40
raw_kelly_pct  = 0.40 × 0.5 × 0.25 × 100  = 5.0%
× conviction   = 5.0% × 0.90              = 4.5%
× profile cap  = min(4.5%, 5.0%)          = 4.5%
```

Recommended size: **4.5%** — close to the cap. The Kelly math wanted to size larger, but the profile cap kept it bounded.

## When sizing is zero

- Decision is **not BUY** (HOLD or SELL → no new allocation suggested).
- Upside is **non-positive** (current price already above fair value — by definition can't be a BUY anyway).
- Conviction is **very_low** (decision becomes INSUFFICIENT_DATA).

## What sizing does NOT consider

- **Existing exposure to the same ticker.** If the user already owns 3% of AAPL and Ray suggests 4%, the implied action is "add 1pp," but Ray doesn't compute that delta in v1.
- **Sector concentration.** The user might already hold three tech names; Ray doesn't aggregate.
- **Correlation between holdings.** Two semi names are correlated; Ray treats them independently.
- **Liquidity / market impact.** Sizing assumes the user can fill at the current price.
- **Tax considerations.** Realized gains/losses, holding period, tax-loss harvesting — none of these are modeled.

These are real concerns for portfolio construction. Ray's position sizing is one input into that process, not a substitute for it.

## Future direction (v2)

- **Portfolio-aware sizing.** If the holdings list is provided, suggest *target* weight and compute the implied buy/trim.
- **Sector concentration check.** Penalize sizes that would push sector weight above a configurable threshold.
- **Correlation-adjusted sizing.** Reduce size when the ticker is highly correlated with existing holdings.
- **Tax-aware suggestions.** When trimming an overvalued position, surface the holding period and basis.

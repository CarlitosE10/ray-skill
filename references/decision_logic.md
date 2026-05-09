# Decision Logic

The final BUY/HOLD/SELL rule is **deliberately simple**. Most of Ray's intelligence sits in the inputs feeding the decision (DCF, MOAT-keyed MOS, conviction). The decision itself is a comparison.

## The rule

In order:

1. **If conviction is `very_low`** (score < 30) → **INSUFFICIENT_DATA**.
   - We don't pretend to a recommendation when the inputs don't support one.
   - Surface the warnings and conflicts; let the user investigate.

2. **If `current_price` ≤ `buy_below`** → **BUY**.
   - The price has fallen below fair value × (1 − applied_MOS).
   - The position-sizing logic determines how much to allocate.

3. **If `current_price` ≥ `sell_above`** → **SELL**.
   - The price has risen above fair value × (1 + sell_premium).
   - Symmetric in form to BUY, but not MOAT-adjusted (the premium is flat 25%).

4. **Otherwise** → **HOLD**.
   - The price sits between buy and sell thresholds.
   - The decision narrative explains how far from each threshold.

## Why this is the whole rule

The temptation is to add more logic — momentum, technical confirmation, news context, sentiment — and have those override the price-vs-fair-value comparison. We deliberately don't.

Reasons:

1. **Snowball already feeds those signals into Charlie's qualitative score.** Sentiment, technicals, and momentum-style signals are upstream of the conviction score. Layering them again at the decision stage would double-count.

2. **The decision should be auditable.** A simple price comparison is reproducible and easy to challenge. A composite "BUY-confidence-weighted-momentum-adjusted-sentiment-filtered" signal is opaque.

3. **The MOS already encodes uncertainty.** If we're uncertain (weak moat, conservative profile), we use a wider MOS — a wider buffer between price and fair value. We don't need another filter on top.

## Time horizon

Independent of BUY/HOLD/SELL, Ray attaches a recommended **time horizon**, derived from Charlie:

| Horizon | Trigger |
|---|---|
| `1-3y` | Highly cyclical macro OR weak/very_weak moat (medium-term value play, not a compounder) |
| `3-5y` | Default. Strong moat OR growth-stage sector |
| `5-10y` | Very strong moat AND durability ≥ 15 years (long-horizon compounder) |
| `short_term` | Reserved for special cases (rare in v1) |
| `long_term` | Reserved for special cases (rare in v1) |

The horizon is a *recommended* holding period for the thesis to play out. It's not a stop-loss or a time-out trigger.

## What about INSUFFICIENT_DATA?

`INSUFFICIENT_DATA` triggers when:
- Conviction is `very_low` (< 30) — most common reason
- Tickers don't match between Snowball and Charlie inputs
- Current price or fair value is missing

In these cases:
- No buy/sell action is recommended.
- The reasoning explains what's missing or conflicting.
- `data_quality.warnings` and `data_quality.blocking_issues` give the specifics.

## Decision is *not* a price target

A BUY says "the price is below the level I'd be willing to pay." It does not say:
- The price will recover to fair value.
- The price will recover within the time horizon.
- A specific price target.

The fair value and `upside_pct` give the implied price level if the thesis plays out, but they're not commitments.

## What happens after a BUY

Ray does not track follow-through. Each `decide` invocation is a snapshot. If the price falls another 20% after a BUY, that's a new decision context that requires a fresh run. The user (or the agent calling Ray) decides when to re-evaluate.

## What happens after a SELL

Same. SELL is a snapshot judgment that the price exceeds the sell threshold. It doesn't say:
- Sell now, in full, immediately.
- Sell at any price.
- Don't re-buy if the price falls back.

Tax-aware execution, gradual trimming, and re-entry policy are user decisions.

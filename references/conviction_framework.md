# Conviction Framework

**Conviction is not the strength of the signal. It is Ray's confidence in the inputs that produced the signal.**

A high-conviction BUY means: the DCF inputs are complete, the qualitative thesis is well-developed, the price gap is decisive, and Snowball and Charlie agree.

A low-conviction BUY means: the math says buy, but something is incomplete or in disagreement — the user should investigate before sizing aggressively.

## Composition

Conviction is a weighted average of four components, each scored 0–100:

| Component | Weight | What it measures |
|---|---|---|
| **Quantitative confidence** | 40% | Snowball's `data_quality.completeness_pct`. How complete were the inputs to the DCF? |
| **Qualitative score** | 30% | Charlie's `qualitative_score` (0–100). How attractive is the business qualitatively? |
| **Distance to threshold** | 15% | How decisively the current price sits below `buy_below` or above `sell_above`. HOLD decisions inherently have a lower component here. |
| **Coherence** | 15% | Inverse of sync-gate penalties. If Snowball and Charlie disagree (value trap, moat erosion signal, etc.), this drops. |

## Levels

| Score | Level |
|---|---|
| ≥ 85 | very_high |
| 70–84 | high |
| 50–69 | moderate |
| 30–49 | low |
| < 30 | very_low → INSUFFICIENT_DATA |

A `very_low` conviction overrides the BUY/HOLD/SELL output and returns `INSUFFICIENT_DATA`. We don't pretend to a recommendation when the inputs don't justify one.

## Why these weights?

**Quant first (40%).** The whole DCF rests on Snowball's numbers. If Snowball has 50% completeness, the fair value is a wild guess and conviction *should* be low.

**Qualitative second (30%).** Charlie's score captures business quality. A 90-quality company priced 20% below fair value is more compelling than a 50-quality company priced 30% below fair value, because the qualitative score accounts for whether the fair value will hold up over time.

**Distance third (15%).** The further price sits from the threshold, the more decisive the signal. A BUY by 1% is fragile; a BUY by 25% is robust. Has lower weight than the data quality dimensions because a noisy fair-value estimate × big distance = still noisy.

**Coherence fourth (15%).** Sync-gate conflicts reduce conviction proportionally to their penalty. The full set of penalties caps at 30pp on the underlying score.

## Effect on the rest of the pipeline

Conviction feeds **position sizing**:

```
suggested_pct = quarter_kelly_pct × (conviction_score / 100), capped by risk_profile
```

A 70-conviction BUY at 10% upside on a moderate profile gets:

```
quarter_kelly = 10% × 0.5 × 0.25 = 1.25%
× 70/100 = 0.875%
```

A 90-conviction BUY at the same upside gets ~1.13%. The size scales with confidence in the inputs, not just the math.

## When conviction is intentionally damped

Ray multiplies the weighted score by 0.85 if either Snowball's `completeness_pct` or Charlie's `qualitative_score` is missing — both are core inputs and their absence should be visible.

## What conviction does NOT capture

- **Macro regime risk** beyond what's in Charlie's macro section.
- **Concentration risk** at the portfolio level (how many similar tickers the user already holds).
- **Tax considerations** of trimming an overvalued position.

These belong in the user's broader process and are not Ray's job.

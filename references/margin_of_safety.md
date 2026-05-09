# Margin of Safety

The **margin of safety (MOS)** is the discount you require below your fair-value estimate before you'll buy. It exists to absorb the inevitable error in the estimate itself.

> "The margin of safety is always dependent on the price paid." — Benjamin Graham

Ray sets MOS dynamically based on **MOAT durability**: the better the business, the smaller the cushion needed; the weaker the business, the larger.

## MOAT-keyed table

| MOAT (Charlie) | Base MOS | Reasoning |
|---|---|---|
| `very_strong` | 10% | Exceptional moats (textbook examples — durable brand, dominant network, regulated franchise). Smaller cushion suffices because the fair-value estimate itself is more reliable. |
| `strong` | 15% | Clear competitive advantage, durable for 10+ years. |
| `neutral` | 20% | The default. Typical company; standard cushion. |
| `weak` | 25% | Visible competitive pressure or vulnerability. Larger cushion required. |
| `very_weak` | 30% | No moat or rapidly eroding moat. Need a substantial discount because the business itself is fragile. |
| `unknown` | 25% | Default to a conservative cushion when MOAT couldn't be assessed. |

## Risk-profile adjustment

The user's risk profile shifts the MOS up or down:

| Profile | MOS adjustment |
|---|---|
| `conservative` | +5pp |
| `moderate` | 0 (default) |
| `aggressive` | −3pp |

Capped at [5%, 45%] regardless of inputs.

**Example:** a `strong`-moat company on an `aggressive` profile → 15% − 3 = 12% MOS.

## Sell premium

The mirror image: how far above fair value before Ray says SELL?

Default = **25%** flat. Not MOAT-adjusted because:
- A great business at 30% above fair value is still rich; the moat doesn't justify infinite price.
- A weak business at 30% above fair value is even more clearly overvalued.

The 25% cushion gives some room for a) optimistic-scenario realization, b) growth being slightly stronger than modeled. Beyond 25% above fair value, mean-reversion risk dominates.

## Buy / hold / sell zones

```
─────────────────────────────────────────────────────────────────
   SELL                  HOLD                     BUY
   ─────────────────────────────────────────────────────────────
   ▲                     │                         │             ▼
   │ Fair × (1 + 25%)    │ Fair                    │ Fair × (1 - MOS)
   │   sell_above        │                         │   buy_below
─────────────────────────────────────────────────────────────────
```

A current price below `buy_below` triggers BUY. A current price above `sell_above` triggers SELL. In between is HOLD.

## What MOS does NOT do

- **It does not increase the fair value estimate.** MOS is a price discipline, not a valuation adjustment. The fair value is what the DCF says; MOS is what *price* you'll pay against it.
- **It is not a stop-loss.** MOS sets entry; it doesn't say what to do if the price falls further after you buy.
- **It does not eliminate downside risk.** MOS reduces the probability of overpaying; it doesn't prevent loss in a bad scenario.

## Calibration philosophy

The MOS table is intentionally conservative. Real-world investors often use larger cushions (20-50%) on uncertain positions. The table above leans on **MOAT durability as the primary uncertainty proxy** because Charlie has already done that qualitative work.

If the user wants larger cushions across the board, they can pass `--risk-profile conservative` for an additional +5pp.

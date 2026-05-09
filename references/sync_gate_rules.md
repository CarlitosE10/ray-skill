# Sync Gate — Snowball ↔ Charlie Conflict Rules

The Sync Gate detects situations where Snowball (quantitative) and Charlie (qualitative) tell different stories. **Disagreement is information** — Ray flags these patterns, attaches a conviction penalty, and surfaces them so the user can investigate.

The gate **does not block** decisions. It only reduces conviction. Three separate conflicts can produce a HOLD outcome via the conviction floor; no single rule by itself blocks a BUY or SELL.

## Patterns in v1

### 1. Value trap (penalty: 12pp, severity: warning)

**Predicate:** Snowball flags cheap valuation (≥2 of: P/E < 15, EV/EBITDA < 10, FCF yield > 6%) AND Charlie rates moat as `weak` or `very_weak` AND sector outlook is `cautious` or `bearish`.

**Why it matters:** "Cheap" with no defensible business is the textbook value trap. The cheapness reflects the market's accurate assessment of declining cash flows — not a mispricing. Examples in history: most legacy print media, certain regional retailers in the 2010s, structurally challenged commodities producers near the end of cycles.

### 2. Quality overpriced (penalty: 5pp, severity: info)

**Predicate:** Snowball flags expensive valuation (≥2 of: P/E > 30, EV/EBITDA > 20, FCF yield < 2.5%) AND Charlie rates moat as `strong` or `very_strong` AND sector outlook is `constructive` or `bullish`.

**Why it matters:** Excellent business at a rich price. Not a "wrong" purchase, but no margin of safety — small disappointments can produce large drawdowns. Often resolves with patience: the price comes to you.

### 3. Moat erosion signal (penalty: 15pp, severity: critical)

**Predicate:** Charlie rates moat as `strong` or `very_strong` AND Snowball shows operating margin < 8% AND revenue growth YoY is negative.

**Why it matters:** The qualitative thesis says "great moat," but the underlying numbers are deteriorating. Either the moat is real and this is a temporary stumble — or the moat is no longer effective and the qualitative assessment hasn't caught up. Highest penalty in the gate because the data is more reliable than the narrative when they conflict.

### 4. Insider disconnect (penalty: 8pp, severity: warning)

**Predicate:** Charlie rates moat as `strong` or `very_strong` AND Snowball shows net insider selling > $1M in the last 3 months.

**Why it matters:** Insiders sell for many benign reasons (diversification, scheduled plans, taxes), but coordinated selling against a "great business" thesis warrants verification. The penalty is moderate because false positives are common.

### 5. Sector headwind vs strength (penalty: 4pp, severity: info)

**Predicate:** Snowball doesn't flag expensive valuation AND Charlie says sector outlook is `cautious` or `bearish` AND moat is not `weak` or `very_weak`.

**Why it matters:** Even good operators face sector-wide compression. A textile leader in a contracting textile market still loses pricing power. The penalty is small because well-run companies often do fine through sector downturns.

### 6. Cyclical peak trap (penalty: 10pp, severity: warning)

**Predicate:** Charlie classifies macro as `highly_cyclical` AND Snowball shows operating margin > 20%.

**Why it matters:** Highly cyclical businesses (especially energy, basic materials, some industrials) earn outsized margins at the top of the cycle and weak margins at the bottom. Valuing on peak margins extrapolates a non-recurring state. A "cheap" P/E at peak earnings is often a trap — the E is about to compress.

## Penalty cap

Total penalty caps at **30 percentage points** on the underlying conviction score. If many patterns fire on a single ticker, the cap prevents conviction from collapsing entirely on rule-based grounds — multiple conflicts justify a manual review rather than mechanical INSUFFICIENT_DATA.

## What's NOT in v1

These patterns require data Snowball v1 doesn't reliably surface:

- **Earnings quality / accruals divergence** — would compare reported earnings vs FCF; flagged when FCF is materially below earnings for multiple periods.
- **Customer concentration at risk** — would catch cases where Charlie says "high customer concentration" + a major customer (publicly known) is in distress.
- **Capex vs depreciation** — would flag businesses where capex chronically exceeds D&A (capital sink) despite a "strong" moat rating.

These are candidates for v2.

## Pattern design philosophy

Rules are intentionally **conservative**:
- High specificity (multiple sub-conditions per rule) to avoid false positives.
- Low penalty per rule, with cap, to avoid runaway dampening from coincidental triggers.
- The output **describes the conflict** rather than prescribing a response. The user investigates.

# RayDecision — JSON Schema (v1.0.0)

The contract Ray emits. Schema version aligns with Snowball and Charlie.

```json
{
  "schema_version": "1.0.0",
  "ticker": "AAPL",
  "company_name": "Apple Inc.",
  "sector": "Technology",
  "decision_timestamp": "2026-05-08T15:30:00",

  "decision": "BUY",
  "decision_reasoning": "Current price $175.50 is 12.3% below the buy threshold of $200.00...",

  "current_price": 175.50,
  "fair_value_per_share": 235.50,
  "upside_pct": 34.2,

  "dcf": { ... },
  "margin_of_safety": { ... },
  "sync_gate_conflicts": [ ... ],
  "conviction": { ... },
  "time_horizon": "5-10y",
  "time_horizon_reasoning": "Very strong moat with ~15y durability — long-horizon compounder.",
  "position_sizing": { ... },

  "key_drivers": [ "..." ],
  "key_risks": [ "..." ],
  "data_quality": { ... },

  "disclaimer": "Not financial advice. ..."
}
```

## Block-by-block

### `decision`

One of: `BUY`, `HOLD`, `SELL`, `INSUFFICIENT_DATA`.

### `dcf`

```json
{
  "fcf_starting_point": 100000000000,
  "shares_outstanding": 15000000000,
  "net_debt": 50000000000,
  "scenarios": [
    {
      "name": "pessimistic",
      "growth_phase1_pct": 0.04,
      "growth_phase2_pct": 0.03,
      "terminal_growth_pct": 0.020,
      "wacc_pct": 0.0935,
      "fair_value_per_share": 180.50,
      "enterprise_value": 2750000000000,
      "weight": 0.25
    },
    { "name": "base", ... },
    { "name": "optimistic", ... }
  ],
  "weighted_fair_value_per_share": 235.50,
  "sensitivity_notes": [
    "WACC (base): 8.50% | risk-free 4.30% | beta 1.20",
    "Phase-1 growth (base): 8.00%"
  ]
}
```

### `margin_of_safety`

```json
{
  "moat_input": "very_strong",
  "base_mos_pct": 0.10,
  "applied_mos_pct": 0.10,
  "sell_premium_pct": 0.25,
  "buy_below": 211.95,
  "sell_above": 294.38,
  "reasoning": "MOAT 'very_strong' → base MOS 10%; applied MOS = 10%"
}
```

### `sync_gate_conflicts`

Array of any conflict patterns that fired:

```json
[
  {
    "pattern": "quality_overpriced",
    "description": "Excellent business by qualitative measures, but Snowball flags expensive valuation...",
    "severity": "info",
    "conviction_penalty_pp": 5
  }
]
```

Severity values: `info`, `warning`, `critical`.

### `conviction`

```json
{
  "quantitative_confidence": 95.0,
  "qualitative_score": 78.0,
  "distance_to_threshold": 70.0,
  "coherence": 92.5,
  "weighted_score": 84.6,
  "level": "high"
}
```

Level values: `very_low`, `low`, `moderate`, `high`, `very_high`.

### `position_sizing`

```json
{
  "suggested_pct_of_portfolio": 3.45,
  "suggested_dollar_amount": 17250.0,
  "risk_profile": "moderate",
  "cap_pct": 5.0,
  "kelly_raw_pct": 4.27,
  "rationale": "Quarter-Kelly raw: 4.27%; × conviction 85/100 = 3.63%; ≈ $17,250 on a $500,000 portfolio."
}
```

### `time_horizon`

One of: `short_term`, `1-3y`, `3-5y`, `5-10y`, `long_term`.

### `key_drivers` and `key_risks`

Arrays of human-readable strings, intended for the user-facing summary. Each is prefixed with a tag like `[regulatory|warning]` or `[high]` to encode metadata cheaply.

### `data_quality`

```json
{
  "snowball_completeness_pct": 95,
  "charlie_completeness_pct": 88,
  "snowball_schema_version": "1.0.0",
  "charlie_schema_version": "1.0.0",
  "schema_compatible": true,
  "warnings": [],
  "blocking_issues": []
}
```

`schema_compatible` is `false` if either source's `schema_version` is missing or doesn't match `1.x.x`. `blocking_issues` (e.g., ticker mismatch) cause Ray to return `INSUFFICIENT_DATA`.

### `disclaimer`

Always present. Always includes the phrase "Not financial advice."

## Field nullability

Most fields can be `null` or absent if the underlying inputs don't support them. The `decision`, `ticker`, `disclaimer`, and `data_quality` fields are always populated.

If `decision == "INSUFFICIENT_DATA"`, the rest of the report may be very sparse — the focus is on `decision_reasoning` and `data_quality.warnings`.

## Versioning

This is **v1.0.0**. Any backward-incompatible change (renamed field, changed type) requires bumping the major version. Adding new optional fields can happen at minor version bumps. Downstream consumers should validate `schema_version` and refuse to run on incompatible versions.

# Input Contracts — what Ray reads from Snowball and Charlie

Ray ingests two JSON files (plus an optional portfolio file). This document specifies the **minimum set of fields Ray reads** from each. The full Snowball and Charlie reports have many more fields; everything below is what Ray actually depends on.

Field paths use dot notation (`.`) for nested objects.

## SnowballInput (v1.x)

| Field | Type | Required | Used for |
|---|---|---|---|
| `schema_version` | string | strongly recommended | Compatibility check |
| `ticker` | string | **yes** | Ticker match with Charlie |
| `company_name` | string | optional | Display |
| `sector` | string | optional | Display |
| `industry` | string | optional | Display |
| `current_price` | number | **yes** for any decision | Price comparison |
| `pe_ratio` | number | optional | Sync gate (cheap/expensive heuristic) |
| `ev_ebitda` | number | optional | Sync gate |
| `fcf_yield` | number | optional | Sync gate |
| `gross_margin` | number | optional | Sync gate |
| `operating_margin` | number | optional | Sync gate (margin compression detection) |
| `revenue_growth_yoy` | number | optional | Sync gate; growth fallback for DCF |
| `rsi_14` | number | optional | Sync gate (overbought) |
| `pct_from_52w_high` | number | optional | Sync gate (overbought) |
| `insider_net_buy_3m` | number | optional | Sync gate (insider disconnect) |
| `dcf_inputs.free_cash_flow` | number | **yes** for DCF | DCF starting cash flow |
| `dcf_inputs.revenue_cagr_3y` | number | recommended | DCF base growth |
| `dcf_inputs.fcf_cagr_3y` | number | recommended | DCF base growth (preferred over revenue CAGR) |
| `dcf_inputs.beta` | number | recommended | WACC |
| `dcf_inputs.shares_outstanding` | number | **yes** for DCF | Per-share fair value |
| `dcf_inputs.net_debt` | number | recommended | EV → Equity bridge |
| `dcf_inputs.total_debt` | number | optional | Fallback when net_debt is missing |
| `dcf_inputs.cash` | number | optional | Fallback when net_debt is missing |
| `data_quality.completeness_pct` | number | recommended | Conviction score |
| `data_quality.warnings` | string[] | optional | Forwarded to Ray's data_quality |

If `schema_version` is missing or doesn't start with `1.`, Ray adds a warning but still attempts to run.

If `current_price` or `dcf_inputs.free_cash_flow` is missing, the DCF is skipped and Ray returns `INSUFFICIENT_DATA`.

## CharlieInput (v1.x)

| Field | Type | Required | Used for |
|---|---|---|---|
| `schema_version` | string | strongly recommended | Compatibility check |
| `ticker` | string | **yes** | Ticker match with Snowball |
| `company_name` | string | optional | Display fallback |
| `sector` | string | optional | Display fallback |
| `moat.moat_strength` | string | **yes** for MOS | One of `very_weak`/`weak`/`neutral`/`strong`/`very_strong` |
| `moat.moat_types` | string[] | optional | Surfaced in summary |
| `moat.moat_durability_years` | int | optional | Time horizon |
| `moat.moat_reasoning` | string | optional | Surfaced in key_drivers if catalysts empty |
| `sector_outlook.outlook` | string | optional | Sync gate |
| `sector_outlook.sector_maturity` | string | optional | Time horizon |
| `macro_environment.cyclicality` | string | optional | Sync gate; time horizon |
| `growth_adjustment.suggested_adjustment_pct` | number | optional | DCF base growth adjustment |
| `growth_adjustment.signal` | string | optional | Display only |
| `catalysts[]` | array | optional | key_drivers in output |
| `qualitative_risks[]` | array | optional | key_risks in output |
| `qualitative_score` | int (0-100) | recommended | Conviction score (30% weight) |
| `data_quality.completeness_pct` | number | optional | Forwarded to Ray's data_quality |

If `moat.moat_strength` is missing, Ray defaults to `unknown` MOS (25%) with a warning.

## PortfolioInput (optional)

| Field | Type | Used for |
|---|---|---|
| `total_value` | number | Convert position % to $ amount |
| `cash_available` | number | (v2: cash drag check) |
| `holdings[].ticker` | string | (v2: existing exposure check) |
| `holdings[].market_value` | number | (v2: existing exposure check) |
| `holdings[].weight_pct` | number | (v2: existing exposure check) |

In v1, the only field actually consumed is `total_value` (for displaying $ amounts in position sizing). The holdings list is parsed but not used.

## Strict mode (planned for v2)

Currently every field is optional and Ray runs with whatever it gets. A future `--strict` flag would refuse to run on missing required fields rather than degrade silently.

## Ticker matching

Ray normalizes tickers to uppercase and verifies that `snowball.ticker.upper() == charlie.ticker.upper()`. A mismatch is a blocking issue and produces `INSUFFICIENT_DATA`.

## Schema version compatibility

Ray accepts any `schema_version` starting with `1.` from both inputs. Missing or non-1.x versions produce a warning but don't block — useful when running against schemas slightly ahead of or behind the current version.

A v2 of any input would require explicit Ray support before being accepted.

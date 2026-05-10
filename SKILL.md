---
name: invest_verdict
description: A generalized investment decision skill that evaluates a stock's market context, portfolio risk, and valuation to provide a final BUY/HOLD/SELL/WAIT verdict. This skill fetches real-time prices, bid/ask spread, RSI, 200-SMA, and checks portfolio concentration limits. Agents can use this to make a precise decision rather than relying solely on static inputs.
version: 2.0.0
commands:
  - /verdict - Generate a final investment decision with live market data and portfolio risk.
  - /market_context - Fetch real-time price, RSI, SMA distance, and spread for a ticker.
  - /portfolio_risk - Check if a proposed investment violates portfolio concentration rules.
metadata: {"requires":{"bins":["uv","python3"]}}
---

# Investment Verdict Skill

A generalized skill for agents to make precise, real-time investment decisions. It combines your computed fair value with live market context and portfolio risk to generate a final verdict.

## Key Capabilities

1. **Market Context & Real-Time Pricing**: Fetches live price, bid/ask spread, RSI (14), and 200-day moving average. It uses these to adjust decisions (e.g., waiting if a stock is overbought despite being undervalued).
2. **Portfolio Risk**: Analyzes `portfolio.json` in the workspace to enforce concentration limits (e.g., max 10% per position, max 30% per sector).
3. **Verdict Generation**: Combines the moat-adjusted margin of safety, live price, and momentum indicators to return `BUY`, `HOLD`, `SELL`, or `WAIT`.

## Usage

Agents can run these scripts directly to get JSON outputs.

### 1. Final Verdict
Combines everything to give you a definitive decision.

```bash
uv run scripts/verdict.py --ticker AAPL --fair-value 180.50 --moat strong --investment 5000 --portfolio ../portfolio.json
```

**Parameters:**
- `--ticker`: The stock symbol (e.g. AAPL).
- `--fair-value`: The fair value per share you calculated.
- `--moat`: The qualitative strength of the company (`very_strong`, `strong`, `neutral`, `weak`, `very_weak`). Adjusts the required margin of safety.
- `--investment` (Optional): The dollar amount you plan to invest. Used for portfolio concentration checks.
- `--portfolio` (Optional): Path to the `portfolio.json`. Defaults to `portfolio.json`.

### 2. Market Context Only
If you just want to know the live price, RSI, and SMA to inform your own logic:

```bash
uv run scripts/market_context.py <TICKER>
```

### 3. Portfolio Risk Only
If you just want to check if a purchase violates concentration limits:

```bash
uv run scripts/portfolio_risk.py --ticker AAPL --amount 5000 --path ../portfolio.json
```

## Portfolio JSON Format
The `portfolio_risk.py` script expects a JSON like this:
```json
{
  "total_value": 100000,
  "cash": 20000,
  "holdings": [
     {"ticker": "NVDA", "sector": "Technology", "value": 10000}
  ]
}
```

## How It Works

- **Margin of Safety**: Depends on the moat (e.g., `strong` = 15% MOS). `Buy Below` = Fair Value * (1 - MOS).
- **Momentum Override**: If the stock is below the `Buy Below` threshold but the RSI > 70, the verdict changes from `BUY` to `WAIT` to avoid catching a falling knife or buying at a local peak.
- **Concentration Limits**: If the proposed investment causes the ticker to exceed 10% of the total portfolio, the system will block the `BUY`.

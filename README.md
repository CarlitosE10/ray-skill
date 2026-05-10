# Invest Verdict Skill

This skill allows any agent to make precise, data-driven investment decisions. It replaces the old rigid "Ray" pipeline with a flexible set of tools that provide real-time market context, enforce portfolio risk limits, and generate actionable verdicts based on fair value.

## Features

- **Real-Time Market Context (`market_context.py`)**: Don't trade blindly. This script fetches the live price, bid/ask spread, RSI (14 days), and distance to the 200-day Simple Moving Average (SMA).
- **Portfolio Concentration Rules (`portfolio_risk.py`)**: Prevents over-concentration. Reads a `portfolio.json` file to ensure no single position exceeds 10% of the total portfolio value and no sector exceeds 30%.
- **Verdict Engine (`verdict.py`)**: Takes your calculated fair value, qualitative moat assessment, and proposed investment amount. It queries the market context and portfolio risk to give a final `BUY`, `HOLD`, `SELL`, or `WAIT` decision.

## Setup

Ensure dependencies are installed:
```bash
pip install -r requirements.txt
```

## How Agents Use This

### Example 1: Full Verdict
You have calculated a fair value of $150 for AAPL. The company has a "strong" moat. You want to invest $5000.

```bash
uv run scripts/verdict.py --ticker AAPL --fair-value 150 --moat strong --investment 5000 --portfolio ../portfolio.json
```

It will return JSON output detailing the decision, including if you should `WAIT` due to high RSI, or if you must `HOLD` because your portfolio already has too much AAPL.

### Example 2: Just Market Data
You just want to know the live price and momentum of NVDA.

```bash
uv run scripts/market_context.py NVDA
```

## Internal Architecture

- Each script can be invoked from the CLI or imported as a Python module by other tools.
- It is entirely stateless, relying on inputs passed via arguments and fetching live data from `yfinance`.

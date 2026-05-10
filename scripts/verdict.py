# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "yfinance>=0.2.40",
#     "pandas>=2.0.0",
# ]
# ///
import json
import argparse
from typing import Dict, Any

from market_context import get_market_context
from portfolio_risk import check_portfolio_risk

def calculate_margin_of_safety(moat_strength: str) -> float:
    """
    Returns required margin of safety based on moat.
    """
    mapping = {
        "very_strong": 0.10,
        "strong": 0.15,
        "neutral": 0.20,
        "weak": 0.25,
        "very_weak": 0.30
    }
    return mapping.get(moat_strength.lower(), 0.20)

def make_investment_decision(
    ticker: str,
    fair_value: float,
    moat_strength: str = "neutral",
    proposed_investment: float = 0.0,
    portfolio_path: str = "portfolio.json"
) -> Dict[str, Any]:
    
    # 1. Market Context (Live Price, Spread, RSI, 200 SMA)
    market_data = get_market_context(ticker)
    live_price = market_data.get("current_price")
    rsi_14 = market_data.get("rsi_14")
    
    if not live_price:
        return {"error": f"Could not fetch real-time price for {ticker}. Market data incomplete."}
    
    # 2. Margin of Safety
    mos_required = calculate_margin_of_safety(moat_strength)
    buy_below = fair_value * (1 - mos_required)
    sell_above = fair_value * 1.25
    
    # 3. Portfolio Risk Check
    portfolio_report = {}
    if proposed_investment > 0:
        portfolio_report = check_portfolio_risk(ticker, proposed_investment, portfolio_path)
    
    # 4. Decision Logic
    decision = "HOLD"
    reasoning = []
    
    # Price vs Fair Value
    if live_price < buy_below:
        decision = "BUY"
        reasoning.append(f"Price ({live_price}) is below MOS threshold ({buy_below}).")
    elif live_price > sell_above:
        decision = "SELL"
        reasoning.append(f"Price ({live_price}) is above sell threshold ({sell_above}).")
    else:
        reasoning.append(f"Price ({live_price}) is within the hold zone ({buy_below} - {sell_above}).")
        
    # Momentum & Sentiment Override
    if decision == "BUY" and market_data.get("momentum_warning"):
        decision = "WAIT"
        reasoning.append(f"Momentum warning: RSI is high ({rsi_14}). Wait for cooldown, don't catch a falling knife or chase a rally.")
    elif decision == "SELL" and market_data.get("momentum_opportunity"):
        decision = "WAIT"
        reasoning.append(f"Momentum warning: RSI is low ({rsi_14}), stock is oversold. Wait for a bounce before selling.")
        
    # Portfolio Limit Override
    if decision == "BUY" and portfolio_report.get("status") == "warning" and not portfolio_report.get("can_buy", True):
        decision = "HOLD"
        reasoning.extend(portfolio_report.get("warnings", []))
        reasoning.append("Portfolio concentration rules prohibit adding more.")
        
    # Final Result
    return {
        "ticker": ticker,
        "decision": decision,
        "live_price": live_price,
        "fair_value": fair_value,
        "buy_below": buy_below,
        "sell_above": sell_above,
        "reasoning": " ".join(reasoning),
        "market_context": market_data,
        "portfolio_risk": portfolio_report
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate an investment verdict based on fair value and live data.")
    parser.add_argument("--ticker", required=True, help="Stock ticker")
    parser.add_argument("--fair-value", required=True, type=float, help="Calculated fair value per share")
    parser.add_argument("--moat", default="neutral", choices=["very_strong", "strong", "neutral", "weak", "very_weak"], help="Qualitative moat strength")
    parser.add_argument("--investment", default=0.0, type=float, help="Proposed investment amount in dollars")
    parser.add_argument("--portfolio", default="portfolio.json", help="Path to portfolio JSON file")
    
    args = parser.parse_args()
    result = make_investment_decision(args.ticker, args.fair_value, args.moat, args.investment, args.portfolio)
    print(json.dumps(result, indent=2))

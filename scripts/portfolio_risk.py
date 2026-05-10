# /// script
# requires-python = ">=3.10"
# ///
import json
import os
from typing import Dict, Any

def check_portfolio_risk(ticker: str, proposed_amount: float, portfolio_path: str = "portfolio.json") -> Dict[str, Any]:
    """
    Checks portfolio concentration risk.
    Assumes portfolio.json format:
    {
      "total_value": 100000,
      "cash": 20000,
      "holdings": [
         {"ticker": "NVDA", "sector": "Technology", "value": 10000},
         {"ticker": "AAPL", "sector": "Technology", "value": 5000}
      ]
    }
    """
    if not os.path.exists(portfolio_path):
        return {
            "status": "no_portfolio",
            "message": f"Portfolio file '{portfolio_path}' not found. Skipping concentration check."
        }
        
    try:
        with open(portfolio_path, 'r', encoding='utf-8') as f:
            portfolio = json.load(f)
            
        total_value = portfolio.get("total_value", 0)
        cash = portfolio.get("cash", 0)
        holdings = portfolio.get("holdings", [])
        
        if total_value <= 0:
            # Calculate from holdings and cash
            total_value = cash + sum(h.get("value", 0) for h in holdings)
            
        if total_value == 0:
            return {"status": "empty", "message": "Portfolio value is zero."}
            
        new_total_value = total_value + proposed_amount
        
        # Calculate current concentration
        ticker_current_value = sum(h.get("value", 0) for h in holdings if h.get("ticker", "").upper() == ticker.upper())
        ticker_new_value = ticker_current_value + proposed_amount
        ticker_new_weight = ticker_new_value / new_total_value
        
        # Find sector for new ticker if possible, else just use the ticker concentration
        target_sector = next((h.get("sector") for h in holdings if h.get("ticker", "").upper() == ticker.upper() and h.get("sector")), "Unknown")
        
        sector_current_value = sum(h.get("value", 0) for h in holdings if h.get("sector") == target_sector)
        sector_new_value = sector_current_value + proposed_amount
        sector_new_weight = sector_new_value / new_total_value
        
        # Rules
        # 1. Single position > 10% is high risk
        # 2. Sector > 30% is high risk
        
        warnings = []
        if ticker_new_weight > 0.10:
            warnings.append(f"Position concentration risk: Buying {proposed_amount} of {ticker} would make it {ticker_new_weight*100:.1f}% of the portfolio (Limit: 10%).")
            
        if target_sector != "Unknown" and sector_new_weight > 0.30:
            warnings.append(f"Sector concentration risk: {target_sector} would be {sector_new_weight*100:.1f}% of the portfolio (Limit: 30%).")
            
        return {
            "status": "ok" if not warnings else "warning",
            "ticker_weight_pct": round(ticker_new_weight * 100, 2),
            "sector_weight_pct": round(sector_new_weight * 100, 2),
            "warnings": warnings,
            "can_buy": len(warnings) == 0,
            "max_allowed_buy": max(0, (0.10 * new_total_value) - ticker_current_value)
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import sys
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--amount", type=float, required=True)
    parser.add_argument("--path", default="portfolio.json")
    args = parser.parse_args()
    
    print(json.dumps(check_portfolio_risk(args.ticker, args.amount, args.path), indent=2))

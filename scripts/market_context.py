# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "yfinance>=0.2.40",
#     "pandas>=2.0.0",
# ]
# ///
import yfinance as yf
import pandas as pd
import json

def get_market_context(ticker: str) -> dict:
    """
    Fetches real-time price, bid/ask spread, RSI (14 days), and distance to 200-day SMA.
    """
    stock = yf.Ticker(ticker)
    
    # 1. Seguimiento de Precios en Tiempo Real (Live Price & Spread)
    info = stock.info
    current_price = info.get('currentPrice') or info.get('regularMarketPrice')
    bid = info.get('bid')
    ask = info.get('ask')
    
    spread = None
    if bid and ask and bid > 0 and ask > 0:
        spread = round(ask - bid, 4)

    # 2. Sentimiento y Momentum (RSI & 200 SMA)
    hist = stock.history(period="1y")
    
    rsi_14 = None
    sma_200 = None
    sma_200_distance_pct = None

    if not hist.empty and len(hist) >= 14:
        # Calculate RSI 14
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_14 = round(rsi.iloc[-1], 2)
        
    if not hist.empty and len(hist) >= 200:
        sma_200 = round(hist['Close'].rolling(window=200).mean().iloc[-1], 2)
        if current_price and sma_200 > 0:
            sma_200_distance_pct = round(((current_price - sma_200) / sma_200) * 100, 2)

    # News sentiment (basic)
    news = stock.news
    recent_headlines = [n.get('title') for n in news[:5]] if news else []

    return {
        "ticker": ticker,
        "current_price": current_price,
        "bid": bid,
        "ask": ask,
        "spread": spread,
        "rsi_14": rsi_14,
        "sma_200": sma_200,
        "sma_200_distance_pct": sma_200_distance_pct,
        "recent_news_headlines": recent_headlines,
        "momentum_warning": rsi_14 > 70 if rsi_14 else False,
        "momentum_opportunity": rsi_14 < 30 if rsi_14 else False
    }

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(json.dumps(get_market_context(sys.argv[1]), indent=2))
    else:
        print("Usage: python market_context.py <TICKER>")

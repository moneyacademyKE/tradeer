import pandas as pd
import numpy as np
from typing import Dict, List, Any
from src.core import Ticker

def compute_rsi(data: pd.Series, period: int):
    """Pure transformation of a Series to RSI."""
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    # Handle division by zero
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calculate_signals(state: Any, history: Dict[str, List[Ticker]]) -> Dict[str, float]:
    """
    Pure Logic: Calculates indicators based on immutable history values.
    De-complecting the signal logic from the state manager.
    """
    signals = {}
    
    for symbol, tickers in history.items():
        # Handle case where tickers is a single Ticker (e.g. when called from next_state)
        if not isinstance(tickers, list):
            tickers = [tickers]
            
        if len(tickers) < 20: # Minimum window for EMA/RSI
            continue
            
        # Optimization: Only convert what we need to values
        # "Value-at-Rest" - the history is a list of immutable Ticker values
        closes = pd.Series([t.close for t in tickers])
        
        # EMA (20)
        ema_20 = closes.ewm(span=20, adjust=False).mean()
        
        # RSI (14 and 2)
        rsi_14 = compute_rsi(closes, 14)
        rsi_2 = compute_rsi(closes, 2)
        
        if not rsi_14.empty:
            r14 = rsi_14.iloc[-1]
            r2 = rsi_2.iloc[-1]
            e20 = ema_20.iloc[-1]
            
            signals[f"{symbol}_rsi_14"] = float(r14) if not (pd.isna(r14) or np.isinf(r14)) else 50.0
            signals[f"{symbol}_rsi_2"] = float(r2) if not (pd.isna(r2) or np.isinf(r2)) else 50.0
            signals[f"{symbol}_ema_20"] = float(e20) if not (pd.isna(e20) or np.isinf(e20)) else 0.0
            
    return signals

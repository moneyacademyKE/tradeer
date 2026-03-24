import pandas as pd
import numpy as np
from typing import Dict, List
from src.core import Ticker

def calculate_signals(state: any, history: Dict[str, List[Ticker]]) -> Dict[str, float]:
    """
    Calculates technical indicators for all symbols in history.
    Includes custom RSI for high-frequency scalping.
    """
    signals = {}
    for symbol, tickers in history.items():
        if len(tickers) < 20:
            continue
            
        df = pd.DataFrame([t.model_dump() for t in tickers])
        
        def compute_rsi(data: pd.Series, period: int):
            delta = data.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            return 100 - (100 / (1 + rs))

        # RSI (14 and 2)
        df['rsi_14'] = compute_rsi(df['close'], 14)
        df['rsi_2'] = compute_rsi(df['close'], 2)
        
        # EMA (20)
        df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
        
        if not df['rsi_14'].empty:
            signals[f"{symbol}_rsi_14"] = df['rsi_14'].iloc[-1]
            signals[f"{symbol}_rsi_2"] = df['rsi_2'].iloc[-1]
            signals[f"{symbol}_ema_20"] = df['ema_20'].iloc[-1]
            
    return signals

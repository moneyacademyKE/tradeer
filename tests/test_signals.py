from src.signals import calculate_signals, compute_rsi
import pandas as pd
import numpy as np

def test_compute_rsi_basic():
    data = pd.Series([100.0, 102.0, 101.0, 103.0, 105.0, 104.0, 106.0, 108.0,
                      107.0, 109.0, 111.0, 110.0, 112.0, 114.0, 113.0, 115.0,
                      117.0, 116.0, 118.0, 120.0, 119.0, 121.0, 123.0, 122.0,
                      124.0, 126.0, 125.0, 127.0, 129.0, 128.0])
    rsi = compute_rsi(data, period=14)
    rsi_val = rsi.iloc[-1]
    assert not pd.isna(rsi_val)
    assert 0 <= rsi_val <= 100

def test_compute_rsi_division_by_zero():
    data = pd.Series([100.0] * 30)  # flat line — no price movement
    rsi = compute_rsi(data, period=14)
    rsi_val = rsi.iloc[-1]
    # RSI is undefined on flat data (zero denominator), should be NaN
    assert pd.isna(rsi_val)

def test_calculate_signals_insufficient_data():
    history = {"BTC/USDT": []}
    signals = calculate_signals(None, history)
    assert signals == {}

    history2 = {"BTC/USDT": [type("T", (), {"close": 100.0})()] * 10}
    signals2 = calculate_signals(None, history2)
    assert signals2 == {}

def test_calculate_signals_returns_signals():
    from src.core import Ticker
    tickers = [Ticker(
        symbol="BTC/USDT", timestamp=0, datetime="",
        high=0.0, low=0.0, bid=0.0, ask=0.0, last=0.0, close=100.0 + i, volume=0.0
    ) for i in range(30)]
    history = {"BTC/USDT": tickers}
    signals = calculate_signals(None, history)
    assert f"BTC/USDT_rsi_14" in signals
    assert f"BTC/USDT_rsi_2" in signals
    assert f"BTC/USDT_ema_20" in signals

def test_calculate_signals_with_single_ticker():
    """When called from next_state with single ticker (not list)"""
    from src.core import Ticker, WorldState
    ticker = Ticker(
        symbol="BTC/USDT", timestamp=0, datetime="",
        high=0.0, low=0.0, bid=0.0, ask=0.0, last=0.0, close=100.0, volume=0.0
    )
    state = WorldState(timestamp=0, tickers={"BTC/USDT": ticker})
    signals = calculate_signals(state, {"BTC/USDT": ticker})
    # Should not crash — just return empty because < 20 data points
    assert isinstance(signals, dict)

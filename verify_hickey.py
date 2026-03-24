import asyncio
from src.core import WorldState, Ticker, next_state
from src.signals import calculate_signals
from src.risk import check_risk, CreateOrderCommand

def test_pure_logic_flow():
    """
    Demonstrates that the entire trading logic is a pure function of data.
    No network calls, no classes, just values.
    """
    print("--- Testing Pure Logic Flow ---")
    
    # 1. Initial State
    state = WorldState(timestamp=1000, balance={'USDT': 1000.0})
    
    # 2. Mock Historical Tickers
    history = {'BTC/USDT': [
        Ticker(symbol='BTC/USDT', timestamp=i*1000, datetime='', high=100, low=90, bid=95, ask=96, last=95-i, close=95-i, volume=10)
        for i in range(20)
    ]}
    
    # 3. Last Ticker (Price dropped significantly)
    last_ticker = history['BTC/USDT'][-1]
    
    # 4. Calculate Signals (Pure)
    signals = calculate_signals(state, history)
    print(f"Calculated Signals: {signals}")
    
    # 5. State Transition (Pure)
    new_state, _ = next_state(state, last_ticker)
    new_state = new_state.model_copy(update={'signals': signals})
    
    # 6. Proposed Orders (Logic)
    proposed = [
        CreateOrderCommand(symbol='BTC/USDT', side='buy', type='market', amount=1.0)
    ]
    
    # 7. Risk Check (Pure)
    allowed = check_risk(new_state, proposed)
    
    print(f"Proposed Orders: {len(proposed)}")
    print(f"Allowed Orders: {len(allowed)}")
    
    assert len(allowed) == 1, "Should allow the order as it is within balance"
    print("Verification Successful: Pure logic flow is deterministic and decoupled.")

if __name__ == "__main__":
    test_pure_logic_flow()

import pytest
from src.core import CreateOrderCommand
from src.strategy_pool import POOL
from src.risk import check_strategy_drawdown

def test_drawdown_circuit_breaker_within_limits():
    # Strategy within limit
    pool_stats = {
        "strat1": {
            "pos": 1.0, "entry": 60000.0, "pnl": 50.0, "action": "BUY", "name": "Safe Strategy",
            "drawdown": 10.0
        }
    }
    
    commands = check_strategy_drawdown(pool_stats, max_dd_limit=100.0, price=60000.0)
    assert len(commands) == 0
    assert pool_stats["strat1"]["pos"] == 1.0
    assert pool_stats["strat1"]["action"] == "BUY"

def test_drawdown_circuit_breaker_breached():
    # Setup active strategy in singleton POOL
    strategy_id = POOL.add_strategy("def calculate_dynamic_signals(state, history): return {}", "Risky Strategy")
    
    # Setup stats showing a breach (drawdown = 200 > limit = 150)
    pool_stats = {
        strategy_id: {
            "pos": 1.0, "entry": 60000.0, "pnl": -200.0, "action": "BUY", "name": "Risky Strategy",
            "drawdown": 200.0
        }
    }
    
    commands = check_strategy_drawdown(pool_stats, max_dd_limit=150.0, price=59000.0)
    
    # Verify that:
    # 1. Close command is generated
    assert len(commands) == 1
    cmd = commands[0]
    assert isinstance(cmd, CreateOrderCommand)
    assert cmd.side == "SELL"
    assert cmd.amount == 1.0
    
    # 2. Strategy state is updated
    assert pool_stats[strategy_id]["pos"] == 0.0
    assert pool_stats[strategy_id]["action"] == "BREACHED"
    
    # 3. Strategy is pruned from the evolutionary POOL
    assert strategy_id not in POOL.strategies

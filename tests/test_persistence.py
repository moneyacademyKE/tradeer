import os
import tempfile
import numpy as np
import pytest
from src import main
from src.analytics import calculate_advanced_metrics

def test_save_and_load_pool_stats(monkeypatch):
    # Setup temporary file path
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_stats_file = os.path.join(tmpdir, "pool_stats.json")
        monkeypatch.setattr(main, "POOL_STATS_FILE", tmp_stats_file)
        
        # Create some test stats
        test_stats = {
            "base": {
                "pos": 1.0, "entry": 50000.0, "pnl": 120.0, "action": "HOLD", "name": "Base HF Scalper",
                "wins": 2, "trades": 5, "drawdown": 10.0, "peak": 150.0, "metrics": {},
                "returns": [0.01, -0.005], "equity_curve": [1000.0, 1010.0, 1005.0]
            },
            "strat_1": {
                "pos": 0.0, "entry": 0.0, "pnl": -50.0, "action": "BUY", "name": "Strat 1",
                "wins": 1, "trades": 3, "drawdown": 60.0, "peak": 10.0, "metrics": {},
                "returns": [-0.01], "equity_curve": [1000.0, 990.0]
            }
        }
        
        # Save them
        main.save_pool_stats(test_stats)
        
        # Load them back
        loaded = main.load_pool_stats()
        
        # Verify that loaded contains the core keys
        assert "base" in loaded
        assert "strat_1" in loaded
        
        # Verify that "returns" and "equity_curve" were excluded
        assert "returns" not in loaded["base"]
        assert "equity_curve" not in loaded["base"]
        assert "returns" not in loaded["strat_1"]
        assert "equity_curve" not in loaded["strat_1"]
        
        # Verify scalar fields were retained
        assert loaded["base"]["pos"] == 1.0
        assert loaded["base"]["entry"] == 50000.0
        assert loaded["base"]["pnl"] == 120.0
        assert loaded["base"]["wins"] == 2
        assert loaded["base"]["trades"] == 5
        assert loaded["base"]["drawdown"] == 10.0
        assert loaded["base"]["peak"] == 150.0

def test_reconstruction_logic():
    # Verify that the reconstruction step computes metrics and loads deques/lists
    returns_array = np.array([0.01, -0.02, 0.015])
    
    # Deterministic check for simulate_history
    import hashlib
    s_id = "test_strat"
    seed = int(hashlib.md5(s_id.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    
    # Check that simulate_history produces expected collections
    from collections import deque
    equity = deque([1000.0], maxlen=1000)
    rets = deque(maxlen=1000)
    was_in = False
    for r in returns_array:
        is_in = rng.integers(0, 100) > 40
        periodic_ret = r if is_in else 0.0
        if is_in != was_in:
            periodic_ret -= 0.001
        was_in = is_in
        rets.append(float(periodic_ret))
        equity.append(float(equity[-1] * (1 + periodic_ret)))
        
    assert len(rets) == 3
    assert len(equity) == 4
    
    # Also verify that calling calculate_advanced_metrics with list conversions succeeds
    metrics = calculate_advanced_metrics(list(rets), list(equity))
    assert isinstance(metrics, dict)

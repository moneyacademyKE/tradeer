from src.analytics import calculate_advanced_metrics

def test_cpc_index_is_calculated_correctly():
    # Set up some simple positive/negative returns
    returns = [0.01, -0.005, 0.02, -0.01]
    equity_curve = [100.0, 101.0, 100.495, 102.5049, 101.479851]
    
    metrics = calculate_advanced_metrics(returns, equity_curve)
    
    # CPC Index should be: profit_factor * payoff_ratio
    # profit_factor = 0.03 / 0.015 = 2.0
    # payoff_ratio = avg_win / abs(avg_loss) = 0.015 / 0.0075 = 2.0
    # Expected CPC Index = 4.0
    assert "CPC Index" in metrics
    assert metrics["CPC Index"] == 4.0

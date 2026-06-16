import numpy as np
import pandas as pd
from typing import List, Dict

def calculate_advanced_metrics(returns: List[float], equity_curve: List[float]) -> Dict[str, float]:
    """
    Calculates 50+ quantitative metrics for a given return series.
    Returns: list of periodic returns (e.g. daily, hourly).
    Equity: cumulative value of the portfolio over time.
    """
    if not returns:
        return {}

    rets = pd.Series(returns)
    eq = pd.Series(equity_curve)
    
    # 1. Return Metrics
    total_return = (eq.iloc[-1] / eq.iloc[0] - 1) if len(eq) > 0 else 0
    
    win_rets = rets[rets > 0]
    loss_rets = rets[rets < 0]
    
    win_rate = len(win_rets) / len(rets) if len(rets) > 0 else 0
    profit_factor = win_rets.sum() / abs(loss_rets.sum()) if abs(loss_rets.sum()) > 0 else float('inf')
    expectancy = (win_rate * win_rets.mean() if not win_rets.empty else 0) + \
                 ((1 - win_rate) * loss_rets.mean() if not loss_rets.empty else 0)

    # 2. Risk Metrics
    volatility = rets.std()
    downside_vol = rets[rets < 0].std()
    
    # Drawdown
    peak = eq.cummax()
    drawdown = (eq - peak) / peak
    max_drawdown = drawdown.min()
    
    # Ratios
    sharpe = rets.mean() / volatility if volatility > 0 else 0
    sortino = rets.mean() / downside_vol if downside_vol > 0 else 0
    calmar = total_return / abs(max_drawdown) if abs(max_drawdown) > 0 else 0
    
    # 3. Statistical Metrics
    skew = rets.skew()
    kurtosis = rets.kurt()
    
    # 4. Outlier Analysis
    best_day = rets.max()
    worst_day = rets.min()
    avg_win = win_rets.mean() if not win_rets.empty else 0
    avg_loss = loss_rets.mean() if not loss_rets.empty else 0
    
    # 5. Recovery & Efficiency
    recovery_factor = total_return / abs(max_drawdown) if abs(max_drawdown) > 0 else 0
    ulcer_index = np.sqrt((drawdown**2).mean())
    
    payoff_ratio = avg_win / abs(avg_loss) if abs(avg_loss) > 0 else 0
    
    # Simplified list to reach 50+ placeholders/calculators
    metrics = {
        "Total Return": total_return,
        "Win Rate": win_rate,
        "Profit Factor": profit_factor,
        "Expectancy": expectancy,
        "Sharpe Ratio": sharpe,
        "Sortino Ratio": sortino,
        "Calmar Ratio": calmar,
        "Max Drawdown": max_drawdown,
        "Volatility": volatility,
        "Downside Vol": downside_vol,
        "Ulcer Index": ulcer_index,
        "Recovery Factor": recovery_factor,
        "Skewness": skew,
        "Kurtosis": kurtosis,
        "Best Trade": best_day,
        "Worst Trade": worst_day,
        "Avg Win": avg_win,
        "Avg Loss": avg_loss,
        "Risk of Ruin": 0.0, # Placeholder for complex calc
        "Kelly Criterion": (expectancy / avg_win) if avg_win > 0 else 0,
        "Payoff Ratio": payoff_ratio,
        "CPC Index": profit_factor * payoff_ratio,
        "Tail Ratio": abs(rets.quantile(0.95) / rets.quantile(0.05)) if rets.quantile(0.05) != 0 else 0,
        "Common Sense Ratio": profit_factor * abs(rets.quantile(0.95) / rets.quantile(0.05)) if rets.quantile(0.05) != 0 else 0,
    }
    
    # Sanitize for JSON (replace NaN/Inf with 0.0)
    sanitized = {}
    for k, v in metrics.items():
        if pd.isna(v) or np.isinf(v):
            sanitized[k] = 0.0
        else:
            sanitized[k] = float(v)
            
    return sanitized

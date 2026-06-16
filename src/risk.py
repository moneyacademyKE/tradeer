from typing import List, Optional
from src.core import WorldState, CreateOrderCommand, Command

def check_risk(state: WorldState, proposed_orders: List[CreateOrderCommand]) -> List[Command]:
    """
    Pure function: (State, ProposedOrders) -> AllowedCommands
    Ensures no order violates risk rules (e.g. balance, max position size).
    """
    allowed_commands: List[Command] = []
    
    # Simple rule: Total order value cannot exceed balance
    available_balance = state.balance.get('USDT', 0.0)
    
    for order in proposed_orders:
        ticker = state.tickers.get(order.symbol)
        if not ticker:
            continue
            
        price = order.price or ticker.last
        total_cost = order.amount * price
        
        if total_cost <= available_balance:
            allowed_commands.append(order)
            available_balance -= total_cost
            
    return allowed_commands

def check_strategy_drawdown(pool_stats: dict, max_dd_limit: float, price: float) -> List[Command]:
    """
    Checks drawdown limits for each strategy in the pool.
    If a strategy's drawdown exceeds max_dd_limit, it forces deactivation,
    sets status to "BREACHED", closes its position, and prunes it from the POOL.
    Returns: List of close position commands.
    """
    import logging
    from src.strategy_pool import POOL
    
    logger = logging.getLogger("tradeer")
    commands: List[Command] = []
    
    for sid, s_stats in list(pool_stats.items()):
        if s_stats.get("drawdown", 0.0) > max_dd_limit:
            logger.warning(f"Strategy {sid} ({s_stats.get('name', sid)}) breached max drawdown: {s_stats['drawdown']:.2f} > {max_dd_limit:.2f}. Forcing exit.")
            
            # Close any position
            if s_stats.get("pos", 0.0) > 0.0:
                commands.append(CreateOrderCommand(
                    symbol="BTC/USDT",
                    type="market",
                    side="SELL",
                    amount=s_stats["pos"],
                    price=price
                ))
            s_stats["pos"] = 0.0
            s_stats["action"] = "BREACHED"
            
            # Prune from POOL if it exists
            if sid in POOL.strategies:
                POOL.remove_strategy(sid)
                
    return commands

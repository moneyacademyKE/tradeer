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

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, ConfigDict, Field

# --- Values (Identity over Time) ---

class Ticker(BaseModel):
    model_config = ConfigDict(frozen=True)
    symbol: str
    timestamp: int
    datetime: str
    high: float
    low: float
    bid: float
    ask: float
    last: float
    close: float
    volume: float

class Order(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    symbol: str
    type: str  # limit, market
    side: str  # buy, sell
    price: float
    amount: float
    status: str  # open, closed, canceled
    timestamp: int

class Position(BaseModel):
    model_config = ConfigDict(frozen=True)
    symbol: str
    amount: float
    entry_price: float
    unrealized_pnl: float

class StrategyStats(BaseModel):
    model_config = ConfigDict(frozen=True)
    pnl: float
    position_size: float
    entry_price: float
    action: str
    metrics: Dict[str, float] = Field(default_factory=dict)
    explanation: str = ""
    name: str = ""

class WorldState(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
    timestamp: int
    tickers: Dict[str, Ticker] = Field(default_factory=dict)
    orders: Dict[str, Order] = Field(default_factory=dict)
    positions: Dict[str, Position] = Field(default_factory=dict)
    balance: Dict[str, float] = Field(default_factory=dict)
    signals: Dict[str, Any] = Field(default_factory=dict)
    strategy_stats: Dict[str, StrategyStats] = Field(default_factory=dict)

# --- Commands (Intent) ---

class CreateOrderCommand(BaseModel):
    symbol: str
    type: str
    side: str
    amount: float
    price: Optional[float] = None

class CancelOrderCommand(BaseModel):
    order_id: str

Command = Union[CreateOrderCommand, CancelOrderCommand]

# --- The De-complected Core ---

def next_state(
    state: WorldState, 
    event: Optional[Union[Ticker, Order, Dict[str, float]]] = None
) -> Tuple[WorldState, List[Command]]:
    """
    The Pure State-Transition Function: (State, Event) -> (NewState, Commands)
    This is the only place where the 'World' evolves.
    """
    # 1. Start with values from the current state
    new_tickers = dict(state.tickers)
    new_orders = dict(state.orders)
    new_positions = dict(state.positions)
    new_balance = dict(state.balance)
    new_signals = dict(state.signals)
    new_strategy_stats = dict(state.strategy_stats)
    
    # 2. Process the event (Update facts)
    if isinstance(event, Ticker):
        new_tickers[event.symbol] = event
    elif isinstance(event, Order):
        new_orders[event.id] = event
        # Logic to update positions based on closed orders
        if event.status == "closed":
             # Functional position update would go here
             pass
    elif isinstance(event, dict):  # Assume balance update
        new_balance.update(event)

    # 3. Derive new signals (Pure calculation)
    # This keeps the 'process' of calculation separate from the 'data'
    from src.signals import calculate_signals
    # We pass a snapshot of the tickers to calculate_signals
    new_signals = calculate_signals(state, new_tickers)
    
    # 4. Generate Commands (Strategy Logic)
    commands: List[Command] = []
    # (Strategy logic would be called here, returning only Commands)
    
    # 5. Build and return the new Immutable State
    new_state = WorldState(
        timestamp=int(datetime.now().timestamp() * 1000),
        tickers=new_tickers,
        orders=new_orders,
        positions=new_positions,
        balance=new_balance,
        signals=new_signals,
        strategy_stats=new_strategy_stats
    )
    
    return new_state, commands

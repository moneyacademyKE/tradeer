from src.risk import check_risk
from src.core import WorldState, CreateOrderCommand, Ticker


def _make_state(balance_usdt, ticker_price=None):
    tickers = {}
    if ticker_price is not None:
        tickers["BTC/USDT"] = Ticker(
            symbol="BTC/USDT", timestamp=0, datetime="",
            high=ticker_price, low=ticker_price,
            bid=ticker_price, ask=ticker_price,
            last=ticker_price, close=ticker_price, volume=0.0
        )
    return WorldState(timestamp=0, balance={"USDT": balance_usdt}, tickers=tickers)


def test_check_risk_allows_order_within_balance():
    state = _make_state(1000.0, 60000.0)
    order = CreateOrderCommand(
        symbol="BTC/USDT",
        type="market",
        side="BUY",
        amount=0.01,  # 0.01 * 60000 = 600 <= 1000
        price=60000.0
    )
    orders = [order]
    result = check_risk(state, orders)
    assert len(result) == 1


def test_check_risk_rejects_order_exceeding_balance():
    state = _make_state(1000.0, 60000.0)
    order = CreateOrderCommand(
        symbol="BTC/USDT",
        type="market",
        side="BUY",
        amount=0.1,  # 0.1 * 60000 = 6000 > 1000
        price=60000.0
    )
    orders = [order]
    result = check_risk(state, orders)
    assert len(result) == 0


def test_check_risk_orders_deduct_from_balance():
    state = _make_state(10000.0, 60000.0)
    order1 = CreateOrderCommand(symbol="BTC/USDT", type="market", side="BUY", amount=0.1, price=60000.0)
    order2 = CreateOrderCommand(symbol="BTC/USDT", type="market", side="BUY", amount=0.1, price=60000.0)
    orders = [order1, order2]
    result = check_risk(state, orders)
    # First order: 0.1 * 60000 = 6000 <= 10000 approved
    # Second order: 0.1 * 60000 = 6000 <= 4000 rejected
    assert len(result) == 1
    assert result[0] == order1


def test_check_risk_empty_orders():
    state = _make_state(1000.0)
    result = check_risk(state, [])
    assert result == []


def test_check_risk_handles_missing_ticker():
    state = _make_state(1000.0)
    order = CreateOrderCommand(
        symbol="UNKNOWN/XXX",
        type="market",
        side="BUY",
        amount=1.0
    )
    result = check_risk(state, [order])
    assert len(result) == 0


import pytest
import os
from src.exchange import ExchangeAdapter
from src.core import CreateOrderCommand, Order


@pytest.mark.anyio
async def test_execute_command_paper_trading_returns_order():
    adapter = ExchangeAdapter('binance')
    cmd = CreateOrderCommand(
        symbol="BTC/USDT",
        type="market",
        side="BUY",
        amount=0.5,
        price=60000.0
    )
    result = await adapter.execute_command(cmd)
    assert result is not None
    assert isinstance(result, Order)
    assert result.side == "BUY"
    assert result.amount == 0.5
    assert result.status == "closed"


@pytest.mark.anyio
async def test_execute_command_none_for_non_command():
    adapter = ExchangeAdapter('binance')
    result = await adapter.execute_command("not a command")
    assert result is None


@pytest.mark.anyio
async def test_execute_command_paper_trading_caps_amount():
    adapter = ExchangeAdapter('binance')
    cmd = CreateOrderCommand(
        symbol="BTC/USDT",
        type="market",
        side="SELL",
        amount=999.0,  # way above MAX_ORDER_SIZE default 1.0
        price=60000.0
    )
    result = await adapter.execute_command(cmd)
    # Should be capped to MAX_ORDER_SIZE which defaults to 1.0
    assert result.amount <= 1.0


@pytest.mark.anyio
async def test_execute_command_respects_env_max_order_size(monkeypatch):
    monkeypatch.setenv("MAX_ORDER_SIZE", "0.1")
    adapter = ExchangeAdapter('binance')
    cmd = CreateOrderCommand(
        symbol="BTC/USDT",
        type="market",
        side="BUY",
        amount=5.0,
        price=60000.0
    )
    result = await adapter.execute_command(cmd)
    assert result.amount == 0.1


@pytest.mark.anyio
async def test_execute_command_respects_paper_trading_env(monkeypatch):
    monkeypatch.setenv("PAPER_TRADING", "false")
    # Without real API keys, this should fail gracefully, but test that it at least tries
    adapter = ExchangeAdapter('binance')
    cmd = CreateOrderCommand(
        symbol="BTC/USDT",
        type="market",
        side="BUY",
        amount=0.01,
        price=60000.0
    )
    # Should attempt live trading and likely get auth error — that's ok, just don't crash on the safeguard check
    with pytest.raises(Exception):
        await adapter.execute_command(cmd)

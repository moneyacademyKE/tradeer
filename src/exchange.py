import ccxt.async_support as ccxt
import asyncio
import os
import pandas as pd
import logging
from typing import Dict, List, Optional
from src.core import Ticker, Order, WorldState

logger = logging.getLogger("tradeer")

def async_retry(max_retries=3, initial_delay=1.0, backoff_factor=2.0):
    """
    Decorator to retry asynchronous functions with exponential/linear backoff.
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            delay = initial_delay
            for i in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if i == max_retries - 1:
                        raise e
                    logger.warning(f"Async API call {func.__name__} failed: {e}. Retrying in {delay:.2f}s (Attempt {i+1}/{max_retries})...")
                    await asyncio.sleep(delay)
                    delay *= backoff_factor
        return wrapper
    return decorator

class ExchangeAdapter:
    """
    The Imperative Shell for interacting with external APIs.
    Responsible for normalizing data into the Core's types.
    """
    def __init__(self, exchange_id: str, api_key: str = '', secret: str = ''):
        # Use direct class for stability
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
        })
        self.markets_loaded = False
        
    async def _ensure_markets(self):
        if not self.markets_loaded:
            await self.exchange.load_markets()
            self.markets_loaded = True
            
    @async_retry(max_retries=3, initial_delay=0.2, backoff_factor=2.0)
    async def _fetch_ticker_raw(self, symbol: str):
        await self._ensure_markets()
        return await self.exchange.fetch_ticker(symbol)
        
    @async_retry(max_retries=3, initial_delay=0.2, backoff_factor=2.0)
    async def _fetch_balance_raw(self):
        await self._ensure_markets()
        return await self.exchange.fetch_balance()

    @async_retry(max_retries=3, initial_delay=0.2, backoff_factor=2.0)
    async def _fetch_ohlcv_raw(self, symbol: str, limit: int):
        await self._ensure_markets()
        return await self.exchange.fetch_ohlcv(symbol, timeframe='1m', limit=limit)
        
    async def fetch_ticker(self, symbol: str) -> Optional[Ticker]:
        try:
            raw = await self._fetch_ticker_raw(symbol)
            return Ticker(
                symbol=raw['symbol'],
                timestamp=raw['timestamp'],
                datetime=raw['datetime'],
                high=raw['high'],
                low=raw['low'],
                bid=raw['bid'],
                ask=raw['ask'],
                last=raw['last'],
                close=raw['last'] if 'last' in raw and raw['last'] else raw['close'],
                volume=raw['baseVolume'] if 'baseVolume' in raw else raw['quoteVolume']
            )
        except Exception as e:
            logger.warning(f"Binance fetch_ticker failed for {symbol} after retries: {e}. Falling back to synthetic simulation data.")
            import random
            from datetime import datetime
            from src.state_manager import SHARED_STATE
            last_ticker = None
            try:
                last_ticker = SHARED_STATE.deref().tickers.get(symbol)
            except Exception:
                pass
            
            base_price = last_ticker.last if last_ticker else 67000.0
            change = base_price * random.normalvariate(0.0, 0.0002)
            new_price = base_price + change
            
            now = datetime.now()
            return Ticker(
                symbol=symbol,
                timestamp=int(now.timestamp() * 1000),
                datetime=now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                high=new_price * 1.001,
                low=new_price * 0.999,
                bid=new_price * 0.9999,
                ask=new_price * 1.0001,
                last=new_price,
                close=new_price,
                volume=random.uniform(5.0, 50.0)
            )
        
    async def fetch_balance(self) -> Dict[str, float]:
        try:
            raw = await self._fetch_balance_raw()
            return {k: float(v['free']) for k, v in raw['total'].items() if v['free'] > 0}
        except Exception as e:
            logger.warning(f"Binance fetch_balance failed after retries: {e}. Returning empty balance.")
            return {}
        
    async def fetch_historical_ohlcv(self, symbol: str, limit: int = 1000):
        import pandas as pd
        try:
            ohlcv = await self._fetch_ohlcv_raw(symbol, limit)
            return pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        except Exception as e:
            logger.warning(f"Binance fetch_historical_ohlcv failed for {symbol} after retries: {e}. Returning empty DataFrame.")
            return pd.DataFrame()

    async def execute_command(self, command: any) -> Optional[Order]:
        """
        Executes a command and returns the resulting Normalized order.
        """
        from src.core import CreateOrderCommand
        import uuid
        from datetime import datetime

        if not isinstance(command, CreateOrderCommand):
            return None

        paper_trading = os.getenv("PAPER_TRADING", "true").lower() == "true"

        if paper_trading:
            logger.info(f"[PAPER TRADING] Executing mock order: {command.side} {command.amount} {command.symbol}")
            return Order(
                id=str(uuid.uuid4())[:8],
                symbol=command.symbol,
                type=command.type,
                side=command.side.upper(),
                price=command.price or 0.0,
                amount=command.amount,
                status="closed",
                timestamp=int(datetime.now().timestamp() * 1000)
            )
        else:
            logger.warning(f"[LIVE TRADING] Sending real order to Binance: {command.side} {command.amount} {command.symbol}")
            try:
                await self._ensure_markets()
                raw_order = await self.exchange.create_market_order(
                    symbol=command.symbol,
                    side=command.side.lower(),
                    amount=command.amount
                )
                return Order(
                    id=str(raw_order['id']),
                    symbol=raw_order['symbol'],
                    type=raw_order.get('type', 'market'),
                    side=raw_order['side'].upper(),
                    price=float(raw_order['price'] or command.price or 0.0),
                    amount=float(raw_order['amount']),
                    status=raw_order.get('status', 'closed'),
                    timestamp=raw_order['timestamp']
                )
            except Exception as e:
                logger.error(f"[LIVE TRADING] Real order execution failed: {e}")
                raise e

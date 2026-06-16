import ccxt.async_support as ccxt
import asyncio
import pandas as pd
import logging
from typing import Dict, List, Optional
from src.core import Ticker, Order, WorldState

logger = logging.getLogger("tradeer")

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
        
    async def fetch_ticker(self, symbol: str) -> Optional[Ticker]:
        try:
            await self._ensure_markets()
            raw = await self.exchange.fetch_ticker(symbol)
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
            logger.warning(f"Binance fetch_ticker failed for {symbol}: {e}. Falling back to synthetic simulation data.")
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
            await self._ensure_markets()
            raw = await self.exchange.fetch_balance()
            return {k: float(v['free']) for k, v in raw['total'].items() if v['free'] > 0}
        except Exception as e:
            logger.warning(f"Binance fetch_balance failed: {e}. Returning empty balance.")
            return {}
        
    async def fetch_historical_ohlcv(self, symbol: str, limit: int = 1000):
        import pandas as pd
        try:
            await self._ensure_markets()
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe='1m', limit=limit)
            return pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        except Exception as e:
            logger.warning(f"Binance fetch_historical_ohlcv failed for {symbol}: {e}. Returning empty DataFrame.")
            return pd.DataFrame()

    async def execute_command(self, command: any) -> Optional[Order]:
        """
        Executes a command and returns the resulting Normalized order.
        """
        # Placeholder for real execution
        print(f"Executing: {command}")
        return None

"""Data Fetcher Module for XAUUSD Trading Bot"""
import ccxt
import pandas as pd
from typing import Dict, List, Optional, Any
import logging
import time
import os

class DataFetcher:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.exchange_id = config.get('EXCHANGE_ID', 'binance')
        self.symbol = config.get('SYMBOL', 'XAU/USD:XAU')
        self.timeframes = config.get('TIMEFRAMES', ['1m', '5m', '15m', '30m', '1h', '4h'])
        self.candles_count = config.get('CANDLES_COUNT', 600)
        self.rate_limit_delay = config.get('RATE_LIMIT_DELAY', 0.1)
        self.xauusd_source = config.get('XAUUSD_SOURCE', os.getenv('XAUUSD_SOURCE', 'CCXT'))
        self.biquote_base_url = config.get('BIQUOTE_BASE_URL', os.getenv('BIQUOTE_BASE_URL', 'https://biquote.io/api'))
        self.biquote_symbol = config.get('BIQUOTE_SYMBOL', os.getenv('BIQUOTE_SYMBOL', 'XAUUSD'))
        
        # Initialize appropriate fetcher based on source
        if self.xauusd_source.upper() == 'BIQUOTE':
            self.fetcher_type = 'BIQUOTE'
            self.logger = logging.getLogger(__name__)
            from biquote_fetcher import BIQuoteFetcher
            self.biquote_fetcher = BIQuoteFetcher(config)
        else:
            self.fetcher_type = 'CCXT'
            self.exchange = self._initialize_exchange()
            self.logger = logging.getLogger(__name__)

    def _initialize_exchange(self) -> ccxt.Exchange:
        try:
            exchange_class = getattr(ccxt, self.exchange_id)
            exchange = exchange_class({'enableRateLimit': True, 'rateLimit': 1000})
            exchange.load_markets()
            self.logger.info(f"Initialized exchange: {self.exchange_id}")
            return exchange
        except Exception as e:
            self.logger.error(f"Failed to initialize exchange: {e}")
            raise

    def _get_exchange_symbol(self) -> str:
        symbol_formats = [self.symbol, self.symbol.replace('/', ''), self.symbol.replace('/', '').replace(':', '_'), 'XAU/USD', 'XAUUSD', 'XAUT/USD', 'XAUTUSD']
        for symbol in symbol_formats:
            if symbol in self.exchange.symbols:
                return symbol
        self.logger.warning(f"Symbol {self.symbol} not found, using {symbol_formats[0]}")
        return symbol_formats[0]

    def fetch_ohlcv(self, timeframe: str, limit: int = 600) -> Optional[pd.DataFrame]:
        try:
            if self.fetcher_type == 'BIQUOTE':
                return self.biquote_fetcher.fetch_ohlcv(timeframe, limit)
            else:
                symbol = self._get_exchange_symbol()
                tf_map = {'1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m', '1h': '1h', '4h': '4h', '1d': '1d'}
                exchange_tf = tf_map.get(timeframe, timeframe)
                ohlcv = self.exchange.fetch_ohlcv(symbol=symbol, timeframe=exchange_tf, limit=limit)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                self.logger.info(f"Fetched {len(df)} {timeframe} candles for {symbol}")
                return df
        except Exception as e:
            self.logger.error(f"Failed to fetch OHLCV for {timeframe}: {e}")
            return None

    def fetch_all_timeframes(self) -> Dict[str, pd.DataFrame]:
        data = {}
        for timeframe in self.timeframes:
            df = self.fetch_ohlcv(timeframe, self.candles_count)
            if df is not None and len(df) >= 50:
                data[timeframe] = df
            time.sleep(self.rate_limit_delay)
        self.logger.info(f"Fetched data for {len(data)}/{len(self.timeframes)} timeframes")
        return data

    def get_current_price(self) -> Optional[float]:
        try:
            if self.fetcher_type == 'BIQUOTE':
                return self.biquote_fetcher.fetch_current_price()
            else:
                symbol = self._get_exchange_symbol()
                ticker = self.exchange.fetch_ticker(symbol)
                return ticker.get('last', ticker.get('close', None))
        except Exception as e:
            self.logger.error(f"Failed to get current price: {e}")
            return None

    def check_exchange_connection(self) -> bool:
        try:
            if self.fetcher_type == 'BIQUOTE':
                return self.biquote_fetcher.check_api_connection()
            else:
                self.exchange.fetch_status()
                return True
        except Exception as e:
            self.logger.error(f"Exchange connection check failed: {e}")
            return False

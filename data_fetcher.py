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
        self.logger = logging.getLogger(__name__)
        
        self.exchange_id = config.get('EXCHANGE_ID', 'binance')
        self.symbol = config.get('SYMBOL', 'XAU/USD:XAU')
        self.timeframes = config.get('TIMEFRAMES', ['1m', '5m', '15m', '30m', '1h', '4h'])
        self.candles_count = config.get('CANDLES_COUNT', 600)
        self.rate_limit_delay = config.get('RATE_LIMIT_DELAY', 0.1)
        self.xauusd_source = config.get('XAUUSD_SOURCE', os.getenv('XAUUSD_SOURCE', 'BIQUOTE'))
        self.biquote_base_url = config.get('BIQUOTE_BASE_URL', os.getenv('BIQUOTE_BASE_URL', 'https://biquote.io/api'))
        self.biquote_symbol = config.get('BIQUOTE_SYMBOL', os.getenv('BIQUOTE_SYMBOL', 'XAUUSD'))
        
        # تهيئة الـ Exchange دائماً كخيار احتياطي تجنباً للأخطاء
        self.exchange = self._initialize_exchange()
        
        if self.xauusd_source.upper() == 'BIQUOTE':
            self.fetcher_type = 'BIQUOTE'
            try:
                from biquote_fetcher import BIQuoteFetcher
                self.biquote_fetcher = BIQuoteFetcher(config)
            except Exception as e:
                self.logger.error(f"Failed to initialize BIQuote fetcher: {e}")
                self.fetcher_type = 'CCXT'
        else:
            self.fetcher_type = 'CCXT'

    def _initialize_exchange(self) -> Optional[ccxt.Exchange]:
        try:
            exchange_class = getattr(ccxt, self.exchange_id, None)
            if not exchange_class:
                exchange_class = ccxt.binance
            exchange = exchange_class({'enableRateLimit': True, 'rateLimit': 1000})
            self.logger.info(f"Initialized fallback exchange: {self.exchange_id}")
            return exchange
        except Exception as e:
            self.logger.error(f"Failed to initialize exchange fallback: {e}")
            return None

    def _get_exchange_symbol(self) -> str:
        if not self.exchange:
            return 'XAU/USD'
            
        try:
            if not getattr(self.exchange, 'markets', None):
                self.exchange.load_markets()
            symbol_formats = [self.symbol, self.symbol.replace('/', ''), 'XAU/USD', 'XAUUSD', 'PAXG/USDT']
            for symbol in symbol_formats:
                if symbol in self.exchange.symbols:
                    return symbol
        except Exception as e:
            self.logger.warning(f"Error loading markets: {e}")
            
        return 'XAU/USD'

    def fetch_ohlcv(self, timeframe: str, limit: int = 600) -> Optional[pd.DataFrame]:
        try:
            if self.fetcher_type == 'BIQUOTE' and hasattr(self, 'biquote_fetcher'):
                df = self.biquote_fetcher.fetch_ohlcv(timeframe, limit)
                if df is not None and len(df) >= 10:
                    return df
                else:
                    self.logger.warning(f"BIQuote failed for {timeframe}, falling back to CCXT")
            
            # Fallback to CCXT safely
            if not self.exchange:
                self.logger.error("No exchange available for fallback")
                return None
                
            symbol = self._get_exchange_symbol()
            tf_map = {'1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m', '1h': '1h', '4h': '4h', '1d': '1d'}
            exchange_tf = tf_map.get(timeframe, timeframe)
            ohlcv = self.exchange.fetch_ohlcv(symbol=symbol, timeframe=exchange_tf, limit=limit)
            
            if not ohlcv:
                return None
                
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
            if df is not None and len(df) >= 10:
                data[timeframe] = df
            time.sleep(self.rate_limit_delay)
        self.logger.info(f"Fetched data for {len(data)}/{len(self.timeframes)} timeframes")
        return data

    def get_current_price(self) -> Optional[float]:
        try:
            if self.fetcher_type == 'BIQUOTE' and hasattr(self, 'biquote_fetcher'):
                price = self.biquote_fetcher.fetch_current_price()
                if price:
                    return price
            
            if self.exchange:
                symbol = self._get_exchange_symbol()
                ticker = self.exchange.fetch_ticker(symbol)
                return ticker.get('last', ticker.get('close', None))
        except Exception as e:
            self.logger.error(f"Failed to get current price: {e}")
        return None

    def check_exchange_connection(self) -> bool:
        try:
            if self.fetcher_type == 'BIQUOTE' and hasattr(self, 'biquote_fetcher'):
                return self.biquote_fetcher.check_api_connection()
            elif self.exchange:
                return True
        except Exception as e:
            self.logger.error(f"Exchange connection check failed: {e}")
        return False

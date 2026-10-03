"""
BIQuote API Data Fetcher for XAUUSD Trading Bot
Fetches OHLCV and Current Price directly from BIQuote API
"""

import requests
import pandas as pd
from typing import Dict, List, Optional, Any
import logging
import time

class BIQuoteFetcher:
    """Fetches market data from BIQuote API"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.base_url = config.get('BIQUOTE_BASE_URL', 'https://biquote.io/api')
        self.symbol = config.get('BIQUOTE_SYMBOL', 'XAUUSD')
        self.timeframes = config.get('TIMEFRAMES', ['1m', '5m', '15m', '30m', '1h', '4h'])
        self.candles_count = config.get('CANDLES_COUNT', 600)
        self.rate_limit_delay = config.get('RATE_LIMIT_DELAY', 0.1)
        self.logger = logging.getLogger(__name__)
        self.headers = {'User-Agent': 'Mozilla/5.0'}

    def _get_timeframe_in_seconds(self, timeframe: str) -> int:
        tf_map = {
            '1m': 60,
            '5m': 300,
            '15m': 900,
            '30m': 1800,
            '1h': 3600,
            '4h': 14400,
            '1d': 86400,
        }
        return tf_map.get(timeframe, 60)

    def fetch_ohlcv(self, timeframe: str, limit: int = 600) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data from BIQuote API"""
        try:
            seconds = self._get_timeframe_in_seconds(timeframe)
            end_time = int(time.time())
            start_time = end_time - (limit * seconds)
            
            url = f"{self.base_url}/v1/history"
            params = {
                'symbol': self.symbol,
                'resolution': timeframe,
                'from': start_time,
                'to': end_time,
                'limit': limit
            }
            
            response = requests.get(url, params=params, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            if not data or 'data' not in data or not data['data']:
                return None
            
            candles = data['data']
            df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            if len(df) == 0:
                return None
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            df.set_index('timestamp', inplace=True)
            
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df
            
        except Exception as e:
            self.logger.error(f"Failed to fetch OHLCV for {timeframe} from BIQuote: {e}")
            return None

    def fetch_current_price(self) -> Optional[float]:
        """Fetch current price directly using https://biquote.io/api/{symbol}"""
        try:
            url = f"{self.base_url}/{self.symbol}"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                # تجربة حقول السعر المتاحة في الاستجابة (bid/ask/price/close)
                if 'bid' in data and 'ask' in data:
                    return float((data['bid'] + data['ask']) / 2)
                elif 'price' in data:
                    return float(data['price'])
                elif 'close' in data:
                    return float(data['close'])
            
            return None
                
        except Exception as e:
            self.logger.error(f"Failed to fetch price from BIQuote: {e}")
            return None

    def fetch_all_timeframes(self) -> Dict[str, pd.DataFrame]:
        data = {}
        for timeframe in self.timeframes:
            df = self.fetch_ohlcv(timeframe, self.candles_count)
            if df is not None and len(df) >= 10:
                data[timeframe] = df
            time.sleep(self.rate_limit_delay)
        return data

    def check_api_connection(self) -> bool:
        return self.fetch_current_price() is not None

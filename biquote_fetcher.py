"""
BIQuote API Data Fetcher for XAUUSD Trading Bot
Fetches OHLCV data from BIQuote API
"""

import requests
import pandas as pd
from typing import Dict, List, Optional, Any
import logging
import time
from datetime import datetime, timedelta

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
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        
    def _get_timeframe_in_seconds(self, timeframe: str) -> int:
        """Convert timeframe string to seconds"""
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
            
            # Calculate start and end timestamps
            end_time = int(time.time())
            start_time = end_time - (limit * seconds)
            
            # Build API URL
            url = f"{self.base_url}/v1/history"
            
            params = {
                'symbol': self.symbol,
                'resolution': timeframe,
                'from': start_time,
                'to': end_time,
                'limit': limit
            }
            
            self.logger.info(f"Fetching {limit} {timeframe} candles for {self.symbol} from BIQuote")
            
            # Make API request with headers
            response = requests.get(url, params=params, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if not data or 'data' not in data or not data['data']:
                self.logger.warning(f"No data received for {timeframe}")
                return None
            
            # Convert to DataFrame
            candles = data['data']
            df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            if len(df) == 0:
                return None
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            df.set_index('timestamp', inplace=True)
            
            # Convert to float
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            self.logger.info(f"Fetched {len(df)} {timeframe} candles from BIQuote")
            return df
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"BIQuote API request failed for {timeframe}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Failed to fetch OHLCV for {timeframe} from BIQuote: {e}")
            return None
    
    def fetch_current_price(self) -> Optional[float]:
        """Fetch current price from BIQuote history endpoint"""
        try:
            url = f"{self.base_url}/v1/history"
            end_time = int(time.time())
            start_time = end_time - 300
            
            params = {
                'symbol': self.symbol,
                'resolution': '1m',
                'from': start_time,
                'to': end_time,
                'limit': 1
            }
            
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data and 'data' in data and len(data['data']) > 0:
                    latest_candle = data['data'][-1]
                    return float(latest_candle[4])
            
            self.logger.warning(f"Could not fetch price from history endpoint, status: {response.status_code}")
            return None
                
        except Exception as e:
            self.logger.error(f"Failed to fetch current price from BIQuote: {e}")
            return None
    
    def fetch_all_timeframes(self) -> Dict[str, pd.DataFrame]:
        """Fetch data for all configured timeframes from BIQuote"""
        data = {}
        
        for timeframe in self.timeframes:
            df = self.fetch_ohlcv(timeframe, self.candles_count)
            if df is not None and len(df) >= 10:
                data[timeframe] = df
            time.sleep(self.rate_limit_delay)
        
        self.logger.info(f"Fetched data for {len(data)}/{len(self.timeframes)} timeframes from BIQuote")
        return data
    
    def check_api_connection(self) -> bool:
        """Check if BIQuote API is accessible"""
        try:
            url = f"{self.base_url}/v1/history"
            end_time = int(time.time())
            params = {
                'symbol': self.symbol,
                'resolution': '1m',
                'from': end_time - 300,
                'to': end_time,
                'limit': 1
            }
            response = requests.get(url, params=params, headers=self.headers, timeout=5)
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"BIQuote API connection check failed: {e}")
            return False

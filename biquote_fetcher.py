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
        self.base_url = config.get('BIQUOTE_BASE_URL', 'https://biquote.io/api').rstrip('/')
        self.symbol = config.get('BIQUOTE_SYMBOL', 'XAUUSD')
        self.timeframes = config.get('TIMEFRAMES', ['1m', '5m', '15m', '30m', '1h', '4h'])
        self.candles_count = config.get('CANDLES_COUNT', 500)
        self.rate_limit_delay = config.get('RATE_LIMIT_DELAY', 0.1)
        self.logger = logging.getLogger(__name__)
        self.headers = {'User-Agent': 'Mozilla/5.0'}

    def fetch_ohlcv(self, timeframe: str, limit: int = 500) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data from BIQuote API using official /ohlc endpoint"""
        try:
            url = f"{self.base_url}/{self.symbol}/ohlc"
            params = {
                'interval': timeframe,
                'limit': limit
            }
            
            response = requests.get(url, params=params, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # التأكد من وجود مصفوفة الشموع bars
            bars = data.get('bars') if isinstance(data, dict) else None
            if not bars:
                self.logger.warning(f"No bars returned from BIQuote for {timeframe}")
                return None
            
            df = pd.DataFrame(bars)
            
            if df.empty:
                return None
            
            # تحويل حقل الوقت openTime
            if 'openTime' in df.columns:
                df['openTime'] = pd.to_datetime(df['openTime'])
                df.set_index('openTime', inplace=True)
            elif 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
            
            # إضافة حجم التداول Volume إن لم يكن موجوداً لمنع أي خطأ في التحليل الفني
            if 'volume' not in df.columns:
                df['volume'] = 0
                
            cols = ['open', 'high', 'low', 'close', 'volume']
            for col in cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            self.logger.info(f"Successfully fetched {len(df)} candles for {self.symbol} ({timeframe}) from BIQuote")
            return df[cols]
            
        except Exception as e:
            self.logger.error(f"Failed to fetch OHLCV for {timeframe} from BIQuote: {e}")
            return None

    def fetch_current_price(self) -> Optional[float]:
        """Fetch current price using the latest candle from BIQuote"""
        try:
            df = self.fetch_ohlcv('1m', limit=1)
            if df is not None and not df.empty:
                return float(df['close'].iloc[-1])
            
            # محاولة جلب السعر المباشر إذا وُجد endpoint السعر
            url = f"{self.base_url}/{self.symbol}"
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict):
                    if 'bid' in data and 'ask' in data:
                        return float((data['bid'] + data['ask']) / 2)
                    for key in ['price', 'close', 'last']:
                        if key in data:
                            return float(data[key])
            return None
                
        except Exception as e:
            self.logger.error(f"Failed to fetch current price from BIQuote: {e}")
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

"""Data Fetcher Module for XAUUSD Trading Bot - Pure BIQuote Version"""
import pandas as pd
from typing import Dict, List, Optional, Any
import logging
import time
import os

class DataFetcher:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        self.timeframes = config.get('TIMEFRAMES', ['1m', '5m', '15m', '30m', '1h', '4h'])
        self.candles_count = config.get('CANDLES_COUNT', 500)
        self.rate_limit_delay = config.get('RATE_LIMIT_DELAY', 0.1)
        
        # الاعتماد الحصري على BIQuote
        try:
            from biquote_fetcher import BIQuoteFetcher
            self.biquote_fetcher = BIQuoteFetcher(config)
            self.logger.info("BIQuote fetcher initialized successfully.")
        except Exception as e:
            self.logger.error(f"Failed to initialize BIQuote fetcher: {e}")
            self.biquote_fetcher = None

    def fetch_ohlcv(self, timeframe: str, limit: int = 500) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data directly from BIQuote only"""
        if not self.biquote_fetcher:
            self.logger.error("BIQuote fetcher is not available")
            return None

        try:
            df = self.biquote_fetcher.fetch_ohlcv(timeframe, limit)
            if df is not None and not df.empty:
                return df
            
            self.logger.warning(f"No data returned from BIQuote for timeframe {timeframe}")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching OHLCV from BIQuote for {timeframe}: {e}")
            return None

    def fetch_all_timeframes(self) -> Dict[str, pd.DataFrame]:
        data = {}
        for timeframe in self.timeframes:
            df = self.fetch_ohlcv(timeframe, self.candles_count)
            if df is not None and len(df) >= 10:
                data[timeframe] = df
            time.sleep(self.rate_limit_delay)
        self.logger.info(f"Fetched data for {len(data)}/{len(self.timeframes)} timeframes from BIQuote")
        return data

    def get_current_price(self) -> Optional[float]:
        if self.biquote_fetcher:
            return self.biquote_fetcher.fetch_current_price()
        return None

    def check_exchange_connection(self) -> bool:
        if self.biquote_fetcher:
            return self.biquote_fetcher.check_api_connection()
        return False

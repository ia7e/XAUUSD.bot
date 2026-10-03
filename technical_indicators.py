"""Technical Indicators Module for XAUUSD Trading Bot"""
import numpy as np
import pandas as pd
from typing import Tuple, List, Dict, Any

class TechnicalIndicators:
    @staticmethod
    def rsi(data: pd.Series, period: int = 14) -> pd.Series:
        delta = data.diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        ema_fast = data.ewm(span=fast, adjust=False).mean()
        ema_slow = data.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        return macd_line, signal_line, macd_line - signal_line

    @staticmethod
    def bollinger_bands(data: pd.Series, period: int = 20, std: float = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
        sma = data.rolling(window=period).mean()
        std_dev = data.rolling(window=period).std()
        return sma + (std_dev * std), sma, sma - (std_dev * std)

    @staticmethod
    def sma(data: pd.Series, period: int) -> pd.Series:
        return data.rolling(window=period).mean()

    @staticmethod
    def ema(data: pd.Series, period: int) -> pd.Series:
        return data.ewm(span=period, adjust=False).mean()

    @staticmethod
    def atr(data: pd.DataFrame, period: int = 14) -> pd.Series:
        high, low, close = data['high'], data['low'], data['close']
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    @staticmethod
    def stochastic(data: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> Tuple[pd.Series, pd.Series]:
        low_min = data['low'].rolling(window=k_period).min()
        high_max = data['high'].rolling(window=k_period).max()
        k = 100 * (data['close'] - low_min) / (high_max - low_min)
        return k, k.rolling(window=d_period).mean()

    @staticmethod
    def volume_weighted_average(data: pd.DataFrame, period: int = 20) -> pd.Series:
        return (data['close'] * data['volume']).rolling(window=period).sum() / data['volume'].rolling(window=period).sum()

    @staticmethod
    def calculate_all_indicators(df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
        result = df.copy()
        result['rsi'] = TechnicalIndicators.rsi(result['close'], config.get('RSI_PERIOD', 14))
        macd_line, signal_line, histogram = TechnicalIndicators.macd(result['close'], config.get('MACD_FAST', 12), config.get('MACD_SLOW', 26), config.get('MACD_SIGNAL', 9))
        result['macd_line'] = macd_line
        result['macd_signal'] = signal_line
        result['macd_histogram'] = histogram
        upper, middle, lower = TechnicalIndicators.bollinger_bands(result['close'], config.get('BOLLINGER_PERIOD', 20), config.get('BOLLINGER_STD', 2))
        result['bb_upper'] = upper
        result['bb_middle'] = middle
        result['bb_lower'] = lower
        for period in config.get('SMA_PERIODS', [50, 100, 200]):
            result[f'sma_{period}'] = TechnicalIndicators.sma(result['close'], period)
        for period in config.get('EMA_PERIODS', [20, 50]):
            result[f'ema_{period}'] = TechnicalIndicators.ema(result['close'], period)
        result['atr'] = TechnicalIndicators.atr(result, 14)
        k, d = TechnicalIndicators.stochastic(result)
        result['stoch_k'] = k
        result['stoch_d'] = d
        result['vwap'] = TechnicalIndicators.volume_weighted_average(result)
        return result

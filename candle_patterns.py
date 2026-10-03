"""
Candle Patterns Module for XAUUSD Trading Bot
Detects all major candlestick patterns for trading signals
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class CandlePattern(Enum):
    # Bullish Patterns
    HAMMER = "HAMMER"
    INVERTED_HAMMER = "INVERTED_HAMMER"
    BULLISH_ENGULFING = "BULLISH_ENGULFING"
    PIERCING_LINE = "PIERCING_LINE"
    MORNING_STAR = "MORNING_STAR"
    THREE_WHITE_SOLDERS = "THREE_WHITE_SOLDERS"
    BULLISH_HARAMI = "BULLISH_HARAMI"
    BULLISH_HARAMI_CROSS = "BULLISH_HARAMI_CROSS"
    RISING_THREE_METHODS = "RISING_THREE_METHODS"
    BULLISH_ABANDONED_BABY = "BULLISH_ABANDONED_BABY"
    
    # Bearish Patterns
    SHOOTING_STAR = "SHOOTING_STAR"
    HANGING_MAN = "HANGING_MAN"
    BEARISH_ENGULFING = "BEARISH_ENGULFING"
    DARK_CLOUD_COVER = "DARK_CLOUD_COVER"
    EVENING_STAR = "EVENING_STAR"
    THREE_BLACK_CROWS = "THREE_BLACK_CROWS"
    BEARISH_HARAMI = "BEARISH_HARAMI"
    BEARISH_HARAMI_CROSS = "BEARISH_HARAMI_CROSS"
    FALLING_THREE_METHODS = "FALLING_THREE_METHODS"
    BEARISH_ABANDONED_BABY = "BEARISH_ABANDONED_BABY"
    
    # Continuation Patterns
    DOJI = "DOJI"
    DRAGONFLY_DOJI = "DRAGONFLY_DOJI"
    GRAVESTONE_DOJI = "GRAVESTONE_DOJI"
    SPINNING_TOP = "SPINNING_TOP"
    FALLING_WINDOW = "FALLING_WINDOW"
    RISING_WINDOW = "RISING_WINDOW"
    
    # Neutral Patterns
    LONG_LEGGED_DOJI = "LONG_LEGGED_DOJI"
    NEUTRAL = "NEUTRAL"

@dataclass
class DetectedPattern:
    """Represents a detected candle pattern"""
    pattern: CandlePattern
    confidence: float  # 0-1
    candle_index: int
    candle_data: Dict[str, float]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'pattern': self.pattern.value,
            'confidence': round(self.confidence, 4),
            'candle_index': self.candle_index,
            'candle_data': {k: round(v, 4) for k, v in self.candle_data.items()}
        }

class CandlePatterns:
    """Detect various candlestick patterns"""
    
    @staticmethod
    def get_body_size(row: pd.Series) -> float:
        """Calculate candle body size"""
        return abs(row['close'] - row['open'])
    
    @staticmethod
    def get_upper_shadow(row: pd.Series) -> float:
        """Calculate upper shadow size"""
        return row['high'] - max(row['open'], row['close'])
    
    @staticmethod
    def get_lower_shadow(row: pd.Series) -> float:
        """Calculate lower shadow size"""
        return min(row['open'], row['close']) - row['low']
    
    @staticmethod
    def get_candle_range(row: pd.Series) -> float:
        """Calculate total candle range"""
        return row['high'] - row['low']
    
    @staticmethod
    def is_bullish(row: pd.Series) -> bool:
        """Check if candle is bullish"""
        return row['close'] > row['open']
    
    @staticmethod
    def is_bearish(row: pd.Series) -> bool:
        """Check if candle is bearish"""
        return row['close'] < row['open']
    
    @staticmethod
    def is_doji(row: pd.Series, threshold: float = 0.05) -> bool:
        """Check if candle is a Doji"""
        body_size = CandlePatterns.get_body_size(row)
        candle_range = CandlePatterns.get_candle_range(row)
        if candle_range == 0:
            return False
        return body_size / candle_range < threshold
    
    # Bullish Patterns
    
    @staticmethod
    def detect_hammer(row: pd.Series, prev_rows: pd.DataFrame = None) -> Optional[DetectedPattern]:
        """Detect Hammer pattern"""
        if not CandlePatterns.is_bullish(row):
            return None
        
        body_size = CandlePatterns.get_body_size(row)
        lower_shadow = CandlePatterns.get_lower_shadow(row)
        upper_shadow = CandlePatterns.get_upper_shadow(row)
        candle_range = CandlePatterns.get_candle_range(row)
        
        if candle_range == 0:
            return None
        
        # Hammer: long lower shadow, small body, little/no upper shadow
        if (lower_shadow >= 2 * body_size and 
            upper_shadow <= 0.1 * body_size and
            body_size > 0):
            confidence = min(lower_shadow / candle_range, 0.9)
            return DetectedPattern(
                pattern=CandlePattern.HAMMER,
                confidence=confidence,
                candle_index=0,
                candle_data={
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'body_size': body_size,
                    'lower_shadow': lower_shadow,
                    'upper_shadow': upper_shadow
                }
            )
        return None
    
    @staticmethod
    def detect_inverted_hammer(row: pd.Series) -> Optional[DetectedPattern]:
        """Detect Inverted Hammer pattern"""
        if not CandlePatterns.is_bullish(row):
            return None
        
        body_size = CandlePatterns.get_body_size(row)
        lower_shadow = CandlePatterns.get_lower_shadow(row)
        upper_shadow = CandlePatterns.get_upper_shadow(row)
        candle_range = CandlePatterns.get_candle_range(row)
        
        if candle_range == 0:
            return None
        
        # Inverted Hammer: long upper shadow, small body, little/no lower shadow
        if (upper_shadow >= 2 * body_size and 
            lower_shadow <= 0.1 * body_size and
            body_size > 0):
            confidence = min(upper_shadow / candle_range, 0.9)
            return DetectedPattern(
                pattern=CandlePattern.INVERTED_HAMMER,
                confidence=confidence,
                candle_index=0,
                candle_data={
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'body_size': body_size,
                    'lower_shadow': lower_shadow,
                    'upper_shadow': upper_shadow
                }
            )
        return None
    
    @staticmethod
    def detect_bullish_engulfing(df: pd.DataFrame, index: int) -> Optional[DetectedPattern]:
        """Detect Bullish Engulfing pattern (2 candles)"""
        if index < 1:
            return None
        
        current = df.iloc[index]
        previous = df.iloc[index - 1]
        
        if (not CandlePatterns.is_bullish(current) or 
            not CandlePatterns.is_bearish(previous)):
            return None
        
        current_body = CandlePatterns.get_body_size(current)
        previous_body = CandlePatterns.get_body_size(previous)
        
        # Current body engulfs previous body
        if current_body > previous_body:
            # Check if current candle opens below previous close and closes above previous open
            if (current['open'] < previous['close'] and 
                current['close'] > previous['open']):
                confidence = min(current_body / (previous_body + 0.0001), 0.95)
                return DetectedPattern(
                    pattern=CandlePattern.BULLISH_ENGULFING,
                    confidence=confidence,
                    candle_index=index,
                    candle_data={
                        'current_open': current['open'],
                        'current_high': current['high'],
                        'current_low': current['low'],
                        'current_close': current['close'],
                        'previous_open': previous['open'],
                        'previous_close': previous['close']
                    }
                )
        return None
    
    @staticmethod
    def detect_piercing_line(df: pd.DataFrame, index: int) -> Optional[DetectedPattern]:
        """Detect Piercing Line pattern (2 candles)"""
        if index < 1:
            return None
        
        current = df.iloc[index]
        previous = df.iloc[index - 1]
        
        if (not CandlePatterns.is_bullish(current) or 
            not CandlePatterns.is_bearish(previous)):
            return None
        
        # Current candle closes above midpoint of previous candle
        previous_body = abs(previous['close'] - previous['open'])
        previous_midpoint = previous['open'] + (previous_body / 2) if previous['open'] > previous['close'] else previous['close'] + (previous_body / 2)
        
        if (current['open'] < previous['low'] and 
            current['close'] > previous_midpoint and
            current['close'] < previous['open']):
            confidence = min((current['close'] - current['open']) / previous_body, 0.9)
            return DetectedPattern(
                pattern=CandlePattern.PIERCING_LINE,
                confidence=confidence,
                candle_index=index,
                candle_data={
                    'current_open': current['open'],
                    'current_close': current['close'],
                    'previous_open': previous['open'],
                    'previous_close': previous['close'],
                    'previous_midpoint': previous_midpoint
                }
            )
        return None
    
    @staticmethod
    def detect_morning_star(df: pd.DataFrame, index: int) -> Optional[DetectedPattern]:
        """Detect Morning Star pattern (3 candles)"""
        if index < 2:
            return None
        
        first = df.iloc[index - 2]
        second = df.iloc[index - 1]
        third = df.iloc[index]
        
        # First: long bearish, Second: small body (doji or spinning top), Third: bullish
        if (not CandlePatterns.is_bearish(first) or 
            not CandlePatterns.is_bullish(third)):
            return None
        
        first_body = CandlePatterns.get_body_size(first)
        second_body = CandlePatterns.get_body_size(second)
        third_body = CandlePatterns.get_body_size(third)
        
        # Second candle has small body, gaps down from first
        if (second_body < 0.5 * first_body and
            second['high'] < first['low'] and
            third['close'] > first_body / 2):
            confidence = min(third_body / first_body, 0.85)
            return DetectedPattern(
                pattern=CandlePattern.MORNING_STAR,
                confidence=confidence,
                candle_index=index,
                candle_data={
                    'first_open': first['open'],
                    'first_close': first['close'],
                    'second_open': second['open'],
                    'second_close': second['close'],
                    'third_open': third['open'],
                    'third_close': third['close']
                }
            )
        return None
    
    @staticmethod
    def detect_three_white_soldiers(df: pd.DataFrame, index: int) -> Optional[DetectedPattern]:
        """Detect Three White Soldiers pattern (3 candles)"""
        if index < 2:
            return None
        
        candles = df.iloc[index - 2:index + 1]
        
        # All three are bullish
        if not all(CandlePatterns.is_bullish(row) for _, row in candles.iterrows()):
            return None
        
        # Each candle opens within previous body and closes higher
        valid = True
        for i in range(1, len(candles)):
            current = candles.iloc[i]
            previous = candles.iloc[i - 1]
            if (current['open'] < previous['open'] or 
                current['close'] <= previous['close']):
                valid = False
                break
        
        if valid:
            avg_body = candles['close'].mean() - candles['open'].mean()
            confidence = min(avg_body / (candles['high'].max() - candles['low'].min()), 0.8)
            return DetectedPattern(
                pattern=CandlePattern.THREE_WHITE_SOLDERS,
                confidence=confidence,
                candle_index=index,
                candle_data={
                    'candle1_open': candles.iloc[0]['open'],
                    'candle1_close': candles.iloc[0]['close'],
                    'candle2_open': candles.iloc[1]['open'],
                    'candle2_close': candles.iloc[1]['close'],
                    'candle3_open': candles.iloc[2]['open'],
                    'candle3_close': candles.iloc[2]['close']
                }
            )
        return None
    
    # Bearish Patterns
    
    @staticmethod
    def detect_shooting_star(row: pd.Series) -> Optional[DetectedPattern]:
        """Detect Shooting Star pattern"""
        if not CandlePatterns.is_bearish(row):
            return None
        
        body_size = CandlePatterns.get_body_size(row)
        lower_shadow = CandlePatterns.get_lower_shadow(row)
        upper_shadow = CandlePatterns.get_upper_shadow(row)
        candle_range = CandlePatterns.get_candle_range(row)
        
        if candle_range == 0:
            return None
        
        # Shooting Star: long upper shadow, small body, little/no lower shadow
        if (upper_shadow >= 2 * body_size and 
            lower_shadow <= 0.1 * body_size and
            body_size > 0):
            confidence = min(upper_shadow / candle_range, 0.9)
            return DetectedPattern(
                pattern=CandlePattern.SHOOTING_STAR,
                confidence=confidence,
                candle_index=0,
                candle_data={
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'body_size': body_size,
                    'lower_shadow': lower_shadow,
                    'upper_shadow': upper_shadow
                }
            )
        return None
    
    @staticmethod
    def detect_hanging_man(row: pd.Series) -> Optional[DetectedPattern]:
        """Detect Hanging Man pattern"""
        if not CandlePatterns.is_bearish(row):
            return None
        
        body_size = CandlePatterns.get_body_size(row)
        lower_shadow = CandlePatterns.get_lower_shadow(row)
        upper_shadow = CandlePatterns.get_upper_shadow(row)
        candle_range = CandlePatterns.get_candle_range(row)
        
        if candle_range == 0:
            return None
        
        # Hanging Man: long lower shadow, small body, little/no upper shadow
        if (lower_shadow >= 2 * body_size and 
            upper_shadow <= 0.1 * body_size and
            body_size > 0):
            confidence = min(lower_shadow / candle_range, 0.9)
            return DetectedPattern(
                pattern=CandlePattern.HANGING_MAN,
                confidence=confidence,
                candle_index=0,
                candle_data={
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'body_size': body_size,
                    'lower_shadow': lower_shadow,
                    'upper_shadow': upper_shadow
                }
            )
        return None
    
    @staticmethod
    def detect_bearish_engulfing(df: pd.DataFrame, index: int) -> Optional[DetectedPattern]:
        """Detect Bearish Engulfing pattern (2 candles)"""
        if index < 1:
            return None
        
        current = df.iloc[index]
        previous = df.iloc[index - 1]
        
        if (not CandlePatterns.is_bearish(current) or 
            not CandlePatterns.is_bullish(previous)):
            return None
        
        current_body = CandlePatterns.get_body_size(current)
        previous_body = CandlePatterns.get_body_size(previous)
        
        # Current body engulfs previous body
        if current_body > previous_body:
            # Check if current candle opens above previous close and closes below previous open
            if (current['open'] > previous['close'] and 
                current['close'] < previous['open']):
                confidence = min(current_body / (previous_body + 0.0001), 0.95)
                return DetectedPattern(
                    pattern=CandlePattern.BEARISH_ENGULFING,
                    confidence=confidence,
                    candle_index=index,
                    candle_data={
                        'current_open': current['open'],
                        'current_high': current['high'],
                        'current_low': current['low'],
                        'current_close': current['close'],
                        'previous_open': previous['open'],
                        'previous_close': previous['close']
                    }
                )
        return None
    
    @staticmethod
    def detect_dark_cloud_cover(df: pd.DataFrame, index: int) -> Optional[DetectedPattern]:
        """Detect Dark Cloud Cover pattern (2 candles)"""
        if index < 1:
            return None
        
        current = df.iloc[index]
        previous = df.iloc[index - 1]
        
        if (not CandlePatterns.is_bearish(current) or 
            not CandlePatterns.is_bullish(previous)):
            return None
        
        # Current candle opens above previous high and closes below midpoint
        previous_body = abs(previous['close'] - previous['open'])
        previous_midpoint = previous['open'] + (previous_body / 2)
        
        if (current['open'] > previous['high'] and 
            current['close'] < previous_midpoint and
            current['close'] > previous['open']):
            confidence = min((previous['high'] - current['close']) / previous_body, 0.9)
            return DetectedPattern(
                pattern=CandlePattern.DARK_CLOUD_COVER,
                confidence=confidence,
                candle_index=index,
                candle_data={
                    'current_open': current['open'],
                    'current_close': current['close'],
                    'previous_open': previous['open'],
                    'previous_close': previous['close'],
                    'previous_midpoint': previous_midpoint
                }
            )
        return None
    
    @staticmethod
    def detect_evening_star(df: pd.DataFrame, index: int) -> Optional[DetectedPattern]:
        """Detect Evening Star pattern (3 candles)"""
        if index < 2:
            return None
        
        first = df.iloc[index - 2]
        second = df.iloc[index - 1]
        third = df.iloc[index]
        
        # First: long bullish, Second: small body (doji or spinning top), Third: bearish
        if (not CandlePatterns.is_bullish(first) or 
            not CandlePatterns.is_bearish(third)):
            return None
        
        first_body = CandlePatterns.get_body_size(first)
        second_body = CandlePatterns.get_body_size(second)
        third_body = CandlePatterns.get_body_size(third)
        
        # Second candle has small body, gaps up from first
        if (second_body < 0.5 * first_body and
            second['low'] > first['high'] and
            third['close'] < first['open'] + (first_body / 2)):
            confidence = min(third_body / first_body, 0.85)
            return DetectedPattern(
                pattern=CandlePattern.EVENING_STAR,
                confidence=confidence,
                candle_index=index,
                candle_data={
                    'first_open': first['open'],
                    'first_close': first['close'],
                    'second_open': second['open'],
                    'second_close': second['close'],
                    'third_open': third['open'],
                    'third_close': third['close']
                }
            )
        return None
    
    @staticmethod
    def detect_three_black_crows(df: pd.DataFrame, index: int) -> Optional[DetectedPattern]:
        """Detect Three Black Crows pattern (3 candles)"""
        if index < 2:
            return None
        
        candles = df.iloc[index - 2:index + 1]
        
        # All three are bearish
        if not all(CandlePatterns.is_bearish(row) for _, row in candles.iterrows()):
            return None
        
        # Each candle opens within previous body and closes lower
        valid = True
        for i in range(1, len(candles)):
            current = candles.iloc[i]
            previous = candles.iloc[i - 1]
            if (current['open'] > previous['open'] or 
                current['close'] >= previous['close']):
                valid = False
                break
        
        if valid:
            avg_body = candles['open'].mean() - candles['close'].mean()
            confidence = min(avg_body / (candles['high'].max() - candles['low'].min()), 0.8)
            return DetectedPattern(
                pattern=CandlePattern.THREE_BLACK_CROWS,
                confidence=confidence,
                candle_index=index,
                candle_data={
                    'candle1_open': candles.iloc[0]['open'],
                    'candle1_close': candles.iloc[0]['close'],
                    'candle2_open': candles.iloc[1]['open'],
                    'candle2_close': candles.iloc[1]['close'],
                    'candle3_open': candles.iloc[2]['open'],
                    'candle3_close': candles.iloc[2]['close']
                }
            )
        return None
    
    # Doji Patterns
    
    @staticmethod
    def detect_doji(row: pd.Series) -> Optional[DetectedPattern]:
        """Detect Doji pattern"""
        if not CandlePatterns.is_doji(row, 0.1):
            return None
        
        candle_range = CandlePatterns.get_candle_range(row)
        if candle_range == 0:
            return None
        
        confidence = 0.7
        return DetectedPattern(
            pattern=CandlePattern.DOJI,
            confidence=confidence,
            candle_index=0,
            candle_data={
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close']
            }
        )
    
    @staticmethod
    def detect_dragonfly_doji(row: pd.Series) -> Optional[DetectedPattern]:
        """Detect Dragonfly Doji pattern"""
        if not CandlePatterns.is_doji(row, 0.1):
            return None
        
        body_size = CandlePatterns.get_body_size(row)
        lower_shadow = CandlePatterns.get_lower_shadow(row)
        upper_shadow = CandlePatterns.get_upper_shadow(row)
        candle_range = CandlePatterns.get_candle_range(row)
        
        if candle_range == 0:
            return None
        
        # Dragonfly: long lower shadow, no upper shadow
        if (lower_shadow >= 2 * body_size and 
            upper_shadow <= 0.1 * body_size):
            confidence = min(lower_shadow / candle_range, 0.85)
            return DetectedPattern(
                pattern=CandlePattern.DRAGONFLY_DOJI,
                confidence=confidence,
                candle_index=0,
                candle_data={
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'lower_shadow': lower_shadow,
                    'upper_shadow': upper_shadow
                }
            )
        return None
    
    @staticmethod
    def detect_gravestone_doji(row: pd.Series) -> Optional[DetectedPattern]:
        """Detect Gravestone Doji pattern"""
        if not CandlePatterns.is_doji(row, 0.1):
            return None
        
        body_size = CandlePatterns.get_body_size(row)
        lower_shadow = CandlePatterns.get_lower_shadow(row)
        upper_shadow = CandlePatterns.get_upper_shadow(row)
        candle_range = CandlePatterns.get_candle_range(row)
        
        if candle_range == 0:
            return None
        
        # Gravestone: long upper shadow, no lower shadow
        if (upper_shadow >= 2 * body_size and 
            lower_shadow <= 0.1 * body_size):
            confidence = min(upper_shadow / candle_range, 0.85)
            return DetectedPattern(
                pattern=CandlePattern.GRAVESTONE_DOJI,
                confidence=confidence,
                candle_index=0,
                candle_data={
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'lower_shadow': lower_shadow,
                    'upper_shadow': upper_shadow
                }
            )
        return None
    
    @staticmethod
    def detect_spinning_top(row: pd.Series) -> Optional[DetectedPattern]:
        """Detect Spinning Top pattern"""
        body_size = CandlePatterns.get_body_size(row)
        candle_range = CandlePatterns.get_candle_range(row)
        
        if candle_range == 0:
            return None
        
        # Spinning top: small body with long shadows on both sides
        if (body_size < 0.3 * candle_range and
            CandlePatterns.get_lower_shadow(row) > body_size and
            CandlePatterns.get_upper_shadow(row) > body_size):
            confidence = min(1 - (body_size / candle_range), 0.75)
            return DetectedPattern(
                pattern=CandlePattern.SPINNING_TOP,
                confidence=confidence,
                candle_index=0,
                candle_data={
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'body_size': body_size,
                    'lower_shadow': CandlePatterns.get_lower_shadow(row),
                    'upper_shadow': CandlePatterns.get_upper_shadow(row)
                }
            )
        return None
    
    @staticmethod
    def detect_all_patterns(df: pd.DataFrame, lookback: int = 5) -> List[DetectedPattern]:
        """Detect all patterns in the DataFrame"""
        patterns = []
        
        # Check last N candles
        for i in range(max(0, len(df) - lookback), len(df)):
            row = df.iloc[i]
            
            # Single candle patterns
            single_patterns = [
                CandlePatterns.detect_hammer,
                CandlePatterns.detect_inverted_hammer,
                CandlePatterns.detect_shooting_star,
                CandlePatterns.detect_hanging_man,
                CandlePatterns.detect_doji,
                CandlePatterns.detect_dragonfly_doji,
                CandlePatterns.detect_gravestone_doji,
                CandlePatterns.detect_spinning_top,
            ]
            
            for detector in single_patterns:
                pattern = detector(row)
                if pattern:
                    pattern.candle_index = i
                    patterns.append(pattern)
            
            # Multi-candle patterns
            if i >= 1:
                multi_patterns_2 = [
                    lambda idx: CandlePatterns.detect_bullish_engulfing(df, idx),
                    lambda idx: CandlePatterns.detect_bearish_engulfing(df, idx),
                    lambda idx: CandlePatterns.detect_piercing_line(df, idx),
                    lambda idx: CandlePatterns.detect_dark_cloud_cover(df, idx),
                ]
                for detector in multi_patterns_2:
                    pattern = detector(i)
                    if pattern:
                        patterns.append(pattern)
            
            if i >= 2:
                multi_patterns_3 = [
                    lambda idx: CandlePatterns.detect_morning_star(df, idx),
                    lambda idx: CandlePatterns.detect_evening_star(df, idx),
                    lambda idx: CandlePatterns.detect_three_white_soldiers(df, idx),
                    lambda idx: CandlePatterns.detect_three_black_crows(df, idx),
                ]
                for detector in multi_patterns_3:
                    pattern = detector(i)
                    if pattern:
                        patterns.append(pattern)
        
        return patterns
    
    @staticmethod
    def get_pattern_signal_strength(pattern: CandlePattern) -> Tuple[str, float]:
        """Get signal strength for a pattern"""
        bullish_patterns = {
            CandlePattern.HAMMER: ('BULLISH', 0.8),
            CandlePattern.INVERTED_HAMMER: ('BULLISH', 0.75),
            CandlePattern.BULLISH_ENGULFING: ('BULLISH', 0.85),
            CandlePattern.PIERCING_LINE: ('BULLISH', 0.8),
            CandlePattern.MORNING_STAR: ('BULLISH', 0.9),
            CandlePattern.THREE_WHITE_SOLDERS: ('BULLISH', 0.85),
            CandlePattern.BULLISH_HARAMI: ('BULLISH', 0.7),
            CandlePattern.BULLISH_HARAMI_CROSS: ('BULLISH', 0.75),
            CandlePattern.RISING_THREE_METHODS: ('BULLISH', 0.75),
            CandlePattern.BULLISH_ABANDONED_BABY: ('BULLISH', 0.85),
            CandlePattern.DRAGONFLY_DOJI: ('BULLISH', 0.75),
            CandlePattern.RISING_WINDOW: ('BULLISH', 0.7),
        }
        
        bearish_patterns = {
            CandlePattern.SHOOTING_STAR: ('BEARISH', 0.8),
            CandlePattern.HANGING_MAN: ('BEARISH', 0.75),
            CandlePattern.BEARISH_ENGULFING: ('BEARISH', 0.85),
            CandlePattern.DARK_CLOUD_COVER: ('BEARISH', 0.8),
            CandlePattern.EVENING_STAR: ('BEARISH', 0.9),
            CandlePattern.THREE_BLACK_CROWS: ('BEARISH', 0.85),
            CandlePattern.BEARISH_HARAMI: ('BEARISH', 0.7),
            CandlePattern.BEARISH_HARAMI_CROSS: ('BEARISH', 0.75),
            CandlePattern.FALLING_THREE_METHODS: ('BEARISH', 0.75),
            CandlePattern.BEARISH_ABANDONED_BABY: ('BEARISH', 0.85),
            CandlePattern.GRAVESTONE_DOJI: ('BEARISH', 0.75),
            CandlePattern.FALLING_WINDOW: ('BEARISH', 0.7),
        }
        
        if pattern in bullish_patterns:
            return bullish_patterns[pattern]
        elif pattern in bearish_patterns:
            return bearish_patterns[pattern]
        else:
            return ('NEUTRAL', 0.0)

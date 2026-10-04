"""Signal Generator Module for XAUUSD Trading Bot"""
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from candle_patterns import CandlePatterns, CandlePattern, DetectedPattern

class SignalType(Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    WEAK_BUY = "WEAK_BUY"
    NEUTRAL = "NEUTRAL"
    WEAK_SELL = "WEAK_SELL"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"

@dataclass
class TradingSignal:
    signal_type: SignalType
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    confidence: float
    timeframe: str
    reasons: List[str]
    indicators: Dict[str, float]
    candle_patterns: List[str] = None

    def __post_init__(self):
        if self.candle_patterns is None:
            self.candle_patterns = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            'signal_type': self.signal_type.value,
            'entry_price': round(self.entry_price, 4),
            'stop_loss': round(self.stop_loss, 4),
            'take_profit_1': round(self.take_profit_1, 4),
            'take_profit_2': round(self.take_profit_2, 4),
            'take_profit_3': round(self.take_profit_3, 4),
            'confidence': round(self.confidence, 4),
            'timeframe': self.timeframe,
            'reasons': self.reasons,
            'candle_patterns': self.candle_patterns,
            'indicators': {k: round(v, 4) if isinstance(v, float) else v for k, v in self.indicators.items()}
        }

class SignalGenerator:
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def _check_rsi_signal(self, df: pd.DataFrame) -> Tuple[SignalType, List[str], float]:
        rsi = df['rsi'].iloc[-1]
        rsi_prev = df['rsi'].iloc[-2] if len(df) > 1 else rsi
        reasons = []
        confidence = 0.0
        signal = SignalType.NEUTRAL
        if pd.isna(rsi):
            return signal, reasons, confidence
        if rsi < self.config['RSI_OVERSOLD']:
            if rsi_prev >= self.config['RSI_OVERSOLD']:
                signal = SignalType.STRONG_BUY
                reasons.append(f"RSI crossed above oversold ({self.config['RSI_OVERSOLD']})")
                confidence += 0.4
            else:
                signal = SignalType.BUY
                reasons.append(f"RSI in oversold zone ({rsi:.2f})")
                confidence += 0.25
        elif rsi > self.config['RSI_OVERBOUGHT']:
            if rsi_prev <= self.config['RSI_OVERBOUGHT']:
                signal = SignalType.STRONG_SELL
                reasons.append(f"RSI crossed below overbought ({self.config['RSI_OVERBOUGHT']})")
                confidence += 0.4
            else:
                signal = SignalType.SELL
                reasons.append(f"RSI in overbought zone ({rsi:.2f})")
                confidence += 0.25
        return signal, reasons, confidence

    def _check_macd_signal(self, df: pd.DataFrame) -> Tuple[SignalType, List[str], float]:
        macd = df['macd_line'].iloc[-1]
        signal = df['macd_signal'].iloc[-1]
        histogram = df['macd_histogram'].iloc[-1]
        macd_prev = df['macd_line'].iloc[-2] if len(df) > 1 else macd
        signal_prev = df['macd_signal'].iloc[-2] if len(df) > 1 else signal
        reasons = []
        confidence = 0.0
        signal_type = SignalType.NEUTRAL
        if pd.isna(macd) or pd.isna(signal):
            return signal_type, reasons, confidence
        if macd > signal and macd_prev <= signal_prev:
            signal_type = SignalType.BUY
            reasons.append("MACD bullish crossover")
            confidence += 0.35
        elif macd < signal and macd_prev >= signal_prev:
            signal_type = SignalType.SELL
            reasons.append("MACD bearish crossover")
            confidence += 0.35
        hist_prev = df['macd_histogram'].iloc[-2] if len(df) > 1 else histogram
        if not pd.isna(hist_prev):
            if histogram > 0 and hist_prev < 0:
                signal_type = SignalType.BUY if signal_type == SignalType.NEUTRAL else signal_type
                reasons.append("MACD histogram turned positive")
                confidence += 0.15
            elif histogram < 0 and hist_prev > 0:
                signal_type = SignalType.SELL if signal_type == SignalType.NEUTRAL else signal_type
                reasons.append("MACD histogram turned negative")
                confidence += 0.15
        return signal_type, reasons, confidence

    def _check_bollinger_signal(self, df: pd.DataFrame) -> Tuple[SignalType, List[str], float]:
        close = df['close'].iloc[-1]
        upper = df['bb_upper'].iloc[-1]
        lower = df['bb_lower'].iloc[-1]
        middle = df['bb_middle'].iloc[-1]
        reasons = []
        confidence = 0.0
        signal = SignalType.NEUTRAL
        if pd.isna(close) or pd.isna(upper) or pd.isna(lower):
            return signal, reasons, confidence
        band_width = (upper - lower) / middle * 100
        position = (close - lower) / (upper - lower)
        if close <= lower:
            signal = SignalType.STRONG_BUY
            reasons.append("Price touched lower Bollinger Band")
            confidence += 0.3
        elif close >= upper:
            signal = SignalType.STRONG_SELL
            reasons.append("Price touched upper Bollinger Band")
            confidence += 0.3
        elif close < lower + (middle - lower) * 0.2:
            signal = SignalType.BUY
            reasons.append("Price near lower Bollinger Band")
            confidence += 0.2
        elif close > upper - (upper - middle) * 0.2:
            signal = SignalType.SELL
            reasons.append("Price near upper Bollinger Band")
            confidence += 0.2
        if band_width < 5:
            reasons.append("Bollinger squeeze detected")
            confidence += 0.1
        return signal, reasons, confidence

    def _check_sma_signal(self, df: pd.DataFrame) -> Tuple[SignalType, List[str], float]:
        close = df['close'].iloc[-1]
        reasons = []
        confidence = 0.0
        signal = SignalType.NEUTRAL
        sma_periods = self.config.get('SMA_PERIODS', [50, 100, 200])
        for period in sma_periods:
            sma_col = f'sma_{period}'
            if sma_col not in df.columns:
                continue
            sma = df[sma_col].iloc[-1]
            sma_prev = df[sma_col].iloc[-2] if len(df) > 1 else sma
            close_prev = df['close'].iloc[-2] if len(df) > 1 else close
            if pd.isna(sma):
                continue
            if close > sma and close_prev <= sma_prev:
                signal = SignalType.BUY if signal == SignalType.NEUTRAL else signal
                reasons.append(f"Price crossed above SMA {period}")
                confidence += 0.15
            elif close < sma and close_prev >= sma_prev:
                signal = SignalType.SELL if signal == SignalType.NEUTRAL else signal
                reasons.append(f"Price crossed below SMA {period}")
                confidence += 0.15
        if len(sma_periods) >= 2:
            short_sma = f'sma_{min(sma_periods)}'
            long_sma = f'sma_{max(sma_periods)}'
            if short_sma in df.columns and long_sma in df.columns:
                short = df[short_sma].iloc[-1]
                long = df[long_sma].iloc[-1]
                short_prev = df[short_sma].iloc[-2] if len(df) > 1 else short
                long_prev = df[long_sma].iloc[-2] if len(df) > 1 else long
                if not pd.isna(short) and not pd.isna(long):
                    if short > long and short_prev <= long_prev:
                        signal = SignalType.STRONG_BUY
                        reasons.append(f"Golden cross: SMA {min(sma_periods)} crossed above SMA {max(sma_periods)}")
                        confidence += 0.4
                    elif short < long and short_prev >= long_prev:
                        signal = SignalType.STRONG_SELL
                        reasons.append(f"Death cross: SMA {min(sma_periods)} crossed below SMA {max(sma_periods)}")
                        confidence += 0.4
        return signal, reasons, confidence

    def _check_ema_signal(self, df: pd.DataFrame) -> Tuple[SignalType, List[str], float]:
        reasons = []
        confidence = 0.0
        signal = SignalType.NEUTRAL
        ema_periods = self.config.get('EMA_PERIODS', [20, 50])
        if len(ema_periods) >= 2:
            short_ema = f'ema_{min(ema_periods)}'
            long_ema = f'ema_{max(ema_periods)}'
            if short_ema in df.columns and long_ema in df.columns:
                short = df[short_ema].iloc[-1]
                long = df[long_ema].iloc[-1]
                short_prev = df[short_ema].iloc[-2] if len(df) > 1 else short
                long_prev = df[long_ema].iloc[-2] if len(df) > 1 else long
                if not pd.isna(short) and not pd.isna(long):
                    if short > long and short_prev <= long_prev:
                        signal = SignalType.BUY
                        reasons.append(f"EMA {min(ema_periods)} crossed above EMA {max(ema_periods)}")
                        confidence += 0.3
                    elif short < long and short_prev >= long_prev:
                        signal = SignalType.SELL
                        reasons.append(f"EMA {min(ema_periods)} crossed below EMA {max(ema_periods)}")
                        confidence += 0.3
        return signal, reasons, confidence

    def _check_stochastic_signal(self, df: pd.DataFrame) -> Tuple[SignalType, List[str], float]:
        k = df['stoch_k'].iloc[-1]
        d = df['stoch_d'].iloc[-1]
        k_prev = df['stoch_k'].iloc[-2] if len(df) > 1 else k
        d_prev = df['stoch_d'].iloc[-2] if len(df) > 1 else d
        reasons = []
        confidence = 0.0
        signal = SignalType.NEUTRAL
        if pd.isna(k) or pd.isna(d):
            return signal, reasons, confidence
        if k < 20 and d < 20:
            if k > d and k_prev <= d_prev:
                signal = SignalType.STRONG_BUY
                reasons.append("Stochastic bullish crossover in oversold zone")
                confidence += 0.35
            else:
                signal = SignalType.BUY
                reasons.append("Stochastic in oversold zone")
                confidence += 0.2
        elif k > 80 and d > 80:
            if k < d and k_prev >= d_prev:
                signal = SignalType.STRONG_SELL
                reasons.append("Stochastic bearish crossover in overbought zone")
                confidence += 0.35
            else:
                signal = SignalType.SELL
                reasons.append("Stochastic in overbought zone")
                confidence += 0.2
        return signal, reasons, confidence

    def _calculate_confidence_and_signal(self, signals: List[Tuple[SignalType, List[str], float]], weights: List[float]) -> Tuple[SignalType, float]:
        buy_score = 0.0
        sell_score = 0.0
        total_weight = sum(weights)
        for (signal, reasons, conf), weight in zip(signals, weights):
            if signal == SignalType.STRONG_BUY:
                buy_score += conf * weight * 1.5
            elif signal == SignalType.BUY:
                buy_score += conf * weight * 1.0
            elif signal == SignalType.WEAK_BUY:
                buy_score += conf * weight * 0.5
            elif signal == SignalType.STRONG_SELL:
                sell_score += conf * weight * 1.5
            elif signal == SignalType.SELL:
                sell_score += conf * weight * 1.0
            elif signal == SignalType.WEAK_SELL:
                sell_score += conf * weight * 0.5
        net_score = buy_score - sell_score
        total_possible = total_weight * 1.5
        if net_score > total_possible * self.config.get('STRONG_BUY_THRESHOLD', 0.7):
            return SignalType.STRONG_BUY, net_score / total_possible
        elif net_score > total_possible * 0.4:
            return SignalType.BUY, net_score / total_possible
        elif net_score > total_possible * 0.1:
            return SignalType.WEAK_BUY, net_score / total_possible
        elif net_score < -total_possible * self.config.get('STRONG_SELL_THRESHOLD', 0.7):
            return SignalType.STRONG_SELL, abs(net_score) / total_possible
        elif net_score < -total_possible * 0.4:
            return SignalType.SELL, abs(net_score) / total_possible
        elif net_score < -total_possible * 0.1:
            return SignalType.WEAK_SELL, abs(net_score) / total_possible
        else:
            return SignalType.NEUTRAL, 0.0

    def _check_candle_patterns(self, df: pd.DataFrame) -> Tuple[SignalType, List[str], float]:
        """Check for candlestick patterns"""
        patterns = CandlePatterns.detect_all_patterns(decision_df, lookback=5)
        if not patterns:
            return SignalType.NEUTRAL, [], 0.0
        
        bullish_score = 0.0
        bearish_score = 0.0
        reasons = []
        
        for pattern in patterns:
            signal_str, strength = CandlePatterns.get_pattern_signal_strength(pattern.pattern)
            if signal_str == 'BULLISH':
                bullish_score += strength * pattern.confidence
                reasons.append(f"Candle pattern: {pattern.pattern.value}")
            elif signal_str == 'BEARISH':
                bearish_score += strength * pattern.confidence
                reasons.append(f"Candle pattern: {pattern.pattern.value}")
        
        net_score = bullish_score - bearish_score
        
        if net_score > 0.6:
            return SignalType.STRONG_BUY, reasons, min(bullish_score, 0.9)
        elif net_score > 0.3:
            return SignalType.BUY, reasons, bullish_score * 0.7
        elif net_score < -0.6:
            return SignalType.STRONG_SELL, reasons, min(bearish_score, 0.9)
        elif net_score < -0.3:
            return SignalType.SELL, reasons, bearish_score * 0.7
        else:
            return SignalType.NEUTRAL, reasons, 0.0

    def generate_signal(self, df: pd.DataFrame, timeframe: str) -> Optional[TradingSignal]:
        decision_candles = int(self.config.get('DECISION_CANDLES', 50))
        if len(df) < decision_candles:
            return None
        decision_df = df.tail(decision_candles).copy()
        signals = []
        all_reasons = []
        signals.append(self._check_rsi_signal(decision_df))
        all_reasons.extend(signals[-1][1])
        signals.append(self._check_macd_signal(decision_df))
        all_reasons.extend(signals[-1][1])
        signals.append(self._check_bollinger_signal(decision_df))
        all_reasons.extend(signals[-1][1])
        signals.append(self._check_sma_signal(decision_df))
        all_reasons.extend(signals[-1][1])
        signals.append(self._check_ema_signal(decision_df))
        all_reasons.extend(signals[-1][1])
        signals.append(self._check_stochastic_signal(decision_df))
        all_reasons.extend(signals[-1][1])
        signals.append(self._check_candle_patterns(decision_df))
        all_reasons.extend(signals[-1][1])
        weights = [0.15, 0.2, 0.15, 0.15, 0.15, 0.1, 0.15]
        final_signal, confidence = self._calculate_confidence_and_signal(signals, weights)
        if final_signal == SignalType.NEUTRAL:
            return None
        close = decision_df['close'].iloc[-1]
        atr = decision_df['atr'].iloc[-1]
        if pd.isna(atr) or atr == 0:
            atr = close * 0.01
        stop_loss_multiplier = self.config.get('STOP_LOSS_ATR_MULTIPLIER', 1.25)
        tp1_multiplier = self.config.get('TP1_ATR_MULTIPLIER', 1.0)
        tp2_multiplier = self.config.get('TP2_ATR_MULTIPLIER', 1.5)
        tp3_multiplier = self.config.get('TP3_ATR_MULTIPLIER', 2.0)
        if final_signal in [SignalType.STRONG_BUY, SignalType.BUY, SignalType.WEAK_BUY]:
            entry = close
            stop_loss = close - (atr * stop_loss_multiplier)
            tp1 = close + (atr * tp1_multiplier)
            tp2 = close + (atr * tp2_multiplier)
            tp3 = close + (atr * tp3_multiplier)
        else:
            entry = close
            stop_loss = close + (atr * stop_loss_multiplier)
            tp1 = close - (atr * tp1_multiplier)
            tp2 = close - (atr * tp2_multiplier)
            tp3 = close - (atr * tp3_multiplier)
        # Detect candle patterns
        patterns = CandlePatterns.detect_all_patterns(df, lookback=5)
        candle_patterns = [p.pattern.value for p in patterns if p.pattern.value not in all_reasons]
        
        indicators = {
            'rsi': decision_df['rsi'].iloc[-1],
            'macd_line': decision_df['macd_line'].iloc[-1],
            'macd_signal': decision_df['macd_signal'].iloc[-1],
            'bb_upper': decision_df['bb_upper'].iloc[-1],
            'bb_lower': decision_df['bb_lower'].iloc[-1],
            'atr': atr,
            'stoch_k': decision_df['stoch_k'].iloc[-1],
            'stoch_d': decision_df['stoch_d'].iloc[-1],
        }
        for period in self.config.get('SMA_PERIODS', []):
            indicators[f'sma_{period}'] = decision_df[f'sma_{period}'].iloc[-1]
        for period in self.config.get('EMA_PERIODS', []):
            indicators[f'ema_{period}'] = decision_df[f'ema_{period}'].iloc[-1]
        
        # Add candle patterns to reasons
        for pattern_name in candle_patterns:
            all_reasons.append(f"Candle pattern: {pattern_name}")
        
        return TradingSignal(
            signal_type=final_signal,
            entry_price=entry,
            stop_loss=stop_loss,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            confidence=confidence,
            timeframe=timeframe,
            reasons=all_reasons,
            indicators=indicators,
            candle_patterns=candle_patterns
        )

    def generate_signals_all_timeframes(self, data_dict: Dict[str, pd.DataFrame]) -> List[TradingSignal]:
        signals = []
        for timeframe, df in data_dict.items():
            signal = self.generate_signal(df, timeframe)
            if signal:
                signals.append(signal)
        return signals

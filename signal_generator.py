"""Candle-price-action signal engine for XAUUSD.

The entry decision intentionally uses OHLC candle structure only:
- confirmed candlestick patterns
- recent swing structure
- breakout/rejection of recent candle ranges
- candle body/wick strength

No RSI, MACD, Bollinger, SMA, EMA or other indicator is used to decide BUY/SELL.
"""
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from candle_patterns import CandlePatterns


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
            "signal_type": self.signal_type.value,
            "entry_price": round(float(self.entry_price), 4),
            "stop_loss": round(float(self.stop_loss), 4),
            "take_profit_1": round(float(self.take_profit_1), 4),
            "take_profit_2": round(float(self.take_profit_2), 4),
            "take_profit_3": round(float(self.take_profit_3), 4),
            "confidence": round(float(self.confidence), 4),
            "timeframe": self.timeframe,
            "reasons": self.reasons,
            "candle_patterns": self.candle_patterns,
            # Kept for dashboard compatibility. Deliberately empty:
            # indicators are NOT used by the candle decision engine.
            "indicators": self.indicators,
        }


class SignalGenerator:
    """High-selectivity price-action engine using closed candles only."""

    # Use pattern VALUE strings here instead of hard Enum-member references.
    # This keeps the signal engine robust if candle_patterns.py has an Enum
    # naming mismatch between deployments.
    BULLISH_PATTERNS = {
        "HAMMER",
        "INVERTED_HAMMER",
        "BULLISH_ENGULFING",
        "PIERCING_LINE",
        "MORNING_STAR",
        "THREE_WHITE_SOLDIERS",
        "DRAGONFLY_DOJI",
    }

    BEARISH_PATTERNS = {
        "SHOOTING_STAR",
        "HANGING_MAN",
        "BEARISH_ENGULFING",
        "DARK_CLOUD_COVER",
        "EVENING_STAR",
        "THREE_BLACK_CROWS",
        "GRAVESTONE_DOJI",
    }

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @staticmethod
    def _candle_stats(row: pd.Series) -> Tuple[float, float, float, float]:
        body = abs(float(row["close"]) - float(row["open"]))
        high = float(row["high"])
        low = float(row["low"])
        upper = high - max(float(row["open"]), float(row["close"]))
        lower = min(float(row["open"]), float(row["close"])) - low
        return body, high - low, upper, lower

    @staticmethod
    def _direction(row: pd.Series) -> int:
        if float(row["close"]) > float(row["open"]):
            return 1
        if float(row["close"]) < float(row["open"]):
            return -1
        return 0

    def _market_structure(self, df: pd.DataFrame) -> int:
        """Return +1 bullish, -1 bearish, 0 mixed using candle highs/lows/closes."""
        if len(df) < 4:
            return 0
        a, b, c, d = [df.iloc[i] for i in range(-4, 0)]
        bullish = (
            float(d["close"]) > float(c["close"])
            and float(d["high"]) >= float(c["high"])
            and float(d["low"]) >= float(c["low"])
        )
        bearish = (
            float(d["close"]) < float(c["close"])
            and float(d["high"]) <= float(c["high"])
            and float(d["low"]) <= float(c["low"])
        )
        if bullish:
            return 1
        if bearish:
            return -1

        # Secondary structure check over the last four closes.
        closes = [float(x) for x in df["close"].iloc[-4:]]
        if closes[-1] > closes[0] and closes[-2] >= closes[1]:
            return 1
        if closes[-1] < closes[0] and closes[-2] <= closes[1]:
            return -1
        return 0

    def _latest_patterns(self, df: pd.DataFrame):
        patterns = CandlePatterns.detect_all_patterns(df, lookback=min(5, len(df)))
        last_index = len(df) - 1
        return [
            p for p in patterns
            if p.candle_index == last_index
            and p.pattern.value in (self.BULLISH_PATTERNS | self.BEARISH_PATTERNS)
        ]

    def _price_action_score(
        self, df: pd.DataFrame, direction: int, patterns: List[Any]
    ) -> Tuple[float, List[str]]:
        """Score only candle evidence. 0..1."""
        last = df.iloc[-1]
        body, rng, upper, lower = self._candle_stats(last)
        if rng <= 0:
            return 0.0, []

        score = 0.0
        reasons: List[str] = []

        # Strong named candle pattern is the primary evidence.
        matching = []
        pattern_strengths = {
            "HAMMER": ("BULLISH", 0.80),
            "INVERTED_HAMMER": ("BULLISH", 0.75),
            "BULLISH_ENGULFING": ("BULLISH", 0.85),
            "PIERCING_LINE": ("BULLISH", 0.80),
            "MORNING_STAR": ("BULLISH", 0.90),
            "THREE_WHITE_SOLDIERS": ("BULLISH", 0.85),
            "DRAGONFLY_DOJI": ("BULLISH", 0.75),
            "SHOOTING_STAR": ("BEARISH", 0.80),
            "HANGING_MAN": ("BEARISH", 0.75),
            "BEARISH_ENGULFING": ("BEARISH", 0.85),
            "DARK_CLOUD_COVER": ("BEARISH", 0.80),
            "EVENING_STAR": ("BEARISH", 0.90),
            "THREE_BLACK_CROWS": ("BEARISH", 0.85),
            "GRAVESTONE_DOJI": ("BEARISH", 0.75),
        }
        for pattern in patterns:
            signal, strength = pattern_strengths.get(pattern.pattern.value, ("NEUTRAL", 0.0))
            if (direction == 1 and signal == "BULLISH") or (direction == -1 and signal == "BEARISH"):
                matching.append((pattern, strength))

        if matching:
            best = max(matching, key=lambda x: x[1] * x[0].confidence)
            score += min(0.60, 0.45 * best[1] + 0.25 * best[0].confidence)
            reasons.append(f"Candle pattern: {best[0].pattern.value}")

        # Rejection: wick shows failed move through a recent extreme.
        prior = df.iloc[-6:-1] if len(df) >= 6 else df.iloc[:-1]
        if not prior.empty:
            prior_high = float(prior["high"].max())
            prior_low = float(prior["low"].min())

            bullish_rejection = (
                direction == 1
                and float(last["low"]) <= prior_low
                and lower >= max(body * 1.5, rng * 0.30)
                and float(last["close"]) > float(last["open"])
            )
            bearish_rejection = (
                direction == -1
                and float(last["high"]) >= prior_high
                and upper >= max(body * 1.5, rng * 0.30)
                and float(last["close"]) < float(last["open"])
            )
            if bullish_rejection or bearish_rejection:
                score += 0.20
                reasons.append("رفض سعري واضح عند قاع/قمة حديثة")

            # Breakout: candle closes beyond the recent range, not just wicks through it.
            bullish_breakout = (
                direction == 1
                and float(last["close"]) > prior_high
                and body >= rng * 0.55
            )
            bearish_breakout = (
                direction == -1
                and float(last["close"]) < prior_low
                and body >= rng * 0.55
            )
            if bullish_breakout or bearish_breakout:
                score += 0.20
                reasons.append("اختراق سعري مؤكد بإغلاق الشمعة")

        # Body quality: strong close near the candle extreme.
        body_ratio = body / rng
        close_position = (float(last["close"]) - float(last["low"])) / rng
        if direction == 1 and body_ratio >= 0.55 and close_position >= 0.70:
            score += 0.12
            reasons.append("شمعة صاعدة قوية وإغلاق قريب من القمة")
        elif direction == -1 and body_ratio >= 0.55 and close_position <= 0.30:
            score += 0.12
            reasons.append("شمعة هابطة قوية وإغلاق قريب من القاع")

        # The previous candle should not strongly oppose the setup.
        prev_direction = self._direction(df.iloc[-2])
        if prev_direction == direction:
            score += 0.08
            reasons.append("استمرار ضغط سعري من الشمعة السابقة")

        return min(score, 1.0), reasons

    def _levels_from_structure(self, df: pd.DataFrame, direction: int):
        """Build SL/TP from candle structure, not ATR/indicators."""
        last = df.iloc[-1]
        body, rng, _, _ = self._candle_stats(last)
        if rng <= 0:
            return None

        lookback = df.iloc[-12:]
        entry = float(last["close"])

        # Structure-based stop: place the SL beyond the real recent swing,
        # with a wider candle-range buffer for XAUUSD noise. No ATR/indicator is used.
        recent_ranges = (lookback["high"].astype(float) - lookback["low"].astype(float)).tolist()
        recent_ranges = [x for x in recent_ranges if x > 0]
        typical_range = sorted(recent_ranges)[len(recent_ranges) // 2] if recent_ranges else rng

        # The buffer is tied to the latest candle ranges, not a fixed dollar amount.
        # The wider multiplier prevents unrealistically tight stops on gold.
        buffer = max(rng * 0.75, typical_range * 1.25)

        if direction == 1:
            swing = float(lookback["low"].min())
            sl = swing - buffer
            risk = entry - sl
            if risk <= 0:
                return None
            tp1 = entry + risk
            tp2 = entry + risk * 1.5
            tp3 = entry + risk * 2.0
        else:
            swing = float(lookback["high"].max())
            sl = swing + buffer
            risk = sl - entry
            if risk <= 0:
                return None
            tp1 = entry - risk
            tp2 = entry - risk * 1.5
            tp3 = entry - risk * 2.0

        # Reject pathological levels caused by a bad/outlier candle.
        if risk > entry * 0.01:
            return None

        return entry, sl, tp1, tp2, tp3

    def generate_signal(self, df: pd.DataFrame, timeframe: str) -> Optional[TradingSignal]:
        decision_candles = int(self.config.get("DECISION_CANDLES", 10))
        if df is None or len(df) < decision_candles:
            return None

        decision_df = df.tail(decision_candles).copy()
        required = {"open", "high", "low", "close"}
        if not required.issubset(decision_df.columns):
            return None

        # Only the latest CLOSED candle can trigger a new signal.
        last = decision_df.iloc[-1]
        if not all(pd.notna(last[col]) for col in required):
            return None

        patterns = self._latest_patterns(decision_df)
        pattern_dirs = set()
        for p in patterns:
            pattern_name = p.pattern.value
            if pattern_name in self.BULLISH_PATTERNS:
                pattern_dirs.add(1)
            elif pattern_name in self.BEARISH_PATTERNS:
                pattern_dirs.add(-1)

        # Conflicting reversal candles = NO TRADE.
        if len(pattern_dirs) > 1:
            return None

        structure = self._market_structure(decision_df)

        candidates = []
        for direction in (1, -1):
            # A candle setup must either have a matching named pattern,
            # or a strong breakout/rejection price-action confirmation.
            score, reasons = self._price_action_score(decision_df, direction, patterns)
            if direction in pattern_dirs:
                score += 0.10
                reasons.append("نموذج شموعي مؤكد على آخر شمعة مغلقة")

            if structure == direction:
                score += 0.10
                reasons.append("هيكل سعري متوافق")
            elif structure == -direction:
                score -= 0.15

            candidates.append((score, direction, reasons))

        score, direction, reasons = max(candidates, key=lambda x: x[0])

        # High selectivity: no indicator voting and no weak BUY/SELL.
        min_score = float(self.config.get("CANDLE_MIN_SCORE", 0.72))
        if score < min_score:
            return None

        # Require either a named candle reversal/continuation pattern OR
        # a strong price-action breakout/rejection on the latest candle.
        has_named_pattern = direction in pattern_dirs
        _, rng, upper, lower = self._candle_stats(last)
        body = abs(float(last["close"]) - float(last["open"]))
        prior = decision_df.iloc[:-1]
        if prior.empty:
            return None
        prior_high = float(prior.tail(5)["high"].max())
        prior_low = float(prior.tail(5)["low"].min())
        strong_breakout = (
            body >= rng * 0.55
            and ((direction == 1 and float(last["close"]) > prior_high)
                 or (direction == -1 and float(last["close"]) < prior_low))
        )
        strong_rejection = (
            (direction == 1 and float(last["low"]) <= prior_low and lower >= max(body * 1.5, rng * 0.30))
            or
            (direction == -1 and float(last["high"]) >= prior_high and upper >= max(body * 1.5, rng * 0.30))
        )
        if not (has_named_pattern or strong_breakout or strong_rejection):
            return None

        levels = self._levels_from_structure(decision_df, direction)
        if levels is None:
            return None
        entry, sl, tp1, tp2, tp3 = levels

        confidence = min(0.98, max(0.0, score))
        signal_type = (
            SignalType.STRONG_BUY if direction == 1 and confidence >= 0.86
            else SignalType.BUY if direction == 1
            else SignalType.STRONG_SELL if confidence >= 0.86
            else SignalType.SELL
        )

        candle_patterns = [p.pattern.value for p in patterns if (
            (direction == 1 and p.pattern.value in self.BULLISH_PATTERNS)
            or (direction == -1 and p.pattern.value in self.BEARISH_PATTERNS)
        )]

        # This engine intentionally exposes no indicator values.
        return TradingSignal(
            signal_type=signal_type,
            entry_price=entry,
            stop_loss=sl,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            confidence=confidence,
            timeframe=timeframe,
            reasons=list(dict.fromkeys(reasons)),
            indicators={},
            candle_patterns=candle_patterns,
        )

    def generate_signals_all_timeframes(self, data_dict: Dict[str, pd.DataFrame]) -> List[TradingSignal]:
        signals = []
        for timeframe, df in data_dict.items():
            signal = self.generate_signal(df, timeframe)
            if signal:
                signals.append(signal)
        return signals

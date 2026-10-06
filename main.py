"""Main XAUUSD signal bot: closed-candle decisions + 1-second active-signal monitoring."""
import asyncio
import logging
import os
import sys
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import *
from data_fetcher import DataFetcher
from technical_indicators import TechnicalIndicators
from signal_generator import SignalGenerator, TradingSignal, SignalType
from telegram_bot import TelegramBot

logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

TF_SECONDS = {'1m': 60, '5m': 300, '15m': 900, '30m': 1800, '1h': 3600, '4h': 14400}


class XAUUSBot:
    def __init__(self):
        self.config = {
            'TELEGRAM_TOKEN': TELEGRAM_TOKEN, 'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
            'EXCHANGE_ID': EXCHANGE_ID, 'SYMBOL': SYMBOL, 'TIMEFRAMES': TIMEFRAMES,
            'CANDLES_COUNT': CANDLES_COUNT, 'DECISION_CANDLES': DECISION_CANDLES,
            'RSI_PERIOD': RSI_PERIOD, 'RSI_OVERBOUGHT': RSI_OVERBOUGHT, 'RSI_OVERSOLD': RSI_OVERSOLD,
            'MACD_FAST': MACD_FAST, 'MACD_SLOW': MACD_SLOW, 'MACD_SIGNAL': MACD_SIGNAL,
            'BOLLINGER_PERIOD': BOLLINGER_PERIOD, 'BOLLINGER_STD': BOLLINGER_STD,
            'SMA_PERIODS': SMA_PERIODS, 'EMA_PERIODS': EMA_PERIODS,
            'STRONG_BUY_THRESHOLD': STRONG_BUY_THRESHOLD, 'STRONG_SELL_THRESHOLD': STRONG_SELL_THRESHOLD,
            'BUY_THRESHOLD': BUY_THRESHOLD, 'SELL_THRESHOLD': SELL_THRESHOLD,
            'RISK_PER_TRADE': RISK_PER_TRADE,
            'STOP_LOSS_ATR_MULTIPLIER': STOP_LOSS_ATR_MULTIPLIER,
            'TAKE_PROFIT_ATR_MULTIPLIER': TAKE_PROFIT_ATR_MULTIPLIER,
            'TP1_ATR_MULTIPLIER': TP1_ATR_MULTIPLIER,
            'TP2_ATR_MULTIPLIER': TP2_ATR_MULTIPLIER,
            'TP3_ATR_MULTIPLIER': TP3_ATR_MULTIPLIER,
            'RATE_LIMIT_DELAY': RATE_LIMIT_DELAY,
        }
        self.data_fetcher = DataFetcher(self.config)
        self.technical_indicators = TechnicalIndicators()
        self.signal_generator = SignalGenerator(self.config)
        self.telegram_bot = None
        self.active_signals: Dict[str, Dict[str, Any]] = {}
        self.last_processed_candle: Dict[str, Any] = {}
        self.signal_history: List[Dict[str, Any]] = []
        self.running = False
        self.market_open_state: Optional[bool] = None

    async def initialize(self):
        logger.info(f"Initializing {BOT_NAME} v{BOT_VERSION}")
        if self.config['TELEGRAM_TOKEN'] and self.config['TELEGRAM_CHAT_ID']:
            self.telegram_bot = TelegramBot(self.config['TELEGRAM_TOKEN'], self.config['TELEGRAM_CHAT_ID'])
            try:
                await self.telegram_bot.initialize()
                sent = await self.telegram_bot.send_message('🟢 <b>تم تشغيل النظام</b>\n\n🤖 نظام إشارات XAUUSD يعمل الآن.\n📡 مصدر البيانات: BIQuote\n⏱️ المراقبة: كل ثانية\n📊 اتخاذ القرار: آخر 10 شموع مغلقة')
                if not sent:
                    logger.error('Telegram startup message could not be sent')
            except Exception as e:
                logger.error(f"Telegram initialization failed: {e}")
                self.telegram_bot = None
        else:
            logger.error('Telegram is DISABLED: TELEGRAM_TOKEN or TELEGRAM_CHAT_ID is missing.')
        try:
            if self.data_fetcher.check_exchange_connection():
                logger.info("BIQuote connection established")
        except Exception as e:
            logger.error(f"Connection check failed: {e}")

    def _closed_candles(self, df, timeframe: str):
        if df is None or len(df) < DECISION_CANDLES:
            return None

        df = df.copy()
        try:
            df.index = pd.to_datetime(df.index, utc=True)
            df = df.sort_index()
        except Exception:
            return None

        if 'isOpen' in df.columns and bool(df['isOpen'].iloc[-1]):
            df = df.iloc[:-1].copy()

        if len(df) < DECISION_CANDLES:
            return None

        seconds = TF_SECONDS.get(timeframe)
        if not seconds:
            return None

        now = datetime.now(timezone.utc)
        last_open = df.index[-1].to_pydatetime()
        if last_open.tzinfo is None:
            last_open = last_open.replace(tzinfo=timezone.utc)

        candle_close = last_open + timedelta(seconds=seconds)
        age = (now - candle_close).total_seconds()

        # Reject genuinely old candles returned by BIQuote.
        if age > max(15, seconds * 1.25):
            logger.warning(
                f"{timeframe}: stale BIQuote candle rejected; "
                f"last_close={candle_close.isoformat()} age={age:.1f}s"
            )
            return None

        if age < -10:
            logger.warning(
                f"{timeframe}: future BIQuote candle rejected; "
                f"last_open={last_open.isoformat()}"
            )
            return None

        return df

    async def analyze_timeframe(self, timeframe: str) -> Optional[TradingSignal]:
        df = self.data_fetcher.fetch_ohlcv(timeframe, self.config['CANDLES_COUNT'])
        df = self._closed_candles(df, timeframe)
        if df is None or len(df) < DECISION_CANDLES:
            return None

        candle_id = df.index[-1]
        if self.last_processed_candle.get(timeframe) == candle_id:
            return None

        # Candle engine uses raw OHLC only. Indicators are intentionally not calculated.
        signal = self.signal_generator.generate_signal(df, timeframe)
        self.last_processed_candle[timeframe] = candle_id

        # The candle decides direction/setup; live price is the actionable entry.
        if signal:
            live_price = self.data_fetcher.get_current_price()
            if live_price is not None and float(live_price) > 0:
                signal.entry_price = float(live_price)
                # Fixed XAUUSD targets: 5 dollars, then another 5, then 4.
                # TP1 = 5, TP2 = 10, TP3 = 14 from the live entry.
                if self._is_buy(signal.signal_type.value):
                    signal.take_profit_1 = signal.entry_price + 5.0
                    signal.take_profit_2 = signal.entry_price + 10.0
                    signal.take_profit_3 = signal.entry_price + 14.0
                else:
                    signal.take_profit_1 = signal.entry_price - 5.0
                    signal.take_profit_2 = signal.entry_price - 10.0
                    signal.take_profit_3 = signal.entry_price - 14.0

        if signal:
            logger.info(f"{timeframe}: {signal.signal_type.value} confidence={signal.confidence:.1%}")
        return signal

    async def send_signal_alert(self, signal: TradingSignal) -> bool:
        if not self.telegram_bot:
            logger.error("Telegram is not initialized; signal cannot be sent")
            return False
        return await self.telegram_bot.send_signal_alert(signal.to_dict())

    async def send_signal_update(self, signal_data: Dict[str, Any], event: str, price: float):
        if self.telegram_bot:
            await self.telegram_bot.send_signal_update(signal_data, event, price)

    @staticmethod
    def _is_buy(signal_type: str) -> bool:
        return signal_type in ['STRONG_BUY', 'BUY', 'WEAK_BUY']

    async def _open_best_signal(self):
        """Find the strongest NEW candle setup and allow only one global active signal."""
        if self.active_signals:
            return

        candidates = []
        for timeframe in self.config['TIMEFRAMES']:
            try:
                signal = await self.analyze_timeframe(timeframe)
                if signal and signal.signal_type in [
                    SignalType.STRONG_BUY, SignalType.BUY,
                    SignalType.STRONG_SELL, SignalType.SELL
                ]:
                    candidates.append(signal)
            except Exception as e:
                logger.error(f"Candle analysis failed for {timeframe}: {e}", exc_info=True)

        if not candidates:
            return

        # If more than one timeframe confirms a setup, use the highest-confidence one.
        signal = max(candidates, key=lambda s: s.confidence)
        data = signal.to_dict()
        data['tp1_hit'] = False
        data['tp2_hit'] = False
        data['protected'] = False
        data['opened_at'] = datetime.now(timezone.utc).isoformat()
        self.active_signals = {signal.timeframe: data}
        self.signal_history.append(data.copy())

        sent = await self.send_signal_alert(signal)
        if sent is False:
            logger.error(
                f"Telegram signal delivery failed for {signal.timeframe} "
                f"{signal.signal_type.value}"
            )

    async def _check_market_status(self):
        status = self.data_fetcher.fetch_market_status()
        if status is None:
            return

        if self.market_open_state is None:
            self.market_open_state = status
            return

        if status == self.market_open_state:
            return

        self.market_open_state = status
        if not status:
            logger.info("BIQuote reports XAUUSD market CLOSED")
            if self.telegram_bot:
                await self.telegram_bot.send_market_closed()
        else:
            logger.info("BIQuote reports XAUUSD market OPEN")
            if self.telegram_bot:
                await self.telegram_bot.send_message(
                    "🟢 <b>تم فتح السوق</b>\n📡 XAUUSD عاد للعمل."
                )

    async def _monitor_active_signals(self):
        if not self.active_signals:
            return
        price = self.data_fetcher.get_current_price()
        if price is None:
            return

        finished = []
        for timeframe, signal in list(self.active_signals.items()):
            buy = self._is_buy(signal['signal_type'])
            entry = float(signal['entry_price'])
            sl = float(signal['stop_loss'])
            tp1 = float(signal['take_profit_1'])
            tp2 = float(signal['take_profit_2'])
            tp3 = float(signal['take_profit_3'])

            # SL is only checked until TP2 protection has been reached.
            if not signal['protected']:
                sl_hit = price <= sl if buy else price >= sl
                if sl_hit:
                    await self.send_signal_update(signal, 'SL', price)
                    finished.append(timeframe)
                    continue

            if not signal['tp1_hit']:
                tp1_hit = price >= tp1 if buy else price <= tp1
                if tp1_hit:
                    signal['tp1_hit'] = True
                    await self.send_signal_update(signal, 'TP1', price)

            if not signal['tp2_hit']:
                tp2_hit = price >= tp2 if buy else price <= tp2
                if tp2_hit:
                    signal['tp2_hit'] = True
                    signal['protected'] = True
                    await self.send_signal_update(signal, 'TP2', price)
                    continue

            if signal['tp2_hit']:
                # Signal remains active until TP3; protection means the virtual SL is entry.
                protected_sl_hit = price <= entry if buy else price >= entry
                if protected_sl_hit:
                    await self.send_signal_update(signal, 'SL', price)
                    finished.append(timeframe)
                    continue

            tp3_hit = price >= tp3 if buy else price <= tp3
            if tp3_hit:
                await self.send_signal_update(signal, 'TP3', price)
                finished.append(timeframe)

        for timeframe in finished:
            self.active_signals.pop(timeframe, None)

    async def run(self):
        self.running = True
        # Scan all timeframes once at startup and open at most ONE signal globally.
        await self._open_best_signal()
        while self.running:
            try:
                # Every second: market state + active-signal monitoring.
                await self._check_market_status()
                await self._monitor_active_signals()

                # New-candle analysis is scheduled by timeframe, not every second.
                # If a signal is active, absolutely no second signal can be opened.
                if not self.active_signals:
                    now = datetime.now(timezone.utc)
                    epoch = int(now.timestamp())
                    if any(
                        TF_SECONDS.get(tf) and epoch % TF_SECONDS[tf] == 0
                        for tf in self.config['TIMEFRAMES']
                    ):
                        await self._open_best_signal()

                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Main loop error: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def shutdown(self):
        self.running = False
        if self.telegram_bot:
            await self.telegram_bot.shutdown()

    def get_status(self) -> Dict[str, Any]:
        return {
            'bot_name': BOT_NAME,
            'version': BOT_VERSION,
            'status': 'running' if self.running else 'stopped',
            'current_price': self.data_fetcher.get_current_price(),
            'timeframes': self.config['TIMEFRAMES'],
            'active_signals': len(self.active_signals),
            'signal_history_count': len(self.signal_history),
            'telegram_enabled': self.telegram_bot is not None,
        }


async def start_bot():
    bot = XAUUSBot()
    await bot.initialize()
    await bot.run()


def main():
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

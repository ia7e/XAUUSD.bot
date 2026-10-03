"""Main XAUUSD Trading Bot - Professional trading signal generator"""
import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import *
from data_fetcher import DataFetcher
from technical_indicators import TechnicalIndicators
from signal_generator import SignalGenerator, TradingSignal
from telegram_bot import TelegramBot

logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
logger = logging.getLogger(__name__)

class XAUUSBot:
    def __init__(self):
        self.config = {
            'TELEGRAM_TOKEN': TELEGRAM_TOKEN, 'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
            'EXCHANGE_ID': EXCHANGE_ID, 'SYMBOL': SYMBOL, 'TIMEFRAMES': TIMEFRAMES,
            'CANDLES_COUNT': CANDLES_COUNT, 'RSI_PERIOD': RSI_PERIOD,
            'RSI_OVERBOUGHT': RSI_OVERBOUGHT, 'RSI_OVERSOLD': RSI_OVERSOLD,
            'MACD_FAST': MACD_FAST, 'MACD_SLOW': MACD_SLOW, 'MACD_SIGNAL': MACD_SIGNAL,
            'BOLLINGER_PERIOD': BOLLINGER_PERIOD, 'BOLLINGER_STD': BOLLINGER_STD,
            'SMA_PERIODS': SMA_PERIODS, 'EMA_PERIODS': EMA_PERIODS,
            'STRONG_BUY_THRESHOLD': STRONG_BUY_THRESHOLD, 'STRONG_SELL_THRESHOLD': STRONG_SELL_THRESHOLD,
            'RISK_PER_TRADE': RISK_PER_TRADE, 'STOP_LOSS_ATR_MULTIPLIER': STOP_LOSS_ATR_MULTIPLIER,
            'TAKE_PROFIT_ATR_MULTIPLIER': TAKE_PROFIT_ATR_MULTIPLIER, 'RATE_LIMIT_DELAY': RATE_LIMIT_DELAY,
        }
        self.data_fetcher = DataFetcher(self.config)
        self.technical_indicators = TechnicalIndicators()
        self.signal_generator = SignalGenerator(self.config)
        self.telegram_bot = None
        self.last_signals = {}
        self.signal_history = []
        self.running = False

    async def initialize(self):
        logger.info(f"Initializing {BOT_NAME} v{BOT_VERSION}")
        if self.config['TELEGRAM_TOKEN'] and self.config['TELEGRAM_CHAT_ID']:
            self.telegram_bot = TelegramBot(token=self.config['TELEGRAM_TOKEN'], chat_id=self.config['TELEGRAM_CHAT_ID'])
            try:
                await self.telegram_bot.initialize()
                logger.info("Telegram bot initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Telegram bot: {e}")
                self.telegram_bot = None
        else:
            logger.warning("Telegram credentials not provided, running without Telegram notifications")
        if self.data_fetcher.check_exchange_connection():
            logger.info("Exchange connection established")
        else:
            logger.error("Failed to connect to exchange")
            raise ConnectionError("Cannot connect to exchange")
        logger.info("Bot initialization complete")

    async def analyze_timeframe(self, timeframe: str) -> Optional[TradingSignal]:
        logger.info(f"Analyzing {timeframe} timeframe...")
        df = self.data_fetcher.fetch_ohlcv(timeframe, self.config['CANDLES_COUNT'])
        if df is None or len(df) < 50:
            logger.warning(f"Insufficient data for {timeframe}")
            return None
        df = self.technical_indicators.calculate_all_indicators(df, self.config)
        signal = self.signal_generator.generate_signal(df, timeframe)
        if signal:
            logger.info(f"Signal generated for {timeframe}: {signal.signal_type.value}")
        else:
            logger.debug(f"No signal for {timeframe}")
        return signal

    async def analyze_all_timeframes(self) -> List[TradingSignal]:
        signals = []
        for timeframe in self.config['TIMEFRAMES']:
            signal = await self.analyze_timeframe(timeframe)
            if signal:
                signals.append(signal)
            await asyncio.sleep(self.config['RATE_LIMIT_DELAY'])
        return signals

    async def send_signal_alert(self, signal: TradingSignal) -> bool:
        if not self.telegram_bot:
            logger.warning("Telegram bot not available, cannot send alert")
            return False
        return await self.telegram_bot.send_signal_alert(signal.to_dict())

    async def send_multiple_signals_alert(self, signals: List[TradingSignal]) -> bool:
        if not self.telegram_bot:
            logger.warning("Telegram bot not available, cannot send alert")
            return False
        return await self.telegram_bot.send_multiple_signals(signals)

    async def run_analysis_cycle(self):
        logger.info("Starting analysis cycle...")
        try:
            data_dict = self.data_fetcher.fetch_all_timeframes()
            for timeframe, df in data_dict.items():
                data_dict[timeframe] = self.technical_indicators.calculate_all_indicators(df, self.config)
            signals = self.signal_generator.generate_signals_all_timeframes(data_dict)
            strong_signals = [s for s in signals if s.signal_type.value in ['STRONG_BUY', 'STRONG_SELL', 'BUY', 'SELL']]
            if strong_signals:
                for signal in strong_signals:
                    if signal.signal_type.value in ['STRONG_BUY', 'STRONG_SELL']:
                        await self.send_signal_alert(signal)
                await self.send_multiple_signals_alert(signals)
            self.last_signals = {s.timeframe: s for s in signals}
            self.signal_history.extend(signals)
            if len(self.signal_history) > 100:
                self.signal_history = self.signal_history[-100:]
            logger.info(f"Analysis cycle complete. Generated {len(signals)} signals")
        except Exception as e:
            logger.error(f"Error in analysis cycle: {e}", exc_info=True)

    async def run(self):
        self.running = True
        await self.run_analysis_cycle()
        while self.running:
            try:
                await asyncio.sleep(self.config.get('CHECK_INTERVAL', 60))
                await self.run_analysis_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(60)

    async def shutdown(self):
        self.running = False
        logger.info("Shutting down bot...")
        if self.telegram_bot:
            await self.telegram_bot.shutdown()
        logger.info("Bot shutdown complete")

    def get_status(self) -> Dict[str, Any]:
        return {
            'bot_name': BOT_NAME, 'version': BOT_VERSION, 'status': 'running' if self.running else 'stopped',
            'current_price': self.data_fetcher.get_current_price(), 'timeframes': self.config['TIMEFRAMES'],
            'last_analysis': datetime.now().isoformat(), 'active_signals': len(self.last_signals),
            'signal_history_count': len(self.signal_history), 'telegram_enabled': self.telegram_bot is not None,
        }

def main():
    bot = XAUUSBot()
    try:
        asyncio.run(bot.initialize())
        logger.info("Starting main bot loop...")
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
        asyncio.run(bot.shutdown())
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

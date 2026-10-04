"""Telegram Bot Module for XAUUSD Trading Bot"""
import logging
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from typing import Optional, Dict, Any
import asyncio

class TelegramBot:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.bot: Optional[Bot] = None
        self.app: Optional[Application] = None
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        try:
            self.bot = Bot(token=self.token)
            self.app = Application.builder().token(self.token).build()
            
            # إضافة معالجات الأوامر
            self.app.add_handler(CommandHandler("start", self._start_command))
            self.app.add_handler(CommandHandler("status", self._status_command))
            self.app.add_handler(CommandHandler("signals", self._signals_command))
            self.app.add_handler(CommandHandler("help", self._help_command))
            self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._echo))
            
            # تهيئة وتغيير حالة التطبيق والبدء بالاستماع للرسائل
            await self.app.initialize()
            await self.app.start()
            if self.app.updater:
                await self.app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
                
            self.logger.info("Telegram bot initialized and polling started successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Telegram bot: {e}")
            raise

    async def send_message(self, text: str, parse_mode: str = 'HTML') -> bool:
        if not self.bot:
            self.logger.error("Telegram bot not initialized")
            return False
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode=parse_mode)
            return True
        except Exception as e:
            self.logger.error(f"Failed to send Telegram message: {e}")
            return False

    async def send_signal_alert(self, signal: Dict[str, Any]) -> bool:
        signal_type = signal.get('signal_type', 'UNKNOWN')
        timeframe = signal.get('timeframe', 'Unknown')
        entry = signal.get('entry_price', 0)
        stop_loss = signal.get('stop_loss', 0)
        tp1 = signal.get('take_profit_1', 0)
        tp2 = signal.get('take_profit_2', 0)
        tp3 = signal.get('take_profit_3', 0)
        confidence = signal.get('confidence', 0)
        reasons = signal.get('reasons', [])
        candle_patterns = signal.get('candle_patterns', [])
        is_buy = signal_type in ['STRONG_BUY', 'BUY', 'WEAK_BUY']
        title = '🟢🟢 إشارة شراء الذهب 🟢🟢' if is_buy else '🔴🔴 إشارة بيع الذهب 🔴🔴'
        direction = 'شراء' if is_buy else 'بيع'
        message = f"""<b>{title}</b>

📊 الزوج: XAUUSD
⏱️ الفريم: {timeframe}
📌 الاتجاه: <b>{direction}</b>
📈 الثقة: <b>{confidence:.1%}</b>

💰 الدخول: <b>{entry:.4f}</b>
🛑 وقف الخسارة: <b>{stop_loss:.4f}</b>

🎯 الهدف الأول TP1: <b>{tp1:.4f}</b>
🛡️ الهدف الثاني TP2: <b>{tp2:.4f}</b> — عنده يتم تأمين الصفقة
🎯 الهدف الثالث TP3: <b>{tp3:.4f}</b>

🕯️ تأكيد الشموع:
"""
        for reason in reasons[:5]:
            message += f"• {reason}\n"
        if candle_patterns:
            message += "\n🕯️ أنماط الشموع:\n"
            for pattern in candle_patterns[:3]:
                message += f"• {pattern}\n"
        message += "\n🛡️ التأمين: عند وصول TP2 حرّك وقف الخسارة إلى سعر الدخول.\n⚠️ حالة الإشارة: نشطة"
        return await self.send_message(message)

    async def send_signal_update(self, signal: Dict[str, Any], event: str, current_price: float) -> bool:
        is_buy = signal.get('signal_type') in ['STRONG_BUY', 'BUY', 'WEAK_BUY']
        direction = 'شراء' if is_buy else 'بيع'
        tf = signal.get('timeframe', 'Unknown')
        if event == 'TP1':
            text = f"🎯 <b>وصل الهدف الأول</b>\n\n📌 {direction} XAUUSD | {tf}\n💰 السعر: <b>{current_price:.4f}</b>\n⏳ الصفقة مستمرة إلى TP2."
        elif event == 'TP2':
            text = f"🛡️ <b>تأمين الصفقة — TP2</b>\n\n📌 {direction} XAUUSD | {tf}\n💰 السعر: <b>{current_price:.4f}</b>\n🔒 حرّك وقف الخسارة إلى سعر الدخول: <b>{signal.get('entry_price', 0):.4f}</b>"
        elif event == 'TP3':
            text = f"✅ <b>اكتمل الهدف الثالث TP3</b>\n\n📌 {direction} XAUUSD | {tf}\n💰 السعر: <b>{current_price:.4f}</b>\n📊 الإشارة انتهت."
        else:
            text = f"❌ <b>انتهت إشارة {direction}</b>\n\n📌 XAUUSD | {tf}\n💰 السعر: <b>{current_price:.4f}</b>\n🛑 تم الوصول إلى وقف الخسارة."
        return await self.send_message(text)

    async def send_multiple_signals(self, signals: list) -> bool:
        if not signals:
            return False
        message = "<b>📊 XAUUSD Multi-Timeframe Analysis</b>\n\n"
        for signal in signals:
            signal_data = signal.to_dict() if hasattr(signal, 'to_dict') else signal
            signal_type = signal_data.get('signal_type', 'UNKNOWN')
            timeframe = signal_data.get('timeframe', 'Unknown')
            confidence = signal_data.get('confidence', 0)
            entry = signal_data.get('entry_price', 0)
            emoji_map = {'STRONG_BUY': '🚀', 'BUY': '🟢', 'WEAK_BUY': '✅', 'STRONG_SELL': '📉', 'SELL': '🔴', 'WEAK_SELL': '⚠️'}
            emoji = emoji_map.get(signal_type, '➖')
            message += f"{emoji} <b>{timeframe}:</b> {signal_type} (Conf: {confidence:.1%}) - Entry: ${entry:.4f}\n"
        message += "\n" + "=" * 40
        return await self.send_message(message)

    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🚀 <b>XAUUSD Trading Bot</b> 🚀\n\nWelcome to the professional XAUUSD trading signal bot!\n\nThis bot analyzes 600 candles across multiple timeframes (1m, 5m, 15m, 30m, 1h, 4h)\nand provides high-confidence trading signals with entry, stop loss, and take profit levels.\n\nAvailable commands:\n/start - Show this message\n/status - Show bot status\n/signals - Show recent signals\n/help - Show help\n\nSignals are sent automatically when detected!", parse_mode='HTML')

    async def _status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🤖 <b>Bot Status</b> 🤖\n\n✅ Running and monitoring XAUUSD\n✅ Analyzing all timeframes\n✅ Ready to send signals\n\nNext analysis in a few seconds...", parse_mode='HTML')

    async def _signals_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("📊 <b>Recent Signals</b> 📊\n\nFetching latest signals...\nCheck back soon for active signals!", parse_mode='HTML')

    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🆘 <b>Help</b> 🆘\n\nFor support or questions, contact the bot administrator.\n\nThe bot automatically sends signals when conditions are met.\nEach signal includes:\n  • Signal type (BUY/SELL)\n  • Entry price\n  • Stop Loss\n  • 3 Take Profit levels\n  • Confidence score\n  • Technical reasons\n", parse_mode='HTML')

    async def _echo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(f"I received: <i>{update.message.text}</i>\n\nUse /start, /status, /signals, or /help for commands.", parse_mode='HTML')

    async def shutdown(self):
        if self.app:
            if self.app.updater:
                await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            self.logger.info("Telegram bot stopped")

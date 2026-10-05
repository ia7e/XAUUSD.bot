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

    @staticmethod
    def _translate_reason(reason: str) -> str:
        s = str(reason or '')
        replacements = {
            'RSI crossed above oversold': 'مؤشر RSI اخترق صعودًا منطقة التشبع البيعي',
            'RSI crossed below overbought': 'مؤشر RSI اخترق هبوطًا منطقة التشبع الشرائي',
            'RSI in oversold zone': 'مؤشر RSI في منطقة التشبع البيعي',
            'RSI in overbought zone': 'مؤشر RSI في منطقة التشبع الشرائي',
            'MACD bullish crossover': 'تقاطع MACD شرائي',
            'MACD bearish crossover': 'تقاطع MACD بيعي',
            'MACD bullish': 'زخم MACD صاعد',
            'MACD bearish': 'زخم MACD هابط',
            'Bollinger lower band': 'السعر قرب الحد السفلي لبولينجر',
            'Bollinger upper band': 'السعر قرب الحد العلوي لبولينجر',
            'SMA trend bullish': 'اتجاه المتوسطات SMA صاعد',
            'SMA trend bearish': 'اتجاه المتوسطات SMA هابط',
            'EMA trend bullish': 'اتجاه المتوسطات EMA صاعد',
            'EMA trend bearish': 'اتجاه المتوسطات EMA هابط',
            'Stochastic bullish': 'استوكاستك شرائي',
            'Stochastic bearish': 'استوكاستك بيعي',
            'Candle pattern:': 'نموذج شموع:',
            'HAMMER': 'مطرقة',
            'INVERTED_HAMMER': 'مطرقة مقلوبة',
            'BULLISH_ENGULFING': 'ابتلاع شرائي',
            'PIERCING_LINE': 'خط الاختراق الشرائي',
            'MORNING_STAR': 'نجمة الصباح',
            'THREE_WHITE_SOLDIERS': 'ثلاثة جنود بيض',
            'DRAGONFLY_DOJI': 'دوجي اليعسوب',
            'SHOOTING_STAR': 'نجمة ساقطة',
            'HANGING_MAN': 'الرجل المشنوق',
            'BEARISH_ENGULFING': 'ابتلاع بيعي',
            'DARK_CLOUD_COVER': 'غطاء السحابة الداكنة',
            'EVENING_STAR': 'نجمة المساء',
            'THREE_BLACK_CROWS': 'ثلاثة غربان سوداء',
            'GRAVESTONE_DOJI': 'دوجي شاهد القبر'
        }
        for old, new in replacements.items():
            s = s.replace(old, new)
        return s

    async def send_signal_alert(self, signal: Dict[str, Any]) -> bool:
        signal_type = signal.get('signal_type', 'UNKNOWN')
        timeframe = signal.get('timeframe', 'Unknown')
        entry = signal.get('entry_price', 0)
        stop_loss = signal.get('stop_loss', 0)
        tp1 = signal.get('take_profit_1', 0)
        tp2 = signal.get('take_profit_2', 0)
        tp3 = signal.get('take_profit_3', 0)
        confidence = signal.get('confidence', 0)
        patterns = signal.get('candle_patterns', [])
        is_buy = signal_type in ['STRONG_BUY', 'BUY', 'WEAK_BUY']
        direction = 'شراء' if is_buy else 'بيع'
        emoji = '🟢' if is_buy else '🔴'
        pattern = self._translate_reason(patterns[0]) if patterns else 'حركة سعر واضحة'

        message = (
            f"<b>{emoji} XAUUSD | {direction}</b>\n"
            f"⏱ {timeframe} | 📊 ثقة {confidence:.0%}\n"
            f"💰 دخول: <b>{entry:.4f}</b>\n"
            f"🛑 وقف: <b>{stop_loss:.4f}</b>\n"
            f"🎯 TP1: <b>{tp1:.4f}</b> | TP2: <b>{tp2:.4f}</b> | TP3: <b>{tp3:.4f}</b>\n"
            f"🕯️ {pattern}\n"
            f"🔒 الإشارة نشطة — لا توجد إشارة جديدة حتى تنتهي."
        )
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
        message = "<b>📊 تحليل إشارات الذهب متعدد الأطر الزمنية</b>\n\n"
        for signal in signals:
            signal_data = signal.to_dict() if hasattr(signal, 'to_dict') else signal
            signal_type = signal_data.get('signal_type', 'UNKNOWN')
            timeframe = signal_data.get('timeframe', 'Unknown')
            confidence = signal_data.get('confidence', 0)
            entry = signal_data.get('entry_price', 0)
            emoji_map = {'STRONG_BUY': '🚀', 'BUY': '🟢', 'WEAK_BUY': '✅', 'STRONG_SELL': '📉', 'SELL': '🔴', 'WEAK_SELL': '⚠️'}
            emoji = emoji_map.get(signal_type, '➖')
            names = {'STRONG_BUY':'شراء قوي','BUY':'شراء','WEAK_BUY':'شراء','STRONG_SELL':'بيع قوي','SELL':'بيع','WEAK_SELL':'بيع'}
            message += f"{emoji} <b>الفريم {timeframe}:</b> {names.get(signal_type, 'غير معروف')} — الثقة: {confidence:.1%} — الدخول: ${entry:.4f}\n"
        message += "\n" + "=" * 40
        return await self.send_message(message)

    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🚀 <b>XAUUSD Trading Bot</b> 🚀\n\nمرحبًا بك في نظام إشارات الذهب XAUUSD.\n\n📡 مصدر البيانات: BIQuote\n📊 يتم اتخاذ القرار من آخر 10 شموع مغلقة.\n⏱️ المراقبة مستمرة كل ثانية.\n\nالأوامر المتاحة:\n/start - عرض رسالة التشغيل\n/status - حالة النظام\n/signals - آخر الإشارات\n/help - المساعدة\n\n🟢🟢 يتم إرسال إشارة الشراء أو البيع تلقائيًا عند تحقق الشروط.", parse_mode='HTML')

    async def _status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🤖 <b>حالة نظام إشارات الذهب</b> 🤖\n\n✅ النظام يعمل ويراقب XAUUSD\n✅ يتم تحليل جميع الأطر الزمنية\n✅ النظام جاهز لإرسال الإشارات\n📊 القرار يعتمد على آخر 10 شموع مغلقة\n📡 مصدر البيانات: BIQuote", parse_mode='HTML')

    async def _signals_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("📊 <b>آخر الإشارات</b> 📊\n\nجاري جلب أحدث الإشارات...\nستظهر الإشارات النشطة هنا عند توفرها.", parse_mode='HTML')

    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🆘 <b>المساعدة</b> 🆘\n\nالنظام يرسل إشارات الذهب تلقائيًا عند تحقق الشروط.\n\nكل إشارة تحتوي على:\n• نوع الإشارة: شراء أو بيع\n• سعر الدخول\n• وقف الخسارة\n• ثلاثة أهداف\n• نسبة الثقة\n• أسباب فنية\n• نماذج الشموع", parse_mode='HTML')

    async def _echo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(f"وصلتني رسالتك: <i>{update.message.text}</i>\n\nاستخدم /start أو /status أو /signals أو /help.", parse_mode='HTML')

    async def shutdown(self):
        if self.app:
            if self.app.updater:
                await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            self.logger.info("Telegram bot stopped")

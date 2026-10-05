"""تشغيل نظام إشارات XAUUSD + لوحة التحكم + Telegram."""
import os
import sys
import asyncio
import threading
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web_server import app, set_trading_bot
from main import XAUUSBot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_trading_bot():
    async def runner():
        bot = XAUUSBot()
        set_trading_bot(bot)
        await bot.initialize()
        await bot.run()
    asyncio.run(runner())


if __name__ == '__main__':
    bot_thread = threading.Thread(target=run_trading_bot, daemon=True, name='xauusd-trading-bot')
    bot_thread.start()
    port = int(os.getenv('PORT', 10000))
    logger.info('تشغيل لوحة التحكم ونظام الإشارات على المنفذ %s', port)
    app.run(host='0.0.0.0', port=port, threaded=True, debug=False)

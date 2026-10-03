"""
Run Web Server & Telegram Bot for XAUUSD Trading Bot
This script starts both the Flask web server and the Telegram bot
"""

import os
import sys
import threading
import asyncio
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web_server import app
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from telegram_bot import TelegramBot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_telegram_bot():
    """Run Telegram Bot in a dedicated asyncio loop"""
    if not TELEGRAM_TOKEN:
        logger.warning("TELEGRAM_TOKEN is missing. Telegram bot will not start.")
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    bot = TelegramBot(token=TELEGRAM_TOKEN, chat_id=TELEGRAM_CHAT_ID)
    
    try:
        logger.info("Starting Telegram Bot...")
        loop.run_until_complete(bot.initialize())
        loop.run_forever()
    except Exception as e:
        logger.error(f"Telegram Bot error: {e}")
    finally:
        loop.run_until_complete(bot.shutdown())
        loop.close()

if __name__ == '__main__':
    # Start Telegram Bot in a background thread
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()
    
    # Start Flask Web Server
    port = int(os.getenv('PORT', 8080))
    print(f"Starting XAUUSD Web Server on port {port}")
    print(f"Access the dashboard at: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, threaded=True, debug=False)

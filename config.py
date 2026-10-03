# XAUUSD Trading Bot Configuration
import os

# Telegram Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# Exchange Configuration (Using Binance as default)
EXCHANGE_ID = 'binance'
SYMBOL = 'XAU/USD:XAU'

# Trading Parameters
TIMEFRAMES = ['1m', '5m', '15m', '30m', '1h', '4h']
CANDLES_COUNT = 600

# Technical Indicators Settings
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2

SMA_PERIODS = [50, 100, 200]
EMA_PERIODS = [20, 50]

# Signal Strength Thresholds
STRONG_BUY_THRESHOLD = 0.7
STRONG_SELL_THRESHOLD = 0.7

# Risk Management
RISK_PER_TRADE = 0.02
STOP_LOSS_ATR_MULTIPLIER = 2
TAKE_PROFIT_ATR_MULTIPLIER = 3

# API Rate Limits
RATE_LIMIT_DELAY = 0.1

# Bot Settings
BOT_NAME = "XAUUSD Trading Bot"
BOT_VERSION = "1.0.0"
CHECK_INTERVAL = 60

# Logging
LOG_LEVEL = 'INFO'
LOG_FILE = 'bot.log'

# Render/Deployment Settings
PORT = int(os.getenv('PORT', 8080))

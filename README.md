# XAUUSD Trading Bot

A professional trading bot for XAUUSD that analyzes 600 candles across 6 timeframes (1m, 5m, 15m, 30m, 1h, 4h) and sends trading signals to Telegram with entry, stop loss, and 3 take profit levels.

## Features

- Multi-timeframe analysis (1m, 5m, 15m, 30m, 1h, 4h)
- 8 technical indicators: RSI, MACD, Bollinger Bands, SMA, EMA, Stochastic, ATR, VWAP
- Signal generation with confidence scoring
- Telegram real-time alerts
- Automatic stop loss and take profit calculation
- Clean, efficient code (~1200 lines)

## Setup

```bash
git clone https://github.com/ia7e/XAUUSD.bot.git
cd XAUUSD.bot
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Telegram token and chat ID
python main.py
```

## Deployment to Render

1. Create Render account at https://render.com
2. Connect your GitHub repository
3. Create Web Service with:
   - Build: `pip install -r requirements.txt`
   - Start: `python main.py`
   - Add environment variables from .env

## Telegram Setup

1. Create bot with @BotFather on Telegram
2. Get your chat ID
3. Add to .env:
   ```
   TELEGRAM_TOKEN=your_bot_token
   TELEGRAM_CHAT_ID=your_chat_id
   ```

## Signal Types

- STRONG_BUY/STRONG_SELL - High confidence
- BUY/SELL - Moderate confidence
- WEAK_BUY/WEAK_SELL - Low confidence

Each signal includes entry, stop loss, and 3 take profit levels with confidence score.

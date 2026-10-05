"""
Web Server for XAUUSD Trading Bot
Provides a beautiful web interface showing current price, signals, and statistics
"""

from flask import Flask, render_template, jsonify, request
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import os
import sys
import pandas as pd
import math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import *
from data_fetcher import DataFetcher
from signal_generator import SignalGenerator, TradingSignal
from technical_indicators import TechnicalIndicators
from candle_patterns import CandlePatterns

app = Flask(__name__, template_folder='templates', static_folder='static')

trading_bot = None


def set_trading_bot(bot):
    """Connect the dashboard to the one real bot instance used for Telegram/lifecycle."""
    global trading_bot
    trading_bot = bot

# Global state
bot_state = {
    'current_price': None,
    'last_updated': None,
    'signals': [],
    'signal_history': [],
    'statistics': {
        'total_signals': 0,
        'buy_signals': 0,
        'sell_signals': 0,
        'strong_buy': 0,
        'strong_sell': 0,
        'last_24h_signals': 0,
        'last_1h_signals': 0
    },
    'timeframes_data': {},
    'candle_patterns': [],
    'last_error': None
}

# Initialize components
config = {
    'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
    'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    'EXCHANGE_ID': EXCHANGE_ID,
    'SYMBOL': SYMBOL,
    'TIMEFRAMES': TIMEFRAMES,
    'CANDLES_COUNT': CANDLES_COUNT,
    'DECISION_CANDLES': DECISION_CANDLES,
    'BUY_THRESHOLD': BUY_THRESHOLD,
    'SELL_THRESHOLD': SELL_THRESHOLD,
    'STRONG_BUY_THRESHOLD': STRONG_BUY_THRESHOLD,
    'STRONG_SELL_THRESHOLD': STRONG_SELL_THRESHOLD,
    'RSI_PERIOD': RSI_PERIOD,
    'RSI_OVERBOUGHT': RSI_OVERBOUGHT,
    'RSI_OVERSOLD': RSI_OVERSOLD,
    'MACD_FAST': MACD_FAST,
    'MACD_SLOW': MACD_SLOW,
    'MACD_SIGNAL': MACD_SIGNAL,
    'BOLLINGER_PERIOD': BOLLINGER_PERIOD,
    'BOLLINGER_STD': BOLLINGER_STD,
    'SMA_PERIODS': SMA_PERIODS,
    'EMA_PERIODS': EMA_PERIODS,
    'STOP_LOSS_ATR_MULTIPLIER': STOP_LOSS_ATR_MULTIPLIER,
    'TAKE_PROFIT_ATR_MULTIPLIER': TAKE_PROFIT_ATR_MULTIPLIER,
    'RATE_LIMIT_DELAY': RATE_LIMIT_DELAY,
    'XAUUSD_SOURCE': XAUUSD_SOURCE,
    'BIQUOTE_BASE_URL': BIQUOTE_BASE_URL,
    'BIQUOTE_SYMBOL': BIQUOTE_SYMBOL
}

data_fetcher = DataFetcher(config)
technical_indicators = TechnicalIndicators()
signal_generator = SignalGenerator(config)

def _json_safe(value):
    """Convert pandas/numpy values and non-finite numbers to strict JSON-safe values."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if hasattr(value, 'item'):
        try:
            return _json_safe(value.item())
        except Exception:
            pass
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return value

def update_bot_state():
    """Update bot state with fresh data"""
    global bot_state
    
    try:
        bot_state['last_error'] = None
        # Get current price
        current_price = data_fetcher.get_current_price()
        if current_price:
            bot_state['current_price'] = float(current_price)
            bot_state['last_updated'] = datetime.now().isoformat()
        
        # Fetch data for all timeframes
        data_dict = data_fetcher.fetch_all_timeframes()
        
        # Calculate indicators and detect patterns
        timeframes_data = {}
        all_patterns = []
        
        for timeframe, df in data_dict.items():
            if df is not None and len(df) > 0:
                if 'isOpen' in df.columns and bool(df['isOpen'].iloc[-1]):
                    df = df.iloc[:-1].copy()
                if len(df) < DECISION_CANDLES:
                    continue;
                # Calculate indicators
                df_with_indicators = technical_indicators.calculate_all_indicators(df, config)
                timeframes_data[timeframe] = df_with_indicators
                
                # Detect candle patterns
                patterns = CandlePatterns.detect_all_patterns(df_with_indicators, lookback=10)
                for pattern in patterns:
                    pattern_data = pattern.to_dict() if hasattr(pattern, 'to_dict') else dict(pattern)
                    pattern_data['timeframe'] = timeframe
                    all_patterns.append(pattern_data)
        
        bot_state['timeframes_data'] = timeframes_data
        bot_state['candle_patterns'] = all_patterns
        
        # The dashboard displays the SAME active signal that is sent to Telegram.
        # It never creates/duplicates a new signal every refresh.
        if trading_bot is not None:
            signals_dicts = list(trading_bot.active_signals.values())
            history_dicts = list(trading_bot.signal_history)
        else:
            raw_signals = signal_generator.generate_signals_all_timeframes(timeframes_data)
            signals_dicts = [s.to_dict() if hasattr(s, 'to_dict') else vars(s) for s in raw_signals]
            history_dicts = bot_state.get('signal_history', [])

        bot_state['signals'] = signals_dicts
        bot_state['signal_history'] = history_dicts[-100:]

        def is_last_hours(ts_str, hours):
            try:
                if not ts_str:
                    return False
                parsed = datetime.fromisoformat(str(ts_str).replace('Z', '+00:00'))
                now = datetime.now(parsed.tzinfo) if parsed.tzinfo else datetime.now()
                return parsed > now - timedelta(hours=hours)
            except Exception:
                return False

        all_history = bot_state['signal_history']
        buy_signals = len([s for s in all_history if 'BUY' in s.get('signal_type', '')])
        sell_signals = len([s for s in all_history if 'SELL' in s.get('signal_type', '')])
        strong_buy = len([s for s in all_history if s.get('signal_type') == 'STRONG_BUY'])
        strong_sell = len([s for s in all_history if s.get('signal_type') == 'STRONG_SELL'])

        bot_state['statistics'] = {
            'total_signals': len(all_history),
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'strong_buy': strong_buy,
            'strong_sell': strong_sell,
            'last_24h_signals': len([s for s in all_history if is_last_hours(s.get('opened_at') or s.get('timestamp'), 24)]),
            'last_1h_signals': len([s for s in all_history if is_last_hours(s.get('opened_at') or s.get('timestamp'), 1)])
        }        
        return True
    except Exception as e:
        print(f"Error updating bot state: {e}")
        bot_state['last_error'] = str(e)
        return False

def background_updater():
    """Background thread to update data periodically"""
    while True:
        update_bot_state()
        time.sleep(60)  # Update every 60 seconds

# Start background updater
updater_thread = threading.Thread(target=background_updater, daemon=True)
updater_thread.start()

# Initial update
update_bot_state()

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

@app.route('/api/price')
def get_price():
    """Get current XAUUSD price"""
    return jsonify({
        'price': bot_state['current_price'],
        'last_updated': bot_state['last_updated']
    })

@app.route('/api/signals')
def get_signals():
    """Get current signals"""
    return jsonify(_json_safe({
        'signals': bot_state['signals'],
        'count': len(bot_state['signals']),
        'last_error': bot_state.get('last_error')
    }))

@app.route('/api/signals/history')
def get_signal_history():
    """Get signal history"""
    return jsonify(_json_safe({
        'history': bot_state['signal_history'],
        'count': len(bot_state['signal_history']),
        'last_error': bot_state.get('last_error')
    }))

@app.route('/api/statistics')
def get_statistics():
    """Get trading statistics"""
    return jsonify(_json_safe(bot_state['statistics']))

@app.route('/api/timeframes')
def get_timeframes():
    """Get data for all timeframes with safe float casting for JSON"""
    data = {}
    for timeframe, df in bot_state['timeframes_data'].items():
        if df is not None and len(df) > 0:
            def safe_float(val):
                if pd.notna(val):
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        return None
                return None

            data[timeframe] = {
                'open': safe_float(df['open'].iloc[-1]),
                'high': safe_float(df['high'].iloc[-1]),
                'low': safe_float(df['low'].iloc[-1]),
                'close': safe_float(df['close'].iloc[-1]),
                'volume': safe_float(df['volume'].iloc[-1]) if 'volume' in df.columns else 0.0,
                'rsi': safe_float(df['rsi'].iloc[-1]) if 'rsi' in df.columns else None,
                'macd': safe_float(df['macd_line'].iloc[-1]) if 'macd_line' in df.columns else None,
                'bb_upper': safe_float(df['bb_upper'].iloc[-1]) if 'bb_upper' in df.columns else None,
                'bb_lower': safe_float(df['bb_lower'].iloc[-1]) if 'bb_lower' in df.columns else None
            }
    return jsonify(_json_safe(data))

@app.route('/api/patterns')
def get_patterns():
    """Get detected candle patterns"""
    return jsonify(_json_safe({
        'patterns': bot_state['candle_patterns'],
        'count': len(bot_state['candle_patterns']),
        'last_error': bot_state.get('last_error')
    }))

@app.route('/api/status')
def get_status():
    """Get bot status"""
    return jsonify({
        'status': 'running',
        'current_price': bot_state['current_price'],
        'last_updated': bot_state['last_updated'],
        'active_signals': len(bot_state['signals']),
        'total_signals': bot_state['statistics']['total_signals'],
        'data_source': config.get('XAUUSD_SOURCE', 'BIQUOTE'),
        'decision_candles': DECISION_CANDLES,
        'last_error': bot_state.get('last_error')
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    print(f"Starting XAUUSD Web Server on port {port}")
    app.run(host='0.0.0.0', port=port, threaded=True, debug=False)

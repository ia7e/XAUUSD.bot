"""
Web Server for XAUUSD Trading Bot
Provides a beautiful web interface showing current price, signals, and statistics
"""

from flask import Flask, render_template, jsonify, request
import threading
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import *
from data_fetcher import DataFetcher
from signal_generator import SignalGenerator, TradingSignal
from technical_indicators import TechnicalIndicators
from candle_patterns import CandlePatterns

app = Flask(__name__, template_folder='templates', static_folder='static')

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
    'candle_patterns': []
}

# Initialize components
config = {
    'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
    'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    'EXCHANGE_ID': EXCHANGE_ID,
    'SYMBOL': SYMBOL,
    'TIMEFRAMES': TIMEFRAMES,
    'CANDLES_COUNT': CANDLES_COUNT,
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

def update_bot_state():
    """Update bot state with fresh data"""
    global bot_state
    
    try:
        # Get current price
        current_price = data_fetcher.get_current_price()
        if current_price:
            bot_state['current_price'] = current_price
            bot_state['last_updated'] = datetime.now().isoformat()
        
        # Fetch data for all timeframes
        data_dict = data_fetcher.fetch_all_timeframes()
        
        # Calculate indicators and detect patterns
        timeframes_data = {}
        all_patterns = []
        
        for timeframe, df in data_dict.items():
            if len(df) > 0:
                # Calculate indicators
                df_with_indicators = technical_indicators.calculate_all_indicators(df, config)
                timeframes_data[timeframe] = df_with_indicators
                
                # Detect candle patterns
                patterns = CandlePatterns.detect_all_patterns(df_with_indicators, lookback=10)
                for pattern in patterns:
                    pattern_data = pattern.to_dict()
                    pattern_data['timeframe'] = timeframe
                    all_patterns.append(pattern_data)
        
        bot_state['timeframes_data'] = timeframes_data
        bot_state['candle_patterns'] = all_patterns
        
        # Generate signals
        signals = signal_generator.generate_signals_all_timeframes(timeframes_data)
        bot_state['signals'] = [s.to_dict() for s in signals]
        
        # Update statistics
        total_signals = len(bot_state['signal_history']) + len(signals)
        buy_signals = len([s for s in signals if 'BUY' in s['signal_type']]) + \
                      len([s for s in bot_state['signal_history'] if 'BUY' in s['signal_type']])
        sell_signals = len([s for s in signals if 'SELL' in s['signal_type']]) + \
                       len([s for s in bot_state['signal_history'] if 'SELL' in s['signal_type']])
        
        strong_buy = len([s for s in signals if s['signal_type'] == 'STRONG_BUY']) + \
                     len([s for s in bot_state['signal_history'] if s['signal_type'] == 'STRONG_BUY'])
        strong_sell = len([s for s in signals if s['signal_type'] == 'STRONG_SELL']) + \
                      len([s for s in bot_state['signal_history'] if s['signal_type'] == 'STRONG_SELL'])
        
        # Add new signals to history
        bot_state['signal_history'] = signals + bot_state['signal_history']
        if len(bot_state['signal_history']) > 100:
            bot_state['signal_history'] = bot_state['signal_history'][:100]
        
        bot_state['statistics'] = {
            'total_signals': total_signals,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'strong_buy': strong_buy,
            'strong_sell': strong_sell,
            'last_24h_signals': len([s for s in bot_state['signal_history'] 
                                     if datetime.fromisoformat(s.get('timestamp', '')) > datetime.now() - timedelta(hours=24)]),
            'last_1h_signals': len([s for s in signals])
        }
        
        return True
    except Exception as e:
        print(f"Error updating bot state: {e}")
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
    return jsonify({
        'signals': bot_state['signals'],
        'count': len(bot_state['signals'])
    })

@app.route('/api/signals/history')
def get_signal_history():
    """Get signal history"""
    return jsonify({
        'history': [s.to_dict() if hasattr(s, 'to_dict') else s for s in bot_state['signal_history']],
        'count': len(bot_state['signal_history'])
    })

@app.route('/api/statistics')
def get_statistics():
    """Get trading statistics"""
    return jsonify(bot_state['statistics'])

@app.route('/api/timeframes')
def get_timeframes():
    """Get data for all timeframes"""
    data = {}
    for timeframe, df in bot_state['timeframes_data'].items():
        if len(df) > 0:
            data[timeframe] = {
                'open': df['open'].iloc[-1],
                'high': df['high'].iloc[-1],
                'low': df['low'].iloc[-1],
                'close': df['close'].iloc[-1],
                'volume': df['volume'].iloc[-1],
                'rsi': df['rsi'].iloc[-1] if 'rsi' in df.columns else None,
                'macd': df['macd_line'].iloc[-1] if 'macd_line' in df.columns else None,
                'bb_upper': df['bb_upper'].iloc[-1] if 'bb_upper' in df.columns else None,
                'bb_lower': df['bb_lower'].iloc[-1] if 'bb_lower' in df.columns else None
            }
    return jsonify(data)

@app.route('/api/patterns')
def get_patterns():
    """Get detected candle patterns"""
    return jsonify({
        'patterns': bot_state['candle_patterns'],
        'count': len(bot_state['candle_patterns'])
    })

@app.route('/api/status')
def get_status():
    """Get bot status"""
    return jsonify({
        'status': 'running',
        'current_price': bot_state['current_price'],
        'last_updated': bot_state['last_updated'],
        'active_signals': len(bot_state['signals']),
        'total_signals': bot_state['statistics']['total_signals'],
        'data_source': config.get('XAUUSD_SOURCE', 'Unknown')
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    print(f"Starting XAUUSD Web Server on port {port}")
    app.run(host='0.0.0.0', port=port, threaded=True, debug=False)

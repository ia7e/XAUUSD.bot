"""
Run Web Server for XAUUSD Trading Bot
This script starts the Flask web server
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web_server import app

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    print(f"Starting XAUUSD Web Server on port {port}")
    print(f"Access the dashboard at: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, threaded=True, debug=False)

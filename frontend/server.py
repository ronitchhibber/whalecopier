#!/usr/bin/env python3
"""
Simple web server for the settings frontend
"""

import json
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse

class SettingsHandler(SimpleHTTPRequestHandler):
    """Custom handler for settings API"""

    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/api/settings':
            self.send_settings()
        elif self.path == '/':
            # Serve unified_dashboard.html as the root
            self.path = '/unified_dashboard.html'
            super().do_GET()
        elif self.path == '/index':
            # Legacy index page redirect
            self.path = '/unified_dashboard.html'
            super().do_GET()
        else:
            # Serve static files
            super().do_GET()

    def do_POST(self):
        """Handle POST requests"""
        if self.path == '/api/settings':
            self.save_settings()
        else:
            self.send_error(404, "Not Found")

    def send_settings(self):
        """Send current settings as JSON"""
        settings_file = '../config/settings.json'

        if os.path.exists(settings_file):
            with open(settings_file, 'r') as f:
                settings = json.load(f)
        else:
            settings = self.get_default_settings()

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(settings).encode())

    def save_settings(self):
        """Save settings from POST request"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        try:
            settings = json.loads(post_data.decode('utf-8'))

            # Save to file
            settings_file = '../config/settings.json'
            os.makedirs('../config', exist_ok=True)

            with open(settings_file, 'w') as f:
                json.dump(settings, f, indent=2)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success"}).encode())

        except Exception as e:
            self.send_error(400, f"Bad Request: {str(e)}")

    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def get_default_settings(self):
        """Return default settings"""
        return {
            "display": {
                "format": "mini",
                "refresh_rate": 5,
                "show_alerts": True,
                "show_emojis": True,
                "terminal_width": 80,
                "color_enabled": False,
                "format_options": {
                    "single": {
                        "lines": 1,
                        "description": "Ultra minimal scrolling display"
                    },
                    "status": {
                        "lines": 2,
                        "description": "Minimal status bar"
                    },
                    "metrics": {
                        "lines": 4,
                        "description": "Key numbers only"
                    },
                    "ticker": {
                        "lines": 5,
                        "description": "Essential info ticker"
                    },
                    "grid": {
                        "lines": 8,
                        "description": "Organized metric grid"
                    },
                    "mini": {
                        "lines": 10,
                        "description": "Balanced information view"
                    },
                    "compact": {
                        "lines": 15,
                        "description": "Full monitoring dashboard"
                    }
                }
            },
            "trading": {
                "mode": "paper",
                "max_position_size": 1000,
                "max_daily_trades": 50,
                "stop_loss_percent": 10,
                "take_profit_percent": 20,
                "enable_copy_trading": False
            },
            "risk": {
                "max_drawdown": 15,
                "position_sizing": "kelly",
                "kelly_fraction": 0.25,
                "var_confidence": 0.95,
                "max_correlation": 0.7
            },
            "whales": {
                "min_wqs_score": 0.7,
                "min_sharpe_ratio": 1.5,
                "min_win_rate": 0.6,
                "max_whales_to_follow": 10,
                "update_frequency": 3600
            }
        }


def run_server(port=8888):
    """Run the web server"""
    server_address = ('', port)
    httpd = HTTPServer(server_address, SettingsHandler)

    print(f"""
    ════════════════════════════════════════════════════════
    🚀 WhaleTracker Unified Dashboard Server Started
    ════════════════════════════════════════════════════════

    Main Dashboard:
    → http://localhost:{port}/

    Available Pages:
    • http://localhost:{port}/                      - Unified Dashboard (default)
    • http://localhost:{port}/settings.html         - Settings Configuration
    • http://localhost:{port}/index.html            - Legacy Home Page

    API endpoints:
    • GET  /api/settings - Get current settings
    • POST /api/settings - Save settings

    Press Ctrl+C to stop the server
    ════════════════════════════════════════════════════════
    """)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.shutdown()


if __name__ == '__main__':
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8888

    # Change to frontend directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    run_server(port)
#!/usr/bin/env python3
"""
Settings Manager for Polymarket Whale Copy Trader
Centralized settings interface with tabs for different configuration areas
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional

class SettingsManager:
    """Main settings management interface"""

    def __init__(self):
        self.settings_file = "config/settings.json"
        self.load_all_settings()

    def load_all_settings(self):
        """Load all settings from file"""
        if os.path.exists(self.settings_file):
            with open(self.settings_file, 'r') as f:
                self.settings = json.load(f)
        else:
            self.settings = self.get_default_settings()
            self.save_settings()

    def get_default_settings(self) -> Dict:
        """Get default settings structure"""
        return {
            "display": {
                "format": "mini",
                "refresh_rate": 5,
                "show_alerts": True,
                "show_emojis": True,
                "terminal_width": 80,
                "color_enabled": False
            },
            "trading": {
                "mode": "paper",  # paper or live
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
            },
            "alerts": {
                "discord_enabled": False,
                "discord_webhook": "",
                "telegram_enabled": False,
                "telegram_token": "",
                "telegram_chat_id": "",
                "email_enabled": False,
                "email_address": "",
                "alert_on_trade": True,
                "alert_on_error": True
            },
            "api": {
                "polymarket_api_url": "https://gamma-api.polymarket.com",
                "graph_api_url": "https://api.thegraph.com",
                "websocket_url": "wss://ws-subscriptions-clob.polymarket.com/ws/market",
                "rate_limit": 100,
                "timeout": 30
            },
            "database": {
                "host": "localhost",
                "port": 5432,
                "name": "polymarket_trader",
                "user": "trader",
                "password": "trader_password"
            }
        }

    def save_settings(self):
        """Save all settings to file"""
        os.makedirs('config', exist_ok=True)
        with open(self.settings_file, 'w') as f:
            json.dump(self.settings, f, indent=2)

    def display_header(self):
        """Display settings header"""
        print("\n" + "="*70)
        print("POLYMARKET WHALE TRADER - SETTINGS MANAGER")
        print("="*70)

    def display_menu(self):
        """Display main menu"""
        print("\nSettings Categories:")
        print("  1. Display Settings     - Screen format and appearance")
        print("  2. Trading Settings     - Trading parameters and limits")
        print("  3. Risk Settings        - Risk management parameters")
        print("  4. Whale Settings       - Whale selection criteria")
        print("  5. Alert Settings       - Notification configuration")
        print("  6. API Settings         - API endpoints and limits")
        print("  7. Database Settings    - Database connection")
        print("  8. Import/Export        - Backup and restore settings")
        print("  9. Reset to Defaults    - Reset all settings")
        print("  0. Save & Exit          - Save changes and exit")

    def edit_display_settings(self):
        """Edit display settings with format selector"""
        while True:
            print("\n" + "="*70)
            print("DISPLAY SETTINGS")
            print("="*70)

            current = self.settings['display']
            print(f"\nCurrent Display Format: {current['format'].upper()}")
            print(f"Refresh Rate: {current['refresh_rate']} seconds")
            print(f"Show Alerts: {current['show_alerts']}")
            print(f"Show Emojis: {current['show_emojis']}")
            print(f"Terminal Width: {current['terminal_width']}")
            print(f"Colors Enabled: {current['color_enabled']}")

            print("\n--- Available Display Formats ---")
            print("  single     (1 line)  - Ultra minimal scrolling")
            print("  status     (2 lines) - Minimal status bar")
            print("  metrics    (4 lines) - Key numbers only")
            print("  ticker     (5 lines) - Essential info ticker")
            print("  grid       (8 lines) - Organized metric grid")
            print("  mini      (10 lines) - Balanced view [DEFAULT]")
            print("  compact   (15 lines) - Full dashboard")

            print("\nOptions:")
            print("  F. Change display format")
            print("  P. Preview formats")
            print("  R. Set refresh rate")
            print("  A. Toggle alerts")
            print("  E. Toggle emojis")
            print("  W. Set terminal width")
            print("  C. Toggle colors")
            print("  B. Back to main menu")

            choice = input("\nSelect option: ").strip().upper()

            if choice == 'B':
                break
            elif choice == 'F':
                self.select_display_format()
            elif choice == 'P':
                self.preview_display_formats()
            elif choice == 'R':
                rate = input("Enter refresh rate in seconds (1-60): ")
                try:
                    rate = int(rate)
                    if 1 <= rate <= 60:
                        self.settings['display']['refresh_rate'] = rate
                        print(f"✓ Refresh rate set to {rate} seconds")
                except:
                    print("⚠ Invalid input")
            elif choice == 'A':
                self.settings['display']['show_alerts'] = not self.settings['display']['show_alerts']
                print(f"✓ Alerts {'enabled' if self.settings['display']['show_alerts'] else 'disabled'}")
            elif choice == 'E':
                self.settings['display']['show_emojis'] = not self.settings['display']['show_emojis']
                print(f"✓ Emojis {'enabled' if self.settings['display']['show_emojis'] else 'disabled'}")
            elif choice == 'W':
                width = input("Enter terminal width (40-200): ")
                try:
                    width = int(width)
                    if 40 <= width <= 200:
                        self.settings['display']['terminal_width'] = width
                        print(f"✓ Terminal width set to {width}")
                except:
                    print("⚠ Invalid input")
            elif choice == 'C':
                self.settings['display']['color_enabled'] = not self.settings['display']['color_enabled']
                print(f"✓ Colors {'enabled' if self.settings['display']['color_enabled'] else 'disabled'}")

    def select_display_format(self):
        """Select display format with preview"""
        formats = ['single', 'status', 'metrics', 'ticker', 'grid', 'mini', 'compact']

        print("\nSelect Display Format:")
        for i, fmt in enumerate(formats, 1):
            print(f"  {i}. {fmt}")

        choice = input("\nEnter number (1-7): ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(formats):
                self.settings['display']['format'] = formats[idx]
                print(f"✓ Display format set to: {formats[idx]}")
                self.preview_format(formats[idx])
        except:
            print("⚠ Invalid selection")

    def preview_format(self, format_name: str):
        """Preview a specific format"""
        print(f"\n--- Preview of {format_name.upper()} format ---")

        if format_name == 'single':
            print("WHALE TRADER | P&L:+$8.5K Win:73% Sharpe:2.34 | Systems:🟢")
        elif format_name == 'status':
            print("WHALE TRADER │ P&L:+$8.5K Win:73% │ ⚠ Loss limit 8.5%")
            print("━" * 50)
        elif format_name == 'metrics':
            print("P&L:+$8.5K │ Win:73% │ Sharpe:2.34 │ DD:8%")
            print("Whales:25  │ Signals:145/d │ VaR:12%")
            print("Volume:$125K │ Trades:1456 │ Exp:$45K")
            print("Last: BUY BTC>100k +12.5% │ Systems:🟢")
        elif format_name == 'ticker':
            print("══ WHALE TRADER ══")
            print("P&L:+$8.5K Win:73% Sharpe:2.34 DD:8%")
            print("Whales:25 Signals:145 Trades:1456")
            print("Last: BUY BTC>100k $5K +12.5%")
            print("Systems: DB:🟢 API:🟢 WS:🟢 Engine:🟢")
        elif format_name == 'grid':
            print(f"WHALE TRADER  {datetime.now().strftime('%H:%M:%S')}")
            print("┌─────────────┬─────────────┬─────────────┐")
            print("│ P&L: +$8.5K │ Win: 73%    │ Sharpe: 2.34│")
            print("│ DD: 8%      │ VaR: 12%    │ Trades: 1456│")
            print("│ Whales: 25  │ Signals:145 │ Exp: $45K   │")
            print("└─────────────┴─────────────┴─────────────┘")
            print("Last: BUY BTC>100k $5K +12.5%")
            print("Status: 🟢 🟢 🟢 🟢 🟡")
        elif format_name == 'mini':
            print(f"WHALE TRADER {datetime.now().strftime('%H:%M:%S')}")
            print("DB:🟢 API:🟢 WS:🟢 Engine:🟢 Monitor:🟡")
            print("Trades:1456 Win:73% P&L:+$8.5K Sharpe:2.34")
            print("Whales:25 Signals:145 Exposure:$45K DD:8%")
            print("Last: BUY BTC>100k $5K +12.5%")
            print("⚠ Loss limit 8.5%")
            print("[Q]uit [R]efresh")
        elif format_name == 'compact':
            print(f"POLYMARKET WHALE TRADER - {datetime.now().strftime('%H:%M:%S')}")
            print("─" * 50)
            print("Status: DB:🟢 API:🟢 WS:🟢 Engine:🟢 Monitor:🟡")
            print("\nPerformance:")
            print("  Trades:1456 WinRate:73% Vol:$125K P&L:+$8.5K")
            print("  Sharpe:2.34 DD:8% VaR:12% Whales:25")
            print("\nRecent: BUY 0x1234→BTC>100k $5K +12.5%")
            print("Alert: ⚠ Approaching daily loss limit")

    def preview_display_formats(self):
        """Preview all display formats"""
        formats = ['single', 'status', 'metrics', 'ticker', 'grid', 'mini', 'compact']
        for fmt in formats:
            print("\n" + "="*50)
            self.preview_format(fmt)
        print("\n" + "="*50)

    def edit_trading_settings(self):
        """Edit trading settings"""
        while True:
            print("\n" + "="*70)
            print("TRADING SETTINGS")
            print("="*70)

            current = self.settings['trading']
            print(f"\nTrading Mode: {current['mode'].upper()}")
            print(f"Max Position Size: ${current['max_position_size']}")
            print(f"Max Daily Trades: {current['max_daily_trades']}")
            print(f"Stop Loss: {current['stop_loss_percent']}%")
            print(f"Take Profit: {current['take_profit_percent']}%")
            print(f"Copy Trading: {'Enabled' if current['enable_copy_trading'] else 'Disabled'}")

            print("\nOptions:")
            print("  M. Toggle mode (paper/live)")
            print("  P. Set max position size")
            print("  T. Set max daily trades")
            print("  S. Set stop loss %")
            print("  R. Set take profit %")
            print("  C. Toggle copy trading")
            print("  B. Back to main menu")

            choice = input("\nSelect option: ").strip().upper()

            if choice == 'B':
                break
            elif choice == 'M':
                self.settings['trading']['mode'] = 'live' if current['mode'] == 'paper' else 'paper'
                print(f"✓ Trading mode set to: {self.settings['trading']['mode']}")
            elif choice == 'P':
                size = input("Enter max position size ($): ")
                try:
                    self.settings['trading']['max_position_size'] = float(size)
                    print(f"✓ Max position size set to ${size}")
                except:
                    print("⚠ Invalid input")
            elif choice == 'T':
                trades = input("Enter max daily trades: ")
                try:
                    self.settings['trading']['max_daily_trades'] = int(trades)
                    print(f"✓ Max daily trades set to {trades}")
                except:
                    print("⚠ Invalid input")
            elif choice == 'S':
                sl = input("Enter stop loss % (0-100): ")
                try:
                    self.settings['trading']['stop_loss_percent'] = float(sl)
                    print(f"✓ Stop loss set to {sl}%")
                except:
                    print("⚠ Invalid input")
            elif choice == 'R':
                tp = input("Enter take profit % (0-1000): ")
                try:
                    self.settings['trading']['take_profit_percent'] = float(tp)
                    print(f"✓ Take profit set to {tp}%")
                except:
                    print("⚠ Invalid input")
            elif choice == 'C':
                self.settings['trading']['enable_copy_trading'] = not current['enable_copy_trading']
                print(f"✓ Copy trading {'enabled' if self.settings['trading']['enable_copy_trading'] else 'disabled'}")

    def edit_risk_settings(self):
        """Edit risk management settings"""
        while True:
            print("\n" + "="*70)
            print("RISK MANAGEMENT SETTINGS")
            print("="*70)

            current = self.settings['risk']
            print(f"\nMax Drawdown: {current['max_drawdown']}%")
            print(f"Position Sizing: {current['position_sizing'].upper()}")
            print(f"Kelly Fraction: {current['kelly_fraction']}")
            print(f"VaR Confidence: {current['var_confidence']}")
            print(f"Max Correlation: {current['max_correlation']}")

            print("\nOptions:")
            print("  D. Set max drawdown %")
            print("  P. Set position sizing method")
            print("  K. Set Kelly fraction")
            print("  V. Set VaR confidence")
            print("  C. Set max correlation")
            print("  B. Back to main menu")

            choice = input("\nSelect option: ").strip().upper()

            if choice == 'B':
                break
            elif choice == 'D':
                dd = input("Enter max drawdown % (0-100): ")
                try:
                    self.settings['risk']['max_drawdown'] = float(dd)
                    print(f"✓ Max drawdown set to {dd}%")
                except:
                    print("⚠ Invalid input")
            elif choice == 'P':
                print("Position sizing methods: fixed, kelly, risk_parity")
                method = input("Enter method: ").strip().lower()
                if method in ['fixed', 'kelly', 'risk_parity']:
                    self.settings['risk']['position_sizing'] = method
                    print(f"✓ Position sizing set to: {method}")
            elif choice == 'K':
                kelly = input("Enter Kelly fraction (0.1-1.0): ")
                try:
                    self.settings['risk']['kelly_fraction'] = float(kelly)
                    print(f"✓ Kelly fraction set to {kelly}")
                except:
                    print("⚠ Invalid input")

    def edit_whale_settings(self):
        """Edit whale selection settings"""
        while True:
            print("\n" + "="*70)
            print("WHALE SELECTION SETTINGS")
            print("="*70)

            current = self.settings['whales']
            print(f"\nMin WQS Score: {current['min_wqs_score']}")
            print(f"Min Sharpe Ratio: {current['min_sharpe_ratio']}")
            print(f"Min Win Rate: {current['min_win_rate']}")
            print(f"Max Whales to Follow: {current['max_whales_to_follow']}")
            print(f"Update Frequency: {current['update_frequency']} seconds")

            print("\nOptions:")
            print("  W. Set min WQS score")
            print("  S. Set min Sharpe ratio")
            print("  R. Set min win rate")
            print("  M. Set max whales to follow")
            print("  U. Set update frequency")
            print("  B. Back to main menu")

            choice = input("\nSelect option: ").strip().upper()

            if choice == 'B':
                break
            elif choice == 'W':
                wqs = input("Enter min WQS score (0.0-1.0): ")
                try:
                    self.settings['whales']['min_wqs_score'] = float(wqs)
                    print(f"✓ Min WQS score set to {wqs}")
                except:
                    print("⚠ Invalid input")

    def export_settings(self):
        """Export settings to backup file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"config/settings_backup_{timestamp}.json"

        with open(backup_file, 'w') as f:
            json.dump(self.settings, f, indent=2)

        print(f"✓ Settings exported to: {backup_file}")

    def import_settings(self):
        """Import settings from file"""
        print("\nAvailable backup files:")

        import glob
        backups = glob.glob("config/settings_backup_*.json")

        if not backups:
            print("No backup files found")
            return

        for i, backup in enumerate(backups, 1):
            print(f"  {i}. {backup}")

        choice = input("\nSelect file number: ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(backups):
                with open(backups[idx], 'r') as f:
                    self.settings = json.load(f)
                self.save_settings()
                print(f"✓ Settings imported from: {backups[idx]}")
        except:
            print("⚠ Import failed")

    def run(self):
        """Main settings interface loop"""
        while True:
            self.display_header()
            self.display_menu()

            choice = input("\nSelect category (0-9): ").strip()

            if choice == '0':
                self.save_settings()
                print("\n✓ Settings saved successfully!")
                print("Exiting settings manager...")
                break
            elif choice == '1':
                self.edit_display_settings()
            elif choice == '2':
                self.edit_trading_settings()
            elif choice == '3':
                self.edit_risk_settings()
            elif choice == '4':
                self.edit_whale_settings()
            elif choice == '5':
                print("\n⚠ Alert settings configuration not yet implemented")
            elif choice == '6':
                print("\n⚠ API settings configuration not yet implemented")
            elif choice == '7':
                print("\n⚠ Database settings configuration not yet implemented")
            elif choice == '8':
                export = input("Export (E) or Import (I) settings? ").strip().upper()
                if export == 'E':
                    self.export_settings()
                elif export == 'I':
                    self.import_settings()
            elif choice == '9':
                confirm = input("Reset all settings to defaults? (yes/no): ").strip().lower()
                if confirm == 'yes':
                    self.settings = self.get_default_settings()
                    self.save_settings()
                    print("✓ Settings reset to defaults")
            else:
                print("⚠ Invalid selection")


def main():
    """Main entry point"""
    manager = SettingsManager()
    manager.run()


if __name__ == "__main__":
    main()
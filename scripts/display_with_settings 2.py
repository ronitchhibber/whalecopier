#!/usr/bin/env python3
"""
Display status using the format selected in settings
"""

import json
import os
import time
import sys
from datetime import datetime
from typing import Dict, Any


class SettingsBasedDisplay:
    """Display system status based on settings.json configuration"""

    def __init__(self):
        self.settings = self.load_settings()
        self.format_type = self.settings['display']['format']

    def load_settings(self) -> Dict[str, Any]:
        """Load settings from config file"""
        settings_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'config', 'settings.json'
        )

        if os.path.exists(settings_path):
            with open(settings_path, 'r') as f:
                return json.load(f)
        else:
            # Default settings if file not found
            return {
                'display': {
                    'format': 'mini',
                    'refresh_rate': 5,
                    'show_alerts': True,
                    'show_emojis': True,
                    'terminal_width': 80
                }
            }

    def get_mock_data(self) -> Dict[str, Any]:
        """Get mock data for display (replace with real data source)"""
        return {
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'p&l': '+$8,542',
            'win_rate': 73,
            'sharpe': 2.34,
            'trades': 1456,
            'whales': 25,
            'signals': 145,
            'volume': '$125K',
            'drawdown': 8,
            'var': 12,
            'exposure': '$45K',
            'last_trade': {
                'type': 'BUY',
                'market': 'BTC>100k',
                'amount': '$5K',
                'return': '+12.5%'
            },
            'systems': {
                'db': 'online',
                'api': 'online',
                'ws': 'online',
                'engine': 'online',
                'monitor': 'warning'
            }
        }

    def format_single_line(self, data: Dict[str, Any]) -> str:
        """Format: Single Line (1 line)"""
        emojis = '🟢' if self.settings['display']['show_emojis'] else '[OK]'
        return f"WHALE TRADER | P&L:{data['p&l']} Win:{data['win_rate']}% Sharpe:{data['sharpe']} | {emojis}"

    def format_status_bar(self, data: Dict[str, Any]) -> str:
        """Format: Status Bar (2 lines)"""
        lines = [
            f"WHALE TRADER │ P&L:{data['p&l']} Win:{data['win_rate']}%",
            "━" * 40
        ]
        return '\n'.join(lines)

    def format_metrics(self, data: Dict[str, Any]) -> str:
        """Format: Metrics (4 lines)"""
        lines = [
            f"P&L:{data['p&l']} │ Win:{data['win_rate']}% │ Sharpe:{data['sharpe']}",
            f"Whales:{data['whales']} │ Signals:{data['signals']}/d │ VaR:{data['var']}%",
            f"Volume:{data['volume']} │ Trades:{data['trades']}",
            f"Last: {data['last_trade']['type']} {data['last_trade']['market']} {data['last_trade']['return']}"
        ]
        return '\n'.join(lines)

    def format_ticker(self, data: Dict[str, Any]) -> str:
        """Format: Ticker (5 lines)"""
        emoji_status = '🟢' if self.settings['display']['show_emojis'] else 'OK'
        lines = [
            "══ WHALE TRADER ══",
            f"P&L:{data['p&l']} Win:{data['win_rate']}% Sharpe:{data['sharpe']}",
            f"Whales:{data['whales']} Signals:{data['signals']} Trades:{data['trades']}",
            f"Last: {data['last_trade']['type']} {data['last_trade']['market']} {data['last_trade']['amount']} {data['last_trade']['return']}",
            f"Systems: DB:{emoji_status} API:{emoji_status} WS:{emoji_status}"
        ]
        return '\n'.join(lines)

    def format_grid(self, data: Dict[str, Any]) -> str:
        """Format: Grid (8 lines)"""
        lines = [
            f"WHALE TRADER  {data['timestamp']}",
            "┌─────────────┬─────────────┬─────────────┐",
            f"│ P&L: {data['p&l']:>7} │ Win: {data['win_rate']:>3}%    │ Sharpe: {data['sharpe']:>4}│",
            f"│ DD: {data['drawdown']:>3}%     │ VaR: {data['var']:>3}%    │ Trades:{data['trades']:>5}│",
            f"│ Whales: {data['whales']:>3} │ Signals:{data['signals']:>3} │ Exp: {data['exposure']:>7}│",
            "└─────────────┴─────────────┴─────────────┘",
            f"Last: {data['last_trade']['type']} {data['last_trade']['market']} {data['last_trade']['amount']} {data['last_trade']['return']}",
            self._get_status_line(data['systems'])
        ]
        return '\n'.join(lines)

    def format_mini(self, data: Dict[str, Any]) -> str:
        """Format: Mini (10 lines)"""
        status = self._get_status_emojis(data['systems'])
        lines = [
            f"WHALE TRADER {data['timestamp']}",
            status,
            f"Trades:{data['trades']} Win:{data['win_rate']}% P&L:{data['p&l']}",
            f"Whales:{data['whales']} Signals:{data['signals']} Exposure:{data['exposure']}",
            f"Last: {data['last_trade']['type']} {data['last_trade']['market']} {data['last_trade']['amount']} {data['last_trade']['return']}",
            ""
        ]

        if self.settings['display']['show_alerts']:
            lines.append(f"⚠ Loss limit {data['drawdown']}.5%")

        lines.append("")
        lines.append("[Q]uit [R]efresh [S]ettings")

        return '\n'.join(lines)

    def format_compact(self, data: Dict[str, Any]) -> str:
        """Format: Compact (15 lines)"""
        status = self._get_status_emojis(data['systems'])
        lines = [
            f"POLYMARKET WHALE TRADER - {data['timestamp']}",
            "─" * 40,
            f"Status: {status}",
            "",
            "Performance:",
            f"  Trades:{data['trades']} WinRate:{data['win_rate']}% Vol:{data['volume']}",
            f"  Sharpe:{data['sharpe']} DD:{data['drawdown']}% VaR:{data['var']}%",
            "",
            "Recent:",
            f"  {data['last_trade']['type']:<4} {data['last_trade']['market']:<20} {data['last_trade']['amount']:<6} {data['last_trade']['return']:>7}",
            "  SELL 0x5678→Trump2024      $2.5K   -3.2%",
            ""
        ]

        if self.settings['display']['show_alerts']:
            lines.append(f"Alert: ⚠ Approaching daily loss limit")
            lines.append("")

        lines.append("[Q]uit [R]efresh [D]etails [S]ettings")

        return '\n'.join(lines)

    def _get_status_emojis(self, systems: Dict[str, str]) -> str:
        """Get status emojis or text based on settings"""
        if self.settings['display']['show_emojis']:
            emoji_map = {
                'online': '🟢',
                'warning': '🟡',
                'offline': '🔴'
            }
            return ' '.join([
                f"{name.upper()}:{emoji_map.get(status, '⚪')}"
                for name, status in systems.items()
            ])
        else:
            return ' '.join([
                f"{name.upper()}:[{'OK' if status == 'online' else 'WARN' if status == 'warning' else 'ERR'}]"
                for name, status in systems.items()
            ])

    def _get_status_line(self, systems: Dict[str, str]) -> str:
        """Get single line status"""
        if self.settings['display']['show_emojis']:
            emoji_map = {
                'online': '🟢',
                'warning': '🟡',
                'offline': '🔴'
            }
            statuses = [emoji_map.get(status, '⚪') for status in systems.values()]
            return "Status: " + " ".join(statuses)
        else:
            return "Status: " + " ".join([
                f"[{'OK' if s == 'online' else 'WARN' if s == 'warning' else 'ERR'}]"
                for s in systems.values()
            ])

    def display(self):
        """Display based on selected format"""
        format_methods = {
            'single': self.format_single_line,
            'status': self.format_status_bar,
            'metrics': self.format_metrics,
            'ticker': self.format_ticker,
            'grid': self.format_grid,
            'mini': self.format_mini,
            'compact': self.format_compact
        }

        # Get the format method
        format_method = format_methods.get(
            self.format_type,
            self.format_mini  # Default to mini
        )

        # Get data and display
        data = self.get_mock_data()
        output = format_method(data)

        # Clear screen for better display
        if self.format_type != 'single':
            os.system('clear' if os.name != 'nt' else 'cls')

        print(output)

        # Show format info
        format_info = self.settings['display'].get('format_options', {}).get(self.format_type, {})
        if format_info:
            print(f"\n[Format: {self.format_type} - {format_info.get('lines', 'N/A')} lines]")

    def run_continuous(self):
        """Run continuous display with refresh"""
        refresh_rate = self.settings['display'].get('refresh_rate', 5)

        try:
            while True:
                self.display()
                time.sleep(refresh_rate)

                # Reload settings periodically
                if time.time() % 30 < refresh_rate:
                    self.settings = self.load_settings()
                    self.format_type = self.settings['display']['format']

        except KeyboardInterrupt:
            print("\n\nDisplay stopped.")
            sys.exit(0)


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description='Display trading status based on settings')
    parser.add_argument(
        '--continuous',
        action='store_true',
        help='Run continuous display with auto-refresh'
    )
    parser.add_argument(
        '--format',
        choices=['single', 'status', 'metrics', 'ticker', 'grid', 'mini', 'compact'],
        help='Override format from settings (temporary)'
    )

    args = parser.parse_args()

    display = SettingsBasedDisplay()

    # Override format if specified
    if args.format:
        display.format_type = args.format

    if args.continuous:
        print(f"Starting continuous display (Format: {display.format_type})")
        print("Press Ctrl+C to stop\n")
        time.sleep(2)
        display.run_continuous()
    else:
        display.display()


if __name__ == '__main__':
    main()
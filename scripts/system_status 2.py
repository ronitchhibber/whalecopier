#!/usr/bin/env python3
"""
Compact System Status Display for Polymarket Whale Copy Trading
Shows all critical metrics in a compact, terminal-friendly format
"""

import asyncio
import psutil
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional
from tabulate import tabulate
from colorama import init, Fore, Back, Style

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Initialize colorama for cross-platform color support
init(autoreset=True)

class CompactStatusDisplay:
    """Compact status display for terminal"""

    def __init__(self):
        self.width = 80  # Compact width
        self.components = {
            "DB": "🔴",
            "API": "🔴",
            "WS": "🔴",
            "Engine": "🔴",
            "Monitor": "🔴"
        }

    def clear_screen(self):
        """Clear terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def get_color(self, status: str) -> str:
        """Get color based on status"""
        colors = {
            "🟢": Fore.GREEN,
            "🟡": Fore.YELLOW,
            "🔴": Fore.RED,
            "healthy": Fore.GREEN,
            "degraded": Fore.YELLOW,
            "unhealthy": Fore.RED
        }
        return colors.get(status, Fore.WHITE)

    def format_number(self, num: float, decimals: int = 2) -> str:
        """Format number compactly"""
        if abs(num) >= 1_000_000:
            return f"{num/1_000_000:.{decimals}f}M"
        elif abs(num) >= 1_000:
            return f"{num/1_000:.{decimals}f}K"
        else:
            return f"{num:.{decimals}f}"

    def display_header(self):
        """Display compact header"""
        print(f"{Fore.CYAN}{'─' * self.width}")
        print(f"{Fore.CYAN}{'POLYMARKET WHALE COPY TRADER':^{self.width}}")
        print(f"{Fore.CYAN}{datetime.now().strftime('%Y-%m-%d %H:%M:%S'):^{self.width}}")
        print(f"{Fore.CYAN}{'─' * self.width}")

    def display_components(self, data: Dict):
        """Display component status in single line"""
        status_line = " | ".join([
            f"{name}:{self.get_color(status)}{status}{Style.RESET_ALL}"
            for name, status in self.components.items()
        ])
        print(f"Components: {status_line}")

    def display_metrics_table(self, metrics: Dict):
        """Display metrics in compact table"""
        # Trading metrics
        trading_data = [
            ["Trades", self.format_number(metrics.get('total_trades', 0), 0),
             "Win Rate", f"{metrics.get('win_rate', 0)*100:.1f}%"],
            ["Volume", f"${self.format_number(metrics.get('volume', 0))}",
             "P&L", f"${self.format_number(metrics.get('pnl', 0))}"],
        ]

        # Risk metrics
        risk_data = [
            ["Exposure", f"${self.format_number(metrics.get('exposure', 0))}",
             "Drawdown", f"{metrics.get('drawdown', 0)*100:.1f}%"],
            ["VaR 95%", f"{metrics.get('var_95', 0)*100:.1f}%",
             "Sharpe", f"{metrics.get('sharpe', 0):.2f}"],
        ]

        # Whale metrics
        whale_data = [
            ["Whales", metrics.get('whale_count', 0),
             "Signals", metrics.get('signals', 0)],
            ["Avg WQS", f"{metrics.get('avg_wqs', 0):.3f}",
             "Active", metrics.get('active_positions', 0)],
        ]

        print(f"\n{Fore.YELLOW}Trading:{Style.RESET_ALL}")
        for row in trading_data:
            print(f"  {row[0]:<8} {row[1]:>10}  │  {row[2]:<8} {row[3]:>10}")

        print(f"\n{Fore.YELLOW}Risk:{Style.RESET_ALL}")
        for row in risk_data:
            print(f"  {row[0]:<8} {row[1]:>10}  │  {row[2]:<8} {row[3]:>10}")

        print(f"\n{Fore.YELLOW}Whales:{Style.RESET_ALL}")
        for row in whale_data:
            print(f"  {row[0]:<8} {row[1]:>10}  │  {row[2]:<8} {row[3]:>10}")

    def display_recent_trades(self, trades: List[Dict]):
        """Display recent trades compactly"""
        print(f"\n{Fore.YELLOW}Recent Trades:{Style.RESET_ALL}")

        if not trades:
            print("  No recent trades")
            return

        for i, trade in enumerate(trades[:3], 1):
            whale = trade.get('whale', 'Unknown')[:10]
            market = trade.get('market', 'Unknown')[:20]
            side = trade.get('side', 'BUY')
            size = self.format_number(trade.get('size', 0))
            pnl = trade.get('pnl', 0)

            pnl_color = Fore.GREEN if pnl >= 0 else Fore.RED
            side_color = Fore.GREEN if side == 'BUY' else Fore.RED

            print(f"  {i}. {whale:<10} {market:<20} {side_color}{side:>4}{Style.RESET_ALL} "
                  f"${size:>7} {pnl_color}{'↑' if pnl >= 0 else '↓'}{abs(pnl):.1f}%{Style.RESET_ALL}")

    def display_alerts(self, alerts: List[Dict]):
        """Display active alerts compactly"""
        print(f"\n{Fore.YELLOW}Alerts:{Style.RESET_ALL}")

        if not alerts:
            print(f"  {Fore.GREEN}✓ No active alerts{Style.RESET_ALL}")
            return

        for alert in alerts[:2]:
            severity = alert.get('severity', 'INFO')
            message = alert.get('message', 'Unknown alert')[:50]

            severity_colors = {
                'CRITICAL': Fore.RED + '⚠',
                'ERROR': Fore.RED + '✗',
                'WARNING': Fore.YELLOW + '!',
                'INFO': Fore.CYAN + 'ℹ'
            }

            icon = severity_colors.get(severity, 'ℹ')
            print(f"  {icon} {message}{Style.RESET_ALL}")

    def display_system_resources(self):
        """Display system resource usage"""
        cpu = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # Color code based on usage
        cpu_color = Fore.GREEN if cpu < 50 else Fore.YELLOW if cpu < 80 else Fore.RED
        mem_color = Fore.GREEN if memory.percent < 50 else Fore.YELLOW if memory.percent < 80 else Fore.RED
        disk_color = Fore.GREEN if disk.percent < 70 else Fore.YELLOW if disk.percent < 90 else Fore.RED

        print(f"\n{Fore.YELLOW}System:{Style.RESET_ALL}")
        print(f"  CPU: {cpu_color}{cpu:>5.1f}%{Style.RESET_ALL}  "
              f"MEM: {mem_color}{memory.percent:>5.1f}%{Style.RESET_ALL}  "
              f"DISK: {disk_color}{disk.percent:>5.1f}%{Style.RESET_ALL}")

    def display_footer(self):
        """Display footer"""
        print(f"{Fore.CYAN}{'─' * self.width}{Style.RESET_ALL}")
        print(f"  {Fore.GRAY}[Q]uit  [R]efresh  [D]etails  [H]elp{Style.RESET_ALL}")

    async def run(self):
        """Main display loop"""
        while True:
            try:
                self.clear_screen()

                # Mock data for demonstration
                mock_metrics = {
                    'total_trades': 1456,
                    'win_rate': 0.73,
                    'volume': 125000,
                    'pnl': 8456.23,
                    'exposure': 45000,
                    'drawdown': 0.08,
                    'var_95': 0.12,
                    'sharpe': 2.34,
                    'whale_count': 25,
                    'signals': 145,
                    'avg_wqs': 0.782,
                    'active_positions': 8
                }

                mock_trades = [
                    {'whale': '0x1234abcd', 'market': 'BTC>100k EOY', 'side': 'BUY', 'size': 5000, 'pnl': 12.5},
                    {'whale': '0x5678efgh', 'market': 'Trump Win 2024', 'side': 'SELL', 'size': 2500, 'pnl': -3.2},
                    {'whale': '0x9012ijkl', 'market': 'ETH Merge Success', 'side': 'BUY', 'size': 8000, 'pnl': 5.8}
                ]

                mock_alerts = [
                    {'severity': 'WARNING', 'message': 'Approaching daily loss limit (8.5%)'},
                    {'severity': 'INFO', 'message': 'New whale detected with 0.85 WQS'}
                ]

                # Update component status randomly for demo
                import random
                statuses = ["🟢", "🟡", "🔴"]
                for comp in self.components:
                    if random.random() > 0.3:
                        self.components[comp] = "🟢"
                    elif random.random() > 0.5:
                        self.components[comp] = "🟡"

                # Display all sections
                self.display_header()
                self.display_components({})
                self.display_metrics_table(mock_metrics)
                self.display_recent_trades(mock_trades)
                self.display_alerts(mock_alerts)
                self.display_system_resources()
                self.display_footer()

                await asyncio.sleep(5)  # Refresh every 5 seconds

            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}Shutting down...{Style.RESET_ALL}")
                break
            except Exception as e:
                print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
                await asyncio.sleep(5)


def create_compact_architecture():
    """Create compact ASCII architecture diagram"""
    diagram = """
    ┌─────────────────────────────────────────────────────────┐
    │                   WHALE COPY TRADER                      │
    ├─────────────────────────────────────────────────────────┤
    │  [WebSocket] ──→ [Executor] ──→ [Risk Mgr] ──→ [Trade]  │
    │       ↓              ↓              ↓            ↓       │
    │  [Graph API]    [WQS Score]    [Position]    [Monitor]   │
    │       ↓              ↓            Size           ↓       │
    │  [Database] ←── [Backtest] ←── [Paper] ←── [Analytics]   │
    └─────────────────────────────────────────────────────────┘

    Components:
    • WebSocket: Real-time whale trade streaming
    • Graph API: Historical data fetching
    • Executor:  Signal processing pipeline
    • WQS Score: 5-factor whale quality scoring
    • Risk Mgr:  Cornish-Fisher VaR & limits
    • Monitor:   Real-time metrics & alerts

    Metrics:
    ┌──────────┬────────┬──────────┬────────┐
    │ Sharpe   │ 2.34   │ Win Rate │ 73%    │
    │ Drawdown │ 8%     │ VaR 95%  │ 12%    │
    │ P&L      │ +$8.5K │ Signals  │ 145/d  │
    └──────────┴────────┴──────────┴────────┘
    """
    return diagram


async def main():
    """Main entry point"""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--diagram':
        # Show architecture diagram
        print(create_compact_architecture())
    else:
        # Run status display
        display = CompactStatusDisplay()
        await display.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
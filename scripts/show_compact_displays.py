#!/usr/bin/env python3
"""
Demonstration of all compact display formats
"""

from datetime import datetime

def show_ultra_compact():
    """Show ultra-compact display (15 lines)"""
    print("\n" + "="*60)
    print("ULTRA-COMPACT MODE (15 lines):")
    print("="*60)

    print(f"POLYMARKET WHALE TRADER - {datetime.now().strftime('%H:%M:%S')}")
    print('─' * 60)
    print(f"Status: DB:🟢 API:🟢 WS:🟢 Engine:🟢 Monitor:🟡")
    print(f"\nPerformance:")
    print(f"  Trades:1456 WinRate:73% Vol:$125K P&L:+$8.5K")
    print(f"  Sharpe:2.34 DD:8% VaR:12% Whales:25 Signals:145/d")
    print(f"\nRecent:")
    print(f"  BUY  0x1234→BTC>100k    $5K  +12.5%")
    print(f"  SELL 0x5678→Trump2024   $2.5K -3.2%")
    print(f"\nAlert: ⚠ Approaching daily loss limit (8.5%)")
    print(f"\n[Q]uit [R]efresh [D]etails")


def show_mini():
    """Show mini display (10 lines)"""
    print("\n" + "="*60)
    print("MINI MODE (10 lines):")
    print("="*60)

    print(f"WHALE TRADER {datetime.now().strftime('%H:%M:%S')}")
    print(f"DB:🟢 API:🟢 WS:🟢 Engine:🟢 Monitor:🟡")
    print(f"Trades:1456 Win:73% P&L:+$8.5K Sharpe:2.34")
    print(f"Whales:25 Signals:145 Exposure:$45K DD:8%")
    print(f"Last: BUY BTC>100k $5K +12.5%")
    print(f"⚠ Loss limit 8.5%")
    print(f"[Q]uit [R]efresh")


def show_single_line():
    """Show single line display"""
    print("\n" + "="*60)
    print("SINGLE LINE MODE (1 line scrolling):")
    print("="*60)

    # Show 3 example states
    print("\nState 1:")
    print("WHALE TRADER | P&L:+$8.5K Win:73% Sharpe:2.34 | Systems:🟢")

    print("\nState 2:")
    print("WHALE TRADER | Whales:25 Signals:145/d DD:8% | Systems:🟢")

    print("\nState 3:")
    print("WHALE TRADER | VaR:12% Trades:1456 P&L:+$8.5K | Systems:🟢")


def show_ticker_style():
    """Show ticker-style compact display (5 lines)"""
    print("\n" + "="*60)
    print("TICKER STYLE (5 lines):")
    print("="*60)

    print(f"══ WHALE TRADER ══")
    print(f"P&L:+$8.5K Win:73% Sharpe:2.34 DD:8%")
    print(f"Whales:25 Signals:145 Trades:1456")
    print(f"Last: BUY BTC>100k $5K +12.5%")
    print(f"Systems: DB:🟢 API:🟢 WS:🟢 Engine:🟢")


def show_dashboard_grid():
    """Show grid-style layout (8 lines)"""
    print("\n" + "="*60)
    print("GRID LAYOUT (8 lines):")
    print("="*60)

    print(f"WHALE TRADER  {datetime.now().strftime('%H:%M:%S')}")
    print("┌─────────────┬─────────────┬─────────────┐")
    print("│ P&L: +$8.5K │ Win: 73%    │ Sharpe: 2.34│")
    print("│ DD: 8%      │ VaR: 12%    │ Trades: 1456│")
    print("│ Whales: 25  │ Signals:145 │ Exp: $45K   │")
    print("└─────────────┴─────────────┴─────────────┘")
    print("Last: BUY BTC>100k $5K +12.5%")
    print("Status: 🟢 🟢 🟢 🟢 🟡")


def main():
    """Show all display formats"""
    print(f"\n{'='*60}")
    print(f"COMPACT DISPLAY FORMATS FOR POLYMARKET WHALE TRADER")
    print(f"{'='*60}")

    show_single_line()
    show_ticker_style()
    show_dashboard_grid()
    show_mini()
    show_ultra_compact()

    print(f"\nAll display formats shown above.")
    print(f"Choose the one that fits your screen best!\n")


if __name__ == "__main__":
    main()
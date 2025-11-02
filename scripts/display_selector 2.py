#!/usr/bin/env python3
"""
Display Format Selector for Polymarket Whale Copy Trader
Allows users to preview and select their preferred display format
"""

import json
import os
from datetime import datetime
from typing import Dict, Optional

class DisplaySelector:
    """Interactive display format selector"""

    def __init__(self):
        self.settings_file = "config/display_settings.json"
        self.current_selection = self.load_settings()

    def load_settings(self) -> str:
        """Load saved display preference"""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    return settings.get('display_format', 'mini')
            except:
                pass
        return 'mini'

    def save_settings(self, format_choice: str):
        """Save display preference"""
        os.makedirs('config', exist_ok=True)
        settings = {'display_format': format_choice}
        with open(self.settings_file, 'w') as f:
            json.dump(settings, f, indent=2)
        print(f"\n✓ Settings saved! Default display is now: {format_choice}")

    def show_single_line(self):
        """Single line display (1 line)"""
        print("\n" + "="*70)
        print("FORMAT 1: SINGLE LINE (1 line) - Ultra Minimal")
        print("="*70)
        print("WHALE TRADER | P&L:+$8.5K Win:73% Sharpe:2.34 | Systems:🟢")
        print("\nThis scrolls through metrics: P&L→Whales→VaR→Trades (every 2 sec)")

    def show_ticker(self):
        """Ticker style display (5 lines)"""
        print("\n" + "="*70)
        print("FORMAT 2: TICKER (5 lines) - Essential Info")
        print("="*70)
        print("══ WHALE TRADER ══")
        print("P&L:+$8.5K Win:73% Sharpe:2.34 DD:8%")
        print("Whales:25 Signals:145 Trades:1456")
        print("Last: BUY BTC>100k $5K +12.5%")
        print("Systems: DB:🟢 API:🟢 WS:🟢 Engine:🟢")

    def show_grid(self):
        """Grid layout display (8 lines)"""
        print("\n" + "="*70)
        print("FORMAT 3: GRID (8 lines) - Organized Metrics")
        print("="*70)
        print(f"WHALE TRADER  {datetime.now().strftime('%H:%M:%S')}")
        print("┌─────────────┬─────────────┬─────────────┐")
        print("│ P&L: +$8.5K │ Win: 73%    │ Sharpe: 2.34│")
        print("│ DD: 8%      │ VaR: 12%    │ Trades: 1456│")
        print("│ Whales: 25  │ Signals:145 │ Exp: $45K   │")
        print("└─────────────┴─────────────┴─────────────┘")
        print("Last: BUY BTC>100k $5K +12.5%")
        print("Status: 🟢 🟢 🟢 🟢 🟡")

    def show_mini(self):
        """Mini display (10 lines)"""
        print("\n" + "="*70)
        print("FORMAT 4: MINI (10 lines) - Balanced View")
        print("="*70)
        print(f"WHALE TRADER {datetime.now().strftime('%H:%M:%S')}")
        print("DB:🟢 API:🟢 WS:🟢 Engine:🟢 Monitor:🟡")
        print("Trades:1456 Win:73% P&L:+$8.5K Sharpe:2.34")
        print("Whales:25 Signals:145 Exposure:$45K DD:8%")
        print("Last: BUY BTC>100k $5K +12.5%")
        print("⚠ Loss limit 8.5%")
        print("[Q]uit [R]efresh")

    def show_compact(self):
        """Compact display (15 lines)"""
        print("\n" + "="*70)
        print("FORMAT 5: COMPACT (15 lines) - Full Status")
        print("="*70)
        print(f"POLYMARKET WHALE TRADER - {datetime.now().strftime('%H:%M:%S')}")
        print("─" * 60)
        print("Status: DB:🟢 API:🟢 WS:🟢 Engine:🟢 Monitor:🟡")
        print("\nPerformance:")
        print("  Trades:1456 WinRate:73% Vol:$125K P&L:+$8.5K")
        print("  Sharpe:2.34 DD:8% VaR:12% Whales:25 Signals:145/d")
        print("\nRecent:")
        print("  BUY  0x1234→BTC>100k    $5K  +12.5%")
        print("  SELL 0x5678→Trump2024   $2.5K -3.2%")
        print("\nAlert: ⚠ Approaching daily loss limit (8.5%)")
        print("\n[Q]uit [R]efresh [D]etails")

    def show_status_bar(self):
        """Status bar display (2 lines)"""
        print("\n" + "="*70)
        print("FORMAT 6: STATUS BAR (2 lines) - Minimal Status")
        print("="*70)
        print("WHALE TRADER │ P&L:+$8.5K Win:73% │ ⚠ Loss limit 8.5%")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    def show_metrics_only(self):
        """Metrics only display (4 lines)"""
        print("\n" + "="*70)
        print("FORMAT 7: METRICS (4 lines) - Key Numbers Only")
        print("="*70)
        print("P&L:+$8.5K │ Win:73% │ Sharpe:2.34 │ DD:8%")
        print("Whales:25  │ Signals:145/d │ VaR:12%")
        print("Volume:$125K │ Trades:1456 │ Exp:$45K")
        print("Last: BUY BTC>100k +12.5% │ Systems:🟢")

    def show_comparison_table(self):
        """Show comparison of all formats"""
        print("\n" + "="*70)
        print("DISPLAY FORMAT COMPARISON")
        print("="*70)
        print("\n┌────────────┬───────┬──────────────────────────────────┐")
        print("│ Format     │ Lines │ Best For                         │")
        print("├────────────┼───────┼──────────────────────────────────┤")
        print("│ Single     │   1   │ Terminal status bar, tmux pane  │")
        print("│ Status Bar │   2   │ Small terminal window            │")
        print("│ Metrics    │   4   │ Quick glance monitoring          │")
        print("│ Ticker     │   5   │ Sidebar widget                   │")
        print("│ Grid       │   8   │ Clean organized view             │")
        print("│ Mini       │  10   │ Balanced information             │")
        print("│ Compact    │  15   │ Full monitoring dashboard        │")
        print("└────────────┴───────┴──────────────────────────────────┘")

    def interactive_menu(self):
        """Interactive selection menu"""
        while True:
            print("\n" + "="*70)
            print("POLYMARKET WHALE TRADER - DISPLAY FORMAT SELECTOR")
            print("="*70)
            print(f"\nCurrent selection: {self.current_selection.upper()}")
            print("\nAvailable formats:")
            print("  1. Single Line  (1 line)  - Ultra minimal")
            print("  2. Status Bar   (2 lines) - Minimal status")
            print("  3. Metrics      (4 lines) - Key numbers only")
            print("  4. Ticker       (5 lines) - Essential info")
            print("  5. Grid         (8 lines) - Organized view")
            print("  6. Mini        (10 lines) - Balanced [DEFAULT]")
            print("  7. Compact     (15 lines) - Full status")
            print("\nOptions:")
            print("  A. Show all formats")
            print("  C. Compare formats")
            print("  S. Save current selection")
            print("  Q. Quit")

            choice = input("\nSelect format to preview (1-7) or option (A/C/S/Q): ").strip().upper()

            if choice == 'Q':
                print("\nExiting display selector...")
                break
            elif choice == 'A':
                self.show_all_formats()
            elif choice == 'C':
                self.show_comparison_table()
            elif choice == 'S':
                self.save_settings(self.current_selection)
            elif choice == '1':
                self.show_single_line()
                self.current_selection = 'single'
            elif choice == '2':
                self.show_status_bar()
                self.current_selection = 'status_bar'
            elif choice == '3':
                self.show_metrics_only()
                self.current_selection = 'metrics'
            elif choice == '4':
                self.show_ticker()
                self.current_selection = 'ticker'
            elif choice == '5':
                self.show_grid()
                self.current_selection = 'grid'
            elif choice == '6':
                self.show_mini()
                self.current_selection = 'mini'
            elif choice == '7':
                self.show_compact()
                self.current_selection = 'compact'
            else:
                print("\n⚠ Invalid choice. Please select 1-7 or A/C/S/Q")

    def show_all_formats(self):
        """Display all formats for comparison"""
        print("\n" + "="*70)
        print("ALL DISPLAY FORMATS - SIDE BY SIDE COMPARISON")
        print("="*70)

        self.show_single_line()
        self.show_status_bar()
        self.show_metrics_only()
        self.show_ticker()
        self.show_grid()
        self.show_mini()
        self.show_compact()

        print("\n" + "="*70)
        print("End of format examples. Press Enter to continue...")
        input()


def main():
    """Main entry point"""
    import sys

    selector = DisplaySelector()

    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()

        # Quick preview mode
        if arg == 'single':
            selector.show_single_line()
        elif arg == 'status':
            selector.show_status_bar()
        elif arg == 'metrics':
            selector.show_metrics_only()
        elif arg == 'ticker':
            selector.show_ticker()
        elif arg == 'grid':
            selector.show_grid()
        elif arg == 'mini':
            selector.show_mini()
        elif arg == 'compact':
            selector.show_compact()
        elif arg == 'all':
            selector.show_all_formats()
        elif arg == 'compare':
            selector.show_comparison_table()
        else:
            print(f"Unknown format: {arg}")
            print("Available: single, status, metrics, ticker, grid, mini, compact, all, compare")
    else:
        # Interactive mode
        selector.interactive_menu()


if __name__ == "__main__":
    main()
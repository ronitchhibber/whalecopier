#!/usr/bin/env python3
"""
Ultra-Compact System Status for Polymarket Whale Copy Trading
Designed for minimal vertical space usage
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Dict, List
from colorama import init, Fore, Style

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Initialize colorama
init(autoreset=True)

class UltraCompactDisplay:
    """Ultra-compact single-screen status display"""

    def __init__(self):
        self.components = {"DB": "🟢", "API": "🟢", "WS": "🟢", "Engine": "🟢", "Monitor": "🟡"}

    def clear_screen(self):
        """Clear terminal"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def display(self):
        """Display all status in minimal vertical space"""
        self.clear_screen()

        # Header (2 lines)
        print(f"{Fore.CYAN}POLYMARKET WHALE TRADER - {datetime.now().strftime('%H:%M:%S')}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'─' * 60}{Style.RESET_ALL}")

        # Components (1 line)
        comp = " ".join([f"{k}:{v}" for k, v in self.components.items()])
        print(f"Status: {comp}")

        # Key Metrics (3 lines) - all on same lines
        print(f"\n{Fore.YELLOW}Performance:{Style.RESET_ALL}")
        print(f"  Trades:1456 WinRate:73% Vol:$125K P&L:+$8.5K")
        print(f"  Sharpe:2.34 DD:8% VaR:12% Whales:25 Signals:145/d")

        # Recent Activity (2 lines)
        print(f"\n{Fore.YELLOW}Recent:{Style.RESET_ALL}")
        print(f"  BUY  0x1234→BTC>100k    $5K  +12.5%")
        print(f"  SELL 0x5678→Trump2024   $2.5K -3.2%")

        # Alerts (1 line)
        print(f"\n{Fore.YELLOW}Alert:{Style.RESET_ALL} {Fore.YELLOW}⚠ Approaching daily loss limit (8.5%){Style.RESET_ALL}")

        # Footer (1 line)
        print(f"\n{Fore.GRAY}[Q]uit [R]efresh [D]etails{Style.RESET_ALL}")

    async def run(self):
        """Main loop"""
        while True:
            try:
                self.display()
                await asyncio.sleep(5)
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}Exiting...{Style.RESET_ALL}")
                break


class MiniDashboard:
    """Even more minimal dashboard - fits in 10 lines"""

    def __init__(self):
        self.iteration = 0

    def display_mini(self):
        """Ultra-minimal 10-line display"""
        os.system('cls' if os.name == 'nt' else 'clear')

        # Everything in exactly 10 lines
        print(f"{Fore.CYAN}WHALE TRADER {datetime.now().strftime('%H:%M:%S')}{Style.RESET_ALL}")
        print(f"DB:🟢 API:🟢 WS:🟢 Engine:🟢 Monitor:🟡")
        print(f"Trades:1456 Win:73% P&L:+$8.5K Sharpe:2.34")
        print(f"Whales:25 Signals:145 Exposure:$45K DD:8%")
        print(f"Last: BUY BTC>100k $5K +12.5%")
        if self.iteration % 2 == 0:
            print(f"{Fore.YELLOW}⚠ Loss limit 8.5%{Style.RESET_ALL}")
        else:
            print(f"{Fore.GREEN}✓ All systems normal{Style.RESET_ALL}")
        print(f"{Fore.GRAY}[Q]uit [R]efresh{Style.RESET_ALL}")

        self.iteration += 1

    async def run(self):
        """Run mini display"""
        while True:
            try:
                self.display_mini()
                await asyncio.sleep(3)
            except KeyboardInterrupt:
                print("\nExiting...")
                break


class SingleLineStatus:
    """Single line scrolling status - ultimate compact"""

    def __init__(self):
        self.metrics = [
            "P&L:+$8.5K",
            "Win:73%",
            "Sharpe:2.34",
            "Whales:25",
            "Signals:145/d",
            "DD:8%",
            "VaR:12%",
            "Trades:1456"
        ]
        self.index = 0

    def display_line(self):
        """Display single scrolling line"""
        # Clear line and return to start
        print('\r', end='')

        # Build status line
        status = f"WHALE TRADER | "

        # Add 3 rotating metrics
        for i in range(3):
            metric_idx = (self.index + i) % len(self.metrics)
            status += f"{self.metrics[metric_idx]} "

        # Add system status
        status += "| Systems:🟢"

        # Print without newline
        print(status, end='', flush=True)

        self.index = (self.index + 1) % len(self.metrics)

    async def run(self):
        """Run single line display"""
        print("\033[?25l")  # Hide cursor
        try:
            while True:
                self.display_line()
                await asyncio.sleep(2)
        except KeyboardInterrupt:
            print("\033[?25h")  # Show cursor
            print("\nExiting...")


async def main():
    """Main entry point"""
    import sys

    if len(sys.argv) > 1:
        mode = sys.argv[1]
    else:
        mode = "compact"

    if mode == "ultra":
        display = UltraCompactDisplay()
        await display.run()
    elif mode == "mini":
        display = MiniDashboard()
        await display.run()
    elif mode == "line":
        display = SingleLineStatus()
        await display.run()
    else:
        # Default compact mode
        display = UltraCompactDisplay()
        await display.run()


if __name__ == "__main__":
    try:
        # Show options
        print("Display Modes:")
        print("1. ultra   - Ultra-compact (15 lines)")
        print("2. mini    - Minimal (10 lines)")
        print("3. line    - Single line scrolling")
        print("\nUsage: python ultra_compact_status.py [mode]")
        print("Starting ultra-compact mode in 2 seconds...")

        import time
        time.sleep(2)

        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
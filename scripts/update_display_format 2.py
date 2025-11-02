#!/usr/bin/env python3
"""
Update display format in settings
"""

import json
import os
import sys
from typing import Dict, Any


def load_settings() -> Dict[str, Any]:
    """Load current settings"""
    settings_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'config', 'settings.json'
    )

    if os.path.exists(settings_path):
        with open(settings_path, 'r') as f:
            return json.load(f)
    else:
        print(f"Error: Settings file not found at {settings_path}")
        sys.exit(1)


def save_settings(settings: Dict[str, Any]):
    """Save settings to file"""
    settings_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'config', 'settings.json'
    )

    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=2)


def show_formats(settings: Dict[str, Any]):
    """Show all available formats"""
    current = settings['display']['format']
    formats = settings['display']['format_options']

    print("\n" + "=" * 60)
    print("DISPLAY FORMAT OPTIONS")
    print("=" * 60)

    for fmt_id, fmt_info in formats.items():
        marker = "→" if fmt_id == current else " "
        print(f"{marker} {fmt_id:10} ({fmt_info['lines']:2} lines) - {fmt_info['description']}")

    print("=" * 60)
    print(f"\nCurrent format: {current}")


def show_preview(format_type: str):
    """Show preview of a specific format"""
    previews = {
        'single': """
WHALE TRADER | P&L:+$8.5K Win:73% Sharpe:2.34 | 🟢
        """,
        'status': """
WHALE TRADER │ P&L:+$8.5K Win:73%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        """,
        'metrics': """
P&L:+$8.5K │ Win:73% │ Sharpe:2.34
Whales:25 │ Signals:145/d │ VaR:12%
Volume:$125K │ Trades:1456
Last: BUY BTC>100k +12.5%
        """,
        'ticker': """
══ WHALE TRADER ══
P&L:+$8.5K Win:73% Sharpe:2.34
Whales:25 Signals:145 Trades:1456
Last: BUY BTC>100k $5K +12.5%
Systems: DB:🟢 API:🟢 WS:🟢
        """,
        'grid': """
WHALE TRADER  22:30:45
┌─────────────┬─────────────┬─────────────┐
│ P&L: +$8.5K │ Win: 73%    │ Sharpe: 2.34│
│ DD: 8%      │ VaR: 12%    │ Trades: 1456│
│ Whales: 25  │ Signals:145 │ Exp: $45K   │
└─────────────┴─────────────┴─────────────┘
Last: BUY BTC>100k $5K +12.5%
Status: 🟢 🟢 🟢 🟢 🟡
        """,
        'mini': """
WHALE TRADER 22:30:45
DB:🟢 API:🟢 WS:🟢 Engine:🟢 Monitor:🟡
Trades:1456 Win:73% P&L:+$8.5K
Whales:25 Signals:145 Exposure:$45K
Last: BUY BTC>100k $5K +12.5%

⚠ Loss limit 8.5%

[Q]uit [R]efresh [S]ettings
        """,
        'compact': """
POLYMARKET WHALE TRADER - 22:30:45
────────────────────────────────────
Status: DB:🟢 API:🟢 WS:🟢 Engine:🟢

Performance:
  Trades:1456 WinRate:73% Vol:$125K
  Sharpe:2.34 DD:8% VaR:12%

Recent:
  BUY  0x1234→BTC>100k    $5K  +12.5%
  SELL 0x5678→Trump2024   $2.5K -3.2%

Alert: ⚠ Approaching daily loss limit

[Q]uit [R]efresh [D]etails [S]ettings
        """
    }

    if format_type in previews:
        print(f"\n{format_type.upper()} FORMAT PREVIEW:")
        print("-" * 40)
        print(previews[format_type])
        print("-" * 40)
    else:
        print(f"No preview available for format: {format_type}")


def update_format(settings: Dict[str, Any], new_format: str):
    """Update the display format"""
    available_formats = list(settings['display']['format_options'].keys())

    if new_format not in available_formats:
        print(f"Error: '{new_format}' is not a valid format")
        print(f"Available formats: {', '.join(available_formats)}")
        return False

    old_format = settings['display']['format']
    settings['display']['format'] = new_format

    save_settings(settings)

    print(f"\n✅ Display format updated: {old_format} → {new_format}")

    # Show preview of new format
    show_preview(new_format)

    return True


def interactive_mode():
    """Interactive format selection"""
    settings = load_settings()

    while True:
        print("\n" + "=" * 60)
        print("DISPLAY FORMAT SELECTOR")
        print("=" * 60)

        show_formats(settings)

        print("\nOptions:")
        print("  1-7: Select format by number")
        print("  p:   Preview all formats")
        print("  t:   Test current format")
        print("  q:   Quit")

        choice = input("\nYour choice: ").strip().lower()

        if choice == 'q':
            break
        elif choice == 'p':
            for fmt in settings['display']['format_options'].keys():
                show_preview(fmt)
                input("\nPress Enter for next format...")
        elif choice == 't':
            os.system('python3 scripts/display_with_settings.py')
            input("\nPress Enter to continue...")
        elif choice.isdigit():
            formats = list(settings['display']['format_options'].keys())
            idx = int(choice) - 1
            if 0 <= idx < len(formats):
                if update_format(settings, formats[idx]):
                    settings = load_settings()  # Reload settings
            else:
                print("Invalid selection")
        else:
            # Try as format name
            if update_format(settings, choice):
                settings = load_settings()


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description='Update display format in settings')
    parser.add_argument(
        'format',
        nargs='?',
        choices=['single', 'status', 'metrics', 'ticker', 'grid', 'mini', 'compact'],
        help='New display format to set'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available formats'
    )
    parser.add_argument(
        '--preview',
        metavar='FORMAT',
        help='Preview a specific format'
    )
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Interactive format selection'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test current format'
    )

    args = parser.parse_args()

    settings = load_settings()

    if args.interactive:
        interactive_mode()
    elif args.list:
        show_formats(settings)
    elif args.preview:
        show_preview(args.preview)
    elif args.test:
        os.system('python3 scripts/display_with_settings.py')
    elif args.format:
        update_format(settings, args.format)
    else:
        # No arguments - show interactive mode
        interactive_mode()


if __name__ == '__main__':
    main()
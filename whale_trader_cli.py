#!/usr/bin/env python3
"""
Whale Trader CLI - Master Control Script
One interface to control all system components.

Usage:
    python3 whale_trader_cli.py [command] [options]

Commands:
    discover        Run whale discovery
    analyze         Analyze discovered whales
    backtest        Run backtest
    dashboard       Launch dashboard
    monitor         Monitor system health
    export          Export whale data
    calculate-wqs   Calculate WQS for specific whale
    test            Test production modules

Examples:
    python3 whale_trader_cli.py discover --trades 100000
    python3 whale_trader_cli.py analyze --export-csv
    python3 whale_trader_cli.py backtest --start 2024-01-01
    python3 whale_trader_cli.py dashboard
"""

import sys
import os
import argparse
import subprocess
from datetime import datetime, timedelta


class Colors:
    """Terminal colors."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text):
    """Print colored header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}")
    print(f" {text}")
    print(f"{'='*80}{Colors.ENDC}\n")


def print_success(text):
    """Print success message."""
    print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")


def print_error(text):
    """Print error message."""
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")


def print_info(text):
    """Print info message."""
    print(f"{Colors.OKCYAN}ℹ️  {text}{Colors.ENDC}")


def print_warning(text):
    """Print warning message."""
    print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")


def cmd_discover(args):
    """Run whale discovery."""
    print_header("🐋 WHALE DISCOVERY")

    if args.trades == 100000:
        print_info("Running 100K trade discovery (~30 minutes)")
        script = "scripts/massive_whale_discovery.py"
    else:
        print_info(f"Running {args.trades:,} trade discovery")
        script = "scripts/massive_whale_discovery_1M.py"

    if args.background:
        print_info("Running in background...")
        cmd = f"nohup python3 {script} > whale_discovery.log 2>&1 &"
        subprocess.run(cmd, shell=True)
        print_success("Discovery started in background")
        print_info("Monitor progress: tail -f whale_discovery.log")
    else:
        subprocess.run(["python3", script])


def cmd_analyze(args):
    """Analyze discovered whales."""
    print_header("📊 WHALE ANALYSIS")

    if not args.input:
        print_error("No input file specified")
        print_info("Usage: whale_trader_cli.py analyze --input whale_data.json")
        return

    cmd = ["python3", "scripts/analyze_all_whales.py", "--input", args.input, "--top", str(args.top)]

    if args.export_csv:
        cmd.append("--export-csv")
    if args.export_json:
        cmd.append("--export-json")

    subprocess.run(cmd)


def cmd_backtest(args):
    """Run backtest."""
    print_header("🧪 BACKTESTING")

    cmd = [
        "python3", "scripts/run_whale_backtest.py",
        "--start", args.start,
        "--end", args.end,
        "--capital", str(args.capital),
        "--min-wqs", str(args.min_wqs)
    ]

    if args.no_pipeline:
        cmd.append("--no-pipeline")
    if args.no_adaptive_sizing:
        cmd.append("--no-adaptive-sizing")

    subprocess.run(cmd)


def cmd_dashboard(args):
    """Launch dashboard."""
    print_header("📊 DASHBOARD")

    if args.type == "streamlit":
        print_info("Launching Streamlit dashboard on http://localhost:8501")
        subprocess.run(["./run_dashboard.sh"])
    elif args.type == "react":
        print_info("Launching React dashboard on http://localhost:5174")
        subprocess.run(["npm", "run", "dev"], cwd="frontend")
    else:
        print_error(f"Unknown dashboard type: {args.type}")


def cmd_monitor(args):
    """Monitor system health."""
    print_header("🔍 SYSTEM MONITOR")

    # Check database
    print("Checking database...")
    result = subprocess.run(
        ["python3", "-c", "from api.db import get_db_session; next(get_db_session())"],
        capture_output=True
    )

    if result.returncode == 0:
        print_success("Database: Connected")
    else:
        print_error("Database: Not available")

    # Check API
    print("\nChecking API...")
    result = subprocess.run(
        ["curl", "-s", "http://localhost:8000/health"],
        capture_output=True
    )

    if result.returncode == 0:
        print_success("API: Running on port 8000")
    else:
        print_warning("API: Not running")

    # Check frontend
    print("\nChecking frontend...")
    result = subprocess.run(
        ["curl", "-s", "http://localhost:5174"],
        capture_output=True
    )

    if result.returncode == 0:
        print_success("Frontend: Running on port 5174")
    else:
        print_warning("Frontend: Not running")

    # Check running processes
    print("\n" + "="*80)
    print("Background Processes:")
    print("="*80)
    subprocess.run(["ps", "aux"], stdout=subprocess.PIPE)


def cmd_export(args):
    """Export whale data."""
    print_header("📤 EXPORT WHALE DATA")

    # TODO: Implement actual export from database
    print_info(f"Exporting to {args.output}")
    print_info(f"Format: {args.format}")
    print_info(f"Min WQS: {args.min_wqs}")

    print_warning("Export functionality coming soon!")


def cmd_calculate_wqs(args):
    """Calculate WQS for specific whale."""
    print_header("🎯 CALCULATE WQS")

    print_info(f"Whale: {args.address}")

    # TODO: Implement WQS calculation from database/API
    print_warning("WQS calculation functionality coming soon!")


def cmd_test(args):
    """Test production modules."""
    print_header("🧪 TESTING PRODUCTION MODULES")

    modules = []

    if args.all or args.wqs:
        modules.append(("Enhanced WQS", "libs/analytics/enhanced_wqs.py"))
    if args.all or args.bayesian:
        modules.append(("Bayesian Scoring", "libs/analytics/bayesian_scoring.py"))
    if args.all or args.consistency:
        modules.append(("Consistency Metrics", "libs/analytics/consistency.py"))
    if args.all or args.pipeline:
        modules.append(("Signal Pipeline", "libs/trading/signal_pipeline.py"))
    if args.all or args.sizing:
        modules.append(("Position Sizing", "libs/trading/position_sizing.py"))
    if args.all or args.risk:
        modules.append(("Risk Management", "libs/trading/risk_management.py"))
    if args.all or args.attribution:
        modules.append(("Performance Attribution", "libs/analytics/performance_attribution.py"))
    if args.all or args.backtest:
        modules.append(("Backtest Engine", "libs/backtesting/backtest_engine.py"))

    if not modules:
        modules = [
            ("Enhanced WQS", "libs/analytics/enhanced_wqs.py"),
            ("Signal Pipeline", "libs/trading/signal_pipeline.py"),
            ("Position Sizing", "libs/trading/position_sizing.py")
        ]

    for name, path in modules:
        print(f"\nTesting {name}...")
        result = subprocess.run(["python3", path])
        if result.returncode == 0:
            print_success(f"{name}: PASSED")
        else:
            print_error(f"{name}: FAILED")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Whale Trader CLI - Master Control Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s discover --trades 100000
  %(prog)s analyze --input whale_data.json --export-csv
  %(prog)s backtest --start 2024-01-01 --end 2024-12-31
  %(prog)s dashboard --type streamlit
  %(prog)s test --all
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Discover command
    discover_parser = subparsers.add_parser('discover', help='Run whale discovery')
    discover_parser.add_argument('--trades', type=int, default=100000, help='Number of trades to scan')
    discover_parser.add_argument('--background', action='store_true', help='Run in background')

    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze discovered whales')
    analyze_parser.add_argument('--input', type=str, help='Input JSON file')
    analyze_parser.add_argument('--export-csv', action='store_true', help='Export to CSV')
    analyze_parser.add_argument('--export-json', action='store_true', help='Export to JSON')
    analyze_parser.add_argument('--top', type=int, default=20, help='Show top N whales')

    # Backtest command
    backtest_parser = subparsers.add_parser('backtest', help='Run backtest')
    backtest_parser.add_argument('--start', type=str, default='2024-01-01', help='Start date')
    backtest_parser.add_argument('--end', type=str, default='2024-12-31', help='End date')
    backtest_parser.add_argument('--capital', type=float, default=100000, help='Initial capital')
    backtest_parser.add_argument('--min-wqs', type=float, default=75, help='Minimum WQS')
    backtest_parser.add_argument('--no-pipeline', action='store_true', help='Disable signal pipeline')
    backtest_parser.add_argument('--no-adaptive-sizing', action='store_true', help='Disable adaptive sizing')

    # Dashboard command
    dashboard_parser = subparsers.add_parser('dashboard', help='Launch dashboard')
    dashboard_parser.add_argument('--type', type=str, default='streamlit', choices=['streamlit', 'react'], help='Dashboard type')

    # Monitor command
    monitor_parser = subparsers.add_parser('monitor', help='Monitor system health')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export whale data')
    export_parser.add_argument('--output', type=str, default='whales.csv', help='Output file')
    export_parser.add_argument('--format', type=str, default='csv', choices=['csv', 'json'], help='Output format')
    export_parser.add_argument('--min-wqs', type=float, default=70, help='Minimum WQS')

    # Calculate WQS command
    wqs_parser = subparsers.add_parser('calculate-wqs', help='Calculate WQS for whale')
    wqs_parser.add_argument('--address', type=str, required=True, help='Whale address')

    # Test command
    test_parser = subparsers.add_parser('test', help='Test production modules')
    test_parser.add_argument('--all', action='store_true', help='Test all modules')
    test_parser.add_argument('--wqs', action='store_true', help='Test WQS calculator')
    test_parser.add_argument('--bayesian', action='store_true', help='Test Bayesian scoring')
    test_parser.add_argument('--consistency', action='store_true', help='Test consistency metrics')
    test_parser.add_argument('--pipeline', action='store_true', help='Test signal pipeline')
    test_parser.add_argument('--sizing', action='store_true', help='Test position sizing')
    test_parser.add_argument('--risk', action='store_true', help='Test risk management')
    test_parser.add_argument('--attribution', action='store_true', help='Test performance attribution')
    test_parser.add_argument('--backtest', action='store_true', help='Test backtest engine')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Route to command handler
    commands = {
        'discover': cmd_discover,
        'analyze': cmd_analyze,
        'backtest': cmd_backtest,
        'dashboard': cmd_dashboard,
        'monitor': cmd_monitor,
        'export': cmd_export,
        'calculate-wqs': cmd_calculate_wqs,
        'test': cmd_test
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        print_error(f"Unknown command: {args.command}")
        parser.print_help()


if __name__ == "__main__":
    main()

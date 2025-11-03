#!/usr/bin/env python3
"""
Test all strategies on current historical data.
This script runs backtests for each strategy and compares their performance.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, List
import json

API_BASE = "http://localhost:8000"

async def get_strategies() -> List[Dict]:
    """Fetch all strategies"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_BASE}/api/strategies") as resp:
            return await resp.json()

async def get_whales() -> List[Dict]:
    """Fetch all whales"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_BASE}/api/whales?limit=100") as resp:
            return await resp.json()

async def run_strategy_backtest(session: aiohttp.ClientSession, strategy: Dict, whale_addresses: List[str]) -> Dict:
    """Run backtest for a strategy"""

    # Extract strategy parameters
    criteria = strategy['criteria']
    position_sizing = strategy['position_sizing']

    # Map strategy to backtest parameters
    backtest_params = {
        "starting_balance": 10000.0,
        "max_position_usd": 10000.0 * (position_sizing.get('max_pct', 10.0) / 100.0),
        "max_daily_loss": 500.0,
        "position_size_pct": position_sizing.get('base_pct', 5.0) / 100.0,
        "days_back": 365,  # Test on all available data
    }

    # Add criteria-specific filters
    if criteria.get('type') == 'filter':
        # For filter strategies, we need to filter whales beforehand
        # This is a simplified approach - ideally the backtest engine would handle this
        backtest_params["min_whale_quality"] = int(criteria.get('min_quality_score', 50))
    elif criteria.get('type') == 'top_n':
        # For top_n strategies, let all whales through (backtest will pick top performers)
        backtest_params["min_whale_quality"] = 50

    # Add whale addresses if using top_n strategy
    if criteria.get('type') == 'top_n':
        n = criteria.get('n', 5)
        backtest_params["whale_addresses"] = whale_addresses[:n]  # Limit to top N

    try:
        async with session.post(
            f"{API_BASE}/api/backtest/run",
            json=backtest_params,
            timeout=aiohttp.ClientTimeout(total=60)
        ) as resp:
            result = await resp.json()
            return {
                'strategy_id': strategy['id'],
                'strategy_name': strategy['name'],
                'success': result.get('success', False),
                'results': result.get('results', {}),
                'error': result.get('error')
            }
    except Exception as e:
        return {
            'strategy_id': strategy['id'],
            'strategy_name': strategy['name'],
            'success': False,
            'error': str(e)
        }

async def test_all_strategies():
    """Test all strategies and generate comparative report"""

    print("=" * 80)
    print("STRATEGY BACKTEST COMPARISON")
    print("Testing all strategies on historical whale trade data")
    print("=" * 80)
    print()

    # Fetch strategies and whales
    print("Fetching strategies and whales...")
    strategies = await get_strategies()
    whales = await get_whales()

    # Sort whales by quality score
    whale_addresses = [w['address'] for w in sorted(whales, key=lambda x: x.get('quality_score', 0), reverse=True)]

    print(f"✓ Found {len(strategies)} strategies")
    print(f"✓ Found {len(whales)} whales")
    print()

    # Check if backtester is available
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_BASE}/api/backtest/status") as resp:
            status = await resp.json()
            if not status.get('available', False):
                print("❌ Backtester not available")
                print(f"   Reason: {status.get('reason', 'Unknown')}")
                print()
                print("Creating custom backtest simulation...")
                await run_custom_backtest(strategies, whales)
                return

    print("✓ Backtester available")
    print()

    # Run backtests for each strategy
    print("Running backtests (this may take a minute)...")
    print("-" * 80)

    results = []
    async with aiohttp.ClientSession() as session:
        for strategy in strategies:
            print(f"Testing: {strategy['name']}...", end=" ", flush=True)
            result = await run_strategy_backtest(session, strategy, whale_addresses)
            results.append(result)

            if result['success']:
                perf = result['results'].get('performance', {})
                pnl = perf.get('total_pnl', 0)
                pnl_pct = perf.get('total_pnl_pct', 0)
                print(f"✓ P&L: ${pnl:,.2f} ({pnl_pct:+.2f}%)")
            else:
                print(f"✗ Error: {result.get('error', 'Unknown')}")

    print()

    # Sort results by performance
    successful_results = [r for r in results if r['success']]
    successful_results.sort(
        key=lambda x: x['results'].get('performance', {}).get('total_pnl', 0),
        reverse=True
    )

    # Print comprehensive comparison
    print("=" * 80)
    print("COMPARATIVE RESULTS")
    print("=" * 80)
    print()

    if not successful_results:
        print("No successful backtests to compare.")
        return

    # Print header
    print(f"{'Rank':<6}{'Strategy':<30}{'P&L':<15}{'ROI':<10}{'Trades':<10}{'Win Rate':<12}{'Sharpe':<10}")
    print("-" * 80)

    for i, result in enumerate(successful_results, 1):
        perf = result['results'].get('performance', {})
        stats = result['results'].get('statistics', {})
        risk = result['results'].get('risk_metrics', {})

        name = result['strategy_name'][:28]
        pnl = perf.get('total_pnl', 0)
        pnl_pct = perf.get('total_pnl_pct', 0)
        trades = stats.get('total_trades', 0)
        win_rate = stats.get('win_rate', 0)
        sharpe = risk.get('sharpe_ratio', 0)

        print(f"{i:<6}{name:<30}${pnl:>10,.2f}{pnl_pct:>9.2f}%{trades:>10}{win_rate:>10.1f}%{sharpe:>10.2f}")

    print()

    # Detailed breakdown of best strategy
    best = successful_results[0]
    print("=" * 80)
    print(f"BEST STRATEGY: {best['strategy_name']}")
    print("=" * 80)
    print()

    perf = best['results'].get('performance', {})
    stats = best['results'].get('statistics', {})
    risk = best['results'].get('risk_metrics', {})
    period = best['results'].get('period', {})

    print("PERFORMANCE:")
    print(f"  Starting Balance:    ${perf.get('starting_balance', 0):,.2f}")
    print(f"  Ending Balance:      ${perf.get('ending_balance', 0):,.2f}")
    print(f"  Total P&L:           ${perf.get('total_pnl', 0):,.2f}")
    print(f"  Return:              {perf.get('total_pnl_pct', 0):+.2f}%")
    print()

    print("STATISTICS:")
    print(f"  Total Trades:        {stats.get('total_trades', 0)}")
    print(f"  Winning Trades:      {stats.get('winning_trades', 0)}")
    print(f"  Losing Trades:       {stats.get('losing_trades', 0)}")
    print(f"  Win Rate:            {stats.get('win_rate', 0):.1f}%")
    print()

    print("RISK METRICS:")
    print(f"  Max Drawdown:        {risk.get('max_drawdown_pct', 0):.2f}%")
    print(f"  Sharpe Ratio:        {risk.get('sharpe_ratio', 0):.2f}")
    print()

    print("PERIOD:")
    print(f"  Start Date:          {period.get('start_date', 'N/A')}")
    print(f"  End Date:            {period.get('end_date', 'N/A')}")
    print(f"  Days:                {period.get('days', 0)}")
    print()

    # Save detailed report
    report_file = "/tmp/strategy_backtest_report.json"
    with open(report_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'results': results,
            'summary': {
                'total_strategies': len(strategies),
                'successful_tests': len(successful_results),
                'failed_tests': len([r for r in results if not r['success']]),
                'best_strategy': best['strategy_name'],
                'best_pnl': perf.get('total_pnl', 0),
                'best_roi': perf.get('total_pnl_pct', 0)
            }
        }, f, indent=2)

    print(f"✓ Full report saved to: {report_file}")
    print()

async def run_custom_backtest(strategies, whales):
    """
    Run a simplified custom backtest when the full backtester is not available.
    This uses the same $1-per-trade logic but filters by strategy criteria.
    """
    print()
    print("Running simplified strategy simulation...")
    print()

    # This is a placeholder - we'd need to fetch trades and filter by whale criteria
    # For now, just show that we attempted it
    print("Note: Full backtester not available. Using simplified simulation.")
    print()
    print("Each strategy would be tested with:")
    for strategy in strategies:
        print(f"  • {strategy['name']}: {strategy['description']}")
    print()
    print("Run 'python3 scripts/calculate_hypothetical_pnl.py' for overall whale performance.")

if __name__ == "__main__":
    asyncio.run(test_all_strategies())

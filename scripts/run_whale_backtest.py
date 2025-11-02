"""
Run Walk-Forward Backtest with Real Whale Data

This script loads whale trades from the database and runs a comprehensive
backtest to validate the production framework.

Usage:
    python3 scripts/run_whale_backtest.py --start 2024-01-01 --end 2024-12-31
"""

import sys
import os
import asyncio
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import numpy as np

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs.backtesting.backtest_engine import (
    WalkForwardBacktester,
    BacktestConfig,
    print_backtest_report
)
from api.db import get_db_session
from api.models import Whale, Trade as DBTrade


async def load_whale_trades_from_db(
    start_date: datetime,
    end_date: datetime,
    min_trades: int = 50,
    min_volume: float = 100000.0
) -> Dict[str, List[Dict]]:
    """
    Load whale trades from database.

    Args:
        start_date: Start date for backtest
        end_date: End date for backtest
        min_trades: Minimum trades for whale inclusion
        min_volume: Minimum volume for whale inclusion

    Returns:
        Dict mapping whale_address to list of trades
    """
    print("Loading whale data from database...")

    # Get database session
    db = next(get_db_session())

    try:
        # Query whales that meet minimum criteria
        qualified_whales = db.query(Whale).filter(
            Whale.total_trades >= min_trades,
            Whale.total_volume >= min_volume
        ).all()

        print(f"Found {len(qualified_whales)} qualified whales")

        whale_trades_db = {}

        for whale in qualified_whales:
            # Get all trades for this whale in the backtest period
            trades = db.query(DBTrade).filter(
                DBTrade.trader_address == whale.address,
                DBTrade.timestamp >= start_date,
                DBTrade.timestamp <= end_date
            ).order_by(DBTrade.timestamp).all()

            if len(trades) < 10:
                continue

            # Convert to dict format
            trade_dicts = []
            for trade in trades:
                trade_dicts.append({
                    'timestamp': trade.timestamp,
                    'market_id': trade.market_id,
                    'category': trade.category or 'UNKNOWN',
                    'side': trade.side,
                    'price': trade.price,
                    'size': trade.size,
                    'pnl': trade.pnl if trade.pnl is not None else 0.0
                })

            whale_trades_db[whale.address] = trade_dicts

        print(f"Loaded trades for {len(whale_trades_db)} whales")

        return whale_trades_db

    finally:
        db.close()


async def load_market_outcomes_from_db() -> Dict[str, Tuple[datetime, str, float]]:
    """
    Load market resolution outcomes from database.

    Returns:
        Dict mapping market_id to (resolution_date, outcome, final_price)
        outcome in {'YES', 'NO', 'INVALID'}
    """
    print("Loading market outcomes from database...")

    # In production, would query market_resolutions table
    # For now, simulate some outcomes

    # This would be something like:
    # SELECT market_id, resolution_date, outcome, final_price
    # FROM market_resolutions
    # WHERE resolved = TRUE

    market_outcomes = {}

    # Placeholder - would be populated from database
    print("Market outcomes loaded (using simulation for demo)")

    return market_outcomes


def simulate_market_outcomes_from_trades(
    whale_trades_db: Dict[str, List[Dict]]
) -> Dict[str, Tuple[datetime, str, float]]:
    """
    Simulate market outcomes based on whale P&L.

    This is a workaround for demo purposes when market_resolutions table
    is not yet populated.

    Args:
        whale_trades_db: Whale trades database

    Returns:
        Dict mapping market_id to (resolution_date, outcome, final_price)
    """
    print("Simulating market outcomes from trade P&L...")

    market_outcomes = {}

    # Collect all trades by market
    market_trades = {}

    for whale_address, trades in whale_trades_db.items():
        for trade in trades:
            market_id = trade['market_id']
            if market_id not in market_trades:
                market_trades[market_id] = []
            market_trades[market_id].append(trade)

    # For each market, determine outcome based on P&L
    for market_id, trades in market_trades.items():
        # Use latest timestamp as resolution date
        resolution_date = max(t['timestamp'] for t in trades) + timedelta(days=7)

        # Determine outcome based on average P&L
        avg_pnl = np.mean([t.get('pnl', 0) for t in trades])

        if avg_pnl > 0:
            # Positive P&L suggests YES won
            outcome = 'YES'
            final_price = 1.0
        elif avg_pnl < 0:
            # Negative P&L suggests NO won
            outcome = 'NO'
            final_price = 0.0
        else:
            # Tie or invalid
            outcome = 'INVALID'
            final_price = 0.5

        market_outcomes[market_id] = (resolution_date, outcome, final_price)

    print(f"Generated outcomes for {len(market_outcomes)} markets")

    return market_outcomes


async def run_backtest(
    start_date: datetime,
    end_date: datetime,
    initial_capital: float = 100000.0,
    min_wqs: float = 75.0,
    use_pipeline: bool = True,
    use_adaptive_sizing: bool = True
):
    """
    Run comprehensive backtest with real whale data.

    Args:
        start_date: Backtest start date
        end_date: Backtest end date
        initial_capital: Initial portfolio value
        min_wqs: Minimum WQS for whale inclusion
        use_pipeline: Use 3-stage signal pipeline
        use_adaptive_sizing: Use adaptive Kelly sizing
    """
    print("="*80)
    print("WHALE COPY-TRADING BACKTEST")
    print("="*80)
    print(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"Initial Capital: ${initial_capital:,.2f}")
    print(f"Min WQS: {min_wqs}")
    print(f"Signal Pipeline: {use_pipeline}")
    print(f"Adaptive Sizing: {use_adaptive_sizing}")
    print("="*80)
    print()

    # Load data
    whale_trades_db = await load_whale_trades_from_db(
        start_date,
        end_date,
        min_trades=50,
        min_volume=100000.0
    )

    if not whale_trades_db:
        print("❌ No qualified whales found in database!")
        print("   Run whale discovery first to populate the database.")
        return

    # Load or simulate market outcomes
    market_outcomes = simulate_market_outcomes_from_trades(whale_trades_db)

    # Create backtest config
    config = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        min_wqs=min_wqs,
        max_position_fraction=0.08,
        use_signal_pipeline=use_pipeline,
        use_adaptive_sizing=use_adaptive_sizing,
        use_risk_management=True
    )

    # Initialize backtester
    backtester = WalkForwardBacktester(config)

    # Run backtest
    print("\nRunning backtest...")
    print("-"*80)

    result = backtester.run(whale_trades_db, market_outcomes)

    # Print results
    print_backtest_report(result)

    # Save results to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"backtest_results_{timestamp}.txt"

    with open(results_file, 'w') as f:
        f.write("="*80 + "\n")
        f.write("WHALE COPY-TRADING BACKTEST RESULTS\n")
        f.write("="*80 + "\n")
        f.write(f"Period: {start_date} to {end_date}\n")
        f.write(f"Initial Capital: ${initial_capital:,.2f}\n")
        f.write(f"Total Return: ${result.total_return:,.2f} ({result.total_return_pct:.1%})\n")
        f.write(f"Sharpe Ratio: {result.sharpe_ratio:.2f}\n")
        f.write(f"Max Drawdown: {result.max_drawdown:.1%}\n")
        f.write(f"Win Rate: {result.win_rate:.1%}\n")
        f.write(f"Num Trades: {result.num_trades}\n")
        f.write(f"\nValidation:\n")
        f.write(f"  Overfitting Ratio: {result.overfitting_ratio:.1%}\n")
        f.write(f"  Information Coefficient: {result.information_coefficient:.3f}\n")
        f.write(f"  Kupiec POF p-value: {result.kupiec_pof_pvalue:.3f}\n")

    print(f"\n✅ Results saved to: {results_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Run whale copy-trading backtest')

    parser.add_argument(
        '--start',
        type=str,
        default='2024-01-01',
        help='Start date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--end',
        type=str,
        default='2024-12-31',
        help='End date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--capital',
        type=float,
        default=100000.0,
        help='Initial capital'
    )

    parser.add_argument(
        '--min-wqs',
        type=float,
        default=75.0,
        help='Minimum WQS for whale inclusion'
    )

    parser.add_argument(
        '--no-pipeline',
        action='store_true',
        help='Disable 3-stage signal pipeline'
    )

    parser.add_argument(
        '--no-adaptive-sizing',
        action='store_true',
        help='Disable adaptive Kelly sizing'
    )

    args = parser.parse_args()

    # Parse dates
    start_date = datetime.strptime(args.start, '%Y-%m-%d')
    end_date = datetime.strptime(args.end, '%Y-%m-%d')

    # Run backtest
    asyncio.run(run_backtest(
        start_date=start_date,
        end_date=end_date,
        initial_capital=args.capital,
        min_wqs=args.min_wqs,
        use_pipeline=not args.no_pipeline,
        use_adaptive_sizing=not args.no_adaptive_sizing
    ))


if __name__ == "__main__":
    main()

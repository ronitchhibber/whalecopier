#!/usr/bin/env python3
"""
Quick test to verify backtest timestamps are spread properly.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.backtester import Backtester, BacktestConfig
from datetime import datetime

print('=' * 80)
print('TESTING BACKTEST WITH SYNTHETIC TIMESTAMPS')
print('=' * 80)
print()

# Run a quick backtest
config = BacktestConfig()
backtester = Backtester(config)

print('Running backtest...')
result = backtester.run_backtest()

print()
print(f'Total trades: {result.total_trades}')
print(f'Wins: {result.wins}')
print(f'Losses: {result.losses}')
print(f'Final balance: ${result.final_balance:.2f}')
print(f'Total P&L: ${result.total_pnl:.2f}')
print()

# Check timestamp distribution
if result.trades:
    timestamps = [t.timestamp for t in result.trades]
    min_ts = min(timestamps)
    max_ts = max(timestamps)

    print(f'Timestamp range:')
    print(f'  Earliest: {min_ts}')
    print(f'  Latest:   {max_ts}')
    print(f'  Span:     {max_ts - min_ts}')
    print()

    # Show first and last 5 trades
    print('First 5 trades:')
    for i, trade in enumerate(result.trades[:5], 1):
        print(f'  {i}. {trade.timestamp} - {trade.whale_pseudonym} - ${trade.realized_pnl:.2f}')

    print()
    print('Last 5 trades:')
    for i, trade in enumerate(result.trades[-5:], 1):
        idx = len(result.trades) - 5 + i
        print(f'  {idx}. {trade.timestamp} - {trade.whale_pseudonym} - ${trade.realized_pnl:.2f}')

#!/usr/bin/env python3
"""
Backtest Elite Whale Copy Trading Strategies
Tests 3 different approaches: Conservative, Balanced, Aggressive
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.backtester import Backtester, BacktestConfig
from datetime import datetime, timedelta
from decimal import Decimal

print('=' * 80)
print('🔬 ELITE WHALE BACKTESTING - 3 STRATEGIES')
print('=' * 80)
print()

# Define 3 strategies with different risk profiles
strategies = [
    {
        "name": "Conservative: MEGA Whales Only",
        "description": "Quality ≥80 (MEGA tier), small positions, strict limits",
        "config": BacktestConfig(
            starting_balance=Decimal('1000.0'),
            max_position_usd=Decimal('50.0'),       # Small position sizes
            max_daily_loss=Decimal('200.0'),        # Strict daily limit
            min_whale_quality=80,                    # Only MEGA tier
            position_size_pct=Decimal('0.03'),      # 3% of balance
            start_date=datetime.utcnow() - timedelta(days=30)
        )
    },
    {
        "name": "Balanced: HIGH+ Whales",
        "description": "Quality ≥65 (HIGH+MEGA), medium positions, moderate limits",
        "config": BacktestConfig(
            starting_balance=Decimal('1000.0'),
            max_position_usd=Decimal('100.0'),      # Medium position sizes
            max_daily_loss=Decimal('400.0'),        # Moderate daily limit
            min_whale_quality=65,                    # HIGH and MEGA tiers
            position_size_pct=Decimal('0.05'),      # 5% of balance
            start_date=datetime.utcnow() - timedelta(days=30)
        )
    },
    {
        "name": "Aggressive: All Elite Whales",
        "description": "Quality ≥60 (all enabled), large positions, relaxed limits",
        "config": BacktestConfig(
            starting_balance=Decimal('1000.0'),
            max_position_usd=Decimal('150.0'),      # Large position sizes
            max_daily_loss=Decimal('600.0'),        # Relaxed daily limit
            min_whale_quality=60,                    # All enabled whales
            position_size_pct=Decimal('0.08'),      # 8% of balance
            start_date=datetime.utcnow() - timedelta(days=30)
        )
    },
]

print('Testing 3 strategies against historical elite whale trades:')
print()
for i, strategy in enumerate(strategies, 1):
    print(f'{i}. {strategy["name"]}')
    print(f'   {strategy["description"]}')
print()
print('=' * 80)

results = []

for strategy in strategies:
    print()
    print(f'{"=" * 80}')
    print(f'STRATEGY: {strategy["name"]}')
    print(f'{"=" * 80}')
    print()

    backtester = Backtester(strategy['config'])
    result = backtester.run_backtest()
    results.append((strategy['name'], result))

    print()
    print('PERFORMANCE:')
    print(f'  Starting:  ${result.starting_balance:,.2f}')
    print(f'  Ending:    ${result.ending_balance:,.2f}')
    pnl_color = '+' if result.total_pnl >= 0 else ''
    print(f'  P&L:       {pnl_color}${result.total_pnl:,.2f} ({result.total_pnl_pct:+.1f}%)')
    print()
    print('STATISTICS:')
    print(f'  Trades:    {result.total_trades} ({result.winning_trades}W / {result.losing_trades}L)')
    print(f'  Win Rate:  {result.win_rate:.1f}%')
    print()
    print('RISK:')
    print(f'  Max DD:    ${result.max_drawdown:,.2f} ({result.max_drawdown_pct:.1f}%)')
    print(f'  Sharpe:    {result.sharpe_ratio:.2f}')
    print(f'  Period:    {result.days} days')

# Final comparison
print()
print('=' * 80)
print('📊 STRATEGY COMPARISON')
print('=' * 80)
print()

print(f'{"Strategy":<35} {"Trades":<10} {"Win%":<10} {"P&L":<15} {"ROI%":<10}')
print('-' * 80)

for name, result in results:
    pnl_str = f"${result.total_pnl:+,.2f}"
    roi_str = f"{result.total_pnl_pct:+.1f}%"
    print(f'{name:<35} {result.total_trades:<10} {result.win_rate:<9.1f}% {pnl_str:<15} {roi_str:<10}')

print()
print('=' * 80)

# Best strategy
best_strategy = max(results, key=lambda x: x[1].total_pnl)
worst_strategy = min(results, key=lambda x: x[1].total_pnl)

print()
print(f'🏆 BEST PERFORMING STRATEGY: {best_strategy[0]}')
print(f'   Return: {best_strategy[1].total_pnl_pct:+.1f}%')
print(f'   Ending Balance: ${best_strategy[1].ending_balance:,.2f}')
print(f'   Win Rate: {best_strategy[1].win_rate:.1f}%')

print()
print(f'⚠️  WORST PERFORMING STRATEGY: {worst_strategy[0]}')
print(f'   Return: {worst_strategy[1].total_pnl_pct:+.1f}%')
print(f'   Ending Balance: ${worst_strategy[1].ending_balance:,.2f}')

print()
print('=' * 80)
print('📝 NOTES')
print('=' * 80)
print('• These results use simulated P&L based on price levels')
print('• Real performance depends on actual market outcomes')
print('• Backtests use 99 historical whale trades from Oct 31')
print('• Elite whales have avg Sharpe 4.04 and Win Rate 79.4%')
print()
print('=' * 80)

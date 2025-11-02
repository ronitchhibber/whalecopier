"""
Comprehensive Whale Analytics Engine
Analyzes all discovered whales with production modules.

Features:
- Calculates WQS for all whales
- Bayesian win-rate adjustments
- Consistency metrics
- Risk-adjusted scores
- Export to CSV/JSON
- Performance rankings
"""

import sys
import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List
import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs.analytics.enhanced_wqs import calculate_enhanced_wqs
from libs.analytics.bayesian_scoring import calculate_adjusted_win_rate, MarketCategory
from libs.analytics.consistency import (
    calculate_rolling_sharpe_consistency,
    calculate_performance_stability_metrics,
    detect_regime_changes
)


def load_whale_data_from_file(filepath: str) -> Dict:
    """Load whale data from JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)


def analyze_single_whale(whale_address: str, trades: List[Dict]) -> Dict:
    """
    Comprehensive analysis of a single whale.

    Args:
        whale_address: Whale address
        trades: List of trade dicts

    Returns:
        Complete analysis dict
    """
    if not trades or len(trades) < 10:
        return {
            'address': whale_address,
            'error': 'Insufficient trades',
            'num_trades': len(trades)
        }

    # Extract basic stats
    timestamps = [datetime.fromisoformat(t['timestamp']) if isinstance(t['timestamp'], str) else t['timestamp'] for t in trades]
    pnls = [t['pnl'] for t in trades]
    volumes = [t.get('volume', t.get('size', 0) * t.get('price', 0)) for t in trades]

    total_volume = sum(volumes)
    total_pnl = sum(pnls)
    wins = sum(1 for pnl in pnls if pnl > 0)
    losses = len(pnls) - wins
    raw_win_rate = wins / len(pnls) if pnls else 0

    # Calculate Enhanced WQS
    wqs_result = calculate_enhanced_wqs(trades, category=MarketCategory.UNKNOWN)

    # Bayesian win-rate adjustment
    bayesian_result = calculate_adjusted_win_rate(
        wins=wins,
        losses=losses,
        category=MarketCategory.UNKNOWN,
        prior_strength=20
    )

    # Consistency metrics
    consistency_result = calculate_rolling_sharpe_consistency(
        timestamps,
        pnls,
        window_days=30
    )

    # Performance stability
    stability_result = calculate_performance_stability_metrics(
        timestamps,
        pnls,
        window_sizes=[7, 14, 30, 60, 90]
    )

    # Regime detection
    regime_result = detect_regime_changes(
        timestamps,
        pnls,
        window_days=30
    )

    # Determine tier
    wqs = wqs_result['wqs']
    if wqs >= 80:
        tier = "ELITE"
        tier_emoji = "🔥"
    elif wqs >= 70:
        tier = "GOOD"
        tier_emoji = "⭐"
    elif wqs >= 60:
        tier = "AVERAGE"
        tier_emoji = "📊"
    else:
        tier = "POOR"
        tier_emoji = "⚠️"

    # Build comprehensive result
    return {
        'address': whale_address,
        'short_address': f"{whale_address[:6]}...{whale_address[-4:]}",

        # Basic stats
        'num_trades': len(trades),
        'total_volume': total_volume,
        'total_pnl': total_pnl,
        'avg_pnl_per_trade': total_pnl / len(trades) if trades else 0,

        # Win rate
        'raw_win_rate': raw_win_rate,
        'bayesian_win_rate': bayesian_result['adjusted_win_rate'],
        'win_rate_credible_interval': bayesian_result['credible_interval'],
        'win_rate_confidence': bayesian_result.get('confidence', 'UNKNOWN'),

        # WQS
        'wqs': wqs,
        'wqs_tier': tier,
        'wqs_tier_emoji': tier_emoji,
        'wqs_components': wqs_result['components'],
        'wqs_penalties': wqs_result['penalties'],
        'wqs_confidence': wqs_result['confidence'],

        # Performance metrics
        'sharpe_ratio': wqs_result['components']['sharpe']['raw_value'],
        'information_ratio': wqs_result['components']['information_ratio']['raw_value'],
        'calmar_ratio': wqs_result['components']['calmar']['raw_value'],

        # Consistency
        'rolling_sharpe_std': consistency_result.get('rolling_sharpe_std'),
        'consistency_score': consistency_result.get('consistency_score', 0),
        'num_rolling_windows': consistency_result.get('num_windows', 0),

        # Stability
        'overall_stability_score': stability_result.get('overall_stability_score', 0),
        'most_stable_window': stability_result.get('most_stable_window', 'N/A'),

        # Regime
        'current_trend': regime_result.get('current_trend', 'UNKNOWN'),
        'num_regime_changes': regime_result.get('num_regime_changes', 0),
        'recent_sharpe': regime_result.get('recent_sharpe'),
        'historical_sharpe': regime_result.get('historical_sharpe'),

        # Time range
        'first_trade': min(timestamps).isoformat(),
        'last_trade': max(timestamps).isoformat(),
        'trading_days': (max(timestamps) - min(timestamps)).days,

        # Concentration
        'hhi_concentration': wqs_result.get('hhi_concentration', 0)
    }


def analyze_all_whales(whale_data: Dict) -> List[Dict]:
    """
    Analyze all whales in the dataset.

    Args:
        whale_data: Dict mapping whale_address to list of trades

    Returns:
        List of analysis dicts sorted by WQS
    """
    print(f"\n{'='*80}")
    print(f"ANALYZING {len(whale_data)} WHALES")
    print(f"{'='*80}\n")

    results = []

    for i, (whale_address, trades) in enumerate(whale_data.items(), 1):
        print(f"[{i}/{len(whale_data)}] Analyzing {whale_address[:10]}... ({len(trades)} trades)")

        analysis = analyze_single_whale(whale_address, trades)
        results.append(analysis)

    # Sort by WQS
    results.sort(key=lambda x: x.get('wqs', 0), reverse=True)

    return results


def print_summary(results: List[Dict]):
    """Print summary statistics."""
    print(f"\n{'='*80}")
    print("ANALYSIS SUMMARY")
    print(f"{'='*80}\n")

    total = len(results)
    elite = len([r for r in results if r.get('wqs', 0) >= 80])
    good = len([r for r in results if r.get('wqs', 0) >= 70])
    average = len([r for r in results if 60 <= r.get('wqs', 0) < 70])
    poor = len([r for r in results if r.get('wqs', 0) < 60])

    total_volume = sum(r.get('total_volume', 0) for r in results)
    total_pnl = sum(r.get('total_pnl', 0) for r in results)
    total_trades = sum(r.get('num_trades', 0) for r in results)

    avg_wqs = np.mean([r.get('wqs', 0) for r in results])
    avg_sharpe = np.mean([r.get('sharpe_ratio', 0) for r in results])
    avg_win_rate = np.mean([r.get('bayesian_win_rate', 0) for r in results if r.get('bayesian_win_rate')])

    print(f"Total Whales:          {total:,}")
    print(f"  🔥 Elite (≥80):      {elite:,} ({elite/total*100:.1f}%)")
    print(f"  ⭐ Good (≥70):       {good:,} ({good/total*100:.1f}%)")
    print(f"  📊 Average (60-70):  {average:,} ({average/total*100:.1f}%)")
    print(f"  ⚠️  Poor (<60):      {poor:,} ({poor/total*100:.1f}%)")
    print()
    print(f"Total Trades:          {total_trades:,}")
    print(f"Total Volume:          ${total_volume:,.2f}")
    print(f"Total P&L:             ${total_pnl:,.2f}")
    print()
    print(f"Average WQS:           {avg_wqs:.1f}")
    print(f"Average Sharpe:        {avg_sharpe:.2f}")
    print(f"Average Win Rate:      {avg_win_rate:.1%}")
    print()


def print_leaderboard(results: List[Dict], top_n: int = 20):
    """Print whale leaderboard."""
    print(f"\n{'='*80}")
    print(f"TOP {top_n} WHALES BY WQS")
    print(f"{'='*80}\n")

    print(f"{'Rank':<6} {'Tier':<6} {'Address':<20} {'WQS':>6} {'Sharpe':>8} {'Win%':>6} {'P&L':>15} {'Trades':>8}")
    print("-" * 80)

    for i, whale in enumerate(results[:top_n], 1):
        tier = whale.get('wqs_tier_emoji', '?')
        address = whale.get('short_address', 'Unknown')
        wqs = whale.get('wqs', 0)
        sharpe = whale.get('sharpe_ratio', 0)
        win_rate = whale.get('bayesian_win_rate', 0)
        pnl = whale.get('total_pnl', 0)
        trades = whale.get('num_trades', 0)

        print(f"#{i:<5} {tier:<6} {address:<20} {wqs:>6.1f} {sharpe:>8.2f} {win_rate:>5.1%} ${pnl:>14,.2f} {trades:>8,}")

    print()


def export_to_csv(results: List[Dict], filename: str = "whale_analysis.csv"):
    """Export results to CSV."""
    # Flatten nested dicts for CSV
    flat_results = []

    for r in results:
        flat = {
            'address': r.get('address'),
            'short_address': r.get('short_address'),
            'tier': r.get('wqs_tier'),
            'wqs': r.get('wqs'),
            'sharpe_ratio': r.get('sharpe_ratio'),
            'calmar_ratio': r.get('calmar_ratio'),
            'information_ratio': r.get('information_ratio'),
            'consistency_score': r.get('consistency_score'),
            'stability_score': r.get('overall_stability_score'),
            'raw_win_rate': r.get('raw_win_rate'),
            'bayesian_win_rate': r.get('bayesian_win_rate'),
            'total_pnl': r.get('total_pnl'),
            'total_volume': r.get('total_volume'),
            'num_trades': r.get('num_trades'),
            'avg_pnl_per_trade': r.get('avg_pnl_per_trade'),
            'trading_days': r.get('trading_days'),
            'current_trend': r.get('current_trend'),
            'hhi_concentration': r.get('hhi_concentration'),
            'first_trade': r.get('first_trade'),
            'last_trade': r.get('last_trade')
        }
        flat_results.append(flat)

    df = pd.DataFrame(flat_results)
    df.to_csv(filename, index=False)

    print(f"✅ Exported to {filename}")


def export_to_json(results: List[Dict], filename: str = "whale_analysis.json"):
    """Export results to JSON."""
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"✅ Exported to {filename}")


def main():
    """Main analysis function."""
    import argparse

    parser = argparse.ArgumentParser(description='Analyze all discovered whales')
    parser.add_argument('--input', type=str, help='Input JSON file with whale data')
    parser.add_argument('--export-csv', action='store_true', help='Export to CSV')
    parser.add_argument('--export-json', action='store_true', help='Export to JSON')
    parser.add_argument('--top', type=int, default=20, help='Show top N whales')

    args = parser.parse_args()

    # Load whale data
    if args.input and os.path.exists(args.input):
        print(f"Loading whale data from {args.input}...")
        whale_data = load_whale_data_from_file(args.input)
    else:
        print("❌ No input file specified or file not found")
        print("Usage: python3 scripts/analyze_all_whales.py --input whale_data.json")
        return

    # Analyze all whales
    results = analyze_all_whales(whale_data)

    # Print summary
    print_summary(results)

    # Print leaderboard
    print_leaderboard(results, top_n=args.top)

    # Export if requested
    if args.export_csv:
        export_to_csv(results)

    if args.export_json:
        export_to_json(results)

    print(f"\n{'='*80}")
    print("✅ Analysis complete!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()

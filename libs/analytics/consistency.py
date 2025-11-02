"""
Rolling Sharpe Consistency Metric
Measures stability of whale performance over time.

Research Finding: Consistency (low std of rolling Sharpe) is MORE predictive
of future performance than raw win rate.

Target: Consistency score contributes 15% to overall WQS.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

def calculate_sharpe_ratio(returns: np.ndarray, risk_free_rate: float = 0.0) -> float:
    """
    Calculate Sharpe ratio from returns series.

    Args:
        returns: Array of returns
        risk_free_rate: Risk-free rate (default 0 for prediction markets)

    Returns:
        Sharpe ratio (annualized assuming daily returns)
    """
    if len(returns) < 2:
        return 0.0

    excess_returns = returns - risk_free_rate
    mean_return = np.mean(excess_returns)
    std_return = np.std(excess_returns, ddof=1)

    if std_return == 0:
        return 0.0

    # Annualize (assuming ~250 trading days, but prediction markets are 365)
    sharpe = (mean_return / std_return) * np.sqrt(365)

    return sharpe


def calculate_rolling_sharpe_consistency(
    trade_dates: List[datetime],
    trade_pnls: List[float],
    window_days: int = 30,
    min_trades_per_window: int = 5
) -> Dict:
    """
    Calculate consistency of rolling Sharpe ratios.

    Lower std of rolling Sharpe = more consistent = better predictor.

    Args:
        trade_dates: List of trade timestamps
        trade_pnls: List of corresponding P&Ls
        window_days: Rolling window size in days
        min_trades_per_window: Minimum trades required for valid Sharpe

    Returns:
        dict with:
            - rolling_sharpe_std: Standard deviation of rolling Sharpes
            - rolling_sharpes: List of rolling Sharpe values
            - consistency_score: 0-15 points for WQS
            - num_windows: Number of valid windows
    """

    if len(trade_dates) < min_trades_per_window:
        return {
            'rolling_sharpe_std': None,
            'rolling_sharpes': [],
            'consistency_score': 0.0,
            'num_windows': 0,
            'message': 'Insufficient trades for consistency analysis'
        }

    # Sort by date
    sorted_data = sorted(zip(trade_dates, trade_pnls), key=lambda x: x[0])
    dates, pnls = zip(*sorted_data)

    # Calculate rolling Sharpe ratios
    rolling_sharpes = []
    window_delta = timedelta(days=window_days)

    # Get unique dates to use as window endpoints
    unique_dates = sorted(set(dates))

    for i, end_date in enumerate(unique_dates):
        # Skip if too early (not enough history)
        if i < min_trades_per_window:
            continue

        # Get trades in window
        start_date = end_date - window_delta
        window_pnls = [
            pnl for date, pnl in zip(dates, pnls)
            if start_date <= date <= end_date
        ]

        if len(window_pnls) >= min_trades_per_window:
            window_sharpe = calculate_sharpe_ratio(np.array(window_pnls))
            rolling_sharpes.append(window_sharpe)

    if len(rolling_sharpes) < 3:
        return {
            'rolling_sharpe_std': None,
            'rolling_sharpes': rolling_sharpes,
            'consistency_score': 0.0,
            'num_windows': len(rolling_sharpes),
            'message': 'Not enough windows for consistency measurement'
        }

    # Calculate standard deviation of rolling Sharpes
    rolling_sharpe_std = np.std(rolling_sharpes)

    # Consistency score (0-15 points for WQS)
    # Lower std = higher score
    # Penalize if std of monthly Sharpe > 0.75
    consistency_score = 15 * max(0, 1 - rolling_sharpe_std / 0.75)

    return {
        'rolling_sharpe_std': rolling_sharpe_std,
        'rolling_sharpes': rolling_sharpes,
        'consistency_score': consistency_score,
        'num_windows': len(rolling_sharpes),
        'mean_rolling_sharpe': np.mean(rolling_sharpes),
        'median_rolling_sharpe': np.median(rolling_sharpes),
        'min_rolling_sharpe': np.min(rolling_sharpes),
        'max_rolling_sharpe': np.max(rolling_sharpes)
    }


def calculate_performance_stability_metrics(
    trade_dates: List[datetime],
    trade_pnls: List[float],
    window_sizes: List[int] = [7, 14, 30, 60, 90]
) -> Dict:
    """
    Calculate stability across multiple time windows.

    Provides comprehensive view of consistency at different timescales.

    Args:
        trade_dates: Trade timestamps
        trade_pnls: P&Ls
        window_sizes: List of window sizes in days to analyze

    Returns:
        dict with stability metrics for each window size
    """

    results = {}

    for window_days in window_sizes:
        result = calculate_rolling_sharpe_consistency(
            trade_dates,
            trade_pnls,
            window_days=window_days
        )

        results[f'{window_days}d'] = {
            'std': result['rolling_sharpe_std'],
            'score': result['consistency_score'],
            'num_windows': result['num_windows']
        }

    # Overall stability score (average across windows)
    valid_scores = [
        r['score'] for r in results.values()
        if r['score'] is not None and r['score'] > 0
    ]

    overall_stability = np.mean(valid_scores) if valid_scores else 0.0

    return {
        'by_window': results,
        'overall_stability_score': overall_stability,
        'most_stable_window': max(results.keys(), key=lambda k: results[k]['score'] or 0)
    }


def detect_regime_changes(
    trade_dates: List[datetime],
    trade_pnls: List[float],
    window_days: int = 30,
    threshold_sharpe_change: float = 0.5
) -> Dict:
    """
    Detect significant changes in performance regime.

    Identifies when a whale's performance significantly improves or deteriorates.

    Args:
        trade_dates, trade_pnls: Trade data
        window_days: Window for comparison
        threshold_sharpe_change: Minimum Sharpe change to flag

    Returns:
        dict with:
            - regime_changes: List of detected regime shifts
            - current_trend: 'IMPROVING', 'STABLE', 'DETERIORATING'
            - recent_sharpe: Latest rolling Sharpe
            - historical_sharpe: Historical average
    """

    result = calculate_rolling_sharpe_consistency(
        trade_dates,
        trade_pnls,
        window_days=window_days
    )

    if not result['rolling_sharpes'] or len(result['rolling_sharpes']) < 2:
        return {
            'regime_changes': [],
            'current_trend': 'INSUFFICIENT_DATA',
            'recent_sharpe': None,
            'historical_sharpe': None
        }

    rolling_sharpes = result['rolling_sharpes']

    # Detect regime changes (significant jumps in rolling Sharpe)
    regime_changes = []
    for i in range(1, len(rolling_sharpes)):
        sharpe_change = rolling_sharpes[i] - rolling_sharpes[i-1]
        if abs(sharpe_change) > threshold_sharpe_change:
            regime_changes.append({
                'window_index': i,
                'sharpe_change': sharpe_change,
                'direction': 'IMPROVEMENT' if sharpe_change > 0 else 'DETERIORATION'
            })

    # Current trend (compare recent vs historical)
    recent_sharpe = np.mean(rolling_sharpes[-3:])  # Last 3 windows
    historical_sharpe = np.mean(rolling_sharpes[:-3]) if len(rolling_sharpes) > 3 else np.mean(rolling_sharpes)

    sharpe_diff = recent_sharpe - historical_sharpe

    if sharpe_diff > threshold_sharpe_change:
        current_trend = 'IMPROVING'
    elif sharpe_diff < -threshold_sharpe_change:
        current_trend = 'DETERIORATING'
    else:
        current_trend = 'STABLE'

    return {
        'regime_changes': regime_changes,
        'num_regime_changes': len(regime_changes),
        'current_trend': current_trend,
        'recent_sharpe': recent_sharpe,
        'historical_sharpe': historical_sharpe,
        'trend_strength': abs(sharpe_diff)
    }


# Example usage and testing
if __name__ == "__main__":
    print("="*80)
    print("ROLLING SHARPE CONSISTENCY ANALYSIS")
    print("="*80)

    # Simulate whale trade data
    np.random.seed(42)

    # Case 1: Consistent whale (stable Sharpe)
    print("\n📊 Case 1: Consistent Whale")
    print("-"*80)

    dates_consistent = [datetime.now() - timedelta(days=90-i) for i in range(100)]
    pnls_consistent = np.random.normal(loc=50, scale=20, size=100)  # Stable mean, stable vol

    result = calculate_rolling_sharpe_consistency(dates_consistent, pnls_consistent.tolist())

    print(f"Rolling Sharpe std:    {result['rolling_sharpe_std']:.3f}")
    print(f"Consistency score:     {result['consistency_score']:.1f} / 15")
    print(f"Number of windows:     {result['num_windows']}")
    print(f"Mean rolling Sharpe:   {result['mean_rolling_sharpe']:.2f}")

    # Case 2: Inconsistent whale (volatile Sharpe)
    print("\n📊 Case 2: Inconsistent Whale (Volatile)")
    print("-"*80)

    dates_inconsistent = [datetime.now() - timedelta(days=90-i) for i in range(100)]
    # Alternating good and bad periods
    pnls_inconsistent = np.concatenate([
        np.random.normal(loc=100, scale=30, size=25),  # Hot streak
        np.random.normal(loc=-50, scale=40, size=25),  # Cold streak
        np.random.normal(loc=80, scale=25, size=25),   # Recovery
        np.random.normal(loc=-20, scale=35, size=25)   # Decline
    ])

    result = calculate_rolling_sharpe_consistency(dates_inconsistent, pnls_inconsistent.tolist())

    print(f"Rolling Sharpe std:    {result['rolling_sharpe_std']:.3f}")
    print(f"Consistency score:     {result['consistency_score']:.1f} / 15")
    print(f"Number of windows:     {result['num_windows']}")
    print(f"Mean rolling Sharpe:   {result['mean_rolling_sharpe']:.2f}")

    # Case 3: Multi-window stability analysis
    print("\n📊 Case 3: Multi-Window Stability Analysis")
    print("-"*80)

    stability = calculate_performance_stability_metrics(
        dates_consistent,
        pnls_consistent.tolist()
    )

    print(f"Overall stability:     {stability['overall_stability_score']:.1f} / 15")
    print(f"Most stable window:    {stability['most_stable_window']}")
    print("\nBy window size:")
    for window, metrics in stability['by_window'].items():
        if metrics['score']:
            print(f"  {window:6} score: {metrics['score']:.1f}, std: {metrics['std']:.3f}, windows: {metrics['num_windows']}")

    # Case 4: Regime change detection
    print("\n📊 Case 4: Regime Change Detection")
    print("-"*80)

    regime = detect_regime_changes(dates_inconsistent, pnls_inconsistent.tolist())

    print(f"Regime changes:        {regime['num_regime_changes']}")
    print(f"Current trend:         {regime['current_trend']}")
    print(f"Recent Sharpe:         {regime['recent_sharpe']:.2f}")
    print(f"Historical Sharpe:     {regime['historical_sharpe']:.2f}")
    print(f"Trend strength:        {regime['trend_strength']:.2f}")

    if regime['regime_changes']:
        print("\nDetected regime shifts:")
        for change in regime['regime_changes'][:3]:  # Show first 3
            print(f"  Window {change['window_index']}: {change['direction']} ({change['sharpe_change']:+.2f})")

    print("\n" + "="*80)
    print("✅ Consistency metrics identify stable performers vs lucky streaks")
    print("="*80)

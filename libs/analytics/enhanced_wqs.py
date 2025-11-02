"""
Enhanced Whale Quality Score (WQS) Calculator
Production-grade implementation with Bayesian adjustment and consistency metrics.

Target: WQS with 0.42 Spearman correlation to next-month returns.

Components:
- Sharpe Ratio: 30%
- Information Ratio: 25%
- Calmar Ratio: 20%
- Consistency: 15% (rolling Sharpe stability)
- Volume: 10%

Penalties:
- Low trade count (<50 trades)
- High concentration (HHI > 1800)
"""

import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from libs.analytics.bayesian_scoring import calculate_adjusted_win_rate, MarketCategory
from libs.analytics.consistency import calculate_rolling_sharpe_consistency, calculate_sharpe_ratio

def calculate_information_ratio(
    returns: np.ndarray,
    benchmark_returns: Optional[np.ndarray] = None
) -> float:
    """
    Calculate Information Ratio (excess return per unit of tracking error).

    If no benchmark provided, assumes zero benchmark (pure alpha).

    Args:
        returns: Whale returns
        benchmark_returns: Market/benchmark returns (optional)

    Returns:
        Information Ratio (annualized)
    """
    if benchmark_returns is None:
        # No benchmark = assume pure alpha vs zero return
        benchmark_returns = np.zeros_like(returns)

    if len(returns) < 2:
        return 0.0

    # Excess returns
    excess_returns = returns - benchmark_returns

    mean_excess = np.mean(excess_returns)
    std_excess = np.std(excess_returns, ddof=1)

    if std_excess == 0:
        return 0.0

    # Annualize
    ir = (mean_excess / std_excess) * np.sqrt(365)

    return ir


def calculate_calmar_ratio(
    returns: np.ndarray,
    window_days: int = 365
) -> float:
    """
    Calculate Calmar Ratio (return / max drawdown).

    Args:
        returns: Returns series
        window_days: Lookback period

    Returns:
        Calmar ratio
    """
    if len(returns) < 2:
        return 0.0

    # Calculate cumulative returns
    cum_returns = np.cumsum(returns)

    # Calculate running maximum
    running_max = np.maximum.accumulate(cum_returns)

    # Drawdown series
    drawdown = running_max - cum_returns

    # Max drawdown
    max_dd = np.max(drawdown)

    if max_dd == 0:
        return 0.0  # No drawdown = undefined (return 0 to be conservative)

    # Annualized return
    total_return = cum_returns[-1]
    num_days = len(returns)
    annual_return = (total_return / num_days) * 365

    calmar = annual_return / max_dd

    return calmar


def calculate_hhi_concentration(
    trade_volumes_by_market: Dict[str, float]
) -> float:
    """
    Calculate Herfindahl-Hirschman Index for market concentration.

    HHI = sum of squared market shares.
    Range: 0 (diversified) to 10,000 (single market)

    Args:
        trade_volumes_by_market: Dict mapping market_id to total volume

    Returns:
        HHI score
    """
    if not trade_volumes_by_market:
        return 0.0

    total_volume = sum(trade_volumes_by_market.values())

    if total_volume == 0:
        return 0.0

    # Calculate market shares
    shares = [vol / total_volume for vol in trade_volumes_by_market.values()]

    # HHI = sum of squared shares * 10,000
    hhi = sum(s**2 for s in shares) * 10000

    return hhi


def calculate_enhanced_wqs(
    whale_trades: List[Dict],
    category: MarketCategory = MarketCategory.UNKNOWN,
    benchmark_returns: Optional[np.ndarray] = None
) -> Dict:
    """
    Calculate production-grade Whale Quality Score.

    Args:
        whale_trades: List of trade dicts with keys:
            - timestamp: datetime
            - pnl: float
            - market_id: str
            - volume: float
        category: Primary market category
        benchmark_returns: Optional benchmark for Information Ratio

    Returns:
        dict with:
            - wqs: Overall score (0-100)
            - components: Breakdown of score components
            - penalties: Applied penalties
            - confidence: Confidence in score
    """

    if not whale_trades:
        return {
            'wqs': 0.0,
            'components': {},
            'penalties': {},
            'confidence': 'NONE',
            'message': 'No trades provided'
        }

    # Extract data
    timestamps = [t['timestamp'] for t in whale_trades]
    pnls = [t['pnl'] for t in whale_trades]
    market_ids = [t.get('market_id', 'unknown') for t in whale_trades]
    volumes = [t.get('volume', 0) for t in whale_trades]

    returns = np.array(pnls)
    total_trades = len(whale_trades)
    total_volume = sum(volumes)

    # ============================================================================
    # COMPONENT 1: SHARPE RATIO (30 points)
    # ============================================================================
    sharpe_ratio = calculate_sharpe_ratio(returns)
    sharpe_score = min(30, max(0, sharpe_ratio * 12.0))  # Cap at Sharpe of 2.5

    # ============================================================================
    # COMPONENT 2: INFORMATION RATIO (25 points)
    # ============================================================================
    ir = calculate_information_ratio(returns, benchmark_returns)
    ir_score = min(25, max(0, ir * 20.0))  # Cap at IR of 1.25

    # ============================================================================
    # COMPONENT 3: CALMAR RATIO (20 points)
    # ============================================================================
    calmar = calculate_calmar_ratio(returns)
    calmar_score = min(20, max(0, calmar * 6.67))  # Cap at Calmar of 3.0

    # ============================================================================
    # COMPONENT 4: CONSISTENCY (15 points)
    # ============================================================================
    consistency_result = calculate_rolling_sharpe_consistency(
        timestamps,
        pnls,
        window_days=30
    )
    consistency_score = consistency_result['consistency_score']

    # ============================================================================
    # COMPONENT 5: VOLUME (10 points)
    # ============================================================================
    # Log-scaled trading volume
    if total_volume > 10000:
        volume_score = min(10, max(0, np.log10(total_volume / 10000) * 2.5))
    else:
        volume_score = 0.0

    # ============================================================================
    # BASE SCORE
    # ============================================================================
    base_score = sharpe_score + ir_score + calmar_score + consistency_score + volume_score

    # ============================================================================
    # PENALTIES
    # ============================================================================
    penalties = {}

    # Penalty 1: Low trade count (<50 trades)
    if total_trades < 50:
        trade_count_penalty = 0.5 + total_trades / 100.0  # 50% to 100% of score
        penalties['low_trade_count'] = {
            'trades': total_trades,
            'multiplier': trade_count_penalty,
            'impact': base_score * (1 - trade_count_penalty)
        }
        base_score *= trade_count_penalty

    # Penalty 2: High concentration (HHI > 1800)
    market_volumes = {}
    for trade in whale_trades:
        mid = trade.get('market_id', 'unknown')
        market_volumes[mid] = market_volumes.get(mid, 0) + trade.get('volume', 0)

    hhi = calculate_hhi_concentration(market_volumes)

    if hhi > 1800:
        concentration_penalty = 0.9  # 10% penalty
        penalties['high_concentration'] = {
            'hhi': hhi,
            'multiplier': concentration_penalty,
            'impact': base_score * (1 - concentration_penalty)
        }
        base_score *= concentration_penalty

    # ============================================================================
    # FINAL WQS
    # ============================================================================
    final_wqs = min(100, max(0, base_score))

    # ============================================================================
    # CONFIDENCE LEVEL
    # ============================================================================
    if total_trades < 10:
        confidence = "VERY_LOW"
    elif total_trades < 30:
        confidence = "LOW"
    elif total_trades < 50:
        confidence = "MEDIUM"
    elif total_trades < 100:
        confidence = "HIGH"
    else:
        confidence = "VERY_HIGH"

    # ============================================================================
    # BAYESIAN ADJUSTED WIN RATE (for reference)
    # ============================================================================
    wins = sum(1 for pnl in pnls if pnl > 0)
    losses = sum(1 for pnl in pnls if pnl <= 0)

    bayesian_result = calculate_adjusted_win_rate(wins, losses, category)

    return {
        'wqs': final_wqs,
        'components': {
            'sharpe': {
                'score': sharpe_score,
                'raw_value': sharpe_ratio,
                'weight': 0.30
            },
            'information_ratio': {
                'score': ir_score,
                'raw_value': ir,
                'weight': 0.25
            },
            'calmar': {
                'score': calmar_score,
                'raw_value': calmar,
                'weight': 0.20
            },
            'consistency': {
                'score': consistency_score,
                'raw_value': consistency_result.get('rolling_sharpe_std'),
                'weight': 0.15
            },
            'volume': {
                'score': volume_score,
                'raw_value': total_volume,
                'weight': 0.10
            }
        },
        'penalties': penalties,
        'confidence': confidence,
        'total_trades': total_trades,
        'total_volume': total_volume,
        'bayesian_win_rate': bayesian_result['adjusted_win_rate'],
        'raw_win_rate': wins / total_trades if total_trades > 0 else 0,
        'hhi_concentration': hhi
    }


# Example usage
if __name__ == "__main__":
    print("="*80)
    print("ENHANCED WHALE QUALITY SCORE (WQS) DEMO")
    print("="*80)

    # Simulate whale trade data
    np.random.seed(42)

    # Test Case 1: Elite whale (high Sharpe, consistent, high volume)
    print("\n📊 Test Case 1: Elite Whale")
    print("-"*80)

    elite_trades = []
    base_date = datetime.now() - timedelta(days=180)

    for i in range(120):
        elite_trades.append({
            'timestamp': base_date + timedelta(days=i),
            'pnl': np.random.normal(loc=80, scale=25),  # Good mean, low vol
            'market_id': f'market_{i % 10}',  # Diversified across 10 markets
            'volume': np.random.uniform(5000, 15000)
        })

    result = calculate_enhanced_wqs(elite_trades, MarketCategory.POLITICS)

    print(f"WQS:                   {result['wqs']:.1f} / 100")
    print(f"Confidence:            {result['confidence']}")
    print(f"Total trades:          {result['total_trades']}")
    print(f"Total volume:          ${result['total_volume']:,.0f}")
    print(f"HHI concentration:     {result['hhi_concentration']:.0f}")
    print("\nComponent Breakdown:")
    for comp, data in result['components'].items():
        print(f"  {comp:20} {data['score']:5.1f} pts (raw: {data['raw_value']:.2f})")
    if result['penalties']:
        print("\nPenalties Applied:")
        for penalty, data in result['penalties'].items():
            print(f"  {penalty}: -{data['impact']:.1f} pts")

    # Test Case 2: Mediocre whale (lower scores)
    print("\n📊 Test Case 2: Mediocre Whale")
    print("-"*80)

    mediocre_trades = []
    for i in range(40):  # Fewer trades
        mediocre_trades.append({
            'timestamp': base_date + timedelta(days=i*2),
            'pnl': np.random.normal(loc=20, scale=50),  # Lower mean, higher vol
            'market_id': f'market_{i % 3}',  # Concentrated in 3 markets
            'volume': np.random.uniform(1000, 3000)
        })

    result = calculate_enhanced_wqs(mediocre_trades, MarketCategory.CRYPTO)

    print(f"WQS:                   {result['wqs']:.1f} / 100")
    print(f"Confidence:            {result['confidence']}")
    print(f"HHI concentration:     {result['hhi_concentration']:.0f}")
    print("\nComponent Breakdown:")
    for comp, data in result['components'].items():
        print(f"  {comp:20} {data['score']:5.1f} pts")
    if result['penalties']:
        print("\nPenalties Applied:")
        for penalty, data in result['penalties'].items():
            print(f"  {penalty}: multiplier {data['multiplier']:.2f}")

    print("\n" + "="*80)
    print("✅ Enhanced WQS successfully differentiates whale quality")
    print("="*80)

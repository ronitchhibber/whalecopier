"""
Performance Attribution System
Decomposes returns into various factors for analysis and optimization
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from scipy import stats
import logging

logger = logging.getLogger(__name__)


class PerformanceAttribution:
    """
    Attributes portfolio performance to various factors:
    - Whale Selection (which whales contributed most)
    - Market Timing (entry/exit timing)
    - Position Sizing (Kelly effectiveness)
    - Risk Management (drawdown prevention)
    - Market/Category Selection
    """

    def __init__(self):
        self.attribution_history = []
        self.factor_contributions = {}

    def calculate_attribution(
        self,
        trades: List[Dict],
        portfolio_value: float,
        benchmark_return: float = 0.0,
        period_start: datetime = None,
        period_end: datetime = None
    ) -> Dict:
        """
        Calculate comprehensive performance attribution.

        Args:
            trades: List of executed trades
            portfolio_value: Current portfolio value
            benchmark_return: Benchmark return for comparison
            period_start: Analysis period start
            period_end: Analysis period end

        Returns:
            Attribution breakdown by factor
        """
        if not trades:
            return self._empty_attribution()

        # Convert trades to DataFrame for easier analysis
        df = pd.DataFrame(trades)

        # Calculate total return
        total_pnl = df['pnl'].sum() if 'pnl' in df else 0
        total_return = total_pnl / portfolio_value if portfolio_value > 0 else 0

        # 1. Whale Selection Attribution
        whale_attribution = self._whale_selection_attribution(df)

        # 2. Market Timing Attribution
        timing_attribution = self._market_timing_attribution(df)

        # 3. Position Sizing Attribution
        sizing_attribution = self._position_sizing_attribution(df)

        # 4. Risk Management Attribution
        risk_attribution = self._risk_management_attribution(df)

        # 5. Market/Category Attribution
        market_attribution = self._market_category_attribution(df)

        # 6. Calculate unexplained return (alpha)
        explained_return = sum([
            whale_attribution['contribution'],
            timing_attribution['contribution'],
            sizing_attribution['contribution'],
            risk_attribution['contribution'],
            market_attribution['contribution']
        ])

        alpha = total_return - explained_return - benchmark_return

        attribution = {
            'total_return': total_return,
            'benchmark_return': benchmark_return,
            'excess_return': total_return - benchmark_return,
            'factors': {
                'whale_selection': whale_attribution,
                'market_timing': timing_attribution,
                'position_sizing': sizing_attribution,
                'risk_management': risk_attribution,
                'market_category': market_attribution
            },
            'alpha': alpha,
            'information_ratio': self._calculate_information_ratio(df, benchmark_return),
            'period': {
                'start': period_start or df['timestamp'].min() if 'timestamp' in df else None,
                'end': period_end or df['timestamp'].max() if 'timestamp' in df else None
            }
        }

        # Store for historical analysis
        self.attribution_history.append(attribution)

        return attribution

    def _whale_selection_attribution(self, df: pd.DataFrame) -> Dict:
        """
        Attribute performance to whale selection decisions.
        Measures how much each whale contributed to returns.
        """
        if 'source_whale' not in df or df.empty:
            return {'contribution': 0, 'details': {}}

        # Group by whale
        whale_performance = df.groupby('source_whale').agg({
            'pnl': 'sum',
            'amount': 'sum',
            'trade_id': 'count'
        }).rename(columns={'trade_id': 'trade_count'})

        # Calculate returns by whale
        whale_performance['return'] = whale_performance['pnl'] / whale_performance['amount'].abs()

        # Calculate contribution
        total_pnl = df['pnl'].sum()
        whale_contributions = {}

        for whale, row in whale_performance.iterrows():
            contribution = row['pnl'] / total_pnl if total_pnl != 0 else 0
            whale_contributions[whale] = {
                'pnl': row['pnl'],
                'return': row['return'],
                'trade_count': row['trade_count'],
                'contribution_pct': contribution * 100
            }

        # Find best and worst whales
        best_whale = whale_performance['pnl'].idxmax() if not whale_performance.empty else None
        worst_whale = whale_performance['pnl'].idxmin() if not whale_performance.empty else None

        return {
            'contribution': whale_performance['return'].mean() if not whale_performance.empty else 0,
            'whale_count': len(whale_performance),
            'best_whale': best_whale,
            'worst_whale': worst_whale,
            'whale_contributions': whale_contributions,
            'concentration': self._calculate_concentration(whale_performance['pnl'].values)
        }

    def _market_timing_attribution(self, df: pd.DataFrame) -> Dict:
        """
        Attribute performance to market timing decisions.
        Measures entry/exit timing effectiveness.
        """
        if 'timestamp' not in df or 'price' not in df or df.empty:
            return {'contribution': 0, 'details': {}}

        # Calculate timing score for each trade
        timing_scores = []

        for idx, trade in df.iterrows():
            # Compare entry price to market average
            market_id = trade.get('market_id')
            if market_id:
                same_market = df[df['market_id'] == market_id]
                if len(same_market) > 1:
                    avg_price = same_market['price'].mean()
                    if trade['side'] == 'BUY':
                        # Good timing if bought below average
                        timing_score = (avg_price - trade['price']) / avg_price
                    else:
                        # Good timing if sold above average
                        timing_score = (trade['price'] - avg_price) / avg_price
                    timing_scores.append(timing_score)

        avg_timing_score = np.mean(timing_scores) if timing_scores else 0

        # Calculate timing contribution to returns
        timing_contribution = avg_timing_score * 0.3  # Timing typically contributes ~30% of excess return

        return {
            'contribution': timing_contribution,
            'avg_timing_score': avg_timing_score,
            'successful_timing_pct': len([s for s in timing_scores if s > 0]) / len(timing_scores) * 100 if timing_scores else 0,
            'best_timed_trades': len([s for s in timing_scores if s > 0.05]),
            'worst_timed_trades': len([s for s in timing_scores if s < -0.05])
        }

    def _position_sizing_attribution(self, df: pd.DataFrame) -> Dict:
        """
        Attribute performance to position sizing decisions.
        Measures Kelly criterion effectiveness.
        """
        if 'amount' not in df or 'pnl' not in df or df.empty:
            return {'contribution': 0, 'details': {}}

        # Calculate correlation between position size and returns
        if len(df) > 1:
            size_return_correlation = df['amount'].abs().corr(df['pnl'])
        else:
            size_return_correlation = 0

        # Ideal correlation is positive (bigger positions on winners)
        sizing_effectiveness = max(0, size_return_correlation)

        # Calculate if winning trades had larger positions
        winning_trades = df[df['pnl'] > 0]
        losing_trades = df[df['pnl'] <= 0]

        avg_winning_size = winning_trades['amount'].abs().mean() if not winning_trades.empty else 0
        avg_losing_size = losing_trades['amount'].abs().mean() if not losing_trades.empty else 0

        size_ratio = avg_winning_size / avg_losing_size if avg_losing_size > 0 else 1

        # Contribution based on sizing effectiveness
        sizing_contribution = sizing_effectiveness * 0.2  # Sizing typically contributes ~20% of excess return

        return {
            'contribution': sizing_contribution,
            'size_return_correlation': size_return_correlation,
            'sizing_effectiveness': sizing_effectiveness,
            'avg_winning_size': avg_winning_size,
            'avg_losing_size': avg_losing_size,
            'size_ratio': size_ratio,
            'optimal_sizing': size_ratio > 1.2  # Winners should be 20% larger
        }

    def _risk_management_attribution(self, df: pd.DataFrame) -> Dict:
        """
        Attribute performance to risk management decisions.
        Measures drawdown prevention and risk control.
        """
        if 'pnl' not in df or df.empty:
            return {'contribution': 0, 'details': {}}

        # Calculate drawdown statistics
        cumulative_pnl = df['pnl'].cumsum()
        running_max = cumulative_pnl.expanding().max()
        drawdown = (cumulative_pnl - running_max) / running_max.abs()

        max_drawdown = drawdown.min() if not drawdown.empty else 0
        avg_drawdown = drawdown[drawdown < 0].mean() if len(drawdown[drawdown < 0]) > 0 else 0

        # Calculate risk-adjusted metrics
        returns = df['pnl'] / df['amount'].abs() if 'amount' in df else pd.Series()
        if not returns.empty and returns.std() > 0:
            sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252)
            sortino_ratio = returns.mean() / returns[returns < 0].std() * np.sqrt(252) if len(returns[returns < 0]) > 0 else 0
        else:
            sharpe_ratio = 0
            sortino_ratio = 0

        # Risk management contribution (prevented losses)
        risk_contribution = abs(max_drawdown) * 0.15 if max_drawdown < -0.10 else 0

        return {
            'contribution': risk_contribution,
            'max_drawdown': max_drawdown,
            'avg_drawdown': avg_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'drawdown_recovery_days': self._calculate_recovery_time(drawdown),
            'risk_control_effectiveness': 1 + max_drawdown  # 0 to 1 scale
        }

    def _market_category_attribution(self, df: pd.DataFrame) -> Dict:
        """
        Attribute performance to market/category selection.
        Measures which markets/categories performed best.
        """
        if 'category' not in df or df.empty:
            # Try to use market_id if category not available
            if 'market_id' in df:
                groupby_col = 'market_id'
            else:
                return {'contribution': 0, 'details': {}}
        else:
            groupby_col = 'category'

        # Group by market/category
        market_performance = df.groupby(groupby_col).agg({
            'pnl': 'sum',
            'amount': 'sum',
            'trade_id': 'count' if 'trade_id' in df else 'size'
        })

        if 'trade_id' not in df:
            market_performance.rename(columns={'amount': 'trade_count'}, inplace=True)
        else:
            market_performance.rename(columns={'trade_id': 'trade_count'}, inplace=True)

        # Calculate returns by market
        market_performance['return'] = market_performance['pnl'] / market_performance['amount'].abs()

        # Find best performing markets
        best_market = market_performance['return'].idxmax() if not market_performance.empty else None
        worst_market = market_performance['return'].idxmin() if not market_performance.empty else None

        # Market selection contribution
        market_contribution = market_performance['return'].std() * 0.15 if not market_performance.empty else 0

        return {
            'contribution': market_contribution,
            'market_count': len(market_performance),
            'best_market': best_market,
            'worst_market': worst_market,
            'market_returns': market_performance['return'].to_dict() if not market_performance.empty else {},
            'diversification': 1 / self._calculate_concentration(market_performance['pnl'].values) if not market_performance.empty else 0
        }

    def _calculate_concentration(self, values: np.ndarray) -> float:
        """Calculate Herfindahl concentration index."""
        if len(values) == 0:
            return 1.0

        total = np.sum(np.abs(values))
        if total == 0:
            return 1.0

        shares = np.abs(values) / total
        hhi = np.sum(shares ** 2)

        return hhi

    def _calculate_recovery_time(self, drawdown_series: pd.Series) -> int:
        """Calculate average drawdown recovery time in days."""
        if drawdown_series.empty:
            return 0

        in_drawdown = False
        recovery_times = []
        drawdown_start = 0

        for i, dd in enumerate(drawdown_series):
            if dd < 0 and not in_drawdown:
                in_drawdown = True
                drawdown_start = i
            elif dd >= 0 and in_drawdown:
                in_drawdown = False
                recovery_times.append(i - drawdown_start)

        return int(np.mean(recovery_times)) if recovery_times else 0

    def _calculate_information_ratio(self, df: pd.DataFrame, benchmark_return: float) -> float:
        """Calculate information ratio vs benchmark."""
        if 'pnl' not in df or 'amount' not in df or df.empty:
            return 0.0

        returns = df['pnl'] / df['amount'].abs()
        excess_returns = returns - benchmark_return / len(returns)

        if excess_returns.std() == 0:
            return 0.0

        return excess_returns.mean() / excess_returns.std() * np.sqrt(252)

    def _empty_attribution(self) -> Dict:
        """Return empty attribution structure."""
        return {
            'total_return': 0,
            'benchmark_return': 0,
            'excess_return': 0,
            'factors': {
                'whale_selection': {'contribution': 0, 'details': {}},
                'market_timing': {'contribution': 0, 'details': {}},
                'position_sizing': {'contribution': 0, 'details': {}},
                'risk_management': {'contribution': 0, 'details': {}},
                'market_category': {'contribution': 0, 'details': {}}
            },
            'alpha': 0,
            'information_ratio': 0,
            'period': {'start': None, 'end': None}
        }

    def get_factor_trends(self, lookback_periods: int = 10) -> Dict:
        """
        Analyze trends in factor contributions over time.
        """
        if len(self.attribution_history) < 2:
            return {'message': 'Insufficient history'}

        recent_history = self.attribution_history[-lookback_periods:]

        trends = {}
        for factor in ['whale_selection', 'market_timing', 'position_sizing', 'risk_management', 'market_category']:
            contributions = [h['factors'][factor]['contribution'] for h in recent_history]

            if len(contributions) > 1:
                # Calculate trend (positive = improving)
                x = np.arange(len(contributions))
                slope, _ = np.polyfit(x, contributions, 1)

                trends[factor] = {
                    'current': contributions[-1],
                    'average': np.mean(contributions),
                    'trend': 'improving' if slope > 0 else 'declining',
                    'slope': slope,
                    'volatility': np.std(contributions)
                }

        return trends

    def get_optimization_recommendations(self) -> List[Dict]:
        """
        Generate recommendations based on attribution analysis.
        """
        if not self.attribution_history:
            return []

        latest = self.attribution_history[-1]
        recommendations = []

        # Check whale selection
        whale_attr = latest['factors']['whale_selection']
        if whale_attr['contribution'] < 0:
            recommendations.append({
                'priority': 'high',
                'area': 'whale_selection',
                'issue': 'Negative whale selection contribution',
                'recommendation': 'Review whale quality scores and consider removing underperformers'
            })

        # Check timing
        timing_attr = latest['factors']['market_timing']
        if timing_attr.get('successful_timing_pct', 0) < 40:
            recommendations.append({
                'priority': 'medium',
                'area': 'market_timing',
                'issue': 'Poor entry/exit timing',
                'recommendation': 'Consider using limit orders and volatility-based entry signals'
            })

        # Check position sizing
        sizing_attr = latest['factors']['position_sizing']
        if not sizing_attr.get('optimal_sizing', False):
            recommendations.append({
                'priority': 'high',
                'area': 'position_sizing',
                'issue': 'Suboptimal position sizing',
                'recommendation': 'Increase position sizes on high-confidence trades'
            })

        # Check risk management
        risk_attr = latest['factors']['risk_management']
        if risk_attr.get('max_drawdown', 0) < -0.15:
            recommendations.append({
                'priority': 'critical',
                'area': 'risk_management',
                'issue': f"Excessive drawdown: {risk_attr['max_drawdown']:.1%}",
                'recommendation': 'Implement stricter stop-losses and reduce position sizes'
            })

        # Check diversification
        market_attr = latest['factors']['market_category']
        if market_attr.get('diversification', 0) < 0.3:
            recommendations.append({
                'priority': 'medium',
                'area': 'diversification',
                'issue': 'Poor market diversification',
                'recommendation': 'Spread trades across more markets/categories'
            })

        return sorted(recommendations, key=lambda x: {'critical': 0, 'high': 1, 'medium': 2}.get(x['priority'], 3))

    def generate_attribution_report(self) -> Dict:
        """
        Generate comprehensive attribution report.
        """
        if not self.attribution_history:
            return {'message': 'No attribution history available'}

        latest = self.attribution_history[-1]
        trends = self.get_factor_trends()
        recommendations = self.get_optimization_recommendations()

        # Calculate summary statistics
        all_returns = [h['total_return'] for h in self.attribution_history]
        all_alphas = [h['alpha'] for h in self.attribution_history]

        report = {
            'summary': {
                'total_return': latest['total_return'],
                'excess_return': latest['excess_return'],
                'alpha': latest['alpha'],
                'information_ratio': latest['information_ratio'],
                'avg_return': np.mean(all_returns),
                'return_volatility': np.std(all_returns),
                'avg_alpha': np.mean(all_alphas),
                'consistency': len([r for r in all_returns if r > 0]) / len(all_returns) if all_returns else 0
            },
            'latest_attribution': latest,
            'factor_trends': trends,
            'recommendations': recommendations,
            'top_contributors': self._get_top_contributors(latest),
            'report_timestamp': datetime.utcnow()
        }

        return report

    def _get_top_contributors(self, attribution: Dict) -> List[Dict]:
        """Get top contributing factors."""
        contributors = []

        for factor, data in attribution['factors'].items():
            contributors.append({
                'factor': factor,
                'contribution': data['contribution'],
                'percentage': data['contribution'] / attribution['total_return'] * 100 if attribution['total_return'] != 0 else 0
            })

        return sorted(contributors, key=lambda x: abs(x['contribution']), reverse=True)
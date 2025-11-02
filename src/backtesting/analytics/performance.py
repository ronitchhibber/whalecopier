"""
Performance Analytics Module for Backtesting
Calculates comprehensive performance metrics and generates reports
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging
from scipy import stats
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Complete performance metrics for a strategy."""
    # Returns
    total_return: float
    annualized_return: float
    cumulative_return: float

    # Risk metrics
    volatility: float
    downside_volatility: float
    max_drawdown: float
    max_drawdown_duration: int  # days

    # Risk-adjusted returns
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    information_ratio: float

    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    expectancy: float

    # Distribution metrics
    skewness: float
    kurtosis: float
    value_at_risk_95: float
    conditional_var_95: float

    # Consistency metrics
    consistency_score: float
    monthly_win_rate: float
    longest_winning_streak: int
    longest_losing_streak: int

    # Additional metrics
    recovery_factor: float
    ulcer_index: float
    omega_ratio: float
    tail_ratio: float


class PerformanceAnalyzer:
    """
    Comprehensive performance analysis for backtesting results.

    Calculates all standard and advanced metrics needed to evaluate
    trading strategy performance.
    """

    def __init__(self, config: Dict = None):
        """Initialize performance analyzer."""
        self.config = config or self._default_config()

        # Data storage
        self.equity_curve = []
        self.returns = []
        self.trades = []
        self.positions = []

        # Cached calculations
        self._cached_metrics = None
        self._cache_timestamp = None

    def _default_config(self) -> Dict:
        """Default configuration for analytics."""
        return {
            'risk_free_rate': 0.02,  # 2% annual
            'benchmark_return': 0.10,  # 10% annual benchmark
            'confidence_level': 0.95,
            'min_periods': 30,  # Minimum periods for calculations
            'annualization_factor': 252,  # Trading days per year
            'target_return': 0.0,  # For Sortino/Omega
            'var_method': 'historical',  # or 'parametric', 'cornish_fisher'
        }

    def add_data_point(
        self,
        timestamp: datetime,
        equity: float,
        positions: Dict[str, float],
        trades: List[Dict] = None
    ):
        """
        Add a data point to the performance tracker.

        Args:
            timestamp: Current time
            equity: Total equity value
            positions: Current positions
            trades: Any trades executed at this time
        """
        # Update equity curve
        self.equity_curve.append({
            'timestamp': timestamp,
            'equity': equity,
            'positions': positions.copy()
        })

        # Calculate return if we have previous data
        if len(self.equity_curve) > 1:
            prev_equity = self.equity_curve[-2]['equity']
            if prev_equity > 0:
                ret = (equity - prev_equity) / prev_equity
                self.returns.append(ret)

        # Store positions
        self.positions.append({
            'timestamp': timestamp,
            'positions': positions.copy(),
            'total_exposure': sum(abs(p) for p in positions.values())
        })

        # Store trades
        if trades:
            for trade in trades:
                trade['timestamp'] = timestamp
                self.trades.append(trade)

        # Invalidate cache
        self._cached_metrics = None

    def calculate_metrics(self, force_recalculate: bool = False) -> PerformanceMetrics:
        """
        Calculate comprehensive performance metrics.

        Args:
            force_recalculate: Force recalculation even if cached

        Returns:
            PerformanceMetrics object with all calculations
        """
        # Check cache
        if not force_recalculate and self._cached_metrics:
            return self._cached_metrics

        if len(self.returns) < self.config['min_periods']:
            logger.warning(f"Insufficient data: {len(self.returns)} returns, need {self.config['min_periods']}")
            return self._empty_metrics()

        # Convert to numpy for calculations
        returns_array = np.array(self.returns)

        # Basic return metrics
        total_return = self._calculate_total_return()
        annualized_return = self._annualize_return(total_return)
        cumulative_return = (1 + returns_array).prod() - 1

        # Risk metrics
        volatility = self._calculate_volatility(returns_array)
        downside_vol = self._calculate_downside_volatility(returns_array)
        max_dd, max_dd_duration = self._calculate_max_drawdown()

        # Risk-adjusted returns
        sharpe = self._calculate_sharpe_ratio(returns_array, volatility)
        sortino = self._calculate_sortino_ratio(returns_array, downside_vol)
        calmar = self._calculate_calmar_ratio(annualized_return, max_dd)
        info_ratio = self._calculate_information_ratio(returns_array)

        # Trade statistics
        trade_stats = self._calculate_trade_statistics()

        # Distribution metrics
        skewness = stats.skew(returns_array)
        kurtosis = stats.kurtosis(returns_array)
        var_95 = self._calculate_value_at_risk(returns_array, 0.95)
        cvar_95 = self._calculate_conditional_var(returns_array, 0.95)

        # Consistency metrics
        consistency = self._calculate_consistency_score(returns_array)
        monthly_wr = self._calculate_monthly_win_rate()
        win_streak, lose_streak = self._calculate_streaks()

        # Additional metrics
        recovery = self._calculate_recovery_factor(total_return, max_dd)
        ulcer = self._calculate_ulcer_index()
        omega = self._calculate_omega_ratio(returns_array)
        tail = self._calculate_tail_ratio(returns_array)

        # Create metrics object
        metrics = PerformanceMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            cumulative_return=cumulative_return,
            volatility=volatility,
            downside_volatility=downside_vol,
            max_drawdown=max_dd,
            max_drawdown_duration=max_dd_duration,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            information_ratio=info_ratio,
            total_trades=trade_stats['total_trades'],
            winning_trades=trade_stats['winning_trades'],
            losing_trades=trade_stats['losing_trades'],
            win_rate=trade_stats['win_rate'],
            avg_win=trade_stats['avg_win'],
            avg_loss=trade_stats['avg_loss'],
            profit_factor=trade_stats['profit_factor'],
            expectancy=trade_stats['expectancy'],
            skewness=skewness,
            kurtosis=kurtosis,
            value_at_risk_95=var_95,
            conditional_var_95=cvar_95,
            consistency_score=consistency,
            monthly_win_rate=monthly_wr,
            longest_winning_streak=win_streak,
            longest_losing_streak=lose_streak,
            recovery_factor=recovery,
            ulcer_index=ulcer,
            omega_ratio=omega,
            tail_ratio=tail
        )

        # Cache results
        self._cached_metrics = metrics
        self._cache_timestamp = datetime.utcnow()

        return metrics

    def _calculate_total_return(self) -> float:
        """Calculate total return from equity curve."""
        if len(self.equity_curve) < 2:
            return 0.0

        initial_equity = self.equity_curve[0]['equity']
        final_equity = self.equity_curve[-1]['equity']

        if initial_equity > 0:
            return (final_equity - initial_equity) / initial_equity
        return 0.0

    def _annualize_return(self, total_return: float) -> float:
        """Annualize return based on period length."""
        if len(self.equity_curve) < 2:
            return 0.0

        start_time = self.equity_curve[0]['timestamp']
        end_time = self.equity_curve[-1]['timestamp']
        years = (end_time - start_time).days / 365.25

        if years > 0:
            return (1 + total_return) ** (1 / years) - 1
        return total_return

    def _calculate_volatility(self, returns: np.ndarray) -> float:
        """Calculate annualized volatility."""
        if len(returns) < 2:
            return 0.0

        daily_vol = returns.std()
        annual_vol = daily_vol * np.sqrt(self.config['annualization_factor'])
        return annual_vol

    def _calculate_downside_volatility(self, returns: np.ndarray) -> float:
        """Calculate downside volatility (for Sortino ratio)."""
        target = self.config['target_return'] / self.config['annualization_factor']
        downside_returns = returns[returns < target]

        if len(downside_returns) < 2:
            return 0.0

        downside_vol = np.sqrt(np.mean(downside_returns ** 2))
        return downside_vol * np.sqrt(self.config['annualization_factor'])

    def _calculate_max_drawdown(self) -> Tuple[float, int]:
        """Calculate maximum drawdown and duration."""
        if len(self.equity_curve) < 2:
            return 0.0, 0

        equity_values = [e['equity'] for e in self.equity_curve]
        timestamps = [e['timestamp'] for e in self.equity_curve]

        # Calculate running maximum
        running_max = np.maximum.accumulate(equity_values)

        # Calculate drawdowns
        drawdowns = (np.array(equity_values) - running_max) / running_max

        # Find maximum drawdown
        max_dd = abs(drawdowns.min())

        # Calculate drawdown duration
        max_dd_idx = drawdowns.argmin()
        recovery_idx = max_dd_idx

        # Find recovery point
        for i in range(max_dd_idx, len(equity_values)):
            if equity_values[i] >= running_max[max_dd_idx]:
                recovery_idx = i
                break

        # Calculate duration in days
        if recovery_idx > max_dd_idx:
            duration = (timestamps[recovery_idx] - timestamps[max_dd_idx]).days
        else:
            # Still in drawdown
            duration = (timestamps[-1] - timestamps[max_dd_idx]).days

        return max_dd, duration

    def _calculate_sharpe_ratio(self, returns: np.ndarray, volatility: float) -> float:
        """Calculate Sharpe ratio."""
        if volatility == 0:
            return 0.0

        rf_rate = self.config['risk_free_rate'] / self.config['annualization_factor']
        excess_returns = returns - rf_rate

        return (excess_returns.mean() * self.config['annualization_factor']) / volatility

    def _calculate_sortino_ratio(self, returns: np.ndarray, downside_vol: float) -> float:
        """Calculate Sortino ratio."""
        if downside_vol == 0:
            return 0.0

        target = self.config['target_return'] / self.config['annualization_factor']
        excess_returns = returns - target

        return (excess_returns.mean() * self.config['annualization_factor']) / downside_vol

    def _calculate_calmar_ratio(self, annual_return: float, max_drawdown: float) -> float:
        """Calculate Calmar ratio."""
        if max_drawdown == 0:
            return 0.0

        return annual_return / max_drawdown

    def _calculate_information_ratio(self, returns: np.ndarray) -> float:
        """Calculate information ratio vs benchmark."""
        benchmark_return = self.config['benchmark_return'] / self.config['annualization_factor']
        excess_returns = returns - benchmark_return

        if len(excess_returns) < 2:
            return 0.0

        tracking_error = excess_returns.std() * np.sqrt(self.config['annualization_factor'])

        if tracking_error == 0:
            return 0.0

        return (excess_returns.mean() * self.config['annualization_factor']) / tracking_error

    def _calculate_trade_statistics(self) -> Dict:
        """Calculate trade-based statistics."""
        if not self.trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0,
                'expectancy': 0.0
            }

        # Calculate P&L for each trade
        trade_pnls = []
        for trade in self.trades:
            if 'pnl' in trade:
                trade_pnls.append(trade['pnl'])
            elif 'exit_price' in trade and 'entry_price' in trade:
                if trade['side'] == 'buy':
                    pnl = (trade['exit_price'] - trade['entry_price']) * trade['size']
                else:
                    pnl = (trade['entry_price'] - trade['exit_price']) * trade['size']
                trade_pnls.append(pnl)

        if not trade_pnls:
            return self._empty_trade_stats()

        trade_pnls = np.array(trade_pnls)
        winning_trades = trade_pnls[trade_pnls > 0]
        losing_trades = trade_pnls[trade_pnls < 0]

        total_trades = len(trade_pnls)
        num_winners = len(winning_trades)
        num_losers = len(losing_trades)

        win_rate = num_winners / total_trades if total_trades > 0 else 0
        avg_win = winning_trades.mean() if num_winners > 0 else 0
        avg_loss = abs(losing_trades.mean()) if num_losers > 0 else 0

        # Profit factor
        gross_profit = winning_trades.sum() if num_winners > 0 else 0
        gross_loss = abs(losing_trades.sum()) if num_losers > 0 else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Expectancy
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

        return {
            'total_trades': total_trades,
            'winning_trades': num_winners,
            'losing_trades': num_losers,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'expectancy': expectancy
        }

    def _calculate_value_at_risk(self, returns: np.ndarray, confidence: float) -> float:
        """Calculate Value at Risk."""
        method = self.config['var_method']

        if method == 'historical':
            # Historical VaR
            var = np.percentile(returns, (1 - confidence) * 100)

        elif method == 'parametric':
            # Parametric VaR (assumes normal distribution)
            mean = returns.mean()
            std = returns.std()
            z_score = stats.norm.ppf(1 - confidence)
            var = mean + z_score * std

        elif method == 'cornish_fisher':
            # Cornish-Fisher VaR (adjusts for skewness and kurtosis)
            var = self._cornish_fisher_var(returns, confidence)

        else:
            var = 0.0

        return abs(var) * np.sqrt(self.config['annualization_factor'])

    def _cornish_fisher_var(self, returns: np.ndarray, confidence: float) -> float:
        """Calculate Cornish-Fisher adjusted VaR."""
        mean = returns.mean()
        std = returns.std()
        skew = stats.skew(returns)
        kurt = stats.kurtosis(returns)

        z = stats.norm.ppf(1 - confidence)

        # Cornish-Fisher expansion
        z_cf = z + (z**2 - 1) * skew / 6 + \
               (z**3 - 3*z) * kurt / 24 - \
               (2*z**3 - 5*z) * skew**2 / 36

        return mean + z_cf * std

    def _calculate_conditional_var(self, returns: np.ndarray, confidence: float) -> float:
        """Calculate Conditional VaR (Expected Shortfall)."""
        var = self._calculate_value_at_risk(returns, confidence) / np.sqrt(self.config['annualization_factor'])

        # Get returns worse than VaR
        tail_returns = returns[returns < -abs(var)]

        if len(tail_returns) == 0:
            return var

        cvar = abs(tail_returns.mean()) * np.sqrt(self.config['annualization_factor'])
        return cvar

    def _calculate_consistency_score(self, returns: np.ndarray) -> float:
        """Calculate consistency score (0-100)."""
        if len(returns) < 2:
            return 0.0

        # Factors for consistency
        positive_periods = (returns > 0).mean()  # Percentage of positive returns

        # Rolling Sharpe stability
        if len(returns) > 30:
            rolling_sharpes = []
            for i in range(30, len(returns)):
                window = returns[i-30:i]
                vol = window.std()
                if vol > 0:
                    sharpe = (window.mean() / vol) * np.sqrt(252)
                    rolling_sharpes.append(sharpe)

            if rolling_sharpes:
                sharpe_stability = 1 - (np.std(rolling_sharpes) / (abs(np.mean(rolling_sharpes)) + 1))
            else:
                sharpe_stability = 0.5
        else:
            sharpe_stability = 0.5

        # Return distribution consistency
        return_stability = 1 - min(1, abs(stats.skew(returns)))

        # Combine factors
        consistency = (positive_periods * 0.4 + sharpe_stability * 0.4 + return_stability * 0.2) * 100

        return max(0, min(100, consistency))

    def _calculate_monthly_win_rate(self) -> float:
        """Calculate win rate at monthly level."""
        if not self.equity_curve:
            return 0.0

        # Group by month
        monthly_returns = defaultdict(list)

        for i in range(1, len(self.equity_curve)):
            current = self.equity_curve[i]
            previous = self.equity_curve[i-1]

            month_key = current['timestamp'].strftime('%Y-%m')

            if previous['equity'] > 0:
                ret = (current['equity'] - previous['equity']) / previous['equity']
                monthly_returns[month_key].append(ret)

        # Calculate monthly aggregates
        winning_months = 0
        total_months = 0

        for month, returns in monthly_returns.items():
            if returns:
                monthly_return = np.prod([1 + r for r in returns]) - 1
                if monthly_return > 0:
                    winning_months += 1
                total_months += 1

        return winning_months / total_months if total_months > 0 else 0.0

    def _calculate_streaks(self) -> Tuple[int, int]:
        """Calculate longest winning and losing streaks."""
        if not self.trades:
            return 0, 0

        current_win_streak = 0
        current_lose_streak = 0
        max_win_streak = 0
        max_lose_streak = 0

        for trade in self.trades:
            pnl = trade.get('pnl', 0)

            if pnl > 0:
                current_win_streak += 1
                current_lose_streak = 0
                max_win_streak = max(max_win_streak, current_win_streak)
            elif pnl < 0:
                current_lose_streak += 1
                current_win_streak = 0
                max_lose_streak = max(max_lose_streak, current_lose_streak)

        return max_win_streak, max_lose_streak

    def _calculate_recovery_factor(self, total_return: float, max_drawdown: float) -> float:
        """Calculate recovery factor."""
        if max_drawdown == 0:
            return 0.0

        initial_equity = self.equity_curve[0]['equity'] if self.equity_curve else 0
        total_profit = total_return * initial_equity

        return abs(total_profit) / max_drawdown if max_drawdown > 0 else 0.0

    def _calculate_ulcer_index(self) -> float:
        """Calculate Ulcer Index (measures downside volatility)."""
        if len(self.equity_curve) < 2:
            return 0.0

        equity_values = np.array([e['equity'] for e in self.equity_curve])

        # Calculate running maximum
        running_max = np.maximum.accumulate(equity_values)

        # Calculate percentage drawdowns
        drawdowns = ((equity_values - running_max) / running_max) * 100

        # Ulcer Index is RMS of drawdowns
        ulcer = np.sqrt(np.mean(drawdowns ** 2))

        return ulcer

    def _calculate_omega_ratio(self, returns: np.ndarray) -> float:
        """Calculate Omega ratio."""
        threshold = self.config['target_return'] / self.config['annualization_factor']

        gains = returns[returns > threshold] - threshold
        losses = threshold - returns[returns <= threshold]

        if len(losses) == 0 or losses.sum() == 0:
            return 0.0

        return gains.sum() / losses.sum()

    def _calculate_tail_ratio(self, returns: np.ndarray) -> float:
        """Calculate tail ratio (right tail / left tail)."""
        if len(returns) < 20:
            return 0.0

        # Use 95th and 5th percentiles
        right_tail = abs(np.percentile(returns, 95))
        left_tail = abs(np.percentile(returns, 5))

        if left_tail == 0:
            return 0.0

        return right_tail / left_tail

    def _empty_metrics(self) -> PerformanceMetrics:
        """Return empty metrics when insufficient data."""
        return PerformanceMetrics(
            total_return=0, annualized_return=0, cumulative_return=0,
            volatility=0, downside_volatility=0, max_drawdown=0, max_drawdown_duration=0,
            sharpe_ratio=0, sortino_ratio=0, calmar_ratio=0, information_ratio=0,
            total_trades=0, winning_trades=0, losing_trades=0, win_rate=0,
            avg_win=0, avg_loss=0, profit_factor=0, expectancy=0,
            skewness=0, kurtosis=0, value_at_risk_95=0, conditional_var_95=0,
            consistency_score=0, monthly_win_rate=0, longest_winning_streak=0,
            longest_losing_streak=0, recovery_factor=0, ulcer_index=0,
            omega_ratio=0, tail_ratio=0
        )

    def _empty_trade_stats(self) -> Dict:
        """Return empty trade statistics."""
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'profit_factor': 0.0,
            'expectancy': 0.0
        }

    def generate_report(self) -> Dict:
        """Generate comprehensive performance report."""
        metrics = self.calculate_metrics()

        report = {
            'summary': {
                'total_return': f"{metrics.total_return:.2%}",
                'annualized_return': f"{metrics.annualized_return:.2%}",
                'sharpe_ratio': f"{metrics.sharpe_ratio:.2f}",
                'max_drawdown': f"{metrics.max_drawdown:.2%}",
                'win_rate': f"{metrics.win_rate:.2%}"
            },
            'returns': {
                'total': metrics.total_return,
                'annualized': metrics.annualized_return,
                'cumulative': metrics.cumulative_return
            },
            'risk': {
                'volatility': metrics.volatility,
                'downside_volatility': metrics.downside_volatility,
                'max_drawdown': metrics.max_drawdown,
                'max_drawdown_duration_days': metrics.max_drawdown_duration,
                'value_at_risk_95': metrics.value_at_risk_95,
                'conditional_var_95': metrics.conditional_var_95,
                'ulcer_index': metrics.ulcer_index
            },
            'risk_adjusted': {
                'sharpe_ratio': metrics.sharpe_ratio,
                'sortino_ratio': metrics.sortino_ratio,
                'calmar_ratio': metrics.calmar_ratio,
                'information_ratio': metrics.information_ratio,
                'omega_ratio': metrics.omega_ratio
            },
            'trade_statistics': {
                'total_trades': metrics.total_trades,
                'win_rate': metrics.win_rate,
                'avg_win': metrics.avg_win,
                'avg_loss': metrics.avg_loss,
                'profit_factor': metrics.profit_factor,
                'expectancy': metrics.expectancy,
                'longest_win_streak': metrics.longest_winning_streak,
                'longest_lose_streak': metrics.longest_losing_streak
            },
            'distribution': {
                'skewness': metrics.skewness,
                'kurtosis': metrics.kurtosis,
                'tail_ratio': metrics.tail_ratio
            },
            'consistency': {
                'consistency_score': metrics.consistency_score,
                'monthly_win_rate': metrics.monthly_win_rate,
                'recovery_factor': metrics.recovery_factor
            },
            'data_points': {
                'total_days': len(self.equity_curve),
                'total_trades': len(self.trades),
                'start_date': self.equity_curve[0]['timestamp'].isoformat() if self.equity_curve else None,
                'end_date': self.equity_curve[-1]['timestamp'].isoformat() if self.equity_curve else None
            }
        }

        return report

    def export_results(self, filepath: str):
        """Export results to JSON file."""
        report = self.generate_report()

        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Performance report exported to {filepath}")
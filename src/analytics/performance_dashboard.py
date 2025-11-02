"""
Performance Analytics Dashboard for Polymarket Whale Copy Trading
Provides comprehensive analytics and visualization of trading performance
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass, field
from collections import defaultdict
import logging
import numpy as np
from enum import Enum

logger = logging.getLogger(__name__)


class TimeFrame(Enum):
    """Time frames for analysis"""
    HOURLY = "1h"
    DAILY = "1d"
    WEEKLY = "1w"
    MONTHLY = "1m"
    YEARLY = "1y"
    ALL_TIME = "all"


class MetricType(Enum):
    """Types of performance metrics"""
    RETURNS = "returns"
    VOLUME = "volume"
    WIN_RATE = "win_rate"
    SHARPE = "sharpe"
    SORTINO = "sortino"
    CALMAR = "calmar"
    MAX_DD = "max_drawdown"
    PROFIT_FACTOR = "profit_factor"


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics"""
    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    max_drawdown_duration: int  # days
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    best_trade: float
    worst_trade: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    consecutive_wins: int
    consecutive_losses: int
    recovery_factor: float
    payoff_ratio: float
    expectancy: float
    kelly_fraction: float
    var_95: float
    cvar_95: float
    skewness: float
    kurtosis: float
    ulcer_index: float
    information_ratio: float
    treynor_ratio: float
    omega_ratio: float


@dataclass
class WhalePerformance:
    """Individual whale performance tracking"""
    whale_address: str
    whale_name: Optional[str]
    metrics: PerformanceMetrics
    trade_history: List[Dict]
    position_history: List[Dict]
    pnl_curve: List[float]
    drawdown_curve: List[float]
    last_updated: datetime


@dataclass
class MarketAnalysis:
    """Market-level analysis"""
    market_id: str
    market_name: str
    total_volume: Decimal
    total_trades: int
    avg_trade_size: Decimal
    whale_participation: float  # % of trades from whales
    profitability: float
    volatility: float
    trending_direction: Optional[str]  # 'up', 'down', 'sideways'
    correlation_with_btc: float
    correlation_with_eth: float


class PerformanceAnalyzer:
    """
    Core performance analysis engine
    Calculates all metrics and statistics
    """

    def __init__(self):
        self.cache = {}
        self.benchmark_returns = None  # For relative performance

    def calculate_metrics(self, returns: np.ndarray, timeframe: TimeFrame = TimeFrame.DAILY) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics from returns"""

        if len(returns) < 2:
            return self._empty_metrics()

        # Basic statistics
        total_return = self._calculate_total_return(returns)
        annualized_return = self._annualize_return(total_return, len(returns), timeframe)
        volatility = self._calculate_volatility(returns, timeframe)

        # Risk-adjusted metrics
        sharpe = self._calculate_sharpe(returns, volatility, timeframe)
        sortino = self._calculate_sortino(returns, timeframe)
        calmar = self._calculate_calmar(annualized_return, returns)

        # Drawdown analysis
        dd_series = self._calculate_drawdown_series(returns)
        max_dd = np.min(dd_series) if len(dd_series) > 0 else 0
        max_dd_duration = self._calculate_max_dd_duration(dd_series)

        # Win/Loss analysis
        wins = returns[returns > 0]
        losses = returns[returns < 0]
        win_rate = len(wins) / len(returns) if len(returns) > 0 else 0
        avg_win = np.mean(wins) if len(wins) > 0 else 0
        avg_loss = np.mean(losses) if len(losses) > 0 else 0

        profit_factor = self._calculate_profit_factor(wins, losses)
        consecutive_wins, consecutive_losses = self._calculate_streaks(returns)

        # Advanced metrics
        kelly = self._calculate_kelly_criterion(win_rate, avg_win, abs(avg_loss))
        var_95, cvar_95 = self._calculate_var_cvar(returns)
        skewness = self._calculate_skewness(returns)
        kurtosis = self._calculate_kurtosis(returns)
        ulcer = self._calculate_ulcer_index(dd_series)

        # Expectancy
        expectancy = win_rate * avg_win + (1 - win_rate) * avg_loss

        # Recovery factor
        recovery_factor = total_return / abs(max_dd) if max_dd != 0 else 0

        # Payoff ratio
        payoff_ratio = avg_win / abs(avg_loss) if avg_loss != 0 else 0

        # Information ratio (needs benchmark)
        info_ratio = self._calculate_information_ratio(returns)

        # Treynor ratio (using market beta)
        treynor = self._calculate_treynor_ratio(returns)

        # Omega ratio
        omega = self._calculate_omega_ratio(returns)

        return PerformanceMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            volatility=volatility,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            max_drawdown=max_dd,
            max_drawdown_duration=max_dd_duration,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            best_trade=np.max(returns) if len(returns) > 0 else 0,
            worst_trade=np.min(returns) if len(returns) > 0 else 0,
            total_trades=len(returns),
            winning_trades=len(wins),
            losing_trades=len(losses),
            consecutive_wins=consecutive_wins,
            consecutive_losses=consecutive_losses,
            recovery_factor=recovery_factor,
            payoff_ratio=payoff_ratio,
            expectancy=expectancy,
            kelly_fraction=kelly,
            var_95=var_95,
            cvar_95=cvar_95,
            skewness=skewness,
            kurtosis=kurtosis,
            ulcer_index=ulcer,
            information_ratio=info_ratio,
            treynor_ratio=treynor,
            omega_ratio=omega
        )

    def _empty_metrics(self) -> PerformanceMetrics:
        """Return empty metrics when insufficient data"""
        return PerformanceMetrics(**{field.name: 0 for field in PerformanceMetrics.__dataclass_fields__.values()})

    def _calculate_total_return(self, returns: np.ndarray) -> float:
        """Calculate total cumulative return"""
        return np.prod(1 + returns) - 1

    def _annualize_return(self, total_return: float, periods: int, timeframe: TimeFrame) -> float:
        """Annualize returns based on timeframe"""
        periods_per_year = {
            TimeFrame.HOURLY: 24 * 365,
            TimeFrame.DAILY: 252,  # Trading days
            TimeFrame.WEEKLY: 52,
            TimeFrame.MONTHLY: 12,
            TimeFrame.YEARLY: 1
        }.get(timeframe, 252)

        if periods == 0:
            return 0

        years = periods / periods_per_year
        if years == 0:
            return 0

        return (1 + total_return) ** (1 / years) - 1

    def _calculate_volatility(self, returns: np.ndarray, timeframe: TimeFrame) -> float:
        """Calculate annualized volatility"""
        if len(returns) < 2:
            return 0

        periods_per_year = {
            TimeFrame.HOURLY: 24 * 365,
            TimeFrame.DAILY: 252,
            TimeFrame.WEEKLY: 52,
            TimeFrame.MONTHLY: 12,
            TimeFrame.YEARLY: 1
        }.get(timeframe, 252)

        return np.std(returns) * np.sqrt(periods_per_year)

    def _calculate_sharpe(self, returns: np.ndarray, volatility: float, timeframe: TimeFrame, risk_free: float = 0.02) -> float:
        """Calculate Sharpe ratio"""
        if volatility == 0:
            return 0

        periods_per_year = {
            TimeFrame.HOURLY: 24 * 365,
            TimeFrame.DAILY: 252,
            TimeFrame.WEEKLY: 52,
            TimeFrame.MONTHLY: 12,
            TimeFrame.YEARLY: 1
        }.get(timeframe, 252)

        rf_per_period = risk_free / periods_per_year
        excess_returns = returns - rf_per_period

        return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(periods_per_year) if np.std(excess_returns) > 0 else 0

    def _calculate_sortino(self, returns: np.ndarray, timeframe: TimeFrame, target: float = 0) -> float:
        """Calculate Sortino ratio (uses downside deviation)"""
        if len(returns) < 2:
            return 0

        periods_per_year = {
            TimeFrame.HOURLY: 24 * 365,
            TimeFrame.DAILY: 252,
            TimeFrame.WEEKLY: 52,
            TimeFrame.MONTHLY: 12,
            TimeFrame.YEARLY: 1
        }.get(timeframe, 252)

        downside_returns = returns[returns < target]
        if len(downside_returns) == 0:
            return 0

        downside_deviation = np.std(downside_returns)
        if downside_deviation == 0:
            return 0

        return (np.mean(returns) - target) / downside_deviation * np.sqrt(periods_per_year)

    def _calculate_calmar(self, annualized_return: float, returns: np.ndarray) -> float:
        """Calculate Calmar ratio"""
        dd_series = self._calculate_drawdown_series(returns)
        max_dd = abs(np.min(dd_series)) if len(dd_series) > 0 else 0

        if max_dd == 0:
            return 0

        return annualized_return / max_dd

    def _calculate_drawdown_series(self, returns: np.ndarray) -> np.ndarray:
        """Calculate drawdown series"""
        cumulative = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        return drawdown

    def _calculate_max_dd_duration(self, dd_series: np.ndarray) -> int:
        """Calculate maximum drawdown duration in periods"""
        if len(dd_series) == 0:
            return 0

        in_drawdown = dd_series < 0
        if not np.any(in_drawdown):
            return 0

        # Find consecutive periods in drawdown
        max_duration = 0
        current_duration = 0

        for is_dd in in_drawdown:
            if is_dd:
                current_duration += 1
                max_duration = max(max_duration, current_duration)
            else:
                current_duration = 0

        return max_duration

    def _calculate_profit_factor(self, wins: np.ndarray, losses: np.ndarray) -> float:
        """Calculate profit factor"""
        total_wins = np.sum(wins) if len(wins) > 0 else 0
        total_losses = abs(np.sum(losses)) if len(losses) > 0 else 0

        if total_losses == 0:
            return float('inf') if total_wins > 0 else 0

        return total_wins / total_losses

    def _calculate_streaks(self, returns: np.ndarray) -> Tuple[int, int]:
        """Calculate maximum consecutive wins and losses"""
        if len(returns) == 0:
            return 0, 0

        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0

        for ret in returns:
            if ret > 0:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            elif ret < 0:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)
            else:
                current_wins = 0
                current_losses = 0

        return max_wins, max_losses

    def _calculate_kelly_criterion(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """Calculate Kelly criterion for optimal bet sizing"""
        if avg_loss == 0 or win_rate == 0 or win_rate == 1:
            return 0

        b = avg_win / avg_loss  # Payoff ratio
        p = win_rate
        q = 1 - p

        kelly = (p * b - q) / b

        # Apply Kelly fraction (usually 0.25 for safety)
        return max(0, min(kelly * 0.25, 0.25))

    def _calculate_var_cvar(self, returns: np.ndarray, confidence: float = 0.95) -> Tuple[float, float]:
        """Calculate Value at Risk and Conditional VaR"""
        if len(returns) == 0:
            return 0, 0

        var = np.percentile(returns, (1 - confidence) * 100)
        cvar = np.mean(returns[returns <= var]) if np.any(returns <= var) else var

        return abs(var), abs(cvar)

    def _calculate_skewness(self, returns: np.ndarray) -> float:
        """Calculate skewness of returns"""
        if len(returns) < 3:
            return 0

        mean = np.mean(returns)
        std = np.std(returns)
        if std == 0:
            return 0

        return np.mean(((returns - mean) / std) ** 3)

    def _calculate_kurtosis(self, returns: np.ndarray) -> float:
        """Calculate excess kurtosis of returns"""
        if len(returns) < 4:
            return 0

        mean = np.mean(returns)
        std = np.std(returns)
        if std == 0:
            return 0

        return np.mean(((returns - mean) / std) ** 4) - 3

    def _calculate_ulcer_index(self, dd_series: np.ndarray) -> float:
        """Calculate Ulcer Index (measures downside volatility)"""
        if len(dd_series) == 0:
            return 0

        squared_dds = dd_series ** 2
        return np.sqrt(np.mean(squared_dds))

    def _calculate_information_ratio(self, returns: np.ndarray, benchmark_returns: np.ndarray = None) -> float:
        """Calculate Information Ratio"""
        if benchmark_returns is None:
            benchmark_returns = self.benchmark_returns

        if benchmark_returns is None or len(benchmark_returns) != len(returns):
            return 0

        active_returns = returns - benchmark_returns
        if np.std(active_returns) == 0:
            return 0

        return np.mean(active_returns) / np.std(active_returns) * np.sqrt(252)

    def _calculate_treynor_ratio(self, returns: np.ndarray, market_returns: np.ndarray = None, risk_free: float = 0.02) -> float:
        """Calculate Treynor Ratio"""
        if market_returns is None or len(returns) < 2:
            return 0

        # Calculate beta
        covariance = np.cov(returns, market_returns)[0, 1]
        market_variance = np.var(market_returns)

        if market_variance == 0:
            return 0

        beta = covariance / market_variance

        if beta == 0:
            return 0

        excess_return = np.mean(returns) - risk_free / 252
        return excess_return / beta * 252

    def _calculate_omega_ratio(self, returns: np.ndarray, threshold: float = 0) -> float:
        """Calculate Omega Ratio"""
        if len(returns) == 0:
            return 0

        gains = returns[returns > threshold] - threshold
        losses = threshold - returns[returns <= threshold]

        sum_gains = np.sum(gains) if len(gains) > 0 else 0
        sum_losses = np.sum(losses) if len(losses) > 0 else 0

        if sum_losses == 0:
            return float('inf') if sum_gains > 0 else 0

        return sum_gains / sum_losses


class PortfolioAnalyzer:
    """
    Portfolio-level analysis
    Analyzes correlation, diversification, and allocation
    """

    def __init__(self):
        self.analyzer = PerformanceAnalyzer()

    def analyze_portfolio(self, positions: List[Dict], prices: Dict[str, List[float]]) -> Dict:
        """Analyze portfolio composition and performance"""

        # Calculate portfolio weights
        total_value = sum(p['value'] for p in positions)
        weights = {p['market_id']: p['value'] / total_value for p in positions}

        # Calculate portfolio returns
        portfolio_returns = self._calculate_portfolio_returns(weights, prices)

        # Calculate correlation matrix
        correlation_matrix = self._calculate_correlations(prices)

        # Calculate diversification ratio
        diversification_ratio = self._calculate_diversification_ratio(weights, correlation_matrix)

        # Calculate concentration metrics
        herfindahl_index = sum(w ** 2 for w in weights.values())
        effective_n = 1 / herfindahl_index if herfindahl_index > 0 else 0

        # Performance attribution
        attribution = self._performance_attribution(positions, prices)

        return {
            "total_value": total_value,
            "weights": weights,
            "returns": portfolio_returns,
            "metrics": self.analyzer.calculate_metrics(np.array(portfolio_returns)),
            "correlation_matrix": correlation_matrix,
            "diversification_ratio": diversification_ratio,
            "herfindahl_index": herfindahl_index,
            "effective_positions": effective_n,
            "attribution": attribution
        }

    def _calculate_portfolio_returns(self, weights: Dict, prices: Dict) -> List[float]:
        """Calculate weighted portfolio returns"""
        returns = []

        # Get all timestamps
        timestamps = set()
        for price_series in prices.values():
            timestamps.update(price_series.keys())

        timestamps = sorted(timestamps)

        for i in range(1, len(timestamps)):
            portfolio_return = 0
            for market_id, weight in weights.items():
                if market_id in prices:
                    prev_price = prices[market_id].get(timestamps[i-1], 0)
                    curr_price = prices[market_id].get(timestamps[i], 0)

                    if prev_price > 0:
                        market_return = (curr_price - prev_price) / prev_price
                        portfolio_return += weight * market_return

            returns.append(portfolio_return)

        return returns

    def _calculate_correlations(self, prices: Dict) -> np.ndarray:
        """Calculate correlation matrix between assets"""
        market_ids = list(prices.keys())
        n = len(market_ids)

        if n == 0:
            return np.array([])

        # Convert prices to returns
        returns_matrix = []
        for market_id in market_ids:
            price_series = list(prices[market_id].values())
            returns = []
            for i in range(1, len(price_series)):
                if price_series[i-1] > 0:
                    returns.append((price_series[i] - price_series[i-1]) / price_series[i-1])
                else:
                    returns.append(0)
            returns_matrix.append(returns)

        if not returns_matrix or not returns_matrix[0]:
            return np.eye(n)

        return np.corrcoef(returns_matrix)

    def _calculate_diversification_ratio(self, weights: Dict, correlation_matrix: np.ndarray) -> float:
        """Calculate diversification ratio"""
        if len(weights) == 0 or len(correlation_matrix) == 0:
            return 1

        w = np.array(list(weights.values()))

        # Portfolio volatility
        portfolio_vol = np.sqrt(w @ correlation_matrix @ w.T)

        # Sum of weighted individual volatilities (assuming unit volatility)
        weighted_vols = np.sum(w)

        if portfolio_vol == 0:
            return 0

        return weighted_vols / portfolio_vol

    def _performance_attribution(self, positions: List[Dict], prices: Dict) -> Dict:
        """Attribute performance to individual positions"""
        attribution = {}

        for position in positions:
            market_id = position['market_id']
            if market_id not in prices:
                continue

            price_series = list(prices[market_id].values())
            if len(price_series) < 2:
                continue

            # Calculate position return
            entry_price = position.get('entry_price', price_series[0])
            current_price = price_series[-1]

            if entry_price > 0:
                position_return = (current_price - entry_price) / entry_price
                position_pnl = position['value'] * position_return

                attribution[market_id] = {
                    "return": position_return,
                    "pnl": position_pnl,
                    "contribution": position_pnl,  # Contribution to total P&L
                    "weight": position['value']
                }

        return attribution


class WhaleAnalyzer:
    """
    Whale-specific performance analysis
    Tracks and analyzes individual whale performance
    """

    def __init__(self, database_connection):
        self.db = database_connection
        self.performance_analyzer = PerformanceAnalyzer()
        self.whale_cache = {}

    async def analyze_whale(self, whale_address: str, timeframe: TimeFrame = TimeFrame.DAILY) -> WhalePerformance:
        """Analyze individual whale performance"""

        # Check cache
        cache_key = f"{whale_address}:{timeframe.value}"
        if cache_key in self.whale_cache:
            cached = self.whale_cache[cache_key]
            if (datetime.now() - cached['timestamp']).seconds < 300:  # 5 min cache
                return cached['data']

        # Fetch whale data
        trades = await self._fetch_whale_trades(whale_address)
        positions = await self._fetch_whale_positions(whale_address)

        # Calculate returns
        returns = self._calculate_returns_from_trades(trades, timeframe)

        # Calculate metrics
        metrics = self.performance_analyzer.calculate_metrics(np.array(returns), timeframe)

        # Generate P&L curve
        pnl_curve = self._generate_pnl_curve(trades)

        # Generate drawdown curve
        dd_curve = self._generate_drawdown_curve(pnl_curve)

        # Get whale name if available
        whale_info = await self._fetch_whale_info(whale_address)
        whale_name = whale_info.get('name') if whale_info else None

        performance = WhalePerformance(
            whale_address=whale_address,
            whale_name=whale_name,
            metrics=metrics,
            trade_history=trades[-100:],  # Last 100 trades
            position_history=positions,
            pnl_curve=pnl_curve,
            drawdown_curve=dd_curve,
            last_updated=datetime.now()
        )

        # Cache result
        self.whale_cache[cache_key] = {
            'data': performance,
            'timestamp': datetime.now()
        }

        return performance

    async def _fetch_whale_trades(self, whale_address: str) -> List[Dict]:
        """Fetch whale's trade history from database"""
        query = """
            SELECT * FROM trades
            WHERE whale_address = $1
            ORDER BY timestamp DESC
            LIMIT 10000
        """

        results = await self.db.fetch(query, whale_address)
        return [dict(r) for r in results] if results else []

    async def _fetch_whale_positions(self, whale_address: str) -> List[Dict]:
        """Fetch whale's position history"""
        query = """
            SELECT * FROM positions
            WHERE whale_address = $1
            ORDER BY opened_at DESC
            LIMIT 1000
        """

        results = await self.db.fetch(query, whale_address)
        return [dict(r) for r in results] if results else []

    async def _fetch_whale_info(self, whale_address: str) -> Optional[Dict]:
        """Fetch whale information"""
        query = """
            SELECT * FROM whales
            WHERE address = $1
        """

        result = await self.db.fetchrow(query, whale_address)
        return dict(result) if result else None

    def _calculate_returns_from_trades(self, trades: List[Dict], timeframe: TimeFrame) -> List[float]:
        """Calculate returns from trade history"""
        if not trades:
            return []

        # Group trades by timeframe
        grouped_trades = self._group_trades_by_timeframe(trades, timeframe)

        returns = []
        for period_trades in grouped_trades.values():
            period_pnl = sum(t.get('pnl', 0) for t in period_trades)
            period_volume = sum(t.get('size', 0) for t in period_trades)

            if period_volume > 0:
                period_return = period_pnl / period_volume
                returns.append(period_return)

        return returns

    def _group_trades_by_timeframe(self, trades: List[Dict], timeframe: TimeFrame) -> Dict:
        """Group trades by timeframe"""
        grouped = defaultdict(list)

        for trade in trades:
            timestamp = trade.get('timestamp')
            if not timestamp:
                continue

            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)

            # Determine period key based on timeframe
            if timeframe == TimeFrame.HOURLY:
                key = timestamp.strftime("%Y-%m-%d %H:00")
            elif timeframe == TimeFrame.DAILY:
                key = timestamp.strftime("%Y-%m-%d")
            elif timeframe == TimeFrame.WEEKLY:
                key = timestamp.strftime("%Y-W%W")
            elif timeframe == TimeFrame.MONTHLY:
                key = timestamp.strftime("%Y-%m")
            elif timeframe == TimeFrame.YEARLY:
                key = timestamp.strftime("%Y")
            else:
                key = "all"

            grouped[key].append(trade)

        return grouped

    def _generate_pnl_curve(self, trades: List[Dict]) -> List[float]:
        """Generate cumulative P&L curve"""
        pnl_curve = []
        cumulative_pnl = 0

        for trade in sorted(trades, key=lambda x: x.get('timestamp', '')):
            pnl = trade.get('pnl', 0)
            cumulative_pnl += pnl
            pnl_curve.append(cumulative_pnl)

        return pnl_curve

    def _generate_drawdown_curve(self, pnl_curve: List[float]) -> List[float]:
        """Generate drawdown curve from P&L curve"""
        if not pnl_curve:
            return []

        peak = pnl_curve[0]
        dd_curve = []

        for value in pnl_curve:
            peak = max(peak, value)
            drawdown = (value - peak) / peak if peak != 0 else 0
            dd_curve.append(drawdown)

        return dd_curve


class PerformanceDashboard:
    """
    Main performance dashboard interface
    Orchestrates all analytics components
    """

    def __init__(self, database_connection):
        self.db = database_connection
        self.whale_analyzer = WhaleAnalyzer(database_connection)
        self.portfolio_analyzer = PortfolioAnalyzer()
        self.performance_analyzer = PerformanceAnalyzer()
        self.cache = {}

    async def get_dashboard_data(self, timeframe: TimeFrame = TimeFrame.DAILY) -> Dict:
        """Get comprehensive dashboard data"""

        # Get top whales
        top_whales = await self.get_top_performing_whales(limit=10)

        # Get portfolio performance
        portfolio_data = await self.get_portfolio_performance(timeframe)

        # Get market analysis
        market_analysis = await self.get_market_analysis()

        # Get recent performance
        recent_performance = await self.get_recent_performance(days=30)

        # Get risk metrics
        risk_metrics = await self.get_risk_metrics()

        return {
            "timestamp": datetime.now().isoformat(),
            "timeframe": timeframe.value,
            "top_whales": top_whales,
            "portfolio": portfolio_data,
            "markets": market_analysis,
            "recent_performance": recent_performance,
            "risk_metrics": risk_metrics,
            "summary": await self.get_performance_summary()
        }

    async def get_top_performing_whales(self, limit: int = 10, metric: str = "sharpe_ratio") -> List[Dict]:
        """Get top performing whales by specified metric"""

        query = """
            SELECT
                w.address,
                w.name,
                w.total_pnl,
                w.total_trades,
                w.win_rate,
                w.sharpe_ratio,
                w.max_drawdown,
                w.whale_quality_score
            FROM whales w
            WHERE w.total_trades > 10
            ORDER BY {} DESC
            LIMIT $1
        """.format(metric)

        results = await self.db.fetch(query, limit)

        whales = []
        for row in results:
            whale_data = dict(row)

            # Get detailed performance
            performance = await self.whale_analyzer.analyze_whale(whale_data['address'])

            whale_data['metrics'] = {
                "total_return": performance.metrics.total_return,
                "sharpe_ratio": performance.metrics.sharpe_ratio,
                "win_rate": performance.metrics.win_rate,
                "max_drawdown": performance.metrics.max_drawdown,
                "profit_factor": performance.metrics.profit_factor
            }

            whale_data['recent_trades'] = performance.trade_history[:5]
            whales.append(whale_data)

        return whales

    async def get_portfolio_performance(self, timeframe: TimeFrame) -> Dict:
        """Get overall portfolio performance"""

        # Get all positions
        query = """
            SELECT
                p.*,
                m.name as market_name
            FROM positions p
            LEFT JOIN markets m ON p.market_id = m.id
            WHERE p.closed_at IS NULL
        """

        positions = await self.db.fetch(query)

        if not positions:
            return {"message": "No open positions"}

        # Get price data
        prices = await self._fetch_price_data([p['market_id'] for p in positions])

        # Analyze portfolio
        portfolio_analysis = self.portfolio_analyzer.analyze_portfolio(
            [dict(p) for p in positions],
            prices
        )

        return portfolio_analysis

    async def get_market_analysis(self) -> List[MarketAnalysis]:
        """Analyze all traded markets"""

        query = """
            SELECT
                m.id,
                m.name,
                COUNT(t.id) as total_trades,
                SUM(t.size) as total_volume,
                AVG(t.size) as avg_trade_size,
                COUNT(DISTINCT t.whale_address) as unique_whales
            FROM markets m
            LEFT JOIN trades t ON m.id = t.market_id
            WHERE t.timestamp > NOW() - INTERVAL '30 days'
            GROUP BY m.id, m.name
            ORDER BY total_volume DESC
            LIMIT 20
        """

        results = await self.db.fetch(query)

        markets = []
        for row in results:
            market = MarketAnalysis(
                market_id=row['id'],
                market_name=row['name'],
                total_volume=Decimal(str(row['total_volume'] or 0)),
                total_trades=row['total_trades'] or 0,
                avg_trade_size=Decimal(str(row['avg_trade_size'] or 0)),
                whale_participation=0,  # Calculate separately
                profitability=0,  # Calculate from P&L
                volatility=0,  # Calculate from price data
                trending_direction=None,
                correlation_with_btc=0,
                correlation_with_eth=0
            )
            markets.append(market)

        return markets

    async def get_recent_performance(self, days: int = 30) -> Dict:
        """Get recent performance summary"""

        query = """
            SELECT
                DATE(closed_at) as date,
                SUM(pnl) as daily_pnl,
                COUNT(*) as trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses
            FROM positions
            WHERE closed_at > NOW() - INTERVAL '{} days'
            GROUP BY DATE(closed_at)
            ORDER BY date DESC
        """.format(days)

        results = await self.db.fetch(query)

        daily_data = [dict(r) for r in results]

        # Calculate cumulative P&L
        cumulative_pnl = []
        total = 0
        for day in reversed(daily_data):
            total += float(day['daily_pnl'] or 0)
            cumulative_pnl.append(total)

        return {
            "daily_data": daily_data,
            "cumulative_pnl": list(reversed(cumulative_pnl)),
            "total_pnl": total,
            "total_trades": sum(d['trades'] for d in daily_data),
            "win_rate": sum(d['wins'] for d in daily_data) / max(1, sum(d['trades'] for d in daily_data))
        }

    async def get_risk_metrics(self) -> Dict:
        """Get current risk metrics"""

        # Get portfolio value
        query = """
            SELECT
                SUM(CASE WHEN closed_at IS NULL THEN size * current_price ELSE 0 END) as open_value,
                SUM(ABS(pnl)) as total_risk,
                MAX(ABS(pnl)) as max_loss
            FROM positions
        """

        result = await self.db.fetchrow(query)

        return {
            "open_value": float(result['open_value'] or 0),
            "total_risk": float(result['total_risk'] or 0),
            "max_loss": float(result['max_loss'] or 0),
            "risk_level": self._calculate_risk_level(result)
        }

    async def get_performance_summary(self) -> Dict:
        """Get overall performance summary"""

        query = """
            SELECT
                SUM(pnl) as total_pnl,
                COUNT(*) as total_trades,
                AVG(pnl) as avg_pnl,
                SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) as total_wins,
                SUM(CASE WHEN pnl < 0 THEN ABS(pnl) ELSE 0 END) as total_losses,
                COUNT(DISTINCT whale_address) as unique_whales,
                COUNT(DISTINCT market_id) as unique_markets
            FROM positions
            WHERE closed_at IS NOT NULL
        """

        result = await self.db.fetchrow(query)

        total_wins = float(result['total_wins'] or 0)
        total_losses = float(result['total_losses'] or 1)

        return {
            "total_pnl": float(result['total_pnl'] or 0),
            "total_trades": result['total_trades'] or 0,
            "avg_pnl": float(result['avg_pnl'] or 0),
            "profit_factor": total_wins / total_losses if total_losses > 0 else 0,
            "unique_whales": result['unique_whales'] or 0,
            "unique_markets": result['unique_markets'] or 0
        }

    async def _fetch_price_data(self, market_ids: List[str]) -> Dict:
        """Fetch price data for markets"""
        # Placeholder - would fetch from API or database
        prices = {}
        for market_id in market_ids:
            # Generate sample price data
            prices[market_id] = {
                datetime.now() - timedelta(days=i): 0.5 + np.random.randn() * 0.1
                for i in range(30)
            }
        return prices

    def _calculate_risk_level(self, metrics: Dict) -> str:
        """Calculate current risk level"""
        open_value = float(metrics['open_value'] or 0)
        max_loss = float(metrics['max_loss'] or 0)

        if open_value == 0:
            return "low"

        risk_ratio = max_loss / open_value

        if risk_ratio < 0.1:
            return "low"
        elif risk_ratio < 0.2:
            return "medium"
        elif risk_ratio < 0.3:
            return "high"
        else:
            return "critical"


async def test_performance_dashboard():
    """Test performance dashboard"""
    from src.database.connection import DatabaseConnection

    print("=" * 60)
    print("PERFORMANCE ANALYTICS DASHBOARD TEST")
    print("=" * 60)

    # Create mock database connection
    class MockDB:
        async def fetch(self, query, *args):
            return []

        async def fetchrow(self, query, *args):
            return {
                'total_pnl': 5000,
                'total_trades': 100,
                'avg_pnl': 50,
                'total_wins': 6000,
                'total_losses': 1000,
                'unique_whales': 25,
                'unique_markets': 15,
                'open_value': 10000,
                'total_risk': 2000,
                'max_loss': 500
            }

    db = MockDB()
    dashboard = PerformanceDashboard(db)

    # Test performance analyzer
    print("\n1. Testing Performance Analyzer...")
    analyzer = PerformanceAnalyzer()

    # Generate sample returns
    np.random.seed(42)
    returns = np.random.randn(100) * 0.02 + 0.001  # 0.1% average return, 2% volatility

    metrics = analyzer.calculate_metrics(returns)

    print(f"   Total Return: {metrics.total_return:.2%}")
    print(f"   Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
    print(f"   Max Drawdown: {metrics.max_drawdown:.2%}")
    print(f"   Win Rate: {metrics.win_rate:.2%}")
    print(f"   Profit Factor: {metrics.profit_factor:.2f}")

    # Test dashboard data
    print("\n2. Testing Dashboard Data Generation...")
    data = await dashboard.get_dashboard_data(TimeFrame.DAILY)

    print(f"   Timestamp: {data['timestamp']}")
    print(f"   Timeframe: {data['timeframe']}")

    # Test summary
    print("\n3. Testing Performance Summary...")
    summary = await dashboard.get_performance_summary()

    print(f"   Total P&L: ${summary['total_pnl']:,.2f}")
    print(f"   Total Trades: {summary['total_trades']}")
    print(f"   Profit Factor: {summary['profit_factor']:.2f}")
    print(f"   Unique Whales: {summary['unique_whales']}")
    print(f"   Unique Markets: {summary['unique_markets']}")

    print("\n" + "=" * 60)
    print("✓ PERFORMANCE DASHBOARD TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    asyncio.run(test_performance_dashboard())
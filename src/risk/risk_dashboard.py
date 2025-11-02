"""
Risk Monitoring Dashboard
Week 5: Risk Management Framework - Real-Time Risk Monitoring
Comprehensive dashboard with VaR, Sharpe, Sortino, and exposure metrics
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict

logger = logging.getLogger(__name__)


# ==================== Data Structures ====================

@dataclass
class PortfolioSnapshot:
    """Point-in-time portfolio snapshot"""
    timestamp: datetime
    total_value: Decimal
    pnl: Decimal
    position_count: int


@dataclass
class RiskMetrics:
    """Comprehensive risk metrics"""
    # Value at Risk
    var_95: Decimal  # 95% VaR (1-day)
    var_99: Decimal  # 99% VaR (1-day)

    # Performance metrics
    sharpe_ratio: Decimal  # Risk-adjusted returns
    sortino_ratio: Decimal  # Downside risk-adjusted returns
    max_drawdown: Decimal  # Maximum peak-to-trough decline
    win_rate: Decimal  # Percentage of winning trades

    # Exposure metrics
    total_exposure: Decimal
    largest_position_pct: Decimal
    average_position_size: Decimal

    # Volatility
    daily_volatility: Decimal
    annualized_volatility: Decimal

    # Time
    calculation_time: datetime


@dataclass
class ExposureBreakdown:
    """Detailed exposure breakdown"""
    by_topic: Dict[str, Decimal]
    by_whale: Dict[str, Decimal]
    by_market: Dict[str, Decimal]
    largest_exposures: List[Dict]


@dataclass
class AlertConfig:
    """Alert thresholds configuration"""
    # Loss thresholds
    daily_loss_alert: Decimal = Decimal("300")
    var_breach_multiplier: Decimal = Decimal("1.5")  # Alert if actual loss > 1.5x VaR

    # Exposure thresholds
    max_single_position_pct: Decimal = Decimal("0.25")  # 25%
    max_topic_concentration: Decimal = Decimal("0.40")  # 40%

    # Performance thresholds
    min_sharpe_ratio: Decimal = Decimal("0.5")
    max_drawdown_pct: Decimal = Decimal("0.10")  # 10%


@dataclass
class Alert:
    """Risk alert"""
    severity: str  # INFO, WARNING, CRITICAL
    category: str  # LOSS, EXPOSURE, PERFORMANCE, RISK_LIMIT
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    metric_value: Optional[Decimal] = None
    threshold: Optional[Decimal] = None


# ==================== Risk Dashboard ====================

class RiskDashboard:
    """
    Comprehensive Risk Monitoring Dashboard

    Provides real-time risk analytics and monitoring:
    - Value at Risk (VaR) calculation
    - Sharpe & Sortino ratios
    - Maximum drawdown tracking
    - Exposure breakdowns by topic/whale/market
    - Automated alerting on threshold breaches

    Integrates with all Week 5 risk components for
    complete portfolio risk visibility.
    """

    def __init__(self, alert_config: Optional[AlertConfig] = None):
        """
        Initialize risk dashboard

        Args:
            alert_config: Alert configuration
        """
        self.alert_config = alert_config or AlertConfig()

        # Historical data
        self.portfolio_history: List[PortfolioSnapshot] = []
        self.daily_returns: List[Decimal] = []

        # Current state
        self.current_positions: Dict = {}
        self.alerts: List[Alert] = []

        # Peak tracking for drawdown
        self.peak_value = Decimal("0")

        logger.info("RiskDashboard initialized")

    def update_portfolio(
        self,
        total_value: Decimal,
        pnl: Decimal,
        positions: Dict
    ):
        """
        Update portfolio state and calculate metrics

        Args:
            total_value: Current portfolio value
            pnl: Profit/loss for current period
            positions: Current positions dictionary
        """
        # Add snapshot
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(),
            total_value=total_value,
            pnl=pnl,
            position_count=len(positions)
        )
        self.portfolio_history.append(snapshot)

        # Update positions
        self.current_positions = positions

        # Calculate daily return if we have previous value
        if len(self.portfolio_history) > 1:
            prev_value = self.portfolio_history[-2].total_value
            if prev_value > 0:
                daily_return = (total_value - prev_value) / prev_value
                self.daily_returns.append(daily_return)

        # Update peak for drawdown calculation
        if total_value > self.peak_value:
            self.peak_value = total_value

        # Check for alerts
        self._check_alerts()

        # Trim history (keep last 365 days)
        self._trim_history()

    def calculate_metrics(self) -> RiskMetrics:
        """
        Calculate comprehensive risk metrics

        Returns:
            RiskMetrics with current calculations
        """
        if not self.portfolio_history:
            return self._empty_metrics()

        current = self.portfolio_history[-1]

        # Calculate VaR
        var_95, var_99 = self._calculate_var()

        # Calculate Sharpe ratio
        sharpe = self._calculate_sharpe_ratio()

        # Calculate Sortino ratio
        sortino = self._calculate_sortino_ratio()

        # Calculate max drawdown
        max_drawdown = self._calculate_max_drawdown()

        # Calculate win rate
        win_rate = self._calculate_win_rate()

        # Calculate volatility
        daily_vol = self._calculate_volatility()
        annual_vol = daily_vol * Decimal(str(np.sqrt(252)))  # Annualize

        # Exposure metrics
        total_exposure = sum(
            Decimal(str(p.get("size_usd", 0)))
            for p in self.current_positions.values()
        )

        largest_position = Decimal("0")
        if self.current_positions and total_exposure > 0:
            largest_position = max(
                Decimal(str(p.get("size_usd", 0)))
                for p in self.current_positions.values()
            )

        largest_position_pct = (
            largest_position / total_exposure
            if total_exposure > 0
            else Decimal("0")
        )

        average_position = (
            total_exposure / Decimal(str(len(self.current_positions)))
            if self.current_positions
            else Decimal("0")
        )

        return RiskMetrics(
            var_95=var_95,
            var_99=var_99,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            total_exposure=total_exposure,
            largest_position_pct=largest_position_pct,
            average_position_size=average_position,
            daily_volatility=daily_vol,
            annualized_volatility=annual_vol,
            calculation_time=datetime.now()
        )

    def get_exposure_breakdown(self) -> ExposureBreakdown:
        """
        Get detailed exposure breakdown

        Returns:
            ExposureBreakdown with categories
        """
        by_topic = defaultdict(Decimal)
        by_whale = defaultdict(Decimal)
        by_market = defaultdict(Decimal)

        for position in self.current_positions.values():
            size = Decimal(str(position.get("size_usd", 0)))
            topic = position.get("topic", "Unknown")
            whale = position.get("whale_address", "Unknown")
            market = position.get("market_id", "Unknown")

            by_topic[topic] += size
            by_whale[whale] += size
            by_market[market] += size

        # Get largest exposures
        all_exposures = []
        for position_id, position in self.current_positions.items():
            all_exposures.append({
                "position_id": position_id,
                "size_usd": float(Decimal(str(position.get("size_usd", 0)))),
                "topic": position.get("topic", "Unknown"),
                "whale": position.get("whale_address", "Unknown")[:10] + "...",
                "market": position.get("market_id", "Unknown")
            })

        largest_exposures = sorted(
            all_exposures,
            key=lambda x: x["size_usd"],
            reverse=True
        )[:10]

        return ExposureBreakdown(
            by_topic=dict(by_topic),
            by_whale=dict(by_whale),
            by_market=dict(by_market),
            largest_exposures=largest_exposures
        )

    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts (last 24 hours)"""
        cutoff = datetime.now() - timedelta(hours=24)
        return [
            alert for alert in self.alerts
            if alert.timestamp > cutoff
        ]

    def get_dashboard_summary(self) -> Dict:
        """
        Get comprehensive dashboard summary

        Returns:
            Dictionary with all metrics, exposures, and alerts
        """
        metrics = self.calculate_metrics()
        exposure = self.get_exposure_breakdown()
        alerts = self.get_active_alerts()

        return {
            "timestamp": datetime.now().isoformat(),
            "portfolio": {
                "total_value": float(self.portfolio_history[-1].total_value) if self.portfolio_history else 0,
                "position_count": len(self.current_positions),
                "peak_value": float(self.peak_value)
            },
            "risk_metrics": {
                "var_95": float(metrics.var_95),
                "var_99": float(metrics.var_99),
                "sharpe_ratio": float(metrics.sharpe_ratio),
                "sortino_ratio": float(metrics.sortino_ratio),
                "max_drawdown": float(metrics.max_drawdown),
                "win_rate": float(metrics.win_rate),
                "daily_volatility": float(metrics.daily_volatility),
                "annualized_volatility": float(metrics.annualized_volatility)
            },
            "exposure": {
                "total": float(metrics.total_exposure),
                "largest_position_pct": float(metrics.largest_position_pct),
                "average_position": float(metrics.average_position_size),
                "by_topic": {k: float(v) for k, v in exposure.by_topic.items()},
                "largest_positions": exposure.largest_exposures[:5]
            },
            "alerts": [
                {
                    "severity": alert.severity,
                    "category": alert.category,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat()
                }
                for alert in alerts
            ]
        }

    # ==================== Private Methods ====================

    def _calculate_var(self) -> Tuple[Decimal, Decimal]:
        """
        Calculate Value at Risk (VaR) at 95% and 99% confidence

        VaR estimates the maximum expected loss over a time period
        at a given confidence level.
        """
        if len(self.daily_returns) < 30:
            # Need minimum 30 days of data
            return Decimal("0"), Decimal("0")

        returns_array = np.array([float(r) for r in self.daily_returns[-252:]])  # Last year

        # Calculate historical VaR (non-parametric)
        var_95 = np.percentile(returns_array, 5)  # 5th percentile
        var_99 = np.percentile(returns_array, 1)  # 1st percentile

        # Convert to dollar amounts if we have current value
        if self.portfolio_history:
            current_value = self.portfolio_history[-1].total_value
            var_95_dollar = current_value * Decimal(str(abs(var_95)))
            var_99_dollar = current_value * Decimal(str(abs(var_99)))
            return var_95_dollar, var_99_dollar

        return Decimal("0"), Decimal("0")

    def _calculate_sharpe_ratio(self, risk_free_rate: Decimal = Decimal("0.04")) -> Decimal:
        """
        Calculate Sharpe Ratio (risk-adjusted returns)

        Sharpe = (Mean Return - Risk-Free Rate) / Std Dev of Returns
        """
        if len(self.daily_returns) < 30:
            return Decimal("0")

        returns_array = np.array([float(r) for r in self.daily_returns[-252:]])

        mean_return = Decimal(str(np.mean(returns_array)))
        std_dev = Decimal(str(np.std(returns_array)))

        if std_dev == 0:
            return Decimal("0")

        # Annualize
        annual_return = mean_return * Decimal("252")
        annual_std = std_dev * Decimal(str(np.sqrt(252)))

        sharpe = (annual_return - risk_free_rate) / annual_std
        return sharpe

    def _calculate_sortino_ratio(self, risk_free_rate: Decimal = Decimal("0.04")) -> Decimal:
        """
        Calculate Sortino Ratio (downside risk-adjusted returns)

        Like Sharpe but only penalizes downside volatility
        """
        if len(self.daily_returns) < 30:
            return Decimal("0")

        returns_array = np.array([float(r) for r in self.daily_returns[-252:]])

        mean_return = Decimal(str(np.mean(returns_array)))

        # Calculate downside deviation (only negative returns)
        negative_returns = returns_array[returns_array < 0]
        if len(negative_returns) == 0:
            return Decimal("999")  # Perfect (no downside)

        downside_std = Decimal(str(np.std(negative_returns)))

        if downside_std == 0:
            return Decimal("0")

        # Annualize
        annual_return = mean_return * Decimal("252")
        annual_downside_std = downside_std * Decimal(str(np.sqrt(252)))

        sortino = (annual_return - risk_free_rate) / annual_downside_std
        return sortino

    def _calculate_max_drawdown(self) -> Decimal:
        """Calculate maximum drawdown from peak"""
        if not self.portfolio_history or self.peak_value == 0:
            return Decimal("0")

        current_value = self.portfolio_history[-1].total_value
        drawdown = (self.peak_value - current_value) / self.peak_value

        return drawdown

    def _calculate_win_rate(self) -> Decimal:
        """Calculate win rate from daily returns"""
        if len(self.daily_returns) < 10:
            return Decimal("0.5")

        wins = sum(1 for r in self.daily_returns if r > 0)
        total = len(self.daily_returns)

        return Decimal(str(wins / total))

    def _calculate_volatility(self) -> Decimal:
        """Calculate daily volatility"""
        if len(self.daily_returns) < 30:
            return Decimal("0")

        returns_array = np.array([float(r) for r in self.daily_returns[-252:]])
        volatility = Decimal(str(np.std(returns_array)))

        return volatility

    def _check_alerts(self):
        """Check for alert conditions and generate alerts"""
        if not self.portfolio_history:
            return

        current = self.portfolio_history[-1]
        metrics = self.calculate_metrics()

        # Check daily loss alert
        if current.pnl < -self.alert_config.daily_loss_alert:
            self.alerts.append(Alert(
                severity="CRITICAL",
                category="LOSS",
                message=f"Daily loss exceeds threshold: ${float(current.pnl):.2f}",
                metric_value=abs(current.pnl),
                threshold=self.alert_config.daily_loss_alert
            ))

        # Check VaR breach
        if current.pnl < 0 and abs(current.pnl) > metrics.var_95 * self.alert_config.var_breach_multiplier:
            self.alerts.append(Alert(
                severity="WARNING",
                category="RISK_LIMIT",
                message=f"Loss exceeds VaR estimate: ${float(current.pnl):.2f} > ${float(metrics.var_95):.2f}",
                metric_value=abs(current.pnl),
                threshold=metrics.var_95
            ))

        # Check max drawdown
        if metrics.max_drawdown > self.alert_config.max_drawdown_pct:
            self.alerts.append(Alert(
                severity="CRITICAL",
                category="PERFORMANCE",
                message=f"Max drawdown exceeded: {float(metrics.max_drawdown)*100:.2f}%",
                metric_value=metrics.max_drawdown,
                threshold=self.alert_config.max_drawdown_pct
            ))

        # Check Sharpe ratio
        if metrics.sharpe_ratio < self.alert_config.min_sharpe_ratio and len(self.daily_returns) > 60:
            self.alerts.append(Alert(
                severity="WARNING",
                category="PERFORMANCE",
                message=f"Low Sharpe ratio: {float(metrics.sharpe_ratio):.2f}",
                metric_value=metrics.sharpe_ratio,
                threshold=self.alert_config.min_sharpe_ratio
            ))

        # Check position concentration
        if metrics.largest_position_pct > self.alert_config.max_single_position_pct:
            self.alerts.append(Alert(
                severity="WARNING",
                category="EXPOSURE",
                message=f"Single position too large: {float(metrics.largest_position_pct)*100:.1f}%",
                metric_value=metrics.largest_position_pct,
                threshold=self.alert_config.max_single_position_pct
            ))

        # Check topic concentration
        exposure = self.get_exposure_breakdown()
        total_exposure = metrics.total_exposure
        if total_exposure > 0:
            for topic, topic_exp in exposure.by_topic.items():
                concentration = topic_exp / total_exposure
                if concentration > self.alert_config.max_topic_concentration:
                    self.alerts.append(Alert(
                        severity="WARNING",
                        category="EXPOSURE",
                        message=f"Topic '{topic}' over-concentrated: {float(concentration)*100:.1f}%",
                        metric_value=concentration,
                        threshold=self.alert_config.max_topic_concentration
                    ))

    def _trim_history(self):
        """Keep only last 365 days of history"""
        if len(self.portfolio_history) > 365:
            self.portfolio_history = self.portfolio_history[-365:]

        if len(self.daily_returns) > 365:
            self.daily_returns = self.daily_returns[-365:]

        # Trim alerts (keep last 7 days)
        cutoff = datetime.now() - timedelta(days=7)
        self.alerts = [a for a in self.alerts if a.timestamp > cutoff]

    def _empty_metrics(self) -> RiskMetrics:
        """Return empty metrics when no data available"""
        return RiskMetrics(
            var_95=Decimal("0"),
            var_99=Decimal("0"),
            sharpe_ratio=Decimal("0"),
            sortino_ratio=Decimal("0"),
            max_drawdown=Decimal("0"),
            win_rate=Decimal("0.5"),
            total_exposure=Decimal("0"),
            largest_position_pct=Decimal("0"),
            average_position_size=Decimal("0"),
            daily_volatility=Decimal("0"),
            annualized_volatility=Decimal("0"),
            calculation_time=datetime.now()
        )


# ==================== Example Usage ====================

def main():
    """Example usage of RiskDashboard"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize dashboard
    dashboard = RiskDashboard()

    print("\n=== Risk Dashboard Test Scenarios ===\n")

    # Simulate portfolio updates
    base_value = Decimal("10000")

    # Scenario 1: Profitable period
    print("=== Scenario 1: Profitable Period ===")
    for day in range(60):
        # Simulate daily returns
        daily_change = Decimal(str(np.random.normal(0.01, 0.02)))  # 1% mean, 2% std
        pnl = base_value * daily_change
        base_value += pnl

        # Simulate positions
        positions = {
            f"pos_{i}": {
                "size_usd": float(base_value / 5),
                "topic": ["Politics", "Sports", "Tech", "Finance", "Crypto"][i % 5],
                "whale_address": f"0x{'0'*40}",
                "market_id": f"market_{i}"
            }
            for i in range(5)
        }

        dashboard.update_portfolio(base_value, pnl, positions)

    # Calculate metrics
    metrics = dashboard.calculate_metrics()
    print(f"Portfolio Value: ${float(base_value):.2f}")
    print(f"Sharpe Ratio: {float(metrics.sharpe_ratio):.3f}")
    print(f"Sortino Ratio: {float(metrics.sortino_ratio):.3f}")
    print(f"VaR (95%): ${float(metrics.var_95):.2f}")
    print(f"VaR (99%): ${float(metrics.var_99):.2f}")
    print(f"Max Drawdown: {float(metrics.max_drawdown)*100:.2f}%")
    print(f"Win Rate: {float(metrics.win_rate)*100:.1f}%")

    # Scenario 2: Big loss day
    print("\n=== Scenario 2: Big Loss Day ===")
    big_loss = base_value * Decimal("-0.05")  # -5% loss
    base_value += big_loss
    dashboard.update_portfolio(base_value, big_loss, positions)

    # Check alerts
    alerts = dashboard.get_active_alerts()
    print(f"Active Alerts: {len(alerts)}")
    for alert in alerts[:5]:
        print(f"  [{alert.severity}] {alert.category}: {alert.message}")

    # Full dashboard summary
    print("\n=== Full Dashboard Summary ===")
    import json
    summary = dashboard.get_dashboard_summary()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

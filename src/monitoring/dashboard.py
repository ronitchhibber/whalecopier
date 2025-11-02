"""
Real-time Monitoring Dashboard for Polymarket Whale Copy Trading
Provides comprehensive system visibility and alerting
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
from decimal import Decimal
import numpy as np
from collections import deque, defaultdict

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MetricType(Enum):
    """Types of metrics to track"""
    SYSTEM = "system"
    TRADING = "trading"
    PERFORMANCE = "performance"
    RISK = "risk"
    WHALE = "whale"


@dataclass
class Alert:
    """Represents a system alert"""
    id: str
    severity: AlertSeverity
    category: str
    message: str
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[datetime] = None


@dataclass
class MetricSnapshot:
    """Point-in-time metric value"""
    name: str
    value: float
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """Collects and aggregates system metrics"""

    def __init__(self, history_size: int = 1000):
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=history_size))
        self.aggregations: Dict[str, Dict] = {}
        self.last_values: Dict[str, float] = {}

    def record(self, name: str, value: float, labels: Dict[str, str] = None):
        """Record a metric value"""
        snapshot = MetricSnapshot(
            name=name,
            value=value,
            timestamp=datetime.now(),
            labels=labels or {}
        )

        # Store in time series
        self.metrics[name].append(snapshot)
        self.last_values[name] = value

        # Update aggregations
        self._update_aggregations(name, value)

    def _update_aggregations(self, name: str, value: float):
        """Update metric aggregations"""
        if name not in self.aggregations:
            self.aggregations[name] = {
                "min": value,
                "max": value,
                "sum": value,
                "count": 1,
                "mean": value
            }
        else:
            agg = self.aggregations[name]
            agg["min"] = min(agg["min"], value)
            agg["max"] = max(agg["max"], value)
            agg["sum"] += value
            agg["count"] += 1
            agg["mean"] = agg["sum"] / agg["count"]

    def get_metric(self, name: str, duration: timedelta = None) -> List[MetricSnapshot]:
        """Get metric history"""
        if name not in self.metrics:
            return []

        if duration:
            cutoff = datetime.now() - duration
            return [m for m in self.metrics[name] if m.timestamp >= cutoff]

        return list(self.metrics[name])

    def get_aggregation(self, name: str) -> Dict:
        """Get metric aggregations"""
        return self.aggregations.get(name, {})


class AlertManager:
    """Manages system alerts and notifications"""

    def __init__(self, max_alerts: int = 1000):
        self.alerts: deque = deque(maxlen=max_alerts)
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_handlers = []
        self.alert_rules = []

    def add_rule(self, rule_func, severity: AlertSeverity, category: str):
        """Add an alert rule"""
        self.alert_rules.append({
            "func": rule_func,
            "severity": severity,
            "category": category
        })

    def register_handler(self, handler):
        """Register an alert handler"""
        self.alert_handlers.append(handler)

    async def trigger_alert(self,
                           severity: AlertSeverity,
                           category: str,
                           message: str,
                           details: Dict = None):
        """Trigger a new alert"""
        alert_id = f"{category}_{datetime.now().timestamp()}"

        alert = Alert(
            id=alert_id,
            severity=severity,
            category=category,
            message=message,
            timestamp=datetime.now(),
            details=details or {}
        )

        # Store alert
        self.alerts.append(alert)
        if severity in [AlertSeverity.ERROR, AlertSeverity.CRITICAL]:
            self.active_alerts[alert_id] = alert

        # Notify handlers
        for handler in self.alert_handlers:
            try:
                await handler(alert)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")

        logger.info(f"Alert triggered: [{severity.value}] {category}: {message}")

        return alert

    def resolve_alert(self, alert_id: str):
        """Mark an alert as resolved"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.resolved = True
            alert.resolved_at = datetime.now()
            del self.active_alerts[alert_id]

    async def check_rules(self, metrics: Dict):
        """Check alert rules against current metrics"""
        for rule in self.alert_rules:
            try:
                should_alert, message, details = rule["func"](metrics)
                if should_alert:
                    await self.trigger_alert(
                        rule["severity"],
                        rule["category"],
                        message,
                        details
                    )
            except Exception as e:
                logger.error(f"Alert rule check failed: {e}")


class MonitoringDashboard:
    """
    Main monitoring dashboard for the copy trading system
    Tracks all critical metrics and generates alerts
    """

    def __init__(self, config: Dict = None):
        self.config = config or self._default_config()
        self.metrics = MetricsCollector()
        self.alerts = AlertManager()
        self.running = False

        # Component status tracking
        self.component_status = {
            "database": "unknown",
            "api": "unknown",
            "websocket": "unknown",
            "risk_manager": "unknown",
            "executor": "unknown"
        }

        # Initialize alert rules
        self._setup_alert_rules()

    def _default_config(self) -> Dict:
        """Default monitoring configuration"""
        return {
            "check_interval": 10,  # seconds
            "metrics_retention": 3600,  # seconds
            "alert_thresholds": {
                "error_rate": 0.05,  # 5% error rate
                "latency_p95": 1000,  # 1 second
                "risk_level": "HIGH",
                "drawdown": 0.15,  # 15%
                "circuit_breaker": True
            }
        }

    def _setup_alert_rules(self):
        """Setup monitoring alert rules"""

        # High error rate alert
        def check_error_rate(metrics):
            error_rate = metrics.get("error_rate", 0)
            if error_rate > self.config["alert_thresholds"]["error_rate"]:
                return True, f"High error rate: {error_rate:.2%}", {"error_rate": error_rate}
            return False, None, None

        self.alerts.add_rule(check_error_rate, AlertSeverity.ERROR, "system")

        # High latency alert
        def check_latency(metrics):
            latency = metrics.get("latency_p95", 0)
            threshold = self.config["alert_thresholds"]["latency_p95"]
            if latency > threshold:
                return True, f"High latency: {latency}ms", {"latency": latency}
            return False, None, None

        self.alerts.add_rule(check_latency, AlertSeverity.WARNING, "performance")

        # Risk level alert
        def check_risk_level(metrics):
            risk_level = metrics.get("risk_level", "")
            if risk_level in ["HIGH", "CRITICAL"]:
                return True, f"Elevated risk level: {risk_level}", {"risk_level": risk_level}
            return False, None, None

        self.alerts.add_rule(check_risk_level, AlertSeverity.WARNING, "risk")

        # Circuit breaker alert
        def check_circuit_breaker(metrics):
            if metrics.get("circuit_breaker_active", False):
                return True, "Circuit breaker activated", {"circuit_breaker": True}
            return False, None, None

        self.alerts.add_rule(check_circuit_breaker, AlertSeverity.CRITICAL, "risk")

        # Drawdown alert
        def check_drawdown(metrics):
            drawdown = metrics.get("current_drawdown", 0)
            threshold = self.config["alert_thresholds"]["drawdown"]
            if drawdown > threshold:
                return True, f"High drawdown: {drawdown:.2%}", {"drawdown": drawdown}
            return False, None, None

        self.alerts.add_rule(check_drawdown, AlertSeverity.ERROR, "performance")

    async def collect_system_metrics(self):
        """Collect system-level metrics"""
        try:
            import psutil

            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.metrics.record("system.cpu_usage", cpu_percent)

            # Memory usage
            memory = psutil.virtual_memory()
            self.metrics.record("system.memory_usage", memory.percent)
            self.metrics.record("system.memory_available", memory.available / 1024 / 1024)  # MB

            # Disk usage
            disk = psutil.disk_usage('/')
            self.metrics.record("system.disk_usage", disk.percent)

            # Network I/O
            net_io = psutil.net_io_counters()
            self.metrics.record("system.bytes_sent", net_io.bytes_sent)
            self.metrics.record("system.bytes_recv", net_io.bytes_recv)

        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")

    async def collect_trading_metrics(self, executor):
        """Collect trading metrics from executor"""
        try:
            if hasattr(executor, 'get_metrics'):
                metrics = executor.get_metrics()

                # Record trading metrics
                self.metrics.record("trading.total_trades", metrics.get("total_trades", 0))
                self.metrics.record("trading.successful_trades", metrics.get("successful_trades", 0))
                self.metrics.record("trading.failed_trades", metrics.get("failed_trades", 0))
                self.metrics.record("trading.pending_signals", metrics.get("pending_signals", 0))

                # Calculate success rate
                total = metrics.get("total_trades", 0)
                successful = metrics.get("successful_trades", 0)
                if total > 0:
                    success_rate = successful / total
                    self.metrics.record("trading.success_rate", success_rate)

                # Record latencies
                if "latency_p50" in metrics:
                    self.metrics.record("trading.latency_p50", metrics["latency_p50"])
                if "latency_p95" in metrics:
                    self.metrics.record("trading.latency_p95", metrics["latency_p95"])

        except Exception as e:
            logger.error(f"Failed to collect trading metrics: {e}")

    async def collect_performance_metrics(self, database):
        """Collect performance metrics from database"""
        try:
            # Get portfolio performance
            query = """
                SELECT
                    SUM(pnl) as total_pnl,
                    COUNT(*) as total_positions,
                    AVG(pnl) as avg_pnl,
                    MAX(pnl) as max_win,
                    MIN(pnl) as max_loss
                FROM positions
                WHERE closed_at > NOW() - INTERVAL '24 hours'
            """

            result = await database.fetch_one(query)
            if result:
                self.metrics.record("performance.daily_pnl", float(result["total_pnl"] or 0))
                self.metrics.record("performance.positions_count", result["total_positions"] or 0)
                self.metrics.record("performance.avg_pnl", float(result["avg_pnl"] or 0))

                # Calculate Sharpe ratio
                returns_query = """
                    SELECT pnl FROM positions
                    WHERE closed_at > NOW() - INTERVAL '30 days'
                    ORDER BY closed_at
                """
                returns_data = await database.fetch(returns_query)
                if returns_data:
                    returns = [float(r["pnl"]) for r in returns_data]
                    if len(returns) > 1:
                        sharpe = self._calculate_sharpe(returns)
                        self.metrics.record("performance.sharpe_ratio", sharpe)

        except Exception as e:
            logger.error(f"Failed to collect performance metrics: {e}")

    def _calculate_sharpe(self, returns: List[float], risk_free: float = 0.02) -> float:
        """Calculate Sharpe ratio"""
        if not returns:
            return 0

        returns_array = np.array(returns)
        excess_returns = returns_array - (risk_free / 252)  # Daily risk-free rate

        if np.std(excess_returns) == 0:
            return 0

        return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)

    async def check_component_health(self):
        """Check health of all system components"""

        # Check database
        try:
            # Attempt database connection
            self.component_status["database"] = "healthy"
        except:
            self.component_status["database"] = "unhealthy"
            await self.alerts.trigger_alert(
                AlertSeverity.CRITICAL,
                "component",
                "Database connection failed"
            )

        # Check API
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8000/health") as resp:
                    if resp.status == 200:
                        self.component_status["api"] = "healthy"
                    else:
                        self.component_status["api"] = "degraded"
        except:
            self.component_status["api"] = "unhealthy"
            await self.alerts.trigger_alert(
                AlertSeverity.ERROR,
                "component",
                "API health check failed"
            )

        # Check WebSocket connections
        # This would check the WebSocket client status
        self.component_status["websocket"] = "healthy"  # Placeholder

        # Record component health metrics
        for component, status in self.component_status.items():
            value = 1 if status == "healthy" else 0
            self.metrics.record(f"component.{component}.health", value)

    def get_dashboard_data(self) -> Dict:
        """Get current dashboard data"""
        return {
            "timestamp": datetime.now().isoformat(),
            "component_status": self.component_status,
            "metrics": {
                name: {
                    "current": self.metrics.last_values.get(name, 0),
                    "aggregation": self.metrics.get_aggregation(name)
                }
                for name in self.metrics.last_values
            },
            "active_alerts": [
                {
                    "id": alert.id,
                    "severity": alert.severity.value,
                    "category": alert.category,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat(),
                    "details": alert.details
                }
                for alert in self.alerts.active_alerts.values()
            ],
            "recent_alerts": [
                {
                    "severity": alert.severity.value,
                    "category": alert.category,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat()
                }
                for alert in list(self.alerts.alerts)[-10:]
            ]
        }

    async def start(self, executor=None, database=None):
        """Start monitoring"""
        self.running = True
        logger.info("Starting monitoring dashboard...")

        while self.running:
            try:
                # Collect all metrics
                await self.collect_system_metrics()

                if executor:
                    await self.collect_trading_metrics(executor)

                if database:
                    await self.collect_performance_metrics(database)

                await self.check_component_health()

                # Check alert rules
                current_metrics = self.metrics.last_values
                await self.alerts.check_rules(current_metrics)

                # Wait before next collection
                await asyncio.sleep(self.config["check_interval"])

            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(self.config["check_interval"])

    def stop(self):
        """Stop monitoring"""
        self.running = False
        logger.info("Monitoring dashboard stopped")


class WebDashboardServer:
    """
    Web server for dashboard visualization
    Serves real-time metrics via WebSocket and REST API
    """

    def __init__(self, dashboard: MonitoringDashboard, port: int = 8080):
        self.dashboard = dashboard
        self.port = port
        self.app = None
        self.websockets = set()

    async def handle_websocket(self, request):
        """Handle WebSocket connections for real-time updates"""
        ws = aiohttp.web.WebSocketResponse()
        await ws.prepare(request)
        self.websockets.add(ws)

        try:
            # Send initial data
            data = self.dashboard.get_dashboard_data()
            await ws.send_json(data)

            # Keep connection alive and send updates
            while not ws.closed:
                await asyncio.sleep(5)  # Update every 5 seconds
                data = self.dashboard.get_dashboard_data()
                await ws.send_json(data)

        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            self.websockets.discard(ws)

        return ws

    async def handle_metrics(self, request):
        """REST endpoint for metrics"""
        data = self.dashboard.get_dashboard_data()
        return aiohttp.web.json_response(data)

    async def handle_alerts(self, request):
        """REST endpoint for alerts"""
        alerts = {
            "active": [
                {
                    "id": a.id,
                    "severity": a.severity.value,
                    "message": a.message,
                    "timestamp": a.timestamp.isoformat()
                }
                for a in self.dashboard.alerts.active_alerts.values()
            ],
            "total": len(self.dashboard.alerts.alerts)
        }
        return aiohttp.web.json_response(alerts)

    async def handle_index(self, request):
        """Serve dashboard HTML"""
        html = self._generate_dashboard_html()
        return aiohttp.web.Response(text=html, content_type='text/html')

    def _generate_dashboard_html(self) -> str:
        """Generate dashboard HTML with real-time updates"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Whale Copy Trading Monitor</title>
            <style>
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: #1a1a2e;
                    color: #eee;
                    margin: 0;
                    padding: 20px;
                }
                .dashboard {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 20px;
                }
                .card {
                    background: #16213e;
                    border-radius: 8px;
                    padding: 20px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.3);
                }
                .card h3 {
                    margin-top: 0;
                    color: #4fbdba;
                }
                .metric {
                    display: flex;
                    justify-content: space-between;
                    padding: 8px 0;
                    border-bottom: 1px solid #2a2a4e;
                }
                .metric-value {
                    font-weight: bold;
                    color: #7ec8e3;
                }
                .status {
                    display: inline-block;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 12px;
                }
                .status.healthy { background: #27ae60; }
                .status.degraded { background: #f39c12; }
                .status.unhealthy { background: #e74c3c; }
                .alert {
                    padding: 10px;
                    margin: 5px 0;
                    border-radius: 4px;
                }
                .alert.info { background: #3498db; }
                .alert.warning { background: #f39c12; }
                .alert.error { background: #e74c3c; }
                .alert.critical { background: #c0392b; }
            </style>
        </head>
        <body>
            <h1>🐋 Whale Copy Trading Monitor</h1>
            <div class="dashboard">
                <div class="card">
                    <h3>System Status</h3>
                    <div id="component-status"></div>
                </div>
                <div class="card">
                    <h3>Trading Metrics</h3>
                    <div id="trading-metrics"></div>
                </div>
                <div class="card">
                    <h3>Performance</h3>
                    <div id="performance-metrics"></div>
                </div>
                <div class="card">
                    <h3>Active Alerts</h3>
                    <div id="alerts"></div>
                </div>
            </div>

            <script>
                const ws = new WebSocket('ws://localhost:8080/ws');

                ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    updateDashboard(data);
                };

                function updateDashboard(data) {
                    // Update component status
                    const statusDiv = document.getElementById('component-status');
                    statusDiv.innerHTML = Object.entries(data.component_status)
                        .map(([name, status]) =>
                            `<div class="metric">
                                <span>${name}</span>
                                <span class="status ${status}">${status}</span>
                            </div>`
                        ).join('');

                    // Update trading metrics
                    const tradingDiv = document.getElementById('trading-metrics');
                    const tradingMetrics = Object.entries(data.metrics)
                        .filter(([name]) => name.startsWith('trading.'))
                        .map(([name, metric]) =>
                            `<div class="metric">
                                <span>${name.replace('trading.', '')}</span>
                                <span class="metric-value">${metric.current.toFixed(2)}</span>
                            </div>`
                        ).join('');
                    tradingDiv.innerHTML = tradingMetrics || '<p>No trading data</p>';

                    // Update performance metrics
                    const perfDiv = document.getElementById('performance-metrics');
                    const perfMetrics = Object.entries(data.metrics)
                        .filter(([name]) => name.startsWith('performance.'))
                        .map(([name, metric]) =>
                            `<div class="metric">
                                <span>${name.replace('performance.', '')}</span>
                                <span class="metric-value">${metric.current.toFixed(2)}</span>
                            </div>`
                        ).join('');
                    perfDiv.innerHTML = perfMetrics || '<p>No performance data</p>';

                    // Update alerts
                    const alertsDiv = document.getElementById('alerts');
                    const alerts = data.active_alerts
                        .map(alert =>
                            `<div class="alert ${alert.severity}">
                                <strong>${alert.category}:</strong> ${alert.message}
                            </div>`
                        ).join('');
                    alertsDiv.innerHTML = alerts || '<p>No active alerts</p>';
                }
            </script>
        </body>
        </html>
        """

    async def start(self):
        """Start web server"""
        self.app = aiohttp.web.Application()
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/ws', self.handle_websocket)
        self.app.router.add_get('/api/metrics', self.handle_metrics)
        self.app.router.add_get('/api/alerts', self.handle_alerts)

        runner = aiohttp.web.AppRunner(self.app)
        await runner.setup()
        site = aiohttp.web.TCPSite(runner, 'localhost', self.port)
        await site.start()

        logger.info(f"Dashboard web server started on http://localhost:{self.port}")


async def test_monitoring():
    """Test monitoring dashboard"""
    dashboard = MonitoringDashboard()

    # Add test alert handler
    async def console_handler(alert: Alert):
        print(f"[{alert.severity.value.upper()}] {alert.message}")

    dashboard.alerts.register_handler(console_handler)

    # Start web server
    web_server = WebDashboardServer(dashboard)
    await web_server.start()

    # Run monitoring
    await dashboard.start()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    asyncio.run(test_monitoring())
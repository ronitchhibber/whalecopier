"""
Health Monitoring System - Real-time system health and performance monitoring.

Features:
- System health checks (CPU, memory, disk, network)
- Component health monitoring
- Performance metrics tracking
- Automatic health reporting
- Health dashboard endpoint
- Degraded service detection
"""

import asyncio
import psutil
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass, field
import json

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """System health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


class ComponentType(Enum):
    """Types of monitored components"""
    ENGINE = "engine"
    DATABASE = "database"
    API = "api"
    ANALYTICS = "analytics"
    RISK_MANAGER = "risk_manager"
    POSITION_TRACKER = "position_tracker"
    EXTERNAL_API = "external_api"


@dataclass
class HealthCheck:
    """Health check result"""
    component: ComponentType
    status: HealthStatus
    timestamp: datetime
    message: str
    metrics: Dict = field(default_factory=dict)
    latency_ms: Optional[float] = None


@dataclass
class SystemMetrics:
    """System resource metrics"""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # CPU
    cpu_percent: float = 0.0
    cpu_count: int = 0
    load_average: tuple = field(default_factory=lambda: (0.0, 0.0, 0.0))

    # Memory
    memory_total_mb: float = 0.0
    memory_used_mb: float = 0.0
    memory_percent: float = 0.0

    # Disk
    disk_total_gb: float = 0.0
    disk_used_gb: float = 0.0
    disk_percent: float = 0.0

    # Network
    network_sent_mb: float = 0.0
    network_recv_mb: float = 0.0

    # Process
    process_memory_mb: float = 0.0
    process_threads: int = 0
    process_open_files: int = 0


@dataclass
class HealthMonitorConfig:
    """Configuration for health monitor"""

    # Check intervals
    system_check_interval_seconds: int = 60
    component_check_interval_seconds: int = 30
    api_check_interval_seconds: int = 120

    # Thresholds
    cpu_warning_percent: float = 70.0
    cpu_critical_percent: float = 90.0
    memory_warning_percent: float = 75.0
    memory_critical_percent: float = 90.0
    disk_warning_percent: float = 80.0
    disk_critical_percent: float = 95.0

    # Component timeouts
    component_timeout_seconds: int = 10
    api_timeout_seconds: int = 30

    # Reporting
    report_interval_minutes: int = 60
    health_history_hours: int = 24


class SystemHealthChecker:
    """Checks system resource health"""

    def __init__(self, config: HealthMonitorConfig):
        self.config = config
        self.baseline_network: Optional[Dict] = None

    def check(self) -> Tuple[HealthStatus, SystemMetrics]:
        """Check system health"""

        metrics = self.collect_metrics()
        status = self.evaluate_health(metrics)

        return status, metrics

    def collect_metrics(self) -> SystemMetrics:
        """Collect system resource metrics"""

        metrics = SystemMetrics()

        # CPU
        metrics.cpu_percent = psutil.cpu_percent(interval=1)
        metrics.cpu_count = psutil.cpu_count()
        try:
            metrics.load_average = psutil.getloadavg()
        except:
            pass  # Not available on all platforms

        # Memory
        mem = psutil.virtual_memory()
        metrics.memory_total_mb = mem.total / (1024 * 1024)
        metrics.memory_used_mb = mem.used / (1024 * 1024)
        metrics.memory_percent = mem.percent

        # Disk
        disk = psutil.disk_usage('/')
        metrics.disk_total_gb = disk.total / (1024 * 1024 * 1024)
        metrics.disk_used_gb = disk.used / (1024 * 1024 * 1024)
        metrics.disk_percent = disk.percent

        # Network
        net = psutil.net_io_counters()
        if self.baseline_network is None:
            self.baseline_network = {
                'sent': net.bytes_sent,
                'recv': net.bytes_recv
            }

        metrics.network_sent_mb = (net.bytes_sent - self.baseline_network['sent']) / (1024 * 1024)
        metrics.network_recv_mb = (net.bytes_recv - self.baseline_network['recv']) / (1024 * 1024)

        # Process
        try:
            process = psutil.Process()
            metrics.process_memory_mb = process.memory_info().rss / (1024 * 1024)
            metrics.process_threads = process.num_threads()
            metrics.process_open_files = len(process.open_files())
        except:
            pass

        return metrics

    def evaluate_health(self, metrics: SystemMetrics) -> HealthStatus:
        """Evaluate overall system health"""

        # Check CPU
        if metrics.cpu_percent >= self.config.cpu_critical_percent:
            return HealthStatus.CRITICAL
        elif metrics.cpu_percent >= self.config.cpu_warning_percent:
            return HealthStatus.DEGRADED

        # Check memory
        if metrics.memory_percent >= self.config.memory_critical_percent:
            return HealthStatus.CRITICAL
        elif metrics.memory_percent >= self.config.memory_warning_percent:
            return HealthStatus.DEGRADED

        # Check disk
        if metrics.disk_percent >= self.config.disk_critical_percent:
            return HealthStatus.CRITICAL
        elif metrics.disk_percent >= self.config.disk_warning_percent:
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY


class ComponentHealthChecker:
    """Checks health of application components"""

    def __init__(self, config: HealthMonitorConfig):
        self.config = config
        self.components: Dict[ComponentType, Callable] = {}

    def register_component(self, component_type: ComponentType, health_check_func):
        """Register a component with its health check function"""
        self.components[component_type] = health_check_func
        logger.info(f"Registered health check for {component_type.value}")

    async def check_all(self) -> List[HealthCheck]:
        """Check health of all registered components"""

        results = []

        for component_type, check_func in self.components.items():
            result = await self.check_component(component_type, check_func)
            results.append(result)

        return results

    async def check_component(self, component_type: ComponentType, check_func) -> HealthCheck:
        """Check health of a single component"""

        start_time = datetime.utcnow()

        try:
            # Run health check with timeout
            result = await asyncio.wait_for(
                check_func(),
                timeout=self.config.component_timeout_seconds
            )

            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            return HealthCheck(
                component=component_type,
                status=result.get('status', HealthStatus.HEALTHY),
                timestamp=datetime.utcnow(),
                message=result.get('message', 'OK'),
                metrics=result.get('metrics', {}),
                latency_ms=latency
            )

        except asyncio.TimeoutError:
            return HealthCheck(
                component=component_type,
                status=HealthStatus.UNHEALTHY,
                timestamp=datetime.utcnow(),
                message=f"Health check timed out after {self.config.component_timeout_seconds}s",
                latency_ms=self.config.component_timeout_seconds * 1000
            )

        except Exception as e:
            return HealthCheck(
                component=component_type,
                status=HealthStatus.UNHEALTHY,
                timestamp=datetime.utcnow(),
                message=f"Health check failed: {str(e)}",
                latency_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
            )


class HealthMonitor:
    """Main health monitoring system"""

    def __init__(self, config: Optional[HealthMonitorConfig] = None):
        self.config = config or HealthMonitorConfig()

        self.system_checker = SystemHealthChecker(self.config)
        self.component_checker = ComponentHealthChecker(self.config)

        self.health_history: List[Dict] = []
        self.last_report_time: Optional[datetime] = None

        self.running = False
        self.monitoring_tasks: List[asyncio.Task] = []

    async def start(self):
        """Start health monitoring"""
        self.running = True

        # Start monitoring loops
        self.monitoring_tasks = [
            asyncio.create_task(self._system_monitoring_loop()),
            asyncio.create_task(self._component_monitoring_loop()),
            asyncio.create_task(self._reporting_loop())
        ]

        logger.info("✅ Health Monitor started")

    async def stop(self):
        """Stop health monitoring"""
        self.running = False

        for task in self.monitoring_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        logger.info("Health Monitor stopped")

    async def _system_monitoring_loop(self):
        """Monitor system resources"""
        while self.running:
            try:
                status, metrics = self.system_checker.check()

                # Log if unhealthy
                if status in [HealthStatus.DEGRADED, HealthStatus.UNHEALTHY, HealthStatus.CRITICAL]:
                    logger.warning(f"System health: {status.value}")
                    logger.warning(f"  CPU: {metrics.cpu_percent:.1f}%")
                    logger.warning(f"  Memory: {metrics.memory_percent:.1f}%")
                    logger.warning(f"  Disk: {metrics.disk_percent:.1f}%")

                # Store in history
                self._record_health({
                    'type': 'system',
                    'status': status.value,
                    'metrics': {
                        'cpu_percent': metrics.cpu_percent,
                        'memory_percent': metrics.memory_percent,
                        'disk_percent': metrics.disk_percent,
                        'process_memory_mb': metrics.process_memory_mb
                    }
                })

                await asyncio.sleep(self.config.system_check_interval_seconds)

            except Exception as e:
                logger.error(f"Error in system monitoring: {e}")
                await asyncio.sleep(5)

    async def _component_monitoring_loop(self):
        """Monitor application components"""
        while self.running:
            try:
                checks = await self.component_checker.check_all()

                for check in checks:
                    if check.status in [HealthStatus.DEGRADED, HealthStatus.UNHEALTHY, HealthStatus.CRITICAL]:
                        logger.warning(f"Component {check.component.value}: {check.status.value} - {check.message}")

                    self._record_health({
                        'type': 'component',
                        'component': check.component.value,
                        'status': check.status.value,
                        'message': check.message,
                        'latency_ms': check.latency_ms,
                        'metrics': check.metrics
                    })

                await asyncio.sleep(self.config.component_check_interval_seconds)

            except Exception as e:
                logger.error(f"Error in component monitoring: {e}")
                await asyncio.sleep(5)

    async def _reporting_loop(self):
        """Generate periodic health reports"""
        while self.running:
            try:
                await asyncio.sleep(self.config.report_interval_minutes * 60)

                report = self.generate_health_report()
                logger.info("=" * 80)
                logger.info("HEALTH REPORT")
                logger.info("=" * 80)
                logger.info(f"Overall Status: {report['overall_status']}")
                logger.info(f"Uptime: {report['uptime_hours']:.1f} hours")
                logger.info(f"System Health: {report['system']['status']}")
                logger.info(f"Component Health: {report['components_healthy']}/{report['components_total']}")
                logger.info("=" * 80)

                self.last_report_time = datetime.utcnow()

            except Exception as e:
                logger.error(f"Error in reporting loop: {e}")
                await asyncio.sleep(60)

    def _record_health(self, health_data: Dict):
        """Record health data in history"""
        health_data['timestamp'] = datetime.utcnow().isoformat()
        self.health_history.append(health_data)

        # Trim old history
        cutoff = datetime.utcnow() - timedelta(hours=self.config.health_history_hours)
        self.health_history = [
            h for h in self.health_history
            if datetime.fromisoformat(h['timestamp']) > cutoff
        ]

    def register_component(self, component_type: ComponentType, health_check_func):
        """Register a component for health monitoring"""
        self.component_checker.register_component(component_type, health_check_func)

    def get_current_health(self) -> Dict:
        """Get current health status"""

        # Get latest system check
        system_status, system_metrics = self.system_checker.check()

        # Get latest component checks
        component_status = {}
        for component_type in self.component_checker.components.keys():
            # Get most recent check from history
            recent = [
                h for h in self.health_history
                if h.get('type') == 'component' and h.get('component') == component_type.value
            ]
            if recent:
                latest = recent[-1]
                component_status[component_type.value] = {
                    'status': latest['status'],
                    'message': latest.get('message'),
                    'latency_ms': latest.get('latency_ms')
                }

        # Determine overall status
        statuses = [system_status] + [
            HealthStatus(c['status']) for c in component_status.values()
        ]

        if any(s == HealthStatus.CRITICAL for s in statuses):
            overall = HealthStatus.CRITICAL
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            overall = HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.HEALTHY

        return {
            'overall_status': overall.value,
            'timestamp': datetime.utcnow().isoformat(),
            'system': {
                'status': system_status.value,
                'cpu_percent': system_metrics.cpu_percent,
                'memory_percent': system_metrics.memory_percent,
                'disk_percent': system_metrics.disk_percent,
                'process_memory_mb': system_metrics.process_memory_mb
            },
            'components': component_status
        }

    def generate_health_report(self) -> Dict:
        """Generate comprehensive health report"""

        current = self.get_current_health()

        # Calculate uptime (time since first health record)
        if self.health_history:
            first_record = datetime.fromisoformat(self.health_history[0]['timestamp'])
            uptime_hours = (datetime.utcnow() - first_record).total_seconds() / 3600
        else:
            uptime_hours = 0

        # Component statistics
        components_total = len(self.component_checker.components)
        components_healthy = sum(
            1 for c in current['components'].values()
            if c['status'] == HealthStatus.HEALTHY.value
        )

        # System statistics from history
        system_history = [h for h in self.health_history if h.get('type') == 'system']
        if system_history:
            avg_cpu = sum(h['metrics'].get('cpu_percent', 0) for h in system_history) / len(system_history)
            avg_memory = sum(h['metrics'].get('memory_percent', 0) for h in system_history) / len(system_history)
            max_cpu = max(h['metrics'].get('cpu_percent', 0) for h in system_history)
            max_memory = max(h['metrics'].get('memory_percent', 0) for h in system_history)
        else:
            avg_cpu = avg_memory = max_cpu = max_memory = 0

        return {
            'overall_status': current['overall_status'],
            'timestamp': current['timestamp'],
            'uptime_hours': uptime_hours,
            'system': current['system'],
            'system_averages': {
                'avg_cpu_percent': avg_cpu,
                'avg_memory_percent': avg_memory,
                'max_cpu_percent': max_cpu,
                'max_memory_percent': max_memory
            },
            'components': current['components'],
            'components_total': components_total,
            'components_healthy': components_healthy,
            'health_checks_count': len(self.health_history)
        }

    def export_health_history(self, filename: str):
        """Export health history to JSON file"""
        try:
            with open(filename, 'w') as f:
                json.dump({
                    'export_timestamp': datetime.utcnow().isoformat(),
                    'history': self.health_history,
                    'current_health': self.get_current_health()
                }, f, indent=2)

            logger.info(f"Health history exported to {filename}")

        except Exception as e:
            logger.error(f"Failed to export health history: {e}")


# Example component health check functions

async def engine_health_check() -> Dict:
    """Example health check for copy trading engine"""
    # In real implementation, check if engine is running, processing trades, etc.
    return {
        'status': HealthStatus.HEALTHY,
        'message': 'Engine is running and processing trades',
        'metrics': {
            'active_whales': 10,
            'open_positions': 5,
            'trades_today': 15
        }
    }


async def database_health_check() -> Dict:
    """Example health check for database"""
    try:
        # In real implementation, execute a simple query
        # conn = get_db_connection()
        # conn.execute("SELECT 1")
        return {
            'status': HealthStatus.HEALTHY,
            'message': 'Database connection OK',
            'metrics': {
                'connection_pool_size': 10,
                'active_connections': 3
            }
        }
    except Exception as e:
        return {
            'status': HealthStatus.UNHEALTHY,
            'message': f'Database error: {str(e)}'
        }


async def analytics_health_check() -> Dict:
    """Example health check for analytics system"""
    return {
        'status': HealthStatus.HEALTHY,
        'message': 'Analytics processing normally',
        'metrics': {
            'metrics_updated': 'recently',
            'data_lag_seconds': 30
        }
    }

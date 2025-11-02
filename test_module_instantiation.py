#!/usr/bin/env python3
"""
Test module instantiation and functionality.
This attempts to create instances of key classes to verify they work.
"""

import sys
import logging
from pathlib import Path
from decimal import Decimal
from datetime import datetime

# Setup path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(level=logging.WARNING)

test_results = {
    'total': 0,
    'passed': 0,
    'failed': 0,
    'failures': []
}

def test_import_and_instantiate(module_name, class_name, *args, **kwargs):
    """Test importing a module and instantiating a class."""
    test_results['total'] += 1

    try:
        # Import the module
        module = __import__(module_name, fromlist=[class_name])

        # Get the class
        if not hasattr(module, class_name):
            raise AttributeError(f"Module {module_name} does not have class {class_name}")

        cls = getattr(module, class_name)

        # Try to instantiate
        instance = cls(*args, **kwargs)

        print(f"✓ PASS: {module_name}.{class_name}")
        test_results['passed'] += 1
        return True

    except Exception as e:
        error = f"{module_name}.{class_name}: {str(e)}"
        print(f"✗ FAIL: {error}")
        test_results['failed'] += 1
        test_results['failures'].append({
            'module': module_name,
            'class': class_name,
            'error': str(e)
        })
        return False

def main():
    """Test key classes from each module."""

    print("=" * 80)
    print("MODULE INSTANTIATION TESTS - WEEKS 9-14")
    print("=" * 80)
    print()

    # Week 9-10 Analytics
    print("WEEK 9-10: ANALYTICS")
    print("-" * 80)

    # Performance Metrics Engine
    from src.analytics.performance_metrics_engine import PerformanceConfig
    test_import_and_instantiate('src.analytics.performance_metrics_engine', 'PerformanceMetricsEngine', PerformanceConfig())

    # Trade Attribution Analyzer
    from src.analytics.trade_attribution_analyzer import AttributionConfig
    test_import_and_instantiate('src.analytics.trade_attribution_analyzer', 'TradeAttributionAnalyzer', AttributionConfig())

    # Edge Detection System
    from src.analytics.edge_detection_system import EdgeConfig
    test_import_and_instantiate('src.analytics.edge_detection_system', 'EdgeDetectionSystem', EdgeConfig())

    # Benchmarking System
    from src.analytics.benchmarking_system import BenchmarkConfig
    test_import_and_instantiate('src.analytics.benchmarking_system', 'BenchmarkingSystem', BenchmarkConfig())

    # CUSUM Edge Decay Detector
    from src.analytics.cusum_edge_decay_detector import CUSUMConfig
    test_import_and_instantiate('src.analytics.cusum_edge_decay_detector', 'CUSUMEdgeDecayDetector', CUSUMConfig())

    # Whale Lifecycle Tracker
    from src.analytics.whale_lifecycle_tracker import LifecycleConfig
    test_import_and_instantiate('src.analytics.whale_lifecycle_tracker', 'WhaleLifecycleTracker', LifecycleConfig())

    # Market Efficiency Analyzer
    from src.analytics.market_efficiency_analyzer import EfficiencyConfig
    test_import_and_instantiate('src.analytics.market_efficiency_analyzer', 'MarketEfficiencyAnalyzer', EfficiencyConfig())

    # Adaptive Threshold Manager
    from src.analytics.adaptive_threshold_manager import AdaptiveConfig
    test_import_and_instantiate('src.analytics.adaptive_threshold_manager', 'AdaptiveThresholdManager', AdaptiveConfig())

    # Reporting Engine
    from src.analytics.reporting_engine import ReportConfig
    test_import_and_instantiate('src.analytics.reporting_engine', 'ReportingEngine', ReportConfig())

    # Analytics Integration
    from src.analytics.analytics_integration import AnalyticsIntegrationConfig
    test_import_and_instantiate('src.analytics.analytics_integration', 'AnalyticsIntegration', AnalyticsIntegrationConfig())

    print()

    # Week 11-12 Optimization
    print("WEEK 11-12: OPTIMIZATION")
    print("-" * 80)

    # Strategy Parameter Optimizer
    from src.optimization.strategy_parameter_optimizer import OptimizerConfig
    test_import_and_instantiate('src.optimization.strategy_parameter_optimizer', 'StrategyParameterOptimizer', OptimizerConfig())

    # Portfolio Optimizer
    from src.optimization.portfolio_optimizer import PortfolioConfig
    test_import_and_instantiate('src.optimization.portfolio_optimizer', 'PortfolioOptimizer', PortfolioConfig())

    # Optimization Integration
    test_import_and_instantiate('src.optimization.optimization_integration', 'MultiStrategyEnsemble')

    print()

    # Week 13-14 Production & Risk
    print("WEEK 13-14: PRODUCTION & RISK MANAGEMENT")
    print("-" * 80)

    # Risk Manager
    from src.risk_management.risk_manager import RiskManagerConfig
    test_import_and_instantiate('src.risk_management.risk_manager', 'RiskManager', RiskManagerConfig())

    # Alert System
    from src.risk_management.alert_system import AlertConfig
    test_import_and_instantiate('src.risk_management.alert_system', 'AlertSystem', AlertConfig())

    # Health Monitor
    from src.production.health_monitor import HealthMonitorConfig
    test_import_and_instantiate('src.production.health_monitor', 'HealthMonitor', HealthMonitorConfig())

    print()
    print("=" * 80)
    print("INSTANTIATION TEST RESULTS")
    print("=" * 80)
    print(f"Total tests: {test_results['total']}")
    print(f"Passed: {test_results['passed']}")
    print(f"Failed: {test_results['failed']}")
    print()

    if test_results['failures']:
        print("FAILURES:")
        print("-" * 80)
        for failure in test_results['failures']:
            print(f"\n{failure['module']}.{failure['class']}")
            print(f"Error: {failure['error']}")

    return 0 if test_results['failed'] == 0 else 1

if __name__ == '__main__':
    exit(main())

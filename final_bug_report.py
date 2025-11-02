#!/usr/bin/env python3
"""
Final comprehensive bug detection and reporting for Weeks 9-14 modules.
"""

import sys
import traceback
from pathlib import Path
from typing import Dict, List

# Setup path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

class BugDetector:
    """Detects bugs in modules."""

    def __init__(self):
        self.modules = [
            ('src.analytics.performance_metrics_engine', 'PerformanceMetricsEngine', 'PerformanceConfig'),
            ('src.analytics.trade_attribution_analyzer', 'TradeAttributionAnalyzer', 'AttributionConfig'),
            ('src.analytics.edge_detection_system', 'EdgeDetectionSystem', 'EdgeConfig'),
            ('src.analytics.benchmarking_system', 'BenchmarkingSystem', 'BenchmarkConfig'),
            ('src.analytics.cusum_edge_decay_detector', 'CUSUMEdgeDecayDetector', 'CUSUMConfig'),
            ('src.analytics.whale_lifecycle_tracker', 'WhaleLifecycleTracker', 'LifecycleConfig'),
            ('src.analytics.market_efficiency_analyzer', 'MarketEfficiencyAnalyzer', 'EfficiencyConfig'),
            ('src.analytics.adaptive_threshold_manager', 'AdaptiveThresholdManager', 'AdaptiveConfig'),
            ('src.analytics.reporting_engine', 'ReportingEngine', 'ReportConfig'),
            ('src.analytics.analytics_integration', 'AnalyticsIntegration', 'AnalyticsIntegrationConfig'),
            ('src.optimization.strategy_parameter_optimizer', 'StrategyParameterOptimizer', 'OptimizationConfig'),
            ('src.optimization.portfolio_optimizer', 'PortfolioOptimizer', 'PortfolioConfig'),
            ('src.optimization.optimization_integration', 'MultiStrategyEnsemble', 'EnsembleConfig'),
            ('src.risk_management.risk_manager', 'RiskManager', 'RiskManagerConfig'),
            ('src.risk_management.alert_system', 'AlertSystem', 'AlertConfig'),
            ('src.production.health_monitor', 'HealthMonitor', 'HealthMonitorConfig'),
        ]

        self.results = {
            'passed': [],
            'import_errors': [],
            'instantiation_errors': [],
            'config_errors': []
        }

    def test_module(self, module_name: str, class_name: str, config_class_name: str) -> bool:
        """Test a module."""
        try:
            # Import module
            module = __import__(module_name, fromlist=[class_name, config_class_name])

            # Check if class exists
            if not hasattr(module, class_name):
                self.results['import_errors'].append(
                    f"{module_name}: Class '{class_name}' not found"
                )
                return False

            # Check if config class exists
            if not hasattr(module, config_class_name):
                self.results['config_errors'].append(
                    f"{module_name}: Config class '{config_class_name}' not found"
                )
                return False

            # Try to instantiate config
            config_cls = getattr(module, config_class_name)
            try:
                config_instance = config_cls()
            except Exception as e:
                self.results['config_errors'].append(
                    f"{module_name}.{config_class_name}: {str(e)}"
                )
                return False

            # Try to instantiate class
            cls = getattr(module, class_name)
            try:
                instance = cls(config_instance)
            except Exception as e:
                self.results['instantiation_errors'].append(
                    f"{module_name}.{class_name}: {str(e)}"
                )
                return False

            self.results['passed'].append(module_name)
            return True

        except ImportError as e:
            self.results['import_errors'].append(
                f"{module_name}: Import failed - {str(e)}"
            )
            return False
        except Exception as e:
            self.results['import_errors'].append(
                f"{module_name}: Unexpected error - {str(e)}"
            )
            return False

    def run_all_tests(self) -> None:
        """Run tests on all modules."""
        for module_name, class_name, config_class_name in self.modules:
            self.test_module(module_name, class_name, config_class_name)

    def print_report(self) -> None:
        """Print test report."""
        total = len(self.modules)
        passed = len(self.results['passed'])
        failed = total - passed

        print("=" * 80)
        print("COMPREHENSIVE BUG DETECTION REPORT - WEEKS 9-14 MODULES")
        print("=" * 80)
        print()

        print("SUMMARY")
        print("-" * 80)
        print(f"Total modules tested: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print()

        if self.results['passed']:
            print("PASSED MODULES:")
            print("-" * 80)
            for module in self.results['passed']:
                print(f"✓ {module}")
            print()

        if self.results['import_errors']:
            print("IMPORT ERRORS:")
            print("-" * 80)
            for error in self.results['import_errors']:
                print(f"✗ {error}")
            print()

        if self.results['config_errors']:
            print("CONFIG ERRORS:")
            print("-" * 80)
            for error in self.results['config_errors']:
                print(f"⚠ {error}")
            print()

        if self.results['instantiation_errors']:
            print("INSTANTIATION ERRORS:")
            print("-" * 80)
            for error in self.results['instantiation_errors']:
                print(f"✗ {error}")
            print()

        # Final status
        print("=" * 80)
        if failed == 0:
            print("✓ ALL MODULES PASSED!")
        else:
            print(f"✗ {failed} MODULE(S) HAVE ISSUES")

def main():
    """Run bug detection."""
    detector = BugDetector()
    detector.run_all_tests()
    detector.print_report()

    # Return exit code
    failed = len(detector.results['import_errors']) + len(detector.results['instantiation_errors']) + len(detector.results['config_errors'])
    return 0 if failed == 0 else 1

if __name__ == '__main__':
    exit(main())

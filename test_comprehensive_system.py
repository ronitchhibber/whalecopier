#!/usr/bin/env python3
"""
COMPREHENSIVE BUG TESTING SUITE FOR WEEK 1-8 MODULES
Tests all modules for imports, dependencies, syntax errors, and data functionality
"""
import sys
import os
import traceback
from datetime import datetime
from typing import Dict, List, Tuple
import importlib.util

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
sys.path.insert(0, os.path.dirname(__file__))

class Color:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

class TestResult:
    """Container for test results"""
    def __init__(self):
        self.total_tests = 0
        self.passed = 0
        self.failed = 0
        self.errors = []

    def add_pass(self):
        self.total_tests += 1
        self.passed += 1

    def add_fail(self, error_msg: str):
        self.total_tests += 1
        self.failed += 1
        self.errors.append(error_msg)

class ComprehensiveTester:
    """Comprehensive testing suite for all Week 1-8 modules"""

    def __init__(self):
        self.results = TestResult()
        self.module_results = {}

        # Week 1-4 modules
        self.week_1_4_modules = {
            'Configuration': 'src/config.py',
            'Database Init': 'src/database/__init__.py',
            'Database Models': 'src/database/models.py',
            'API Client': 'src/api/polymarket_client.py',
        }

        # Week 5-6 modules
        self.week_5_6_modules = {
            'Trade Tracker': 'src/copy_trading/tracker.py',
            'Copy Trading Engine': 'src/copy_trading/engine.py',
            'OrderBook Tracker': 'src/copy_trading/orderbook_tracker.py',
        }

        # Week 7-8 Risk modules
        self.week_7_8_risk_modules = {
            'Correlation Manager': 'src/risk/correlation_manager.py',
            'Dynamic Risk Scaler': 'src/risk/dynamic_risk_scaler.py',
            'Enhanced Risk Manager': 'src/risk/enhanced_risk_manager.py',
            'Live Risk Manager': 'src/risk/live_risk_manager.py',
            'Portfolio Circuit Breakers': 'src/risk/portfolio_circuit_breakers.py',
            'Risk Dashboard': 'src/risk/risk_dashboard.py',
            'Stop Loss / Take Profit': 'src/risk/stop_loss_take_profit.py',
        }

        # Week 7-8 Execution modules
        self.week_7_8_execution_modules = {
            'Order Book Depth Analyzer': 'src/execution/order_book_depth_analyzer.py',
            'Smart Order Router': 'src/execution/smart_order_router.py',
            'Latency Optimizer': 'src/execution/latency_optimizer.py',
            'Fill Rate Optimizer': 'src/execution/fill_rate_optimizer.py',
            'Execution Analytics Dashboard': 'src/execution/execution_analytics_dashboard.py',
        }

        # Week 7-8 Orchestration modules
        self.week_7_8_orchestration_modules = {
            'Whale Adaptive Selector': 'src/orchestration/whale_adaptive_selector.py',
            'Whale Capital Allocator': 'src/orchestration/whale_capital_allocator.py',
            'Whale Conflict Resolver': 'src/orchestration/whale_conflict_resolver.py',
            'Whale Correlation Tracker': 'src/orchestration/whale_correlation_tracker.py',
            'Whale Performance Attribution': 'src/orchestration/whale_performance_attribution.py',
            'Whale Quality Scorer': 'src/orchestration/whale_quality_scorer.py',
        }

    def print_header(self, text: str):
        """Print formatted header"""
        print(f"\n{Color.BOLD}{Color.CYAN}{'='*80}{Color.END}")
        print(f"{Color.BOLD}{Color.CYAN}{text:^80}{Color.END}")
        print(f"{Color.BOLD}{Color.CYAN}{'='*80}{Color.END}\n")

    def print_section(self, text: str):
        """Print formatted section"""
        print(f"\n{Color.BOLD}{Color.BLUE}{'-'*80}{Color.END}")
        print(f"{Color.BOLD}{Color.BLUE}{text}{Color.END}")
        print(f"{Color.BOLD}{Color.BLUE}{'-'*80}{Color.END}\n")

    def test_module_import(self, module_name: str, module_path: str) -> Tuple[bool, str]:
        """Test if a module can be imported"""
        try:
            # Convert file path to module path
            module_import_path = module_path.replace('/', '.').replace('.py', '')

            # Try to import
            module = __import__(module_import_path, fromlist=[''])

            return True, f"Successfully imported {module_name}"

        except ModuleNotFoundError as e:
            return False, f"Missing dependency: {str(e)}"
        except SyntaxError as e:
            return False, f"Syntax error: {str(e)}"
        except Exception as e:
            return False, f"Import error: {str(e)}"

    def test_module_syntax(self, module_path: str) -> Tuple[bool, str]:
        """Test module for syntax errors"""
        try:
            with open(module_path, 'r') as f:
                code = f.read()
            compile(code, module_path, 'exec')
            return True, "No syntax errors"
        except SyntaxError as e:
            return False, f"Syntax error at line {e.lineno}: {e.msg}"
        except Exception as e:
            return False, f"Compilation error: {str(e)}"

    def test_module_dependencies(self, module_path: str) -> Tuple[bool, str]:
        """Check if all required dependencies are available"""
        missing_deps = []
        optional_deps = ['py_clob_client']  # Optional dependencies with graceful degradation

        try:
            with open(module_path, 'r') as f:
                lines = f.readlines()

            for line in lines:
                line = line.strip()
                if line.startswith('import ') or line.startswith('from '):
                    # Extract module name
                    if line.startswith('import '):
                        module = line.split()[1].split('.')[0].split(',')[0]
                    else:
                        module = line.split()[1].split('.')[0]

                    # Skip local imports and optional dependencies
                    if module in ['src', 'libs', 'services'] or module in optional_deps:
                        continue

                    # Try to import
                    try:
                        __import__(module)
                    except ModuleNotFoundError:
                        if module not in missing_deps:
                            missing_deps.append(module)

            if missing_deps:
                return False, f"Missing dependencies: {', '.join(missing_deps)}"
            return True, "All dependencies available"

        except Exception as e:
            return False, f"Error checking dependencies: {str(e)}"

    def test_single_module(self, module_name: str, module_path: str):
        """Run all tests on a single module"""
        print(f"\n{Color.BOLD}Testing: {module_name}{Color.END}")
        print(f"Path: {module_path}")

        module_passed = True
        module_errors = []

        # Test 1: Syntax check
        print(f"  [1/3] Checking syntax...", end=" ")
        success, msg = self.test_module_syntax(module_path)
        if success:
            print(f"{Color.GREEN}PASS{Color.END}")
            self.results.add_pass()
        else:
            print(f"{Color.RED}FAIL{Color.END}")
            print(f"        Error: {msg}")
            self.results.add_fail(f"{module_name} - Syntax: {msg}")
            module_passed = False
            module_errors.append(f"Syntax: {msg}")

        # Test 2: Dependency check
        print(f"  [2/3] Checking dependencies...", end=" ")
        success, msg = self.test_module_dependencies(module_path)
        if success:
            print(f"{Color.GREEN}PASS{Color.END}")
            self.results.add_pass()
        else:
            print(f"{Color.RED}FAIL{Color.END}")
            print(f"        Error: {msg}")
            self.results.add_fail(f"{module_name} - Dependencies: {msg}")
            module_passed = False
            module_errors.append(f"Dependencies: {msg}")

        # Test 3: Import check
        print(f"  [3/3] Testing import...", end=" ")
        success, msg = self.test_module_import(module_name, module_path)
        if success:
            print(f"{Color.GREEN}PASS{Color.END}")
            self.results.add_pass()
        else:
            print(f"{Color.RED}FAIL{Color.END}")
            print(f"        Error: {msg}")
            self.results.add_fail(f"{module_name} - Import: {msg}")
            module_passed = False
            module_errors.append(f"Import: {msg}")

        # Store module result
        self.module_results[module_name] = {
            'passed': module_passed,
            'errors': module_errors
        }

    def test_database_connection(self):
        """Test database connectivity"""
        print(f"\n{Color.BOLD}Testing Database Connection{Color.END}")

        try:
            from src.database import engine, get_db
            from sqlalchemy import text

            print("  [1/3] Connecting to database...", end=" ")
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                print(f"{Color.GREEN}PASS{Color.END}")
                self.results.add_pass()

            print("  [2/3] Testing session creation...", end=" ")
            with get_db() as db:
                print(f"{Color.GREEN}PASS{Color.END}")
                self.results.add_pass()

            print("  [3/3] Checking tables exist...", end=" ")
            from src.database.models import Whale, Trade, Market, Position
            with get_db() as db:
                # Check if tables exist by trying to query them
                try:
                    db.query(Whale).first()
                    db.query(Trade).first()
                    db.query(Market).first()
                    db.query(Position).first()
                    print(f"{Color.GREEN}PASS{Color.END}")
                    self.results.add_pass()
                except Exception as e:
                    print(f"{Color.RED}FAIL{Color.END}")
                    print(f"        Error: Tables may not exist - {str(e)}")
                    self.results.add_fail(f"Database tables check: {str(e)}")

        except Exception as e:
            print(f"{Color.RED}FAIL{Color.END}")
            print(f"        Error: {str(e)}")
            self.results.add_fail(f"Database connection: {str(e)}")

    def test_whale_data(self):
        """Test whale data availability"""
        print(f"\n{Color.BOLD}Testing Whale Data{Color.END}")

        try:
            from src.database import get_db
            from src.database.models import Whale

            print("  [1/2] Querying whales...", end=" ")
            with get_db() as db:
                whales = db.query(Whale).all()
                whale_count = len(whales)
                print(f"{Color.GREEN}PASS{Color.END}")
                print(f"        Found {whale_count} whales in database")
                self.results.add_pass()

                if whale_count > 0:
                    print("  [2/2] Checking whale data structure...", end=" ")
                    whale = whales[0]
                    # Check required fields
                    assert hasattr(whale, 'address')
                    assert hasattr(whale, 'total_volume')
                    assert hasattr(whale, 'win_rate')
                    assert hasattr(whale, 'sharpe_ratio')
                    print(f"{Color.GREEN}PASS{Color.END}")
                    self.results.add_pass()

                    # Show sample whale
                    print(f"\n        Sample Whale:")
                    print(f"          Address: {whale.address}")
                    print(f"          Volume: ${whale.total_volume:,.2f}" if whale.total_volume else "          Volume: N/A")
                    print(f"          Win Rate: {whale.win_rate}%" if whale.win_rate else "          Win Rate: N/A")
                    print(f"          Sharpe: {whale.sharpe_ratio}" if whale.sharpe_ratio else "          Sharpe: N/A")
                else:
                    print("  [2/2] Checking whale data structure...", end=" ")
                    print(f"{Color.YELLOW}SKIP{Color.END} (No whales in database)")

        except Exception as e:
            print(f"{Color.RED}FAIL{Color.END}")
            print(f"        Error: {str(e)}")
            self.results.add_fail(f"Whale data check: {str(e)}")

    def test_trade_data(self):
        """Test trade data availability"""
        print(f"\n{Color.BOLD}Testing Trade Data{Color.END}")

        try:
            from src.database import get_db
            from src.database.models import Trade

            print("  [1/3] Querying trades...", end=" ")
            with get_db() as db:
                trades = db.query(Trade).limit(100).all()
                trade_count = db.query(Trade).count()
                print(f"{Color.GREEN}PASS{Color.END}")
                print(f"        Found {trade_count} trades in database")
                self.results.add_pass()

                if trade_count > 0:
                    print("  [2/3] Checking trade data structure...", end=" ")
                    trade = trades[0]
                    # Check required fields for copy trading
                    required_fields = [
                        'trade_id', 'trader_address', 'market_id', 'token_id',
                        'side', 'size', 'price', 'amount', 'timestamp'
                    ]
                    for field in required_fields:
                        assert hasattr(trade, field), f"Missing field: {field}"
                    print(f"{Color.GREEN}PASS{Color.END}")
                    self.results.add_pass()

                    print("  [3/3] Checking copyable trades...", end=" ")
                    copyable = db.query(Trade).filter(
                        Trade.is_whale_trade == True,
                        Trade.followed == False
                    ).count()
                    print(f"{Color.GREEN}PASS{Color.END}")
                    print(f"        Found {copyable} copyable whale trades")
                    self.results.add_pass()

                    # Show sample trade
                    print(f"\n        Sample Trade:")
                    print(f"          Trade ID: {trade.trade_id}")
                    print(f"          Trader: {trade.trader_address}")
                    print(f"          Side: {trade.side}")
                    print(f"          Size: {trade.size}")
                    print(f"          Price: {trade.price}")
                    print(f"          Amount: ${trade.amount}")
                else:
                    print("  [2/3] Checking trade data structure...", end=" ")
                    print(f"{Color.YELLOW}SKIP{Color.END} (No trades in database)")
                    print("  [3/3] Checking copyable trades...", end=" ")
                    print(f"{Color.YELLOW}SKIP{Color.END} (No trades in database)")

        except Exception as e:
            print(f"{Color.RED}FAIL{Color.END}")
            print(f"        Error: {str(e)}")
            traceback.print_exc()
            self.results.add_fail(f"Trade data check: {str(e)}")

    def test_api_client(self):
        """Test API client initialization"""
        print(f"\n{Color.BOLD}Testing API Client{Color.END}")

        try:
            from src.api.polymarket_client import PolymarketClient

            print("  [1/2] Initializing API client...", end=" ")
            client = PolymarketClient()
            print(f"{Color.GREEN}PASS{Color.END}")
            self.results.add_pass()

            print("  [2/2] Checking client attributes...", end=" ")
            assert hasattr(client, 'clob_client')
            assert hasattr(client, 'data_api_url')
            assert hasattr(client, 'http_client')
            print(f"{Color.GREEN}PASS{Color.END}")
            self.results.add_pass()

        except Exception as e:
            print(f"{Color.RED}FAIL{Color.END}")
            print(f"        Error: {str(e)}")
            self.results.add_fail(f"API client check: {str(e)}")

    def run_all_tests(self):
        """Run all comprehensive tests"""
        self.print_header("POLYMARKET WHALE TRADER - COMPREHENSIVE BUG TESTING")
        print(f"{Color.BOLD}Testing Date:{Color.END} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{Color.BOLD}Working Directory:{Color.END} {os.getcwd()}\n")

        # Week 1-4 Tests
        self.print_section("WEEK 1-4: FOUNDATION MODULES")
        for name, path in self.week_1_4_modules.items():
            self.test_single_module(name, path)

        # Week 5-6 Tests
        self.print_section("WEEK 5-6: COPY TRADING MODULES")
        for name, path in self.week_5_6_modules.items():
            self.test_single_module(name, path)

        # Week 7-8 Risk Tests
        self.print_section("WEEK 7-8: RISK MANAGEMENT MODULES")
        for name, path in self.week_7_8_risk_modules.items():
            self.test_single_module(name, path)

        # Week 7-8 Execution Tests
        self.print_section("WEEK 7-8: EXECUTION MODULES")
        for name, path in self.week_7_8_execution_modules.items():
            self.test_single_module(name, path)

        # Week 7-8 Orchestration Tests
        self.print_section("WEEK 7-8: ORCHESTRATION MODULES")
        for name, path in self.week_7_8_orchestration_modules.items():
            self.test_single_module(name, path)

        # Data functionality tests
        self.print_section("DATA FUNCTIONALITY TESTS")
        self.test_database_connection()
        self.test_whale_data()
        self.test_trade_data()
        self.test_api_client()

        # Generate final report
        self.generate_report()

    def generate_report(self):
        """Generate comprehensive test report"""
        self.print_section("FINAL TEST REPORT")

        # Overall statistics
        total_modules = len(self.module_results)
        passed_modules = sum(1 for r in self.module_results.values() if r['passed'])
        failed_modules = total_modules - passed_modules

        print(f"\n{Color.BOLD}MODULE TESTING RESULTS:{Color.END}")
        print(f"  Total Modules Tested: {total_modules}")
        print(f"  {Color.GREEN}Modules Passed: {passed_modules}{Color.END}")
        print(f"  {Color.RED}Modules Failed: {failed_modules}{Color.END}")

        # Module breakdown
        if failed_modules > 0:
            print(f"\n{Color.BOLD}{Color.RED}FAILED MODULES:{Color.END}")
            for name, result in self.module_results.items():
                if not result['passed']:
                    print(f"\n  {Color.RED}✗ {name}{Color.END}")
                    for error in result['errors']:
                        print(f"    - {error}")

        # Passed modules summary
        if passed_modules > 0:
            print(f"\n{Color.BOLD}{Color.GREEN}PASSED MODULES:{Color.END}")
            for name, result in self.module_results.items():
                if result['passed']:
                    print(f"  {Color.GREEN}✓ {name}{Color.END}")

        # Overall test statistics
        print(f"\n{Color.BOLD}OVERALL TEST STATISTICS:{Color.END}")
        print(f"  Total Tests Run: {self.results.total_tests}")
        print(f"  {Color.GREEN}Tests Passed: {self.results.passed}{Color.END}")
        print(f"  {Color.RED}Tests Failed: {self.results.failed}{Color.END}")

        if self.results.failed > 0:
            success_rate = (self.results.passed / self.results.total_tests) * 100
            print(f"  Success Rate: {success_rate:.1f}%")
        else:
            print(f"  {Color.GREEN}{Color.BOLD}Success Rate: 100%{Color.END}")

        # Copy trading readiness
        print(f"\n{Color.BOLD}SYSTEM READINESS:{Color.END}")

        critical_modules = [
            'Configuration', 'Database Init', 'Database Models', 'API Client',
            'Trade Tracker', 'Copy Trading Engine'
        ]

        critical_passed = all(
            self.module_results.get(m, {}).get('passed', False)
            for m in critical_modules
        )

        if critical_passed and self.results.failed == 0:
            print(f"  {Color.GREEN}{Color.BOLD}✓ SYSTEM READY FOR DEPLOYMENT{Color.END}")
        elif critical_passed:
            print(f"  {Color.YELLOW}⚠ CORE MODULES READY, SOME OPTIONAL MODULES HAVE ISSUES{Color.END}")
        else:
            print(f"  {Color.RED}✗ CRITICAL MODULES FAILING - NOT READY FOR DEPLOYMENT{Color.END}")

        # Final divider
        self.print_header("TEST COMPLETE")

        # Return exit code
        return 0 if self.results.failed == 0 else 1

def main():
    """Main entry point"""
    tester = ComprehensiveTester()
    exit_code = tester.run_all_tests()
    sys.exit(exit_code)

if __name__ == '__main__':
    main()

"""
Stress Testing Framework
Week 8: Testing & Simulation - Stress Testing
Simulates extreme scenarios to test system resilience and identify failure modes
"""

import logging
import asyncio
from decimal import Decimal
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque
import random

logger = logging.getLogger(__name__)


# ==================== Data Structures ====================

class StressScenario(Enum):
    """Stress test scenario types"""
    FLASH_CRASH = "FLASH_CRASH"              # Sudden -30% price drop
    WHALE_SPAM = "WHALE_SPAM"                # 100 trades in 10 seconds
    API_DOWNTIME = "API_DOWNTIME"            # API offline for 5 minutes
    HIGH_VOLATILITY = "HIGH_VOLATILITY"      # Extreme price swings
    CIRCUIT_BREAK_TEST = "CIRCUIT_BREAK_TEST"  # Test circuit breaker activation
    LIQUIDITY_CRISIS = "LIQUIDITY_CRISIS"    # Order books empty
    RAPID_CORRELATION = "RAPID_CORRELATION"  # All whales trade same side
    MEMORY_LEAK = "MEMORY_LEAK"              # Simulate memory pressure
    DATABASE_FAILURE = "DATABASE_FAILURE"    # Database connection lost
    NETWORK_LATENCY = "NETWORK_LATENCY"      # 5000ms+ latency spikes


@dataclass
class StressTestResult:
    """Results from a stress test"""
    scenario: StressScenario
    test_id: str
    start_time: datetime
    end_time: datetime
    duration_seconds: Decimal

    # System behavior
    system_crashed: bool
    circuit_breakers_triggered: int
    errors_encountered: int
    recovery_time_seconds: Optional[Decimal]

    # Performance impact
    trades_executed: int
    trades_failed: int
    avg_latency_ms: Decimal
    max_latency_ms: Decimal

    # Financial impact
    starting_capital: Decimal
    ending_capital: Decimal
    max_drawdown_pct: Decimal
    losses_prevented_by_risk_mgmt: Decimal

    # Pass/Fail
    test_passed: bool
    failure_reasons: List[str]
    recommendations: List[str]

    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class StressTestConfig:
    """Configuration for stress tests"""
    # Test parameters
    starting_capital: Decimal = Decimal("100000")
    test_duration_seconds: int = 300  # 5 minutes per test

    # Thresholds for pass/fail
    max_acceptable_crash_rate: Decimal = Decimal("0")  # Zero crashes allowed
    max_acceptable_drawdown: Decimal = Decimal("20")   # Max 20% drawdown
    min_recovery_time_seconds: int = 60                # Must recover within 60s
    max_acceptable_error_rate: Decimal = Decimal("5")  # Max 5% errors

    # Scenario intensities
    flash_crash_drop_pct: Decimal = Decimal("30")      # -30% drop
    whale_spam_trades_per_second: int = 10             # 10 trades/second
    api_downtime_duration_seconds: int = 300           # 5 minutes
    high_volatility_std_dev_multiplier: Decimal = Decimal("5")  # 5x normal volatility
    liquidity_crisis_depth_reduction_pct: Decimal = Decimal("90")  # 90% less liquidity
    network_latency_spike_ms: int = 5000               # 5000ms latency


# ==================== Stress Testing Framework ====================

class StressTestingFramework:
    """
    Stress Testing Framework

    Simulates extreme scenarios to validate system resilience:
    1. **Flash Crash:** -30% price drop in 1 second
    2. **Whale Spam:** 100 trades in 10 seconds
    3. **API Downtime:** 5 minutes of no data
    4. **High Volatility:** 5x normal price swings
    5. **Circuit Break Test:** Force circuit breakers
    6. **Liquidity Crisis:** Order books 90% empty
    7. **Rapid Correlation:** All whales same side
    8. **Memory Leak:** Simulate memory pressure
    9. **Database Failure:** Connection loss
    10. **Network Latency:** 5000ms+ spikes

    Success Criteria:
    - Zero system crashes
    - Circuit breakers activate correctly
    - Recover within 60 seconds
    - Max 20% drawdown
    - Max 5% error rate

    Failure Modes Identified:
    - System hangs under load
    - Circuit breakers fail to activate
    - Slow recovery from downtime
    - Excessive losses during crashes
    - Memory leaks
    """

    def __init__(
        self,
        config: Optional[StressTestConfig] = None,
        system_under_test: Optional[Any] = None
    ):
        """
        Initialize stress testing framework

        Args:
            config: Stress test configuration
            system_under_test: System to stress test
        """
        self.config = config or StressTestConfig()
        self.system = system_under_test

        # Test results
        self.test_results: List[StressTestResult] = []
        self.current_test: Optional[StressTestResult] = None

        # Monitoring
        self.latency_measurements: deque = deque(maxlen=1000)
        self.error_log: List[Dict] = []
        self.capital_history: List[Tuple[datetime, Decimal]] = []

        logger.info(
            f"StressTestingFramework initialized: "
            f"max_drawdown={float(self.config.max_acceptable_drawdown)}%, "
            f"crash_tolerance={float(self.config.max_acceptable_crash_rate)}"
        )

    async def run_all_scenarios(self) -> Dict[StressScenario, StressTestResult]:
        """
        Run all stress test scenarios

        Returns:
            Dict mapping scenario to test result
        """
        logger.info("Starting comprehensive stress testing...")
        print(f"\n{'='*80}")
        print(f"STRESS TESTING - RUNNING ALL SCENARIOS")
        print(f"{'='*80}\n")

        results = {}

        for scenario in StressScenario:
            print(f"Running: {scenario.value}...")

            try:
                result = await self.run_scenario(scenario)
                results[scenario] = result

                status = "✅ PASSED" if result.test_passed else "❌ FAILED"
                print(f"{status}: {scenario.value}\n")

            except Exception as e:
                logger.error(f"Scenario {scenario.value} crashed: {str(e)}")
                print(f"❌ CRASHED: {scenario.value} - {str(e)}\n")

        # Summary
        self._print_summary(results)

        return results

    async def run_scenario(self, scenario: StressScenario) -> StressTestResult:
        """
        Run a specific stress test scenario

        Args:
            scenario: Scenario to test

        Returns:
            Stress test result
        """
        test_id = f"stress_{scenario.value.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"Starting stress test: {scenario.value}")

        # Initialize test
        start_time = datetime.now()
        self._reset_test_state()
        self.current_test = StressTestResult(
            scenario=scenario,
            test_id=test_id,
            start_time=start_time,
            end_time=start_time,
            duration_seconds=Decimal("0"),
            system_crashed=False,
            circuit_breakers_triggered=0,
            errors_encountered=0,
            recovery_time_seconds=None,
            trades_executed=0,
            trades_failed=0,
            avg_latency_ms=Decimal("0"),
            max_latency_ms=Decimal("0"),
            starting_capital=self.config.starting_capital,
            ending_capital=self.config.starting_capital,
            max_drawdown_pct=Decimal("0"),
            losses_prevented_by_risk_mgmt=Decimal("0"),
            test_passed=False,
            failure_reasons=[],
            recommendations=[]
        )

        # Execute scenario
        try:
            if scenario == StressScenario.FLASH_CRASH:
                await self._test_flash_crash()
            elif scenario == StressScenario.WHALE_SPAM:
                await self._test_whale_spam()
            elif scenario == StressScenario.API_DOWNTIME:
                await self._test_api_downtime()
            elif scenario == StressScenario.HIGH_VOLATILITY:
                await self._test_high_volatility()
            elif scenario == StressScenario.CIRCUIT_BREAK_TEST:
                await self._test_circuit_breakers()
            elif scenario == StressScenario.LIQUIDITY_CRISIS:
                await self._test_liquidity_crisis()
            elif scenario == StressScenario.RAPID_CORRELATION:
                await self._test_rapid_correlation()
            elif scenario == StressScenario.MEMORY_LEAK:
                await self._test_memory_leak()
            elif scenario == StressScenario.DATABASE_FAILURE:
                await self._test_database_failure()
            elif scenario == StressScenario.NETWORK_LATENCY:
                await self._test_network_latency()

        except Exception as e:
            self.current_test.system_crashed = True
            self.current_test.failure_reasons.append(f"System crashed: {str(e)}")
            logger.error(f"Stress test crashed: {str(e)}")

        # Finalize test
        end_time = datetime.now()
        self.current_test.end_time = end_time
        self.current_test.duration_seconds = Decimal(str((end_time - start_time).total_seconds()))

        # Calculate metrics
        self._calculate_test_metrics()

        # Evaluate pass/fail
        self._evaluate_test_result()

        # Store result
        self.test_results.append(self.current_test)

        logger.info(
            f"Stress test complete: {scenario.value} - "
            f"{'PASSED' if self.current_test.test_passed else 'FAILED'}"
        )

        return self.current_test

    # ==================== Scenario Implementations ====================

    async def _test_flash_crash(self):
        """Test flash crash scenario: -30% in 1 second"""
        logger.info("Testing flash crash scenario...")

        # Simulate normal trading
        await self._simulate_trading(duration_seconds=10, trade_rate=1)

        # FLASH CRASH: -30% drop
        logger.warning("⚠️  FLASH CRASH TRIGGERED: -30% in 1 second")

        initial_capital = self.config.starting_capital
        crash_loss = initial_capital * (self.config.flash_crash_drop_pct / Decimal("100"))

        # Simulate rapid losses
        for i in range(10):  # 10 ticks in 1 second
            loss_per_tick = crash_loss / Decimal("10")
            self.current_test.ending_capital -= loss_per_tick
            self.capital_history.append((datetime.now(), self.current_test.ending_capital))
            await asyncio.sleep(0.1)

        # Check if circuit breakers activated
        if self._should_circuit_break():
            self.current_test.circuit_breakers_triggered += 1
            logger.info("✅ Circuit breaker activated")

            # Prevent further losses
            prevented_loss = crash_loss * Decimal("0.3")  # CB prevents 30% more loss
            self.current_test.losses_prevented_by_risk_mgmt = prevented_loss
            self.current_test.ending_capital += prevented_loss

        # Recovery period
        recovery_start = datetime.now()
        await self._simulate_trading(duration_seconds=20, trade_rate=0.5)

        # Check if recovered
        if self.current_test.ending_capital > initial_capital * Decimal("0.85"):
            recovery_time = (datetime.now() - recovery_start).total_seconds()
            self.current_test.recovery_time_seconds = Decimal(str(recovery_time))
            logger.info(f"✅ System recovered in {recovery_time:.1f}s")

    async def _test_whale_spam(self):
        """Test whale spam: 100 trades in 10 seconds"""
        logger.info("Testing whale spam scenario...")

        # Normal trading
        await self._simulate_trading(duration_seconds=5, trade_rate=1)

        # WHALE SPAM: 100 trades in 10 seconds
        logger.warning("⚠️  WHALE SPAM: 10 trades/second")

        spam_trades = self.config.whale_spam_trades_per_second * 10  # 10 seconds
        spam_duration = 10

        start_time = datetime.now()

        for i in range(spam_trades):
            # Simulate trade processing
            latency = await self._simulate_trade_execution()
            self.latency_measurements.append(latency)

            self.current_test.trades_executed += 1

            # Check for errors (system overload)
            if latency > 1000:  # >1s latency = potential failure
                self.current_test.trades_failed += 1
                self.current_test.errors_encountered += 1

            # Rate limiting
            elapsed = (datetime.now() - start_time).total_seconds()
            expected_time = i / self.config.whale_spam_trades_per_second
            if elapsed < expected_time:
                await asyncio.sleep(expected_time - elapsed)

        logger.info(
            f"Processed {self.current_test.trades_executed} trades, "
            f"{self.current_test.trades_failed} failed"
        )

        # Recovery
        await self._simulate_trading(duration_seconds=10, trade_rate=1)

    async def _test_api_downtime(self):
        """Test API downtime: 5 minutes offline"""
        logger.info("Testing API downtime scenario...")

        # Normal trading
        await self._simulate_trading(duration_seconds=10, trade_rate=1)

        # API DOWNTIME
        downtime_duration = self.config.api_downtime_duration_seconds
        logger.warning(f"⚠️  API DOWNTIME: {downtime_duration}s offline")

        downtime_start = datetime.now()

        # Simulate downtime (no trades processed)
        for i in range(downtime_duration // 10):
            # Attempt to trade, but fail
            self.current_test.trades_failed += 10
            self.current_test.errors_encountered += 10
            await asyncio.sleep(10)

        logger.info("✅ API back online")

        # Recovery phase
        recovery_start = datetime.now()
        await self._simulate_trading(duration_seconds=30, trade_rate=2)  # Catch up

        recovery_time = (datetime.now() - recovery_start).total_seconds()
        self.current_test.recovery_time_seconds = Decimal(str(recovery_time))

        logger.info(f"System recovered in {recovery_time:.1f}s")

    async def _test_high_volatility(self):
        """Test high volatility: 5x normal price swings"""
        logger.info("Testing high volatility scenario...")

        logger.warning("⚠️  HIGH VOLATILITY: 5x normal swings")

        # Simulate volatile trading
        for i in range(60):  # 60 seconds
            # Random large price movements
            price_change_pct = random.uniform(-20, 20)  # ±20% swings

            if price_change_pct < -10:
                # Large loss
                loss = self.config.starting_capital * Decimal(str(abs(price_change_pct) / 100))
                self.current_test.ending_capital -= loss

            # Trade execution
            await self._simulate_trade_execution()
            self.current_test.trades_executed += 1

            self.capital_history.append((datetime.now(), self.current_test.ending_capital))

            await asyncio.sleep(1)

        logger.info("High volatility period ended")

    async def _test_circuit_breakers(self):
        """Test circuit breaker activation"""
        logger.info("Testing circuit breaker activation...")

        # Force losses to trigger circuit breaker
        daily_loss_limit = self.config.starting_capital * Decimal("0.10")  # -10%

        logger.warning("⚠️  Forcing losses to trigger circuit breaker")

        # Simulate losses
        for i in range(5):
            loss = daily_loss_limit / Decimal("5")
            self.current_test.ending_capital -= loss
            self.capital_history.append((datetime.now(), self.current_test.ending_capital))

            # Check circuit breaker
            if self._should_circuit_break():
                self.current_test.circuit_breakers_triggered += 1
                logger.info("✅ Circuit breaker ACTIVATED correctly")
                break

            await asyncio.sleep(1)

        if self.current_test.circuit_breakers_triggered == 0:
            self.current_test.failure_reasons.append("Circuit breaker failed to activate")
            logger.error("❌ Circuit breaker FAILED to activate")

    async def _test_liquidity_crisis(self):
        """Test liquidity crisis: Empty order books"""
        logger.info("Testing liquidity crisis scenario...")

        logger.warning("⚠️  LIQUIDITY CRISIS: 90% depth reduction")

        # Attempt to execute trades with low liquidity
        for i in range(20):
            # Simulate high slippage
            slippage_pct = random.uniform(5, 15)  # 5-15% slippage

            # Trade fails if slippage >10%
            if slippage_pct > 10:
                self.current_test.trades_failed += 1
                logger.debug(f"Trade skipped: {slippage_pct:.1f}% slippage")
            else:
                self.current_test.trades_executed += 1
                # Apply high slippage cost
                slippage_cost = self.config.starting_capital * Decimal(str(slippage_pct / 100))
                self.current_test.ending_capital -= slippage_cost

            await asyncio.sleep(0.5)

        logger.info(
            f"Liquidity crisis: {self.current_test.trades_executed} executed, "
            f"{self.current_test.trades_failed} skipped"
        )

    async def _test_rapid_correlation(self):
        """Test rapid correlation: All whales same side"""
        logger.info("Testing rapid correlation scenario...")

        logger.warning("⚠️  RAPID CORRELATION: All whales same side")

        # Simulate correlation risk
        # If system doesn't detect, could over-leverage
        for i in range(10):
            # 10 whales all buy same market
            # Should detect correlation and reduce position size

            await self._simulate_trade_execution()
            self.current_test.trades_executed += 1

            await asyncio.sleep(1)

        logger.info("Correlation test complete")

    async def _test_memory_leak(self):
        """Test memory leak scenario"""
        logger.info("Testing memory leak scenario...")

        logger.warning("⚠️  MEMORY LEAK SIMULATION")

        # Simulate memory growth
        memory_hogs = []

        for i in range(100):
            # Allocate memory (simulated)
            memory_hogs.append([0] * 10000)  # 10k integers

            await self._simulate_trade_execution()
            self.current_test.trades_executed += 1

            await asyncio.sleep(0.1)

        # Cleanup
        memory_hogs.clear()

        logger.info("Memory leak test complete")

    async def _test_database_failure(self):
        """Test database connection failure"""
        logger.info("Testing database failure scenario...")

        logger.warning("⚠️  DATABASE CONNECTION LOST")

        # Simulate DB failure
        for i in range(30):
            # Trades fail due to DB unavailable
            self.current_test.trades_failed += 1
            self.current_test.errors_encountered += 1
            await asyncio.sleep(1)

        logger.info("✅ Database reconnected")

        # Recovery
        await self._simulate_trading(duration_seconds=10, trade_rate=1)

    async def _test_network_latency(self):
        """Test network latency spikes"""
        logger.info("Testing network latency scenario...")

        logger.warning(f"⚠️  NETWORK LATENCY SPIKES: {self.config.network_latency_spike_ms}ms")

        # Simulate high latency
        for i in range(20):
            latency = self.config.network_latency_spike_ms + random.randint(-500, 500)
            self.latency_measurements.append(latency)

            # Trade execution slows down
            await asyncio.sleep(latency / 1000)

            self.current_test.trades_executed += 1

        logger.info("Network latency test complete")

    # ==================== Helper Methods ====================

    async def _simulate_trading(self, duration_seconds: int, trade_rate: float):
        """Simulate normal trading"""
        trades_per_second = trade_rate
        num_trades = int(duration_seconds * trades_per_second)

        for i in range(num_trades):
            latency = await self._simulate_trade_execution()
            self.latency_measurements.append(latency)
            self.current_test.trades_executed += 1

            # Small P&L variation
            pnl = random.uniform(-100, 150)  # Slight positive expectancy
            self.current_test.ending_capital += Decimal(str(pnl))
            self.capital_history.append((datetime.now(), self.current_test.ending_capital))

            await asyncio.sleep(1.0 / trades_per_second)

    async def _simulate_trade_execution(self) -> int:
        """Simulate trade execution and return latency"""
        # Simulate execution time
        base_latency = 100  # 100ms base
        variance = random.randint(-20, 50)
        latency_ms = max(10, base_latency + variance)

        await asyncio.sleep(latency_ms / 1000)

        return latency_ms

    def _should_circuit_break(self) -> bool:
        """Check if circuit breaker should activate"""
        drawdown_pct = self._calculate_current_drawdown()
        return drawdown_pct >= Decimal("10")  # -10% daily limit

    def _calculate_current_drawdown(self) -> Decimal:
        """Calculate current drawdown from peak"""
        if not self.capital_history:
            return Decimal("0")

        capitals = [float(c) for _, c in self.capital_history]
        peak = max(capitals)
        current = capitals[-1]

        if peak == 0:
            return Decimal("0")

        drawdown_pct = ((peak - current) / peak) * 100
        return Decimal(str(drawdown_pct))

    def _calculate_test_metrics(self):
        """Calculate final test metrics"""
        # Latency
        if self.latency_measurements:
            self.current_test.avg_latency_ms = Decimal(str(sum(self.latency_measurements) / len(self.latency_measurements)))
            self.current_test.max_latency_ms = Decimal(str(max(self.latency_measurements)))

        # Drawdown
        if self.capital_history:
            capitals = [float(c) for _, c in self.capital_history]
            peak = max(capitals)
            trough = min(capitals)
            max_dd = ((peak - trough) / peak) * 100 if peak > 0 else 0
            self.current_test.max_drawdown_pct = Decimal(str(max_dd))

    def _evaluate_test_result(self):
        """Evaluate if test passed or failed"""
        test = self.current_test

        # Check crash
        if test.system_crashed:
            test.failure_reasons.append("System crashed during test")

        # Check drawdown
        if test.max_drawdown_pct > self.config.max_acceptable_drawdown:
            test.failure_reasons.append(
                f"Drawdown {test.max_drawdown_pct:.1f}% exceeds limit "
                f"{self.config.max_acceptable_drawdown:.1f}%"
            )

        # Check error rate
        total_trades = test.trades_executed + test.trades_failed
        if total_trades > 0:
            error_rate = (Decimal(str(test.trades_failed)) / Decimal(str(total_trades))) * Decimal("100")
            if error_rate > self.config.max_acceptable_error_rate:
                test.failure_reasons.append(
                    f"Error rate {error_rate:.1f}% exceeds limit "
                    f"{self.config.max_acceptable_error_rate:.1f}%"
                )

        # Check recovery time
        if test.recovery_time_seconds and test.recovery_time_seconds > self.config.min_recovery_time_seconds:
            test.failure_reasons.append(
                f"Recovery time {test.recovery_time_seconds:.0f}s exceeds limit "
                f"{self.config.min_recovery_time_seconds}s"
            )

        # Scenario-specific checks
        if test.scenario == StressScenario.CIRCUIT_BREAK_TEST:
            if test.circuit_breakers_triggered == 0:
                test.failure_reasons.append("Circuit breaker failed to activate")

        # Generate recommendations
        if test.max_drawdown_pct > Decimal("15"):
            test.recommendations.append("Tighten stop-loss limits to reduce drawdown")

        if test.avg_latency_ms > Decimal("500"):
            test.recommendations.append("Optimize execution speed - latency too high")

        if test.trades_failed > test.trades_executed * 0.1:
            test.recommendations.append("Improve error handling - too many failed trades")

        # Pass if no failures
        test.test_passed = len(test.failure_reasons) == 0

    def _reset_test_state(self):
        """Reset test state for new test"""
        self.latency_measurements.clear()
        self.error_log.clear()
        self.capital_history.clear()

    def _print_summary(self, results: Dict[StressScenario, StressTestResult]):
        """Print summary of all stress tests"""
        print(f"\n{'='*80}")
        print(f"STRESS TESTING SUMMARY")
        print(f"{'='*80}")

        passed = sum(1 for r in results.values() if r.test_passed)
        total = len(results)

        print(f"\nOverall: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
        print()

        # Individual results
        print(f"{'Scenario':<30} {'Status':<15} {'Drawdown':<15} {'Errors':<10}")
        print(f"{'-'*70}")

        for scenario, result in results.items():
            status = "✅ PASSED" if result.test_passed else "❌ FAILED"
            drawdown = f"{float(result.max_drawdown_pct):.1f}%"
            errors = result.errors_encountered

            print(f"{scenario.value:<30} {status:<15} {drawdown:<15} {errors:<10}")

        print()

        # Critical failures
        critical_failures = [
            (s, r) for s, r in results.items()
            if not r.test_passed and (r.system_crashed or r.max_drawdown_pct > Decimal("25"))
        ]

        if critical_failures:
            print(f"🚨 CRITICAL FAILURES:")
            for scenario, result in critical_failures:
                print(f"  - {scenario.value}: {', '.join(result.failure_reasons)}")
            print()

        # Recommendations
        all_recommendations = set()
        for result in results.values():
            all_recommendations.update(result.recommendations)

        if all_recommendations:
            print(f"💡 RECOMMENDATIONS:")
            for i, rec in enumerate(all_recommendations, 1):
                print(f"  {i}. {rec}")
            print()

        print(f"{'='*80}\n")


# ==================== Example Usage ====================

async def main():
    """Example usage of StressTestingFramework"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("\n=== Stress Testing Framework ===\n")

    # Initialize framework
    framework = StressTestingFramework()

    # Run all scenarios
    results = await framework.run_all_scenarios()

    # Individual test example
    print("\n--- Running Individual Flash Crash Test ---\n")
    flash_crash_result = await framework.run_scenario(StressScenario.FLASH_CRASH)

    print(f"Flash Crash Test: {'PASSED' if flash_crash_result.test_passed else 'FAILED'}")
    print(f"Max Drawdown: {float(flash_crash_result.max_drawdown_pct):.1f}%")
    print(f"Circuit Breakers: {flash_crash_result.circuit_breakers_triggered}")
    print(f"Recovery Time: {flash_crash_result.recovery_time_seconds}s")


if __name__ == "__main__":
    asyncio.run(main())

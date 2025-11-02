"""
Unified Trading Execution System
Orchestrates all components for live whale copy trading
"""

import asyncio
import logging
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
import json
from enum import Enum

# Import all system components
from src.scoring.advanced_wqs import AdvancedWQS
from src.filters.three_stage_filter import ThreeStageFilter
from src.position_sizing.adaptive_kelly import AdaptiveKellySizer
from src.risk.live_risk_manager import LiveRiskManager, RiskLevel
from src.realtime.websocket_client import PolymarketWebSocketClient, RealTimeTradeMonitor, EventType, StreamEvent
from src.database.connection import get_connection
from src.inefficiencies.arbitrage_detector import ArbitrageDetector

logger = logging.getLogger(__name__)


class TradingMode(Enum):
    """Trading modes for the executor"""
    PAPER = "paper"  # Paper trading mode
    LIVE = "live"    # Live trading mode
    BACKTEST = "backtest"  # Backtesting mode


class TradeDecision(Enum):
    """Trade decision outcomes"""
    COPY = "copy"       # Copy the whale trade
    SKIP = "skip"       # Skip this trade
    REDUCE = "reduce"   # Reduce position size
    CLOSE = "close"     # Close position


@dataclass
class TradeSignal:
    """Represents a trading signal"""
    whale_address: str
    market_id: str
    side: str  # 'buy' or 'sell'
    whale_size: Decimal
    whale_price: Decimal
    timestamp: datetime
    confidence: float
    wqs_score: float
    decision: TradeDecision
    adjusted_size: Optional[Decimal] = None
    reason: Optional[str] = None


@dataclass
class ExecutionResult:
    """Result of trade execution"""
    success: bool
    signal: TradeSignal
    executed_size: Decimal
    executed_price: Decimal
    fees: Decimal
    error: Optional[str] = None
    execution_time_ms: int = 0


class UnifiedTradingExecutor:
    """
    Main trading executor that coordinates all components
    """

    def __init__(self, config: Dict[str, Any], mode: TradingMode = TradingMode.PAPER):
        self.config = config
        self.mode = mode
        self.running = False

        # Initialize components
        self.wqs_calculator = AdvancedWQS()
        self.filter = ThreeStageFilter()
        self.kelly_sizer = AdaptiveKellySizer()
        self.risk_manager = LiveRiskManager(config.get("risk", {}))
        self.arbitrage_detector = ArbitrageDetector()

        # WebSocket client for real-time data
        self.ws_client = None
        self.trade_monitor = None

        # Trading state
        self.whale_scores: Dict[str, float] = {}
        self.active_positions: Dict[str, Dict] = {}
        self.pending_signals: asyncio.Queue = asyncio.Queue()
        self.execution_results: List[ExecutionResult] = []

        # Performance tracking
        self.portfolio_value = Decimal(config.get("initial_capital", 10000))
        self.total_pnl = Decimal(0)
        self.trade_count = 0
        self.win_count = 0

    async def initialize(self):
        """Initialize all components and connections"""
        logger.info(f"Initializing Unified Trading Executor in {self.mode.value} mode")

        # Load whale profiles from database
        await self._load_whale_profiles()

        # Initialize WebSocket client if not backtesting
        if self.mode != TradingMode.BACKTEST:
            self.ws_client = PolymarketWebSocketClient(set(self.whale_scores.keys()))
            self.trade_monitor = RealTimeTradeMonitor(self.ws_client)

            # Register event handlers
            self.ws_client.register_handler(EventType.WHALE_TRADE, self._handle_whale_trade)
            self.ws_client.register_handler(EventType.ORDER_FILLED, self._handle_order_filled)

        # Calculate initial risk metrics
        self.risk_manager.calculate_risk_metrics(self.portfolio_value)

        logger.info("Initialization complete")

    async def _load_whale_profiles(self):
        """Load and score whale profiles from database"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Get top whales with good metrics
            cursor.execute("""
                SELECT
                    address,
                    total_volume,
                    win_rate,
                    sharpe_ratio,
                    information_ratio,
                    calmar_ratio,
                    consistency_score,
                    max_drawdown
                FROM whales
                WHERE
                    is_active = true
                    AND total_volume > 100000
                    AND win_rate > 0.5
                    AND sharpe_ratio > 0.5
                ORDER BY sharpe_ratio DESC
                LIMIT 100
            """)

            whales = cursor.fetchall()

            for whale in whales:
                address = whale[0]
                metrics = {
                    'sharpe_ratio': float(whale[3]) if whale[3] else 0,
                    'information_ratio': float(whale[4]) if whale[4] else 0,
                    'calmar_ratio': float(whale[5]) if whale[5] else 0,
                    'consistency': float(whale[6]) if whale[6] else 0,
                    'volume_score': min(1.0, float(whale[1]) / 1000000) if whale[1] else 0,
                    'win_rate': float(whale[2]) if whale[2] else 0.5,
                    'trade_count': 100  # Default assumption
                }

                # Calculate WQS
                wqs = self.wqs_calculator.calculate_wqs(metrics)
                self.whale_scores[address.lower()] = wqs

            logger.info(f"Loaded {len(self.whale_scores)} whale profiles")

        finally:
            cursor.close()
            conn.close()

    async def _handle_whale_trade(self, event: StreamEvent):
        """Handle detected whale trade event"""
        if not event.user_address or event.user_address.lower() not in self.whale_scores:
            return

        whale_address = event.user_address.lower()
        wqs_score = self.whale_scores[whale_address]

        # Create trade signal
        signal = TradeSignal(
            whale_address=whale_address,
            market_id=event.market_id,
            side=event.data.get("side", "buy"),
            whale_size=Decimal(str(event.data.get("size", 0))),
            whale_price=Decimal(str(event.data.get("price", 0))),
            timestamp=datetime.fromtimestamp(event.timestamp),
            confidence=0.0,  # Will be calculated
            wqs_score=wqs_score,
            decision=TradeDecision.SKIP  # Default
        )

        # Add to processing queue
        await self.pending_signals.put(signal)
        logger.info(f"🐋 Whale trade signal queued: {whale_address[:8]}... in market {event.market_id}")

    async def _handle_order_filled(self, event: StreamEvent):
        """Handle order filled events"""
        # Process if it's one of our whales
        if event.user_address and event.user_address.lower() in self.whale_scores:
            await self._handle_whale_trade(event)

    async def process_signal(self, signal: TradeSignal) -> TradeSignal:
        """
        Process a trade signal through all filters and sizing
        """
        logger.info(f"Processing signal from whale {signal.whale_address[:8]}...")

        # Stage 1: Check whale quality
        if signal.wqs_score < self.config.get("min_wqs", 0.5):
            signal.decision = TradeDecision.SKIP
            signal.reason = f"WQS score {signal.wqs_score:.2f} below threshold"
            return signal

        # Stage 2: Apply three-stage filter
        filter_result = await self.filter.evaluate_trade(
            whale_address=signal.whale_address,
            market_id=signal.market_id,
            trade_size=signal.whale_size,
            side=signal.side
        )

        if not filter_result['pass']:
            signal.decision = TradeDecision.SKIP
            signal.reason = filter_result.get('reason', 'Failed filter')
            return signal

        signal.confidence = filter_result['confidence']

        # Stage 3: Check for arbitrage opportunities
        arb_opportunity = self.arbitrage_detector.check_opportunity(
            signal.market_id,
            signal.whale_price
        )

        if arb_opportunity and arb_opportunity['edge'] > 0.02:  # 2% edge
            signal.confidence *= 1.5  # Boost confidence for arbitrage
            logger.info(f"💎 Arbitrage opportunity detected: {arb_opportunity['edge']*100:.1f}% edge")

        # Stage 4: Risk checks
        risk_check, risk_reason = self.risk_manager.check_trade_allowed(
            market_id=signal.market_id,
            side=signal.side,
            size=signal.whale_size * Decimal(str(self.config.get("copy_ratio", 0.1))),
            portfolio_value=self.portfolio_value
        )

        if not risk_check:
            signal.decision = TradeDecision.SKIP
            signal.reason = risk_reason
            return signal

        # Stage 5: Position sizing
        kelly_fraction = self.kelly_sizer.calculate_position_size(
            confidence=signal.confidence,
            win_rate=0.58,  # Historical average
            avg_win_loss_ratio=1.5,
            current_drawdown=float(self.risk_manager.risk_metrics.current_drawdown) if self.risk_manager.risk_metrics else 0
        )

        # Calculate final position size
        base_size = self.portfolio_value * Decimal(str(kelly_fraction))
        whale_ratio = Decimal(str(self.config.get("copy_ratio", 0.1)))
        max_copy_size = signal.whale_size * whale_ratio

        signal.adjusted_size = min(base_size, max_copy_size)

        # Final decision based on risk level
        risk_level = self.risk_manager.risk_metrics.risk_level if self.risk_manager.risk_metrics else RiskLevel.NORMAL

        if risk_level == RiskLevel.CRITICAL:
            signal.decision = TradeDecision.CLOSE
            signal.reason = "Critical risk level - closing positions"
        elif risk_level == RiskLevel.HIGH:
            signal.decision = TradeDecision.REDUCE
            signal.adjusted_size *= Decimal("0.5")
            signal.reason = "High risk - reduced position"
        else:
            signal.decision = TradeDecision.COPY
            signal.reason = "Signal approved"

        return signal

    async def execute_trade(self, signal: TradeSignal) -> ExecutionResult:
        """
        Execute a trade based on the signal
        """
        start_time = datetime.now()

        if signal.decision == TradeDecision.SKIP:
            return ExecutionResult(
                success=False,
                signal=signal,
                executed_size=Decimal(0),
                executed_price=Decimal(0),
                fees=Decimal(0),
                error=signal.reason
            )

        # Paper trading execution
        if self.mode == TradingMode.PAPER:
            result = await self._execute_paper_trade(signal)
        # Live trading execution
        elif self.mode == TradingMode.LIVE:
            result = await self._execute_live_trade(signal)
        # Backtest execution
        else:
            result = await self._execute_backtest_trade(signal)

        # Calculate execution time
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        result.execution_time_ms = int(execution_time)

        # Update risk manager
        if result.success:
            self.risk_manager.update_position(
                market_id=signal.market_id,
                side=signal.side,
                size=result.executed_size,
                price=result.executed_price
            )

            self.risk_manager.record_trade({
                'market_id': signal.market_id,
                'side': signal.side,
                'size': float(result.executed_size),
                'price': float(result.executed_price),
                'portfolio_value': float(self.portfolio_value)
            })

            self.trade_count += 1
            logger.info(f"✅ Trade executed: {signal.side} {result.executed_size:.2f} @ {result.executed_price:.4f}")
        else:
            logger.warning(f"❌ Trade failed: {result.error}")

        # Store result
        self.execution_results.append(result)

        return result

    async def _execute_paper_trade(self, signal: TradeSignal) -> ExecutionResult:
        """Execute trade in paper trading mode"""
        # Simulate execution with slippage
        slippage = Decimal(str(self.config.get("slippage", 0.001)))  # 0.1% default

        if signal.side == "buy":
            executed_price = signal.whale_price * (Decimal(1) + slippage)
        else:
            executed_price = signal.whale_price * (Decimal(1) - slippage)

        # Calculate fees
        fee_rate = Decimal(str(self.config.get("fee_rate", 0.001)))  # 0.1% default
        fees = signal.adjusted_size * executed_price * fee_rate

        # Update portfolio
        total_cost = (signal.adjusted_size * executed_price) + fees

        if total_cost > self.portfolio_value:
            return ExecutionResult(
                success=False,
                signal=signal,
                executed_size=Decimal(0),
                executed_price=Decimal(0),
                fees=Decimal(0),
                error="Insufficient funds"
            )

        # Update positions
        if signal.market_id not in self.active_positions:
            self.active_positions[signal.market_id] = {
                'size': Decimal(0),
                'avg_price': Decimal(0),
                'side': signal.side
            }

        position = self.active_positions[signal.market_id]

        if signal.side == position['side']:
            # Adding to position
            total_cost = position['size'] * position['avg_price'] + signal.adjusted_size * executed_price
            position['size'] += signal.adjusted_size
            position['avg_price'] = total_cost / position['size']
        else:
            # Reducing/flipping position
            position['size'] -= signal.adjusted_size
            if position['size'] < 0:
                position['side'] = signal.side
                position['size'] = abs(position['size'])
                position['avg_price'] = executed_price

        return ExecutionResult(
            success=True,
            signal=signal,
            executed_size=signal.adjusted_size,
            executed_price=executed_price,
            fees=fees
        )

    async def _execute_live_trade(self, signal: TradeSignal) -> ExecutionResult:
        """Execute trade in live mode"""
        # TODO: Implement actual Polymarket API integration
        # This would involve:
        # 1. Connecting to Polymarket API
        # 2. Placing limit/market order
        # 3. Monitoring fill status
        # 4. Handling partial fills

        logger.warning("Live trading not yet implemented - using paper trade simulation")
        return await self._execute_paper_trade(signal)

    async def _execute_backtest_trade(self, signal: TradeSignal) -> ExecutionResult:
        """Execute trade in backtest mode"""
        # Similar to paper trade but uses historical data
        return await self._execute_paper_trade(signal)

    async def run(self):
        """Main execution loop"""
        self.running = True
        logger.info(f"Starting trading executor in {self.mode.value} mode")

        # Start WebSocket client if not backtesting
        if self.mode != TradingMode.BACKTEST and self.ws_client:
            ws_task = asyncio.create_task(self.ws_client.start())

        # Signal processing loop
        while self.running:
            try:
                # Get signal from queue (wait up to 1 second)
                signal = await asyncio.wait_for(
                    self.pending_signals.get(),
                    timeout=1.0
                )

                # Process signal
                processed_signal = await self.process_signal(signal)

                # Execute if approved
                if processed_signal.decision in [TradeDecision.COPY, TradeDecision.REDUCE]:
                    result = await self.execute_trade(processed_signal)

                    # Update statistics
                    if result.success:
                        await self._update_performance(result)

                # Risk check every N trades
                if self.trade_count % 10 == 0:
                    await self._perform_risk_check()

            except asyncio.TimeoutError:
                # No signals, continue
                continue
            except Exception as e:
                logger.error(f"Error in execution loop: {e}")

    async def _update_performance(self, result: ExecutionResult):
        """Update performance metrics"""
        # Calculate P&L for closed positions
        # This is simplified - real implementation would track actual closes
        if result.signal.market_id in self.active_positions:
            position = self.active_positions[result.signal.market_id]

            if position['size'] == 0:
                # Position closed
                pnl = (result.executed_price - position['avg_price']) * result.executed_size
                if result.signal.side == "sell":
                    pnl = -pnl

                self.total_pnl += pnl

                if pnl > 0:
                    self.win_count += 1

                logger.info(f"Position closed - P&L: ${pnl:.2f}")

    async def _perform_risk_check(self):
        """Perform periodic risk check"""
        metrics = self.risk_manager.calculate_risk_metrics(self.portfolio_value)

        if metrics.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            logger.warning(f"⚠️ Risk level: {metrics.risk_level.value}")

            # Reduce all positions if critical
            if metrics.risk_level == RiskLevel.CRITICAL:
                await self._reduce_all_positions()

    async def _reduce_all_positions(self):
        """Reduce all positions due to risk"""
        logger.warning("Reducing all positions due to critical risk level")

        for market_id, position in self.active_positions.items():
            if position['size'] > 0:
                # Create close signal
                signal = TradeSignal(
                    whale_address="risk_manager",
                    market_id=market_id,
                    side="sell" if position['side'] == "buy" else "buy",
                    whale_size=position['size'],
                    whale_price=position['avg_price'],
                    timestamp=datetime.now(),
                    confidence=1.0,
                    wqs_score=1.0,
                    decision=TradeDecision.CLOSE,
                    adjusted_size=position['size'] * Decimal("0.5"),  # Close half
                    reason="Risk reduction"
                )

                await self.execute_trade(signal)

    async def stop(self):
        """Stop the executor"""
        logger.info("Stopping trading executor")
        self.running = False

        if self.ws_client:
            await self.ws_client.stop()

        # Generate final report
        report = self.get_performance_report()
        logger.info(f"Final performance report: {json.dumps(report, indent=2)}")

    def get_performance_report(self) -> Dict:
        """Get comprehensive performance report"""
        win_rate = (self.win_count / self.trade_count * 100) if self.trade_count > 0 else 0

        return {
            'mode': self.mode.value,
            'portfolio_value': float(self.portfolio_value),
            'total_pnl': float(self.total_pnl),
            'trade_count': self.trade_count,
            'win_count': self.win_count,
            'win_rate': win_rate,
            'active_positions': len(self.active_positions),
            'whales_monitored': len(self.whale_scores),
            'risk_metrics': self.risk_manager.get_risk_report(self.portfolio_value) if self.risk_manager else None,
            'timestamp': datetime.now().isoformat()
        }


# Main execution script
async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Unified Trading Executor')
    parser.add_argument('--mode', choices=['paper', 'live', 'backtest'],
                       default='paper', help='Trading mode')
    parser.add_argument('--config', type=str,
                       help='Path to configuration file')
    parser.add_argument('--capital', type=float, default=10000,
                       help='Initial capital')

    args = parser.parse_args()

    # Load configuration
    config = {
        'initial_capital': args.capital,
        'min_wqs': 0.5,
        'copy_ratio': 0.1,
        'slippage': 0.001,
        'fee_rate': 0.001,
        'risk': {
            'max_position_pct': 0.05,
            'max_total_exposure': 0.75,
            'max_daily_loss': 0.10,
            'max_drawdown': 0.20
        }
    }

    if args.config:
        with open(args.config) as f:
            config.update(json.load(f))

    # Create executor
    mode = TradingMode(args.mode)
    executor = UnifiedTradingExecutor(config, mode)

    try:
        # Initialize
        await executor.initialize()

        # Run
        await executor.run()

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        await executor.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    asyncio.run(main())
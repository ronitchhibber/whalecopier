#!/usr/bin/env python3
"""
Comprehensive Backtest Runner for Polymarket Whale Copy Trading
Integrates all components to run complete strategy validation
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

import asyncio
import logging
from datetime import datetime, timedelta
import json
import pandas as pd
import numpy as np
from typing import Dict, List, Any

# Import backtesting components
from backtesting.core.engine import BacktestingEngine, Event, EventType
from backtesting.market.simulator import MarketSimulator
from backtesting.execution.simulator import PolymarketExecutionSimulator
from backtesting.data.historical_manager import HistoricalDataManager
from backtesting.replay.market_replay import MarketReplaySystem, ReplaySpeed
from backtesting.strategies.adapter import WhaleCopyStrategy, ArbitrageStrategy, CompositeStrategy
from backtesting.orchestration.multi_strategy import MultiStrategyOrchestrator, AllocationMethod
from backtesting.analytics.performance import PerformanceAnalyzer
from backtesting.risk.risk_simulator import RiskSimulator

# Import strategies from main system
from copy_trading.advanced_engine import AdvancedCopyTradingEngine
from scoring.advanced_wqs import AdvancedWQS
from inefficiency_detection.structural_arbitrage import StructuralArbitrageDetector
from inefficiency_detection.behavioral_patterns import BehavioralPatternDetector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ComprehensiveBacktest:
    """
    Complete backtesting system integrating all components.
    """

    def __init__(self, config_path: str = None):
        """Initialize comprehensive backtest."""
        self.config = self._load_config(config_path)

        # Initialize components
        self.engine = BacktestingEngine(self.config['engine'])
        self.market_sim = MarketSimulator(self.config['market'])
        self.execution_sim = PolymarketExecutionSimulator(self.config['execution'])
        self.data_manager = HistoricalDataManager(self.config['data'])
        self.replay_system = MarketReplaySystem(self.config['replay'])
        self.orchestrator = MultiStrategyOrchestrator(self.config['orchestrator'])
        self.performance = PerformanceAnalyzer(self.config['performance'])
        self.risk_sim = RiskSimulator(self.config['risk'])

        # Initialize strategies
        self.strategies = {}
        self._initialize_strategies()

        # Results storage
        self.results = {}
        self.trades_executed = []
        self.equity_curve = []

    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from file or use defaults."""
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)

        # Default configuration
        return {
            'engine': {
                'initial_capital': 100000,
                'max_events': 1000000,
                'enable_logging': True
            },
            'market': {
                'tick_size': 0.001,
                'base_spreads': {
                    'high_volume': 0.001,
                    'medium_volume': 0.002,
                    'low_volume': 0.005
                }
            },
            'execution': {
                'latency': {
                    'network_mean': 20,
                    'processing_mean': 5,
                    'exchange_mean': 10
                },
                'slippage': {
                    'base_impact_bps': 5,
                    'size_factor': 0.5
                }
            },
            'data': {
                'database': {
                    'host': 'localhost',
                    'port': 5432,
                    'dbname': 'polymarket_backtest',
                    'user': 'trader',
                    'password': 'trader_password'
                }
            },
            'replay': {
                'buffer_size': 10000,
                'interpolation': {'enabled': True}
            },
            'orchestrator': {
                'allocation': {
                    'method': AllocationMethod.RISK_PARITY,
                    'rebalance_frequency': 'daily'
                }
            },
            'performance': {
                'risk_free_rate': 0.02,
                'confidence_level': 0.95
            },
            'risk': {
                'lookback_days': 252,
                'confidence_levels': [0.95, 0.99],
                'ewma_lambda': 0.94
            },
            'backtest': {
                'start_date': '2024-01-01',
                'end_date': '2024-12-31',
                'markets': ['election_2024', 'crypto_btc_100k', 'sports_superbowl']
            }
        }

    def _initialize_strategies(self):
        """Initialize trading strategies."""
        # Whale Copy Strategy
        whale_config = {
            'min_wqs': 75,
            'min_trade_size': 5000,
            'copy_ratio': 0.1
        }
        self.strategies['whale_copy'] = WhaleCopyStrategy(whale_config)

        # Arbitrage Strategy
        arb_config = {
            'min_edge_bps': 100,
            'max_position': 50000
        }
        self.strategies['arbitrage'] = ArbitrageStrategy(arb_config)

        # Register with orchestrator
        self.orchestrator.add_strategy('whale_copy', self.strategies['whale_copy'], 0.6)
        self.orchestrator.add_strategy('arbitrage', self.strategies['arbitrage'], 0.4)

    async def run(
        self,
        start_date: str = None,
        end_date: str = None,
        markets: List[str] = None
    ) -> Dict:
        """
        Run comprehensive backtest.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            markets: List of markets to test

        Returns:
            Complete backtest results
        """
        # Parse dates
        start = datetime.fromisoformat(start_date or self.config['backtest']['start_date'])
        end = datetime.fromisoformat(end_date or self.config['backtest']['end_date'])
        markets = markets or self.config['backtest']['markets']

        logger.info(f"Starting backtest from {start} to {end}")
        logger.info(f"Markets: {markets}")
        logger.info(f"Initial capital: ${self.config['engine']['initial_capital']:,.2f}")

        # Initialize systems
        await self._initialize_systems(start, end, markets)

        # Run main backtest loop
        results = await self._run_backtest_loop(start, end)

        # Calculate final metrics
        final_results = self._calculate_final_results(results)

        # Generate report
        self._generate_report(final_results)

        return final_results

    async def _initialize_systems(
        self,
        start: datetime,
        end: datetime,
        markets: List[str]
    ):
        """Initialize all systems for backtesting."""
        # Initialize data manager
        logger.info("Loading historical data...")
        # In production, would load actual data
        # self.data_manager.initialize(start, end)

        # Initialize market simulator
        for market_id in markets:
            self.market_sim.initialize_market(market_id, {
                'last_price': 0.5,
                'base_spread': 0.002
            })

        # Initialize replay system
        await self.replay_system.initialize(start, end, markets)

        # Initialize orchestrator
        self.orchestrator.initialize(
            self.config['engine']['initial_capital'],
            start
        )

        # Initialize risk simulator
        self.risk_sim.update_positions({}, {}, start)

        # Register event handlers
        self._register_event_handlers()

    def _register_event_handlers(self):
        """Register event handlers for the engine."""
        # Market data handler
        def handle_market_tick(event: Event, context: Dict) -> List[Event]:
            market_data = event.data['market_data']

            # Update market simulator
            self.market_sim.update_market_state(
                event.timestamp,
                [market_data]
            )

            # Generate strategy signals
            signals = []
            for name, strategy in self.strategies.items():
                strategy_signals = strategy.on_market_data(
                    event.timestamp,
                    market_data
                )
                signals.extend(strategy_signals)

            # Process through orchestrator
            position_requests = asyncio.run(
                self.orchestrator.process_signals(event.timestamp, signals)
            )

            # Create order events
            new_events = []
            for request in position_requests:
                new_events.append(Event(
                    timestamp=event.timestamp + timedelta(milliseconds=10),
                    event_type=EventType.ORDER_PLACED,
                    data={'request': request}
                ))

            return new_events

        self.engine.register_handler(EventType.MARKET_TICK, handle_market_tick)

        # Order execution handler
        def handle_order(event: Event, context: Dict) -> List[Event]:
            request = event.data['request']

            # Check risk limits
            accepted, reason = self.risk_sim.should_accept_trade(
                request.market_id,
                request.side,
                request.requested_size,
                0.5  # Simplified price
            )

            if not accepted:
                logger.warning(f"Trade rejected: {reason}")
                return []

            # Simulate execution
            order_data = {
                'market_id': request.market_id,
                'side': request.side,
                'size': request.requested_size,
                'type': 'market',
                'trader_id': request.strategy_name
            }

            market_state = self.market_sim.get_market_snapshot(request.market_id)
            execution_result = self.execution_sim.execute_polymarket_order(
                order_data,
                market_state,
                context.get('portfolio', {})
            )

            # Record trade
            if execution_result.status.value == 'filled':
                self.trades_executed.append({
                    'timestamp': event.timestamp,
                    'strategy': request.strategy_name,
                    'market': request.market_id,
                    'side': request.side,
                    'size': execution_result.total_filled,
                    'price': execution_result.average_price,
                    'slippage_bps': execution_result.slippage_bps,
                    'fees': execution_result.fees
                })

                # Update positions
                context['positions'] = context.get('positions', {})
                if request.side == 'buy':
                    context['positions'][request.market_id] = \
                        context['positions'].get(request.market_id, 0) + execution_result.total_filled
                else:
                    context['positions'][request.market_id] = \
                        context['positions'].get(request.market_id, 0) - execution_result.total_filled

                # Notify strategies
                for strategy in self.strategies.values():
                    strategy.on_trade_executed(event.timestamp, {
                        'execution': execution_result,
                        'request': request
                    })

            return []

        self.engine.register_handler(EventType.ORDER_PLACED, handle_order)

    async def _run_backtest_loop(
        self,
        start: datetime,
        end: datetime
    ) -> Dict:
        """Run the main backtest event loop."""
        # Initialize strategies
        for strategy in self.strategies.values():
            strategy.initialize(
                self.config['engine']['initial_capital'] / len(self.strategies),
                start
            )

        # Run engine
        results = self.engine.run(start, end)

        # Track equity curve
        current_time = start
        equity = self.config['engine']['initial_capital']

        while current_time <= end:
            # Calculate current equity
            positions_value = sum(
                self.engine.context.get('positions', {}).values()
            )
            cash = self.engine.context.get('capital', self.config['engine']['initial_capital'])
            equity = cash + positions_value

            # Update performance tracker
            self.performance.add_data_point(
                current_time,
                equity,
                self.engine.context.get('positions', {}),
                []  # Trades handled separately
            )

            # Update risk tracker
            self.risk_sim.update_positions(
                self.engine.context.get('positions', {}),
                {'default': 0.5},  # Simplified prices
                current_time
            )

            # Store equity curve point
            self.equity_curve.append({
                'timestamp': current_time,
                'equity': equity,
                'cash': cash,
                'positions_value': positions_value
            })

            # Move to next day
            current_time += timedelta(days=1)

            # Check for rebalancing
            if self.orchestrator.should_rebalance():
                await self.orchestrator.rebalance()

        return results

    def _calculate_final_results(self, engine_results: Dict) -> Dict:
        """Calculate comprehensive final results."""
        # Get performance metrics
        perf_metrics = self.performance.calculate_metrics()

        # Get risk metrics
        risk_dashboard = self.risk_sim.get_risk_dashboard()

        # Get execution statistics
        exec_stats = self.execution_sim.get_execution_statistics()

        # Get strategy attribution
        attribution = self.orchestrator.get_attribution()

        # Calculate key metrics vs targets
        results = {
            'summary': {
                'initial_capital': self.config['engine']['initial_capital'],
                'final_equity': self.equity_curve[-1]['equity'] if self.equity_curve else 0,
                'total_return': perf_metrics.total_return,
                'annualized_return': perf_metrics.annualized_return,
                'sharpe_ratio': perf_metrics.sharpe_ratio,
                'max_drawdown': perf_metrics.max_drawdown,
                'win_rate': perf_metrics.win_rate,
                'total_trades': len(self.trades_executed)
            },
            'vs_targets': {
                'sharpe_ratio': {
                    'actual': perf_metrics.sharpe_ratio,
                    'target': 2.07,
                    'achieved': perf_metrics.sharpe_ratio >= 2.07
                },
                'annual_return': {
                    'actual': perf_metrics.annualized_return,
                    'target': 0.31,
                    'achieved': perf_metrics.annualized_return >= 0.31
                },
                'max_drawdown': {
                    'actual': perf_metrics.max_drawdown,
                    'target': 0.112,
                    'achieved': perf_metrics.max_drawdown <= 0.112
                },
                'win_rate': {
                    'actual': perf_metrics.win_rate,
                    'target': 0.582,
                    'achieved': perf_metrics.win_rate >= 0.582
                }
            },
            'performance': {
                'returns': {
                    'total': perf_metrics.total_return,
                    'annualized': perf_metrics.annualized_return,
                    'cumulative': perf_metrics.cumulative_return
                },
                'risk': {
                    'volatility': perf_metrics.volatility,
                    'downside_vol': perf_metrics.downside_volatility,
                    'max_drawdown': perf_metrics.max_drawdown,
                    'var_95': perf_metrics.value_at_risk_95,
                    'cvar_95': perf_metrics.conditional_var_95
                },
                'risk_adjusted': {
                    'sharpe': perf_metrics.sharpe_ratio,
                    'sortino': perf_metrics.sortino_ratio,
                    'calmar': perf_metrics.calmar_ratio,
                    'information': perf_metrics.information_ratio
                }
            },
            'execution': exec_stats,
            'risk': risk_dashboard,
            'attribution': attribution,
            'trades': {
                'total': len(self.trades_executed),
                'by_strategy': self._group_trades_by_strategy(),
                'avg_slippage_bps': np.mean([t['slippage_bps'] for t in self.trades_executed]) if self.trades_executed else 0,
                'total_fees': sum(t['fees'] for t in self.trades_executed)
            },
            'equity_curve': self.equity_curve
        }

        return results

    def _group_trades_by_strategy(self) -> Dict:
        """Group trades by strategy for analysis."""
        grouped = {}
        for trade in self.trades_executed:
            strategy = trade['strategy']
            if strategy not in grouped:
                grouped[strategy] = []
            grouped[strategy].append(trade)

        # Calculate stats per strategy
        stats = {}
        for strategy, trades in grouped.items():
            # Calculate P&L for each trade
            pnls = []
            for i, trade in enumerate(trades):
                # Simplified P&L calculation
                if trade['side'] == 'buy':
                    # Look for corresponding sell
                    for j in range(i+1, len(trades)):
                        if trades[j]['market'] == trade['market'] and trades[j]['side'] == 'sell':
                            pnl = (trades[j]['price'] - trade['price']) * trade['size']
                            pnls.append(pnl)
                            break

            stats[strategy] = {
                'total_trades': len(trades),
                'total_pnl': sum(pnls) if pnls else 0,
                'win_rate': len([p for p in pnls if p > 0]) / len(pnls) if pnls else 0,
                'avg_trade': np.mean(pnls) if pnls else 0
            }

        return stats

    def _generate_report(self, results: Dict):
        """Generate comprehensive backtest report."""
        print("\n" + "="*80)
        print(" "*25 + "BACKTEST RESULTS SUMMARY")
        print("="*80)

        # Summary metrics
        summary = results['summary']
        print(f"\nInitial Capital: ${summary['initial_capital']:,.2f}")
        print(f"Final Equity: ${summary['final_equity']:,.2f}")
        print(f"Total Return: {summary['total_return']:.2%}")
        print(f"Annualized Return: {summary['annualized_return']:.2%}")
        print(f"Sharpe Ratio: {summary['sharpe_ratio']:.2f}")
        print(f"Max Drawdown: {summary['max_drawdown']:.2%}")
        print(f"Win Rate: {summary['win_rate']:.2%}")
        print(f"Total Trades: {summary['total_trades']}")

        # Target comparison
        print("\n" + "-"*40)
        print("PERFORMANCE vs TARGETS:")
        print("-"*40)
        for metric, data in results['vs_targets'].items():
            status = "✅" if data['achieved'] else "❌"
            print(f"{metric.replace('_', ' ').title():20} {status} "
                  f"Actual: {data['actual']:.2f} | Target: {data['target']:.2f}")

        # Strategy attribution
        print("\n" + "-"*40)
        print("STRATEGY ATTRIBUTION:")
        print("-"*40)
        if results.get('attribution'):
            for strategy, metrics in results['attribution'].items():
                print(f"\n{strategy}:")
                print(f"  P&L: ${metrics.get('pnl', 0):,.2f}")
                print(f"  Return: {metrics.get('return', 0):.2%}")
                print(f"  Weight: {metrics.get('weight', 0):.2%}")

        # Trade statistics
        print("\n" + "-"*40)
        print("TRADE STATISTICS:")
        print("-"*40)
        trades = results['trades']
        print(f"Total Trades: {trades['total']}")
        print(f"Average Slippage: {trades['avg_slippage_bps']:.1f} bps")
        print(f"Total Fees: ${trades['total_fees']:,.2f}")

        if trades['by_strategy']:
            for strategy, stats in trades['by_strategy'].items():
                print(f"\n{strategy}:")
                print(f"  Trades: {stats['total_trades']}")
                print(f"  P&L: ${stats['total_pnl']:,.2f}")
                print(f"  Win Rate: {stats['win_rate']:.2%}")

        print("\n" + "="*80)

        # Export detailed results
        output_file = f"backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            # Convert numpy types for JSON serialization
            def convert(obj):
                if isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, datetime):
                    return obj.isoformat()
                return obj

            json.dump(results, f, indent=2, default=convert)

        print(f"\nDetailed results saved to: {output_file}")


async def main():
    """Main entry point for comprehensive backtest."""
    print("\n" + "="*80)
    print(" "*20 + "🚀 COMPREHENSIVE BACKTESTING SYSTEM 🚀")
    print("="*80)
    print("\nImplementing research-based strategies:")
    print("  • Whale Copy Trading (5-Factor WQS)")
    print("  • Structural Arbitrage Detection")
    print("  • Behavioral Pattern Recognition")
    print("  • Cornish-Fisher Modified VaR")
    print("  • Multi-Strategy Orchestration")
    print("\nTarget Performance:")
    print("  • Sharpe Ratio: 2.07")
    print("  • Annual Return: 31%")
    print("  • Max Drawdown: 11.2%")
    print("  • Win Rate: 58.2%")
    print("\n" + "="*80)

    # Initialize backtest
    backtest = ComprehensiveBacktest()

    # Run backtest
    try:
        results = await backtest.run(
            start_date='2024-01-01',
            end_date='2024-06-30',  # 6 months for testing
            markets=['election_2024', 'crypto_btc', 'sports_nfl']
        )

        # Check if targets achieved
        all_achieved = all(
            metric['achieved']
            for metric in results['vs_targets'].values()
        )

        if all_achieved:
            print("\n🎉 SUCCESS! All performance targets achieved!")
        else:
            print("\n⚠️ Some targets not achieved. Further optimization needed.")

    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
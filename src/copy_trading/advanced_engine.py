"""
Advanced Copy Trading Engine with Research-Based Components
Integrates all advanced features from the research document
"""

import asyncio
import json
import logging
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from libs.common.models import Whale, Trade, Order, Market

# Import all advanced components
from copy_trading.orderbook_tracker import OrderbookTracker as WhalePositionTracker
from copy_trading.signal_pipeline import SignalPipeline
from scoring.advanced_wqs import AdvancedWhaleQualityScore
from position_sizing.adaptive_kelly import AdaptiveKellyCalculator
from risk_management.cornish_fisher_var import CornishFisherVaR
from market_analysis.regime_detection import RegimeDetector, MarketRegime
from analytics.performance_attribution import PerformanceAttribution

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AdvancedCopyTradingEngine:
    """
    Advanced copy trading engine implementing all research-based strategies:
    - 5-factor Whale Quality Score
    - 3-stage signal filtering
    - Adaptive Kelly position sizing
    - Cornish-Fisher mVaR risk management
    - Market regime detection
    - Performance attribution
    """

    def __init__(self, config_path: str = "config/advanced_copy_trading.json"):
        """Initialize the advanced copy trading engine with all components."""
        self.config = self.load_config(config_path)
        self.running = False

        # Initialize advanced components
        self.wqs_calculator = AdvancedWhaleQualityScore()
        self.signal_pipeline = SignalPipeline(self.config.get('signal_filters'))
        self.kelly_calculator = AdaptiveKellyCalculator(self.config.get('position_sizing'))
        self.var_calculator = CornishFisherVaR(self.config.get('risk_management'))
        self.regime_detector = RegimeDetector(self.config.get('regime_detection'))
        self.performance_tracker = PerformanceAttribution()

        # Position tracker for monitoring
        self.position_tracker = WhalePositionTracker()

        # Portfolio state
        self.portfolio_state = {
            'positions': {},
            'total_exposure_pct': 0,
            'sector_exposures': {},
            'nav': self.config.get('initial_capital', 10000),
            'cash': self.config.get('initial_capital', 10000),
            'daily_pnl': 0,
            'total_pnl': 0
        }

        # Performance metrics
        self.performance_metrics = {
            'trades_evaluated': 0,
            'trades_copied': 0,
            'filter_stage_rejections': {'stage1': 0, 'stage2': 0, 'stage3': 0},
            'total_pnl': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0
        }

        # Database setup
        self._setup_database()

    def load_config(self, config_path: str) -> dict:
        """Load advanced configuration."""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Config file {config_path} not found, using defaults")
            return self._default_config()

    def _default_config(self) -> dict:
        """Default advanced configuration matching research specifications."""
        return {
            'initial_capital': 10000,
            'min_wqs_score': 75,  # Minimum WQS for whale selection
            'signal_filters': {
                'whale_filter': {
                    'min_wqs': 75,
                    'momentum_lookback_days': 90,
                    'max_whale_drawdown': 0.25
                },
                'trade_filter': {
                    'min_trade_size_usd': 5000,
                    'max_slippage_pct': 0.01,
                    'max_time_to_resolution_days': 90,
                    'min_edge_pct': 0.03
                },
                'portfolio_filter': {
                    'max_correlation': 0.4,
                    'max_total_exposure_pct': 0.95,
                    'max_sector_concentration_pct': 0.30
                }
            },
            'position_sizing': {
                'kelly_fraction': 0.25,  # 25% Kelly
                'max_position_pct': 0.25,
                'min_position_pct': 0.01
            },
            'risk_management': {
                'confidence_levels': [0.95, 0.99],
                'max_daily_var': 0.02,  # 2% daily VaR limit
                'stop_loss_pct': 0.05,
                'take_profit_pct': 0.15
            },
            'regime_detection': {
                'ewma_lambda': 0.94,
                'lookback_days': 60
            },
            'monitoring_interval_seconds': 300  # 5 minutes
        }

    def _setup_database(self):
        """Setup database connection."""
        from dotenv import load_dotenv
        import os
        load_dotenv()

        DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)

    async def start(self):
        """Start the advanced copy trading engine."""
        logger.info("=" * 80)
        logger.info("🚀 ADVANCED COPY TRADING ENGINE STARTING")
        logger.info("=" * 80)
        logger.info("Research-based implementation with:")
        logger.info("  • 5-Factor Whale Quality Score")
        logger.info("  • 3-Stage Signal Filtering")
        logger.info("  • Adaptive Kelly Position Sizing")
        logger.info("  • Cornish-Fisher mVaR Risk Management")
        logger.info("  • Market Regime Detection")
        logger.info("  • Performance Attribution")
        logger.info("=" * 80)

        self.running = True

        # Initialize regime detection with market data
        await self._initialize_market_regime()

        # Main monitoring loop
        try:
            while self.running:
                await self.monitor_cycle()
                await asyncio.sleep(self.config['monitoring_interval_seconds'])
        except KeyboardInterrupt:
            logger.info("\n⏸️  Stopping engine...")
            self.running = False
        except Exception as e:
            logger.error(f"❌ Engine error: {e}")
            raise

    async def monitor_cycle(self):
        """Execute one monitoring cycle with advanced filtering."""
        session = self.Session()

        try:
            # 1. Get high-quality whales (WQS >= 75)
            whales = await self._get_quality_whales(session)

            logger.info(f"🔍 Monitoring {len(whales)} quality whales (WQS >= 75)...")

            trades_evaluated = 0
            trades_copied = 0

            for whale in whales:
                # Get new trades from whale
                new_trades = self.position_tracker.monitor_whale(whale.address)

                if new_trades:
                    for trade_data in new_trades:
                        trades_evaluated += 1

                        # 2. Run through 3-stage signal filtering
                        should_copy, reason, metadata = await self._evaluate_signal(
                            trade_data, whale, session
                        )

                        if should_copy:
                            # 3. Calculate position size with Adaptive Kelly
                            position_size = await self._calculate_position_size(
                                trade_data, whale, session
                            )

                            # 4. Check risk limits with Cornish-Fisher mVaR
                            if await self._check_risk_limits(position_size, session):
                                # 5. Execute copy trade
                                await self._execute_advanced_copy(
                                    trade_data, whale, position_size, session
                                )
                                trades_copied += 1
                                logger.info(f"✅ Trade copied with advanced logic")
                            else:
                                logger.info(f"⚠️ Trade rejected by risk limits")
                        else:
                            # Track filter rejections
                            stage_failed = metadata.get('stage_failed', 0)
                            if stage_failed > 0:
                                stage_key = f'stage{stage_failed}'
                                self.performance_metrics['filter_stage_rejections'][stage_key] += 1
                            logger.info(f"⏭️ Trade filtered: {reason}")

            # Update performance metrics
            self.performance_metrics['trades_evaluated'] += trades_evaluated
            self.performance_metrics['trades_copied'] += trades_copied

            # 6. Update performance attribution
            await self._update_performance_attribution(session)

            # Log summary
            if trades_evaluated > 0:
                copy_rate = trades_copied / trades_evaluated * 100
                logger.info(f"📊 Cycle complete: {trades_copied}/{trades_evaluated} trades copied ({copy_rate:.1f}%)")
                logger.info(f"   Filter rejections - Stage 1: {self.performance_metrics['filter_stage_rejections']['stage1']}, "
                          f"Stage 2: {self.performance_metrics['filter_stage_rejections']['stage2']}, "
                          f"Stage 3: {self.performance_metrics['filter_stage_rejections']['stage3']}")

        except Exception as e:
            logger.error(f"Error in monitor cycle: {e}")
        finally:
            session.close()

    async def _get_quality_whales(self, session: Session) -> List[Whale]:
        """Get whales with WQS >= 75."""
        min_wqs = self.config['min_wqs_score']

        whales = session.query(Whale).filter(
            Whale.quality_score >= min_wqs,
            Whale.is_copying_enabled == True
        ).order_by(Whale.quality_score.desc()).all()

        # Recalculate WQS with advanced formula if needed
        quality_whales = []
        for whale in whales:
            # Get whale metrics for WQS calculation
            metrics = self._get_whale_metrics(whale, session)

            # Calculate advanced WQS
            wqs = self.wqs_calculator.calculate_wqs(metrics)

            if wqs >= min_wqs:
                whale.quality_score = wqs  # Update score
                quality_whales.append(whale)

        return quality_whales

    def _get_whale_metrics(self, whale: Whale, session: Session) -> Dict:
        """Get whale metrics for WQS calculation."""
        # Get recent trades
        recent_trades = session.query(Trade).filter(
            Trade.trader_address == whale.address,
            Trade.timestamp > datetime.utcnow() - timedelta(days=90)
        ).all()

        if not recent_trades:
            return {}

        # Calculate time-decayed metrics
        trades_data = [
            {
                'timestamp': t.timestamp,
                'pnl': t.pnl or 0,
                'amount': t.amount
            }
            for t in recent_trades
        ]

        metrics = self.wqs_calculator.calculate_time_decayed_metrics(trades_data)

        # Add other metrics from whale model
        metrics.update({
            'information_ratio_annualized': whale.information_ratio or 0,
            'calmar_ratio': whale.calmar_ratio or 0,
            'rolling_30d_sharpe_std': 0.5,  # Placeholder
            'total_volume_usd': whale.total_volume or 0,
            'hhi_concentration': 1500  # Placeholder
        })

        return metrics

    async def _evaluate_signal(
        self,
        trade_data: Dict,
        whale: Whale,
        session: Session
    ) -> Tuple[bool, str, Dict]:
        """Evaluate trade signal through 3-stage filtering."""
        # Prepare data for signal pipeline
        whale_data = {
            'quality_score': whale.quality_score,
            'sharpe_30d': whale.sharpe_30d or 0,
            'sharpe_90d': whale.sharpe_90d or 0,
            'current_drawdown': whale.current_drawdown or 0
        }

        market_data = await self._get_market_data(trade_data['market_id'], session)

        # Run through signal pipeline
        should_copy, reason, metadata = self.signal_pipeline.evaluate_signal(
            trade_data,
            whale_data,
            market_data,
            self.portfolio_state
        )

        return should_copy, reason, metadata

    async def _get_market_data(self, market_id: str, session: Session) -> Dict:
        """Get market data for signal evaluation."""
        # Query market data (simplified for now)
        market = session.query(Market).filter_by(id=market_id).first()

        if market:
            return {
                'volume_24h': market.volume_24h or 1000000,
                'volatility': 0.02,  # Placeholder
                'last_price': market.last_price or 0.5,
                'end_date': market.end_date,
                'category': market.category or 'unknown'
            }
        else:
            return {
                'volume_24h': 1000000,
                'volatility': 0.02,
                'last_price': 0.5,
                'end_date': None,
                'category': 'unknown'
            }

    async def _calculate_position_size(
        self,
        trade_data: Dict,
        whale: Whale,
        session: Session
    ) -> float:
        """Calculate position size using Adaptive Kelly."""
        # Get whale metrics
        whale_metrics = {
            'adjusted_win_rate': whale.win_rate or 0.5,
            'avg_win_size': abs(whale.avg_win or 1.0),
            'avg_loss_size': abs(whale.avg_loss or 1.0),
            'trade_count': whale.trade_count or 0
        }

        # Get market metrics
        market_metrics = await self._get_market_data(trade_data['market_id'], session)

        # Detect current regime
        regime_info = await self._get_current_regime()
        market_metrics['regime'] = regime_info['regime'].value

        # Calculate position size
        sizing_result = self.kelly_calculator.calculate_position_size(
            whale_metrics,
            market_metrics,
            self.portfolio_state,
            self.portfolio_state['cash']
        )

        position_size = sizing_result['position_size_usd']

        logger.info(f"📏 Position sizing: ${position_size:.2f} "
                   f"({sizing_result['position_pct']*100:.1f}% of capital)")
        logger.info(f"   Base Kelly: {sizing_result['base_kelly']:.3f}, "
                   f"Safe Kelly: {sizing_result['safe_kelly']:.3f}")

        return position_size

    async def _check_risk_limits(self, position_size: float, session: Session) -> bool:
        """Check risk limits using Cornish-Fisher mVaR."""
        # Get portfolio returns history
        recent_trades = session.query(Trade).filter(
            Trade.is_whale_trade == False,  # Our trades
            Trade.timestamp > datetime.utcnow() - timedelta(days=30)
        ).all()

        if recent_trades:
            returns = np.array([t.pnl / t.amount if t.amount else 0 for t in recent_trades])

            # Calculate mVaR
            mvar_result = self.var_calculator.calculate_mvar(returns, confidence_level=0.95)

            # Check if position would exceed VaR limit
            position_var = (position_size / self.portfolio_state['nav']) * mvar_result.get('mvar', 0.02)
            max_var = self.config['risk_management']['max_daily_var']

            if position_var > max_var:
                logger.warning(f"⚠️ Position VaR ({position_var:.3f}) exceeds limit ({max_var:.3f})")
                return False

            # Calculate dynamic risk limits
            risk_limits = self.var_calculator.calculate_dynamic_risk_limits(
                self.portfolio_state['daily_pnl'],
                returns,
                position_size
            )

            if position_size > risk_limits['adjusted_limit']:
                logger.warning(f"⚠️ Position size exceeds dynamic limit: ${risk_limits['adjusted_limit']:.2f}")
                return False

        return True

    async def _get_current_regime(self) -> Dict:
        """Get current market regime."""
        # Get recent market data (simplified)
        # In production, would fetch actual market prices
        price_data = np.random.randn(60) * 0.02 + 1.0  # Simulated prices
        price_data = np.cumprod(price_data) * 100

        regime_info = self.regime_detector.detect_regime(price_data)

        logger.info(f"🌡️ Market regime: {regime_info['regime'].value} "
                   f"(confidence: {regime_info['confidence']:.2f})")

        return regime_info

    async def _execute_advanced_copy(
        self,
        trade_data: Dict,
        whale: Whale,
        position_size: float,
        session: Session
    ):
        """Execute copy trade with advanced features."""
        price = trade_data['price']
        shares = position_size / price if price > 0 else 0

        logger.info("=" * 80)
        logger.info(f"🎯 EXECUTING ADVANCED COPY TRADE")
        logger.info(f"   Whale: {whale.pseudonym or whale.address[:10]} (WQS: {whale.quality_score:.1f})")
        logger.info(f"   Market: {trade_data.get('market_title', 'Unknown')[:50]}")
        logger.info(f"   Side: {trade_data['type']}")
        logger.info(f"   Size: {shares:.2f} shares @ ${price:.3f} = ${position_size:.2f}")
        logger.info("=" * 80)

        # Create order with advanced metadata
        order = Order(
            order_id=f"adv_{trade_data.get('id', '')}_{datetime.utcnow().timestamp()}",
            market_id=trade_data.get('market_id', ''),
            token_id=trade_data.get('market_id', ''),
            side=trade_data.get('type', 'BUY').upper(),
            order_type="LIMIT",
            price=price,
            size=shares,
            status="PENDING",
            source_whale=whale.address,
            source_trade_id=trade_data.get('id', ''),
            copy_ratio=Decimal(str(position_size / trade_data['amount'])),
            metadata=json.dumps({
                'wqs_score': whale.quality_score,
                'regime': self.regime_detector.current_regime.value,
                'kelly_fraction': self.kelly_calculator.kelly_fraction,
                'signal_confidence': trade_data.get('signal_confidence', 0)
            })
        )

        session.add(order)

        # Update portfolio state
        self.portfolio_state['cash'] -= position_size
        self.portfolio_state['positions'][trade_data['market_id']] = {
            'shares': shares,
            'entry_price': price,
            'size': position_size,
            'whale': whale.address
        }

        # Save trade record
        trade = Trade(
            trade_id=f"copy_{trade_data.get('id', '')}_{datetime.utcnow().timestamp()}"[:100],
            trader_address='self',
            market_id=trade_data.get('market_id', ''),
            market_title=trade_data.get('market_title', ''),
            token_id=trade_data.get('market_id', ''),
            side=trade_data.get('type', 'BUY').upper(),
            size=shares,
            price=price,
            amount=position_size,
            timestamp=datetime.utcnow(),
            is_whale_trade=False,
            followed=True,
            copy_reason=f"Advanced copy from WQS {whale.quality_score:.0f} whale"
        )

        session.add(trade)
        session.commit()

        logger.info(f"✅ Advanced copy trade executed successfully")

    async def _update_performance_attribution(self, session: Session):
        """Update performance attribution analysis."""
        # Get recent trades
        recent_trades = session.query(Trade).filter(
            Trade.is_whale_trade == False,
            Trade.timestamp > datetime.utcnow() - timedelta(days=7)
        ).all()

        if recent_trades:
            trades_data = [
                {
                    'trade_id': t.trade_id,
                    'source_whale': t.trader_address,
                    'market_id': t.market_id,
                    'category': 'unknown',  # Would get from market data
                    'side': t.side,
                    'amount': t.amount,
                    'price': t.price,
                    'pnl': t.pnl or 0,
                    'timestamp': t.timestamp
                }
                for t in recent_trades
            ]

            # Calculate attribution
            attribution = self.performance_tracker.calculate_attribution(
                trades_data,
                self.portfolio_state['nav']
            )

            # Log key insights
            if attribution['total_return'] != 0:
                logger.info(f"📈 Performance Attribution:")
                logger.info(f"   Total Return: {attribution['total_return']*100:.2f}%")
                logger.info(f"   Alpha: {attribution['alpha']*100:.2f}%")

                # Get top factor
                factors = attribution['factors']
                top_factor = max(factors.items(),
                               key=lambda x: abs(x[1]['contribution']))
                logger.info(f"   Top Factor: {top_factor[0]} "
                          f"({top_factor[1]['contribution']*100:.2f}%)")

    async def get_performance_summary(self) -> Dict:
        """Get comprehensive performance summary."""
        return {
            'engine_metrics': self.performance_metrics,
            'portfolio_state': self.portfolio_state,
            'regime': self.regime_detector.current_regime.value,
            'attribution': self.performance_tracker.generate_attribution_report(),
            'recommendations': self.performance_tracker.get_optimization_recommendations(),
            'timestamp': datetime.utcnow()
        }

    async def stop(self):
        """Stop the advanced copy trading engine."""
        logger.info("🛑 Stopping advanced copy trading engine...")
        self.running = False

        # Generate final report
        summary = await self.get_performance_summary()
        logger.info(f"Final Performance Summary:")
        logger.info(f"  Trades Evaluated: {summary['engine_metrics']['trades_evaluated']}")
        logger.info(f"  Trades Copied: {summary['engine_metrics']['trades_copied']}")
        logger.info(f"  Total P&L: ${summary['portfolio_state']['total_pnl']:.2f}")


async def main():
    """Main entry point for advanced copy trading engine."""
    engine = AdvancedCopyTradingEngine()
    await engine.start()


if __name__ == "__main__":
    asyncio.run(main())
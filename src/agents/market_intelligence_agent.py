"""
Market Intelligence Agent - Multi-Agent System Component
Part of Hybrid MAS Architecture (HYBRID_MAS_ARCHITECTURE.md)

This agent provides real-time market intelligence and anomaly detection.

Core Responsibilities:
1. Real-time monitoring via Polymarket RTDS WebSocket
2. Anomaly detection (uses RealTimeAnomalyDetector)
3. Market regime detection (TRENDING, RANGING, HIGH_VOLATILITY, LOW_LIQUIDITY)
4. Alert routing (P1 → PagerDuty, P2 → Slack, P3 → Logs)

Statistical Methods:
- EWMA Z-scores for anomaly detection
- Bai-Perron structural break test
- Regime classification using volatility and autocorrelation

Message Contracts:
- Subscribes: activity.trades (RTDS), MarketDataUpdate
- Publishes: AnomalyAlert, MarketRegimeChange

Performance Targets:
- Sub-2-second anomaly detection
- 92% capture rate for significant whale trades
- <1 false positive per 5 minutes

Author: Whale Trader v2.0 MAS
Date: November 2025
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional
import numpy as np
from scipy import stats
import json
import websockets

# Import anomaly detector
import sys
sys.path.append('/Users/ronitchhibber/Desktop/Whale.Trader-v0.1/src')
from analytics.realtime_anomaly_detector import (
    RealTimeAnomalyDetector,
    AnomalyDetectorConfig,
    TradeEvent,
    AnomalyAlert,
    AlertPriority
)

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime classification"""
    TRENDING = "trending"  # Strong directional movement
    RANGING = "ranging"  # Sideways, mean-reverting
    HIGH_VOLATILITY = "high_volatility"  # Elevated volatility
    LOW_LIQUIDITY = "low_liquidity"  # Thin orderbooks


@dataclass
class MarketIntelligenceConfig:
    """Configuration for Market Intelligence Agent"""

    # Data sources
    rtds_websocket_url: str = "wss://ws-live-data.polymarket.com"
    rtds_api_key: Optional[str] = None

    # Anomaly detection
    anomaly_config: AnomalyDetectorConfig = None

    # Regime detection
    regime_detection_interval_seconds: int = 300  # 5 minutes
    volatility_window_days: int = 30
    high_volatility_threshold_pct: float = 5.0  # Daily vol > 5%
    low_liquidity_threshold_usd: float = 10000.0  # 24h volume < $10k

    # Alert routing
    pagerduty_api_key: Optional[str] = None
    slack_webhook_url: Optional[str] = None

    # Performance
    max_websocket_reconnect_attempts: int = 10
    websocket_reconnect_delay_seconds: int = 5


@dataclass
class MarketRegimeState:
    """Market regime state"""

    market_id: str
    current_regime: MarketRegime
    confidence: float  # 0-1

    # Regime characteristics
    volatility_30d: float
    volume_24h_usd: float
    autocorrelation: float  # Measures mean reversion
    trend_strength: float  # 0-1

    last_updated: datetime


class MarketIntelligenceAgent:
    """
    Specialized agent for market intelligence and anomaly detection.

    Integrates:
    - RealTimeAnomalyDetector for trade volume anomalies
    - Market regime detection for strategy adaptation
    - Alert routing to appropriate channels
    """

    def __init__(self, config: MarketIntelligenceConfig = None):
        """
        Initialize Market Intelligence Agent.

        Args:
            config: Configuration object
        """
        self.config = config or MarketIntelligenceConfig()

        # Initialize anomaly detector
        anomaly_config = self.config.anomaly_config or AnomalyDetectorConfig()
        self.anomaly_detector = RealTimeAnomalyDetector(anomaly_config)

        # Agent state
        self.market_regimes: Dict[str, MarketRegimeState] = {}
        self.websocket_connection: Optional[websockets.WebSocketClientProtocol] = None

        # Message queue (placeholder - would use Kafka in production)
        self.message_queue = []

        # Performance tracking
        self.intelligence_stats = {
            'total_trades_processed': 0,
            'total_anomalies_detected': 0,
            'alerts_sent_by_priority': {
                'P1': 0,
                'P2': 0,
                'P3': 0
            },
            'avg_processing_latency_ms': 0.0,
            'last_rtds_message_time': None
        }

        logger.info("MarketIntelligenceAgent initialized")

    async def rtds_monitoring_loop(self):
        """
        Main RTDS monitoring loop - processes real-time trades.

        Subscribes to Polymarket RTDS WebSocket (activity.trades topic)
        and feeds trades to the anomaly detector.
        """
        logger.info("Starting RTDS monitoring loop")

        reconnect_attempts = 0

        while True:
            try:
                # Connect to RTDS WebSocket
                async with websockets.connect(
                    self.config.rtds_websocket_url,
                    ping_interval=20,
                    ping_timeout=10
                ) as websocket:
                    self.websocket_connection = websocket
                    reconnect_attempts = 0

                    logger.info("Connected to Polymarket RTDS WebSocket")

                    # Subscribe to activity.trades topic
                    subscribe_message = {
                        "type": "subscribe",
                        "topics": ["activity.trades"]
                    }

                    if self.config.rtds_api_key:
                        subscribe_message["auth"] = {
                            "api_key": self.config.rtds_api_key
                        }

                    await websocket.send(json.dumps(subscribe_message))

                    # Process incoming messages
                    async for message in websocket:
                        await self._process_rtds_message(message)

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"RTDS WebSocket connection closed: {e}")
                reconnect_attempts += 1

                if reconnect_attempts > self.config.max_websocket_reconnect_attempts:
                    logger.error("Max reconnect attempts exceeded. Stopping.")
                    break

                # Exponential backoff
                delay = min(
                    self.config.websocket_reconnect_delay_seconds * (2 ** reconnect_attempts),
                    60
                )
                logger.info(f"Reconnecting in {delay}s... (attempt {reconnect_attempts})")
                await asyncio.sleep(delay)

            except Exception as e:
                logger.error(f"Error in RTDS loop: {e}", exc_info=True)
                await asyncio.sleep(10)

    async def _process_rtds_message(self, message: str):
        """
        Process a single RTDS WebSocket message.

        Args:
            message: JSON string from WebSocket
        """
        try:
            data = json.loads(message)

            # Update last message time
            self.intelligence_stats['last_rtds_message_time'] = datetime.now()

            # Parse trade event
            if data.get('type') == 'trade':
                trade_data = data.get('data', {})

                # Convert to TradeEvent
                trade = TradeEvent(
                    trade_id=trade_data.get('id', ''),
                    market_id=trade_data.get('market_id', ''),
                    market_topic=trade_data.get('market_topic', ''),
                    trader_address=trade_data.get('trader_address', ''),
                    side=trade_data.get('side', 'BUY'),
                    size=float(trade_data.get('size', 0)),
                    price=float(trade_data.get('price', 0)),
                    usd_value=float(trade_data.get('usd_value', 0)),
                    timestamp=datetime.fromisoformat(trade_data.get('timestamp', datetime.now().isoformat())),
                    is_whale=trade_data.get('is_whale', False)
                )

                # Feed to anomaly detector
                alert = self.anomaly_detector.process_trade_event(trade)

                # Update stats
                self.intelligence_stats['total_trades_processed'] += 1

                if alert:
                    self.intelligence_stats['total_anomalies_detected'] += 1
                    self.intelligence_stats['alerts_sent_by_priority'][alert.priority.value] += 1

                    # Route alert
                    await self._route_alert(alert)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse RTDS message: {e}")
        except Exception as e:
            logger.error(f"Error processing RTDS message: {e}", exc_info=True)

    async def _route_alert(self, alert: AnomalyAlert):
        """
        Route alert to appropriate channels based on priority.

        P1 (Critical): PagerDuty + Slack + Event Bus
        P2 (Warning): Slack + Event Bus
        P3 (Info): Event Bus only

        Args:
            alert: AnomalyAlert object
        """
        try:
            # Always publish to event bus (Kafka)
            self._publish_event('AnomalyAlert', {
                'alert_id': alert.alert_id,
                'alert_type': alert.alert_type.value,
                'priority': alert.priority.value,
                'market_id': alert.market_id,
                'market_topic': alert.market_topic,
                'trader_address': alert.trader_address,
                'z_score': alert.z_score,
                'observed_value': alert.observed_value,
                'baseline_mean': alert.baseline_mean,
                'message': alert.message,
                'timestamp': alert.timestamp.isoformat()
            })

            # Route to external channels based on priority
            if alert.priority == AlertPriority.P1_CRITICAL:
                # Send to PagerDuty
                if self.config.pagerduty_api_key:
                    await self._send_to_pagerduty(alert)

                # Send to Slack
                if self.config.slack_webhook_url:
                    await self._send_to_slack(alert, critical=True)

                logger.critical(f"🚨 P1 CRITICAL ALERT: {alert.message}")

            elif alert.priority == AlertPriority.P2_WARNING:
                # Send to Slack only
                if self.config.slack_webhook_url:
                    await self._send_to_slack(alert, critical=False)

                logger.warning(f"⚠️  P2 WARNING: {alert.message}")

            else:
                # P3 - just log
                logger.info(f"ℹ️  P3 INFO: {alert.message}")

        except Exception as e:
            logger.error(f"Error routing alert: {e}", exc_info=True)

    async def _send_to_pagerduty(self, alert: AnomalyAlert):
        """Send alert to PagerDuty"""
        # Placeholder - would use PagerDuty Events API v2
        logger.debug(f"Would send to PagerDuty: {alert.alert_id}")

    async def _send_to_slack(self, alert: AnomalyAlert, critical: bool = False):
        """Send alert to Slack"""
        # Placeholder - would use Slack Incoming Webhooks
        emoji = "🚨" if critical else "⚠️"
        logger.debug(f"Would send to Slack: {emoji} {alert.message}")

    async def regime_detection_loop(self):
        """
        Market regime detection loop.

        Runs every 5 minutes to classify market regimes:
        - TRENDING: Strong directional movement
        - RANGING: Mean-reverting, sideways
        - HIGH_VOLATILITY: Elevated volatility
        - LOW_LIQUIDITY: Thin orderbooks
        """
        logger.info("Starting regime detection loop")

        while True:
            try:
                # Fetch all active markets
                markets = await self._fetch_active_markets()

                for market in markets:
                    regime = await self._detect_market_regime(market)

                    # Check if regime changed
                    if market['id'] in self.market_regimes:
                        old_regime = self.market_regimes[market['id']].current_regime

                        if regime.current_regime != old_regime:
                            # Regime change detected!
                            self._publish_event('MarketRegimeChange', {
                                'market_id': market['id'],
                                'old_regime': old_regime.value,
                                'new_regime': regime.current_regime.value,
                                'confidence': regime.confidence,
                                'volatility_30d': regime.volatility_30d,
                                'volume_24h_usd': regime.volume_24h_usd,
                                'timestamp': datetime.now().isoformat()
                            })

                            logger.info(
                                f"📊 Regime change detected | "
                                f"Market: {market['topic'][:30]}... | "
                                f"{old_regime.value} → {regime.current_regime.value}"
                            )

                    # Update state
                    self.market_regimes[market['id']] = regime

                # Sleep 5 minutes
                await asyncio.sleep(self.config.regime_detection_interval_seconds)

            except Exception as e:
                logger.error(f"Error in regime detection loop: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def _detect_market_regime(self, market: Dict) -> MarketRegimeState:
        """
        Detect market regime for a single market.

        Uses:
        - Volatility (EWMA of returns)
        - Volume (24h trading volume)
        - Autocorrelation (measures mean reversion)
        - Trend strength (directional momentum)

        Args:
            market: Market data dict

        Returns:
            MarketRegimeState object
        """
        market_id = market['id']

        # Fetch historical data (prices, volume)
        # Placeholder - would query database
        volatility_30d = 3.5  # Placeholder %
        volume_24h_usd = 50000.0  # Placeholder
        autocorrelation = 0.1  # Placeholder
        trend_strength = 0.6  # Placeholder

        # Classify regime
        if volume_24h_usd < self.config.low_liquidity_threshold_usd:
            regime = MarketRegime.LOW_LIQUIDITY
            confidence = 0.9
        elif volatility_30d > self.config.high_volatility_threshold_pct:
            regime = MarketRegime.HIGH_VOLATILITY
            confidence = 0.85
        elif abs(autocorrelation) < 0.2 and trend_strength > 0.7:
            regime = MarketRegime.TRENDING
            confidence = 0.8
        else:
            regime = MarketRegime.RANGING
            confidence = 0.75

        return MarketRegimeState(
            market_id=market_id,
            current_regime=regime,
            confidence=confidence,
            volatility_30d=volatility_30d,
            volume_24h_usd=volume_24h_usd,
            autocorrelation=autocorrelation,
            trend_strength=trend_strength,
            last_updated=datetime.now()
        )

    async def _fetch_active_markets(self) -> List[Dict]:
        """Fetch list of active markets"""
        # Placeholder - would use Polymarket Gamma API
        return []

    def _publish_event(self, event_type: str, payload: Dict):
        """Publish event to message bus"""
        event = {
            'event_type': event_type,
            'payload': payload,
            'agent': 'MarketIntelligenceAgent',
            'timestamp': datetime.now().isoformat()
        }

        self.message_queue.append(event)
        logger.debug(f"Published event: {event_type}")

    def get_intelligence_stats(self) -> Dict:
        """Get intelligence statistics"""
        # Get anomaly detector performance
        detector_stats = self.anomaly_detector.get_performance_stats()

        return {
            'total_trades_processed': self.intelligence_stats['total_trades_processed'],
            'total_anomalies_detected': self.intelligence_stats['total_anomalies_detected'],
            'anomaly_rate_pct': (
                self.intelligence_stats['total_anomalies_detected']
                / max(1, self.intelligence_stats['total_trades_processed'])
            ) * 100,
            'alerts_by_priority': self.intelligence_stats['alerts_sent_by_priority'],
            'detector_performance': detector_stats,
            'last_rtds_message': self.intelligence_stats['last_rtds_message_time'],
            'active_markets_monitored': len(self.market_regimes)
        }


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def main():
        # Initialize agent
        agent = MarketIntelligenceAgent()

        # Start both loops concurrently
        await asyncio.gather(
            agent.rtds_monitoring_loop(),
            agent.regime_detection_loop()
        )

    # Run
    asyncio.run(main())

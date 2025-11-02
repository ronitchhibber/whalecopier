"""
Real-Time Anomaly Detection with EWMA Z-Scores
Based on Section 9 of the Polymarket Whale Filtering Research Brief

This module implements sub-2-second anomaly detection for whale trades using:
- Exponentially Weighted Moving Average (EWMA) baselines
- Rolling Z-score computation
- Tiered alert escalation with cooldowns
- Alert storm prevention

Architecture:
- Data source: Polymarket RTDS WebSocket (activity.trades topic)
- Processing: Apache Flink / Python streaming
- Output: Redis (real-time cache) + Alert destinations

Performance Target:
- End-to-end latency: < 2 seconds
- Alert precision: > 92% capture rate for significant whale trades
- False positive rate: < 1 alert per 5-minute interval

References:
- Research Brief Section 9: Real-Time Detection & Alerting System
- Research Brief Section 9.2: Trigger Logic (EWMA Z-Scores)
"""

import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Deque, Dict, List, Optional, Tuple
import time
import numpy as np

logger = logging.getLogger(__name__)


class AlertPriority(Enum):
    """Alert priority levels"""
    P1_CRITICAL = "P1"  # Sent to PagerDuty + Slack
    P2_WARNING = "P2"  # Sent to Slack only
    P3_INFO = "P3"  # Logged only


class AlertType(Enum):
    """Types of anomalies detected"""
    LARGE_TRADE_VOLUME = "large_trade_volume"
    HIGH_PRICE_IMPACT = "high_price_impact"
    RAPID_ACCUMULATION = "rapid_accumulation"
    SUSPICIOUS_PATTERN = "suspicious_pattern"
    WASH_TRADE_SUSPECTED = "wash_trade_suspected"


@dataclass
class TradeEvent:
    """Real-time trade event from WebSocket"""
    trade_id: str
    market_id: str
    market_topic: str
    trader_address: str
    side: str  # "BUY" or "SELL"
    size: float  # Number of shares
    price: float  # Price per share
    usd_value: float  # size * price
    timestamp: datetime
    is_whale: bool = False


@dataclass
class AnomalyAlert:
    """Anomaly detection alert"""
    alert_id: str
    alert_type: AlertType
    priority: AlertPriority
    market_id: str
    market_topic: str
    trader_address: str
    trade_id: str

    # Anomaly metrics
    z_score: float
    observed_value: float
    baseline_mean: float
    baseline_std: float

    # Context
    timestamp: datetime
    message: str
    metadata: Dict


@dataclass
class AnomalyDetectorConfig:
    """Configuration for real-time anomaly detection"""

    # EWMA parameters
    ewma_span: int = 60  # 60-minute exponential window
    ewma_adjust: bool = True  # Adjust for early periods

    # Z-score threshold
    z_score_threshold: float = 3.0  # 99.7% confidence

    # Alert cooldown
    cooldown_window_seconds: int = 300  # 5 minutes
    max_alerts_before_cooldown: int = 3  # Suppress after 3 alerts in window
    cooldown_duration_seconds: int = 600  # 10-minute suppression

    # Data retention
    rolling_window_size: int = 1000  # Keep last 1000 trades per market

    # Thresholds (override Z-score for specific conditions)
    min_usd_value_for_whale: float = 5000.0  # $5k minimum
    extreme_z_score_threshold: float = 5.0  # P1 critical

    # Performance
    max_processing_latency_ms: float = 200.0  # 200ms budget


class RealTimeAnomalyDetector:
    """
    Real-time anomaly detection engine using EWMA Z-scores.

    Implements Section 9.2 of the research brief:
    - Establishes EWMA baseline for each market
    - Computes rolling Z-scores for new trades
    - Fires alerts when Z-score > threshold
    - Manages alert cooldowns to prevent storms
    """

    def __init__(self, config: AnomalyDetectorConfig = None):
        """
        Initialize the real-time anomaly detector.

        Args:
            config: Configuration object (uses defaults if None)
        """
        self.config = config or AnomalyDetectorConfig()

        # State: market_id -> deque of trade USD values
        self.market_trade_history: Dict[str, Deque[Tuple[datetime, float]]] = defaultdict(
            lambda: deque(maxlen=self.config.rolling_window_size)
        )

        # EWMA state: market_id -> (ewma_mean, ewma_std)
        self.market_ewma: Dict[str, Tuple[float, float]] = {}

        # Alert cooldown state: (market_id, trader_address) -> deque of alert timestamps
        self.cooldown_state: Dict[Tuple[str, str], Deque[datetime]] = defaultdict(
            lambda: deque(maxlen=self.config.max_alerts_before_cooldown)
        )

        # Suppression state: (market_id, trader_address) -> suppression_end_time
        self.suppressed_until: Dict[Tuple[str, str], datetime] = {}

        # Performance tracking
        self.processing_times: Deque[float] = deque(maxlen=100)

        logger.info("RealTimeAnomalyDetector initialized")

    def update_market_baseline(
        self,
        market_id: str,
        trade_timestamp: datetime,
        trade_usd_value: float
    ) -> Tuple[float, float]:
        """
        Update EWMA baseline for a market.

        Uses exponentially weighted moving average to track:
        - Mean trade size
        - Standard deviation of trade size

        Reference: Section 9.2, "EWMA Z-Scores"

        Args:
            market_id: Market identifier
            trade_timestamp: Timestamp of the trade
            trade_usd_value: USD value of the trade

        Returns:
            Tuple of (ewma_mean, ewma_std)
        """
        # Add to history
        self.market_trade_history[market_id].append((trade_timestamp, trade_usd_value))

        # Extract values for EWMA calculation
        trade_values = [val for _, val in self.market_trade_history[market_id]]

        if len(trade_values) < 2:
            # Insufficient data
            return (trade_usd_value, 0.0)

        # Compute EWMA mean
        ewma_mean = self._ewma(
            trade_values,
            span=self.config.ewma_span,
            adjust=self.config.ewma_adjust
        )

        # Compute EWMA standard deviation
        # Use exponentially weighted variance
        deviations = [(val - ewma_mean)**2 for val in trade_values]
        ewma_variance = self._ewma(
            deviations,
            span=self.config.ewma_span,
            adjust=self.config.ewma_adjust
        )
        ewma_std = np.sqrt(ewma_variance) if ewma_variance > 0 else 0.0

        # Update state
        self.market_ewma[market_id] = (ewma_mean, ewma_std)

        return (ewma_mean, ewma_std)

    def _ewma(
        self,
        values: List[float],
        span: int,
        adjust: bool = True
    ) -> float:
        """
        Calculate Exponentially Weighted Moving Average.

        EWMA formula:
        - α = 2 / (span + 1)
        - EWMA_t = α * value_t + (1 - α) * EWMA_{t-1}

        Args:
            values: List of values (time-ordered)
            span: Span for exponential weighting
            adjust: If True, adjust for early periods

        Returns:
            EWMA value
        """
        if not values:
            return 0.0

        alpha = 2.0 / (span + 1)
        ewma = values[0]

        for i, value in enumerate(values[1:], start=1):
            if adjust:
                # Adjust for bias in early periods
                weight = 1 - (1 - alpha)**i
                ewma = (alpha * value + (1 - alpha) * ewma) / weight
            else:
                ewma = alpha * value + (1 - alpha) * ewma

        return ewma

    def calculate_z_score(
        self,
        observed_value: float,
        baseline_mean: float,
        baseline_std: float
    ) -> float:
        """
        Calculate Z-score for anomaly detection.

        Z-score = (observed_value - baseline_mean) / baseline_std

        Reference: Section 9.2, "Trigger Logic"

        Args:
            observed_value: The observed trade size
            baseline_mean: EWMA baseline mean
            baseline_std: EWMA baseline std

        Returns:
            Z-score (positive = larger than baseline)
        """
        if baseline_std == 0.0:
            # No variation yet - use simple comparison
            return 1.0 if observed_value > baseline_mean else 0.0

        z_score = (observed_value - baseline_mean) / baseline_std

        return float(z_score)

    def is_suppressed(
        self,
        market_id: str,
        trader_address: str,
        current_time: datetime
    ) -> bool:
        """
        Check if alerts are suppressed for this (market, trader) pair.

        Reference: Section 9.3, "Alert Management: Cooldowns"

        Args:
            market_id: Market identifier
            trader_address: Trader wallet address
            current_time: Current timestamp

        Returns:
            True if alerts are suppressed, False otherwise
        """
        key = (market_id, trader_address)

        # Check if currently suppressed
        if key in self.suppressed_until:
            if current_time < self.suppressed_until[key]:
                return True
            else:
                # Suppression expired
                del self.suppressed_until[key]
                self.cooldown_state[key].clear()
                return False

        # Check cooldown window
        recent_alerts = self.cooldown_state[key]
        if len(recent_alerts) == 0:
            return False

        # Remove old alerts outside cooldown window
        window_start = current_time - timedelta(
            seconds=self.config.cooldown_window_seconds
        )
        while recent_alerts and recent_alerts[0] < window_start:
            recent_alerts.popleft()

        # Check if threshold exceeded
        if len(recent_alerts) >= self.config.max_alerts_before_cooldown:
            # Activate suppression
            suppression_end = current_time + timedelta(
                seconds=self.config.cooldown_duration_seconds
            )
            self.suppressed_until[key] = suppression_end

            logger.warning(
                f"Alert storm detected for market={market_id}, trader={trader_address[:10]}. "
                f"Suppressing for {self.config.cooldown_duration_seconds}s"
            )

            return True

        return False

    def record_alert(
        self,
        market_id: str,
        trader_address: str,
        alert_time: datetime
    ):
        """
        Record that an alert was fired (for cooldown tracking).

        Args:
            market_id: Market identifier
            trader_address: Trader wallet address
            alert_time: Alert timestamp
        """
        key = (market_id, trader_address)
        self.cooldown_state[key].append(alert_time)

    def process_trade_event(
        self,
        trade: TradeEvent
    ) -> Optional[AnomalyAlert]:
        """
        Process a real-time trade event and detect anomalies.

        Main entry point for stream processing.

        Reference: Section 9, "Real-Time Detection & Alerting"

        Args:
            trade: TradeEvent object from WebSocket

        Returns:
            AnomalyAlert if anomaly detected, None otherwise
        """
        start_time = time.perf_counter()

        # Update baseline
        ewma_mean, ewma_std = self.update_market_baseline(
            trade.market_id,
            trade.timestamp,
            trade.usd_value
        )

        # Calculate Z-score
        z_score = self.calculate_z_score(
            trade.usd_value,
            ewma_mean,
            ewma_std
        )

        # Check suppression
        if self.is_suppressed(trade.market_id, trade.trader_address, trade.timestamp):
            # Alert suppressed
            end_time = time.perf_counter()
            self.processing_times.append((end_time - start_time) * 1000)
            return None

        # Determine if anomaly
        alert = None

        if z_score >= self.config.z_score_threshold:
            # Anomaly detected!

            # Determine priority
            if z_score >= self.config.extreme_z_score_threshold:
                priority = AlertPriority.P1_CRITICAL
            elif z_score >= 4.0:
                priority = AlertPriority.P2_WARNING
            else:
                priority = AlertPriority.P3_INFO

            # Only create alert if P1 or P2 (or whale trade)
            if priority in [AlertPriority.P1_CRITICAL, AlertPriority.P2_WARNING] or trade.is_whale:
                alert_id = f"alert_{trade.market_id}_{trade.trade_id}_{int(time.time()*1000)}"

                alert = AnomalyAlert(
                    alert_id=alert_id,
                    alert_type=AlertType.LARGE_TRADE_VOLUME,
                    priority=priority,
                    market_id=trade.market_id,
                    market_topic=trade.market_topic,
                    trader_address=trade.trader_address,
                    trade_id=trade.trade_id,
                    z_score=z_score,
                    observed_value=trade.usd_value,
                    baseline_mean=ewma_mean,
                    baseline_std=ewma_std,
                    timestamp=trade.timestamp,
                    message=self._format_alert_message(trade, z_score, ewma_mean),
                    metadata={
                        'side': trade.side,
                        'size': trade.size,
                        'price': trade.price,
                        'is_whale': trade.is_whale
                    }
                )

                # Record alert
                self.record_alert(trade.market_id, trade.trader_address, trade.timestamp)

                logger.info(
                    f"{priority.value} Alert: {alert.message} "
                    f"(Z-score: {z_score:.2f}, Latency: {(time.perf_counter() - start_time)*1000:.1f}ms)"
                )

        # Track processing time
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000
        self.processing_times.append(latency_ms)

        if latency_ms > self.config.max_processing_latency_ms:
            logger.warning(f"High processing latency: {latency_ms:.1f}ms (threshold: {self.config.max_processing_latency_ms}ms)")

        return alert

    def _format_alert_message(
        self,
        trade: TradeEvent,
        z_score: float,
        baseline_mean: float
    ) -> str:
        """
        Format a human-readable alert message.

        Args:
            trade: TradeEvent object
            z_score: Calculated Z-score
            baseline_mean: Baseline mean for comparison

        Returns:
            Formatted message string
        """
        magnitude = trade.usd_value / baseline_mean if baseline_mean > 0 else 0.0

        message = (
            f"Anomalous {trade.side} trade detected | "
            f"Market: {trade.market_topic} | "
            f"Trader: {trade.trader_address[:10]}... | "
            f"Size: ${trade.usd_value:,.0f} ({magnitude:.1f}x baseline) | "
            f"Z-score: {z_score:.2f}"
        )

        return message

    def get_performance_stats(self) -> Dict:
        """
        Get performance statistics for the detector.

        Returns:
            Dictionary of performance metrics
        """
        if not self.processing_times:
            return {
                'avg_latency_ms': 0.0,
                'p50_latency_ms': 0.0,
                'p95_latency_ms': 0.0,
                'p99_latency_ms': 0.0,
                'total_events_processed': 0
            }

        latencies = list(self.processing_times)

        return {
            'avg_latency_ms': np.mean(latencies),
            'p50_latency_ms': np.percentile(latencies, 50),
            'p95_latency_ms': np.percentile(latencies, 95),
            'p99_latency_ms': np.percentile(latencies, 99),
            'max_latency_ms': np.max(latencies),
            'total_events_processed': len(latencies)
        }


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Initialize detector
    detector = RealTimeAnomalyDetector()

    # Simulate incoming trade stream
    market_id = "0xc4bfd17e4fcfea59ff7e96a32e5f85d2e1b3ef96"
    market_topic = "Will Trump win 2024 election?"

    # Baseline trades (typical activity)
    for i in range(20):
        trade = TradeEvent(
            trade_id=f"trade_{i}",
            market_id=market_id,
            market_topic=market_topic,
            trader_address=f"0x{i:040x}",
            side="BUY" if i % 2 == 0 else "SELL",
            size=1000.0,
            price=0.65,
            usd_value=650.0 + np.random.normal(0, 100),  # ~$650 typical
            timestamp=datetime.now() - timedelta(minutes=20-i),
            is_whale=False
        )

        alert = detector.process_trade_event(trade)
        if alert:
            print(f"  [ALERT] {alert.message}")

    # Anomalous whale trade
    print("\n--- Anomalous Whale Trade Incoming ---")
    whale_trade = TradeEvent(
        trade_id="whale_trade_1",
        market_id=market_id,
        market_topic=market_topic,
        trader_address="0xwhale12345",
        side="BUY",
        size=50000.0,
        price=0.67,
        usd_value=33500.0,  # 50x baseline!
        timestamp=datetime.now(),
        is_whale=True
    )

    alert = detector.process_trade_event(whale_trade)
    if alert:
        print(f"\n🚨 {alert.priority.value} ALERT FIRED 🚨")
        print(f"  Message: {alert.message}")
        print(f"  Z-Score: {alert.z_score:.2f}")
        print(f"  Baseline: ${alert.baseline_mean:,.0f} ± ${alert.baseline_std:,.0f}")
        print(f"  Observed: ${alert.observed_value:,.0f}")

    # Performance stats
    print("\n--- Performance Statistics ---")
    stats = detector.get_performance_stats()
    for key, value in stats.items():
        print(f"  {key}: {value:.2f}")

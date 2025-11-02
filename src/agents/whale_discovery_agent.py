"""
Whale Discovery Agent - Multi-Agent System Component
Part of Hybrid MAS Architecture (HYBRID_MAS_ARCHITECTURE.md)

This agent continuously discovers, scores, and ranks high-quality whale traders,
pruning underperformers using institutional-grade statistical methods.

Statistical Engines Used:
- CompositeWhaleScorer (XGBoost learning-to-rank)
- SkillVsLuckAnalyzer (DSR, PSR, bootstrap testing)
- Thompson Sampling (dynamic allocation)

Message Contracts:
- Subscribes: MarketDataUpdate
- Publishes: WhaleDiscovered, WhaleScoreUpdated, WhalePruned

Performance Targets:
- Discovery rate: 5-10 new qualified whales per week
- Pruning precision: >90% (pruned whales should underperform)
- Thompson Sampling alpha: +28% Sharpe Ratio improvement

Author: Whale Trader v2.0 MAS
Date: November 2025
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import numpy as np
from scipy import stats
import json

# Import statistical engines
import sys
sys.path.append('/Users/ronitchhibber/Desktop/Whale.Trader-v0.1/src')
from scoring.composite_whale_scorer import CompositeWhaleScorer, WhaleFeatures, WhaleScore
from scoring.skill_vs_luck_analyzer import SkillVsLuckAnalyzer, SkillTestResult

logger = logging.getLogger(__name__)


@dataclass
class WhaleDiscoveryConfig:
    """Configuration for Whale Discovery Agent"""

    # Scanning intervals
    scan_interval_seconds: int = 600  # 10 minutes
    pruning_interval_seconds: int = 86400  # 24 hours

    # Quality thresholds
    min_trades_for_significance: int = 30
    target_sharpe_ratio: float = 2.0
    psr_threshold: float = 0.85  # 85% probability SR > target
    dsr_threshold: float = 0.0  # Must be positive after bias correction

    # Thompson Sampling parameters
    thompson_prior_alpha: float = 1.0
    thompson_prior_beta: float = 1.0
    thompson_discount_factor: float = 0.95  # Emphasize recent performance

    # Changepoint detection (for pruning)
    cusum_threshold: float = 5.0  # Standard CUSUM threshold
    min_changepoint_window: int = 20  # Min trades before changepoint detection

    # Data sources
    polymarket_subgraphs: Dict[str, str] = None  # URLs for GraphQL subgraphs
    database_connection: str = "postgresql://trader:password@localhost:5432/polymarket_trader"


@dataclass
class WhaleCandidate:
    """Whale candidate for evaluation"""

    address: str
    discovered_at: datetime
    total_trades: int
    total_volume_usd: float
    realized_pnl_usd: float
    win_rate: float

    # Raw data for feature extraction
    trade_history: List[Dict]  # List of trade records
    position_history: List[Dict]  # List of position snapshots


@dataclass
class ThompsonSamplingState:
    """State for Thompson Sampling bandit"""

    address: str
    alpha: float  # Successes (winning trades)
    beta: float  # Failures (losing trades)
    last_updated: datetime
    total_samples: int  # Total trades sampled

    def sample_probability(self) -> float:
        """Sample from Beta(alpha, beta) posterior"""
        return np.random.beta(self.alpha, self.beta)

    def update(self, is_win: bool, discount_factor: float = 0.95):
        """Update posterior with new trade outcome"""
        time_decay = discount_factor ** ((datetime.now() - self.last_updated).days)

        if is_win:
            self.alpha += 1 * time_decay
        else:
            self.beta += 1 * time_decay

        self.last_updated = datetime.now()
        self.total_samples += 1


class WhaleDiscoveryAgent:
    """
    Specialized agent for whale discovery, scoring, and allocation.

    Responsibilities:
    1. Scan Polymarket subgraphs for new whale candidates
    2. Score candidates using CompositeWhaleScorer
    3. Validate skill using SkillVsLuckAnalyzer
    4. Dynamically allocate capital using Thompson Sampling
    5. Prune underperformers using changepoint detection
    """

    def __init__(self, config: WhaleDiscoveryConfig = None):
        """
        Initialize Whale Discovery Agent.

        Args:
            config: Configuration object
        """
        self.config = config or WhaleDiscoveryConfig()

        # Initialize statistical engines
        self.scorer = CompositeWhaleScorer(
            min_trades_for_significance=self.config.min_trades_for_significance,
            target_sharpe_ratio=self.config.target_sharpe_ratio
        )

        self.skill_analyzer = SkillVsLuckAnalyzer()

        # Agent state
        self.discovered_whales: Dict[str, WhaleScore] = {}  # address -> latest score
        self.skill_test_results: Dict[str, SkillTestResult] = {}  # address -> latest test
        self.thompson_state: Dict[str, ThompsonSamplingState] = {}  # address -> bandit state

        # Message queue (placeholder - would use Kafka in production)
        self.message_queue = []

        # Performance tracking
        self.discovery_stats = {
            'total_scanned': 0,
            'total_discovered': 0,
            'total_pruned': 0,
            'last_scan_time': None
        }

        logger.info("WhaleDiscoveryAgent initialized")

    async def discovery_loop(self):
        """
        Main discovery loop - runs continuously.

        Steps:
        1. Fetch whale candidates from Polymarket subgraphs
        2. Score each candidate
        3. Validate skill
        4. Update Thompson Sampling state
        5. Publish WhaleDiscovered events
        """
        logger.info("Starting whale discovery loop")

        while True:
            try:
                start_time = datetime.now()

                # Step 1: Fetch candidates
                candidates = await self.fetch_whale_candidates()
                logger.info(f"Fetched {len(candidates)} whale candidates")

                # Step 2: Process each candidate
                for candidate in candidates:
                    await self.process_whale_candidate(candidate)

                # Update stats
                self.discovery_stats['total_scanned'] += len(candidates)
                self.discovery_stats['last_scan_time'] = datetime.now()

                # Log performance
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.info(
                    f"Discovery cycle complete: {len(candidates)} candidates processed in {elapsed:.2f}s"
                )

                # Sleep until next scan
                await asyncio.sleep(self.config.scan_interval_seconds)

            except Exception as e:
                logger.error(f"Error in discovery loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait 1 minute before retry

    async def process_whale_candidate(self, candidate: WhaleCandidate):
        """
        Process a single whale candidate.

        Steps:
        1. Extract features
        2. Compute composite score
        3. Run skill vs luck tests
        4. Initialize/update Thompson Sampling state
        5. Publish events if qualified
        """
        try:
            # Step 1: Extract features
            whale_data = self._candidate_to_whale_data(candidate)
            features = self.scorer.extract_features(whale_data)

            # Step 2: Compute composite score
            score = self.scorer.compute_composite_score(features)

            # Step 3: Skill vs luck analysis
            returns = self._extract_returns(candidate.trade_history)
            returns_series = self._extract_returns_series(candidate.trade_history)

            skill_result = self.skill_analyzer.analyze_whale_skill(
                whale_address=candidate.address,
                returns=returns,
                returns_series=returns_series,
                num_whales_tested=len(self.discovered_whales)
            )

            # Step 4: Check qualification criteria
            is_qualified = (
                score.is_statistically_significant
                and skill_result.probabilistic_sharpe_ratio >= self.config.psr_threshold
                and skill_result.deflated_sharpe_ratio >= self.config.dsr_threshold
                and skill_result.has_persistent_skill
            )

            if is_qualified:
                # Step 5: Initialize Thompson Sampling state
                if candidate.address not in self.thompson_state:
                    self.thompson_state[candidate.address] = ThompsonSamplingState(
                        address=candidate.address,
                        alpha=self.config.thompson_prior_alpha,
                        beta=self.config.thompson_prior_beta,
                        last_updated=datetime.now(),
                        total_samples=0
                    )

                # Update agent state
                self.discovered_whales[candidate.address] = score
                self.skill_test_results[candidate.address] = skill_result

                # Publish WhaleDiscovered event
                self._publish_event('WhaleDiscovered', {
                    'address': candidate.address,
                    'score': score.score,
                    'rank': score.rank,
                    'percentile': score.percentile,
                    'dsr': skill_result.deflated_sharpe_ratio,
                    'psr': skill_result.probabilistic_sharpe_ratio,
                    'is_persistent': skill_result.has_persistent_skill,
                    'thompson_weight': self._calculate_thompson_weight(candidate.address),
                    'timestamp': datetime.now().isoformat()
                })

                self.discovery_stats['total_discovered'] += 1

                logger.info(
                    f"✅ Qualified whale discovered: {candidate.address[:10]}... | "
                    f"Score: {score.score:.2f} | DSR: {skill_result.deflated_sharpe_ratio:.3f} | "
                    f"PSR: {skill_result.probabilistic_sharpe_ratio:.3f}"
                )
            else:
                logger.debug(
                    f"❌ Candidate rejected: {candidate.address[:10]}... | "
                    f"Significant: {score.is_statistically_significant} | "
                    f"PSR: {skill_result.probabilistic_sharpe_ratio:.3f} | "
                    f"Persistent: {skill_result.has_persistent_skill}"
                )

        except Exception as e:
            logger.error(f"Error processing whale {candidate.address}: {e}")

    async def pruning_loop(self):
        """
        Pruning loop - removes underperforming whales.

        Steps:
        1. For each tracked whale, run changepoint detection
        2. Check if recent performance below thresholds
        3. If 3 consecutive failures, prune whale
        4. Publish WhalePruned event
        """
        logger.info("Starting whale pruning loop")

        while True:
            try:
                start_time = datetime.now()
                pruned_count = 0

                for address, score in list(self.discovered_whales.items()):
                    should_prune = await self._check_if_should_prune(address)

                    if should_prune:
                        # Remove from tracking
                        del self.discovered_whales[address]
                        del self.skill_test_results[address]
                        del self.thompson_state[address]

                        # Publish WhalePruned event
                        self._publish_event('WhalePruned', {
                            'address': address,
                            'reason': 'performance_degradation',
                            'timestamp': datetime.now().isoformat()
                        })

                        pruned_count += 1
                        self.discovery_stats['total_pruned'] += 1

                        logger.info(f"🗑️  Pruned underperforming whale: {address[:10]}...")

                logger.info(f"Pruning cycle complete: {pruned_count} whales pruned")

                # Sleep until next pruning cycle
                await asyncio.sleep(self.config.pruning_interval_seconds)

            except Exception as e:
                logger.error(f"Error in pruning loop: {e}", exc_info=True)
                await asyncio.sleep(3600)  # Wait 1 hour before retry

    async def _check_if_should_prune(self, address: str) -> bool:
        """
        Check if a whale should be pruned.

        Criteria:
        1. PSR drops below threshold
        2. DSR becomes negative
        3. Changepoint detected (structural break in returns)
        """
        # Placeholder - would fetch recent trade data from database
        # For now, return False (no pruning)
        return False

    def _calculate_thompson_weight(self, address: str) -> float:
        """
        Calculate Thompson Sampling allocation weight for a whale.

        Steps:
        1. Sample from each whale's Beta posterior
        2. Calculate proportion (allocation weight)
        """
        if address not in self.thompson_state:
            return 0.0

        # Sample from all whales
        samples = {
            addr: state.sample_probability()
            for addr, state in self.thompson_state.items()
        }

        # Normalize to get weights
        total_samples = sum(samples.values())
        weight = samples[address] / total_samples if total_samples > 0 else 0.0

        return weight

    async def fetch_whale_candidates(self) -> List[WhaleCandidate]:
        """
        Fetch whale candidates from Polymarket subgraphs.

        Queries:
        1. PNL Subgraph: Users with realized PnL > $10k
        2. Positions Subgraph: Users with total volume > $100k
        3. Activity Subgraph: Users with recent trades (last 30 days)

        Returns:
            List of WhaleCandidate objects
        """
        # Placeholder - would use GraphQL queries to Polymarket subgraphs
        # For now, return empty list
        logger.debug("Fetching whale candidates from Polymarket subgraphs...")
        return []

    def _candidate_to_whale_data(self, candidate: WhaleCandidate) -> Dict:
        """Convert WhaleCandidate to whale_data dict for scorer"""
        return {
            'address': candidate.address,
            'volume_30d': candidate.total_volume_usd,
            'total_value': candidate.realized_pnl_usd,
            'realized_pnl': candidate.realized_pnl_usd,
            'roi': candidate.win_rate,  # Simplified
            'total_trades': candidate.total_trades
        }

    def _extract_returns(self, trade_history: List[Dict]) -> np.ndarray:
        """Extract returns array from trade history"""
        if not trade_history:
            return np.array([])

        returns = [trade.get('pnl_pct', 0.0) for trade in trade_history]
        return np.array(returns)

    def _extract_returns_series(self, trade_history: List[Dict]) -> List:
        """Extract (timestamp, return) tuples from trade history"""
        if not trade_history:
            return []

        return [
            (trade.get('timestamp', datetime.now()), trade.get('pnl_pct', 0.0))
            for trade in trade_history
        ]

    def _publish_event(self, event_type: str, payload: Dict):
        """
        Publish event to message bus.

        In production, this would use Kafka producer.
        For now, appends to in-memory queue.
        """
        event = {
            'event_type': event_type,
            'payload': payload,
            'agent': 'WhaleDiscoveryAgent',
            'timestamp': datetime.now().isoformat()
        }

        self.message_queue.append(event)
        logger.debug(f"Published event: {event_type}")

    def get_top_whales(self, top_n: int = 10) -> List[Dict]:
        """
        Get top-ranked whales with Thompson Sampling weights.

        Returns:
            List of whale data with scores and allocation weights
        """
        # Rank whales
        ranked_scores = self.scorer.rank_whales(list(self.discovered_whales.values()))

        # Add Thompson weights
        top_whales = []
        for score in ranked_scores[:top_n]:
            whale_data = {
                'address': score.address,
                'rank': score.rank,
                'score': score.score,
                'percentile': score.percentile,
                'thompson_weight': self._calculate_thompson_weight(score.address),
                'dsr': self.skill_test_results[score.address].deflated_sharpe_ratio,
                'psr': self.skill_test_results[score.address].probabilistic_sharpe_ratio
            }
            top_whales.append(whale_data)

        return top_whales


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def main():
        # Initialize agent
        agent = WhaleDiscoveryAgent()

        # Start both loops concurrently
        await asyncio.gather(
            agent.discovery_loop(),
            agent.pruning_loop()
        )

    # Run
    asyncio.run(main())

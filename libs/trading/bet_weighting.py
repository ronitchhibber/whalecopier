"""
Comprehensive Bet Weighting System for Real Trading

This module implements sophisticated position sizing for whale copy trading:
- Kelly Criterion with safety factors
- Multi-factor weighting (whale quality, market liquidity, confidence)
- Risk management constraints
- Portfolio-level optimization
- Real-time market condition adjustment

Key Features:
1. Fractional Kelly (default 25% Kelly for safety)
2. Whale quality scoring (0-100 scale)
3. Market liquidity adjustment
4. Correlation-aware position sizing
5. Dynamic risk limits
6. Circuit breakers
"""

from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime
import math


@dataclass
class WhaleProfile:
    """Whale trader profile for weighting calculations"""
    address: str
    quality_score: float  # 0-100
    sharpe_ratio: float
    win_rate: float  # 0-100
    total_pnl: float
    total_volume: float
    total_trades: int
    avg_position_size: float
    consistency_score: float  # 0-100
    recent_performance: float  # Recent ROI


@dataclass
class MarketContext:
    """Market context for position sizing"""
    market_id: str
    title: str
    liquidity: float  # Total liquidity in USD
    spread: float  # Bid-ask spread
    volatility: float  # Historical volatility
    current_price: float
    category: str  # sports, politics, crypto, etc.
    time_to_close: int  # Hours until market closes


@dataclass
class PortfolioState:
    """Current portfolio state"""
    total_balance: float
    available_balance: float
    open_positions: int
    total_exposure: float  # Sum of all position values
    unrealized_pnl: float
    daily_pnl: float
    positions_by_market: Dict[str, float]
    positions_by_category: Dict[str, float]


@dataclass
class BetWeight:
    """Calculated bet weight with breakdown"""
    position_size_usd: float
    position_pct: float  # % of portfolio
    confidence_score: float  # 0-100

    # Weight components
    base_weight: float
    whale_quality_multiplier: float
    market_liquidity_multiplier: float
    risk_adjustment_multiplier: float
    portfolio_constraint_multiplier: float

    # Metadata
    reasoning: str
    warnings: List[str]



class BetWeightingEngine:
    """
    Comprehensive bet weighting engine for whale copy trading.

    Implements multi-factor position sizing with robust risk management.
    """

    def __init__(
        self,
        base_position_pct: float = 0.05,  # 5% base position
        max_position_pct: float = 0.10,   # 10% max position
        kelly_fraction: float = 0.25,      # Use 25% of Kelly bet
        min_whale_quality: float = 70.0,   # Minimum quality score
        min_position_size: float = 50.0,   # Minimum $50 bet
        max_position_size: float = 1000.0, # Maximum $1000 bet
        max_total_exposure: float = 0.80,  # Max 80% portfolio exposure
        max_positions: int = 1000,         # Max concurrent positions (effectively unlimited)
        max_per_market: float = 0.20,      # Max 20% per single market
        max_per_category: float = 0.40,    # Max 40% per category
        min_liquidity: float = 10000.0,    # Min $10k market liquidity
        max_spread: float = 0.05,          # Max 5% spread
    ):
        self.base_position_pct = base_position_pct
        self.max_position_pct = max_position_pct
        self.kelly_fraction = kelly_fraction
        self.min_whale_quality = min_whale_quality
        self.min_position_size = min_position_size
        self.max_position_size = max_position_size
        self.max_total_exposure = max_total_exposure
        self.max_positions = max_positions
        self.max_per_market = max_per_market
        self.max_per_category = max_per_category
        self.min_liquidity = min_liquidity
        self.max_spread = max_spread

    def calculate_bet_weight(
        self,
        whale: WhaleProfile,
        market: MarketContext,
        portfolio: PortfolioState,
        entry_price: float,
    ) -> BetWeight:
        """
        Calculate optimal bet size using multi-factor weighting.

        Process:
        1. Calculate base Kelly position
        2. Apply whale quality multiplier
        3. Apply market quality multiplier
        4. Apply risk adjustments
        5. Apply portfolio constraints
        6. Validate and cap final size
        """

        warnings = []

        # Step 1: Calculate base position using fractional Kelly
        kelly_size = self._calculate_kelly_size(whale, entry_price)
        base_weight = kelly_size * self.kelly_fraction
        base_position_usd = portfolio.total_balance * base_weight

        # Step 2: Whale quality multiplier (0.5x to 2.0x)
        whale_multiplier = self._calculate_whale_multiplier(whale, warnings)

        # Step 3: Market quality multiplier (0.5x to 1.5x)
        market_multiplier = self._calculate_market_multiplier(market, warnings)

        # Step 4: Risk adjustment multiplier (0x to 1.0x)
        risk_multiplier = self._calculate_risk_multiplier(
            whale, market, portfolio, warnings
        )

        # Step 5: Portfolio constraint multiplier (0x to 1.0x)
        portfolio_multiplier = self._calculate_portfolio_multiplier(
            market, portfolio, warnings
        )

        # Calculate final position size
        total_multiplier = (
            whale_multiplier *
            market_multiplier *
            risk_multiplier *
            portfolio_multiplier
        )

        position_size_usd = base_position_usd * total_multiplier

        # Apply absolute limits
        position_size_usd = max(position_size_usd, self.min_position_size)
        position_size_usd = min(position_size_usd, self.max_position_size)
        position_size_usd = min(position_size_usd, portfolio.available_balance)

        position_pct = position_size_usd / portfolio.total_balance if portfolio.total_balance > 0 else 0

        # Calculate confidence score
        confidence_score = self._calculate_confidence_score(
            whale, market, total_multiplier
        )

        # Generate reasoning
        reasoning = self._generate_reasoning(
            base_position_usd, position_size_usd, whale, market,
            whale_multiplier, market_multiplier, risk_multiplier, portfolio_multiplier
        )

        # Final validation
        if position_size_usd < self.min_position_size:
            warnings.append(f"Position size ${position_size_usd:.2f} below minimum ${self.min_position_size}")

        if whale.quality_score < self.min_whale_quality:
            warnings.append(f"Whale quality {whale.quality_score:.1f} below minimum {self.min_whale_quality}")

        return BetWeight(
            position_size_usd=position_size_usd,
            position_pct=position_pct,
            confidence_score=confidence_score,
            base_weight=base_weight,
            whale_quality_multiplier=whale_multiplier,
            market_liquidity_multiplier=market_multiplier,
            risk_adjustment_multiplier=risk_multiplier,
            portfolio_constraint_multiplier=portfolio_multiplier,
            reasoning=reasoning,
            warnings=warnings
        )

    def _calculate_kelly_size(self, whale: WhaleProfile, price: float) -> float:
        """
        Calculate Kelly Criterion bet size.

        Kelly% = (p * b - q) / b
        where:
        - p = win probability (whale win rate)
        - q = loss probability (1 - p)
        - b = odds (payout ratio)
        """
        p = whale.win_rate / 100.0
        q = 1.0 - p

        # Calculate implied odds from price
        # For binary outcome at price p: win = (1-p)/p, lose = 1
        b = (1.0 - price) / price if price > 0 and price < 1 else 1.0

        # Kelly formula
        kelly = (p * b - q) / b if b > 0 else 0.0

        # Ensure non-negative
        kelly = max(0.0, kelly)

        # Cap at base position to avoid extreme Kelly values
        kelly = min(kelly, self.base_position_pct * 2)

        return kelly

    def _calculate_whale_multiplier(
        self, whale: WhaleProfile, warnings: List[str]
    ) -> float:
        """
        Calculate whale quality multiplier (0.5x to 2.0x).

        Factors:
        - Quality score (primary)
        - Sharpe ratio
        - Win rate
        - Consistency
        - Recent performance
        """

        # Quality score component (0.5x to 1.5x)
        quality_component = 0.5 + (whale.quality_score / 100.0)

        # Sharpe component (0x to 0.3x bonus)
        sharpe_component = min(whale.sharpe_ratio / 10.0, 0.3) if whale.sharpe_ratio > 0 else 0

        # Win rate component (0x to 0.2x bonus for >60% win rate)
        win_rate_component = max(0, (whale.win_rate - 60.0) / 100.0) * 0.5

        # Recent performance component (-0.2x to +0.2x)
        recent_component = whale.recent_performance * 0.001  # Scale down
        recent_component = max(-0.2, min(0.2, recent_component))

        multiplier = quality_component + sharpe_component + win_rate_component + recent_component

        # Cap between 0.5x and 2.0x
        multiplier = max(0.5, min(2.0, multiplier))

        if multiplier < 0.8:
            warnings.append(f"Low whale quality multiplier: {multiplier:.2f}x")

        return multiplier

    def _calculate_market_multiplier(
        self, market: MarketContext, warnings: List[str]
    ) -> float:
        """
        Calculate market quality multiplier (0.5x to 1.5x).

        Factors:
        - Liquidity (higher is better)
        - Spread (lower is better)
        - Time to close (more time = lower risk)
        """

        # Liquidity component (0.5x to 1.2x)
        if market.liquidity < self.min_liquidity:
            liquidity_component = 0.5
            warnings.append(f"Low liquidity: ${market.liquidity:,.0f}")
        else:
            # Scale from min_liquidity to 100k (full 1.2x)
            liquidity_ratio = min(market.liquidity / 100000.0, 1.0)
            liquidity_component = 0.7 + (liquidity_ratio * 0.5)

        # Spread component (0x to 0.2x penalty)
        spread_penalty = min(market.spread / self.max_spread, 1.0) * 0.2
        if market.spread > self.max_spread:
            warnings.append(f"Wide spread: {market.spread*100:.1f}%")

        # Time component (0x to 0.1x bonus for >48 hours)
        time_bonus = min(market.time_to_close / (48.0 * 24), 0.1)

        multiplier = liquidity_component - spread_penalty + time_bonus

        # Cap between 0.5x and 1.5x
        multiplier = max(0.5, min(1.5, multiplier))

        return multiplier

    def _calculate_risk_multiplier(
        self,
        whale: WhaleProfile,
        market: MarketContext,
        portfolio: PortfolioState,
        warnings: List[str]
    ) -> float:
        """
        Calculate risk adjustment multiplier (0x to 1.0x).

        Reduces position size based on:
        - Current drawdown
        - Daily losses
        - Market volatility
        - Concentration risk
        """

        multiplier = 1.0

        # Drawdown adjustment (reduce if portfolio down)
        if portfolio.unrealized_pnl < 0:
            drawdown_pct = abs(portfolio.unrealized_pnl) / portfolio.total_balance
            if drawdown_pct > 0.1:  # More than 10% drawdown
                multiplier *= (1.0 - min(drawdown_pct, 0.5))
                warnings.append(f"Portfolio drawdown: {drawdown_pct*100:.1f}%")

        # Daily loss adjustment (reduce if losing today)
        if portfolio.daily_pnl < 0:
            daily_loss_pct = abs(portfolio.daily_pnl) / portfolio.total_balance
            if daily_loss_pct > 0.05:  # More than 5% daily loss
                multiplier *= (1.0 - min(daily_loss_pct * 2, 0.5))
                warnings.append(f"Daily loss: {daily_loss_pct*100:.1f}%")

        # Volatility adjustment (reduce for high volatility)
        if market.volatility > 0.3:  # High volatility
            vol_penalty = min((market.volatility - 0.3) * 2, 0.3)
            multiplier *= (1.0 - vol_penalty)
            warnings.append(f"High volatility: {market.volatility*100:.1f}%")

        # Position count adjustment (reduce if many positions)
        if portfolio.open_positions > self.max_positions * 0.75:
            count_penalty = (portfolio.open_positions - self.max_positions * 0.75) / (self.max_positions * 0.25)
            multiplier *= (1.0 - min(count_penalty * 0.3, 0.3))
            warnings.append(f"High position count: {portfolio.open_positions}")

        return max(0.0, multiplier)

    def _calculate_portfolio_multiplier(
        self,
        market: MarketContext,
        portfolio: PortfolioState,
        warnings: List[str]
    ) -> float:
        """
        Calculate portfolio constraint multiplier (0x to 1.0x).

        Enforces:
        - Max total exposure
        - Max per market
        - Max per category
        - Max positions
        """

        multiplier = 1.0

        # Total exposure constraint
        exposure_ratio = portfolio.total_exposure / portfolio.total_balance
        if exposure_ratio > self.max_total_exposure * 0.9:
            exposure_penalty = (exposure_ratio - self.max_total_exposure * 0.9) / (self.max_total_exposure * 0.1)
            multiplier *= (1.0 - min(exposure_penalty, 0.8))
            warnings.append(f"High total exposure: {exposure_ratio*100:.1f}%")

        # Per-market constraint
        market_exposure = portfolio.positions_by_market.get(market.market_id, 0)
        market_ratio = market_exposure / portfolio.total_balance
        if market_ratio > self.max_per_market * 0.8:
            market_penalty = (market_ratio - self.max_per_market * 0.8) / (self.max_per_market * 0.2)
            multiplier *= (1.0 - min(market_penalty, 0.9))
            warnings.append(f"High market exposure: {market_ratio*100:.1f}%")

        # Per-category constraint
        category_exposure = portfolio.positions_by_category.get(market.category, 0)
        category_ratio = category_exposure / portfolio.total_balance
        if category_ratio > self.max_per_category * 0.8:
            category_penalty = (category_ratio - self.max_per_category * 0.8) / (self.max_per_category * 0.2)
            multiplier *= (1.0 - min(category_penalty, 0.7))
            warnings.append(f"High {market.category} exposure: {category_ratio*100:.1f}%")

        # Position count constraint
        if portfolio.open_positions >= self.max_positions:
            multiplier = 0.0
            warnings.append(f"Max positions reached: {portfolio.open_positions}/{self.max_positions}")

        return max(0.0, multiplier)

    def _calculate_confidence_score(
        self, whale: WhaleProfile, market: MarketContext, total_multiplier: float
    ) -> float:
        """Calculate overall confidence score (0-100)"""

        # Whale confidence (0-50)
        whale_confidence = whale.quality_score * 0.5

        # Market confidence (0-30)
        liquidity_score = min(market.liquidity / 50000.0, 1.0) * 15
        spread_score = max(0, (1.0 - market.spread / 0.05)) * 15
        market_confidence = liquidity_score + spread_score

        # Multiplier confidence (0-20)
        multiplier_confidence = total_multiplier * 10  # Assume max 2x multiplier

        total_confidence = whale_confidence + market_confidence + multiplier_confidence

        return min(100.0, total_confidence)

    def _generate_reasoning(
        self,
        base_position: float,
        final_position: float,
        whale: WhaleProfile,
        market: MarketContext,
        whale_mult: float,
        market_mult: float,
        risk_mult: float,
        portfolio_mult: float
    ) -> str:
        """Generate human-readable reasoning for the bet size"""

        reasoning_parts = []

        reasoning_parts.append(f"Base Kelly position: ${base_position:.2f}")

        if whale_mult > 1.1:
            reasoning_parts.append(f"↑ High whale quality ({whale.quality_score:.0f}/100): {whale_mult:.2f}x")
        elif whale_mult < 0.9:
            reasoning_parts.append(f"↓ Lower whale quality ({whale.quality_score:.0f}/100): {whale_mult:.2f}x")

        if market_mult > 1.1:
            reasoning_parts.append(f"↑ Good market conditions (liq: ${market.liquidity:,.0f}): {market_mult:.2f}x")
        elif market_mult < 0.9:
            reasoning_parts.append(f"↓ Suboptimal market conditions: {market_mult:.2f}x")

        if risk_mult < 0.9:
            reasoning_parts.append(f"↓ Risk reduction applied: {risk_mult:.2f}x")

        if portfolio_mult < 0.9:
            reasoning_parts.append(f"↓ Portfolio constraints applied: {portfolio_mult:.2f}x")

        reasoning_parts.append(f"Final position: ${final_position:.2f}")

        return " | ".join(reasoning_parts)

    def validate_trade(
        self,
        bet_weight: BetWeight,
        portfolio: PortfolioState
    ) -> Tuple[bool, List[str]]:
        """
        Validate if trade should be executed.

        Returns: (should_execute, reasons)
        """

        issues = []

        # Check minimum position size
        if bet_weight.position_size_usd < self.min_position_size:
            issues.append(f"Position too small: ${bet_weight.position_size_usd:.2f} < ${self.min_position_size}")

        # Check available balance
        if bet_weight.position_size_usd > portfolio.available_balance:
            issues.append(f"Insufficient balance: ${bet_weight.position_size_usd:.2f} > ${portfolio.available_balance:.2f}")

        # Check confidence
        if bet_weight.confidence_score < 40:
            issues.append(f"Low confidence: {bet_weight.confidence_score:.0f}/100")

        # Check max positions
        if portfolio.open_positions >= self.max_positions:
            issues.append(f"Max positions: {portfolio.open_positions}/{self.max_positions}")

        should_execute = len(issues) == 0

        return should_execute, issues

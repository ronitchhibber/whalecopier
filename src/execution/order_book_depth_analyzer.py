"""
Order Book Depth Analyzer
Week 7: Slippage & Execution Optimization - Order Book Analysis
Analyzes order book depth and estimates slippage before trade execution
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


# ==================== Data Structures ====================

class SlippageRating(Enum):
    """Slippage severity rating"""
    EXCELLENT = "EXCELLENT"      # <0.5% slippage
    GOOD = "GOOD"                # 0.5-1% slippage
    ACCEPTABLE = "ACCEPTABLE"    # 1-2% slippage
    POOR = "POOR"                # 2-5% slippage
    CRITICAL = "CRITICAL"        # >5% slippage


class OrderType(Enum):
    """Order execution type"""
    LIMIT = "LIMIT"              # Limit order (post-only)
    MARKET = "MARKET"            # Market order (immediate fill)


@dataclass
class OrderBookLevel:
    """Single level in order book"""
    price: Decimal
    size: Decimal
    cumulative_size: Decimal


@dataclass
class OrderBookSnapshot:
    """Complete order book snapshot"""
    market_id: str
    timestamp: datetime

    # Bids (buy orders) - highest price first
    bids: List[OrderBookLevel]

    # Asks (sell orders) - lowest price first
    asks: List[OrderBookLevel]

    # Best bid/ask
    best_bid: Decimal
    best_ask: Decimal
    spread: Decimal
    spread_pct: Decimal

    # Depth metrics
    bid_depth: Decimal  # Total $ on buy side
    ask_depth: Decimal  # Total $ on sell side


@dataclass
class SlippageEstimate:
    """Estimated slippage for a trade"""
    market_id: str
    side: str  # "buy" or "sell"
    order_size_usd: Decimal

    # Price estimates
    best_price: Decimal           # Best available price (top of book)
    avg_fill_price: Decimal       # Expected average fill price
    worst_fill_price: Decimal     # Price of last filled level

    # Slippage metrics
    slippage_usd: Decimal         # Dollar slippage
    slippage_pct: Decimal         # Percentage slippage
    slippage_rating: SlippageRating

    # Depth analysis
    total_liquidity: Decimal      # Total liquidity available
    liquidity_pct_used: Decimal   # % of available liquidity consumed
    levels_consumed: int          # Number of order book levels needed

    # Recommendation
    recommended_order_type: OrderType
    should_skip: bool
    skip_reason: Optional[str]

    # Order book snapshot
    book_snapshot: OrderBookSnapshot
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class DepthAnalysisConfig:
    """Configuration for depth analysis"""
    # Slippage thresholds
    max_slippage_limit_order: Decimal = Decimal("0.02")    # 2% max for limit orders
    max_slippage_market_order: Decimal = Decimal("0.05")   # 5% max for market orders

    # Liquidity thresholds
    max_liquidity_consumption: Decimal = Decimal("0.30")   # Max 30% of available liquidity
    min_levels_for_confidence: int = 3                     # Need 3+ levels for confidence

    # Spread thresholds
    max_spread_pct: Decimal = Decimal("0.02")              # 2% max spread

    # Size thresholds
    large_order_threshold: Decimal = Decimal("1000")       # $1,000+ is "large"


# ==================== Order Book Depth Analyzer ====================

class OrderBookDepthAnalyzer:
    """
    Order Book Depth Analyzer

    Analyzes order book depth and estimates slippage before executing trades.

    Key Features:
    1. **Depth Analysis:** Calculate total liquidity at various price levels
    2. **Slippage Estimation:** Predict price impact before execution
    3. **Skip Detection:** Block trades with excessive slippage (>2% limit, >5% market)
    4. **Order Type Recommendation:** Suggest limit vs market based on conditions

    Slippage Calculation:
    - Simulates filling the order against the book
    - Calculates volume-weighted average price (VWAP)
    - Compares VWAP to best available price

    Example:
    ```
    Buy $500 worth at market:
    - Best ask: $0.50
    - Level 1: $0.50 x 200 = $100
    - Level 2: $0.51 x 400 = $204
    - Level 3: $0.52 x 400 = $208
    - Total filled: $500
    - VWAP: $0.5104
    - Slippage: (0.5104 - 0.50) / 0.50 = 2.08%
    ```
    """

    def __init__(self, config: Optional[DepthAnalysisConfig] = None):
        """
        Initialize depth analyzer

        Args:
            config: Depth analysis configuration
        """
        self.config = config or DepthAnalysisConfig()

        # Statistics
        self.total_analyses = 0
        self.skipped_trades = 0
        self.high_slippage_count = 0
        self.insufficient_liquidity_count = 0

        logger.info(
            f"OrderBookDepthAnalyzer initialized: "
            f"max_slippage_limit={float(self.config.max_slippage_limit_order)*100:.1f}%, "
            f"max_slippage_market={float(self.config.max_slippage_market_order)*100:.1f}%"
        )

    def analyze_order_book(
        self,
        market_id: str,
        order_book_data: Dict,
        side: str,
        order_size_usd: Decimal,
        prefer_limit_order: bool = True
    ) -> SlippageEstimate:
        """
        Analyze order book and estimate slippage

        Args:
            market_id: Market identifier
            order_book_data: Order book data (bids/asks with price/size)
            side: "buy" or "sell"
            order_size_usd: Order size in USD
            prefer_limit_order: Prefer limit orders when possible

        Returns:
            SlippageEstimate with analysis and recommendation
        """
        self.total_analyses += 1

        # Parse order book
        book_snapshot = self._parse_order_book(market_id, order_book_data)

        # Determine which side of book to analyze
        if side == "buy":
            # Buying = consuming asks (sell orders)
            levels = book_snapshot.asks
            best_price = book_snapshot.best_ask
            total_liquidity = book_snapshot.ask_depth
        else:
            # Selling = consuming bids (buy orders)
            levels = book_snapshot.bids
            best_price = book_snapshot.best_bid
            total_liquidity = book_snapshot.bid_depth

        # Check if we have sufficient liquidity
        if total_liquidity < order_size_usd:
            self.insufficient_liquidity_count += 1
            return self._create_skip_estimate(
                market_id=market_id,
                side=side,
                order_size_usd=order_size_usd,
                best_price=best_price,
                book_snapshot=book_snapshot,
                skip_reason=f"Insufficient liquidity: ${float(total_liquidity):,.2f} available, ${float(order_size_usd):,.2f} needed"
            )

        # Simulate filling the order
        avg_fill_price, worst_fill_price, levels_consumed = self._simulate_fill(
            levels=levels,
            order_size_usd=order_size_usd,
            side=side
        )

        # Calculate slippage
        if side == "buy":
            # Buying: higher price = worse
            slippage_pct = (avg_fill_price - best_price) / best_price
        else:
            # Selling: lower price = worse
            slippage_pct = (best_price - avg_fill_price) / best_price

        slippage_usd = abs(avg_fill_price - best_price) * (order_size_usd / avg_fill_price)

        # Calculate liquidity consumption
        liquidity_pct_used = order_size_usd / total_liquidity

        # Determine slippage rating
        slippage_rating = self._rate_slippage(slippage_pct)

        # Determine order type and skip logic
        should_skip = False
        skip_reason = None
        recommended_order_type = OrderType.LIMIT if prefer_limit_order else OrderType.MARKET

        # Check slippage thresholds
        if prefer_limit_order:
            if slippage_pct > self.config.max_slippage_limit_order:
                should_skip = True
                skip_reason = f"Slippage {float(slippage_pct)*100:.2f}% exceeds limit order threshold ({float(self.config.max_slippage_limit_order)*100:.1f}%)"
                self.skipped_trades += 1
                self.high_slippage_count += 1
        else:
            if slippage_pct > self.config.max_slippage_market_order:
                should_skip = True
                skip_reason = f"Slippage {float(slippage_pct)*100:.2f}% exceeds market order threshold ({float(self.config.max_slippage_market_order)*100:.1f}%)"
                self.skipped_trades += 1
                self.high_slippage_count += 1

        # Check liquidity consumption
        if liquidity_pct_used > self.config.max_liquidity_consumption:
            should_skip = True
            skip_reason = f"Would consume {float(liquidity_pct_used)*100:.1f}% of available liquidity (max {float(self.config.max_liquidity_consumption)*100:.0f}%)"
            self.skipped_trades += 1
            self.insufficient_liquidity_count += 1

        # Check spread
        if book_snapshot.spread_pct > self.config.max_spread_pct:
            logger.warning(
                f"Wide spread detected: {float(book_snapshot.spread_pct)*100:.2f}% "
                f"(max {float(self.config.max_spread_pct)*100:.1f}%)"
            )

        # Create estimate
        estimate = SlippageEstimate(
            market_id=market_id,
            side=side,
            order_size_usd=order_size_usd,
            best_price=best_price,
            avg_fill_price=avg_fill_price,
            worst_fill_price=worst_fill_price,
            slippage_usd=slippage_usd,
            slippage_pct=slippage_pct,
            slippage_rating=slippage_rating,
            total_liquidity=total_liquidity,
            liquidity_pct_used=liquidity_pct_used,
            levels_consumed=levels_consumed,
            recommended_order_type=recommended_order_type,
            should_skip=should_skip,
            skip_reason=skip_reason,
            book_snapshot=book_snapshot
        )

        logger.info(
            f"Analyzed {market_id} | Side: {side} | Size: ${float(order_size_usd):,.2f} | "
            f"Slippage: {float(slippage_pct)*100:.2f}% ({slippage_rating.value}) | "
            f"Skip: {should_skip}"
        )

        return estimate

    # ==================== Private Methods ====================

    def _parse_order_book(
        self,
        market_id: str,
        order_book_data: Dict
    ) -> OrderBookSnapshot:
        """Parse order book data into structured format"""
        # Parse bids (buy orders - highest price first)
        bids = []
        cumulative_bid_size = Decimal("0")
        for bid in order_book_data.get("bids", []):
            price = Decimal(str(bid["price"]))
            size = Decimal(str(bid["size"]))
            cumulative_bid_size += price * size

            bids.append(OrderBookLevel(
                price=price,
                size=size,
                cumulative_size=cumulative_bid_size
            ))

        # Parse asks (sell orders - lowest price first)
        asks = []
        cumulative_ask_size = Decimal("0")
        for ask in order_book_data.get("asks", []):
            price = Decimal(str(ask["price"]))
            size = Decimal(str(ask["size"]))
            cumulative_ask_size += price * size

            asks.append(OrderBookLevel(
                price=price,
                size=size,
                cumulative_size=cumulative_ask_size
            ))

        # Calculate best bid/ask
        best_bid = bids[0].price if bids else Decimal("0")
        best_ask = asks[0].price if asks else Decimal("1")

        spread = best_ask - best_bid
        mid_price = (best_bid + best_ask) / Decimal("2")
        spread_pct = spread / mid_price if mid_price > 0 else Decimal("0")

        return OrderBookSnapshot(
            market_id=market_id,
            timestamp=datetime.now(),
            bids=bids,
            asks=asks,
            best_bid=best_bid,
            best_ask=best_ask,
            spread=spread,
            spread_pct=spread_pct,
            bid_depth=cumulative_bid_size,
            ask_depth=cumulative_ask_size
        )

    def _simulate_fill(
        self,
        levels: List[OrderBookLevel],
        order_size_usd: Decimal,
        side: str
    ) -> Tuple[Decimal, Decimal, int]:
        """
        Simulate filling an order against the book

        Returns:
            (avg_fill_price, worst_fill_price, levels_consumed)
        """
        remaining_usd = order_size_usd
        total_shares = Decimal("0")
        total_cost = Decimal("0")
        levels_consumed = 0
        worst_price = Decimal("0")

        for level in levels:
            if remaining_usd <= 0:
                break

            # Calculate how much we can fill at this level
            level_value_usd = level.price * level.size
            fill_usd = min(remaining_usd, level_value_usd)

            # Calculate shares filled
            shares_filled = fill_usd / level.price

            # Update totals
            total_shares += shares_filled
            total_cost += fill_usd
            remaining_usd -= fill_usd
            levels_consumed += 1
            worst_price = level.price

        # Calculate volume-weighted average price
        avg_fill_price = total_cost / total_shares if total_shares > 0 else levels[0].price

        return avg_fill_price, worst_price, levels_consumed

    def _rate_slippage(self, slippage_pct: Decimal) -> SlippageRating:
        """Rate slippage severity"""
        abs_slippage = abs(slippage_pct)

        if abs_slippage < Decimal("0.005"):  # <0.5%
            return SlippageRating.EXCELLENT
        elif abs_slippage < Decimal("0.01"):  # <1%
            return SlippageRating.GOOD
        elif abs_slippage < Decimal("0.02"):  # <2%
            return SlippageRating.ACCEPTABLE
        elif abs_slippage < Decimal("0.05"):  # <5%
            return SlippageRating.POOR
        else:
            return SlippageRating.CRITICAL

    def _create_skip_estimate(
        self,
        market_id: str,
        side: str,
        order_size_usd: Decimal,
        best_price: Decimal,
        book_snapshot: OrderBookSnapshot,
        skip_reason: str
    ) -> SlippageEstimate:
        """Create a skip estimate for insufficient liquidity"""
        return SlippageEstimate(
            market_id=market_id,
            side=side,
            order_size_usd=order_size_usd,
            best_price=best_price,
            avg_fill_price=best_price,
            worst_fill_price=best_price,
            slippage_usd=Decimal("0"),
            slippage_pct=Decimal("0"),
            slippage_rating=SlippageRating.CRITICAL,
            total_liquidity=book_snapshot.ask_depth if side == "buy" else book_snapshot.bid_depth,
            liquidity_pct_used=Decimal("1.0"),
            levels_consumed=0,
            recommended_order_type=OrderType.LIMIT,
            should_skip=True,
            skip_reason=skip_reason,
            book_snapshot=book_snapshot
        )

    def get_statistics(self) -> Dict:
        """Get depth analyzer statistics"""
        skip_rate = (
            self.skipped_trades / self.total_analyses
            if self.total_analyses > 0 else 0
        )

        return {
            "total_analyses": self.total_analyses,
            "skipped_trades": {
                "count": self.skipped_trades,
                "rate": f"{skip_rate*100:.1f}%"
            },
            "skip_reasons": {
                "high_slippage": self.high_slippage_count,
                "insufficient_liquidity": self.insufficient_liquidity_count
            }
        }


# ==================== Example Usage ====================

def main():
    """Example usage of OrderBookDepthAnalyzer"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize analyzer
    analyzer = OrderBookDepthAnalyzer()

    print("\n=== Order Book Depth Analyzer Test ===\n")

    # Simulate order book data
    order_book = {
        "bids": [
            {"price": "0.49", "size": "500"},
            {"price": "0.48", "size": "1000"},
            {"price": "0.47", "size": "1500"},
        ],
        "asks": [
            {"price": "0.50", "size": "400"},
            {"price": "0.51", "size": "800"},
            {"price": "0.52", "size": "1000"},
            {"price": "0.53", "size": "1200"},
        ]
    }

    # Test 1: Small buy order (should be fine)
    print("=== Test 1: Small Buy Order ($100) ===")
    estimate1 = analyzer.analyze_order_book(
        market_id="test_market_1",
        order_book_data=order_book,
        side="buy",
        order_size_usd=Decimal("100")
    )
    print(f"Best Price: ${float(estimate1.best_price):.4f}")
    print(f"Avg Fill Price: ${float(estimate1.avg_fill_price):.4f}")
    print(f"Slippage: {float(estimate1.slippage_pct)*100:.2f}% ({estimate1.slippage_rating.value})")
    print(f"Should Skip: {estimate1.should_skip}\n")

    # Test 2: Medium buy order
    print("=== Test 2: Medium Buy Order ($500) ===")
    estimate2 = analyzer.analyze_order_book(
        market_id="test_market_2",
        order_book_data=order_book,
        side="buy",
        order_size_usd=Decimal("500")
    )
    print(f"Best Price: ${float(estimate2.best_price):.4f}")
    print(f"Avg Fill Price: ${float(estimate2.avg_fill_price):.4f}")
    print(f"Slippage: {float(estimate2.slippage_pct)*100:.2f}% ({estimate2.slippage_rating.value})")
    print(f"Liquidity Used: {float(estimate2.liquidity_pct_used)*100:.1f}%")
    print(f"Levels Consumed: {estimate2.levels_consumed}")
    print(f"Should Skip: {estimate2.should_skip}\n")

    # Test 3: Large buy order (should skip)
    print("=== Test 3: Large Buy Order ($2000) ===")
    estimate3 = analyzer.analyze_order_book(
        market_id="test_market_3",
        order_book_data=order_book,
        side="buy",
        order_size_usd=Decimal("2000")
    )
    print(f"Should Skip: {estimate3.should_skip}")
    if estimate3.should_skip:
        print(f"Skip Reason: {estimate3.skip_reason}\n")

    # Get statistics
    print("=== Analyzer Statistics ===")
    import json
    stats = analyzer.get_statistics()
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()

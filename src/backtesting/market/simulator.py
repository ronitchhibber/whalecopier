"""
Market Simulator with Order Book Dynamics
Provides realistic market microstructure simulation for backtesting
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import heapq
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class OrderType(Enum):
    """Order types supported by the simulator."""
    MARKET = "market"
    LIMIT = "limit"
    IOC = "ioc"  # Immediate or Cancel
    FOK = "fok"  # Fill or Kill
    POST_ONLY = "post_only"  # Maker only
    ICEBERG = "iceberg"  # Hidden quantity


class OrderSide(Enum):
    """Order sides."""
    BUY = "buy"
    SELL = "sell"


@dataclass
class Order:
    """Order in the order book."""
    order_id: str
    timestamp: datetime
    side: OrderSide
    price: float
    size: float
    order_type: OrderType
    trader_id: Optional[str] = None
    time_in_force: str = "GTC"  # Good Till Cancelled
    hidden_size: float = 0  # For iceberg orders
    post_only: bool = False

    def __lt__(self, other):
        """Priority for order matching."""
        if self.side == OrderSide.BUY:
            # Buy orders: Higher price = higher priority
            if self.price != other.price:
                return self.price > other.price
        else:
            # Sell orders: Lower price = higher priority
            if self.price != other.price:
                return self.price < other.price
        # Same price: Earlier timestamp = higher priority (FIFO)
        return self.timestamp < other.timestamp


@dataclass
class Trade:
    """Executed trade."""
    trade_id: str
    timestamp: datetime
    price: float
    size: float
    buyer_id: str
    seller_id: str
    taker_side: OrderSide
    market_impact: float = 0.0


class OrderBook:
    """
    Limit Order Book with realistic dynamics.

    Features:
    - Price-time priority matching
    - Multiple order types
    - Market impact modeling
    - Spread dynamics
    - Queue position tracking
    """

    def __init__(self, market_id: str, tick_size: float = 0.001):
        self.market_id = market_id
        self.tick_size = tick_size

        # Order book sides
        self.bids: List[Order] = []  # Buy orders (max heap by price)
        self.asks: List[Order] = []  # Sell orders (min heap by price)

        # Order tracking
        self.orders: Dict[str, Order] = {}
        self.order_count = 0

        # Market state
        self.last_price = 0.5  # Initialize at midpoint
        self.last_trade_time = None
        self.total_volume = 0

        # Spread dynamics
        self.base_spread = 0.002  # 20 bps base spread
        self.spread_volatility = 0.0005

        # Market impact parameters
        self.permanent_impact = 0.1  # Kyle's lambda
        self.temporary_impact = 0.05
        self.impact_decay = 0.95  # Per minute

        # Statistics
        self.trades: List[Trade] = []
        self.depth_snapshots: List[Dict] = []

    def add_order(self, order: Order) -> Dict:
        """
        Add order to book and potentially match.

        Returns:
            Execution result with fills
        """
        self.order_count += 1
        order.order_id = f"{self.market_id}_{self.order_count}"

        # Check for immediate execution
        if order.order_type == OrderType.MARKET:
            return self._execute_market_order(order)
        elif order.order_type == OrderType.LIMIT:
            return self._execute_limit_order(order)
        elif order.order_type == OrderType.IOC:
            return self._execute_ioc_order(order)
        elif order.order_type == OrderType.FOK:
            return self._execute_fok_order(order)
        elif order.order_type == OrderType.POST_ONLY:
            return self._add_post_only_order(order)
        else:
            return {"status": "rejected", "reason": "Unknown order type"}

    def _execute_market_order(self, order: Order) -> Dict:
        """Execute market order immediately."""
        fills = []
        remaining_size = order.size

        # Get opposite side book
        opposite_book = self.asks if order.side == OrderSide.BUY else self.bids

        while remaining_size > 0 and opposite_book:
            best_order = heapq.heappop(opposite_book)

            # Calculate fill
            fill_size = min(remaining_size, best_order.size)
            fill_price = best_order.price

            # Apply market impact
            impact = self._calculate_market_impact(fill_size, order.side)
            fill_price = fill_price * (1 + impact) if order.side == OrderSide.BUY else fill_price * (1 - impact)

            # Record fill
            fills.append({
                "price": fill_price,
                "size": fill_size,
                "timestamp": order.timestamp,
                "impact": impact
            })

            # Update orders
            remaining_size -= fill_size
            best_order.size -= fill_size

            # Add back if partially filled
            if best_order.size > 0:
                heapq.heappush(opposite_book, best_order)
            else:
                del self.orders[best_order.order_id]

            # Record trade
            self._record_trade(
                price=fill_price,
                size=fill_size,
                buyer_id=order.trader_id if order.side == OrderSide.BUY else best_order.trader_id,
                seller_id=best_order.trader_id if order.side == OrderSide.BUY else order.trader_id,
                taker_side=order.side,
                timestamp=order.timestamp
            )

        if fills:
            avg_price = sum(f["price"] * f["size"] for f in fills) / sum(f["size"] for f in fills)
            return {
                "status": "filled",
                "fills": fills,
                "average_price": avg_price,
                "total_size": sum(f["size"] for f in fills),
                "unfilled": remaining_size
            }
        else:
            return {
                "status": "rejected",
                "reason": "No liquidity",
                "unfilled": remaining_size
            }

    def _execute_limit_order(self, order: Order) -> Dict:
        """Execute limit order with price-time priority."""
        fills = []
        remaining_size = order.size

        # Check for crossing orders
        if order.side == OrderSide.BUY:
            # Buy order: check if it crosses with any asks
            while remaining_size > 0 and self.asks:
                best_ask = self.asks[0]
                if order.price >= best_ask.price:
                    # Can fill
                    best_ask = heapq.heappop(self.asks)
                    fill_size = min(remaining_size, best_ask.size)

                    fills.append({
                        "price": best_ask.price,
                        "size": fill_size,
                        "timestamp": order.timestamp
                    })

                    remaining_size -= fill_size
                    best_ask.size -= fill_size

                    if best_ask.size > 0:
                        heapq.heappush(self.asks, best_ask)

                    self._record_trade(
                        price=best_ask.price,
                        size=fill_size,
                        buyer_id=order.trader_id,
                        seller_id=best_ask.trader_id,
                        taker_side=OrderSide.BUY,
                        timestamp=order.timestamp
                    )
                else:
                    break
        else:
            # Sell order: check if it crosses with any bids
            while remaining_size > 0 and self.bids:
                best_bid = self.bids[0]
                if order.price <= best_bid.price:
                    # Can fill
                    best_bid = heapq.heappop(self.bids)
                    fill_size = min(remaining_size, best_bid.size)

                    fills.append({
                        "price": best_bid.price,
                        "size": fill_size,
                        "timestamp": order.timestamp
                    })

                    remaining_size -= fill_size
                    best_bid.size -= fill_size

                    if best_bid.size > 0:
                        heapq.heappush(self.bids, best_bid)

                    self._record_trade(
                        price=best_bid.price,
                        size=fill_size,
                        buyer_id=best_bid.trader_id,
                        seller_id=order.trader_id,
                        taker_side=OrderSide.SELL,
                        timestamp=order.timestamp
                    )
                else:
                    break

        # Add remaining to book if not fully filled
        if remaining_size > 0:
            order.size = remaining_size
            self.orders[order.order_id] = order

            if order.side == OrderSide.BUY:
                heapq.heappush(self.bids, order)
            else:
                heapq.heappush(self.asks, order)

        if fills:
            return {
                "status": "filled" if remaining_size == 0 else "partial",
                "fills": fills,
                "remaining": remaining_size
            }
        else:
            return {
                "status": "accepted",
                "order_id": order.order_id,
                "remaining": remaining_size
            }

    def _execute_ioc_order(self, order: Order) -> Dict:
        """Execute IOC order - fill immediately or cancel."""
        result = self._execute_limit_order(order)

        # Cancel any unfilled portion
        if result.get("remaining", 0) > 0:
            self.cancel_order(order.order_id)
            result["status"] = "partial_fill_cancelled"

        return result

    def _execute_fok_order(self, order: Order) -> Dict:
        """Execute FOK order - fill completely or cancel."""
        # Check if full size can be filled
        available_liquidity = self._check_liquidity(order.side, order.price)

        if available_liquidity >= order.size:
            return self._execute_limit_order(order)
        else:
            return {
                "status": "rejected",
                "reason": "Insufficient liquidity for FOK"
            }

    def _add_post_only_order(self, order: Order) -> Dict:
        """Add post-only order (maker only)."""
        # Check if order would cross the spread
        if order.side == OrderSide.BUY:
            if self.asks and order.price >= self.asks[0].price:
                return {
                    "status": "rejected",
                    "reason": "Post-only order would cross spread"
                }
        else:
            if self.bids and order.price <= self.bids[0].price:
                return {
                    "status": "rejected",
                    "reason": "Post-only order would cross spread"
                }

        # Add to book as maker order
        order.post_only = True
        self.orders[order.order_id] = order

        if order.side == OrderSide.BUY:
            heapq.heappush(self.bids, order)
        else:
            heapq.heappush(self.asks, order)

        return {
            "status": "accepted",
            "order_id": order.order_id,
            "post_only": True
        }

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        if order_id not in self.orders:
            return False

        order = self.orders[order_id]
        del self.orders[order_id]

        # Remove from book
        if order.side == OrderSide.BUY:
            self.bids = [o for o in self.bids if o.order_id != order_id]
            heapq.heapify(self.bids)
        else:
            self.asks = [o for o in self.asks if o.order_id != order_id]
            heapq.heapify(self.asks)

        return True

    def _calculate_market_impact(self, size: float, side: OrderSide) -> float:
        """
        Calculate market impact using square-root model.

        Impact = λ * σ * √(V/ADV)
        where:
        - λ = impact coefficient
        - σ = volatility
        - V = trade size
        - ADV = average daily volume
        """
        # Estimate based on order book imbalance
        total_bid_size = sum(o.size for o in self.bids[:10]) if self.bids else 1
        total_ask_size = sum(o.size for o in self.asks[:10]) if self.asks else 1

        imbalance = (total_bid_size - total_ask_size) / (total_bid_size + total_ask_size)

        # Temporary impact (reverts over time)
        temp_impact = self.temporary_impact * np.sqrt(size / 10000)  # Normalize by typical size

        # Permanent impact (shifts price)
        perm_impact = self.permanent_impact * size / 100000

        # Adjust for order flow imbalance
        if side == OrderSide.BUY:
            impact = temp_impact + perm_impact + max(0, imbalance * 0.001)
        else:
            impact = temp_impact + perm_impact + max(0, -imbalance * 0.001)

        return min(impact, 0.01)  # Cap at 1%

    def _check_liquidity(self, side: OrderSide, price: float) -> float:
        """Check available liquidity at or better than price."""
        total_liquidity = 0

        if side == OrderSide.BUY:
            for order in self.asks:
                if order.price <= price:
                    total_liquidity += order.size
                else:
                    break
        else:
            for order in self.bids:
                if order.price >= price:
                    total_liquidity += order.size
                else:
                    break

        return total_liquidity

    def _record_trade(self, price: float, size: float, buyer_id: str,
                     seller_id: str, taker_side: OrderSide, timestamp: datetime):
        """Record executed trade."""
        trade = Trade(
            trade_id=f"trade_{len(self.trades)}",
            timestamp=timestamp,
            price=price,
            size=size,
            buyer_id=buyer_id,
            seller_id=seller_id,
            taker_side=taker_side
        )

        self.trades.append(trade)
        self.last_price = price
        self.last_trade_time = timestamp
        self.total_volume += size

    def get_best_bid_ask(self) -> Tuple[Optional[float], Optional[float]]:
        """Get current best bid and ask prices."""
        best_bid = self.bids[0].price if self.bids else None
        best_ask = self.asks[0].price if self.asks else None
        return best_bid, best_ask

    def get_spread(self) -> Optional[float]:
        """Get current bid-ask spread."""
        best_bid, best_ask = self.get_best_bid_ask()
        if best_bid and best_ask:
            return best_ask - best_bid
        return None

    def get_depth(self, levels: int = 5) -> Dict:
        """Get order book depth."""
        bid_depth = []
        ask_depth = []

        # Aggregate by price level
        bid_levels = {}
        ask_levels = {}

        for bid in sorted(self.bids, key=lambda x: -x.price)[:levels*10]:
            price = round(bid.price, 3)
            if price not in bid_levels:
                bid_levels[price] = 0
            bid_levels[price] += bid.size

        for ask in sorted(self.asks, key=lambda x: x.price)[:levels*10]:
            price = round(ask.price, 3)
            if price not in ask_levels:
                ask_levels[price] = 0
            ask_levels[price] += ask.size

        # Get top levels
        for price in sorted(bid_levels.keys(), reverse=True)[:levels]:
            bid_depth.append({"price": price, "size": bid_levels[price]})

        for price in sorted(ask_levels.keys())[:levels]:
            ask_depth.append({"price": price, "size": ask_levels[price]})

        return {
            "bids": bid_depth,
            "asks": ask_depth,
            "timestamp": datetime.utcnow()
        }

    def simulate_spread_evolution(self, timestamp: datetime, volatility: float = 0.001):
        """
        Simulate realistic spread evolution.

        Spreads widen during:
        - High volatility
        - Low liquidity
        - Large trades
        """
        # Base spread with noise
        spread_noise = np.random.normal(0, self.spread_volatility)

        # Adjust for volatility
        vol_adjustment = 1 + volatility * 10

        # Adjust for recent trading activity
        if self.last_trade_time:
            seconds_since_trade = (timestamp - self.last_trade_time).total_seconds()
            activity_adjustment = 1 + min(0.5, seconds_since_trade / 300)  # Widen if no trades
        else:
            activity_adjustment = 1.2

        # Calculate new spread
        new_spread = self.base_spread * vol_adjustment * activity_adjustment + spread_noise
        new_spread = max(self.tick_size, new_spread)  # Minimum one tick

        # Adjust order book to match spread
        self._adjust_spread(new_spread)

    def _adjust_spread(self, target_spread: float):
        """Adjust order book to achieve target spread."""
        best_bid, best_ask = self.get_best_bid_ask()

        if not best_bid or not best_ask:
            return

        current_spread = best_ask - best_bid

        if abs(current_spread - target_spread) < self.tick_size:
            return  # Close enough

        # Calculate adjustment
        adjustment = (target_spread - current_spread) / 2

        # Move orders
        for order in self.bids:
            order.price -= adjustment

        for order in self.asks:
            order.price += adjustment

        # Re-heapify
        heapq.heapify(self.bids)
        heapq.heapify(self.asks)


class MarketSimulator:
    """
    Complete market simulator for backtesting.

    Manages multiple order books and provides realistic market dynamics:
    - Order book reconstruction from historical data
    - Spread evolution and dynamics
    - Market impact modeling
    - Cross-market arbitrage opportunities
    - Latency simulation
    """

    def __init__(self, config: Dict = None):
        """Initialize market simulator."""
        self.config = config or self._default_config()

        # Order books by market
        self.order_books: Dict[str, OrderBook] = {}

        # Market state
        self.current_time: Optional[datetime] = None
        self.market_hours = {
            "open": 0,  # 24/7 for crypto/prediction markets
            "close": 24
        }

        # Latency simulation
        self.latency_distribution = {
            "mean_ms": 50,
            "std_ms": 20,
            "min_ms": 10,
            "max_ms": 200
        }

        # Historical data cache
        self.historical_cache = {}

    def _default_config(self) -> Dict:
        """Default configuration."""
        return {
            "tick_size": 0.001,
            "min_spread": 0.001,
            "base_spreads": {
                "high_volume": 0.001,  # 10 bps
                "medium_volume": 0.002,  # 20 bps
                "low_volume": 0.005  # 50 bps
            },
            "impact_model": "square_root",
            "latency_enabled": True
        }

    def initialize_market(self, market_id: str, initial_state: Dict = None):
        """Initialize a new market."""
        book = OrderBook(
            market_id=market_id,
            tick_size=self.config["tick_size"]
        )

        if initial_state:
            # Set initial parameters
            book.last_price = initial_state.get("last_price", 0.5)
            book.base_spread = initial_state.get("base_spread", 0.002)

            # Add initial orders if provided
            if "initial_orders" in initial_state:
                for order_data in initial_state["initial_orders"]:
                    order = Order(
                        order_id="",
                        timestamp=self.current_time or datetime.utcnow(),
                        side=OrderSide[order_data["side"].upper()],
                        price=order_data["price"],
                        size=order_data["size"],
                        order_type=OrderType.LIMIT
                    )
                    book.add_order(order)

        self.order_books[market_id] = book
        logger.info(f"Initialized market {market_id}")

    def process_order(self, market_id: str, order_data: Dict) -> Dict:
        """
        Process an order with latency simulation.

        Args:
            market_id: Market to trade in
            order_data: Order details

        Returns:
            Execution result
        """
        if market_id not in self.order_books:
            return {"status": "error", "reason": "Market not found"}

        # Simulate latency
        if self.config["latency_enabled"]:
            latency_ms = self._simulate_latency()
            # In real backtesting, this would delay the order
            # For now, we just track it
        else:
            latency_ms = 0

        # Create order
        order = Order(
            order_id="",
            timestamp=self.current_time or datetime.utcnow(),
            side=OrderSide[order_data["side"].upper()],
            price=order_data.get("price", 0),
            size=order_data["size"],
            order_type=OrderType[order_data.get("type", "LIMIT").upper()],
            trader_id=order_data.get("trader_id")
        )

        # Process through order book
        result = self.order_books[market_id].add_order(order)
        result["latency_ms"] = latency_ms

        return result

    def _simulate_latency(self) -> float:
        """Simulate network latency."""
        latency = np.random.normal(
            self.latency_distribution["mean_ms"],
            self.latency_distribution["std_ms"]
        )

        return np.clip(
            latency,
            self.latency_distribution["min_ms"],
            self.latency_distribution["max_ms"]
        )

    def update_market_state(self, timestamp: datetime, market_updates: List[Dict]):
        """
        Update market state from external data.

        Args:
            timestamp: Current simulation time
            market_updates: List of market updates
        """
        self.current_time = timestamp

        for update in market_updates:
            market_id = update["market_id"]

            if market_id not in self.order_books:
                self.initialize_market(market_id)

            book = self.order_books[market_id]

            # Update last price if provided
            if "last_price" in update:
                book.last_price = update["last_price"]

            # Update spread dynamics
            if "volatility" in update:
                book.simulate_spread_evolution(timestamp, update["volatility"])

            # Add any new orders
            if "orders" in update:
                for order_data in update["orders"]:
                    self.process_order(market_id, order_data)

    def get_market_snapshot(self, market_id: str) -> Dict:
        """Get current market snapshot."""
        if market_id not in self.order_books:
            return None

        book = self.order_books[market_id]
        best_bid, best_ask = book.get_best_bid_ask()

        return {
            "market_id": market_id,
            "timestamp": self.current_time,
            "last_price": book.last_price,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": book.get_spread(),
            "depth": book.get_depth(),
            "volume": book.total_volume,
            "trades_count": len(book.trades)
        }

    def detect_arbitrage_opportunities(self) -> List[Dict]:
        """
        Detect arbitrage opportunities across markets.

        Looks for:
        - Sum-of-shares mispricing
        - Cross-market arbitrage
        - Stale quote arbitrage
        """
        opportunities = []

        # Check sum-of-shares for binary markets
        for market_id, book in self.order_books.items():
            if "_YES" in market_id:
                # Find corresponding NO market
                no_market_id = market_id.replace("_YES", "_NO")
                if no_market_id in self.order_books:
                    yes_book = book
                    no_book = self.order_books[no_market_id]

                    yes_bid, yes_ask = yes_book.get_best_bid_ask()
                    no_bid, no_ask = no_book.get_best_bid_ask()

                    if yes_ask and no_ask:
                        sum_asks = yes_ask + no_ask
                        if sum_asks < 1.0:
                            opportunities.append({
                                "type": "sum_of_shares_buy",
                                "market_base": market_id.replace("_YES", ""),
                                "yes_ask": yes_ask,
                                "no_ask": no_ask,
                                "edge": 1.0 - sum_asks,
                                "timestamp": self.current_time
                            })

                    if yes_bid and no_bid:
                        sum_bids = yes_bid + no_bid
                        if sum_bids > 1.0:
                            opportunities.append({
                                "type": "sum_of_shares_sell",
                                "market_base": market_id.replace("_YES", ""),
                                "yes_bid": yes_bid,
                                "no_bid": no_bid,
                                "edge": sum_bids - 1.0,
                                "timestamp": self.current_time
                            })

        return opportunities

    def calculate_slippage(self, market_id: str, side: str, size: float) -> Dict:
        """
        Calculate expected slippage for a given order size.

        Returns:
            Dict with average_price, slippage_bps, market_impact
        """
        if market_id not in self.order_books:
            return None

        book = self.order_books[market_id]
        opposite_book = book.asks if side.upper() == "BUY" else book.bids

        if not opposite_book:
            return {
                "average_price": None,
                "slippage_bps": None,
                "market_impact": None,
                "liquidity_available": False
            }

        # Walk the book to calculate average fill price
        remaining = size
        total_cost = 0
        fill_prices = []

        for order in sorted(opposite_book, key=lambda x: x.price if side.upper() == "BUY" else -x.price):
            fill_size = min(remaining, order.size)
            total_cost += fill_size * order.price
            fill_prices.append((order.price, fill_size))
            remaining -= fill_size

            if remaining <= 0:
                break

        if remaining > 0:
            # Not enough liquidity
            return {
                "average_price": None,
                "slippage_bps": None,
                "market_impact": None,
                "liquidity_available": False
            }

        average_price = total_cost / size
        best_price = opposite_book[0].price
        slippage = abs(average_price - best_price) / best_price * 10000  # in bps

        # Estimate market impact
        impact = book._calculate_market_impact(size, OrderSide[side.upper()])

        return {
            "average_price": average_price,
            "slippage_bps": slippage,
            "market_impact": impact,
            "liquidity_available": True,
            "fill_distribution": fill_prices
        }

    def get_statistics(self) -> Dict:
        """Get market simulator statistics."""
        stats = {
            "markets_active": len(self.order_books),
            "total_trades": sum(len(book.trades) for book in self.order_books.values()),
            "total_volume": sum(book.total_volume for book in self.order_books.values()),
            "average_spread": {},
            "market_details": {}
        }

        for market_id, book in self.order_books.items():
            spread = book.get_spread()
            stats["average_spread"][market_id] = spread
            stats["market_details"][market_id] = {
                "last_price": book.last_price,
                "volume": book.total_volume,
                "trades": len(book.trades),
                "active_orders": len(book.orders),
                "bid_depth": len(book.bids),
                "ask_depth": len(book.asks)
            }

        return stats
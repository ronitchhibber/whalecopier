"""
Paper Trading Simulator for Polymarket Whale Copy Trading
Provides risk-free testing environment with realistic execution simulation
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from collections import defaultdict

logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    """Order execution status"""
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class SlippageModel(Enum):
    """Market impact and slippage models"""
    NONE = "none"  # No slippage
    LINEAR = "linear"  # Linear impact based on size
    SQUARE_ROOT = "square_root"  # Square root impact (more realistic)
    REALISTIC = "realistic"  # Complex model with multiple factors


@dataclass
class PaperOrder:
    """Represents a paper trading order"""
    order_id: str
    market_id: str
    side: str  # 'BUY' or 'SELL'
    outcome: str  # 'YES' or 'NO'
    size: Decimal
    price: Decimal
    timestamp: datetime
    status: OrderStatus = OrderStatus.PENDING
    filled_size: Decimal = Decimal(0)
    filled_price: Decimal = Decimal(0)
    fees: Decimal = Decimal(0)
    slippage: Decimal = Decimal(0)
    execution_time: Optional[datetime] = None


@dataclass
class PaperPosition:
    """Represents a paper trading position"""
    market_id: str
    outcome: str
    size: Decimal
    entry_price: Decimal
    current_price: Decimal
    opened_at: datetime
    closed_at: Optional[datetime] = None
    pnl: Decimal = Decimal(0)
    realized_pnl: Decimal = Decimal(0)
    unrealized_pnl: Decimal = Decimal(0)
    fees_paid: Decimal = Decimal(0)


@dataclass
class PaperAccount:
    """Simulated trading account"""
    balance: Decimal
    initial_balance: Decimal
    positions: Dict[str, PaperPosition] = field(default_factory=dict)
    orders: List[PaperOrder] = field(default_factory=list)
    trade_history: List[Dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


class MarketSimulator:
    """
    Simulates market conditions and order execution
    Provides realistic trading environment
    """

    def __init__(self, config: Dict = None):
        self.config = config or self._default_config()
        self.market_prices = {}  # Current market prices
        self.market_liquidity = {}  # Liquidity depth
        self.volatility = {}  # Market volatility
        self.order_books = {}  # Simulated order books

    def _default_config(self) -> Dict:
        """Default market simulation config"""
        return {
            "base_fee_rate": 0.002,  # 0.2% taker fee
            "maker_fee_rate": 0.001,  # 0.1% maker fee
            "base_spread": 0.005,  # 0.5% spread
            "volatility_multiplier": 1.0,
            "liquidity_factor": 100000,  # Base liquidity in USD
            "slippage_model": SlippageModel.REALISTIC,
            "max_slippage": 0.05,  # 5% max slippage
            "execution_delay": 0.5,  # 500ms execution delay
        }

    def set_market_price(self, market_id: str, outcome: str, price: Decimal):
        """Set current market price"""
        key = f"{market_id}:{outcome}"
        self.market_prices[key] = price

        # Initialize volatility if not set
        if key not in self.volatility:
            self.volatility[key] = 0.02  # 2% default volatility

    def get_market_price(self, market_id: str, outcome: str) -> Decimal:
        """Get current market price with random walk simulation"""
        key = f"{market_id}:{outcome}"

        if key not in self.market_prices:
            # Default to 0.5 if price not set
            self.market_prices[key] = Decimal("0.5")

        # Simulate price movement
        current_price = self.market_prices[key]
        volatility = self.volatility.get(key, 0.02)

        # Random walk with mean reversion
        change = np.random.normal(0, float(volatility))
        change *= self.config["volatility_multiplier"]

        # Mean reversion factor (prices tend toward 0.5)
        mean_reversion = (0.5 - float(current_price)) * 0.01

        new_price = float(current_price) + change + mean_reversion

        # Bound between 0.01 and 0.99
        new_price = max(0.01, min(0.99, new_price))

        self.market_prices[key] = Decimal(str(new_price))
        return self.market_prices[key]

    def calculate_slippage(self,
                          market_id: str,
                          outcome: str,
                          side: str,
                          size: Decimal) -> Decimal:
        """Calculate price slippage based on order size"""
        model = self.config["slippage_model"]

        if model == SlippageModel.NONE:
            return Decimal(0)

        # Get market liquidity
        key = f"{market_id}:{outcome}"
        liquidity = self.market_liquidity.get(key, self.config["liquidity_factor"])

        # Calculate impact based on size relative to liquidity
        size_ratio = float(size) / liquidity

        if model == SlippageModel.LINEAR:
            slippage = size_ratio * 0.01  # 1% per liquidity ratio

        elif model == SlippageModel.SQUARE_ROOT:
            slippage = np.sqrt(size_ratio) * 0.02  # 2% for sqrt of ratio

        elif model == SlippageModel.REALISTIC:
            # Complex model with multiple factors
            base_impact = np.sqrt(size_ratio) * 0.015
            volatility_impact = self.volatility.get(key, 0.02) * size_ratio
            spread_cost = self.config["base_spread"]

            slippage = base_impact + volatility_impact + spread_cost

            # Add random component
            slippage += np.random.normal(0, 0.001)

        else:
            slippage = 0

        # Apply directional impact (buying pushes price up)
        if side == "BUY":
            slippage = abs(slippage)
        else:
            slippage = -abs(slippage)

        # Cap at max slippage
        max_slip = self.config["max_slippage"]
        slippage = max(-max_slip, min(max_slip, slippage))

        return Decimal(str(slippage))

    def calculate_fees(self, size: Decimal, is_maker: bool = False) -> Decimal:
        """Calculate trading fees"""
        if is_maker:
            fee_rate = self.config["maker_fee_rate"]
        else:
            fee_rate = self.config["base_fee_rate"]

        return size * Decimal(str(fee_rate))

    async def execute_order(self, order: PaperOrder) -> PaperOrder:
        """Simulate order execution with realistic conditions"""
        # Simulate execution delay
        await asyncio.sleep(self.config["execution_delay"])

        # Get current market price
        market_price = self.get_market_price(order.market_id, order.outcome)

        # Check if order should fill
        if order.side == "BUY" and order.price < market_price:
            order.status = OrderStatus.REJECTED
            return order
        elif order.side == "SELL" and order.price > market_price:
            order.status = OrderStatus.REJECTED
            return order

        # Calculate slippage
        slippage = self.calculate_slippage(
            order.market_id,
            order.outcome,
            order.side,
            order.size
        )

        # Calculate execution price with slippage
        execution_price = market_price * (Decimal(1) + slippage)

        # Calculate fees
        fees = self.calculate_fees(order.size)

        # Update order
        order.status = OrderStatus.FILLED
        order.filled_size = order.size
        order.filled_price = execution_price
        order.fees = fees
        order.slippage = slippage
        order.execution_time = datetime.now()

        return order


class PaperTradingEngine:
    """
    Main paper trading engine
    Manages accounts, positions, and order execution
    """

    def __init__(self, initial_balance: Decimal = Decimal("10000")):
        self.account = PaperAccount(
            balance=initial_balance,
            initial_balance=initial_balance
        )
        self.market_simulator = MarketSimulator()
        self.order_counter = 0
        self.metrics = self._init_metrics()

    def _init_metrics(self) -> Dict:
        """Initialize performance metrics"""
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": Decimal(0),
            "total_fees": Decimal(0),
            "total_slippage": Decimal(0),
            "max_drawdown": Decimal(0),
            "sharpe_ratio": 0.0,
            "win_rate": 0.0,
            "avg_win": Decimal(0),
            "avg_loss": Decimal(0),
            "profit_factor": 0.0,
            "peak_balance": self.account.initial_balance,
            "current_drawdown": Decimal(0)
        }

    async def place_order(self,
                         market_id: str,
                         side: str,
                         outcome: str,
                         size: Decimal,
                         price: Optional[Decimal] = None) -> PaperOrder:
        """Place a paper trading order"""
        # Generate order ID
        self.order_counter += 1
        order_id = f"PAPER-{self.order_counter:06d}"

        # Get market price if not specified
        if price is None:
            price = self.market_simulator.get_market_price(market_id, outcome)

        # Create order
        order = PaperOrder(
            order_id=order_id,
            market_id=market_id,
            side=side,
            outcome=outcome,
            size=size,
            price=price,
            timestamp=datetime.now()
        )

        # Check if we have sufficient balance
        required_balance = size
        if side == "BUY" and self.account.balance < required_balance:
            order.status = OrderStatus.REJECTED
            logger.warning(f"Insufficient balance for order {order_id}")
            return order

        # Add to pending orders
        self.account.orders.append(order)

        # Execute order
        order = await self.market_simulator.execute_order(order)

        # Process filled order
        if order.status == OrderStatus.FILLED:
            await self._process_filled_order(order)

        return order

    async def _process_filled_order(self, order: PaperOrder):
        """Process a filled order and update positions"""
        position_key = f"{order.market_id}:{order.outcome}"

        if order.side == "BUY":
            # Deduct from balance
            cost = order.filled_size * order.filled_price + order.fees
            self.account.balance -= cost

            # Create or update position
            if position_key in self.account.positions:
                position = self.account.positions[position_key]
                # Average in
                total_cost = (position.size * position.entry_price +
                            order.filled_size * order.filled_price)
                position.size += order.filled_size
                position.entry_price = total_cost / position.size
                position.fees_paid += order.fees
            else:
                # New position
                position = PaperPosition(
                    market_id=order.market_id,
                    outcome=order.outcome,
                    size=order.filled_size,
                    entry_price=order.filled_price,
                    current_price=order.filled_price,
                    opened_at=datetime.now(),
                    fees_paid=order.fees
                )
                self.account.positions[position_key] = position

        else:  # SELL
            if position_key in self.account.positions:
                position = self.account.positions[position_key]

                # Calculate P&L
                pnl = (order.filled_price - position.entry_price) * order.filled_size
                pnl -= order.fees  # Subtract fees from P&L

                # Update position
                position.size -= order.filled_size
                position.realized_pnl += pnl
                position.fees_paid += order.fees

                # Add proceeds to balance
                proceeds = order.filled_size * order.filled_price - order.fees
                self.account.balance += proceeds

                # Remove position if fully closed
                if position.size <= 0:
                    position.closed_at = datetime.now()
                    del self.account.positions[position_key]

                # Update metrics
                self._update_metrics_for_trade(pnl, order)

        # Record trade
        self.account.trade_history.append({
            "order_id": order.order_id,
            "timestamp": order.execution_time,
            "market_id": order.market_id,
            "outcome": order.outcome,
            "side": order.side,
            "size": float(order.filled_size),
            "price": float(order.filled_price),
            "fees": float(order.fees),
            "slippage": float(order.slippage),
            "balance": float(self.account.balance)
        })

    def _update_metrics_for_trade(self, pnl: Decimal, order: PaperOrder):
        """Update performance metrics after a trade"""
        self.metrics["total_trades"] += 1
        self.metrics["total_pnl"] += pnl
        self.metrics["total_fees"] += order.fees
        self.metrics["total_slippage"] += abs(order.slippage * order.filled_size)

        if pnl > 0:
            self.metrics["winning_trades"] += 1
            self.metrics["avg_win"] = (
                (self.metrics["avg_win"] * (self.metrics["winning_trades"] - 1) + pnl) /
                self.metrics["winning_trades"]
            )
        else:
            self.metrics["losing_trades"] += 1
            self.metrics["avg_loss"] = (
                (self.metrics["avg_loss"] * (self.metrics["losing_trades"] - 1) + abs(pnl)) /
                self.metrics["losing_trades"]
            )

        # Update win rate
        if self.metrics["total_trades"] > 0:
            self.metrics["win_rate"] = self.metrics["winning_trades"] / self.metrics["total_trades"]

        # Update profit factor
        if self.metrics["avg_loss"] > 0:
            self.metrics["profit_factor"] = self.metrics["avg_win"] / self.metrics["avg_loss"]

        # Update peak and drawdown
        current_balance = self.account.balance + self.get_unrealized_pnl()
        if current_balance > self.metrics["peak_balance"]:
            self.metrics["peak_balance"] = current_balance
            self.metrics["current_drawdown"] = Decimal(0)
        else:
            drawdown = (self.metrics["peak_balance"] - current_balance) / self.metrics["peak_balance"]
            self.metrics["current_drawdown"] = drawdown
            self.metrics["max_drawdown"] = max(self.metrics["max_drawdown"], drawdown)

    def get_unrealized_pnl(self) -> Decimal:
        """Calculate total unrealized P&L"""
        total_unrealized = Decimal(0)

        for position in self.account.positions.values():
            # Get current market price
            current_price = self.market_simulator.get_market_price(
                position.market_id,
                position.outcome
            )
            position.current_price = current_price

            # Calculate unrealized P&L
            position.unrealized_pnl = (current_price - position.entry_price) * position.size
            total_unrealized += position.unrealized_pnl

        return total_unrealized

    def calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio from returns"""
        if len(self.account.trade_history) < 2:
            return 0.0

        # Calculate daily returns
        returns = []
        for i in range(1, len(self.account.trade_history)):
            prev_balance = self.account.trade_history[i-1]["balance"]
            curr_balance = self.account.trade_history[i]["balance"]
            if prev_balance > 0:
                ret = (curr_balance - prev_balance) / prev_balance
                returns.append(ret)

        if not returns:
            return 0.0

        # Calculate Sharpe (assuming 0% risk-free rate)
        returns_array = np.array(returns)
        if np.std(returns_array) > 0:
            sharpe = np.mean(returns_array) / np.std(returns_array) * np.sqrt(252)
            self.metrics["sharpe_ratio"] = sharpe
            return sharpe

        return 0.0

    def get_performance_report(self) -> Dict:
        """Generate comprehensive performance report"""
        # Update current metrics
        self.get_unrealized_pnl()  # Updates position P&Ls
        self.calculate_sharpe_ratio()

        total_pnl = self.metrics["total_pnl"] + self.get_unrealized_pnl()
        roi = (total_pnl / self.account.initial_balance) * 100

        return {
            "account": {
                "initial_balance": float(self.account.initial_balance),
                "current_balance": float(self.account.balance),
                "equity": float(self.account.balance + self.get_unrealized_pnl()),
                "total_pnl": float(total_pnl),
                "roi_percent": float(roi),
                "open_positions": len(self.account.positions)
            },
            "trading": {
                "total_trades": self.metrics["total_trades"],
                "winning_trades": self.metrics["winning_trades"],
                "losing_trades": self.metrics["losing_trades"],
                "win_rate": float(self.metrics["win_rate"]),
                "avg_win": float(self.metrics["avg_win"]),
                "avg_loss": float(self.metrics["avg_loss"]),
                "profit_factor": float(self.metrics["profit_factor"])
            },
            "risk": {
                "max_drawdown": float(self.metrics["max_drawdown"]),
                "current_drawdown": float(self.metrics["current_drawdown"]),
                "sharpe_ratio": self.metrics["sharpe_ratio"]
            },
            "costs": {
                "total_fees": float(self.metrics["total_fees"]),
                "total_slippage": float(self.metrics["total_slippage"]),
                "avg_fee_per_trade": float(
                    self.metrics["total_fees"] / max(1, self.metrics["total_trades"])
                ),
                "avg_slippage_per_trade": float(
                    self.metrics["total_slippage"] / max(1, self.metrics["total_trades"])
                )
            },
            "positions": [
                {
                    "market_id": pos.market_id,
                    "outcome": pos.outcome,
                    "size": float(pos.size),
                    "entry_price": float(pos.entry_price),
                    "current_price": float(pos.current_price),
                    "unrealized_pnl": float(pos.unrealized_pnl),
                    "fees_paid": float(pos.fees_paid)
                }
                for pos in self.account.positions.values()
            ]
        }

    def reset(self):
        """Reset paper trading account"""
        self.account = PaperAccount(
            balance=self.account.initial_balance,
            initial_balance=self.account.initial_balance
        )
        self.order_counter = 0
        self.metrics = self._init_metrics()
        logger.info("Paper trading account reset")


class PaperTradingSimulator:
    """
    High-level paper trading simulator for testing strategies
    """

    def __init__(self, initial_balance: Decimal = Decimal("10000")):
        self.engine = PaperTradingEngine(initial_balance)
        self.running = False

    async def simulate_whale_copy_trade(self, whale_trade: Dict) -> Dict:
        """Simulate copying a whale trade"""
        # Extract trade details
        market_id = whale_trade.get("market_id")
        side = whale_trade.get("side", "BUY")
        outcome = whale_trade.get("outcome", "YES")
        whale_size = Decimal(str(whale_trade.get("size", 100)))

        # Calculate our position size (e.g., 1% of whale size)
        our_size = whale_size * Decimal("0.01")

        # Ensure minimum size
        our_size = max(our_size, Decimal("10"))

        # Place order
        order = await self.engine.place_order(
            market_id=market_id,
            side=side,
            outcome=outcome,
            size=our_size
        )

        return {
            "whale_trade": whale_trade,
            "our_order": {
                "order_id": order.order_id,
                "status": order.status.value,
                "size": float(order.filled_size),
                "price": float(order.filled_price),
                "fees": float(order.fees),
                "slippage": float(order.slippage)
            }
        }

    async def run_backtest(self, historical_trades: List[Dict]) -> Dict:
        """Run backtest on historical trades"""
        logger.info(f"Starting backtest with {len(historical_trades)} trades")

        results = []
        for trade in historical_trades:
            result = await self.simulate_whale_copy_trade(trade)
            results.append(result)

            # Log progress every 10 trades
            if len(results) % 10 == 0:
                report = self.engine.get_performance_report()
                logger.info(
                    f"Progress: {len(results)}/{len(historical_trades)} trades, "
                    f"P&L: ${report['account']['total_pnl']:.2f}, "
                    f"Win Rate: {report['trading']['win_rate']:.2%}"
                )

        # Generate final report
        final_report = self.engine.get_performance_report()
        final_report["trades_executed"] = results

        return final_report

    def get_report(self) -> Dict:
        """Get current performance report"""
        return self.engine.get_performance_report()

    def reset(self):
        """Reset simulator"""
        self.engine.reset()


async def test_paper_trading():
    """Test paper trading simulator"""
    print("=" * 60)
    print("PAPER TRADING SIMULATOR TEST")
    print("=" * 60)

    # Create simulator
    simulator = PaperTradingSimulator(initial_balance=Decimal("10000"))

    # Simulate some whale trades
    test_trades = [
        {
            "market_id": "0x123abc",
            "side": "BUY",
            "outcome": "YES",
            "size": 1000,
            "whale_address": "0xwhale1"
        },
        {
            "market_id": "0x456def",
            "side": "BUY",
            "outcome": "NO",
            "size": 2500,
            "whale_address": "0xwhale1"
        },
        {
            "market_id": "0x123abc",
            "side": "SELL",
            "outcome": "YES",
            "size": 500,
            "whale_address": "0xwhale1"
        }
    ]

    print("\nExecuting test trades...")
    for i, trade in enumerate(test_trades, 1):
        print(f"\nTrade {i}: {trade['side']} {trade['size']} {trade['outcome']}")
        result = await simulator.simulate_whale_copy_trade(trade)
        order = result["our_order"]
        print(f"  Our order: {order['status']}, Size: {order['size']}, "
              f"Price: {order['price']:.4f}, Fees: ${order['fees']:.2f}")

    # Get performance report
    print("\n" + "=" * 60)
    print("PERFORMANCE REPORT")
    print("=" * 60)

    report = simulator.get_report()

    print(f"\nAccount Summary:")
    print(f"  Initial Balance: ${report['account']['initial_balance']:,.2f}")
    print(f"  Current Balance: ${report['account']['current_balance']:,.2f}")
    print(f"  Total Equity:    ${report['account']['equity']:,.2f}")
    print(f"  Total P&L:       ${report['account']['total_pnl']:,.2f}")
    print(f"  ROI:             {report['account']['roi_percent']:.2f}%")

    print(f"\nTrading Statistics:")
    print(f"  Total Trades:    {report['trading']['total_trades']}")
    print(f"  Win Rate:        {report['trading']['win_rate']:.2%}")
    print(f"  Profit Factor:   {report['trading']['profit_factor']:.2f}")

    print(f"\nRisk Metrics:")
    print(f"  Max Drawdown:    {report['risk']['max_drawdown']:.2%}")
    print(f"  Sharpe Ratio:    {report['risk']['sharpe_ratio']:.2f}")

    print(f"\nCost Analysis:")
    print(f"  Total Fees:      ${report['costs']['total_fees']:.2f}")
    print(f"  Total Slippage:  ${report['costs']['total_slippage']:.2f}")

    print("\n✓ Paper trading test complete!")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    asyncio.run(test_paper_trading())
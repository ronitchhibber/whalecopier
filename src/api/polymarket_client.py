"""
Polymarket API Client Wrapper
Handles authentication, REST API calls, and WebSocket connections

NOTE: Requires py-clob-client package (requires Python 3.9.10+)
"""
from typing import List, Dict, Optional, Any
import httpx
import asyncio
import websockets
import json
import logging
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential
import time

from src.config import settings

logger = logging.getLogger(__name__)

# Conditional import for py_clob_client (requires Python 3.9.10+)
PY_CLOB_CLIENT_AVAILABLE = False
try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import (
        OrderArgs, MarketOrderArgs, OrderType,
        OpenOrderParams, DropNotificationParams
    )
    from py_clob_client.order_builder.constants import BUY, SELL
    PY_CLOB_CLIENT_AVAILABLE = True
except ImportError:
    logger.warning("py-clob-client not available - PolymarketClient will operate in stub mode. Requires Python 3.9.10+")
    # Create stub types for when py_clob_client is not available
    ClobClient = None
    OrderArgs = None
    MarketOrderArgs = None
    OrderType = None
    OpenOrderParams = None
    DropNotificationParams = None
    BUY = "BUY"
    SELL = "SELL"


class PolymarketClient:
    """
    Comprehensive Polymarket API client wrapper
    Handles authentication, rate limiting, and error handling
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        passphrase: Optional[str] = None,
        private_key: Optional[str] = None,
    ):
        # Use provided credentials or fall back to config
        self.api_key = api_key or settings.POLYMARKET_API_KEY
        self.secret = secret or settings.POLYMARKET_SECRET
        self.passphrase = passphrase or settings.POLYMARKET_PASSPHRASE
        self.private_key = private_key or settings.PRIVATE_KEY

        # Initialize CLOB client (if py_clob_client is available)
        if PY_CLOB_CLIENT_AVAILABLE and ClobClient is not None:
            # Create credentials object if API keys are provided
            creds = None
            if all([self.api_key, self.secret, self.passphrase]):
                try:
                    from py_clob_client.clob_types import ApiCreds
                    creds = ApiCreds(
                        api_key=self.api_key,
                        api_secret=self.secret,
                        api_passphrase=self.passphrase
                    )
                except ImportError:
                    logger.warning("Could not import ApiCreds from py_clob_client")

            self.clob_client = ClobClient(
                host=settings.POLYMARKET_API_URL,
                key=self.private_key if self.private_key else None,
                chain_id=settings.CHAIN_ID,
                signature_type=0,  # 0 = EOA (MetaMask), 1 = Email/Magic, 2 = Browser
                creds=creds  # Pass credentials during initialization
            )
        else:
            self.clob_client = None
            logger.warning(
                "py-clob-client not available - trading functionality disabled. "
                "Install py-clob-client with Python 3.9.10+ for full functionality."
            )

        # Data API base URL
        self.data_api_url = settings.POLYMARKET_DATA_API_URL

        # HTTP client for data API
        self.http_client = httpx.AsyncClient(timeout=30.0)

        # Rate limiting
        self.request_timestamps = []
        self.max_requests_per_window = 5000  # CLOB General limit
        self.window_seconds = 10

        logger.info("Polymarket client initialized")

    async def _check_rate_limit(self):
        """Check and enforce rate limits"""
        now = time.time()
        # Remove timestamps older than window
        self.request_timestamps = [
            ts for ts in self.request_timestamps
            if now - ts < self.window_seconds
        ]

        if len(self.request_timestamps) >= self.max_requests_per_window:
            # Wait until oldest request expires
            sleep_time = self.window_seconds - (now - self.request_timestamps[0])
            if sleep_time > 0:
                logger.warning(f"Rate limit reached, sleeping for {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)

        self.request_timestamps.append(now)

    # ==================== Authentication ====================

    def create_api_credentials(self) -> Dict[str, str]:
        """
        Create API credentials (L2 authentication)
        Requires L1 (private key) authentication
        """
        try:
            creds = self.clob_client.create_or_derive_api_creds()
            logger.info("API credentials created successfully")
            return creds
        except Exception as e:
            logger.error(f"Failed to create API credentials: {e}")
            raise

    # ==================== Market Data ====================

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_markets(
        self,
        closed: Optional[bool] = None,
        active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        """Get markets from Data API"""
        await self._check_rate_limit()

        params = {"limit": limit, "offset": offset}
        if closed is not None:
            params["closed"] = str(closed).lower()
        if active is not None:
            params["active"] = str(active).lower()

        try:
            response = await self.http_client.get(
                f"{self.data_api_url}/markets",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get markets: {e}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_market(self, condition_id: str) -> Dict:
        """Get single market details"""
        await self._check_rate_limit()

        try:
            response = await self.http_client.get(
                f"{self.data_api_url}/markets/{condition_id}"
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get market {condition_id}: {e}")
            raise

    # ==================== Trade Data ====================

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_trades(
        self,
        user: Optional[str] = None,
        market: Optional[str] = None,
        filter_type: Optional[str] = "CASH",  # or "TOKENS"
        filter_amount: Optional[float] = None,
        side: Optional[str] = None,  # "BUY" or "SELL"
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        """
        Get trades from Data API

        Args:
            user: Wallet address (0x-prefixed)
            market: Comma-separated condition IDs
            filter_type: "CASH" or "TOKENS"
            filter_amount: Minimum transaction value (e.g., 10000 for $10k+ trades)
            side: "BUY" or "SELL"
            limit: Max 10,000
            offset: Pagination offset (max 10,000)
        """
        await self._check_rate_limit()

        params = {"limit": min(limit, 10000), "offset": min(offset, 10000)}

        if user:
            params["user"] = user
        if market:
            params["market"] = market
        if filter_type and filter_amount:
            params["filterType"] = filter_type
            params["filterAmount"] = filter_amount
        if side:
            params["side"] = side.upper()

        try:
            response = await self.http_client.get(
                f"{self.data_api_url}/trades",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get trades: {e}")
            raise

    async def get_whale_trades(
        self,
        min_trade_size: float = 10000.0,
        limit: int = 100
    ) -> List[Dict]:
        """Get large trades (whale activity)"""
        return await self.get_trades(
            filter_type="CASH",
            filter_amount=min_trade_size,
            limit=limit
        )

    # ==================== Positions ====================

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_positions(
        self,
        user: str,
        market: Optional[str] = None,
        size_threshold: float = 1.0,
        sort_by: str = "CURRENT",
        limit: int = 100,
    ) -> List[Dict]:
        """
        Get user positions

        Args:
            user: User address (required)
            market: Condition IDs (optional)
            size_threshold: Minimum position size (default: 1)
            sort_by: CURRENT, INITIAL, TOKENS, CASHPNL, PERCENTPNL, etc.
            limit: Max 500
        """
        await self._check_rate_limit()

        params = {
            "user": user,
            "sizeThreshold": size_threshold,
            "sortBy": sort_by,
            "limit": min(limit, 500),
        }

        if market:
            params["market"] = market

        try:
            response = await self.http_client.get(
                f"{self.data_api_url}/positions",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get positions for {user}: {e}")
            raise

    # ==================== Price Data ====================

    def get_midpoint(self, token_id: str) -> float:
        """Get current midpoint price for a token"""
        try:
            return self.clob_client.get_midpoint(token_id)
        except Exception as e:
            logger.error(f"Failed to get midpoint for {token_id}: {e}")
            raise

    def get_price(self, token_id: str, side: str = "BUY") -> float:
        """Get best bid (SELL) or ask (BUY) price"""
        try:
            return self.clob_client.get_price(token_id, side)
        except Exception as e:
            logger.error(f"Failed to get price for {token_id}: {e}")
            raise

    def get_orderbook(self, token_id: str) -> Dict:
        """Get full orderbook for a token"""
        try:
            return self.clob_client.get_order_book(token_id)
        except Exception as e:
            logger.error(f"Failed to get orderbook for {token_id}: {e}")
            raise

    def get_last_trade_price(self, token_id: str) -> float:
        """Get last trade price"""
        try:
            return self.clob_client.get_last_trade_price(token_id)
        except Exception as e:
            logger.error(f"Failed to get last trade price for {token_id}: {e}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_price_history(
        self,
        market: str,
        interval: Optional[str] = None,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
        fidelity: Optional[int] = None,
    ) -> Dict:
        """
        Get historical prices

        Args:
            market: CLOB token ID (required)
            interval: "1m", "1h", "6h", "1d", "1w", "max" (mutually exclusive with startTs/endTs)
            start_ts: Unix timestamp start
            end_ts: Unix timestamp end
            fidelity: Resolution in minutes
        """
        await self._check_rate_limit()

        params = {"market": market}

        if interval:
            params["interval"] = interval
        else:
            if start_ts:
                params["startTs"] = start_ts
            if end_ts:
                params["endTs"] = end_ts

        if fidelity:
            params["fidelity"] = fidelity

        try:
            response = await self.http_client.get(
                f"{self.data_api_url}/prices-history",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get price history for {market}: {e}")
            raise

    # ==================== Order Management ====================

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=5))
    def place_limit_order(
        self,
        token_id: str,
        price: float,
        size: float,
        side: str = "BUY",
    ) -> Dict:
        """
        Place a limit order

        Args:
            token_id: Token ID to trade
            price: Limit price (0-1 for binary markets)
            size: Number of shares
            side: "BUY" or "SELL"

        Returns:
            Order response with orderID
        """
        try:
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=size,
                side=BUY if side.upper() == "BUY" else SELL,
            )

            response = self.clob_client.create_and_post_order(order_args)
            logger.info(f"Limit order placed: {response.get('orderID')}")
            return response

        except Exception as e:
            logger.error(f"Failed to place limit order: {e}")
            raise

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=5))
    def place_market_order(
        self,
        token_id: str,
        amount: float,
        side: str = "BUY",
        order_type: str = "FOK",  # Fill-or-Kill
    ) -> Dict:
        """
        Place a market order

        Args:
            token_id: Token ID to trade
            amount: Dollar amount to spend/receive
            side: "BUY" or "SELL"
            order_type: "FOK" (Fill-or-Kill) or "GTC" (Good-til-Cancelled)

        Returns:
            Order response
        """
        try:
            market_order_args = MarketOrderArgs(
                token_id=token_id,
                amount=amount,
                side=BUY if side.upper() == "BUY" else SELL,
                order_type=OrderType.FOK if order_type == "FOK" else OrderType.GTC,
            )

            signed_order = self.clob_client.create_market_order(market_order_args)
            response = self.clob_client.post_order(
                signed_order,
                OrderType.FOK if order_type == "FOK" else OrderType.GTC
            )

            logger.info(f"Market order placed: {response.get('orderID')}")
            return response

        except Exception as e:
            logger.error(f"Failed to place market order: {e}")
            raise

    def get_orders(self, market: Optional[str] = None) -> List[Dict]:
        """Get open orders"""
        try:
            params = OpenOrderParams(market=market) if market else OpenOrderParams()
            return self.clob_client.get_orders(params)
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            raise

    def cancel_order(self, order_id: str) -> Dict:
        """Cancel a specific order"""
        try:
            response = self.clob_client.cancel(order_id)
            logger.info(f"Order cancelled: {order_id}")
            return response
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            raise

    def cancel_all_orders(self) -> Dict:
        """Cancel all open orders"""
        try:
            response = self.clob_client.cancel_all()
            logger.info("All orders cancelled")
            return response
        except Exception as e:
            logger.error(f"Failed to cancel all orders: {e}")
            raise

    # ==================== Balance & Account ====================

    def get_balance(self) -> float:
        """Get USDC balance"""
        try:
            # This would need to query the blockchain directly
            # Using web3.py to check USDC balance on Polygon
            # TODO: Implement blockchain balance check
            logger.warning("get_balance not fully implemented")
            return 0.0
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            raise

    # ==================== Cleanup ====================

    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()
        logger.info("Polymarket client closed")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

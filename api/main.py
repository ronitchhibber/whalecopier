"""
Whale Copy-Trading Dashboard API
FastAPI server for real-time whale monitoring and paper trading
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, select, func, desc
from sqlalchemy.orm import Session
from typing import List, Dict
import json
import asyncio
from datetime import datetime, timedelta
import os
import sys
import requests

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs.common.models import Whale, Trade
from dotenv import load_dotenv
import logging
from decimal import Decimal
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import backtester
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'services'))
    from backtester import Backtester, BacktestConfig
    BACKTESTER_AVAILABLE = True
    logger.info("Backtester loaded successfully")
except ImportError as e:
    logger.warning(f"Backtester not available: {e}")
    BACKTESTER_AVAILABLE = False
    Backtester = None
    BacktestConfig = None


# ============================================================================
# 24H METRICS HELPERS
# ============================================================================

def fetch_24h_trades(address: str) -> tuple:
    """
    Fetch trades from last 24h for a whale address from database.
    Returns: (trade_count, total_volume)

    NOTE: This now reads from pre-calculated database columns that are
    updated by the whale_metrics_updater service every 15 minutes.
    """
    try:
        # Query whale record for 24h metrics
        session = next(get_db())
        whale = session.query(Whale).filter(Whale.address == address).first()

        if whale:
            trades_count = whale.trades_24h or 0
            volume = float(whale.volume_24h or 0)
            return trades_count, volume
        else:
            return 0, 0.0

    except Exception as e:
        print(f"Error fetching 24h trades for {address[:10]}: {e}")
        return 0, 0.0

app = FastAPI(title="Whale Tracker Dashboard")

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
engine = create_engine(DATABASE_URL)

# Paper trading state
paper_portfolio = {
    "balance": 10000.0,  # Starting with $10k
    "positions": {},  # {market_id: {size, entry_price, whale_address}}
    "trades": [],  # List of executed paper trades
    "pnl": 0.0
}

# ============================================================================
# STRATEGY SYSTEM - Multiple Paper Trading Accounts
# ============================================================================

# Strategy definitions with separate paper trading accounts
strategies = {
    "top_5_whales": {
        "id": "top_5_whales",
        "name": "Top 5 Whales",
        "description": "Copy trades from the top 5 whales by quality score",
        "active": False,
        "criteria": {
            "type": "top_n",
            "n": 5,
            "sort_by": "quality_score"
        },
        "position_sizing": {
            "base_pct": 5.0,
            "max_pct": 10.0
        },
        "account": {
            "balance": 10000.0,
            "positions": {},
            "trades": [],
            "pnl": 0.0,
            "initial_balance": 10000.0
        }
    },
    "high_sharpe": {
        "id": "high_sharpe",
        "name": "High Sharpe Portfolio",
        "description": "Copy trades only from whales with Sharpe ratio > 3.0",
        "active": False,
        "criteria": {
            "type": "filter",
            "min_sharpe": 3.0
        },
        "position_sizing": {
            "base_pct": 5.0,
            "max_pct": 10.0
        },
        "account": {
            "balance": 10000.0,
            "positions": {},
            "trades": [],
            "pnl": 0.0,
            "initial_balance": 10000.0
        }
    },
    "diversified": {
        "id": "diversified",
        "name": "Diversified All-Stars",
        "description": "Copy trades from top 20 whales with balanced allocation",
        "active": False,
        "criteria": {
            "type": "top_n",
            "n": 20,
            "sort_by": "quality_score"
        },
        "position_sizing": {
            "base_pct": 3.0,
            "max_pct": 6.0
        },
        "account": {
            "balance": 10000.0,
            "positions": {},
            "trades": [],
            "pnl": 0.0,
            "initial_balance": 10000.0
        }
    },
    "conservative": {
        "id": "conservative",
        "name": "Conservative",
        "description": "Copy trades only from whales with win rate > 70%",
        "active": False,
        "criteria": {
            "type": "filter",
            "min_win_rate": 70.0
        },
        "position_sizing": {
            "base_pct": 3.0,
            "max_pct": 5.0
        },
        "account": {
            "balance": 10000.0,
            "positions": {},
            "trades": [],
            "pnl": 0.0,
            "initial_balance": 10000.0
        }
    },
    "aggressive": {
        "id": "aggressive",
        "name": "Aggressive",
        "description": "Copy trades from highest P&L whales with larger positions",
        "active": False,
        "criteria": {
            "type": "top_n",
            "n": 10,
            "sort_by": "total_pnl"
        },
        "position_sizing": {
            "base_pct": 7.0,
            "max_pct": 12.0
        },
        "account": {
            "balance": 10000.0,
            "positions": {},
            "trades": [],
            "pnl": 0.0,
            "initial_balance": 10000.0
        }
    }
}


def check_whale_matches_strategy(whale: dict, strategy: dict) -> bool:
    """Check if a whale matches the strategy's criteria"""
    criteria = strategy["criteria"]

    if criteria["type"] == "filter":
        # Filter-based strategy: check specific metrics
        if "min_sharpe" in criteria and whale.get("sharpe_ratio", 0) < criteria["min_sharpe"]:
            return False
        if "min_win_rate" in criteria and whale.get("win_rate", 0) < criteria["min_win_rate"]:
            return False
        if "min_quality_score" in criteria and whale.get("quality_score", 0) < criteria["min_quality_score"]:
            return False
        return True

    elif criteria["type"] == "top_n":
        # Top-N strategy: handled in get_strategy_whales()
        return True

    return False


def filter_whales_by_strategy(strategy: dict, all_whales: list) -> list:
    """Get the list of whales that match a strategy's criteria"""
    criteria = strategy["criteria"]

    if criteria["type"] == "top_n":
        # Sort by specified field and take top N
        sort_by = criteria.get("sort_by", "quality_score")
        n = criteria.get("n", 5)

        sorted_whales = sorted(
            all_whales,
            key=lambda w: w.get(sort_by, 0),
            reverse=True
        )
        return sorted_whales[:n]

    elif criteria["type"] == "filter":
        # Filter whales by criteria
        return [w for w in all_whales if check_whale_matches_strategy(w, strategy)]

    return []


def copy_trade_to_strategy(strategy_id: str, trade_data: dict, whale_data: dict):
    """Copy a whale trade to a strategy's paper trading account"""
    global strategies

    if strategy_id not in strategies:
        return {"error": "Strategy not found"}

    strategy = strategies[strategy_id]

    if not strategy["active"]:
        return {"error": "Strategy not active"}

    account = strategy["account"]
    position_sizing = strategy["position_sizing"]

    # Calculate position size based on strategy rules
    quality_factor = whale_data.get("quality_score", 50) / 100.0
    trade_size_ratio = min(trade_data.get("amount", 100) / 1000.0, 2.0)

    position_size = account["balance"] * (position_sizing["base_pct"] / 100.0) * quality_factor * trade_size_ratio
    position_size = min(position_size, account["balance"] * (position_sizing["max_pct"] / 100.0))

    if position_size > account["balance"]:
        return {"error": "Insufficient balance"}

    # Create paper trade entry
    paper_trade = {
        "id": len(account["trades"]) + 1,
        "strategy_id": strategy_id,
        "whale_address": trade_data.get("trader_address"),
        "whale_pseudonym": whale_data.get("pseudonym", "Unknown"),
        "market_id": trade_data.get("market_id"),
        "side": trade_data.get("side"),
        "outcome": trade_data.get("outcome"),
        "amount": position_size,
        "price": trade_data.get("price"),
        "timestamp": trade_data.get("timestamp", datetime.utcnow().isoformat()),
        "pnl": 0.0,
        "status": "open"
    }

    # Update account
    account["trades"].append(paper_trade)
    account["balance"] -= position_size

    # Store position
    position_key = f"{trade_data.get('market_id')}_{trade_data.get('outcome')}"
    account["positions"][position_key] = paper_trade

    logger.info(f"Strategy '{strategy['name']}' copied trade: ${position_size:.2f} on {whale_data.get('pseudonym')}")

    return {
        "success": True,
        "strategy": strategy["name"],
        "trade": paper_trade,
        "new_balance": account["balance"]
    }


# Trading settings (can be modified via API)
trading_settings = {
    "paper_trading": {
        "initial_balance": 10000.0,
        "max_position_size_pct": 10.0,  # Max 10% per trade
        "base_position_size_pct": 5.0,   # Base 5% per trade
        "min_quality_score": 50.0,        # Minimum whale quality to copy
        "kelly_fraction": 0.25,           # Quarter-Kelly sizing
        "max_trade_size_ratio": 2.0,      # Max 2x whale's average trade
    },
    "whale_filters": {
        "min_win_rate": 55.0,
        "min_sharpe": 1.0,
        "min_total_volume": 50000.0,
        "copy_only_mega_high": False,     # If true, only copy MEGA/HIGH tier
    },
    "risk_management": {
        "stop_loss_pct": 15.0,
        "take_profit_pct": 30.0,
        "max_daily_loss": 500.0,
        "circuit_breaker_loss_pct": 5.0,
    }
}

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Redirect to dashboard"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Serve the dashboard HTML"""
    import os
    html_path = os.path.join(os.path.dirname(__file__), "static", "dashboard.html")
    with open(html_path, 'r') as f:
        return f.read()


@app.get("/api/whales")
async def get_whales():
    """Get qualified whales with real-time 24h metrics"""
    with Session(engine) as session:
        # Get qualified whales (same criteria as stats)
        whales = session.execute(
            select(Whale)
            .where(
                Whale.quality_score >= 70.0,
                Whale.total_trades >= 20,
                Whale.total_volume >= 10000,
                Whale.win_rate >= 52.0,
                Whale.sharpe_ratio >= 0.8
            )
            .order_by(desc(Whale.quality_score))
        ).scalars().all()

        # Calculate 24h trade counts for each whale
        yesterday = datetime.utcnow() - timedelta(days=1)

        result = []
        for w in whales:
            # Count trades in last 24h for this whale
            trades_24h_count = session.execute(
                select(func.count()).select_from(Trade)
                .where(
                    Trade.trader_address == w.address,
                    Trade.timestamp >= yesterday
                )
            ).scalar()

            result.append({
                "address": w.address,
                "pseudonym": w.pseudonym or f"{w.address[:6]}...{w.address[-4:]}",
                "tier": w.tier or "MEDIUM",
                "quality_score": float(w.quality_score) if w.quality_score else 0,
                "total_volume": float(w.total_volume) if w.total_volume else 0,
                "total_trades": w.total_trades or 0,
                "win_rate": float(w.win_rate) if w.win_rate else 0,
                "sharpe_ratio": float(w.sharpe_ratio) if w.sharpe_ratio else 0,
                "total_pnl": float(w.total_pnl) if w.total_pnl else 0,
                "is_copying_enabled": w.is_copying_enabled,
                "profile_url": f"https://polymarket.com/profile/{w.address}",
                "last_active": w.last_active.isoformat() if w.last_active else None,
                # Real-time 24h metrics
                "trades_24h": trades_24h_count or 0,
                "volume_24h": float(w.volume_24h) if w.volume_24h else 0,
                "active_trades": w.active_trades or 0,
                "most_recent_trade_at": w.most_recent_trade_at.isoformat() if w.most_recent_trade_at else None,
                "last_trade_check_at": w.last_trade_check_at.isoformat() if w.last_trade_check_at else None
            })

        return result


@app.get("/api/trades")
async def get_trades(limit: int = 50):
    """Get recent trades from qualified active whales only"""
    with Session(engine) as session:
        # First, get addresses of all qualified whales
        qualified_whale_addresses = session.execute(
            select(Whale.address)
            .where(
                Whale.quality_score >= 70.0,
                Whale.total_trades >= 20,
                Whale.total_volume >= 10000,
                Whale.win_rate >= 52.0,
                Whale.sharpe_ratio >= 0.8
            )
        ).scalars().all()

        if not qualified_whale_addresses:
            return []  # No qualified whales, return empty list

        # Get trades only from qualified whales
        trades = session.execute(
            select(Trade)
            .where(Trade.trader_address.in_(qualified_whale_addresses))
            .order_by(desc(Trade.timestamp))
            .limit(limit)
        ).scalars().all()

        # Get whale information for each trade
        result = []
        for t in trades:
            # Fetch whale info
            whale = session.execute(
                select(Whale).where(Whale.address == t.trader_address)
            ).scalar_one_or_none()

            # Format whale name: use pseudonym if available and not just an address
            if whale and whale.pseudonym:
                # Check if pseudonym is actually just the address (0x...)
                if whale.pseudonym.startswith('0x') and len(whale.pseudonym) > 20:
                    # It's an address stored as pseudonym, truncate it
                    whale_display_name = f"{whale.pseudonym[:6]}...{whale.pseudonym[-4:]}"
                else:
                    # Real pseudonym, use it
                    whale_display_name = whale.pseudonym
            else:
                # No whale record or no pseudonym, truncate address
                addr = t.trader_address
                whale_display_name = f"{addr[:6]}...{addr[-4:]}" if len(addr) > 10 else addr

            # Format market title: use stored title or show "Market {id[:8]}"
            if t.market_title:
                market_display = t.market_title
            else:
                market_id_str = str(t.market_id) if t.market_id else ""
                market_display = f"Market {market_id_str[:8]}..." if len(market_id_str) > 8 else f"Market {market_id_str}"

            result.append({
                "id": t.trade_id,
                "trader_address": t.trader_address,
                "whale_name": whale_display_name,
                "market_id": t.market_id if t.market_id else "",
                "market_title": market_display,
                "side": t.side,
                "size": float(t.size) if t.size else 0,
                "price": float(t.price) if t.price else 0,
                "amount": float(t.amount) if t.amount else 0,
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                "followed": t.followed
            })

        return result


@app.get("/api/paper-trading/portfolio")
async def get_paper_portfolio():
    """Get current paper trading portfolio"""
    return paper_portfolio


@app.get("/api/paper-trading/performance")
async def get_paper_performance():
    """Get paper trading performance metrics"""
    if not paper_portfolio["trades"]:
        return {
            "total_trades": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "roi": 0
        }

    total_trades = len(paper_portfolio["trades"])
    winning_trades = sum(1 for t in paper_portfolio["trades"] if t.get("pnl", 0) > 0)
    total_pnl = sum(t.get("pnl", 0) for t in paper_portfolio["trades"])

    return {
        "total_trades": total_trades,
        "win_rate": (winning_trades / total_trades * 100) if total_trades > 0 else 0,
        "total_pnl": total_pnl,
        "roi": (total_pnl / 10000 * 100),  # Starting balance $10k
        "current_balance": paper_portfolio["balance"]
    }


@app.post("/api/paper-trading/execute")
async def execute_paper_trade(trade_data: dict):
    """Execute a paper trade based on whale activity"""

    # Get whale info for sizing
    with Session(engine) as session:
        whale = session.execute(
            select(Whale).where(Whale.address == trade_data["trader_address"])
        ).scalar_one_or_none()

        if not whale:
            return {"error": "Whale not found"}

        # Calculate position size using simplified Kelly
        # Size = (Quality Score / 100) * (Trade Size / Whale Avg Trade) * Available Balance
        quality_factor = (whale.quality_score or 70) / 100

        # Get whale's average trade size
        avg_trade_result = session.execute(
            select(func.avg(Trade.amount))
            .where(Trade.trader_address == whale.address)
        ).scalar()

        avg_trade_size = float(avg_trade_result) if avg_trade_result else 1000.0
        trade_size_ratio = min(trade_data["amount"] / avg_trade_size, 2.0)  # Cap at 2x avg

        # Position size
        position_size = paper_portfolio["balance"] * 0.05 * quality_factor * trade_size_ratio
        position_size = min(position_size, paper_portfolio["balance"] * 0.10)  # Max 10% per trade

        # Execute trade
        paper_trade = {
            "id": len(paper_portfolio["trades"]) + 1,
            "timestamp": datetime.utcnow().isoformat(),
            "whale_address": trade_data["trader_address"],
            "whale_name": whale.pseudonym,
            "market_id": trade_data["market_id"],
            "side": trade_data["side"],
            "size": position_size / trade_data["price"],
            "price": trade_data["price"],
            "amount": position_size,
            "quality_score": whale.quality_score,
            "sizing_factor": quality_factor * trade_size_ratio,
            "pnl": 0  # Will be calculated on exit
        }

        paper_portfolio["trades"].append(paper_trade)
        paper_portfolio["balance"] -= position_size

        # Update position
        position_key = f"{trade_data['market_id']}_{trade_data['side']}"
        paper_portfolio["positions"][position_key] = paper_trade

        # Broadcast update
        await manager.broadcast({
            "type": "paper_trade_executed",
            "trade": paper_trade
        })

        return {"success": True, "trade": paper_trade}


# ============================================================================
# STRATEGIES API ENDPOINTS
# ============================================================================

@app.get("/api/strategies")
async def get_strategies():
    """Get all available strategies with their current status"""
    result = []
    for strategy_id, strategy in strategies.items():
        account = strategy["account"]

        # Calculate total P&L for strategy
        total_pnl = sum(t.get("pnl", 0) for t in account["trades"])
        account["pnl"] = total_pnl

        # Calculate performance metrics
        total_trades = len(account["trades"])
        winning_trades = sum(1 for t in account["trades"] if t.get("pnl", 0) > 0)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        result.append({
            "id": strategy["id"],
            "name": strategy["name"],
            "description": strategy["description"],
            "active": strategy["active"],
            "criteria": strategy["criteria"],
            "position_sizing": strategy["position_sizing"],
            "account": {
                "balance": account["balance"],
                "initial_balance": account["initial_balance"],
                "total_trades": total_trades,
                "pnl": total_pnl,
                "win_rate": win_rate,
                "roi": (total_pnl / account["initial_balance"] * 100) if account["initial_balance"] > 0 else 0
            }
        })

    return result


@app.post("/api/strategies/{strategy_id}/activate")
async def activate_strategy(strategy_id: str):
    """Activate a strategy for paper trading"""
    global strategies

    if strategy_id not in strategies:
        return {"error": "Strategy not found"}

    strategies[strategy_id]["active"] = True

    logger.info(f"Strategy '{strategies[strategy_id]['name']}' activated")

    return {
        "success": True,
        "strategy_id": strategy_id,
        "strategy_name": strategies[strategy_id]["name"],
        "active": True
    }


@app.post("/api/strategies/{strategy_id}/deactivate")
async def deactivate_strategy(strategy_id: str):
    """Deactivate a strategy"""
    global strategies

    if strategy_id not in strategies:
        return {"error": "Strategy not found"}

    strategies[strategy_id]["active"] = False

    logger.info(f"Strategy '{strategies[strategy_id]['name']}' deactivated")

    return {
        "success": True,
        "strategy_id": strategy_id,
        "strategy_name": strategies[strategy_id]["name"],
        "active": False
    }


@app.post("/api/strategies/{strategy_id}/reset")
async def reset_strategy(strategy_id: str):
    """Reset a strategy's paper trading account"""
    global strategies

    if strategy_id not in strategies:
        return {"error": "Strategy not found"}

    strategy = strategies[strategy_id]
    initial_balance = strategy["account"]["initial_balance"]

    strategy["account"] = {
        "balance": initial_balance,
        "positions": {},
        "trades": [],
        "pnl": 0.0,
        "initial_balance": initial_balance
    }

    logger.info(f"Strategy '{strategy['name']}' reset to initial balance ${initial_balance}")

    return {
        "success": True,
        "strategy_id": strategy_id,
        "strategy_name": strategy["name"],
        "new_balance": initial_balance
    }


@app.get("/api/strategies/{strategy_id}/whales")
async def get_strategy_whales(strategy_id: str):
    """Get the list of whales that match a strategy's criteria"""
    if strategy_id not in strategies:
        return {"error": "Strategy not found"}

    strategy = strategies[strategy_id]

    # Get all qualified whales
    with Session(engine) as session:
        whales = session.execute(
            select(Whale)
            .where(
                Whale.quality_score >= 70.0,
                Whale.total_trades >= 20,
                Whale.total_volume >= 10000,
                Whale.win_rate >= 52.0,
                Whale.sharpe_ratio >= 0.8
            )
            .order_by(desc(Whale.quality_score))
        ).scalars().all()

        # Convert to dict format
        all_whales = []
        for w in whales:
            all_whales.append({
                "address": w.address,
                "pseudonym": w.pseudonym or f"{w.address[:6]}...{w.address[-4:]}",
                "quality_score": float(w.quality_score) if w.quality_score else 0,
                "win_rate": float(w.win_rate) if w.win_rate else 0,
                "sharpe_ratio": float(w.sharpe_ratio) if w.sharpe_ratio else 0,
                "total_pnl": float(w.total_pnl) if w.total_pnl else 0,
                "total_trades": w.total_trades or 0,
                "total_volume": float(w.total_volume) if w.total_volume else 0
            })

    # Filter whales based on strategy criteria
    matching_whales = filter_whales_by_strategy(strategy, all_whales)

    return {
        "strategy_id": strategy_id,
        "strategy_name": strategy["name"],
        "matching_whales": matching_whales,
        "total_matching": len(matching_whales)
    }


@app.post("/api/strategies/copy-trade")
async def copy_trade_to_strategies(trade_data: dict):
    """Copy a whale trade to all active strategies that match"""
    results = []

    # Get whale data
    with Session(engine) as session:
        whale = session.execute(
            select(Whale).where(Whale.address == trade_data["trader_address"])
        ).scalar_one_or_none()

        if not whale:
            return {"error": "Whale not found"}

        whale_data = {
            "address": whale.address,
            "pseudonym": whale.pseudonym or f"{whale.address[:6]}...{whale.address[-4:]}",
            "quality_score": float(whale.quality_score) if whale.quality_score else 0,
            "win_rate": float(whale.win_rate) if whale.win_rate else 0,
            "sharpe_ratio": float(whale.sharpe_ratio) if whale.sharpe_ratio else 0,
            "total_pnl": float(whale.total_pnl) if whale.total_pnl else 0
        }

    # Get all qualified whales for strategy matching
    with Session(engine) as session:
        whales = session.execute(
            select(Whale)
            .where(
                Whale.quality_score >= 70.0,
                Whale.total_trades >= 20,
                Whale.total_volume >= 10000,
                Whale.win_rate >= 52.0,
                Whale.sharpe_ratio >= 0.8
            )
        ).scalars().all()

        all_whales_dict = []
        for w in whales:
            all_whales_dict.append({
                "address": w.address,
                "quality_score": float(w.quality_score) if w.quality_score else 0,
                "win_rate": float(w.win_rate) if w.win_rate else 0,
                "sharpe_ratio": float(w.sharpe_ratio) if w.sharpe_ratio else 0,
                "total_pnl": float(w.total_pnl) if w.total_pnl else 0
            })

    # Copy trade to each active strategy that matches
    for strategy_id, strategy in strategies.items():
        if not strategy["active"]:
            continue

        # Check if whale matches this strategy's criteria
        matching_whales = filter_whales_by_strategy(strategy, all_whales_dict)
        whale_addresses = [w["address"] for w in matching_whales]

        if whale_data["address"] in whale_addresses:
            result = copy_trade_to_strategy(strategy_id, trade_data, whale_data)
            results.append({
                "strategy_id": strategy_id,
                "strategy_name": strategy["name"],
                "result": result
            })

    return {
        "success": True,
        "whale": whale_data["pseudonym"],
        "strategies_copied": len(results),
        "details": results
    }


# ============================================================================
# WEBSOCKET FOR REAL-TIME UPDATES
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time trade updates"""
    await manager.connect(websocket)

    try:
        # Send initial data
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to whale tracker"
        })

        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_text()
            # Echo back for now
            await websocket.send_json({
                "type": "ack",
                "received": data
            })

    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/api/stats/summary")
async def get_summary_stats():
    """Get dashboard summary statistics with real database values"""
    with Session(engine) as session:
        # Total qualified whales (WQS >= 70, trades >= 20, volume >= $10K)
        total_whales = session.execute(
            select(func.count()).select_from(Whale)
            .where(
                Whale.quality_score >= 70.0,
                Whale.total_trades >= 20,
                Whale.total_volume >= 10000,
                Whale.win_rate >= 52.0,
                Whale.sharpe_ratio >= 0.8
            )
        ).scalar()

        # Recent trades (last 24h) - from ALL trades
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_trades = session.execute(
            select(func.count()).select_from(Trade)
            .where(Trade.timestamp >= yesterday)
        ).scalar()

        # Total volume (last 24h) - from ALL trades
        volume_24h = session.execute(
            select(func.sum(Trade.amount))
            .where(Trade.timestamp >= yesterday)
        ).scalar()

        return {
            "total_whales": total_whales or 0,
            "trades_24h": recent_trades or 0,
            "volume_24h": float(volume_24h) if volume_24h else 0.0,
            "paper_balance": paper_portfolio["balance"],
            "paper_pnl": paper_portfolio["pnl"]
        }


@app.get("/api/settings")
async def get_settings():
    """Get current trading settings"""
    return trading_settings


@app.put("/api/settings")
async def update_settings(new_settings: dict):
    """Update trading settings"""
    global trading_settings

    # Update settings
    for category, values in new_settings.items():
        if category in trading_settings:
            trading_settings[category].update(values)

    # Reset paper trading if initial balance changed
    if "paper_trading" in new_settings and "initial_balance" in new_settings["paper_trading"]:
        paper_portfolio["balance"] = new_settings["paper_trading"]["initial_balance"]
        paper_portfolio["positions"] = {}
        paper_portfolio["trades"] = []
        paper_portfolio["pnl"] = 0.0

    return {"success": True, "settings": trading_settings}


@app.post("/api/settings/reset")
async def reset_settings():
    """Reset settings to defaults"""
    global trading_settings, paper_portfolio

    trading_settings = {
        "paper_trading": {
            "initial_balance": 10000.0,
            "max_position_size_pct": 10.0,
            "base_position_size_pct": 5.0,
            "min_quality_score": 50.0,
            "kelly_fraction": 0.25,
            "max_trade_size_ratio": 2.0,
        },
        "whale_filters": {
            "min_win_rate": 55.0,
            "min_sharpe": 1.0,
            "min_total_volume": 50000.0,
            "copy_only_mega_high": False,
        },
        "risk_management": {
            "stop_loss_pct": 15.0,
            "take_profit_pct": 30.0,
            "max_daily_loss": 500.0,
            "circuit_breaker_loss_pct": 5.0,
        }
    }

    # Reset paper trading
    paper_portfolio = {
        "balance": 10000.0,
        "positions": {},
        "trades": [],
        "pnl": 0.0
    }

    return {"success": True, "settings": trading_settings}


# ============================================================================
# SYSTEM CONTROL ENDPOINTS
# ============================================================================

# Initialize system manager
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'services'))
    from system_manager import system_manager
    SYSTEM_AVAILABLE = True
except ImportError as e:
    logger.warning(f"System manager not available: {e}")
    SYSTEM_AVAILABLE = False
    system_manager = None

# Initialize live trader
try:
    from simple_live_trader import trader as live_trader
    LIVE_TRADER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Live trader not available: {e}")
    LIVE_TRADER_AVAILABLE = False
    live_trader = None


@app.post("/api/system/start")
async def start_system():
    """Start the monitoring system (trade monitor + metrics updater)."""
    if not SYSTEM_AVAILABLE or not system_manager:
        return {"success": False, "error": "System manager not available"}

    success = system_manager.start()
    return {
        "success": success,
        "message": "System started successfully" if success else "System already running",
        "status": system_manager.get_status()
    }


@app.post("/api/system/stop")
async def stop_system():
    """Stop the monitoring system."""
    if not SYSTEM_AVAILABLE or not system_manager:
        return {"success": False, "error": "System manager not available"}

    success = system_manager.stop()
    return {
        "success": success,
        "message": "System stopped successfully" if success else "System not running",
        "status": system_manager.get_status()
    }


@app.get("/api/system/status")
async def get_system_status():
    """Get current system status."""
    if not SYSTEM_AVAILABLE or not system_manager:
        return {
            "running": False,
            "available": False,
            "error": "System manager not available"
        }

    return system_manager.get_status()


# ============================================================================
# LIVE TRADING CONTROL ENDPOINTS
# ============================================================================

@app.get("/api/trading/mode")
async def get_trading_mode():
    """Get current trading mode (paper or live)."""
    if not LIVE_TRADER_AVAILABLE or not live_trader:
        return {
            "mode": "paper",
            "available": False,
            "error": "Live trader not available"
        }

    status = live_trader.get_status()
    return {
        "mode": status['mode'].lower(),
        "available": True,
        "status": status
    }


@app.post("/api/trading/mode")
async def set_trading_mode(request: dict):
    """
    Set trading mode to paper or live.

    Body: {"mode": "paper"} or {"mode": "live"}
    """
    if not LIVE_TRADER_AVAILABLE or not live_trader:
        return {
            "success": False,
            "error": "Live trader not available"
        }

    mode = request.get("mode", "paper").lower()

    if mode == "live":
        live_trader.enable_live_mode()
    else:
        live_trader.disable_live_mode()

    status = live_trader.get_status()

    return {
        "success": True,
        "mode": status['mode'].lower(),
        "status": status
    }


@app.get("/api/trading/status")
async def get_trading_status():
    """Get detailed trading status including safety limits."""
    if not LIVE_TRADER_AVAILABLE or not live_trader:
        return {
            "available": False,
            "error": "Live trader not available"
        }

    return {
        "available": True,
        "status": live_trader.get_status()
    }


# ============================================================================
# BACKTESTING ENDPOINTS
# ============================================================================

class BacktestRequest(BaseModel):
    """Request model for running a backtest."""
    starting_balance: float = 1000.0
    max_position_usd: float = 100.0
    max_daily_loss: float = 500.0
    min_whale_quality: int = 50
    position_size_pct: float = 0.05
    days_back: int = 30  # How many days of history to test
    whale_addresses: list = None  # Optional: specific whales to test


@app.post("/api/backtest/run")
async def run_backtest(request: BacktestRequest):
    """
    Run a backtest simulation with the specified parameters.

    This simulates copy trading strategy against historical whale trades
    to evaluate performance without risking real money.
    """
    if not BACKTESTER_AVAILABLE or not Backtester or not BacktestConfig:
        return {
            "success": False,
            "error": "Backtester not available"
        }

    try:
        # Create backtest config
        config = BacktestConfig(
            starting_balance=Decimal(str(request.starting_balance)),
            max_position_usd=Decimal(str(request.max_position_usd)),
            max_daily_loss=Decimal(str(request.max_daily_loss)),
            min_whale_quality=request.min_whale_quality,
            position_size_pct=Decimal(str(request.position_size_pct)),
            start_date=datetime.utcnow() - timedelta(days=request.days_back),
            whale_addresses=request.whale_addresses
        )

        # Run backtest
        backtester = Backtester(config)
        result = backtester.run_backtest()

        # Format results for JSON
        return {
            "success": True,
            "results": {
                "performance": {
                    "starting_balance": float(result.starting_balance),
                    "ending_balance": float(result.ending_balance),
                    "total_pnl": float(result.total_pnl),
                    "total_pnl_pct": float(result.total_pnl_pct),
                },
                "statistics": {
                    "total_trades": result.total_trades,
                    "winning_trades": result.winning_trades,
                    "losing_trades": result.losing_trades,
                    "win_rate": result.win_rate,
                },
                "risk_metrics": {
                    "max_drawdown": float(result.max_drawdown),
                    "max_drawdown_pct": float(result.max_drawdown_pct),
                    "sharpe_ratio": result.sharpe_ratio,
                },
                "period": {
                    "start_date": result.start_date.isoformat() if result.start_date else None,
                    "end_date": result.end_date.isoformat() if result.end_date else None,
                    "days": result.days,
                },
                "daily_pnl": {
                    date: float(pnl) for date, pnl in result.daily_pnl.items()
                },
                "balance_history": result.balance_history,
                "whale_performance": {
                    addr: {
                        "pseudonym": perf["pseudonym"],
                        "trades": perf["trades"],
                        "wins": perf["wins"],
                        "win_rate": (perf["wins"] / perf["trades"] * 100) if perf["trades"] > 0 else 0,
                        "total_pnl": float(perf["total_pnl"]),
                        "quality": perf["quality"]
                    }
                    for addr, perf in result.whale_performance.items()
                },
                "all_trades": [
                    {
                        "timestamp": trade.timestamp.isoformat(),
                        "whale_pseudonym": trade.whale_pseudonym,
                        "whale_quality": trade.whale_quality,
                        "market_title": trade.market_title,
                        "side": trade.side,
                        "outcome": trade.outcome,
                        "price": float(trade.price),
                        "position_size": float(trade.position_size),
                        "realized_pnl": float(trade.realized_pnl)
                    }
                    for trade in result.trades  # All trades
                ]
            }
        }

    except Exception as e:
        logger.error(f"Error running backtest: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/backtest/status")
async def get_backtest_status():
    """Check if backtesting is available."""
    return {
        "available": BACKTESTER_AVAILABLE,
        "default_config": {
            "starting_balance": 1000.0,
            "max_position_usd": 100.0,
            "max_daily_loss": 500.0,
            "min_whale_quality": 50,
            "position_size_pct": 0.05,
            "days_back": 30
        }
    }


# ============================================================================
# AGENT ENDPOINTS
# ============================================================================

@app.get("/api/agents")
async def get_agents():
    """Get list of all available agents with their status"""
    agents = [
        {
            "id": "whale_discovery",
            "name": "Whale Discovery Agent",
            "description": "Discovers and tracks high-performing whale traders",
            "status": "active",
            "capabilities": ["discover_whales", "analyze_performance", "rank_traders"]
        },
        {
            "id": "risk_management",
            "name": "Risk Management Agent",
            "description": "Monitors and manages portfolio risk exposure",
            "status": "active",
            "capabilities": ["check_position_limits", "calculate_var", "stop_loss_monitoring"]
        },
        {
            "id": "market_intelligence",
            "name": "Market Intelligence Agent",
            "description": "Analyzes market conditions and sentiment",
            "status": "active",
            "capabilities": ["market_analysis", "sentiment_scoring", "liquidity_assessment"]
        },
        {
            "id": "execution",
            "name": "Execution Agent",
            "description": "Executes trades with optimal timing and pricing",
            "status": "active",
            "capabilities": ["execute_trade", "split_orders", "slippage_management"]
        },
        {
            "id": "performance_attribution",
            "name": "Performance Attribution Agent",
            "description": "Analyzes P&L attribution across whale strategies",
            "status": "active",
            "capabilities": ["shapley_analysis", "contribution_tracking", "strategy_optimization"]
        },
        {
            "id": "orchestrator",
            "name": "Orchestrator Agent",
            "description": "Coordinates all agents and manages workflow",
            "status": "active",
            "capabilities": ["task_scheduling", "agent_coordination", "circuit_breaking"]
        }
    ]
    return {"agents": agents}


@app.get("/api/agents/{agent_id}")
async def get_agent_details(agent_id: str):
    """Get detailed information about a specific agent"""

    agent_details = {
        "whale_discovery": {
            "id": "whale_discovery",
            "name": "Whale Discovery Agent",
            "description": "Discovers and tracks high-performing whale traders using on-chain and off-chain data sources",
            "status": "active",
            "health": "healthy",
            "last_run": datetime.now().isoformat(),
            "metrics": {
                "whales_discovered": 50,
                "avg_quality_score": 72.5,
                "discovery_rate": "5 per day"
            },
            "capabilities": [
                {"name": "discover_whales", "description": "Find new whale traders"},
                {"name": "analyze_performance", "description": "Analyze historical trading performance"},
                {"name": "rank_traders", "description": "Rank traders by quality score"}
            ]
        },
        "risk_management": {
            "id": "risk_management",
            "name": "Risk Management Agent",
            "description": "Monitors and manages portfolio risk exposure using VaR, position limits, and stop-loss rules",
            "status": "active",
            "health": "healthy",
            "last_run": datetime.now().isoformat(),
            "metrics": {
                "current_var": "$250",
                "position_utilization": "45%",
                "max_drawdown": "8.5%"
            },
            "capabilities": [
                {"name": "check_position_limits", "description": "Verify position sizes within limits"},
                {"name": "calculate_var", "description": "Calculate Value at Risk"},
                {"name": "stop_loss_monitoring", "description": "Monitor and trigger stop losses"}
            ]
        },
        "market_intelligence": {
            "id": "market_intelligence",
            "name": "Market Intelligence Agent",
            "description": "Analyzes market conditions, sentiment, and liquidity using real-time data",
            "status": "active",
            "health": "healthy",
            "last_run": datetime.now().isoformat(),
            "metrics": {
                "markets_monitored": 120,
                "sentiment_score": 0.62,
                "avg_liquidity": "$45K"
            },
            "capabilities": [
                {"name": "market_analysis", "description": "Analyze market conditions"},
                {"name": "sentiment_scoring", "description": "Score market sentiment"},
                {"name": "liquidity_assessment", "description": "Assess market liquidity"}
            ]
        },
        "execution": {
            "id": "execution",
            "name": "Execution Agent",
            "description": "Executes trades with optimal timing, pricing, and minimal slippage",
            "status": "active",
            "health": "healthy",
            "last_run": datetime.now().isoformat(),
            "metrics": {
                "trades_executed": 156,
                "avg_slippage": "0.25%",
                "success_rate": "98.7%"
            },
            "capabilities": [
                {"name": "execute_trade", "description": "Execute market orders"},
                {"name": "split_orders", "description": "Split large orders to reduce impact"},
                {"name": "slippage_management", "description": "Minimize execution slippage"}
            ]
        },
        "performance_attribution": {
            "id": "performance_attribution",
            "name": "Performance Attribution Agent",
            "description": "Analyzes P&L attribution using Shapley values and contribution tracking",
            "status": "active",
            "health": "healthy",
            "last_run": datetime.now().isoformat(),
            "metrics": {
                "total_pnl": "$3,250",
                "best_whale_contribution": "35%",
                "sharpe_ratio": 1.85
            },
            "capabilities": [
                {"name": "shapley_analysis", "description": "Calculate Shapley value contributions"},
                {"name": "contribution_tracking", "description": "Track whale contributions to P&L"},
                {"name": "strategy_optimization", "description": "Optimize whale selection strategy"}
            ]
        },
        "orchestrator": {
            "id": "orchestrator",
            "name": "Orchestrator Agent",
            "description": "Master coordinator that manages all agents, schedules tasks, and handles circuit breaking",
            "status": "active",
            "health": "healthy",
            "last_run": datetime.now().isoformat(),
            "metrics": {
                "tasks_scheduled": 1247,
                "agents_managed": 5,
                "circuit_breakers": 0
            },
            "capabilities": [
                {"name": "task_scheduling", "description": "Schedule and prioritize agent tasks"},
                {"name": "agent_coordination", "description": "Coordinate multi-agent workflows"},
                {"name": "circuit_breaking", "description": "Manage circuit breaker states"}
            ]
        }
    }

    if agent_id not in agent_details:
        return {"error": "Agent not found"}

    return agent_details[agent_id]


@app.post("/api/agents/{agent_id}/execute")
async def execute_agent_task(agent_id: str, task_data: dict):
    """Trigger a specific agent task"""

    # Placeholder for agent execution
    # In production, this would actually invoke the agent

    return {
        "success": True,
        "agent_id": agent_id,
        "task": task_data.get("task", "default"),
        "message": f"Task submitted to {agent_id}",
        "execution_id": f"exec_{agent_id}_{int(datetime.now().timestamp())}"
    }


@app.get("/api/agents/{agent_id}/health")
async def get_agent_health(agent_id: str):
    """Get health status of a specific agent"""

    return {
        "agent_id": agent_id,
        "status": "healthy",
        "uptime": "99.8%",
        "last_heartbeat": datetime.now().isoformat(),
        "errors": 0,
        "warnings": 0
    }


if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*80)
    print("🐋 WHALE TRACKER DASHBOARD API")
    print("="*80)
    print(f"Dashboard: http://localhost:8000/dashboard")
    print(f"API Docs:  http://localhost:8000/docs")
    print("="*80 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)

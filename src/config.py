"""
Configuration management for Polymarket Copy Trading System
"""
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, ConfigDict
from typing import List, Optional
import os
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Environment
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")

    # Database
    DATABASE_URL: str = Field(
        default="postgresql://trader:changeme123@localhost:5432/polymarket_trader"
    )
    DB_POOL_SIZE: int = Field(default=10)
    DB_MAX_OVERFLOW: int = Field(default=20)

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_MAX_CONNECTIONS: int = Field(default=50)

    # Kafka
    KAFKA_BROKERS: str = Field(default="localhost:9092")
    KAFKA_GROUP_ID: str = Field(default="polymarket-trader")

    # RabbitMQ
    RABBITMQ_URL: str = Field(
        default="amqp://trader:changeme123@localhost:5672"
    )

    # Polymarket API
    POLYMARKET_API_KEY: str = Field(default="")
    POLYMARKET_SECRET: str = Field(default="")
    POLYMARKET_PASSPHRASE: str = Field(default="")
    POLYMARKET_API_URL: str = Field(default="https://clob.polymarket.com")
    POLYMARKET_DATA_API_URL: str = Field(default="https://data-api.polymarket.com")
    POLYMARKET_WS_URL: str = Field(
        default="wss://ws-subscriptions-clob.polymarket.com/ws/"
    )

    # Blockchain
    PRIVATE_KEY: str = Field(default="")
    WALLET_ADDRESS: str = Field(default="")
    POLYGON_RPC: str = Field(default="https://polygon-rpc.com")
    CHAIN_ID: int = Field(default=137)  # Polygon mainnet

    # Trading Capital
    INITIAL_CAPITAL: float = Field(default=10000.0)

    # Risk Limits
    MAX_POSITION_SIZE: float = Field(default=1000.0, description="Max $ per position")
    MAX_TOTAL_EXPOSURE: float = Field(
        default=10000.0, description="Max total portfolio exposure"
    )
    MAX_DAILY_LOSS: float = Field(
        default=500.0, description="Circuit breaker - max daily loss"
    )
    MAX_DRAWDOWN_PCT: float = Field(
        default=20.0, description="Max portfolio drawdown %"
    )
    MAX_ORDERS_PER_MINUTE: int = Field(default=10)
    MAX_WHALE_ALLOCATION: float = Field(
        default=0.30, description="Max % allocated to single whale"
    )

    # Position Sizing
    KELLY_FRACTION: float = Field(
        default=0.25, description="Kelly multiplier (0.25 = quarter-Kelly)"
    )
    STOP_LOSS_PCT: float = Field(default=0.15, description="15% stop-loss")
    TAKE_PROFIT_PCT: float = Field(default=0.30, description="30% take-profit")

    # Market Filters
    MIN_MARKET_LIQUIDITY: float = Field(
        default=50000.0, description="Min 24hr volume"
    )
    MAX_BID_ASK_SPREAD: float = Field(default=0.03, description="Max 3% spread")
    PRE_RESOLUTION_EXIT_HOURS: float = Field(
        default=2.5, description="Exit positions N hours before resolution"
    )

    # Whale Selection
    MIN_WHALE_WIN_RATE: float = Field(default=0.65)
    MIN_WHALE_SHARPE: float = Field(default=1.0)
    MIN_WHALE_TRADES: int = Field(default=20, description="Min historical trades")
    WHALE_SCORE_THRESHOLD: float = Field(default=70.0)
    MAX_WHALES_TO_FOLLOW: int = Field(default=50)

    # Statistical Parameters
    EWMA_HALF_LIFE_DAYS: int = Field(
        default=30, description="EWMA half-life for metrics"
    )
    SHARPE_CONFIDENCE_LEVEL: float = Field(
        default=0.95, description="Confidence level for Sharpe CI"
    )
    BOOTSTRAP_ITERATIONS: int = Field(default=1000)

    # Performance Windows
    ROLLING_WINDOW_DAYS: List[int] = Field(default=[7, 30, 90])

    # Monitoring
    PROMETHEUS_PORT: int = Field(default=8000)
    METRICS_UPDATE_INTERVAL: int = Field(default=60, description="Seconds")
    POSITION_SYNC_INTERVAL: int = Field(default=300, description="Seconds (5 min)")

    # Sentry
    SENTRY_DSN: Optional[str] = Field(default=None)

    @field_validator("PRIVATE_KEY", "WALLET_ADDRESS", "POLYMARKET_API_KEY")
    @classmethod
    def check_required_in_production(cls, v, info):
        """Ensure critical fields are set in production"""
        env = os.getenv("ENVIRONMENT", "development")
        if env == "production" and not v:
            raise ValueError(f"{info.field_name} is required in production")
        return v

    @field_validator("KELLY_FRACTION")
    @classmethod
    def validate_kelly_fraction(cls, v):
        """Kelly fraction must be between 0 and 1"""
        if not 0 < v <= 1:
            raise ValueError("KELLY_FRACTION must be between 0 and 1")
        return v

    @field_validator("MAX_WHALE_ALLOCATION")
    @classmethod
    def validate_whale_allocation(cls, v):
        """Max whale allocation must be between 0 and 1"""
        if not 0 < v <= 1:
            raise ValueError("MAX_WHALE_ALLOCATION must be between 0 and 1")
        return v

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"  # Allow extra fields from .env not defined in model
    )


# Global settings instance
settings = Settings()


# Ensure log directory exists
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

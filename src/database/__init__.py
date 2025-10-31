"""
Database module for Polymarket Copy Trading System
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Generator
import logging

from src.config import settings
from src.database.models import Base

logger = logging.getLogger(__name__)


# Create engine with connection pooling
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,  # Verify connections before using
    echo=settings.ENVIRONMENT == "development",
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database - create all tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Context manager for database sessions

    Usage:
        with get_db() as db:
            whales = db.query(Whale).all()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_session() -> Session:
    """
    Get a database session (for dependency injection)

    Usage with FastAPI:
        @app.get("/whales")
        def get_whales(db: Session = Depends(get_db_session)):
            return db.query(Whale).all()
    """
    return SessionLocal()


__all__ = [
    "engine",
    "SessionLocal",
    "init_db",
    "get_db",
    "get_db_session",
    "Base",
]

"""
Database engine, session factory, and dependency injection for FastAPI.
Uses connection pool tuning for production resilience.
"""

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from shared_core.config import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()

engine = create_engine(
    _settings.db.url,
    pool_size=_settings.db.pool_size,
    max_overflow=_settings.db.max_overflow,
    pool_pre_ping=_settings.db.pool_pre_ping,
    echo=_settings.db.echo,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

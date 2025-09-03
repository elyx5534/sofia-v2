"""
Sofia V2 - Database Configuration
Database connection and session management
"""

import os

from sqlalchemy.ext.declarative import declarative_base

from src.adapters.db.sqlalchemy_adapter import Session, create_engine, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sofia.db")
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Session:
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

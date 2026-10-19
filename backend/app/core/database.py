from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.app.core.config import settings

# Create SQLAlchemy engine with connection health check (pool_pre_ping=True)
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False
)

# Session factory for DB transactions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for SQLAlchemy ORM models
Base = declarative_base()

def get_db():
    """FastAPI dependency to yield database sessions per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./atliq_hr.db",
)

# SQLite needs this option for connections used across normal
# application threads. It does not make sessions thread-safe.
connect_args = (
    {"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {}
)

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy database models."""
    pass


def init_db() -> None:
    """Create database tables for the declared models."""
    from hrms import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db():
    """Provide a database session and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

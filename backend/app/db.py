from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import get_settings

settings = get_settings()

_is_sqlite = settings.database_url.startswith("sqlite")

if _is_sqlite:
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
    )
    from sqlalchemy import inspect as _inspect

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()
else:
    engine = create_engine(
        settings.database_url,
        pool_size=10,
        max_overflow=5,
        pool_pre_ping=True,
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create tables if the database is SQLite (desktop standalone mode)."""
    if not _is_sqlite:
        return
    from . import models as _models  # noqa: F401  (register models)

    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
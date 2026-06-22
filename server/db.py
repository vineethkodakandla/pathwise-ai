"""
Database session management for multi-tenant features.
Uses PostgreSQL/TimescaleDB when available, falls back to SQLite for local dev.
"""
import os
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker

# Try PostgreSQL first, fall back to local SQLite
_PG_URL = os.getenv("DATABASE_URL", "postgresql://pathwise:pathwise_dev@localhost:5432/pathwise")
_SQLITE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pathwise_local.db")
_SQLITE_URL = f"sqlite:///{_SQLITE_PATH}"

_engine = None


def _try_pg():
    """Attempt to connect to PostgreSQL. Returns engine or None."""
    try:
        eng = create_engine(_PG_URL, pool_pre_ping=True, pool_size=5,
                            connect_args={"connect_timeout": 3})
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
        return eng
    except Exception:
        return None


def _get_sqlite():
    """Create a SQLite engine as fallback."""
    eng = create_engine(_SQLITE_URL, connect_args={"check_same_thread": False})
    # Enable WAL mode for better concurrency
    @event.listens_for(eng, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    return eng


def get_engine():
    """Get the active database engine (PG or SQLite)."""
    global _engine
    if _engine is None:
        _engine = _try_pg()
        if _engine is None:
            print("[db] PostgreSQL unavailable — using local SQLite at", _SQLITE_PATH)
            _engine = _get_sqlite()
        else:
            print("[db] Connected to PostgreSQL")
    return _engine


def get_db():
    """FastAPI dependency — yields a DB session."""
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


def is_postgres() -> bool:
    """Check if we're using PostgreSQL (vs SQLite)."""
    return "postgresql" in str(get_engine().url)

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import DATABASE_URL

engine = (
    create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        connect_args=(
            {"check_same_thread": False}
            if DATABASE_URL.startswith("sqlite")
            else {}
        ),
    )
    if DATABASE_URL
    else None
)

SessionLocal = (
    sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    if engine is not None
    else None
)


class Base(DeclarativeBase):
    pass


def get_db():
    """Provide a database session to a FastAPI endpoint."""
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured.")

    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import DATABASE_URL

# Utwórz katalog danych dla SQLite jeśli nie istnieje
if DATABASE_URL.startswith("sqlite"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    db_dir = os.path.dirname(os.path.abspath(db_path))
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

connect_args = {}
if "sqlite" in DATABASE_URL:
    connect_args["check_same_thread"] = False
# PostgreSQL doesn't need special connect_args

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

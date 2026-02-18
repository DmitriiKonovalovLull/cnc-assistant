"""
Настройка подключения к базе данных.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.standards.models import Base

# Создаем engine
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=NullPool if "sqlite" in settings.DATABASE_URL else None,
    echo=False
)

# Создаем session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """
    Dependency для FastAPI.
    Получить сессию БД.
    
    Yields:
        SQLAlchemy сессия
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Инициализировать БД (создать таблицы)."""
    Base.metadata.create_all(bind=engine)


def drop_db():
    """Удалить все таблицы (для тестов)."""
    Base.metadata.drop_all(bind=engine)

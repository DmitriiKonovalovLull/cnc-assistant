"""
Пул соединений с базой данных для оптимизации производительности.
"""

import logging
from typing import Optional
from contextlib import contextmanager
from sqlalchemy import create_engine, pool
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)


class DatabasePool:
    """
    Пул соединений с базой данных.
    Управляет переиспользованием соединений для лучшей производительности.
    """
    
    def __init__(
        self,
        db_url: str,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        pool_recycle: int = 3600
    ):
        """
        Инициализация пула соединений.
        
        Args:
            db_url: URL базы данных
            pool_size: Размер пула соединений
            max_overflow: Максимальное количество дополнительных соединений
            pool_timeout: Таймаут ожидания соединения (секунды)
            pool_recycle: Время переиспользования соединения (секунды)
        """
        self.db_url = db_url
        
        # Создаем engine с пулом соединений
        self.engine = create_engine(
            db_url,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
            echo=False,  # Установить True для отладки SQL
            future=True
        )
        
        # Создаем фабрику сессий
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )
        
        logger.info(
            f"Database pool initialized: "
            f"pool_size={pool_size}, max_overflow={max_overflow}"
        )
    
    @contextmanager
    def get_session(self) -> Session:
        """
        Получить сессию из пула (контекстный менеджер).
        
        Example:
            with db_pool.get_session() as session:
                # Использование session
                pass
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_session_direct(self) -> Session:
        """
        Получить сессию напрямую (без контекстного менеджера).
        Не забудьте закрыть сессию!
        
        Returns:
            SQLAlchemy Session
        """
        return self.SessionLocal()
    
    def dispose(self) -> None:
        """Закрыть все соединения в пуле."""
        self.engine.dispose()
        logger.info("Database pool disposed")
    
    def get_pool_status(self) -> dict:
        """Получить статус пула соединений."""
        pool = self.engine.pool
        return {
            'size': pool.size(),
            'checked_in': pool.checkedin(),
            'checked_out': pool.checkedout(),
            'overflow': pool.overflow(),
            'invalid': pool.invalid()
        }

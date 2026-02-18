"""
Конфигурация приложения.
Поддержка режимов: public (только загрузка) и enterprise (API метаданных).
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения."""
    
    # Режим работы
    MODE: str = os.getenv("STANDARDS_MODE", "public")  # public или enterprise
    
    # База данных
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/cnc_assistant"
    )
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_ENABLED: bool = os.getenv("REDIS_ENABLED", "true").lower() == "true"
    
    # Пути
    STANDARDS_STORAGE_DIR: Path = Path(os.getenv("STANDARDS_STORAGE_DIR", "standards_storage"))
    STANDARDS_UPLOAD_DIR: Path = Path(os.getenv("STANDARDS_UPLOAD_DIR", "standards_storage/uploads"))
    
    # Интервал проверки обновлений (дни)
    UPDATE_CHECK_INTERVAL_DAYS: int = int(os.getenv("UPDATE_CHECK_INTERVAL_DAYS", "180"))
    
    # Кэш TTL (часы)
    CACHE_TTL_HOURS: int = int(os.getenv("CACHE_TTL_HOURS", "24"))
    
    # Enterprise API (только для enterprise режима)
    ENTERPRISE_API_URL: Optional[str] = os.getenv("ENTERPRISE_API_URL")
    ENTERPRISE_API_KEY: Optional[str] = os.getenv("ENTERPRISE_API_KEY")
    
    # Логирование
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Создаем директории если их нет
        self.STANDARDS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self.STANDARDS_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()

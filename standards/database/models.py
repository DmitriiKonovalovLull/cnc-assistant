"""
Модели базы данных для системы стандартов.
Production-архитектура: версионирование, хеширование, управляемый каталог.
"""

from datetime import datetime, date
from typing import Optional
from enum import Enum as PyEnum
import uuid

from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime, Date,
    ForeignKey, JSON, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class StandardStatus(PyEnum):
    """Статус стандарта."""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    UPDATED = "updated"
    SUSPICIOUS = "suspicious"  # Требует проверки ("это не то")


# Экспортируем для использования в других модулях
__all__ = ['Base', 'Standard', 'StandardVersion', 'StandardTable', 'StandardStatus']


class Standard(Base):
    """
    Таблица стандартов.
    Основная таблица с метаданными стандартов.
    """
    __tablename__ = 'standards'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Основные поля
    family = Column(String(20), nullable=False, index=True)  # ISO, DIN, GOST, OST, ANSI
    code = Column(String(100), nullable=False, index=True)  # 33056-80
    full_code = Column(String(200), nullable=False, index=True)  # ОСТ 1 33056-80
    title = Column(Text)  # Название стандарта
    country = Column(String(50))  # Страна/организация
    year = Column(Integer)  # Год издания
    
    # Версионирование
    version_hash = Column(String(64), nullable=False, index=True)  # SHA256 текущей версии
    source_url = Column(Text)  # URL источника
    
    # Временные метки
    last_checked = Column(DateTime, default=datetime.utcnow, index=True)  # Последняя проверка
    last_updated = Column(DateTime, default=datetime.utcnow)  # Последнее обновление
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Статус и флаги
    status = Column(String(20), default=StandardStatus.ACTIVE.value, index=True)
    needs_review = Column(Boolean, default=False, index=True)  # Требует проверки ("это не то")
    
    # Связи
    versions = relationship("StandardVersion", back_populates="standard", cascade="all, delete-orphan")
    tables = relationship("StandardTable", back_populates="standard", cascade="all, delete-orphan")
    
    # Индексы
    __table_args__ = (
        Index('idx_standard_family_code', 'family', 'code'),
        Index('idx_standard_status', 'status', 'needs_review'),
        Index('idx_standard_last_checked', 'last_checked'),
    )
    
    def __repr__(self):
        return f"<Standard(family={self.family}, code={self.code}, status={self.status})>"


class StandardVersion(Base):
    """
    Таблица версий стандартов.
    Хранит историю версий для каждого стандарта.
    """
    __tablename__ = 'standard_versions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    standard_id = Column(UUID(as_uuid=True), ForeignKey('standards.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Версия
    version_hash = Column(String(64), nullable=False, index=True)  # SHA256 этой версии
    published_date = Column(Date)  # Дата публикации версии
    file_path = Column(Text)  # Путь к файлу PDF
    
    # Метаданные
    file_size = Column(Integer)  # Размер файла в байтах
    metadata = Column(JSON)  # Дополнительные метаданные
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Связи
    standard = relationship("Standard", back_populates="versions")
    
    def __repr__(self):
        return f"<StandardVersion(standard_id={self.standard_id}, hash={self.version_hash[:16]}...)>"


class StandardTable(Base):
    """
    Таблица распарсенных данных стандартов.
    Хранит структурированные данные из PDF (таблицы, параметры).
    """
    __tablename__ = 'standard_tables'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    standard_id = Column(UUID(as_uuid=True), ForeignKey('standards.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Структура данных
    section_name = Column(String(200), nullable=False, index=True)  # Название раздела/таблицы
    json_data = Column(JSONB, nullable=False)  # Структурированные данные
    
    # Метаданные
    data_type = Column(String(50))  # table, parameters, dimensions, etc.
    page_number = Column(Integer)  # Номер страницы в PDF
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    standard = relationship("Standard", back_populates="tables")
    
    # Индексы
    __table_args__ = (
        Index('idx_table_standard_section', 'standard_id', 'section_name'),
    )
    
    def __repr__(self):
        return f"<StandardTable(standard_id={self.standard_id}, section={self.section_name})>"

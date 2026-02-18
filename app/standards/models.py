"""
SQLAlchemy модели для системы стандартов.
Production-ready архитектура с версионированием и структурированными данными.
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional
import uuid

from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class StandardFamily(PyEnum):
    """Семейства стандартов."""
    ISO = "ISO"
    DIN = "DIN"
    GOST = "GOST"
    OST = "OST"
    ANSI = "ANSI"
    ASME = "ASME"
    JIS = "JIS"
    EN = "EN"
    BS = "BS"
    GB = "GB"


class Standard(Base):
    """
    Модель стандарта.
    Основная таблица с метаданными стандартов.
    """
    __tablename__ = 'standards'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Основные поля
    family = Column(String(20), nullable=False, index=True)  # ISO, DIN, GOST, OST...
    code = Column(String(100), nullable=False, index=True)  # 33056-80
    full_code = Column(String(200), nullable=False, index=True)  # ОСТ 1 33056-80
    title = Column(Text)  # Название стандарта
    country = Column(String(50))  # Страна/организация
    revision = Column(String(20))  # Ревизия (например "2023")
    
    # Версионирование
    version_hash = Column(String(64), nullable=False, index=True)  # SHA256 текущей версии
    source = Column(String(50), default='user_upload')  # user_upload, api, manual
    
    # Временные метки
    last_checked = Column(DateTime, default=datetime.utcnow, index=True)
    last_updated = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Флаги
    needs_review = Column(Boolean, default=False, index=True)  # Требует проверки
    
    # Связи
    versions = relationship("StandardVersion", back_populates="standard", cascade="all, delete-orphan")
    data = relationship("StandardData", back_populates="standard", cascade="all, delete-orphan")
    
    # Составные индексы
    __table_args__ = (
        Index('idx_standard_family_code', 'family', 'code'),
        Index('idx_standard_needs_review', 'needs_review', 'last_checked'),
    )
    
    def __repr__(self):
        return f"<Standard(family={self.family}, code={self.code}, hash={self.version_hash[:16]}...)>"


class StandardData(Base):
    """
    Модель структурированных данных стандарта.
    Хранит распарсенные данные из PDF (таблицы, параметры).
    """
    __tablename__ = 'standard_data'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    standard_id = Column(UUID(as_uuid=True), ForeignKey('standards.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Структура данных
    section_name = Column(String(200), nullable=False, index=True)  # threads, dimensions, tolerances
    data = Column(JSONB, nullable=False)  # Структурированные данные
    
    # Метаданные
    data_type = Column(String(50))  # table, parameters, dimensions, etc.
    page_number = Column(Integer)  # Номер страницы в PDF
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Связи
    standard = relationship("Standard", back_populates="data")
    
    # Индексы
    __table_args__ = (
        Index('idx_data_standard_section', 'standard_id', 'section_name'),
    )
    
    def __repr__(self):
        return f"<StandardData(standard_id={self.standard_id}, section={self.section_name})>"


class StandardVersion(Base):
    """
    Модель версии стандарта.
    Хранит историю версий для отслеживания изменений.
    """
    __tablename__ = 'standard_versions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    standard_id = Column(UUID(as_uuid=True), ForeignKey('standards.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Версия
    version_hash = Column(String(64), nullable=False, index=True)  # SHA256 этой версии
    file_path = Column(Text, nullable=False)  # Путь к файлу PDF
    
    # Метаданные
    file_size = Column(Integer)  # Размер файла в байтах
    version_metadata = Column(JSONB)  # Дополнительные метаданные версии
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Связи
    standard = relationship("Standard", back_populates="versions")
    
    def __repr__(self):
        return f"<StandardVersion(standard_id={self.standard_id}, hash={self.version_hash[:16]}...)>"

"""
Pydantic схемы для API.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID

from pydantic import BaseModel, Field


class StandardBase(BaseModel):
    """Базовая схема стандарта."""
    family: str = Field(..., description="Семейство стандарта (ISO, DIN, GOST, OST...)")
    code: str = Field(..., description="Код стандарта (например, 33056-80)")
    full_code: str = Field(..., description="Полный код (например, ОСТ 1 33056-80)")
    title: Optional[str] = Field(None, description="Название стандарта")
    country: Optional[str] = Field(None, description="Страна/организация")
    revision: Optional[str] = Field(None, description="Ревизия")


class StandardCreate(StandardBase):
    """Схема создания стандарта."""
    pass


class StandardResponse(StandardBase):
    """Схема ответа со стандартом."""
    id: UUID
    version_hash: str
    source: str
    needs_review: bool
    last_checked: Optional[datetime]
    last_updated: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class StandardDataResponse(BaseModel):
    """Схема ответа с данными стандарта."""
    id: UUID
    standard_id: UUID
    section_name: str
    data: Dict[str, Any]
    data_type: Optional[str]
    page_number: Optional[int]
    
    class Config:
        from_attributes = True


class StandardFullResponse(StandardResponse):
    """Полная схема стандарта с данными."""
    data: List[StandardDataResponse] = Field(default_factory=list)
    versions_count: int = 0


class UploadResponse(BaseModel):
    """Схема ответа на загрузку."""
    success: bool
    standard_id: Optional[UUID] = None
    message: str
    version_hash: Optional[str] = None


class IntegrityCheckResponse(BaseModel):
    """Схема ответа проверки целостности."""
    total_standards: int
    missing_files: int
    corrupted_files: int
    all_ok: bool
    details: List[Dict[str, Any]] = Field(default_factory=list)


class UpdateCheckResponse(BaseModel):
    """Схема ответа проверки обновлений."""
    checked: int
    updated: int
    unchanged: int
    errors: int
    details: List[Dict[str, Any]] = Field(default_factory=list)

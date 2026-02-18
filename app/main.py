"""
FastAPI приложение для системы стандартов.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.standards.routes import router as standards_router

logger = logging.getLogger(__name__)

# Создаем приложение
app = FastAPI(
    title="CNC Assistant Standards API",
    description="Production-ready система управления инженерными стандартами",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роуты
app.include_router(standards_router)


@app.on_event("startup")
async def startup_event():
    """Инициализация при старте."""
    # Создаем таблицы если их нет
    init_db()
    logger.info(f"Standards system started in {settings.MODE} mode")


@app.get("/")
async def root():
    """Корневой endpoint."""
    return {
        "service": "CNC Assistant Standards API",
        "mode": settings.MODE,
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    import logging
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

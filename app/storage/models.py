"""
ORM модели для базы данных.
"""
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json

Base = declarative_base()


class Interaction(Base):
    """Модель взаимодействия с пользователем."""
    __tablename__ = 'interactions'

    id = Column(Integer, primary_key=True)
    user_id = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Контекст
    material = Column(String, nullable=False)
    operation = Column(String, nullable=False)
    mode = Column(String, nullable=False)
    diameter = Column(Float, nullable=False)

    # Рекомендации
    recommended_vc = Column(Float)
    recommended_rpm = Column(Float)
    recommended_feed = Column(Float)

    # Действие пользователя
    user_rpm = Column(Float)
    user_feed = Column(Float)

    # Результаты
    deviation_score = Column(Float)
    decision_quality = Column(Integer)  # будет заполняться позже

    # Контекст
    context_json = Column(Text, default='{}')

    # ML фичи
    features_json = Column(Text, default='{}')

    # Метаданные
    source = Column(String, default='telegram')
    session_id = Column(String)

    @property
    def context(self):
        return json.loads(self.context_json) if self.context_json else {}

    @context.setter
    def context(self, value):
        self.context_json = json.dumps(value, ensure_ascii=False)

    @property
    def features(self):
        return json.loads(self.features_json) if self.features_json else {}

    @features.setter
    def features(self, value):
        self.features_json = json.dumps(value, ensure_ascii=False)

    def to_dict(self):
        """Преобразовать в словарь."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'material': self.material,
            'operation': self.operation,
            'mode': self.mode,
            'diameter': self.diameter,
            'recommended_vc': self.recommended_vc,
            'recommended_rpm': self.recommended_rpm,
            'recommended_feed': self.recommended_feed,
            'user_rpm': self.user_rpm,
            'user_feed': self.user_feed,
            'deviation_score': self.deviation_score,
            'decision_quality': self.decision_quality,
            'context': self.context,
            'features': self.features,
            'source': self.source,
            'session_id': self.session_id
        }


class UserMetadata(Base):
    """Метаданные пользователя."""
    __tablename__ = 'user_metadata'

    user_id = Column(String, primary_key=True)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    total_interactions = Column(Integer, default=0)
    inferred_machine_type = Column(String)
    preferences_json = Column(Text, default='{}')
    consistency_score = Column(Float)

    @property
    def preferences(self):
        return json.loads(self.preferences_json) if self.preferences_json else {}

    @preferences.setter
    def preferences(self, value):
        self.preferences_json = json.dumps(value, ensure_ascii=False)


class Feedback(Base):
    """Обратная связь по результатам обработки."""
    __tablename__ = 'feedback'

    id = Column(Integer, primary_key=True)
    interaction_id = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Обратная связь от пользователя
    vibration_level = Column(Integer)  # 1-5
    surface_quality = Column(Integer)  # 1-5
    tool_wear_observed = Column(Integer)  # 1-5

    # Системная оценка
    success_metric = Column(Float)


# Инициализация базы данных
def init_orm_database(db_url: str = "sqlite:///storage/cnc.db"):
    """Инициализация ORM."""
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session


def get_session(db_url: str = "sqlite:///storage/cnc.db"):
    """Получить сессию базы данных."""
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    return Session()

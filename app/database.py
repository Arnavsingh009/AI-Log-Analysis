import json
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./incidents.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class IncidentModel(Base):
    __tablename__ = "incidents"

    id = Column(String, primary_key=True, index=True)
    service_name = Column(String, index=True)
    level = Column(String)
    message = Column(Text)
    stack_trace = Column(Text, default="")
    timestamp = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="Open")
    ai_analysis_json = Column(Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "service_name": self.service_name,
            "level": self.level,
            "message": self.message,
            "stack_trace": self.stack_trace,
            "timestamp": self.timestamp,
            "status": self.status,
            "ai_analysis": json.loads(self.ai_analysis_json) if self.ai_analysis_json else None,
        }


def init_db():
    Base.metadata.create_all(bind=engine)
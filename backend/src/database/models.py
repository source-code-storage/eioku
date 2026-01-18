from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.sql import func

from .connection import Base


class Video(Base):
    __tablename__ = "videos"

    video_id = Column(String, primary_key=True)
    file_path = Column(String, nullable=False, unique=True, index=True)
    filename = Column(String, nullable=False)
    duration = Column(Float)  # Duration in seconds
    file_size = Column(Integer)  # File size in bytes
    processed_at = Column(DateTime)
    last_modified = Column(DateTime, nullable=False)
    status = Column(String, nullable=False, default="pending", index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

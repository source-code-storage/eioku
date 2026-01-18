from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
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


class Transcription(Base):
    __tablename__ = "transcriptions"

    segment_id = Column(String, primary_key=True)
    video_id = Column(String, ForeignKey("videos.video_id"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    start = Column(Float, nullable=False)  # Start time in seconds
    end = Column(Float, nullable=False)    # End time in seconds
    confidence = Column(Float)             # Transcription confidence score
    speaker = Column(String)               # Speaker ID for multi-speaker audio
    created_at = Column(DateTime, server_default=func.now())


class Scene(Base):
    __tablename__ = "scenes"

    scene_id = Column(String, primary_key=True)
    video_id = Column(String, ForeignKey("videos.video_id"), nullable=False, index=True)
    scene = Column(Integer, nullable=False)  # Scene number/index
    start = Column(Float, nullable=False)    # Start time in seconds
    end = Column(Float, nullable=False)      # End time in seconds
    thumbnail_path = Column(String)          # Path to scene thumbnail image
    created_at = Column(DateTime, server_default=func.now())

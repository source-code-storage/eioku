"""Data models for Global Jump Navigation."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class JumpTo:
    """Temporal boundaries for an artifact occurrence.

    Attributes:
        start_ms: Start timestamp in milliseconds
        end_ms: End timestamp in milliseconds
    """

    start_ms: int
    end_ms: int


@dataclass
class GlobalJumpResult:
    """Result from a global jump navigation query.

    Represents a single artifact occurrence across the video library,
    including video metadata and temporal boundaries for navigation.

    Attributes:
        video_id: Unique identifier of the video containing the artifact
        video_filename: Filename of the video
        file_created_at: EXIF/filesystem creation date of the video (may be None)
        jump_to: Temporal boundaries (start_ms, end_ms) for the artifact
        artifact_id: Unique identifier of the specific artifact occurrence
        preview: Kind-specific preview data (label, confidence, text snippet, etc.)
    """

    video_id: str
    video_filename: str
    file_created_at: datetime | None
    jump_to: JumpTo
    artifact_id: str
    preview: dict

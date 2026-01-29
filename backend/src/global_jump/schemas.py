"""Pydantic response schemas for Global Jump Navigation API.

This module defines the response schemas for the global jump navigation endpoint,
which enables cross-video artifact search and navigation.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class JumpToSchema(BaseModel):
    """Schema for temporal boundaries of an artifact occurrence.

    Defines the start and end timestamps in milliseconds for navigating
    to a specific artifact within a video.

    Attributes:
        start_ms: Start timestamp in milliseconds where the artifact begins
        end_ms: End timestamp in milliseconds where the artifact ends
    """

    start_ms: int = Field(
        ...,
        description="Start timestamp in milliseconds where the artifact begins",
        ge=0,
        examples=[15000],
    )
    end_ms: int = Field(
        ...,
        description="End timestamp in milliseconds where the artifact ends",
        ge=0,
        examples=[15500],
    )


class GlobalJumpResultSchema(BaseModel):
    """Schema for a single global jump navigation result.

    Represents a single artifact occurrence across the video library,
    including video metadata and temporal boundaries for navigation.
    This schema is used to return search results from the global jump endpoint.

    Attributes:
        video_id: Unique identifier of the video containing the artifact
        video_filename: Filename of the video for display purposes
        file_created_at: EXIF/filesystem creation date used for timeline ordering
        jump_to: Temporal boundaries (start_ms, end_ms) for the artifact
        artifact_id: Unique identifier of the specific artifact occurrence
        preview: Kind-specific preview data (label, confidence, text snippet, etc.)

    Example:
        For an object detection result:
        {
            "video_id": "abc-123",
            "video_filename": "beach_trip.mp4",
            "file_created_at": "2025-05-19T02:22:21Z",
            "jump_to": {"start_ms": 15000, "end_ms": 15500},
            "artifact_id": "artifact_xyz",
            "preview": {"label": "dog", "confidence": 0.95}
        }
    """

    video_id: str = Field(
        ...,
        description="Unique identifier of the video containing the artifact",
        examples=["abc-123"],
    )
    video_filename: str = Field(
        ...,
        description="Filename of the video for display purposes",
        examples=["beach_trip.mp4"],
    )
    file_created_at: datetime | None = Field(
        None,
        description=(
            "EXIF/filesystem creation date of the video, used for global "
            "timeline ordering. May be None if not available."
        ),
        examples=["2025-05-19T02:22:21Z"],
    )
    jump_to: JumpToSchema = Field(
        ...,
        description=(
            "Temporal boundaries (start_ms, end_ms) for navigating to the artifact"
        ),
    )
    artifact_id: str = Field(
        ...,
        description="Unique identifier of the specific artifact occurrence",
        examples=["artifact_xyz"],
    )
    preview: dict = Field(
        ...,
        description=(
            "Kind-specific preview data. For objects: {label, confidence}. "
            "For faces: {cluster_id, confidence}. For transcript/OCR: {text}. "
            "For scenes: {scene_index}."
        ),
        examples=[{"label": "dog", "confidence": 0.95}],
    )

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class GlobalJumpResponseSchema(BaseModel):
    """Schema for the global jump navigation API response.

    Contains the list of matching results and pagination information.
    Results are ordered by the global timeline (file_created_at, video_id, start_ms).

    Attributes:
        results: List of matching artifacts ordered by global timeline
        has_more: Indicates whether additional results exist beyond the limit

    Example:
        {
            "results": [
                {
                    "video_id": "abc-123",
                    "video_filename": "beach_trip.mp4",
                    "file_created_at": "2025-05-19T02:22:21Z",
                    "jump_to": {"start_ms": 15000, "end_ms": 15500},
                    "artifact_id": "artifact_xyz",
                    "preview": {"label": "dog", "confidence": 0.95}
                }
            ],
            "has_more": true
        }
    """

    results: list[GlobalJumpResultSchema] = Field(
        ...,
        description=(
            "List of matching artifacts ordered by global timeline "
            "(file_created_at, video_id, start_ms)"
        ),
    )
    has_more: bool = Field(
        ...,
        description=(
            "Indicates whether additional results exist beyond the requested "
            "limit. True if more results are available, False otherwise."
        ),
    )

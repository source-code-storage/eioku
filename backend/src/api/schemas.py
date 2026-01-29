from datetime import datetime

from pydantic import BaseModel, Field


class JumpToSchema(BaseModel):
    """Schema for jump target timestamp."""

    start_ms: int = Field(..., description="Start timestamp in milliseconds")
    end_ms: int = Field(..., description="End timestamp in milliseconds")


class JumpResponseSchema(BaseModel):
    """Schema for jump navigation response."""

    jump_to: JumpToSchema = Field(..., description="Target timestamp to jump to")
    artifact_ids: list[str] = Field(..., description="List of artifact IDs at target")


class FindMatchSchema(BaseModel):
    """Schema for find match result."""

    jump_to: JumpToSchema = Field(..., description="Target timestamp to jump to")
    artifact_id: str = Field(..., description="Artifact ID containing the match")
    snippet: str = Field(..., description="Highlighted text snippet")
    source: str = Field(..., description="Source of match: transcript or ocr")


class FindResponseSchema(BaseModel):
    """Schema for find within video response."""

    matches: list[FindMatchSchema] = Field(..., description="List of matches found")


class ArtifactPayloadSchema(BaseModel):
    """Schema for artifact payload (flexible dict)."""

    class Config:
        extra = "allow"


class ArtifactResponseSchema(BaseModel):
    """Schema for artifact response."""

    artifact_id: str = Field(..., description="Unique artifact identifier")
    asset_id: str = Field(..., description="Asset (video) ID")
    artifact_type: str = Field(..., description="Type of artifact")
    schema_version: int = Field(..., description="Schema version")
    span_start_ms: int = Field(..., description="Start timestamp in milliseconds")
    span_end_ms: int = Field(..., description="End timestamp in milliseconds")
    payload: dict = Field(..., description="Artifact payload data")
    producer: str = Field(..., description="Producer name")
    producer_version: str = Field(..., description="Producer version")
    model_profile: str = Field(..., description="Model profile")
    run_id: str = Field(..., description="Run ID")
    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        from_attributes = True


class VideoCreateSchema(BaseModel):
    """Schema for creating a new video."""

    video_id: str = Field(..., description="Unique video identifier")
    file_path: str = Field(..., description="Path to video file")
    filename: str = Field(..., description="Video filename")
    last_modified: datetime = Field(..., description="File last modified timestamp")
    duration: float | None = Field(None, description="Video duration in seconds")
    file_size: int | None = Field(None, description="File size in bytes")
    file_hash: str | None = Field(None, description="SHA-256 hash of video file")


class VideoResponseSchema(BaseModel):
    """Schema for video API responses."""

    video_id: str
    file_path: str
    filename: str
    last_modified: datetime
    status: str
    duration: float | None = None
    file_size: int | None = None
    file_hash: str | None = None
    file_created_at: datetime | None = None
    processed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class VideoUpdateSchema(BaseModel):
    """Schema for updating video."""

    status: str | None = Field(None, description="Processing status")
    duration: float | None = Field(None, description="Video duration in seconds")
    file_size: int | None = Field(None, description="File size in bytes")
    file_created_at: datetime | None = Field(
        None, description="File creation timestamp from EXIF or file system"
    )
    processed_at: datetime | None = Field(
        None, description="Processing completion time"
    )


class ProfileInfoSchema(BaseModel):
    """Schema for model profile information."""

    profile: str = Field(..., description="Model profile name")
    artifact_count: int = Field(
        ..., description="Number of artifacts with this profile"
    )
    run_ids: list[str] = Field(..., description="List of run IDs for this profile")


class ProfilesResponseSchema(BaseModel):
    """Schema for profiles endpoint response."""

    video_id: str = Field(..., description="Video ID")
    artifact_type: str = Field(..., description="Artifact type")
    profiles: list[ProfileInfoSchema] = Field(..., description="Available profiles")


class RunInfoSchema(BaseModel):
    """Schema for run information."""

    run_id: str = Field(..., description="Run ID")
    created_at: datetime = Field(..., description="Creation timestamp of the run")
    artifact_count: int = Field(
        ..., description="Number of artifacts produced in this run"
    )
    model_profile: str | None = Field(
        None, description="Model profile used for this run"
    )
    language: str | None = Field(
        None, description="Language of artifacts in this run (if applicable)"
    )


class RunsResponseSchema(BaseModel):
    """Schema for runs endpoint response."""

    video_id: str = Field(..., description="Video ID")
    artifact_type: str = Field(..., description="Artifact type")
    runs: list[RunInfoSchema] = Field(..., description="Available runs")


class LocationInfoSchema(BaseModel):
    """Schema for video location information."""

    latitude: float = Field(..., description="Latitude coordinate")
    longitude: float = Field(..., description="Longitude coordinate")
    altitude: float | None = Field(None, description="Altitude in meters")
    country: str | None = Field(None, description="Country name")
    state: str | None = Field(None, description="State/province name")
    city: str | None = Field(None, description="City name")

    class Config:
        from_attributes = True


# Global Jump Navigation Schemas


class GlobalJumpResultSchema(BaseModel):
    """Schema for a single global jump navigation result.

    Represents a single artifact occurrence across the video library,
    including video metadata and temporal boundaries for navigation.
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
        from_attributes = True


class GlobalJumpResponseSchema(BaseModel):
    """Schema for the global jump navigation API response.

    Contains the list of matching results and pagination information.
    Results are ordered by the global timeline (file_created_at, video_id, start_ms).
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

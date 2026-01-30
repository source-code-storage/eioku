from datetime import datetime

from pydantic import BaseModel, Field


class ErrorResponseSchema(BaseModel):
    """Schema for error responses with consistent format.

    All error responses include detail, error_code, and timestamp
    for debugging and client-side error handling.
    """

    detail: str = Field(
        ...,
        description="Human-readable error message describing what went wrong",
        examples=["Video not found"],
    )
    error_code: str = Field(
        ...,
        description="Machine-readable error code for programmatic handling",
        examples=["VIDEO_NOT_FOUND"],
    )
    timestamp: datetime = Field(
        ...,
        description="UTC timestamp when the error occurred",
        examples=["2025-05-19T02:22:21Z"],
    )

    class Config:
        json_schema_extra = {
            "example": {
                "detail": "Video not found",
                "error_code": "VIDEO_NOT_FOUND",
                "timestamp": "2025-05-19T02:22:21Z",
            }
        }


class JumpToSchema(BaseModel):
    """Schema for jump target timestamp boundaries.

    Defines the temporal boundaries (start and end) for navigating to an
    artifact within a video. The start_ms indicates where to seek, and
    end_ms indicates the artifact's end boundary.

    For result chaining in global jump navigation, use end_ms as the
    from_ms parameter in subsequent requests to continue navigation.

    Example:
        ```json
        {"start_ms": 15000, "end_ms": 15500}
        ```

    Attributes:
        start_ms: Start timestamp in milliseconds - seek to this position.
        end_ms: End timestamp in milliseconds - artifact ends here.
    """

    start_ms: int = Field(
        ...,
        description=(
            "Start timestamp in milliseconds. This is the position to seek to "
            "in the video player to view the artifact."
        ),
        examples=[0, 15000, 120000],
        ge=0,
    )
    end_ms: int = Field(
        ...,
        description=(
            "End timestamp in milliseconds. This marks the end of the artifact's "
            "temporal boundary. Use this value as from_ms in subsequent global "
            "jump requests to continue navigation from after this artifact."
        ),
        examples=[500, 15500, 125000],
        ge=0,
    )

    class Config:
        json_schema_extra = {"example": {"start_ms": 15000, "end_ms": 15500}}


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

    This schema is returned as part of the GlobalJumpResponseSchema and
    contains all information needed to navigate to and display the artifact.

    Example:
        ```json
        {
            "video_id": "abc-123",
            "video_filename": "beach_trip.mp4",
            "file_created_at": "2025-05-19T02:22:21Z",
            "jump_to": {"start_ms": 15000, "end_ms": 15500},
            "artifact_id": "obj_xyz_001",
            "preview": {"label": "dog", "confidence": 0.95}
        }
        ```

    Attributes:
        video_id: Unique identifier of the video containing the artifact.
        video_filename: Human-readable filename for display in UI.
        file_created_at: EXIF/filesystem creation date used for timeline ordering.
        jump_to: Temporal boundaries for seeking to the artifact.
        artifact_id: Unique identifier for this specific artifact occurrence.
        preview: Kind-specific preview data for displaying result information.
    """

    video_id: str = Field(
        ...,
        description="Unique identifier of the video containing the artifact",
        examples=["abc-123", "video_001", "550e8400-e29b-41d4-a716-446655440000"],
    )
    video_filename: str = Field(
        ...,
        description="Filename of the video for display purposes in the UI",
        examples=["beach_trip.mp4", "meeting_2025-01-15.mp4", "family_reunion.mov"],
    )
    file_created_at: datetime | None = Field(
        None,
        description=(
            "EXIF/filesystem creation date of the video, used as the primary "
            "sort key for global timeline ordering. May be None if the creation "
            "date could not be determined from EXIF metadata or filesystem."
        ),
        examples=["2025-05-19T02:22:21Z", "2024-12-25T10:30:00Z"],
    )
    jump_to: JumpToSchema = Field(
        ...,
        description=(
            "Temporal boundaries (start_ms, end_ms) defining where to seek in "
            "the video to view this artifact. Use start_ms for initial seek "
            "position and end_ms as the starting point for subsequent searches."
        ),
    )
    artifact_id: str = Field(
        ...,
        description=(
            "Unique identifier of the specific artifact occurrence. Can be used "
            "to fetch additional details about the artifact if needed."
        ),
        examples=["obj_xyz_001", "face_abc_002", "trans_def_003"],
    )
    preview: dict = Field(
        ...,
        description=(
            "Kind-specific preview data for displaying result information. "
            "Contents vary by artifact kind:\n"
            '- **object**: `{"label": "dog", "confidence": 0.95}`\n'
            '- **face**: `{"cluster_id": "person_001", "confidence": 0.89}`\n'
            '- **transcript**: `{"text": "...matched text snippet..."}`\n'
            '- **ocr**: `{"text": "...detected text..."}`\n'
            '- **scene**: `{"scene_index": 5}`\n'
            '- **place**: `{"label": "beach", "confidence": 0.87}`\n'
            '- **location**: `{"latitude": 37.7749, "longitude": -122.4194}`'
        ),
        examples=[
            {"label": "dog", "confidence": 0.95},
            {"cluster_id": "person_001", "confidence": 0.89},
            {"text": "...discussed the project timeline..."},
        ],
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "video_id": "abc-123",
                "video_filename": "beach_trip.mp4",
                "file_created_at": "2025-05-19T02:22:21Z",
                "jump_to": {"start_ms": 15000, "end_ms": 15500},
                "artifact_id": "obj_xyz_001",
                "preview": {"label": "dog", "confidence": 0.95},
            }
        }


class GlobalJumpResponseSchema(BaseModel):
    """Schema for the global jump navigation API response.

    Contains the list of matching results and pagination information.
    Results are ordered by the global timeline using a deterministic
    three-level sort: file_created_at, video_id, start_ms.

    **Pagination:**
    The `has_more` field is crucial for implementing continuous navigation.
    When `has_more` is True, additional results exist beyond the requested
    limit. To fetch the next page:
    1. Take the last result from the current response
    2. Use its `video_id` as `from_video_id`
    3. Use its `jump_to.end_ms` as `from_ms`
    4. Make another request with the same filters

    **Empty Results:**
    When no matching artifacts are found, the response will have an empty
    `results` array and `has_more` will be False. This is not an error
    condition - it simply means no artifacts match the search criteria
    from the specified position in the requested direction.

    Example (with results):
        ```json
        {
            "results": [
                {
                    "video_id": "abc-123",
                    "video_filename": "beach_trip.mp4",
                    "file_created_at": "2025-05-19T02:22:21Z",
                    "jump_to": {"start_ms": 15000, "end_ms": 15500},
                    "artifact_id": "obj_xyz_001",
                    "preview": {"label": "dog", "confidence": 0.95}
                }
            ],
            "has_more": true
        }
        ```

    Example (no results):
        ```json
        {
            "results": [],
            "has_more": false
        }
        ```

    Attributes:
        results: List of matching artifacts ordered by global timeline.
        has_more: Pagination flag indicating if more results exist.
    """

    results: list[GlobalJumpResultSchema] = Field(
        ...,
        description=(
            "List of matching artifacts ordered by global timeline. "
            "The ordering is deterministic using three sort keys:\n"
            "1. **file_created_at** (primary): EXIF/filesystem creation date\n"
            "2. **video_id** (secondary): For deterministic ordering when dates match\n"
            "3. **start_ms** (tertiary): Artifact timestamp within the video\n\n"
            "For 'next' direction, results are in ascending order. "
            "For 'prev' direction, results are in descending order."
        ),
    )
    has_more: bool = Field(
        ...,
        description=(
            "Pagination indicator. True if additional results exist beyond the "
            "requested limit, False otherwise. Use this to implement continuous "
            "navigation:\n\n"
            "- **has_more=true**: More results available. Use the last result's "
            "`video_id` and `jump_to.end_ms` as starting point for next request.\n"
            "- **has_more=false**: No more results in this direction. User has "
            "reached the end (for 'next') or beginning (for 'prev') of matching "
            "artifacts in the global timeline."
        ),
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "summary": "Results found with more available",
                    "value": {
                        "results": [
                            {
                                "video_id": "abc-123",
                                "video_filename": "beach_trip.mp4",
                                "file_created_at": "2025-05-19T02:22:21Z",
                                "jump_to": {"start_ms": 15000, "end_ms": 15500},
                                "artifact_id": "obj_xyz_001",
                                "preview": {"label": "dog", "confidence": 0.95},
                            }
                        ],
                        "has_more": True,
                    },
                },
                {
                    "summary": "No results found",
                    "value": {
                        "results": [],
                        "has_more": False,
                    },
                },
            ]
        }

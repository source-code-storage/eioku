"""Controller for Global Jump Navigation API."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..database.connection import get_db
from ..domain.exceptions import InvalidParameterError, VideoNotFoundError
from ..domain.schema_registry import SchemaRegistry
from ..repositories.artifact_repository import SqlArtifactRepository
from ..services.global_jump_service import GlobalJumpService
from ..services.projection_sync_service import ProjectionSyncService
from .schemas import (
    ErrorResponseSchema,
    GlobalJumpResponseSchema,
    GlobalJumpResultSchema,
    JumpToSchema,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jump", tags=["global-navigation"])

VALID_KINDS = {"object", "face", "transcript", "ocr", "scene", "place", "location"}
VALID_DIRECTIONS = {"next", "prev"}

# Error codes for consistent error handling
ERROR_CODES = {
    "INVALID_VIDEO_ID": "INVALID_VIDEO_ID",
    "INVALID_KIND": "INVALID_KIND",
    "INVALID_DIRECTION": "INVALID_DIRECTION",
    "CONFLICTING_FILTERS": "CONFLICTING_FILTERS",
    "INVALID_FROM_MS": "INVALID_FROM_MS",
    "INVALID_CONFIDENCE": "INVALID_CONFIDENCE",
    "INVALID_LIMIT": "INVALID_LIMIT",
    "VIDEO_NOT_FOUND": "VIDEO_NOT_FOUND",
    "INTERNAL_ERROR": "INTERNAL_ERROR",
}


def create_error_response(
    status_code: int, detail: str, error_code: str
) -> JSONResponse:
    """Create a consistent error response with detail, error_code, and timestamp."""
    error_data = ErrorResponseSchema(
        detail=detail,
        error_code=error_code,
        timestamp=datetime.now(timezone.utc),
    )
    return JSONResponse(
        status_code=status_code,
        content=error_data.model_dump(mode="json"),
    )


def get_global_jump_service(session: Session = Depends(get_db)) -> GlobalJumpService:
    """Dependency injection for GlobalJumpService."""
    schema_registry = SchemaRegistry()
    projection_sync = ProjectionSyncService(session)
    artifact_repo = SqlArtifactRepository(session, schema_registry, projection_sync)
    return GlobalJumpService(session, artifact_repo)


@router.get(
    "/global",
    response_model=GlobalJumpResponseSchema,
    summary="Global Jump Navigation",
    description="""Navigate across videos to find artifacts in chronological order.

## Overview

This endpoint enables **cross-video artifact search and navigation** using a
unified API. Users can search for objects, faces, text (transcript/OCR),
scenes, places, and locations across their entire video library.

## Global Timeline Concept

Results are ordered using a **deterministic global timeline** based on:
1. **Primary sort**: `file_created_at` (EXIF/filesystem date of the video)
2. **Secondary sort**: `video_id` (for deterministic ordering when dates match)
3. **Tertiary sort**: `start_ms` (artifact timestamp within the video)

This ensures consistent, predictable navigation across your video library.

## Supported Artifact Kinds

| Kind | Description | Required Parameters |
|------|-------------|---------------------|
| `object` | Detected object labels (e.g., "dog", "car") | `label` |
| `face` | Face cluster detections | `face_cluster_id` |
| `transcript` | Full-text search in video transcripts | `query` |
| `ocr` | Full-text search in on-screen text | `query` |
| `scene` | Scene boundary navigation | None |
| `place` | Detected place labels | `label` |
| `location` | GPS location data | None |

## Navigation Directions

- **`next`**: Find artifacts chronologically **after** the current position
- **`prev`**: Find artifacts chronologically **before** the current position

## Result Chaining (Pagination)

To navigate through all occurrences sequentially:
1. Make initial request with your starting position
2. Use the returned `video_id` and `jump_to.end_ms` as `from_video_id`
   and `from_ms` for the next request
3. Continue until `has_more` is `false`

## Example Usage

**Find next dog in video library:**
```
GET /jump/global?kind=object&label=dog&direction=next&from_video_id=abc-123
```

**Search for word in transcripts:**
```
GET /jump/global?kind=transcript&query=hello&direction=next&from_video_id=abc
```

**Navigate to previous face occurrence:**
```
GET /jump/global?kind=face&face_cluster_id=face-001&direction=prev&from_video_id=abc
```
""",
    responses={
        200: {
            "description": "Successful response with matching artifacts",
            "model": GlobalJumpResponseSchema,
            "content": {
                "application/json": {
                    "examples": {
                        "object_search": {
                            "summary": "Object search result",
                            "description": (
                                "Example response when searching for objects"
                            ),
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
                        "transcript_search": {
                            "summary": "Transcript search result",
                            "description": "Example response for transcripts",
                            "value": {
                                "results": [
                                    {
                                        "video_id": "def-456",
                                        "video_filename": "meeting_2025.mp4",
                                        "file_created_at": "2025-06-01T10:30:00Z",
                                        "jump_to": {"start_ms": 45000, "end_ms": 48000},
                                        "artifact_id": "trans_abc_002",
                                        "preview": {
                                            "text": "...discussed the project..."
                                        },
                                    }
                                ],
                                "has_more": False,
                            },
                        },
                        "face_search": {
                            "summary": "Face cluster search result",
                            "description": ("Example response when searching by face"),
                            "value": {
                                "results": [
                                    {
                                        "video_id": "ghi-789",
                                        "video_filename": "family_reunion.mp4",
                                        "file_created_at": "2025-04-15T14:00:00Z",
                                        "jump_to": {
                                            "start_ms": 120000,
                                            "end_ms": 125000,
                                        },
                                        "artifact_id": "face_def_003",
                                        "preview": {
                                            "cluster_id": "person_001",
                                            "confidence": 0.89,
                                        },
                                    }
                                ],
                                "has_more": True,
                            },
                        },
                        "empty_results": {
                            "summary": "No results found",
                            "description": "Response when no matching artifacts exist",
                            "value": {
                                "results": [],
                                "has_more": False,
                            },
                        },
                        "multiple_results": {
                            "summary": "Multiple results with pagination",
                            "description": (
                                "Response with multiple results when limit > 1"
                            ),
                            "value": {
                                "results": [
                                    {
                                        "video_id": "abc-123",
                                        "video_filename": "video1.mp4",
                                        "file_created_at": "2025-01-01T00:00:00Z",
                                        "jump_to": {"start_ms": 1000, "end_ms": 1500},
                                        "artifact_id": "art_001",
                                        "preview": {"label": "car", "confidence": 0.92},
                                    },
                                    {
                                        "video_id": "abc-123",
                                        "video_filename": "video1.mp4",
                                        "file_created_at": "2025-01-01T00:00:00Z",
                                        "jump_to": {"start_ms": 5000, "end_ms": 5500},
                                        "artifact_id": "art_002",
                                        "preview": {"label": "car", "confidence": 0.88},
                                    },
                                ],
                                "has_more": True,
                            },
                        },
                    }
                }
            },
        },
        400: {
            "description": "Invalid request parameters",
            "model": ErrorResponseSchema,
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_kind": {
                            "summary": "Invalid artifact kind",
                            "description": (
                                "Returned when kind is not a valid artifact type"
                            ),
                            "value": {
                                "detail": "Invalid artifact kind. Must be one of: "
                                "face, location, object, ocr, place, scene, transcript",
                                "error_code": "INVALID_KIND",
                                "timestamp": "2025-05-19T02:22:21Z",
                            },
                        },
                        "invalid_direction": {
                            "summary": "Invalid direction",
                            "description": (
                                "Returned when direction is not 'next' or 'prev'"
                            ),
                            "value": {
                                "detail": "Direction must be 'next' or 'prev'",
                                "error_code": "INVALID_DIRECTION",
                                "timestamp": "2025-05-19T02:22:21Z",
                            },
                        },
                        "conflicting_filters": {
                            "summary": "Conflicting filters",
                            "description": (
                                "Returned when both label and query are specified"
                            ),
                            "value": {
                                "detail": (
                                    "Cannot specify both label and query parameters"
                                ),
                                "error_code": "CONFLICTING_FILTERS",
                                "timestamp": "2025-05-19T02:22:21Z",
                            },
                        },
                        "invalid_confidence": {
                            "summary": "Invalid confidence value",
                            "description": (
                                "Returned when min_confidence is outside 0-1 range"
                            ),
                            "value": {
                                "detail": "min_confidence must be between 0 and 1",
                                "error_code": "INVALID_CONFIDENCE",
                                "timestamp": "2025-05-19T02:22:21Z",
                            },
                        },
                        "invalid_limit": {
                            "summary": "Invalid limit value",
                            "description": (
                                "Returned when limit is outside 1-50 range"
                            ),
                            "value": {
                                "detail": "limit must be between 1 and 50",
                                "error_code": "INVALID_LIMIT",
                                "timestamp": "2025-05-19T02:22:21Z",
                            },
                        },
                        "invalid_from_ms": {
                            "summary": "Invalid from_ms value",
                            "description": "Returned when from_ms is negative",
                            "value": {
                                "detail": "from_ms must be a non-negative integer",
                                "error_code": "INVALID_FROM_MS",
                                "timestamp": "2025-05-19T02:22:21Z",
                            },
                        },
                        "empty_video_id": {
                            "summary": "Empty video ID",
                            "description": ("Returned when from_video_id is empty"),
                            "value": {
                                "detail": "from_video_id must be a non-empty string",
                                "error_code": "INVALID_VIDEO_ID",
                                "timestamp": "2025-05-19T02:22:21Z",
                            },
                        },
                    }
                }
            },
        },
        404: {
            "description": "Video not found",
            "model": ErrorResponseSchema,
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Video not found",
                        "error_code": "VIDEO_NOT_FOUND",
                        "timestamp": "2025-05-19T02:22:21Z",
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponseSchema,
            "content": {
                "application/json": {
                    "example": {
                        "detail": "An unexpected error occurred",
                        "error_code": "INTERNAL_ERROR",
                        "timestamp": "2025-05-19T02:22:21Z",
                    }
                }
            },
        },
    },
)
async def global_jump(
    kind: str = Query(
        ...,
        description=(
            "Type of artifact to search for. Determines which projection table "
            "is queried and what filter parameters are applicable."
        ),
        examples=["object", "face", "transcript", "ocr", "scene", "place", "location"],
    ),
    direction: str = Query(
        ...,
        description=(
            "Navigation direction along the global timeline. 'next' returns "
            "artifacts chronologically after the current position, 'prev' returns "
            "artifacts chronologically before."
        ),
        examples=["next", "prev"],
    ),
    from_video_id: str = Query(
        ...,
        description=(
            "Starting video ID for the search. The search begins from this video's "
            "position in the global timeline. Must be a valid, existing video ID."
        ),
        examples=["abc-123", "video_001"],
    ),
    from_ms: int | None = Query(
        None,
        description=(
            "Starting timestamp in milliseconds within the from_video_id. "
            "If omitted, defaults to 0 for 'next' direction (start of video) "
            "or video duration for 'prev' direction (end of video). "
            "Values beyond video duration are treated as end of video."
        ),
        examples=[0, 15000, 120000],
        ge=0,
    ),
    label: str | None = Query(
        None,
        description=(
            "Filter by artifact label. Used with kind='object' or kind='place'. "
            "Case-sensitive exact match. Cannot be combined with 'query'."
        ),
        examples=["dog", "car", "person", "beach", "office"],
    ),
    query: str | None = Query(
        None,
        description=(
            "Full-text search query. Used with kind='transcript' or kind='ocr'. "
            "Supports PostgreSQL full-text search syntax. Cannot be used together "
            "with 'label' parameter."
        ),
        examples=["hello world", "project meeting", "kubernetes"],
    ),
    face_cluster_id: str | None = Query(
        None,
        description=(
            "Filter by face cluster ID. Used with kind='face'. "
            "Face clusters group face detections representing the same person."
        ),
        examples=["person_001", "face_cluster_abc"],
    ),
    min_confidence: float | None = Query(
        None,
        description=(
            "Minimum confidence threshold (0.0 to 1.0). Filters results to only "
            "include artifacts with confidence >= this value. Applicable to "
            "kind='object' and kind='face'."
        ),
        examples=[0.5, 0.8, 0.95],
        ge=0.0,
        le=1.0,
    ),
    limit: int = Query(
        1,
        description=(
            "Maximum number of results to return (1-50). Default is 1 for "
            "single-step navigation. Use higher values to preview multiple "
            "upcoming results. Check 'has_more' in response to determine if "
            "additional results exist beyond this limit."
        ),
        examples=[1, 5, 10, 50],
        ge=1,
        le=50,
    ),
    service: GlobalJumpService = Depends(get_global_jump_service),
) -> GlobalJumpResponseSchema | JSONResponse:
    """
    Navigate across videos to find artifacts in chronological order.

    This endpoint provides cross-video artifact search and navigation using a
    unified API. It enables users to search for objects, faces, text (transcript/OCR),
    scenes, places, and locations across their entire video library.

    **Global Timeline Ordering:**
    Results are ordered using a deterministic global timeline based on:
    1. `file_created_at` (EXIF/filesystem date) - primary sort
    2. `video_id` - secondary sort for deterministic ordering
    3. `start_ms` - tertiary sort for artifacts within the same video

    **Navigation Flow:**
    1. Specify starting position with `from_video_id` and optionally `from_ms`
    2. Choose `direction` ('next' or 'prev') to search forward or backward
    3. Filter by artifact type using `kind` and appropriate filter parameters
    4. Use returned `video_id` and `jump_to.end_ms` for subsequent navigation

    **Pagination:**
    The `has_more` field indicates whether additional results exist beyond the
    requested `limit`. To paginate through all results:
    - Use the last result's `video_id` as `from_video_id`
    - Use the last result's `jump_to.end_ms` as `from_ms`
    - Continue until `has_more` is `false`

    Args:
        kind: Type of artifact (object, face, transcript, ocr, scene, place, location)
        direction: Navigation direction ('next' or 'prev')
        from_video_id: Starting video ID for the search
        from_ms: Starting timestamp in milliseconds (optional)
        label: Filter by artifact label (for object/place kinds)
        query: Full-text search query (for transcript/ocr kinds)
        face_cluster_id: Filter by face cluster ID (for face kind)
        min_confidence: Minimum confidence threshold 0-1 (for object/face kinds)
        limit: Maximum number of results to return (1-50, default 1)
        service: Injected GlobalJumpService instance

    Returns:
        GlobalJumpResponseSchema: Contains results array and has_more pagination flag

    Raises:
        400 Bad Request: Invalid parameters (kind, direction, conflicting filters, etc.)
        404 Not Found: Specified from_video_id does not exist
        500 Internal Server Error: Unexpected server error
    """
    # Validate from_video_id is non-empty
    if not from_video_id or not from_video_id.strip():
        logger.warning("Validation error: from_video_id is empty")
        return create_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_video_id must be a non-empty string",
            error_code=ERROR_CODES["INVALID_VIDEO_ID"],
        )

    # Validate kind parameter
    if kind not in VALID_KINDS:
        valid_kinds_str = ", ".join(sorted(VALID_KINDS))
        logger.warning(f"Validation error: invalid kind '{kind}'")
        return create_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid artifact kind. Must be one of: {valid_kinds_str}",
            error_code=ERROR_CODES["INVALID_KIND"],
        )

    # Validate direction parameter
    if direction not in VALID_DIRECTIONS:
        logger.warning(f"Validation error: invalid direction '{direction}'")
        return create_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Direction must be 'next' or 'prev'",
            error_code=ERROR_CODES["INVALID_DIRECTION"],
        )

    # Validate label and query are mutually exclusive
    if label is not None and query is not None:
        logger.warning("Validation error: both label and query specified")
        return create_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot specify both label and query parameters",
            error_code=ERROR_CODES["CONFLICTING_FILTERS"],
        )

    # Validate from_ms is non-negative
    if from_ms is not None and from_ms < 0:
        logger.warning(f"Validation error: negative from_ms '{from_ms}'")
        return create_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_ms must be a non-negative integer",
            error_code=ERROR_CODES["INVALID_FROM_MS"],
        )

    # Validate min_confidence is between 0 and 1
    if min_confidence is not None and (min_confidence < 0 or min_confidence > 1):
        logger.warning(f"Validation error: invalid min_confidence '{min_confidence}'")
        return create_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="min_confidence must be between 0 and 1",
            error_code=ERROR_CODES["INVALID_CONFIDENCE"],
        )

    # Validate limit is between 1 and 50
    if limit < 1 or limit > 50:
        logger.warning(f"Validation error: invalid limit '{limit}'")
        return create_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="limit must be between 1 and 50",
            error_code=ERROR_CODES["INVALID_LIMIT"],
        )

    try:
        # Route to appropriate service method based on direction
        if direction == "next":
            results = service.jump_next(
                kind=kind,
                from_video_id=from_video_id,
                from_ms=from_ms,
                label=label,
                query=query,
                face_cluster_id=face_cluster_id,
                min_confidence=min_confidence,
                limit=limit + 1,
            )
        else:
            results = service.jump_prev(
                kind=kind,
                from_video_id=from_video_id,
                from_ms=from_ms,
                label=label,
                query=query,
                face_cluster_id=face_cluster_id,
                min_confidence=min_confidence,
                limit=limit + 1,
            )

        # Determine has_more and trim results
        has_more = len(results) > limit
        results = results[:limit]

        # Convert domain models to response schemas
        response_results = [
            GlobalJumpResultSchema(
                video_id=r.video_id,
                video_filename=r.video_filename,
                file_created_at=r.file_created_at,
                jump_to=JumpToSchema(
                    start_ms=r.jump_to.start_ms,
                    end_ms=r.jump_to.end_ms,
                ),
                artifact_id=r.artifact_id,
                preview=r.preview,
            )
            for r in results
        ]

        return GlobalJumpResponseSchema(
            results=response_results,
            has_more=has_more,
        )

    except VideoNotFoundError as e:
        logger.warning(f"Video not found: {e.video_id}")
        return create_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
            error_code=ERROR_CODES["VIDEO_NOT_FOUND"],
        )

    except InvalidParameterError as e:
        logger.warning(f"Invalid parameter '{e.parameter}': {e.message}")
        return create_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
            error_code=ERROR_CODES["INVALID_KIND"],
        )

    except Exception as e:
        logger.error(f"Unexpected error in global_jump: {e}", exc_info=True)
        return create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
            error_code=ERROR_CODES["INTERNAL_ERROR"],
        )

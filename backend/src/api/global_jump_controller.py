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

This endpoint enables cross-video artifact search and navigation using a unified API.
Users can search for objects, faces, text (transcript/OCR), scenes, places, and
locations across their entire video library in chronological order based on
file_created_at (EXIF/filesystem date).

**Supported artifact kinds:**
- `object`: Search by detected object labels (e.g., "dog", "car")
- `face`: Search by face cluster ID
- `transcript`: Full-text search in video transcripts
- `ocr`: Full-text search in detected on-screen text
- `scene`: Navigate between scene boundaries
- `place`: Search by detected place labels
- `location`: Search by GPS location data

**Navigation directions:**
- `next`: Find artifacts chronologically after the current position
- `prev`: Find artifacts chronologically before the current position

**Result chaining:**
To navigate through all occurrences, use the returned `video_id` and `end_ms`
as the `from_video_id` and `from_ms` for the next query.
""",
    responses={
        200: {
            "description": "Successful response with matching artifacts",
            "model": GlobalJumpResponseSchema,
            "content": {
                "application/json": {
                    "example": {
                        "results": [
                            {
                                "video_id": "abc-123",
                                "video_filename": "beach_trip.mp4",
                                "file_created_at": "2025-05-19T02:22:21Z",
                                "jump_to": {"start_ms": 15000, "end_ms": 15500},
                                "artifact_id": "artifact_xyz",
                                "preview": {"label": "dog", "confidence": 0.95},
                            }
                        ],
                        "has_more": True,
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
                            "value": {
                                "detail": "Invalid artifact kind. Must be one of: "
                                "face, location, object, ocr, place, scene, transcript",
                                "error_code": "INVALID_KIND",
                                "timestamp": "2025-05-19T02:22:21Z",
                            },
                        },
                        "invalid_direction": {
                            "summary": "Invalid direction",
                            "value": {
                                "detail": "Direction must be 'next' or 'prev'",
                                "error_code": "INVALID_DIRECTION",
                                "timestamp": "2025-05-19T02:22:21Z",
                            },
                        },
                        "conflicting_filters": {
                            "summary": "Conflicting filters",
                            "value": {
                                "detail": "Cannot specify both label and query",
                                "error_code": "CONFLICTING_FILTERS",
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
    kind: str = Query(..., description="Type of artifact to search for"),
    direction: str = Query(..., description="Navigation direction: next or prev"),
    from_video_id: str = Query(..., description="Starting video ID"),
    from_ms: int | None = Query(None, description="Starting timestamp in ms"),
    label: str | None = Query(None, description="Filter by label"),
    query: str | None = Query(None, description="Text search query"),
    face_cluster_id: str | None = Query(None, description="Filter by face cluster ID"),
    min_confidence: float | None = Query(None, description="Min confidence (0-1)"),
    limit: int = Query(1, description="Maximum results (1-50)"),
    service: GlobalJumpService = Depends(get_global_jump_service),
) -> GlobalJumpResponseSchema | JSONResponse:
    """Navigate across videos to find artifacts in chronological order."""
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

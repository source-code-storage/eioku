"""API controller for artifact gallery search.

Provides endpoints for searching artifacts across all videos with pagination,
filtering, and thumbnail URLs for gallery-style display.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database.connection import get_db

router = APIRouter(prefix="/artifacts", tags=["artifacts"])

# Mapping from user-friendly kind names to internal artifact_type values
KIND_TO_ARTIFACT_TYPE = {
    "object": "object.detection",
    "face": "face.detection",
    "transcript": "transcript.segment",
    "ocr": "ocr.text",
    "scene": "scene",
    "place": "place.classification",
}


def build_search_query(
    artifact_type: str,
    label: str | None = None,
    query: str | None = None,
    filename: str | None = None,
    min_confidence: float | None = None,
    group_by_video: bool = False,
) -> tuple[str, str, dict]:
    """Build SQL query for artifact search with filters.

    Constructs the main query and count query based on filters and grouping mode.
    Uses window functions for group_by_video to get first artifact per video.

    Args:
        artifact_type: Internal artifact type (e.g., 'object.detection')
        label: Label filter for object/place artifacts
        query: Text query filter for transcript/ocr artifacts
        filename: Video filename filter (case-insensitive partial match)
        min_confidence: Minimum confidence threshold
        group_by_video: If True, collapse results to one per video

    Returns:
        Tuple of (main_query, count_query, params_dict)
    """
    params: dict = {"artifact_type": artifact_type}

    # Build filter conditions (shared between grouped and ungrouped queries)
    filter_conditions = ""

    if label:
        filter_conditions += " AND a.payload_json->>'label' = :label"
        params["label"] = label

    if query:
        filter_conditions += " AND a.payload_json->>'text' ILIKE '%' || :query || '%'"
        params["query"] = query

    if filename:
        filter_conditions += " AND v.filename ILIKE '%' || :filename || '%'"
        params["filename"] = filename

    if min_confidence is not None:
        filter_conditions += (
            " AND (a.payload_json->>'confidence')::float >= :min_confidence"
        )
        params["min_confidence"] = min_confidence

    if group_by_video:
        # Grouped: Use window function to get first artifact per video + count
        main_query = f"""
            WITH ranked AS (
                SELECT
                    a.artifact_id,
                    a.asset_id as video_id,
                    a.artifact_type,
                    a.span_start_ms as start_ms,
                    a.payload_json as preview,
                    v.filename as video_filename,
                    v.file_created_at,
                    ROW_NUMBER() OVER (
                        PARTITION BY a.asset_id
                        ORDER BY a.span_start_ms ASC
                    ) as rn,
                    COUNT(*) OVER (PARTITION BY a.asset_id) as artifact_count
                FROM artifacts a
                JOIN videos v ON v.video_id = a.asset_id
                WHERE a.artifact_type = :artifact_type
                {filter_conditions}
            )
            SELECT artifact_id, video_id, artifact_type, start_ms, preview,
                   video_filename, file_created_at, artifact_count
            FROM ranked WHERE rn = 1
        """

        # Count query for grouped mode counts distinct videos
        count_query = f"""
            SELECT COUNT(DISTINCT a.asset_id)
            FROM artifacts a
            JOIN videos v ON v.video_id = a.asset_id
            WHERE a.artifact_type = :artifact_type
            {filter_conditions}
        """
    else:
        # Ungrouped: Return all matching artifacts
        main_query = f"""
            SELECT
                a.artifact_id,
                a.asset_id as video_id,
                a.artifact_type,
                a.span_start_ms as start_ms,
                a.payload_json as preview,
                v.filename as video_filename,
                v.file_created_at
            FROM artifacts a
            JOIN videos v ON v.video_id = a.asset_id
            WHERE a.artifact_type = :artifact_type
            {filter_conditions}
        """

        # Count query for ungrouped mode counts all matching artifacts
        count_query = f"""
            SELECT COUNT(*)
            FROM artifacts a
            JOIN videos v ON v.video_id = a.asset_id
            WHERE a.artifact_type = :artifact_type
            {filter_conditions}
        """

    return main_query, count_query, params


class ArtifactSearchResult(BaseModel):
    """Schema for a single artifact search result.

    Contains all information needed to display an artifact in a gallery view,
    including thumbnail URL and video metadata.
    """

    video_id: str = Field(
        ...,
        description="Unique identifier of the video containing the artifact",
        examples=["abc-123", "video_001"],
    )
    artifact_id: str = Field(
        ...,
        description="Unique identifier of the artifact",
        examples=["obj_xyz_001", "face_abc_002"],
    )
    artifact_type: str = Field(
        ...,
        description="Type of artifact (e.g., object.detection, face.detection)",
        examples=["object.detection", "transcript.segment"],
    )
    start_ms: int = Field(
        ...,
        description="Start timestamp in milliseconds",
        ge=0,
        examples=[0, 15000, 120000],
    )
    thumbnail_url: str = Field(
        ...,
        description="URL to the thumbnail image for this artifact's timestamp",
        examples=["/v1/thumbnails/abc-123/15000"],
    )
    preview: dict = Field(
        ...,
        description=(
            "Artifact payload data for preview display. Contents vary by type:\n"
            '- **object**: `{"label": "dog", "confidence": 0.95}`\n'
            '- **face**: `{"cluster_id": "person_001", "confidence": 0.89}`\n'
            '- **transcript**: `{"text": "...matched text..."}`\n'
            '- **ocr**: `{"text": "...detected text..."}`'
        ),
        examples=[
            {"label": "dog", "confidence": 0.95},
            {"text": "Hello world"},
        ],
    )
    video_filename: str = Field(
        ...,
        description="Filename of the video for display in UI",
        examples=["beach_trip.mp4", "meeting_2025-01-15.mp4"],
    )
    file_created_at: str | None = Field(
        None,
        description="ISO format timestamp of video file creation date",
        examples=["2025-05-19T02:22:21Z"],
    )
    artifact_count: int | None = Field(
        None,
        description=(
            "Total count of matching artifacts in this video. "
            "Only present when group_by_video=true"
        ),
        examples=[5, 42],
    )

    class Config:
        json_schema_extra = {
            "example": {
                "video_id": "abc-123",
                "artifact_id": "obj_xyz_001",
                "artifact_type": "object.detection",
                "start_ms": 15000,
                "thumbnail_url": "/v1/thumbnails/abc-123/15000",
                "preview": {"label": "dog", "confidence": 0.95},
                "video_filename": "beach_trip.mp4",
                "file_created_at": "2025-05-19T02:22:21Z",
                "artifact_count": None,
            }
        }


class ArtifactSearchResponse(BaseModel):
    """Schema for artifact search API response.

    Contains paginated search results with total count for pagination UI.
    Results are ordered by global timeline (file_created_at, video_id, start_ms).
    """

    results: list[ArtifactSearchResult] = Field(
        ...,
        description=(
            "List of matching artifacts ordered by global timeline. "
            "Ordering uses three sort keys:\n"
            "1. **file_created_at** (primary): Video creation date\n"
            "2. **video_id** (secondary): For deterministic ordering\n"
            "3. **start_ms** (tertiary): Artifact timestamp within video"
        ),
    )
    total: int = Field(
        ...,
        description="Total count of matching artifacts for pagination UI",
        ge=0,
        examples=[150, 0, 1000],
    )
    limit: int = Field(
        ...,
        description="Maximum number of results per page",
        ge=1,
        le=100,
        examples=[20, 50],
    )
    offset: int = Field(
        ...,
        description="Number of results skipped (for pagination)",
        ge=0,
        examples=[0, 20, 100],
    )

    class Config:
        json_schema_extra = {
            "example": {
                "results": [
                    {
                        "video_id": "abc-123",
                        "artifact_id": "obj_xyz_001",
                        "artifact_type": "object.detection",
                        "start_ms": 15000,
                        "thumbnail_url": "/v1/thumbnails/abc-123/15000",
                        "preview": {"label": "dog", "confidence": 0.95},
                        "video_filename": "beach_trip.mp4",
                        "file_created_at": "2025-05-19T02:22:21Z",
                        "artifact_count": None,
                    }
                ],
                "total": 150,
                "limit": 20,
                "offset": 0,
            }
        }


# Endpoint implementation will be added in Tasks 12-15


@router.get("/search", response_model=ArtifactSearchResponse)
async def search_artifacts(
    kind: str = Query(
        ...,
        description="Artifact type: object, face, transcript, ocr, scene, place",
    ),
    label: str | None = Query(
        None,
        description="Label filter for object/place",
    ),
    query: str | None = Query(
        None,
        description="Text query for transcript/ocr",
    ),
    filename: str | None = Query(
        None,
        description="Filter by video filename (case-insensitive partial match)",
    ),
    min_confidence: float | None = Query(
        None,
        ge=0,
        le=1,
        description="Minimum confidence threshold (0-1)",
    ),
    limit: int = Query(
        20,
        ge=1,
        le=100,
        description="Maximum number of results to return",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of results to skip for pagination",
    ),
    group_by_video: bool = Query(
        False,
        description="Collapse results to one per video",
    ),
    session: Session = Depends(get_db),
) -> ArtifactSearchResponse:
    """Search artifacts across all videos with pagination.

    Returns results ordered by global timeline with thumbnail URLs.
    When group_by_video=true, returns one result per video with artifact_count.

    **Artifact Types:**
    - **object**: Object detections (dogs, cars, etc.) - use `label` filter
    - **face**: Face detections - use `label` filter for cluster_id
    - **transcript**: Speech transcriptions - use `query` filter
    - **ocr**: Text detected in video - use `query` filter
    - **scene**: Scene classifications
    - **place**: Place classifications - use `label` filter

    **Examples:**
    - Find all dogs: `?kind=object&label=dog`
    - Search transcripts: `?kind=transcript&query=hello`
    - Filter by video: `?kind=object&filename=beach`
    - High confidence only: `?kind=face&min_confidence=0.9`
    """
    # Map kind to artifact_type
    artifact_type = KIND_TO_ARTIFACT_TYPE.get(kind)
    if artifact_type is None:
        valid_kinds = ", ".join(KIND_TO_ARTIFACT_TYPE.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Invalid kind '{kind}'. Valid kinds are: {valid_kinds}",
        )

    # Build search query with filters (Task 13)
    main_query, count_query, params = build_search_query(
        artifact_type=artifact_type,
        label=label,
        query=query,
        filename=filename,
        min_confidence=min_confidence,
        group_by_video=group_by_video,
    )

    # Get total count for pagination
    total = session.execute(text(count_query), params).scalar() or 0

    # Add ordering and pagination (Task 14 will refine this)
    main_query += """
        ORDER BY file_created_at ASC NULLS LAST, video_id ASC, start_ms ASC
        LIMIT :limit OFFSET :offset
    """
    params["limit"] = limit
    params["offset"] = offset

    # Execute query
    rows = session.execute(text(main_query), params).fetchall()

    # Build response (Task 15 will add thumbnail URLs)
    results = [
        ArtifactSearchResult(
            video_id=row.video_id,
            artifact_id=row.artifact_id,
            artifact_type=row.artifact_type,
            start_ms=row.start_ms,
            thumbnail_url=f"/v1/thumbnails/{row.video_id}/{row.start_ms}",
            preview=row.preview if row.preview else {},
            video_filename=row.video_filename,
            file_created_at=(
                row.file_created_at.isoformat() if row.file_created_at else None
            ),
            artifact_count=getattr(row, "artifact_count", None),
        )
        for row in rows
    ]

    return ArtifactSearchResponse(
        results=results,
        total=total,
        limit=limit,
        offset=offset,
    )

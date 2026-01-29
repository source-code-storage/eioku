"""Service layer for Global Jump Navigation.

This module provides the GlobalJumpService class which orchestrates cross-video
artifact search and navigation. It enables users to search for objects, faces,
text, and scenes across their entire video library in chronological order.

The service uses existing projection tables (object_labels, face_clusters,
transcript_fts, ocr_fts, scene_ranges, video_locations) to provide fast queries
without requiring new data structures.
"""

import logging
from typing import Literal

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..database.models import ObjectLabel
from ..database.models import Video as VideoEntity
from ..domain.exceptions import VideoNotFoundError
from ..domain.models import GlobalJumpResult, JumpTo
from ..repositories.interfaces import ArtifactRepository

logger = logging.getLogger(__name__)


class GlobalJumpService:
    """Service for cross-video artifact search and navigation.

    GlobalJumpService provides methods to navigate across videos in chronological
    order based on artifact searches. It supports searching by object labels,
    face clusters, transcript text, OCR text, scenes, places, and locations.

    The service uses a deterministic global timeline based on:
    1. file_created_at (EXIF/filesystem date) as primary sort key
    2. video_id as secondary sort key (for deterministic ordering)
    3. start_ms as tertiary sort key (for ordering within a video)

    Attributes:
        session: SQLAlchemy database session for executing queries
        artifact_repo: Repository for accessing artifact data
    """

    def __init__(self, session: Session, artifact_repo: ArtifactRepository):
        """Initialize GlobalJumpService.

        Args:
            session: SQLAlchemy database session for executing queries.
            artifact_repo: Repository for accessing artifact envelope data.
        """
        self.session = session
        self.artifact_repo = artifact_repo

    def _get_video(self, video_id: str) -> VideoEntity:
        """Fetch a video by ID from the database.

        Args:
            video_id: Unique identifier of the video to fetch.

        Returns:
            VideoEntity: The SQLAlchemy video entity with all metadata.

        Raises:
            VideoNotFoundError: If no video exists with the given ID.
        """
        video = (
            self.session.query(VideoEntity)
            .filter(VideoEntity.video_id == video_id)
            .first()
        )

        if video is None:
            raise VideoNotFoundError(video_id)

        return video

    def _to_global_result(
        self,
        video_id: str,
        video_filename: str,
        file_created_at,
        start_ms: int,
        end_ms: int,
        artifact_id: str,
        preview: dict,
    ) -> GlobalJumpResult:
        """Convert database row data to a GlobalJumpResult object.

        Args:
            video_id: Unique identifier of the video containing the artifact.
            video_filename: Filename of the video for display purposes.
            file_created_at: EXIF/filesystem creation date of the video.
            start_ms: Start timestamp in milliseconds.
            end_ms: End timestamp in milliseconds.
            artifact_id: Unique identifier of the specific artifact occurrence.
            preview: Kind-specific preview data.

        Returns:
            GlobalJumpResult: A formatted result object ready for API response.
        """
        return GlobalJumpResult(
            video_id=video_id,
            video_filename=video_filename,
            file_created_at=file_created_at,
            jump_to=JumpTo(start_ms=start_ms, end_ms=end_ms),
            artifact_id=artifact_id,
            preview=preview,
        )

    def _search_objects_global(
        self,
        direction: Literal["next", "prev"],
        from_video_id: str,
        from_ms: int,
        label: str | None = None,
        min_confidence: float | None = None,
        limit: int = 1,
    ) -> list[GlobalJumpResult]:
        """Search for object labels across all videos in global timeline order.

        Queries the object_labels projection table joined with videos to find
        matching objects in chronological order based on the global timeline.

        Args:
            direction: Navigation direction ("next" for forward, "prev" for backward).
            from_video_id: Starting video ID for the search.
            from_ms: Starting timestamp in milliseconds within the video.
            label: Optional label filter to match specific object types.
            min_confidence: Optional minimum confidence threshold (0-1).
            limit: Maximum number of results to return (default 1).

        Returns:
            List of GlobalJumpResult objects ordered by global timeline.
            For "next": ascending order (chronologically after current position).
            For "prev": descending order (chronologically before current position).
            Empty list if no matching objects are found.

        Raises:
            VideoNotFoundError: If from_video_id does not exist.
        """
        # Get the current video to determine its position in the global timeline
        current_video = self._get_video(from_video_id)
        current_file_created_at = current_video.file_created_at

        # Build base query joining object_labels with videos
        query = self.session.query(
            ObjectLabel.artifact_id,
            ObjectLabel.asset_id,
            ObjectLabel.label,
            ObjectLabel.confidence,
            ObjectLabel.start_ms,
            ObjectLabel.end_ms,
            VideoEntity.filename,
            VideoEntity.file_created_at,
        ).join(VideoEntity, VideoEntity.video_id == ObjectLabel.asset_id)

        # Apply label filter if specified
        if label is not None:
            query = query.filter(ObjectLabel.label == label)

        # Apply min_confidence filter if specified
        if min_confidence is not None:
            query = query.filter(ObjectLabel.confidence >= min_confidence)

        # Apply direction-specific WHERE clause for "next" direction
        # Results must be chronologically after the current position
        # Global timeline ordering: file_created_at > video_id > start_ms
        if direction == "next":
            # Handle NULL file_created_at values
            # NULLs are treated as "unknown" and sorted after non-NULL values
            if current_file_created_at is not None:
                query = query.filter(
                    or_(
                        # Case 1: Videos with later file_created_at
                        VideoEntity.file_created_at > current_file_created_at,
                        # Case 2: Videos with NULL file_created_at (sorted after)
                        VideoEntity.file_created_at.is_(None),
                        # Case 3: Same file_created_at, later video_id
                        and_(
                            VideoEntity.file_created_at == current_file_created_at,
                            VideoEntity.video_id > from_video_id,
                        ),
                        # Case 4: Same video, later start_ms
                        and_(
                            VideoEntity.file_created_at == current_file_created_at,
                            VideoEntity.video_id == from_video_id,
                            ObjectLabel.start_ms > from_ms,
                        ),
                    )
                )
            else:
                # Current video has NULL file_created_at
                # Only consider videos with NULL file_created_at
                query = query.filter(
                    or_(
                        # Case 1: Same NULL file_created_at, later video_id
                        and_(
                            VideoEntity.file_created_at.is_(None),
                            VideoEntity.video_id > from_video_id,
                        ),
                        # Case 2: Same video, later start_ms
                        and_(
                            VideoEntity.file_created_at.is_(None),
                            VideoEntity.video_id == from_video_id,
                            ObjectLabel.start_ms > from_ms,
                        ),
                    )
                )

            # Order by global timeline (ascending for "next")
            # NULLS LAST ensures NULL file_created_at values come after non-NULL
            query = query.order_by(
                VideoEntity.file_created_at.asc().nulls_last(),
                VideoEntity.video_id.asc(),
                ObjectLabel.start_ms.asc(),
            )

        elif direction == "prev":
            # Apply direction-specific WHERE clause for "prev" direction
            # Results must be chronologically before the current position
            # Global timeline ordering: file_created_at > video_id > start_ms
            if current_file_created_at is not None:
                query = query.filter(
                    or_(
                        # Case 1: Videos with earlier file_created_at
                        and_(
                            VideoEntity.file_created_at.is_not(None),
                            VideoEntity.file_created_at < current_file_created_at,
                        ),
                        # Case 2: Same file_created_at, earlier video_id
                        and_(
                            VideoEntity.file_created_at == current_file_created_at,
                            VideoEntity.video_id < from_video_id,
                        ),
                        # Case 3: Same video, earlier start_ms
                        and_(
                            VideoEntity.file_created_at == current_file_created_at,
                            VideoEntity.video_id == from_video_id,
                            ObjectLabel.start_ms < from_ms,
                        ),
                    )
                )
            else:
                # Current video has NULL file_created_at
                # Consider all videos with non-NULL file_created_at (they come
                # before) and videos with NULL file_created_at that are earlier
                # in video_id order
                query = query.filter(
                    or_(
                        # Case 1: Videos with non-NULL file_created_at
                        # (come before NULLs)
                        VideoEntity.file_created_at.is_not(None),
                        # Case 2: Same NULL file_created_at, earlier video_id
                        and_(
                            VideoEntity.file_created_at.is_(None),
                            VideoEntity.video_id < from_video_id,
                        ),
                        # Case 3: Same video, earlier start_ms
                        and_(
                            VideoEntity.file_created_at.is_(None),
                            VideoEntity.video_id == from_video_id,
                            ObjectLabel.start_ms < from_ms,
                        ),
                    )
                )

            # Order by global timeline (descending for "prev")
            # NULLS LAST ensures NULL file_created_at values come last in
            # descending order (which means they were originally last in
            # ascending order)
            query = query.order_by(
                VideoEntity.file_created_at.desc().nulls_last(),
                VideoEntity.video_id.desc(),
                ObjectLabel.start_ms.desc(),
            )

        # Apply limit
        query = query.limit(limit)

        # Execute query and convert results to GlobalJumpResult objects
        results = []
        for row in query.all():
            result = self._to_global_result(
                video_id=row.asset_id,
                video_filename=row.filename,
                file_created_at=row.file_created_at,
                start_ms=row.start_ms,
                end_ms=row.end_ms,
                artifact_id=row.artifact_id,
                preview={
                    "label": row.label,
                    "confidence": row.confidence,
                },
            )
            results.append(result)

        logger.debug(
            f"_search_objects_global: direction={direction}, "
            f"from_video_id={from_video_id}, from_ms={from_ms}, "
            f"label={label}, min_confidence={min_confidence}, "
            f"found {len(results)} results"
        )

        return results

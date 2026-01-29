"""Service layer for Global Jump Navigation.

This module provides the GlobalJumpService class which orchestrates cross-video
artifact search and navigation. It enables users to search for objects, faces,
text, and scenes across their entire video library in chronological order.

The service uses existing projection tables (object_labels, face_clusters,
transcript_fts, ocr_fts, scene_ranges, video_locations) to provide fast queries
without requiring new data structures.
"""

import logging

from sqlalchemy.orm import Session

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

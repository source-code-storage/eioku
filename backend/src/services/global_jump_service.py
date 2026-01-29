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

from sqlalchemy import and_, or_, text
from sqlalchemy.orm import Session

from ..database.models import ObjectLabel, SceneRange
from ..database.models import Video as VideoEntity
from ..domain.exceptions import InvalidParameterError, VideoNotFoundError
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

    def _search_transcript_global(
        self,
        direction: Literal["next", "prev"],
        from_video_id: str,
        from_ms: int,
        query: str,
        limit: int = 1,
    ) -> list[GlobalJumpResult]:
        """Search for transcript text across all videos in global timeline order.

        Queries the transcript_fts projection table joined with videos to find
        matching transcript segments using PostgreSQL full-text search. Results
        are ordered by the global timeline.

        Args:
            direction: Navigation direction ("next" or "prev").
            from_video_id: Starting video ID for the search.
            from_ms: Starting timestamp in milliseconds within the video.
            query: Text query to search for in transcripts.
            limit: Maximum number of results to return (default 1).

        Returns:
            List of GlobalJumpResult objects ordered by global timeline.
            For "next": ascending order (chronologically after current position).
            For "prev": descending order (chronologically before current position).
            Empty list if no matching transcript segments are found.

        Raises:
            VideoNotFoundError: If from_video_id does not exist.
        """
        # Get the current video to determine its position in the global timeline
        current_video = self._get_video(from_video_id)
        current_file_created_at = current_video.file_created_at

        # Determine database dialect
        bind = self.session.bind
        is_postgresql = bind.dialect.name == "postgresql"

        if is_postgresql:
            return self._search_transcript_global_postgresql(
                direction, from_video_id, from_ms, query, limit, current_file_created_at
            )
        else:
            return self._search_transcript_global_sqlite(
                direction, from_video_id, from_ms, query, limit, current_file_created_at
            )

    def _search_transcript_global_postgresql(
        self,
        direction: Literal["next", "prev"],
        from_video_id: str,
        from_ms: int,
        query: str,
        limit: int,
        current_file_created_at,
    ) -> list[GlobalJumpResult]:
        """PostgreSQL implementation of transcript global search."""
        # Build direction-specific SQL components
        if direction == "next":
            order_clause = """
                ORDER BY v.file_created_at ASC NULLS LAST,
                         v.video_id ASC,
                         t.start_ms ASC
            """
            if current_file_created_at is not None:
                direction_clause = """
                    AND (
                        v.file_created_at > :current_file_created_at
                        OR v.file_created_at IS NULL
                        OR (v.file_created_at = :current_file_created_at
                            AND v.video_id > :from_video_id)
                        OR (v.file_created_at = :current_file_created_at
                            AND v.video_id = :from_video_id
                            AND t.start_ms > :from_ms)
                    )
                """
            else:
                direction_clause = """
                    AND (
                        (v.file_created_at IS NULL
                         AND v.video_id > :from_video_id)
                        OR (v.file_created_at IS NULL
                            AND v.video_id = :from_video_id
                            AND t.start_ms > :from_ms)
                    )
                """
        else:  # direction == "prev"
            order_clause = """
                ORDER BY v.file_created_at DESC NULLS LAST,
                         v.video_id DESC,
                         t.start_ms DESC
            """
            if current_file_created_at is not None:
                direction_clause = """
                    AND (
                        (v.file_created_at IS NOT NULL
                         AND v.file_created_at < :current_file_created_at)
                        OR (v.file_created_at = :current_file_created_at
                            AND v.video_id < :from_video_id)
                        OR (v.file_created_at = :current_file_created_at
                            AND v.video_id = :from_video_id
                            AND t.start_ms < :from_ms)
                    )
                """
            else:
                direction_clause = """
                    AND (
                        v.file_created_at IS NOT NULL
                        OR (v.file_created_at IS NULL
                            AND v.video_id < :from_video_id)
                        OR (v.file_created_at IS NULL
                            AND v.video_id = :from_video_id
                            AND t.start_ms < :from_ms)
                    )
                """

        # PostgreSQL: Use tsvector and tsquery with plainto_tsquery
        sql = text(
            f"""
            SELECT
                t.artifact_id,
                t.asset_id,
                t.start_ms,
                t.end_ms,
                t.text,
                v.filename,
                v.file_created_at
            FROM transcript_fts t
            JOIN videos v ON v.video_id = t.asset_id
            WHERE t.text_tsv @@ plainto_tsquery('english', :query)
            {direction_clause}
            {order_clause}
            LIMIT :limit
            """
        )

        params = {
            "query": query,
            "from_video_id": from_video_id,
            "from_ms": from_ms,
            "limit": limit,
        }
        if current_file_created_at is not None:
            params["current_file_created_at"] = current_file_created_at

        rows = self.session.execute(sql, params).fetchall()

        # If FTS returned no results, try case-insensitive LIKE search
        if not rows:
            sql_fallback = text(
                f"""
                SELECT
                    t.artifact_id,
                    t.asset_id,
                    t.start_ms,
                    t.end_ms,
                    t.text,
                    v.filename,
                    v.file_created_at
                FROM transcript_fts t
                JOIN videos v ON v.video_id = t.asset_id
                WHERE t.text ILIKE :query_like
                {direction_clause}
                {order_clause}
                LIMIT :limit
                """
            )

            params["query_like"] = f"%{query}%"
            rows = self.session.execute(sql_fallback, params).fetchall()

        # Convert results to GlobalJumpResult objects
        results = []
        for row in rows:
            result = self._to_global_result(
                video_id=row.asset_id,
                video_filename=row.filename,
                file_created_at=row.file_created_at,
                start_ms=row.start_ms,
                end_ms=row.end_ms,
                artifact_id=row.artifact_id,
                preview={"text": row.text},
            )
            results.append(result)

        logger.debug(
            f"_search_transcript_global: direction={direction}, "
            f"from_video_id={from_video_id}, from_ms={from_ms}, "
            f"query={query}, found {len(results)} results"
        )

        return results

    def _search_transcript_global_sqlite(
        self,
        direction: Literal["next", "prev"],
        from_video_id: str,
        from_ms: int,
        query: str,
        limit: int,
        current_file_created_at,
    ) -> list[GlobalJumpResult]:
        """SQLite implementation of transcript global search using FTS5."""
        # SQLite: Use FTS5 MATCH syntax
        # First get matching artifact_ids from FTS5 table
        fts_sql = text(
            """
            SELECT artifact_id, text
            FROM transcript_fts
            WHERE transcript_fts MATCH :query
            """
        )

        fts_rows = self.session.execute(fts_sql, {"query": query}).fetchall()

        if not fts_rows:
            return []

        # Get artifact_ids and text snippets
        artifact_ids = [row.artifact_id for row in fts_rows]
        text_map = {row.artifact_id: row.text for row in fts_rows}

        # Build placeholders for IN clause
        placeholders = ",".join([f":id{i}" for i in range(len(artifact_ids))])

        # Convert datetime to string for SQLite comparison
        current_file_created_at_str = None
        if current_file_created_at is not None:
            current_file_created_at_str = current_file_created_at.strftime(
                "%Y-%m-%d %H:%M:%S.%f"
            )

        # Build direction-specific SQL for SQLite (no NULLS LAST support)
        if direction == "next":
            # SQLite: Use CASE to handle NULL ordering (NULLs last)
            order_clause = """
                ORDER BY CASE WHEN v.file_created_at IS NULL THEN 1 ELSE 0 END,
                         v.file_created_at ASC,
                         v.video_id ASC,
                         m.start_ms ASC
            """
            if current_file_created_at_str is not None:
                direction_clause = """
                    AND (
                        v.file_created_at > :current_file_created_at
                        OR v.file_created_at IS NULL
                        OR (v.file_created_at = :current_file_created_at
                            AND v.video_id > :from_video_id)
                        OR (v.file_created_at = :current_file_created_at
                            AND v.video_id = :from_video_id
                            AND m.start_ms > :from_ms)
                    )
                """
            else:
                direction_clause = """
                    AND (
                        (v.file_created_at IS NULL
                         AND v.video_id > :from_video_id)
                        OR (v.file_created_at IS NULL
                            AND v.video_id = :from_video_id
                            AND m.start_ms > :from_ms)
                    )
                """
        else:  # direction == "prev"
            # SQLite: Use CASE to handle NULL ordering (NULLs last in DESC)
            order_clause = """
                ORDER BY CASE WHEN v.file_created_at IS NULL THEN 1 ELSE 0 END,
                         v.file_created_at DESC,
                         v.video_id DESC,
                         m.start_ms DESC
            """
            if current_file_created_at_str is not None:
                direction_clause = """
                    AND (
                        (v.file_created_at IS NOT NULL
                         AND v.file_created_at < :current_file_created_at)
                        OR (v.file_created_at = :current_file_created_at
                            AND v.video_id < :from_video_id)
                        OR (v.file_created_at = :current_file_created_at
                            AND v.video_id = :from_video_id
                            AND m.start_ms < :from_ms)
                    )
                """
            else:
                direction_clause = """
                    AND (
                        v.file_created_at IS NOT NULL
                        OR (v.file_created_at IS NULL
                            AND v.video_id < :from_video_id)
                        OR (v.file_created_at IS NULL
                            AND v.video_id = :from_video_id
                            AND m.start_ms < :from_ms)
                    )
                """

        # Get metadata with video info and apply direction filter
        metadata_sql = text(
            f"""
            SELECT
                m.artifact_id,
                m.asset_id,
                m.start_ms,
                m.end_ms,
                v.filename,
                v.file_created_at
            FROM transcript_fts_metadata m
            JOIN videos v ON v.video_id = m.asset_id
            WHERE m.artifact_id IN ({placeholders})
            {direction_clause}
            {order_clause}
            LIMIT :limit
            """
        )

        params = {f"id{i}": aid for i, aid in enumerate(artifact_ids)}
        params["from_video_id"] = from_video_id
        params["from_ms"] = from_ms
        params["limit"] = limit
        if current_file_created_at_str is not None:
            params["current_file_created_at"] = current_file_created_at_str

        rows = self.session.execute(metadata_sql, params).fetchall()

        # Convert to results with text from FTS
        results = []
        for row in rows:
            result = self._to_global_result(
                video_id=row.asset_id,
                video_filename=row.filename,
                file_created_at=row.file_created_at,
                start_ms=row.start_ms,
                end_ms=row.end_ms,
                artifact_id=row.artifact_id,
                preview={"text": text_map.get(row.artifact_id, "")},
            )
            results.append(result)

        logger.debug(
            f"_search_transcript_global: direction={direction}, "
            f"from_video_id={from_video_id}, from_ms={from_ms}, "
            f"query={query}, found {len(results)} results"
        )

        return results

    def _search_ocr_global(
        self,
        direction: Literal["next", "prev"],
        from_video_id: str,
        from_ms: int,
        query: str,
        limit: int = 1,
    ) -> list[GlobalJumpResult]:
        """Search for OCR text across all videos in global timeline order.

        Queries the ocr_fts projection table joined with videos to find
        matching OCR text segments using PostgreSQL full-text search. Results
        are ordered by the global timeline.

        Args:
            direction: Navigation direction ("next" or "prev").
            from_video_id: Starting video ID for the search.
            from_ms: Starting timestamp in milliseconds within the video.
            query: Text query to search for in OCR text.
            limit: Maximum number of results to return (default 1).

        Returns:
            List of GlobalJumpResult objects ordered by global timeline.
            For "next": ascending order (chronologically after current position).
            For "prev": descending order (chronologically before current position).
            Empty list if no matching OCR text segments are found.

        Raises:
            VideoNotFoundError: If from_video_id does not exist.
        """
        # Get the current video to determine its position in the global timeline
        current_video = self._get_video(from_video_id)
        current_file_created_at = current_video.file_created_at

        # Determine database dialect
        bind = self.session.bind
        is_postgresql = bind.dialect.name == "postgresql"

        if is_postgresql:
            return self._search_ocr_global_postgresql(
                direction,
                from_video_id,
                from_ms,
                query,
                limit,
                current_file_created_at,
            )
        else:
            return self._search_ocr_global_sqlite(
                direction,
                from_video_id,
                from_ms,
                query,
                limit,
                current_file_created_at,
            )

    def _search_ocr_global_postgresql(
        self,
        direction: Literal["next", "prev"],
        from_video_id: str,
        from_ms: int,
        query: str,
        limit: int,
        current_file_created_at,
    ) -> list[GlobalJumpResult]:
        """PostgreSQL implementation of OCR global search."""
        # Build direction-specific SQL components
        if direction == "next":
            order_clause = """
                ORDER BY v.file_created_at ASC NULLS LAST,
                         v.video_id ASC,
                         o.start_ms ASC
            """
            if current_file_created_at is not None:
                direction_clause = """
                    AND (
                        v.file_created_at > :current_file_created_at
                        OR v.file_created_at IS NULL
                        OR (v.file_created_at = :current_file_created_at
                            AND v.video_id > :from_video_id)
                        OR (v.file_created_at = :current_file_created_at
                            AND v.video_id = :from_video_id
                            AND o.start_ms > :from_ms)
                    )
                """
            else:
                direction_clause = """
                    AND (
                        (v.file_created_at IS NULL
                         AND v.video_id > :from_video_id)
                        OR (v.file_created_at IS NULL
                            AND v.video_id = :from_video_id
                            AND o.start_ms > :from_ms)
                    )
                """
        else:  # direction == "prev"
            order_clause = """
                ORDER BY v.file_created_at DESC NULLS LAST,
                         v.video_id DESC,
                         o.start_ms DESC
            """
            if current_file_created_at is not None:
                direction_clause = """
                    AND (
                        (v.file_created_at IS NOT NULL
                         AND v.file_created_at < :current_file_created_at)
                        OR (v.file_created_at = :current_file_created_at
                            AND v.video_id < :from_video_id)
                        OR (v.file_created_at = :current_file_created_at
                            AND v.video_id = :from_video_id
                            AND o.start_ms < :from_ms)
                    )
                """
            else:
                direction_clause = """
                    AND (
                        v.file_created_at IS NOT NULL
                        OR (v.file_created_at IS NULL
                            AND v.video_id < :from_video_id)
                        OR (v.file_created_at IS NULL
                            AND v.video_id = :from_video_id
                            AND o.start_ms < :from_ms)
                    )
                """

        # PostgreSQL: Use tsvector and tsquery with plainto_tsquery
        sql = text(
            f"""
            SELECT
                o.artifact_id,
                o.asset_id,
                o.start_ms,
                o.end_ms,
                o.text,
                v.filename,
                v.file_created_at
            FROM ocr_fts o
            JOIN videos v ON v.video_id = o.asset_id
            WHERE o.text_tsv @@ plainto_tsquery('english', :query)
            {direction_clause}
            {order_clause}
            LIMIT :limit
            """
        )

        params = {
            "query": query,
            "from_video_id": from_video_id,
            "from_ms": from_ms,
            "limit": limit,
        }
        if current_file_created_at is not None:
            params["current_file_created_at"] = current_file_created_at

        rows = self.session.execute(sql, params).fetchall()

        # If FTS returned no results, try case-insensitive LIKE search
        if not rows:
            sql_fallback = text(
                f"""
                SELECT
                    o.artifact_id,
                    o.asset_id,
                    o.start_ms,
                    o.end_ms,
                    o.text,
                    v.filename,
                    v.file_created_at
                FROM ocr_fts o
                JOIN videos v ON v.video_id = o.asset_id
                WHERE o.text ILIKE :query_like
                {direction_clause}
                {order_clause}
                LIMIT :limit
                """
            )

            params["query_like"] = f"%{query}%"
            rows = self.session.execute(sql_fallback, params).fetchall()

        # Convert results to GlobalJumpResult objects
        results = []
        for row in rows:
            result = self._to_global_result(
                video_id=row.asset_id,
                video_filename=row.filename,
                file_created_at=row.file_created_at,
                start_ms=row.start_ms,
                end_ms=row.end_ms,
                artifact_id=row.artifact_id,
                preview={"text": row.text},
            )
            results.append(result)

        logger.debug(
            f"_search_ocr_global: direction={direction}, "
            f"from_video_id={from_video_id}, from_ms={from_ms}, "
            f"query={query}, found {len(results)} results"
        )

        return results

    def _search_ocr_global_sqlite(
        self,
        direction: Literal["next", "prev"],
        from_video_id: str,
        from_ms: int,
        query: str,
        limit: int,
        current_file_created_at,
    ) -> list[GlobalJumpResult]:
        """SQLite implementation of OCR global search using FTS5."""
        # SQLite: Use FTS5 MATCH syntax
        # First get matching artifact_ids from FTS5 table
        fts_sql = text(
            """
            SELECT artifact_id, text
            FROM ocr_fts
            WHERE ocr_fts MATCH :query
            """
        )

        fts_rows = self.session.execute(fts_sql, {"query": query}).fetchall()

        if not fts_rows:
            return []

        # Get artifact_ids and text snippets
        artifact_ids = [row.artifact_id for row in fts_rows]
        text_map = {row.artifact_id: row.text for row in fts_rows}

        # Build placeholders for IN clause
        placeholders = ",".join([f":id{i}" for i in range(len(artifact_ids))])

        # Convert datetime to string for SQLite comparison
        current_file_created_at_str = None
        if current_file_created_at is not None:
            current_file_created_at_str = current_file_created_at.strftime(
                "%Y-%m-%d %H:%M:%S.%f"
            )

        # Build direction-specific SQL for SQLite (no NULLS LAST support)
        if direction == "next":
            # SQLite: Use CASE to handle NULL ordering (NULLs last)
            order_clause = """
                ORDER BY CASE WHEN v.file_created_at IS NULL THEN 1 ELSE 0 END,
                         v.file_created_at ASC,
                         v.video_id ASC,
                         m.start_ms ASC
            """
            if current_file_created_at_str is not None:
                direction_clause = """
                    AND (
                        v.file_created_at > :current_file_created_at
                        OR v.file_created_at IS NULL
                        OR (v.file_created_at = :current_file_created_at
                            AND v.video_id > :from_video_id)
                        OR (v.file_created_at = :current_file_created_at
                            AND v.video_id = :from_video_id
                            AND m.start_ms > :from_ms)
                    )
                """
            else:
                direction_clause = """
                    AND (
                        (v.file_created_at IS NULL
                         AND v.video_id > :from_video_id)
                        OR (v.file_created_at IS NULL
                            AND v.video_id = :from_video_id
                            AND m.start_ms > :from_ms)
                    )
                """
        else:  # direction == "prev"
            # SQLite: Use CASE to handle NULL ordering (NULLs last in DESC)
            order_clause = """
                ORDER BY CASE WHEN v.file_created_at IS NULL THEN 1 ELSE 0 END,
                         v.file_created_at DESC,
                         v.video_id DESC,
                         m.start_ms DESC
            """
            if current_file_created_at_str is not None:
                direction_clause = """
                    AND (
                        (v.file_created_at IS NOT NULL
                         AND v.file_created_at < :current_file_created_at)
                        OR (v.file_created_at = :current_file_created_at
                            AND v.video_id < :from_video_id)
                        OR (v.file_created_at = :current_file_created_at
                            AND v.video_id = :from_video_id
                            AND m.start_ms < :from_ms)
                    )
                """
            else:
                direction_clause = """
                    AND (
                        v.file_created_at IS NOT NULL
                        OR (v.file_created_at IS NULL
                            AND v.video_id < :from_video_id)
                        OR (v.file_created_at IS NULL
                            AND v.video_id = :from_video_id
                            AND m.start_ms < :from_ms)
                    )
                """

        # Get metadata with video info and apply direction filter
        metadata_sql = text(
            f"""
            SELECT
                m.artifact_id,
                m.asset_id,
                m.start_ms,
                m.end_ms,
                v.filename,
                v.file_created_at
            FROM ocr_fts_metadata m
            JOIN videos v ON v.video_id = m.asset_id
            WHERE m.artifact_id IN ({placeholders})
            {direction_clause}
            {order_clause}
            LIMIT :limit
            """
        )

        params = {f"id{i}": aid for i, aid in enumerate(artifact_ids)}
        params["from_video_id"] = from_video_id
        params["from_ms"] = from_ms
        params["limit"] = limit
        if current_file_created_at_str is not None:
            params["current_file_created_at"] = current_file_created_at_str

        rows = self.session.execute(metadata_sql, params).fetchall()

        # Convert to results with text from FTS
        results = []
        for row in rows:
            result = self._to_global_result(
                video_id=row.asset_id,
                video_filename=row.filename,
                file_created_at=row.file_created_at,
                start_ms=row.start_ms,
                end_ms=row.end_ms,
                artifact_id=row.artifact_id,
                preview={"text": text_map.get(row.artifact_id, "")},
            )
            results.append(result)

        logger.debug(
            f"_search_ocr_global: direction={direction}, "
            f"from_video_id={from_video_id}, from_ms={from_ms}, "
            f"query={query}, found {len(results)} results"
        )

        return results

    def _search_scenes_global(
        self,
        direction: Literal["next", "prev"],
        from_video_id: str,
        from_ms: int,
        limit: int = 1,
    ) -> list[GlobalJumpResult]:
        """Search for scene boundaries across all videos in global timeline order.

        Queries the scene_ranges projection table joined with videos to find
        scene boundaries in chronological order based on the global timeline.

        Args:
            direction: Navigation direction ("next" for forward, "prev" for backward).
            from_video_id: Starting video ID for the search.
            from_ms: Starting timestamp in milliseconds within the video.
            limit: Maximum number of results to return (default 1).

        Returns:
            List of GlobalJumpResult objects ordered by global timeline.
            For "next": ascending order (chronologically after current position).
            For "prev": descending order (chronologically before current position).
            Empty list if no scene boundaries are found.

        Raises:
            VideoNotFoundError: If from_video_id does not exist.
        """
        # Get the current video to determine its position in the global timeline
        current_video = self._get_video(from_video_id)
        current_file_created_at = current_video.file_created_at

        # Build base query joining scene_ranges with videos
        query = self.session.query(
            SceneRange.artifact_id,
            SceneRange.asset_id,
            SceneRange.scene_index,
            SceneRange.start_ms,
            SceneRange.end_ms,
            VideoEntity.filename,
            VideoEntity.file_created_at,
        ).join(VideoEntity, VideoEntity.video_id == SceneRange.asset_id)

        # Apply direction-specific WHERE clause
        if direction == "next":
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
                            SceneRange.start_ms > from_ms,
                        ),
                    )
                )
            else:
                query = query.filter(
                    or_(
                        and_(
                            VideoEntity.file_created_at.is_(None),
                            VideoEntity.video_id > from_video_id,
                        ),
                        and_(
                            VideoEntity.file_created_at.is_(None),
                            VideoEntity.video_id == from_video_id,
                            SceneRange.start_ms > from_ms,
                        ),
                    )
                )

            # Order by global timeline (ascending for "next")
            query = query.order_by(
                VideoEntity.file_created_at.asc().nulls_last(),
                VideoEntity.video_id.asc(),
                SceneRange.start_ms.asc(),
            )

        elif direction == "prev":
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
                            SceneRange.start_ms < from_ms,
                        ),
                    )
                )
            else:
                query = query.filter(
                    or_(
                        VideoEntity.file_created_at.is_not(None),
                        and_(
                            VideoEntity.file_created_at.is_(None),
                            VideoEntity.video_id < from_video_id,
                        ),
                        and_(
                            VideoEntity.file_created_at.is_(None),
                            VideoEntity.video_id == from_video_id,
                            SceneRange.start_ms < from_ms,
                        ),
                    )
                )

            # Order by global timeline (descending for "prev")
            query = query.order_by(
                VideoEntity.file_created_at.desc().nulls_last(),
                VideoEntity.video_id.desc(),
                SceneRange.start_ms.desc(),
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
                    "scene_index": row.scene_index,
                },
            )
            results.append(result)

        logger.debug(
            f"_search_scenes_global: direction={direction}, "
            f"from_video_id={from_video_id}, from_ms={from_ms}, "
            f"found {len(results)} results"
        )

        return results

    def _search_places_global(
        self,
        direction: Literal["next", "prev"],
        from_video_id: str,
        from_ms: int,
        label: str | None = None,
        min_confidence: float | None = None,
        limit: int = 1,
    ) -> list[GlobalJumpResult]:
        """Search for place classifications across all videos in global timeline order.

        Place classifications are stored in the object_labels projection table
        with place-specific labels (e.g., "kitchen", "beach", "office").
        This method queries object_labels with place-related filters.

        Args:
            direction: Navigation direction ("next" for forward, "prev" for backward).
            from_video_id: Starting video ID for the search.
            from_ms: Starting timestamp in milliseconds within the video.
            label: Optional place label filter (e.g., "kitchen", "beach").
            min_confidence: Optional minimum confidence threshold (0-1).
            limit: Maximum number of results to return (default 1).

        Returns:
            List of GlobalJumpResult objects ordered by global timeline.
            For "next": ascending order (chronologically after current position).
            For "prev": descending order (chronologically before current position).
            Empty list if no matching places are found.

        Raises:
            VideoNotFoundError: If from_video_id does not exist.

        Note:
            Place classifications are stored in object_labels with labels from
            the Places365 dataset. This method reuses the object search logic
            but is semantically distinct for place-based navigation.
        """
        # Place search uses the same underlying table as object search
        # but is semantically distinct for place-based navigation
        return self._search_objects_global(
            direction=direction,
            from_video_id=from_video_id,
            from_ms=from_ms,
            label=label,
            min_confidence=min_confidence,
            limit=limit,
        )

    # Valid artifact kinds for global jump navigation
    VALID_KINDS = {"object", "face", "transcript", "ocr", "scene", "place", "location"}

    def jump_next(
        self,
        kind: str,
        from_video_id: str,
        from_ms: int | None = None,
        label: str | None = None,
        query: str | None = None,
        face_cluster_id: str | None = None,
        min_confidence: float | None = None,
        limit: int = 1,
    ) -> list[GlobalJumpResult]:
        """Navigate forward in the global timeline to find matching artifacts.

        Routes to the appropriate search method based on the artifact kind.
        Results are ordered chronologically after the current position.

        Args:
            kind: Type of artifact to search for. Must be one of:
                  object, face, transcript, ocr, scene, place, location.
            from_video_id: Starting video ID for the search.
            from_ms: Starting timestamp in milliseconds (default: 0).
            label: Filter by label (for object and place kinds).
            query: Text search query (for transcript and ocr kinds).
            face_cluster_id: Filter by face cluster ID (for face kind).
            min_confidence: Minimum confidence threshold (0-1).
            limit: Maximum number of results to return (default 1).

        Returns:
            List of GlobalJumpResult objects ordered by global timeline.
            Empty list if no matching artifacts are found.

        Raises:
            InvalidParameterError: If kind is not a valid artifact type.
            VideoNotFoundError: If from_video_id does not exist.
        """
        if kind not in self.VALID_KINDS:
            valid_kinds = ", ".join(sorted(self.VALID_KINDS))
            raise InvalidParameterError(
                "kind",
                f"Invalid artifact kind. Must be one of: {valid_kinds}",
            )

        # Default from_ms to 0 for "next" direction
        if from_ms is None:
            from_ms = 0

        if kind == "object":
            return self._search_objects_global(
                direction="next",
                from_video_id=from_video_id,
                from_ms=from_ms,
                label=label,
                min_confidence=min_confidence,
                limit=limit,
            )
        elif kind == "face":
            # Face cluster search not yet implemented
            # Will be implemented in task 6
            raise InvalidParameterError(
                "kind", "Face cluster search is not yet implemented"
            )
        elif kind == "transcript":
            if query is None:
                raise InvalidParameterError(
                    "query", "Query parameter is required for transcript search"
                )
            return self._search_transcript_global(
                direction="next",
                from_video_id=from_video_id,
                from_ms=from_ms,
                query=query,
                limit=limit,
            )
        elif kind == "ocr":
            if query is None:
                raise InvalidParameterError(
                    "query", "Query parameter is required for OCR search"
                )
            return self._search_ocr_global(
                direction="next",
                from_video_id=from_video_id,
                from_ms=from_ms,
                query=query,
                limit=limit,
            )
        elif kind == "scene":
            return self._search_scenes_global(
                direction="next",
                from_video_id=from_video_id,
                from_ms=from_ms,
                limit=limit,
            )
        elif kind == "place":
            return self._search_places_global(
                direction="next",
                from_video_id=from_video_id,
                from_ms=from_ms,
                label=label,
                min_confidence=min_confidence,
                limit=limit,
            )
        elif kind == "location":
            # Location search not yet implemented
            # Will be implemented in task 12
            raise InvalidParameterError(
                "kind", "Location search is not yet implemented"
            )

        # This should never be reached due to the validation above
        raise InvalidParameterError("kind", f"Unknown artifact kind: {kind}")

    def jump_prev(
        self,
        kind: str,
        from_video_id: str,
        from_ms: int | None = None,
        label: str | None = None,
        query: str | None = None,
        face_cluster_id: str | None = None,
        min_confidence: float | None = None,
        limit: int = 1,
    ) -> list[GlobalJumpResult]:
        """Navigate backward in the global timeline to find matching artifacts.

        Routes to the appropriate search method based on the artifact kind.
        Results are ordered chronologically before the current position.

        Args:
            kind: Type of artifact to search for. Must be one of:
                  object, face, transcript, ocr, scene, place, location.
            from_video_id: Starting video ID for the search.
            from_ms: Starting timestamp in milliseconds. If None, defaults to
                     a large value representing the end of the video.
            label: Filter by label (for object and place kinds).
            query: Text search query (for transcript and ocr kinds).
            face_cluster_id: Filter by face cluster ID (for face kind).
            min_confidence: Minimum confidence threshold (0-1).
            limit: Maximum number of results to return (default 1).

        Returns:
            List of GlobalJumpResult objects ordered by global timeline
            (descending - most recent first).
            Empty list if no matching artifacts are found.

        Raises:
            InvalidParameterError: If kind is not a valid artifact type.
            VideoNotFoundError: If from_video_id does not exist.
        """
        if kind not in self.VALID_KINDS:
            valid_kinds = ", ".join(sorted(self.VALID_KINDS))
            raise InvalidParameterError(
                "kind",
                f"Invalid artifact kind. Must be one of: {valid_kinds}",
            )

        # Default from_ms to a large value for "prev" direction
        # This represents "end of video" - searching backward from the end
        if from_ms is None:
            from_ms = 2**31 - 1  # Max 32-bit signed integer

        if kind == "object":
            return self._search_objects_global(
                direction="prev",
                from_video_id=from_video_id,
                from_ms=from_ms,
                label=label,
                min_confidence=min_confidence,
                limit=limit,
            )
        elif kind == "face":
            # Face cluster search not yet implemented
            # Will be implemented in task 6
            raise InvalidParameterError(
                "kind", "Face cluster search is not yet implemented"
            )
        elif kind == "transcript":
            if query is None:
                raise InvalidParameterError(
                    "query", "Query parameter is required for transcript search"
                )
            return self._search_transcript_global(
                direction="prev",
                from_video_id=from_video_id,
                from_ms=from_ms,
                query=query,
                limit=limit,
            )
        elif kind == "ocr":
            if query is None:
                raise InvalidParameterError(
                    "query", "Query parameter is required for OCR search"
                )
            return self._search_ocr_global(
                direction="prev",
                from_video_id=from_video_id,
                from_ms=from_ms,
                query=query,
                limit=limit,
            )
        elif kind == "scene":
            return self._search_scenes_global(
                direction="prev",
                from_video_id=from_video_id,
                from_ms=from_ms,
                limit=limit,
            )
        elif kind == "place":
            return self._search_places_global(
                direction="prev",
                from_video_id=from_video_id,
                from_ms=from_ms,
                label=label,
                min_confidence=min_confidence,
                limit=limit,
            )
        elif kind == "location":
            # Location search not yet implemented
            # Will be implemented in task 12
            raise InvalidParameterError(
                "kind", "Location search is not yet implemented"
            )

        # This should never be reached due to the validation above
        raise InvalidParameterError("kind", f"Unknown artifact kind: {kind}")

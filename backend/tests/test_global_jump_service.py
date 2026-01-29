"""Tests for GlobalJumpService."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, ObjectLabel
from src.database.models import Video as VideoEntity
from src.domain.exceptions import InvalidParameterError, VideoNotFoundError
from src.services.global_jump_service import GlobalJumpService


@pytest.fixture
def engine():
    """Create in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create database session for testing."""
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def global_jump_service(session):
    """Create GlobalJumpService instance."""
    # artifact_repo is not used by _search_objects_global, so we pass None
    return GlobalJumpService(session, artifact_repo=None)


def create_test_video(
    session,
    video_id: str,
    filename: str,
    file_created_at: datetime | None = None,
) -> VideoEntity:
    """Helper to create a test video."""
    video = VideoEntity(
        video_id=video_id,
        file_path=f"/test/{filename}",
        filename=filename,
        last_modified=datetime.now(),
        file_created_at=file_created_at,
        status="completed",
    )
    session.add(video)
    session.commit()
    return video


def create_object_label(
    session,
    artifact_id: str,
    asset_id: str,
    label: str,
    confidence: float,
    start_ms: int,
    end_ms: int,
) -> ObjectLabel:
    """Helper to create an object label in the projection table."""
    obj = ObjectLabel(
        artifact_id=artifact_id,
        asset_id=asset_id,
        label=label,
        confidence=confidence,
        start_ms=start_ms,
        end_ms=end_ms,
    )
    session.add(obj)
    session.commit()
    return obj


class TestSearchObjectsGlobalNext:
    """Tests for _search_objects_global with direction='next'."""

    def test_search_objects_next_single_video(self, session, global_jump_service):
        """Test searching for next object within the same video."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        create_object_label(session, "obj_1", video.video_id, "dog", 0.9, 0, 100)
        create_object_label(session, "obj_2", video.video_id, "dog", 0.85, 500, 600)
        create_object_label(session, "obj_3", video.video_id, "dog", 0.95, 1000, 1100)

        results = global_jump_service._search_objects_global(
            direction="next",
            from_video_id=video.video_id,
            from_ms=200,
            label="dog",
        )

        assert len(results) == 1
        assert results[0].artifact_id == "obj_2"
        assert results[0].jump_to.start_ms == 500
        assert results[0].preview["label"] == "dog"

    def test_search_objects_next_cross_video(self, session, global_jump_service):
        """Test searching for next object across multiple videos."""
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        create_object_label(session, "obj_1", video1.video_id, "cat", 0.9, 0, 100)
        create_object_label(session, "obj_2", video2.video_id, "cat", 0.85, 500, 600)

        # Search from end of video1
        results = global_jump_service._search_objects_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=5000,
            label="cat",
        )

        assert len(results) == 1
        assert results[0].video_id == "video_2"
        assert results[0].artifact_id == "obj_2"

    def test_search_objects_next_with_label_filter(self, session, global_jump_service):
        """Test that label filter correctly filters results."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        create_object_label(session, "obj_1", video.video_id, "dog", 0.9, 100, 200)
        create_object_label(session, "obj_2", video.video_id, "cat", 0.9, 200, 300)
        create_object_label(session, "obj_3", video.video_id, "dog", 0.9, 300, 400)

        results = global_jump_service._search_objects_global(
            direction="next",
            from_video_id=video.video_id,
            from_ms=150,
            label="dog",
        )

        assert len(results) == 1
        assert results[0].artifact_id == "obj_3"
        assert results[0].preview["label"] == "dog"

    def test_search_objects_next_with_confidence_filter(
        self, session, global_jump_service
    ):
        """Test that min_confidence filter correctly filters results."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        create_object_label(session, "obj_1", video.video_id, "dog", 0.5, 100, 200)
        create_object_label(session, "obj_2", video.video_id, "dog", 0.7, 200, 300)
        create_object_label(session, "obj_3", video.video_id, "dog", 0.9, 300, 400)

        results = global_jump_service._search_objects_global(
            direction="next",
            from_video_id=video.video_id,
            from_ms=0,
            label="dog",
            min_confidence=0.8,
        )

        assert len(results) == 1
        assert results[0].artifact_id == "obj_3"
        assert results[0].preview["confidence"] == 0.9

    def test_search_objects_next_ordering(self, session, global_jump_service):
        """Test that results are ordered by global timeline."""
        # Create videos with different file_created_at
        video1 = create_test_video(
            session, "video_a", "video_a.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_b", "video_b.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )
        video3 = create_test_video(
            session, "video_c", "video_c.mp4", datetime(2025, 1, 3, 12, 0, 0)
        )

        create_object_label(session, "obj_3", video3.video_id, "dog", 0.9, 0, 100)
        create_object_label(session, "obj_1", video1.video_id, "dog", 0.9, 0, 100)
        create_object_label(session, "obj_2", video2.video_id, "dog", 0.9, 0, 100)

        # Search from before all videos
        results = global_jump_service._search_objects_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=500,
            label="dog",
            limit=3,
        )

        assert len(results) == 2
        # Should be ordered by file_created_at
        assert results[0].video_id == "video_b"
        assert results[1].video_id == "video_c"

    def test_search_objects_next_limit(self, session, global_jump_service):
        """Test that limit parameter restricts results."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        for i in range(5):
            create_object_label(
                session, f"obj_{i}", video.video_id, "dog", 0.9, i * 100, i * 100 + 50
            )

        results = global_jump_service._search_objects_global(
            direction="next",
            from_video_id=video.video_id,
            from_ms=0,
            label="dog",
            limit=2,
        )

        assert len(results) == 2

    def test_search_objects_next_no_results(self, session, global_jump_service):
        """Test that empty list is returned when no matching objects found."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        create_object_label(session, "obj_1", video.video_id, "dog", 0.9, 0, 100)

        results = global_jump_service._search_objects_global(
            direction="next",
            from_video_id=video.video_id,
            from_ms=500,
            label="dog",
        )

        assert len(results) == 0

    def test_search_objects_next_video_not_found(self, session, global_jump_service):
        """Test that VideoNotFoundError is raised for non-existent video."""
        with pytest.raises(VideoNotFoundError) as exc_info:
            global_jump_service._search_objects_global(
                direction="next",
                from_video_id="non_existent_video",
                from_ms=0,
            )

        assert exc_info.value.video_id == "non_existent_video"

    def test_search_objects_next_null_file_created_at(
        self, session, global_jump_service
    ):
        """Test handling of videos with NULL file_created_at."""
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session,
            "video_2",
            "video2.mp4",
            None,  # NULL file_created_at
        )

        create_object_label(session, "obj_1", video1.video_id, "dog", 0.9, 0, 100)
        create_object_label(session, "obj_2", video2.video_id, "dog", 0.9, 0, 100)

        # Search from video1 - should find video2 (NULL sorted after)
        results = global_jump_service._search_objects_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=500,
            label="dog",
        )

        assert len(results) == 1
        assert results[0].video_id == "video_2"

    def test_search_objects_next_same_file_created_at_different_video_id(
        self, session, global_jump_service
    ):
        """Test ordering when videos have same file_created_at."""
        same_time = datetime(2025, 1, 1, 12, 0, 0)
        video1 = create_test_video(session, "video_a", "video_a.mp4", same_time)
        video2 = create_test_video(session, "video_b", "video_b.mp4", same_time)

        create_object_label(session, "obj_1", video1.video_id, "dog", 0.9, 0, 100)
        create_object_label(session, "obj_2", video2.video_id, "dog", 0.9, 0, 100)

        # Search from video_a - should find video_b (alphabetically later)
        results = global_jump_service._search_objects_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=500,
            label="dog",
        )

        assert len(results) == 1
        assert results[0].video_id == "video_b"

    def test_search_objects_next_result_contains_all_fields(
        self, session, global_jump_service
    ):
        """Test that results contain all required fields."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        create_object_label(session, "obj_1", video.video_id, "dog", 0.95, 100, 200)

        results = global_jump_service._search_objects_global(
            direction="next",
            from_video_id=video.video_id,
            from_ms=0,
            label="dog",
        )

        assert len(results) == 1
        result = results[0]
        assert result.video_id == "video_1"
        assert result.video_filename == "video1.mp4"
        assert result.file_created_at == datetime(2025, 1, 1, 12, 0, 0)
        assert result.jump_to.start_ms == 100
        assert result.jump_to.end_ms == 200
        assert result.artifact_id == "obj_1"
        assert result.preview == {"label": "dog", "confidence": 0.95}


class TestSearchObjectsGlobalPrev:
    """Tests for _search_objects_global with direction='prev'."""

    def test_search_objects_prev_single_video(self, session, global_jump_service):
        """Test searching for previous object within the same video."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        create_object_label(session, "obj_1", video.video_id, "dog", 0.9, 0, 100)
        create_object_label(session, "obj_2", video.video_id, "dog", 0.85, 500, 600)
        create_object_label(session, "obj_3", video.video_id, "dog", 0.95, 1000, 1100)

        results = global_jump_service._search_objects_global(
            direction="prev",
            from_video_id=video.video_id,
            from_ms=800,
            label="dog",
        )

        assert len(results) == 1
        assert results[0].artifact_id == "obj_2"
        assert results[0].jump_to.start_ms == 500
        assert results[0].preview["label"] == "dog"

    def test_search_objects_prev_cross_video(self, session, global_jump_service):
        """Test searching for previous object across multiple videos."""
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        create_object_label(session, "obj_1", video1.video_id, "cat", 0.9, 500, 600)
        create_object_label(session, "obj_2", video2.video_id, "cat", 0.85, 500, 600)

        # Search from beginning of video2
        results = global_jump_service._search_objects_global(
            direction="prev",
            from_video_id=video2.video_id,
            from_ms=0,
            label="cat",
        )

        assert len(results) == 1
        assert results[0].video_id == "video_1"
        assert results[0].artifact_id == "obj_1"

    def test_search_objects_prev_with_label_filter(self, session, global_jump_service):
        """Test that label filter correctly filters results for prev direction."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        create_object_label(session, "obj_1", video.video_id, "dog", 0.9, 100, 200)
        create_object_label(session, "obj_2", video.video_id, "cat", 0.9, 200, 300)
        create_object_label(session, "obj_3", video.video_id, "dog", 0.9, 300, 400)

        results = global_jump_service._search_objects_global(
            direction="prev",
            from_video_id=video.video_id,
            from_ms=250,
            label="dog",
        )

        assert len(results) == 1
        assert results[0].artifact_id == "obj_1"
        assert results[0].preview["label"] == "dog"

    def test_search_objects_prev_with_confidence_filter(
        self, session, global_jump_service
    ):
        """Test that min_confidence filter correctly filters results for prev."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        create_object_label(session, "obj_1", video.video_id, "dog", 0.9, 100, 200)
        create_object_label(session, "obj_2", video.video_id, "dog", 0.7, 200, 300)
        create_object_label(session, "obj_3", video.video_id, "dog", 0.5, 300, 400)

        results = global_jump_service._search_objects_global(
            direction="prev",
            from_video_id=video.video_id,
            from_ms=500,
            label="dog",
            min_confidence=0.8,
        )

        assert len(results) == 1
        assert results[0].artifact_id == "obj_1"
        assert results[0].preview["confidence"] == 0.9

    def test_search_objects_prev_ordering(self, session, global_jump_service):
        """Test that results are ordered by global timeline (descending for prev)."""
        # Create videos with different file_created_at
        video1 = create_test_video(
            session, "video_a", "video_a.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_b", "video_b.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )
        video3 = create_test_video(
            session, "video_c", "video_c.mp4", datetime(2025, 1, 3, 12, 0, 0)
        )

        create_object_label(session, "obj_1", video1.video_id, "dog", 0.9, 0, 100)
        create_object_label(session, "obj_2", video2.video_id, "dog", 0.9, 0, 100)
        create_object_label(session, "obj_3", video3.video_id, "dog", 0.9, 0, 100)

        # Search from video3 - should find video2 first (descending order)
        results = global_jump_service._search_objects_global(
            direction="prev",
            from_video_id=video3.video_id,
            from_ms=0,
            label="dog",
            limit=3,
        )

        assert len(results) == 2
        # Should be ordered by file_created_at descending
        assert results[0].video_id == "video_b"
        assert results[1].video_id == "video_a"

    def test_search_objects_prev_limit(self, session, global_jump_service):
        """Test that limit parameter restricts results for prev direction."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        for i in range(5):
            create_object_label(
                session, f"obj_{i}", video.video_id, "dog", 0.9, i * 100, i * 100 + 50
            )

        results = global_jump_service._search_objects_global(
            direction="prev",
            from_video_id=video.video_id,
            from_ms=500,
            label="dog",
            limit=2,
        )

        assert len(results) == 2

    def test_search_objects_prev_no_results(self, session, global_jump_service):
        """Test that empty list is returned when no matching objects found."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        create_object_label(session, "obj_1", video.video_id, "dog", 0.9, 500, 600)

        results = global_jump_service._search_objects_global(
            direction="prev",
            from_video_id=video.video_id,
            from_ms=100,
            label="dog",
        )

        assert len(results) == 0

    def test_search_objects_prev_null_file_created_at(
        self, session, global_jump_service
    ):
        """Test handling of videos with NULL file_created_at for prev direction."""
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session,
            "video_2",
            "video2.mp4",
            None,  # NULL file_created_at
        )

        create_object_label(session, "obj_1", video1.video_id, "dog", 0.9, 0, 100)
        create_object_label(session, "obj_2", video2.video_id, "dog", 0.9, 0, 100)

        # Search from video2 (NULL) - should find video1 (non-NULL comes before)
        results = global_jump_service._search_objects_global(
            direction="prev",
            from_video_id=video2.video_id,
            from_ms=0,
            label="dog",
        )

        assert len(results) == 1
        assert results[0].video_id == "video_1"

    def test_search_objects_prev_same_file_created_at_different_video_id(
        self, session, global_jump_service
    ):
        """Test ordering when videos have same file_created_at for prev direction."""
        same_time = datetime(2025, 1, 1, 12, 0, 0)
        video1 = create_test_video(session, "video_a", "video_a.mp4", same_time)
        video2 = create_test_video(session, "video_b", "video_b.mp4", same_time)

        create_object_label(session, "obj_1", video1.video_id, "dog", 0.9, 0, 100)
        create_object_label(session, "obj_2", video2.video_id, "dog", 0.9, 0, 100)

        # Search from video_b - should find video_a (alphabetically earlier)
        results = global_jump_service._search_objects_global(
            direction="prev",
            from_video_id=video2.video_id,
            from_ms=0,
            label="dog",
        )

        assert len(results) == 1
        assert results[0].video_id == "video_a"

    def test_search_objects_prev_result_contains_all_fields(
        self, session, global_jump_service
    ):
        """Test that results contain all required fields for prev direction."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        create_object_label(session, "obj_1", video.video_id, "dog", 0.95, 100, 200)

        results = global_jump_service._search_objects_global(
            direction="prev",
            from_video_id=video.video_id,
            from_ms=500,
            label="dog",
        )

        assert len(results) == 1
        result = results[0]
        assert result.video_id == "video_1"
        assert result.video_filename == "video1.mp4"
        assert result.file_created_at == datetime(2025, 1, 1, 12, 0, 0)
        assert result.jump_to.start_ms == 100
        assert result.jump_to.end_ms == 200
        assert result.artifact_id == "obj_1"
        assert result.preview == {"label": "dog", "confidence": 0.95}


class TestSearchTranscriptGlobalNext:
    """Tests for _search_transcript_global with direction='next'."""

    @pytest.fixture
    def setup_transcript_fts(self, session):
        """Set up transcript_fts table for SQLite testing."""
        # Create FTS5 virtual table for SQLite
        session.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS transcript_fts USING fts5(
                    artifact_id UNINDEXED,
                    asset_id UNINDEXED,
                    start_ms UNINDEXED,
                    end_ms UNINDEXED,
                    text
                )
                """
            )
        )
        # Create metadata table for SQLite
        session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS transcript_fts_metadata (
                    artifact_id TEXT PRIMARY KEY,
                    asset_id TEXT NOT NULL,
                    start_ms INTEGER NOT NULL,
                    end_ms INTEGER NOT NULL
                )
                """
            )
        )
        session.commit()
        yield
        # Cleanup
        session.execute(text("DROP TABLE IF EXISTS transcript_fts_metadata"))
        session.execute(text("DROP TABLE IF EXISTS transcript_fts"))
        session.commit()

    def _insert_transcript(
        self,
        session,
        artifact_id: str,
        asset_id: str,
        start_ms: int,
        end_ms: int,
        text_content: str,
    ):
        """Helper to insert transcript into FTS tables."""
        session.execute(
            text(
                """
                INSERT INTO transcript_fts
                    (artifact_id, asset_id, start_ms, end_ms, text)
                VALUES (:artifact_id, :asset_id, :start_ms, :end_ms, :text)
                """
            ),
            {
                "artifact_id": artifact_id,
                "asset_id": asset_id,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "text": text_content,
            },
        )
        session.execute(
            text(
                """
                INSERT INTO transcript_fts_metadata
                    (artifact_id, asset_id, start_ms, end_ms)
                VALUES (:artifact_id, :asset_id, :start_ms, :end_ms)
                """
            ),
            {
                "artifact_id": artifact_id,
                "asset_id": asset_id,
                "start_ms": start_ms,
                "end_ms": end_ms,
            },
        )
        session.commit()

    def test_search_transcript_next_single_video(
        self, session, global_jump_service, setup_transcript_fts
    ):
        """Test searching for next transcript within the same video."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        self._insert_transcript(
            session, "trans_1", video.video_id, 0, 100, "hello world"
        )
        self._insert_transcript(
            session, "trans_2", video.video_id, 500, 600, "hello again"
        )
        self._insert_transcript(
            session, "trans_3", video.video_id, 1000, 1100, "goodbye world"
        )

        results = global_jump_service._search_transcript_global(
            direction="next",
            from_video_id=video.video_id,
            from_ms=200,
            query="hello",
        )

        assert len(results) == 1
        assert results[0].artifact_id == "trans_2"
        assert results[0].jump_to.start_ms == 500
        assert "hello" in results[0].preview["text"].lower()

    def test_search_transcript_next_cross_video(
        self, session, global_jump_service, setup_transcript_fts
    ):
        """Test searching for next transcript across multiple videos."""
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        self._insert_transcript(
            session, "trans_1", video1.video_id, 0, 100, "kubernetes tutorial"
        )
        self._insert_transcript(
            session, "trans_2", video2.video_id, 500, 600, "kubernetes explained"
        )

        # Search from end of video1
        results = global_jump_service._search_transcript_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=5000,
            query="kubernetes",
        )

        assert len(results) == 1
        assert results[0].video_id == "video_2"
        assert results[0].artifact_id == "trans_2"

    def test_search_transcript_next_ordering(
        self, session, global_jump_service, setup_transcript_fts
    ):
        """Test that results are ordered by global timeline."""
        video1 = create_test_video(
            session, "video_a", "video_a.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_b", "video_b.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )
        video3 = create_test_video(
            session, "video_c", "video_c.mp4", datetime(2025, 1, 3, 12, 0, 0)
        )

        self._insert_transcript(
            session, "trans_3", video3.video_id, 0, 100, "python programming"
        )
        self._insert_transcript(
            session, "trans_1", video1.video_id, 0, 100, "python basics"
        )
        self._insert_transcript(
            session, "trans_2", video2.video_id, 0, 100, "python advanced"
        )

        results = global_jump_service._search_transcript_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=500,
            query="python",
            limit=3,
        )

        assert len(results) == 2
        assert results[0].video_id == "video_b"
        assert results[1].video_id == "video_c"

    def test_search_transcript_next_no_results(
        self, session, global_jump_service, setup_transcript_fts
    ):
        """Test that empty list is returned when no matching transcripts found."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        self._insert_transcript(
            session, "trans_1", video.video_id, 0, 100, "hello world"
        )

        results = global_jump_service._search_transcript_global(
            direction="next",
            from_video_id=video.video_id,
            from_ms=0,
            query="nonexistent",
        )

        assert len(results) == 0

    def test_search_transcript_next_video_not_found(
        self, session, global_jump_service, setup_transcript_fts
    ):
        """Test that VideoNotFoundError is raised for non-existent video."""
        with pytest.raises(VideoNotFoundError) as exc_info:
            global_jump_service._search_transcript_global(
                direction="next",
                from_video_id="non_existent_video",
                from_ms=0,
                query="test",
            )

        assert exc_info.value.video_id == "non_existent_video"

    def test_search_transcript_next_result_contains_all_fields(
        self, session, global_jump_service, setup_transcript_fts
    ):
        """Test that results contain all required fields."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        self._insert_transcript(
            session, "trans_1", video.video_id, 100, 200, "test content here"
        )

        results = global_jump_service._search_transcript_global(
            direction="next",
            from_video_id=video.video_id,
            from_ms=0,
            query="test",
        )

        assert len(results) == 1
        result = results[0]
        assert result.video_id == "video_1"
        assert result.video_filename == "video1.mp4"
        # SQLite returns datetime as string, PostgreSQL returns datetime object
        # Check that file_created_at is present and contains expected date
        assert result.file_created_at is not None
        if isinstance(result.file_created_at, str):
            assert "2025-01-01" in result.file_created_at
        else:
            assert result.file_created_at == datetime(2025, 1, 1, 12, 0, 0)
        assert result.jump_to.start_ms == 100
        assert result.jump_to.end_ms == 200
        assert result.artifact_id == "trans_1"
        assert "text" in result.preview


class TestSearchTranscriptGlobalPrev:
    """Tests for _search_transcript_global with direction='prev'."""

    @pytest.fixture
    def setup_transcript_fts(self, session):
        """Set up transcript_fts table for SQLite testing."""
        session.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS transcript_fts USING fts5(
                    artifact_id UNINDEXED,
                    asset_id UNINDEXED,
                    start_ms UNINDEXED,
                    end_ms UNINDEXED,
                    text
                )
                """
            )
        )
        session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS transcript_fts_metadata (
                    artifact_id TEXT PRIMARY KEY,
                    asset_id TEXT NOT NULL,
                    start_ms INTEGER NOT NULL,
                    end_ms INTEGER NOT NULL
                )
                """
            )
        )
        session.commit()
        yield
        session.execute(text("DROP TABLE IF EXISTS transcript_fts_metadata"))
        session.execute(text("DROP TABLE IF EXISTS transcript_fts"))
        session.commit()

    def _insert_transcript(
        self,
        session,
        artifact_id: str,
        asset_id: str,
        start_ms: int,
        end_ms: int,
        text_content: str,
    ):
        """Helper to insert transcript into FTS tables."""
        session.execute(
            text(
                """
                INSERT INTO transcript_fts
                    (artifact_id, asset_id, start_ms, end_ms, text)
                VALUES (:artifact_id, :asset_id, :start_ms, :end_ms, :text)
                """
            ),
            {
                "artifact_id": artifact_id,
                "asset_id": asset_id,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "text": text_content,
            },
        )
        session.execute(
            text(
                """
                INSERT INTO transcript_fts_metadata
                    (artifact_id, asset_id, start_ms, end_ms)
                VALUES (:artifact_id, :asset_id, :start_ms, :end_ms)
                """
            ),
            {
                "artifact_id": artifact_id,
                "asset_id": asset_id,
                "start_ms": start_ms,
                "end_ms": end_ms,
            },
        )
        session.commit()

    def test_search_transcript_prev_single_video(
        self, session, global_jump_service, setup_transcript_fts
    ):
        """Test searching for previous transcript within the same video."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        self._insert_transcript(
            session, "trans_1", video.video_id, 0, 100, "hello world"
        )
        self._insert_transcript(
            session, "trans_2", video.video_id, 500, 600, "hello again"
        )
        self._insert_transcript(
            session, "trans_3", video.video_id, 1000, 1100, "goodbye world"
        )

        results = global_jump_service._search_transcript_global(
            direction="prev",
            from_video_id=video.video_id,
            from_ms=800,
            query="hello",
        )

        assert len(results) == 1
        assert results[0].artifact_id == "trans_2"
        assert results[0].jump_to.start_ms == 500

    def test_search_transcript_prev_cross_video(
        self, session, global_jump_service, setup_transcript_fts
    ):
        """Test searching for previous transcript across multiple videos."""
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        self._insert_transcript(
            session, "trans_1", video1.video_id, 500, 600, "docker container"
        )
        self._insert_transcript(
            session, "trans_2", video2.video_id, 500, 600, "docker image"
        )

        # Search from beginning of video2
        results = global_jump_service._search_transcript_global(
            direction="prev",
            from_video_id=video2.video_id,
            from_ms=0,
            query="docker",
        )

        assert len(results) == 1
        assert results[0].video_id == "video_1"
        assert results[0].artifact_id == "trans_1"

    def test_search_transcript_prev_ordering(
        self, session, global_jump_service, setup_transcript_fts
    ):
        """Test that results are ordered by global timeline (descending)."""
        video1 = create_test_video(
            session, "video_a", "video_a.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_b", "video_b.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )
        video3 = create_test_video(
            session, "video_c", "video_c.mp4", datetime(2025, 1, 3, 12, 0, 0)
        )

        self._insert_transcript(
            session, "trans_1", video1.video_id, 0, 100, "react tutorial"
        )
        self._insert_transcript(
            session, "trans_2", video2.video_id, 0, 100, "react hooks"
        )
        self._insert_transcript(
            session, "trans_3", video3.video_id, 0, 100, "react components"
        )

        results = global_jump_service._search_transcript_global(
            direction="prev",
            from_video_id=video3.video_id,
            from_ms=0,
            query="react",
            limit=3,
        )

        assert len(results) == 2
        # Should be ordered by file_created_at descending
        assert results[0].video_id == "video_b"
        assert results[1].video_id == "video_a"

    def test_search_transcript_prev_no_results(
        self, session, global_jump_service, setup_transcript_fts
    ):
        """Test that empty list is returned when no matching transcripts found."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        self._insert_transcript(
            session, "trans_1", video.video_id, 500, 600, "hello world"
        )

        results = global_jump_service._search_transcript_global(
            direction="prev",
            from_video_id=video.video_id,
            from_ms=100,
            query="hello",
        )

        assert len(results) == 0


class TestSearchOcrGlobalNext:
    """Tests for _search_ocr_global with direction='next'."""

    @pytest.fixture
    def setup_ocr_fts(self, session):
        """Set up ocr_fts table for SQLite testing."""
        # Create FTS5 virtual table for SQLite
        session.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS ocr_fts USING fts5(
                    artifact_id UNINDEXED,
                    asset_id UNINDEXED,
                    start_ms UNINDEXED,
                    end_ms UNINDEXED,
                    text
                )
                """
            )
        )
        # Create metadata table for SQLite
        session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS ocr_fts_metadata (
                    artifact_id TEXT PRIMARY KEY,
                    asset_id TEXT NOT NULL,
                    start_ms INTEGER NOT NULL,
                    end_ms INTEGER NOT NULL
                )
                """
            )
        )
        session.commit()
        yield
        # Cleanup
        session.execute(text("DROP TABLE IF EXISTS ocr_fts_metadata"))
        session.execute(text("DROP TABLE IF EXISTS ocr_fts"))
        session.commit()

    def _insert_ocr(
        self,
        session,
        artifact_id: str,
        asset_id: str,
        start_ms: int,
        end_ms: int,
        text_content: str,
    ):
        """Helper to insert OCR text into FTS tables."""
        session.execute(
            text(
                """
                INSERT INTO ocr_fts
                    (artifact_id, asset_id, start_ms, end_ms, text)
                VALUES (:artifact_id, :asset_id, :start_ms, :end_ms, :text)
                """
            ),
            {
                "artifact_id": artifact_id,
                "asset_id": asset_id,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "text": text_content,
            },
        )
        session.execute(
            text(
                """
                INSERT INTO ocr_fts_metadata
                    (artifact_id, asset_id, start_ms, end_ms)
                VALUES (:artifact_id, :asset_id, :start_ms, :end_ms)
                """
            ),
            {
                "artifact_id": artifact_id,
                "asset_id": asset_id,
                "start_ms": start_ms,
                "end_ms": end_ms,
            },
        )
        session.commit()

    def test_search_ocr_next_single_video(
        self, session, global_jump_service, setup_ocr_fts
    ):
        """Test searching for next OCR text within the same video."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        self._insert_ocr(session, "ocr_1", video.video_id, 0, 100, "Welcome Screen")
        self._insert_ocr(session, "ocr_2", video.video_id, 500, 600, "Welcome Back")
        self._insert_ocr(session, "ocr_3", video.video_id, 1000, 1100, "Goodbye Screen")

        results = global_jump_service._search_ocr_global(
            direction="next",
            from_video_id=video.video_id,
            from_ms=200,
            query="Welcome",
        )

        assert len(results) == 1
        assert results[0].artifact_id == "ocr_2"
        assert results[0].jump_to.start_ms == 500
        assert "Welcome" in results[0].preview["text"]

    def test_search_ocr_next_cross_video(
        self, session, global_jump_service, setup_ocr_fts
    ):
        """Test searching for next OCR text across multiple videos."""
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        self._insert_ocr(session, "ocr_1", video1.video_id, 0, 100, "Error Message")
        self._insert_ocr(session, "ocr_2", video2.video_id, 500, 600, "Error Code 404")

        # Search from end of video1
        results = global_jump_service._search_ocr_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=5000,
            query="Error",
        )

        assert len(results) == 1
        assert results[0].video_id == "video_2"
        assert results[0].artifact_id == "ocr_2"

    def test_search_ocr_next_ordering(
        self, session, global_jump_service, setup_ocr_fts
    ):
        """Test that results are ordered by global timeline."""
        video1 = create_test_video(
            session, "video_a", "video_a.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_b", "video_b.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )
        video3 = create_test_video(
            session, "video_c", "video_c.mp4", datetime(2025, 1, 3, 12, 0, 0)
        )

        self._insert_ocr(session, "ocr_3", video3.video_id, 0, 100, "Login Button")
        self._insert_ocr(session, "ocr_1", video1.video_id, 0, 100, "Login Form")
        self._insert_ocr(session, "ocr_2", video2.video_id, 0, 100, "Login Page")

        results = global_jump_service._search_ocr_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=500,
            query="Login",
            limit=3,
        )

        assert len(results) == 2
        assert results[0].video_id == "video_b"
        assert results[1].video_id == "video_c"

    def test_search_ocr_next_no_results(
        self, session, global_jump_service, setup_ocr_fts
    ):
        """Test that empty list is returned when no matching OCR text found."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        self._insert_ocr(session, "ocr_1", video.video_id, 0, 100, "Hello World")

        results = global_jump_service._search_ocr_global(
            direction="next",
            from_video_id=video.video_id,
            from_ms=0,
            query="nonexistent",
        )

        assert len(results) == 0

    def test_search_ocr_next_video_not_found(
        self, session, global_jump_service, setup_ocr_fts
    ):
        """Test that VideoNotFoundError is raised for non-existent video."""
        with pytest.raises(VideoNotFoundError) as exc_info:
            global_jump_service._search_ocr_global(
                direction="next",
                from_video_id="non_existent_video",
                from_ms=0,
                query="test",
            )

        assert exc_info.value.video_id == "non_existent_video"

    def test_search_ocr_next_result_contains_all_fields(
        self, session, global_jump_service, setup_ocr_fts
    ):
        """Test that results contain all required fields."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        self._insert_ocr(session, "ocr_1", video.video_id, 100, 200, "Test Label")

        results = global_jump_service._search_ocr_global(
            direction="next",
            from_video_id=video.video_id,
            from_ms=0,
            query="Test",
        )

        assert len(results) == 1
        result = results[0]
        assert result.video_id == "video_1"
        assert result.video_filename == "video1.mp4"
        # SQLite returns datetime as string, PostgreSQL returns datetime object
        assert result.file_created_at is not None
        if isinstance(result.file_created_at, str):
            assert "2025-01-01" in result.file_created_at
        else:
            assert result.file_created_at == datetime(2025, 1, 1, 12, 0, 0)
        assert result.jump_to.start_ms == 100
        assert result.jump_to.end_ms == 200
        assert result.artifact_id == "ocr_1"
        assert "text" in result.preview


class TestSearchOcrGlobalPrev:
    """Tests for _search_ocr_global with direction='prev'."""

    @pytest.fixture
    def setup_ocr_fts(self, session):
        """Set up ocr_fts table for SQLite testing."""
        session.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS ocr_fts USING fts5(
                    artifact_id UNINDEXED,
                    asset_id UNINDEXED,
                    start_ms UNINDEXED,
                    end_ms UNINDEXED,
                    text
                )
                """
            )
        )
        session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS ocr_fts_metadata (
                    artifact_id TEXT PRIMARY KEY,
                    asset_id TEXT NOT NULL,
                    start_ms INTEGER NOT NULL,
                    end_ms INTEGER NOT NULL
                )
                """
            )
        )
        session.commit()
        yield
        session.execute(text("DROP TABLE IF EXISTS ocr_fts_metadata"))
        session.execute(text("DROP TABLE IF EXISTS ocr_fts"))
        session.commit()

    def _insert_ocr(
        self,
        session,
        artifact_id: str,
        asset_id: str,
        start_ms: int,
        end_ms: int,
        text_content: str,
    ):
        """Helper to insert OCR text into FTS tables."""
        session.execute(
            text(
                """
                INSERT INTO ocr_fts
                    (artifact_id, asset_id, start_ms, end_ms, text)
                VALUES (:artifact_id, :asset_id, :start_ms, :end_ms, :text)
                """
            ),
            {
                "artifact_id": artifact_id,
                "asset_id": asset_id,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "text": text_content,
            },
        )
        session.execute(
            text(
                """
                INSERT INTO ocr_fts_metadata
                    (artifact_id, asset_id, start_ms, end_ms)
                VALUES (:artifact_id, :asset_id, :start_ms, :end_ms)
                """
            ),
            {
                "artifact_id": artifact_id,
                "asset_id": asset_id,
                "start_ms": start_ms,
                "end_ms": end_ms,
            },
        )
        session.commit()

    def test_search_ocr_prev_single_video(
        self, session, global_jump_service, setup_ocr_fts
    ):
        """Test searching for previous OCR text within the same video."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        self._insert_ocr(session, "ocr_1", video.video_id, 0, 100, "Submit Button")
        self._insert_ocr(session, "ocr_2", video.video_id, 500, 600, "Submit Form")
        self._insert_ocr(session, "ocr_3", video.video_id, 1000, 1100, "Cancel Button")

        results = global_jump_service._search_ocr_global(
            direction="prev",
            from_video_id=video.video_id,
            from_ms=800,
            query="Submit",
        )

        assert len(results) == 1
        assert results[0].artifact_id == "ocr_2"
        assert results[0].jump_to.start_ms == 500

    def test_search_ocr_prev_cross_video(
        self, session, global_jump_service, setup_ocr_fts
    ):
        """Test searching for previous OCR text across multiple videos."""
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        self._insert_ocr(session, "ocr_1", video1.video_id, 500, 600, "Settings Menu")
        self._insert_ocr(session, "ocr_2", video2.video_id, 500, 600, "Settings Page")

        # Search from beginning of video2
        results = global_jump_service._search_ocr_global(
            direction="prev",
            from_video_id=video2.video_id,
            from_ms=0,
            query="Settings",
        )

        assert len(results) == 1
        assert results[0].video_id == "video_1"
        assert results[0].artifact_id == "ocr_1"

    def test_search_ocr_prev_ordering(
        self, session, global_jump_service, setup_ocr_fts
    ):
        """Test that results are ordered by global timeline (descending)."""
        video1 = create_test_video(
            session, "video_a", "video_a.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_b", "video_b.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )
        video3 = create_test_video(
            session, "video_c", "video_c.mp4", datetime(2025, 1, 3, 12, 0, 0)
        )

        self._insert_ocr(session, "ocr_1", video1.video_id, 0, 100, "Dashboard View")
        self._insert_ocr(session, "ocr_2", video2.video_id, 0, 100, "Dashboard Stats")
        self._insert_ocr(session, "ocr_3", video3.video_id, 0, 100, "Dashboard Home")

        results = global_jump_service._search_ocr_global(
            direction="prev",
            from_video_id=video3.video_id,
            from_ms=0,
            query="Dashboard",
            limit=3,
        )

        assert len(results) == 2
        # Should be ordered by file_created_at descending
        assert results[0].video_id == "video_b"
        assert results[1].video_id == "video_a"

    def test_search_ocr_prev_no_results(
        self, session, global_jump_service, setup_ocr_fts
    ):
        """Test that empty list is returned when no matching OCR text found."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        self._insert_ocr(session, "ocr_1", video.video_id, 500, 600, "Hello World")

        results = global_jump_service._search_ocr_global(
            direction="prev",
            from_video_id=video.video_id,
            from_ms=100,
            query="Hello",
        )

        assert len(results) == 0


class TestJumpNext:
    """Tests for jump_next() public method."""

    def test_jump_next_object_routes_correctly(self, session, global_jump_service):
        """Test that kind='object' routes to object search."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        create_object_label(session, "obj_1", video.video_id, "dog", 0.9, 100, 200)

        results = global_jump_service.jump_next(
            kind="object",
            from_video_id=video.video_id,
            from_ms=0,
            label="dog",
        )

        assert len(results) == 1
        assert results[0].artifact_id == "obj_1"
        assert results[0].preview["label"] == "dog"

    def test_jump_next_invalid_kind_raises_error(self, session, global_jump_service):
        """Test that invalid kind raises InvalidParameterError."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        with pytest.raises(InvalidParameterError) as exc_info:
            global_jump_service.jump_next(
                kind="invalid_kind",
                from_video_id=video.video_id,
                from_ms=0,
            )

        assert exc_info.value.parameter == "kind"
        assert "Invalid artifact kind" in exc_info.value.message

    def test_jump_next_transcript_requires_query(self, session, global_jump_service):
        """Test that transcript search requires query parameter."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        with pytest.raises(InvalidParameterError) as exc_info:
            global_jump_service.jump_next(
                kind="transcript",
                from_video_id=video.video_id,
                from_ms=0,
            )

        assert exc_info.value.parameter == "query"

    def test_jump_next_ocr_requires_query(self, session, global_jump_service):
        """Test that OCR search requires query parameter."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        with pytest.raises(InvalidParameterError) as exc_info:
            global_jump_service.jump_next(
                kind="ocr",
                from_video_id=video.video_id,
                from_ms=0,
            )

        assert exc_info.value.parameter == "query"

    def test_jump_next_default_from_ms(self, session, global_jump_service):
        """Test that from_ms defaults to 0 when not provided."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        create_object_label(session, "obj_1", video.video_id, "cat", 0.9, 100, 200)

        # Call without from_ms - should default to 0 and find the object
        results = global_jump_service.jump_next(
            kind="object",
            from_video_id=video.video_id,
            label="cat",
        )

        assert len(results) == 1
        assert results[0].artifact_id == "obj_1"

    def test_jump_next_video_not_found(self, session, global_jump_service):
        """Test that VideoNotFoundError is raised for non-existent video."""
        with pytest.raises(VideoNotFoundError) as exc_info:
            global_jump_service.jump_next(
                kind="object",
                from_video_id="non_existent_video",
                from_ms=0,
            )

        assert exc_info.value.video_id == "non_existent_video"

    def test_jump_next_with_limit(self, session, global_jump_service):
        """Test that limit parameter is respected."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        for i in range(5):
            create_object_label(
                session, f"obj_{i}", video.video_id, "bird", 0.9, i * 100, i * 100 + 50
            )

        results = global_jump_service.jump_next(
            kind="object",
            from_video_id=video.video_id,
            from_ms=0,
            label="bird",
            limit=3,
        )

        assert len(results) == 3

    def test_jump_next_with_min_confidence(self, session, global_jump_service):
        """Test that min_confidence filter is applied."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        create_object_label(session, "obj_1", video.video_id, "car", 0.5, 100, 200)
        create_object_label(session, "obj_2", video.video_id, "car", 0.9, 200, 300)

        results = global_jump_service.jump_next(
            kind="object",
            from_video_id=video.video_id,
            from_ms=0,
            label="car",
            min_confidence=0.8,
        )

        assert len(results) == 1
        assert results[0].artifact_id == "obj_2"

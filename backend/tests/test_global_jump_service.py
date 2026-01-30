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


class TestJumpPrev:
    """Tests for jump_prev() public method."""

    def test_jump_prev_object_routes_correctly(self, session, global_jump_service):
        """Test that kind='object' routes to object search with prev direction."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        create_object_label(session, "obj_1", video.video_id, "dog", 0.9, 100, 200)
        create_object_label(session, "obj_2", video.video_id, "dog", 0.9, 500, 600)

        results = global_jump_service.jump_prev(
            kind="object",
            from_video_id=video.video_id,
            from_ms=400,
            label="dog",
        )

        assert len(results) == 1
        assert results[0].artifact_id == "obj_1"
        assert results[0].preview["label"] == "dog"

    def test_jump_prev_invalid_kind_raises_error(self, session, global_jump_service):
        """Test that invalid kind raises InvalidParameterError."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        with pytest.raises(InvalidParameterError) as exc_info:
            global_jump_service.jump_prev(
                kind="invalid_kind",
                from_video_id=video.video_id,
                from_ms=0,
            )

        assert exc_info.value.parameter == "kind"
        assert "Invalid artifact kind" in exc_info.value.message

    def test_jump_prev_transcript_requires_query(self, session, global_jump_service):
        """Test that transcript search requires query parameter."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        with pytest.raises(InvalidParameterError) as exc_info:
            global_jump_service.jump_prev(
                kind="transcript",
                from_video_id=video.video_id,
                from_ms=0,
            )

        assert exc_info.value.parameter == "query"

    def test_jump_prev_ocr_requires_query(self, session, global_jump_service):
        """Test that OCR search requires query parameter."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        with pytest.raises(InvalidParameterError) as exc_info:
            global_jump_service.jump_prev(
                kind="ocr",
                from_video_id=video.video_id,
                from_ms=0,
            )

        assert exc_info.value.parameter == "query"

    def test_jump_prev_default_from_ms(self, session, global_jump_service):
        """Test that from_ms defaults to max value when not provided."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        create_object_label(session, "obj_1", video.video_id, "cat", 0.9, 100, 200)
        create_object_label(session, "obj_2", video.video_id, "cat", 0.9, 500, 600)

        # Call without from_ms - should default to max and find the last object
        results = global_jump_service.jump_prev(
            kind="object",
            from_video_id=video.video_id,
            label="cat",
        )

        assert len(results) == 1
        # Should find the last object (obj_2) since we're searching from the end
        assert results[0].artifact_id == "obj_2"

    def test_jump_prev_video_not_found(self, session, global_jump_service):
        """Test that VideoNotFoundError is raised for non-existent video."""
        with pytest.raises(VideoNotFoundError) as exc_info:
            global_jump_service.jump_prev(
                kind="object",
                from_video_id="non_existent_video",
                from_ms=0,
            )

        assert exc_info.value.video_id == "non_existent_video"

    def test_jump_prev_with_limit(self, session, global_jump_service):
        """Test that limit parameter is respected."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        for i in range(5):
            create_object_label(
                session, f"obj_{i}", video.video_id, "bird", 0.9, i * 100, i * 100 + 50
            )

        results = global_jump_service.jump_prev(
            kind="object",
            from_video_id=video.video_id,
            from_ms=1000,
            label="bird",
            limit=3,
        )

        assert len(results) == 3

    def test_jump_prev_with_min_confidence(self, session, global_jump_service):
        """Test that min_confidence filter is applied."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        create_object_label(session, "obj_1", video.video_id, "car", 0.9, 100, 200)
        create_object_label(session, "obj_2", video.video_id, "car", 0.5, 200, 300)

        results = global_jump_service.jump_prev(
            kind="object",
            from_video_id=video.video_id,
            from_ms=500,
            label="car",
            min_confidence=0.8,
        )

        assert len(results) == 1
        assert results[0].artifact_id == "obj_1"


class TestSearchScenesGlobalNext:
    """Tests for _search_scenes_global with direction='next'."""

    @pytest.fixture
    def setup_scene_ranges(self, session):
        """Set up scene_ranges table for testing."""
        session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS scene_ranges (
                    artifact_id TEXT PRIMARY KEY,
                    asset_id TEXT NOT NULL,
                    scene_index INTEGER NOT NULL,
                    start_ms INTEGER NOT NULL,
                    end_ms INTEGER NOT NULL
                )
                """
            )
        )
        session.commit()
        yield
        session.execute(text("DROP TABLE IF EXISTS scene_ranges"))
        session.commit()

    def _insert_scene(
        self,
        session,
        artifact_id: str,
        asset_id: str,
        scene_index: int,
        start_ms: int,
        end_ms: int,
    ):
        """Helper to insert scene into scene_ranges table."""
        session.execute(
            text(
                """
                INSERT INTO scene_ranges
                    (artifact_id, asset_id, scene_index, start_ms, end_ms)
                VALUES (:artifact_id, :asset_id, :scene_index, :start_ms, :end_ms)
                """
            ),
            {
                "artifact_id": artifact_id,
                "asset_id": asset_id,
                "scene_index": scene_index,
                "start_ms": start_ms,
                "end_ms": end_ms,
            },
        )
        session.commit()

    def test_search_scenes_next_single_video(
        self, session, global_jump_service, setup_scene_ranges
    ):
        """Test searching for next scene within the same video."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        self._insert_scene(session, "scene_1", video.video_id, 0, 0, 5000)
        self._insert_scene(session, "scene_2", video.video_id, 1, 5000, 10000)
        self._insert_scene(session, "scene_3", video.video_id, 2, 10000, 15000)

        results = global_jump_service._search_scenes_global(
            direction="next",
            from_video_id=video.video_id,
            from_ms=3000,
        )

        assert len(results) == 1
        assert results[0].artifact_id == "scene_2"
        assert results[0].jump_to.start_ms == 5000
        assert results[0].preview["scene_index"] == 1

    def test_search_scenes_next_cross_video(
        self, session, global_jump_service, setup_scene_ranges
    ):
        """Test searching for next scene across multiple videos."""
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        self._insert_scene(session, "scene_1", video1.video_id, 0, 0, 5000)
        self._insert_scene(session, "scene_2", video2.video_id, 0, 0, 5000)

        # Search from end of video1
        results = global_jump_service._search_scenes_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=10000,
        )

        assert len(results) == 1
        assert results[0].video_id == "video_2"
        assert results[0].artifact_id == "scene_2"

    def test_search_scenes_next_ordering(
        self, session, global_jump_service, setup_scene_ranges
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

        self._insert_scene(session, "scene_3", video3.video_id, 0, 0, 5000)
        self._insert_scene(session, "scene_1", video1.video_id, 0, 0, 5000)
        self._insert_scene(session, "scene_2", video2.video_id, 0, 0, 5000)

        results = global_jump_service._search_scenes_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=10000,
            limit=3,
        )

        assert len(results) == 2
        assert results[0].video_id == "video_b"
        assert results[1].video_id == "video_c"

    def test_search_scenes_next_no_results(
        self, session, global_jump_service, setup_scene_ranges
    ):
        """Test that empty list is returned when no scenes found."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        self._insert_scene(session, "scene_1", video.video_id, 0, 0, 5000)

        results = global_jump_service._search_scenes_global(
            direction="next",
            from_video_id=video.video_id,
            from_ms=10000,
        )

        assert len(results) == 0

    def test_search_scenes_next_video_not_found(
        self, session, global_jump_service, setup_scene_ranges
    ):
        """Test that VideoNotFoundError is raised for non-existent video."""
        with pytest.raises(VideoNotFoundError) as exc_info:
            global_jump_service._search_scenes_global(
                direction="next",
                from_video_id="non_existent_video",
                from_ms=0,
            )

        assert exc_info.value.video_id == "non_existent_video"


class TestSearchScenesGlobalPrev:
    """Tests for _search_scenes_global with direction='prev'."""

    @pytest.fixture
    def setup_scene_ranges(self, session):
        """Set up scene_ranges table for testing."""
        session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS scene_ranges (
                    artifact_id TEXT PRIMARY KEY,
                    asset_id TEXT NOT NULL,
                    scene_index INTEGER NOT NULL,
                    start_ms INTEGER NOT NULL,
                    end_ms INTEGER NOT NULL
                )
                """
            )
        )
        session.commit()
        yield
        session.execute(text("DROP TABLE IF EXISTS scene_ranges"))
        session.commit()

    def _insert_scene(
        self,
        session,
        artifact_id: str,
        asset_id: str,
        scene_index: int,
        start_ms: int,
        end_ms: int,
    ):
        """Helper to insert scene into scene_ranges table."""
        session.execute(
            text(
                """
                INSERT INTO scene_ranges
                    (artifact_id, asset_id, scene_index, start_ms, end_ms)
                VALUES (:artifact_id, :asset_id, :scene_index, :start_ms, :end_ms)
                """
            ),
            {
                "artifact_id": artifact_id,
                "asset_id": asset_id,
                "scene_index": scene_index,
                "start_ms": start_ms,
                "end_ms": end_ms,
            },
        )
        session.commit()

    def test_search_scenes_prev_single_video(
        self, session, global_jump_service, setup_scene_ranges
    ):
        """Test searching for previous scene within the same video."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        self._insert_scene(session, "scene_1", video.video_id, 0, 0, 5000)
        self._insert_scene(session, "scene_2", video.video_id, 1, 5000, 10000)
        self._insert_scene(session, "scene_3", video.video_id, 2, 10000, 15000)

        results = global_jump_service._search_scenes_global(
            direction="prev",
            from_video_id=video.video_id,
            from_ms=8000,
        )

        assert len(results) == 1
        assert results[0].artifact_id == "scene_2"
        assert results[0].jump_to.start_ms == 5000

    def test_search_scenes_prev_cross_video(
        self, session, global_jump_service, setup_scene_ranges
    ):
        """Test searching for previous scene across multiple videos."""
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        self._insert_scene(session, "scene_1", video1.video_id, 0, 5000, 10000)
        self._insert_scene(session, "scene_2", video2.video_id, 0, 5000, 10000)

        # Search from beginning of video2
        results = global_jump_service._search_scenes_global(
            direction="prev",
            from_video_id=video2.video_id,
            from_ms=0,
        )

        assert len(results) == 1
        assert results[0].video_id == "video_1"
        assert results[0].artifact_id == "scene_1"

    def test_search_scenes_prev_ordering(
        self, session, global_jump_service, setup_scene_ranges
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

        self._insert_scene(session, "scene_1", video1.video_id, 0, 0, 5000)
        self._insert_scene(session, "scene_2", video2.video_id, 0, 0, 5000)
        self._insert_scene(session, "scene_3", video3.video_id, 0, 0, 5000)

        results = global_jump_service._search_scenes_global(
            direction="prev",
            from_video_id=video3.video_id,
            from_ms=0,
            limit=3,
        )

        assert len(results) == 2
        # Should be ordered by file_created_at descending
        assert results[0].video_id == "video_b"
        assert results[1].video_id == "video_a"

    def test_search_scenes_prev_no_results(
        self, session, global_jump_service, setup_scene_ranges
    ):
        """Test that empty list is returned when no scenes found."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        self._insert_scene(session, "scene_1", video.video_id, 0, 5000, 10000)

        results = global_jump_service._search_scenes_global(
            direction="prev",
            from_video_id=video.video_id,
            from_ms=1000,
        )

        assert len(results) == 0


class TestSearchPlacesGlobal:
    """Tests for _search_places_global method."""

    def test_search_places_next_routes_to_objects(self, session, global_jump_service):
        """Test that place search uses object_labels table."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        # Places are stored as object labels
        create_object_label(
            session, "place_1", video.video_id, "kitchen", 0.9, 100, 200
        )
        create_object_label(session, "place_2", video.video_id, "beach", 0.8, 500, 600)

        results = global_jump_service._search_places_global(
            direction="next",
            from_video_id=video.video_id,
            from_ms=0,
            label="kitchen",
        )

        assert len(results) == 1
        assert results[0].artifact_id == "place_1"
        assert results[0].preview["label"] == "kitchen"

    def test_search_places_prev_routes_to_objects(self, session, global_jump_service):
        """Test that place search prev direction works."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        create_object_label(session, "place_1", video.video_id, "office", 0.9, 100, 200)
        create_object_label(session, "place_2", video.video_id, "office", 0.8, 500, 600)

        results = global_jump_service._search_places_global(
            direction="prev",
            from_video_id=video.video_id,
            from_ms=400,
            label="office",
        )

        assert len(results) == 1
        assert results[0].artifact_id == "place_1"

    def test_search_places_with_confidence_filter(self, session, global_jump_service):
        """Test that confidence filter is applied to place search."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        create_object_label(session, "place_1", video.video_id, "park", 0.5, 100, 200)
        create_object_label(session, "place_2", video.video_id, "park", 0.9, 500, 600)

        results = global_jump_service._search_places_global(
            direction="next",
            from_video_id=video.video_id,
            from_ms=0,
            label="park",
            min_confidence=0.8,
        )

        assert len(results) == 1
        assert results[0].artifact_id == "place_2"


class TestJumpNextScene:
    """Tests for jump_next() with kind='scene'."""

    @pytest.fixture
    def setup_scene_ranges(self, session):
        """Set up scene_ranges table for testing."""
        session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS scene_ranges (
                    artifact_id TEXT PRIMARY KEY,
                    asset_id TEXT NOT NULL,
                    scene_index INTEGER NOT NULL,
                    start_ms INTEGER NOT NULL,
                    end_ms INTEGER NOT NULL
                )
                """
            )
        )
        session.commit()
        yield
        session.execute(text("DROP TABLE IF EXISTS scene_ranges"))
        session.commit()

    def _insert_scene(
        self,
        session,
        artifact_id: str,
        asset_id: str,
        scene_index: int,
        start_ms: int,
        end_ms: int,
    ):
        """Helper to insert scene into scene_ranges table."""
        session.execute(
            text(
                """
                INSERT INTO scene_ranges
                    (artifact_id, asset_id, scene_index, start_ms, end_ms)
                VALUES (:artifact_id, :asset_id, :scene_index, :start_ms, :end_ms)
                """
            ),
            {
                "artifact_id": artifact_id,
                "asset_id": asset_id,
                "scene_index": scene_index,
                "start_ms": start_ms,
                "end_ms": end_ms,
            },
        )
        session.commit()

    def test_jump_next_scene_routes_correctly(
        self, session, global_jump_service, setup_scene_ranges
    ):
        """Test that kind='scene' routes to scene search."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        self._insert_scene(session, "scene_1", video.video_id, 0, 100, 5000)

        results = global_jump_service.jump_next(
            kind="scene",
            from_video_id=video.video_id,
            from_ms=0,
        )

        assert len(results) == 1
        assert results[0].artifact_id == "scene_1"
        assert "scene_index" in results[0].preview


class TestJumpNextPlace:
    """Tests for jump_next() with kind='place'."""

    def test_jump_next_place_routes_correctly(self, session, global_jump_service):
        """Test that kind='place' routes to place search."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        create_object_label(
            session, "place_1", video.video_id, "restaurant", 0.9, 100, 200
        )

        results = global_jump_service.jump_next(
            kind="place",
            from_video_id=video.video_id,
            from_ms=0,
            label="restaurant",
        )

        assert len(results) == 1
        assert results[0].artifact_id == "place_1"
        assert results[0].preview["label"] == "restaurant"


class TestJumpPrevScene:
    """Tests for jump_prev() with kind='scene'."""

    @pytest.fixture
    def setup_scene_ranges(self, session):
        """Set up scene_ranges table for testing."""
        session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS scene_ranges (
                    artifact_id TEXT PRIMARY KEY,
                    asset_id TEXT NOT NULL,
                    scene_index INTEGER NOT NULL,
                    start_ms INTEGER NOT NULL,
                    end_ms INTEGER NOT NULL
                )
                """
            )
        )
        session.commit()
        yield
        session.execute(text("DROP TABLE IF EXISTS scene_ranges"))
        session.commit()

    def _insert_scene(
        self,
        session,
        artifact_id: str,
        asset_id: str,
        scene_index: int,
        start_ms: int,
        end_ms: int,
    ):
        """Helper to insert scene into scene_ranges table."""
        session.execute(
            text(
                """
                INSERT INTO scene_ranges
                    (artifact_id, asset_id, scene_index, start_ms, end_ms)
                VALUES (:artifact_id, :asset_id, :scene_index, :start_ms, :end_ms)
                """
            ),
            {
                "artifact_id": artifact_id,
                "asset_id": asset_id,
                "scene_index": scene_index,
                "start_ms": start_ms,
                "end_ms": end_ms,
            },
        )
        session.commit()

    def test_jump_prev_scene_routes_correctly(
        self, session, global_jump_service, setup_scene_ranges
    ):
        """Test that kind='scene' routes to scene search with prev direction."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        self._insert_scene(session, "scene_1", video.video_id, 0, 100, 5000)
        self._insert_scene(session, "scene_2", video.video_id, 1, 5000, 10000)

        results = global_jump_service.jump_prev(
            kind="scene",
            from_video_id=video.video_id,
            from_ms=8000,
        )

        assert len(results) == 1
        assert results[0].artifact_id == "scene_2"


class TestJumpPrevPlace:
    """Tests for jump_prev() with kind='place'."""

    def test_jump_prev_place_routes_correctly(self, session, global_jump_service):
        """Test that kind='place' routes to place search with prev direction."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        create_object_label(session, "place_1", video.video_id, "gym", 0.9, 100, 200)
        create_object_label(session, "place_2", video.video_id, "gym", 0.8, 500, 600)

        results = global_jump_service.jump_prev(
            kind="place",
            from_video_id=video.video_id,
            from_ms=400,
            label="gym",
        )

        assert len(results) == 1
        assert results[0].artifact_id == "place_1"


class TestSearchLocationsGlobalNext:
    """Tests for _search_locations_global with direction='next'."""

    @pytest.fixture
    def setup_video_locations(self, session):
        """Set up video_locations table for testing."""
        session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS video_locations (
                    id INTEGER PRIMARY KEY,
                    video_id TEXT NOT NULL UNIQUE,
                    artifact_id TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    altitude REAL,
                    country TEXT,
                    state TEXT,
                    city TEXT
                )
                """
            )
        )
        session.commit()
        yield
        session.execute(text("DROP TABLE IF EXISTS video_locations"))
        session.commit()

    def _insert_location(
        self,
        session,
        video_id: str,
        artifact_id: str,
        latitude: float,
        longitude: float,
        altitude: float | None = None,
        country: str | None = None,
        state: str | None = None,
        city: str | None = None,
    ):
        """Helper to insert location into video_locations table."""
        session.execute(
            text(
                """
                INSERT INTO video_locations
                    (video_id, artifact_id, latitude, longitude, altitude,
                     country, state, city)
                VALUES (:video_id, :artifact_id, :latitude, :longitude, :altitude,
                        :country, :state, :city)
                """
            ),
            {
                "video_id": video_id,
                "artifact_id": artifact_id,
                "latitude": latitude,
                "longitude": longitude,
                "altitude": altitude,
                "country": country,
                "state": state,
                "city": city,
            },
        )
        session.commit()

    def test_search_locations_next_single_video(
        self, session, global_jump_service, setup_video_locations
    ):
        """Test searching for next video with location."""
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        self._insert_location(
            session,
            video1.video_id,
            "loc_1",
            35.6762,
            139.6503,
            country="Japan",
            city="Tokyo",
        )
        self._insert_location(
            session,
            video2.video_id,
            "loc_2",
            40.7128,
            -74.0060,
            country="USA",
            city="New York",
        )

        results = global_jump_service._search_locations_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=0,
        )

        assert len(results) == 1
        assert results[0].video_id == "video_2"
        assert results[0].artifact_id == "loc_2"
        assert results[0].preview["city"] == "New York"

    def test_search_locations_next_ordering(
        self, session, global_jump_service, setup_video_locations
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

        self._insert_location(session, video3.video_id, "loc_3", 51.5074, -0.1278)
        self._insert_location(session, video1.video_id, "loc_1", 35.6762, 139.6503)
        self._insert_location(session, video2.video_id, "loc_2", 40.7128, -74.0060)

        results = global_jump_service._search_locations_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=0,
            limit=3,
        )

        assert len(results) == 2
        assert results[0].video_id == "video_b"
        assert results[1].video_id == "video_c"

    def test_search_locations_next_no_results(
        self, session, global_jump_service, setup_video_locations
    ):
        """Test that empty list is returned when no locations found."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        self._insert_location(session, video.video_id, "loc_1", 35.6762, 139.6503)

        results = global_jump_service._search_locations_global(
            direction="next",
            from_video_id=video.video_id,
            from_ms=0,
        )

        assert len(results) == 0

    def test_search_locations_next_video_not_found(
        self, session, global_jump_service, setup_video_locations
    ):
        """Test that VideoNotFoundError is raised for non-existent video."""
        with pytest.raises(VideoNotFoundError) as exc_info:
            global_jump_service._search_locations_global(
                direction="next",
                from_video_id="non_existent_video",
                from_ms=0,
            )

        assert exc_info.value.video_id == "non_existent_video"

    def test_search_locations_next_result_contains_all_fields(
        self, session, global_jump_service, setup_video_locations
    ):
        """Test that results contain all required fields."""
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        self._insert_location(
            session,
            video2.video_id,
            "loc_2",
            35.6762,
            139.6503,
            altitude=10.5,
            country="Japan",
            state="Tokyo",
            city="Shibuya",
        )

        results = global_jump_service._search_locations_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=0,
        )

        assert len(results) == 1
        result = results[0]
        assert result.video_id == "video_2"
        assert result.video_filename == "video2.mp4"
        assert result.jump_to.start_ms == 0
        assert result.jump_to.end_ms == 0
        assert result.artifact_id == "loc_2"
        assert result.preview["latitude"] == 35.6762
        assert result.preview["longitude"] == 139.6503
        assert result.preview["altitude"] == 10.5
        assert result.preview["country"] == "Japan"
        assert result.preview["state"] == "Tokyo"
        assert result.preview["city"] == "Shibuya"


class TestSearchLocationsGlobalPrev:
    """Tests for _search_locations_global with direction='prev'."""

    @pytest.fixture
    def setup_video_locations(self, session):
        """Set up video_locations table for testing."""
        session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS video_locations (
                    id INTEGER PRIMARY KEY,
                    video_id TEXT NOT NULL UNIQUE,
                    artifact_id TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    altitude REAL,
                    country TEXT,
                    state TEXT,
                    city TEXT
                )
                """
            )
        )
        session.commit()
        yield
        session.execute(text("DROP TABLE IF EXISTS video_locations"))
        session.commit()

    def _insert_location(
        self,
        session,
        video_id: str,
        artifact_id: str,
        latitude: float,
        longitude: float,
        altitude: float | None = None,
        country: str | None = None,
        state: str | None = None,
        city: str | None = None,
    ):
        """Helper to insert location into video_locations table."""
        session.execute(
            text(
                """
                INSERT INTO video_locations
                    (video_id, artifact_id, latitude, longitude, altitude,
                     country, state, city)
                VALUES (:video_id, :artifact_id, :latitude, :longitude, :altitude,
                        :country, :state, :city)
                """
            ),
            {
                "video_id": video_id,
                "artifact_id": artifact_id,
                "latitude": latitude,
                "longitude": longitude,
                "altitude": altitude,
                "country": country,
                "state": state,
                "city": city,
            },
        )
        session.commit()

    def test_search_locations_prev_single_video(
        self, session, global_jump_service, setup_video_locations
    ):
        """Test searching for previous video with location."""
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        self._insert_location(
            session,
            video1.video_id,
            "loc_1",
            35.6762,
            139.6503,
            country="Japan",
            city="Tokyo",
        )
        self._insert_location(
            session,
            video2.video_id,
            "loc_2",
            40.7128,
            -74.0060,
            country="USA",
            city="New York",
        )

        results = global_jump_service._search_locations_global(
            direction="prev",
            from_video_id=video2.video_id,
            from_ms=0,
        )

        assert len(results) == 1
        assert results[0].video_id == "video_1"
        assert results[0].artifact_id == "loc_1"
        assert results[0].preview["city"] == "Tokyo"

    def test_search_locations_prev_ordering(
        self, session, global_jump_service, setup_video_locations
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

        self._insert_location(session, video1.video_id, "loc_1", 35.6762, 139.6503)
        self._insert_location(session, video2.video_id, "loc_2", 40.7128, -74.0060)
        self._insert_location(session, video3.video_id, "loc_3", 51.5074, -0.1278)

        results = global_jump_service._search_locations_global(
            direction="prev",
            from_video_id=video3.video_id,
            from_ms=0,
            limit=3,
        )

        assert len(results) == 2
        # Should be ordered by file_created_at descending
        assert results[0].video_id == "video_b"
        assert results[1].video_id == "video_a"

    def test_search_locations_prev_no_results(
        self, session, global_jump_service, setup_video_locations
    ):
        """Test that empty list is returned when no locations found."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        self._insert_location(session, video.video_id, "loc_1", 35.6762, 139.6503)

        results = global_jump_service._search_locations_global(
            direction="prev",
            from_video_id=video.video_id,
            from_ms=0,
        )

        assert len(results) == 0


class TestJumpNextLocation:
    """Tests for jump_next() with kind='location'."""

    @pytest.fixture
    def setup_video_locations(self, session):
        """Set up video_locations table for testing."""
        session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS video_locations (
                    id INTEGER PRIMARY KEY,
                    video_id TEXT NOT NULL UNIQUE,
                    artifact_id TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    altitude REAL,
                    country TEXT,
                    state TEXT,
                    city TEXT
                )
                """
            )
        )
        session.commit()
        yield
        session.execute(text("DROP TABLE IF EXISTS video_locations"))
        session.commit()

    def _insert_location(
        self,
        session,
        video_id: str,
        artifact_id: str,
        latitude: float,
        longitude: float,
    ):
        """Helper to insert location into video_locations table."""
        session.execute(
            text(
                """
                INSERT INTO video_locations
                    (video_id, artifact_id, latitude, longitude)
                VALUES (:video_id, :artifact_id, :latitude, :longitude)
                """
            ),
            {
                "video_id": video_id,
                "artifact_id": artifact_id,
                "latitude": latitude,
                "longitude": longitude,
            },
        )
        session.commit()

    def test_jump_next_location_routes_correctly(
        self, session, global_jump_service, setup_video_locations
    ):
        """Test that kind='location' routes to location search."""
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        self._insert_location(session, video2.video_id, "loc_2", 35.6762, 139.6503)

        results = global_jump_service.jump_next(
            kind="location",
            from_video_id=video1.video_id,
            from_ms=0,
        )

        assert len(results) == 1
        assert results[0].video_id == "video_2"
        assert "latitude" in results[0].preview
        assert "longitude" in results[0].preview


class TestJumpPrevLocation:
    """Tests for jump_prev() with kind='location'."""

    @pytest.fixture
    def setup_video_locations(self, session):
        """Set up video_locations table for testing."""
        session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS video_locations (
                    id INTEGER PRIMARY KEY,
                    video_id TEXT NOT NULL UNIQUE,
                    artifact_id TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    altitude REAL,
                    country TEXT,
                    state TEXT,
                    city TEXT
                )
                """
            )
        )
        session.commit()
        yield
        session.execute(text("DROP TABLE IF EXISTS video_locations"))
        session.commit()

    def _insert_location(
        self,
        session,
        video_id: str,
        artifact_id: str,
        latitude: float,
        longitude: float,
    ):
        """Helper to insert location into video_locations table."""
        session.execute(
            text(
                """
                INSERT INTO video_locations
                    (video_id, artifact_id, latitude, longitude)
                VALUES (:video_id, :artifact_id, :latitude, :longitude)
                """
            ),
            {
                "video_id": video_id,
                "artifact_id": artifact_id,
                "latitude": latitude,
                "longitude": longitude,
            },
        )
        session.commit()

    def test_jump_prev_location_routes_correctly(
        self, session, global_jump_service, setup_video_locations
    ):
        """Test that kind='location' routes to location search with prev direction."""
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        self._insert_location(session, video1.video_id, "loc_1", 35.6762, 139.6503)

        results = global_jump_service.jump_prev(
            kind="location",
            from_video_id=video2.video_id,
            from_ms=0,
        )

        assert len(results) == 1
        assert results[0].video_id == "video_1"
        assert "latitude" in results[0].preview


class TestBoundaryConditionFromMsBeyondDuration:
    """Tests for boundary condition handling when from_ms exceeds video duration.

    Property 15: Boundary Condition - from_ms Beyond Duration
    Validates: Requirements 11.4

    When from_ms is beyond the video duration, the system should treat it as
    the end of that video and search forward (for "next") or backward (for "prev")
    accordingly without error.
    """

    def test_from_ms_beyond_duration_next_moves_to_next_video(
        self, session, global_jump_service
    ):
        """Test that from_ms beyond duration moves to next video for 'next' direction.

        When from_ms is far beyond any artifact in the current video,
        the search should naturally find artifacts in the next video.
        """
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        # Create artifacts - video1 has artifacts up to 5000ms
        create_object_label(session, "obj_1", video1.video_id, "dog", 0.9, 1000, 2000)
        create_object_label(session, "obj_2", video1.video_id, "dog", 0.9, 3000, 4000)
        create_object_label(session, "obj_3", video2.video_id, "dog", 0.9, 500, 1000)

        # Search with from_ms far beyond video1's content (simulating beyond duration)
        results = global_jump_service.jump_next(
            kind="object",
            from_video_id=video1.video_id,
            from_ms=999999999,  # Way beyond any video duration
            label="dog",
        )

        # Should find artifact in video2, not raise an error
        assert len(results) == 1
        assert results[0].video_id == "video_2"
        assert results[0].artifact_id == "obj_3"

    def test_from_ms_beyond_duration_prev_finds_last_artifact(
        self, session, global_jump_service
    ):
        """Test that from_ms beyond duration finds last artifact for 'prev' direction.

        When from_ms is far beyond any artifact in the current video,
        the search should find the last artifact in that video.
        """
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        # Create artifacts at various timestamps
        create_object_label(session, "obj_1", video.video_id, "cat", 0.9, 1000, 2000)
        create_object_label(session, "obj_2", video.video_id, "cat", 0.9, 3000, 4000)
        create_object_label(session, "obj_3", video.video_id, "cat", 0.9, 5000, 6000)

        # Search with from_ms far beyond video's content
        results = global_jump_service.jump_prev(
            kind="object",
            from_video_id=video.video_id,
            from_ms=999999999,  # Way beyond any video duration
            label="cat",
        )

        # Should find the last artifact (obj_3), not raise an error
        assert len(results) == 1
        assert results[0].artifact_id == "obj_3"
        assert results[0].jump_to.start_ms == 5000

    def test_from_ms_beyond_duration_no_error_raised(
        self, session, global_jump_service
    ):
        """Test that no error is raised when from_ms exceeds video duration."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        create_object_label(session, "obj_1", video.video_id, "dog", 0.9, 1000, 2000)

        # These should not raise any exceptions
        results_next = global_jump_service.jump_next(
            kind="object",
            from_video_id=video.video_id,
            from_ms=2**31 - 1,  # Max 32-bit signed integer
            label="dog",
        )

        results_prev = global_jump_service.jump_prev(
            kind="object",
            from_video_id=video.video_id,
            from_ms=2**31 - 1,  # Max 32-bit signed integer
            label="dog",
        )

        # No errors raised, results are valid (may be empty for next)
        assert isinstance(results_next, list)
        assert isinstance(results_prev, list)
        # prev should find the artifact since it's before the large from_ms
        assert len(results_prev) == 1
        assert results_prev[0].artifact_id == "obj_1"

    def test_from_ms_beyond_duration_empty_results_when_no_next_video(
        self, session, global_jump_service
    ):
        """Test empty results when from_ms beyond duration and no next video exists."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        create_object_label(session, "obj_1", video.video_id, "dog", 0.9, 1000, 2000)

        # Search next with from_ms beyond duration, no other videos exist
        results = global_jump_service.jump_next(
            kind="object",
            from_video_id=video.video_id,
            from_ms=999999999,
            label="dog",
        )

        # Should return empty list, not raise an error
        assert len(results) == 0

    def test_from_ms_beyond_duration_prev_crosses_to_previous_video(
        self, session, global_jump_service
    ):
        """Test prev direction crosses to previous video when from_ms > duration."""
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        create_object_label(session, "obj_1", video1.video_id, "bird", 0.9, 1000, 2000)
        # No artifacts in video2

        # Search prev from video2 with large from_ms
        results = global_jump_service.jump_prev(
            kind="object",
            from_video_id=video2.video_id,
            from_ms=999999999,
            label="bird",
        )

        # Should find artifact in video1
        assert len(results) == 1
        assert results[0].video_id == "video_1"
        assert results[0].artifact_id == "obj_1"


class TestArbitraryPositionNavigation:
    """Tests for arbitrary position navigation.

    Property 13: Arbitrary Position Navigation
    Validates: Requirements 11.1, 11.2, 11.3

    For any global jump query with from_video_id and from_ms parameters,
    the search should start from that position in the global timeline.
    Results should be chronologically after (for "next") or before (for "prev")
    that position.
    """

    def test_arbitrary_position_next_within_same_video(
        self, session, global_jump_service
    ):
        """Test next from arbitrary position within the same video.

        Validates: Requirement 11.1 - from_video_id and from_ms as starting point
        """
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        # Create artifacts at various timestamps
        create_object_label(session, "obj_1", video.video_id, "dog", 0.9, 100, 200)
        create_object_label(session, "obj_2", video.video_id, "dog", 0.9, 500, 600)
        create_object_label(session, "obj_3", video.video_id, "dog", 0.9, 1000, 1100)
        create_object_label(session, "obj_4", video.video_id, "dog", 0.9, 1500, 1600)

        # Search from arbitrary position at 700ms
        results = global_jump_service.jump_next(
            kind="object",
            from_video_id=video.video_id,
            from_ms=700,
            label="dog",
        )

        # Should find obj_3 (first artifact after 700ms)
        assert len(results) == 1
        assert results[0].artifact_id == "obj_3"
        assert results[0].jump_to.start_ms == 1000
        assert results[0].jump_to.start_ms > 700  # Chronologically after

    def test_arbitrary_position_prev_within_same_video(
        self, session, global_jump_service
    ):
        """Test prev from arbitrary position within the same video.

        Validates: Requirement 11.3 - prev returns results before position
        """
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        # Create artifacts at various timestamps
        create_object_label(session, "obj_1", video.video_id, "cat", 0.9, 100, 200)
        create_object_label(session, "obj_2", video.video_id, "cat", 0.9, 500, 600)
        create_object_label(session, "obj_3", video.video_id, "cat", 0.9, 1000, 1100)
        create_object_label(session, "obj_4", video.video_id, "cat", 0.9, 1500, 1600)

        # Search from arbitrary position at 1200ms
        results = global_jump_service.jump_prev(
            kind="object",
            from_video_id=video.video_id,
            from_ms=1200,
            label="cat",
        )

        # Should find obj_3 (first artifact before 1200ms in descending order)
        assert len(results) == 1
        assert results[0].artifact_id == "obj_3"
        assert results[0].jump_to.start_ms == 1000
        assert results[0].jump_to.start_ms < 1200  # Chronologically before

    def test_arbitrary_position_next_crosses_video_boundary(
        self, session, global_jump_service
    ):
        """Test next from arbitrary position crosses to next video.

        Validates: Requirement 11.2 - next returns results after position
        """
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        # Create artifacts in both videos
        create_object_label(session, "obj_1", video1.video_id, "bird", 0.9, 100, 200)
        create_object_label(session, "obj_2", video1.video_id, "bird", 0.9, 500, 600)
        create_object_label(session, "obj_3", video2.video_id, "bird", 0.9, 100, 200)

        # Search from arbitrary position at end of video1
        results = global_jump_service.jump_next(
            kind="object",
            from_video_id=video1.video_id,
            from_ms=800,  # After all artifacts in video1
            label="bird",
        )

        # Should find obj_3 in video2 (chronologically after video1)
        assert len(results) == 1
        assert results[0].video_id == "video_2"
        assert results[0].artifact_id == "obj_3"

    def test_arbitrary_position_prev_crosses_video_boundary(
        self, session, global_jump_service
    ):
        """Test prev from arbitrary position crosses to previous video.

        Validates: Requirement 11.3 - prev returns results before position
        """
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        # Create artifacts in both videos
        create_object_label(session, "obj_1", video1.video_id, "fish", 0.9, 500, 600)
        create_object_label(session, "obj_2", video2.video_id, "fish", 0.9, 1000, 1100)

        # Search from arbitrary position at beginning of video2
        results = global_jump_service.jump_prev(
            kind="object",
            from_video_id=video2.video_id,
            from_ms=50,  # Before all artifacts in video2
            label="fish",
        )

        # Should find obj_1 in video1 (chronologically before video2)
        assert len(results) == 1
        assert results[0].video_id == "video_1"
        assert results[0].artifact_id == "obj_1"

    def test_arbitrary_position_with_various_video_orderings(
        self, session, global_jump_service
    ):
        """Test arbitrary position with videos in various chronological orders.

        Validates: Requirements 11.1, 11.2, 11.3
        """
        # Create videos with non-sequential IDs but sequential dates
        video_c = create_test_video(
            session, "video_c", "video_c.mp4", datetime(2025, 1, 3, 12, 0, 0)
        )
        video_a = create_test_video(
            session, "video_a", "video_a.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video_b = create_test_video(
            session, "video_b", "video_b.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        # Create artifacts in each video
        create_object_label(session, "obj_a", video_a.video_id, "car", 0.9, 500, 600)
        create_object_label(session, "obj_b", video_b.video_id, "car", 0.9, 500, 600)
        create_object_label(session, "obj_c", video_c.video_id, "car", 0.9, 500, 600)

        # Search next from video_a - should find video_b (chronologically next)
        results_next = global_jump_service.jump_next(
            kind="object",
            from_video_id=video_a.video_id,
            from_ms=700,
            label="car",
        )

        assert len(results_next) == 1
        assert results_next[0].video_id == "video_b"

        # Search prev from video_c - should find video_b (chronologically previous)
        results_prev = global_jump_service.jump_prev(
            kind="object",
            from_video_id=video_c.video_id,
            from_ms=0,
            label="car",
        )

        assert len(results_prev) == 1
        assert results_prev[0].video_id == "video_b"

    def test_arbitrary_position_with_same_file_created_at(
        self, session, global_jump_service
    ):
        """Test arbitrary position when videos have same file_created_at.

        When file_created_at is the same, video_id is used as secondary sort key.
        Validates: Requirements 11.1, 11.2, 11.3
        """
        same_time = datetime(2025, 1, 1, 12, 0, 0)

        # Create videos with same timestamp but different IDs
        video_x = create_test_video(session, "video_x", "video_x.mp4", same_time)
        video_y = create_test_video(session, "video_y", "video_y.mp4", same_time)
        video_z = create_test_video(session, "video_z", "video_z.mp4", same_time)

        # Create artifacts
        create_object_label(session, "obj_x", video_x.video_id, "tree", 0.9, 500, 600)
        create_object_label(session, "obj_y", video_y.video_id, "tree", 0.9, 500, 600)
        create_object_label(session, "obj_z", video_z.video_id, "tree", 0.9, 500, 600)

        # Search next from video_x - should find video_y (alphabetically next)
        results_next = global_jump_service.jump_next(
            kind="object",
            from_video_id=video_x.video_id,
            from_ms=700,
            label="tree",
        )

        assert len(results_next) == 1
        assert results_next[0].video_id == "video_y"

        # Search prev from video_z - should find video_y (alphabetically previous)
        results_prev = global_jump_service.jump_prev(
            kind="object",
            from_video_id=video_z.video_id,
            from_ms=0,
            label="tree",
        )

        assert len(results_prev) == 1
        assert results_prev[0].video_id == "video_y"

    def test_arbitrary_position_exact_timestamp_match(
        self, session, global_jump_service
    ):
        """Test arbitrary position when from_ms exactly matches an artifact start_ms.

        The artifact at the exact position should NOT be included in results.
        Validates: Requirements 11.2, 11.3
        """
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        # Create artifacts at specific timestamps
        create_object_label(session, "obj_1", video.video_id, "dog", 0.9, 100, 200)
        create_object_label(session, "obj_2", video.video_id, "dog", 0.9, 500, 600)
        create_object_label(session, "obj_3", video.video_id, "dog", 0.9, 1000, 1100)

        # Search next from exact position of obj_2 (500ms)
        results_next = global_jump_service.jump_next(
            kind="object",
            from_video_id=video.video_id,
            from_ms=500,  # Exact match with obj_2
            label="dog",
        )

        # Should find obj_3, NOT obj_2 (which is at the exact position)
        assert len(results_next) == 1
        assert results_next[0].artifact_id == "obj_3"
        assert results_next[0].jump_to.start_ms > 500

        # Search prev from exact position of obj_2 (500ms)
        results_prev = global_jump_service.jump_prev(
            kind="object",
            from_video_id=video.video_id,
            from_ms=500,  # Exact match with obj_2
            label="dog",
        )

        # Should find obj_1, NOT obj_2 (which is at the exact position)
        assert len(results_prev) == 1
        assert results_prev[0].artifact_id == "obj_1"
        assert results_prev[0].jump_to.start_ms < 500

    def test_arbitrary_position_with_multiple_results(
        self, session, global_jump_service
    ):
        """Test arbitrary position returns multiple results in correct order.

        Validates: Requirements 11.1, 11.2, 11.3
        """
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        # Create multiple artifacts
        create_object_label(session, "obj_1", video1.video_id, "dog", 0.9, 100, 200)
        create_object_label(session, "obj_2", video1.video_id, "dog", 0.9, 500, 600)
        create_object_label(session, "obj_3", video1.video_id, "dog", 0.9, 1000, 1100)
        create_object_label(session, "obj_4", video2.video_id, "dog", 0.9, 100, 200)
        create_object_label(session, "obj_5", video2.video_id, "dog", 0.9, 500, 600)

        # Search next from arbitrary position with limit=3
        results = global_jump_service.jump_next(
            kind="object",
            from_video_id=video1.video_id,
            from_ms=300,
            label="dog",
            limit=3,
        )

        # Should return 3 results in chronological order
        assert len(results) == 3
        assert results[0].artifact_id == "obj_2"  # video1, 500ms
        assert results[1].artifact_id == "obj_3"  # video1, 1000ms
        assert results[2].artifact_id == "obj_4"  # video2, 100ms

        # All results should be chronologically after 300ms in video1
        assert results[0].jump_to.start_ms > 300

    def test_arbitrary_position_from_middle_of_timeline(
        self, session, global_jump_service
    ):
        """Test arbitrary position from middle of global timeline.

        Validates: Requirements 11.1, 11.2, 11.3
        """
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )
        video3 = create_test_video(
            session, "video_3", "video3.mp4", datetime(2025, 1, 3, 12, 0, 0)
        )

        # Create artifacts in all videos
        create_object_label(session, "obj_1", video1.video_id, "cat", 0.9, 500, 600)
        create_object_label(session, "obj_2", video2.video_id, "cat", 0.9, 500, 600)
        create_object_label(session, "obj_3", video3.video_id, "cat", 0.9, 500, 600)

        # Search next from middle video (video2)
        results_next = global_jump_service.jump_next(
            kind="object",
            from_video_id=video2.video_id,
            from_ms=700,
            label="cat",
        )

        # Should find video3 (chronologically after video2)
        assert len(results_next) == 1
        assert results_next[0].video_id == "video_3"

        # Search prev from middle video (video2)
        results_prev = global_jump_service.jump_prev(
            kind="object",
            from_video_id=video2.video_id,
            from_ms=0,
            label="cat",
        )

        # Should find video1 (chronologically before video2)
        assert len(results_prev) == 1
        assert results_prev[0].video_id == "video_1"

    def test_arbitrary_position_with_null_file_created_at(
        self, session, global_jump_service
    ):
        """Test arbitrary position with NULL file_created_at values.

        NULL file_created_at values are sorted after non-NULL values.
        Validates: Requirements 11.1, 11.2, 11.3
        """
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session,
            "video_2",
            "video2.mp4",
            None,  # NULL file_created_at
        )
        video3 = create_test_video(
            session, "video_3", "video3.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        # Create artifacts
        create_object_label(session, "obj_1", video1.video_id, "dog", 0.9, 500, 600)
        create_object_label(session, "obj_2", video2.video_id, "dog", 0.9, 500, 600)
        create_object_label(session, "obj_3", video3.video_id, "dog", 0.9, 500, 600)

        # Search next from video3 - should find video2 (NULL sorted after)
        results_next = global_jump_service.jump_next(
            kind="object",
            from_video_id=video3.video_id,
            from_ms=700,
            label="dog",
        )

        assert len(results_next) == 1
        assert results_next[0].video_id == "video_2"

        # Search prev from video2 (NULL) - should find video3 (non-NULL before NULL)
        results_prev = global_jump_service.jump_prev(
            kind="object",
            from_video_id=video2.video_id,
            from_ms=0,
            label="dog",
        )

        assert len(results_prev) == 1
        assert results_prev[0].video_id == "video_3"

    def test_arbitrary_position_no_results_after_position(
        self, session, global_jump_service
    ):
        """Test arbitrary position when no results exist after the position.

        Validates: Requirements 11.2
        """
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        # Create artifacts only at early timestamps
        create_object_label(session, "obj_1", video.video_id, "dog", 0.9, 100, 200)
        create_object_label(session, "obj_2", video.video_id, "dog", 0.9, 300, 400)

        # Search next from position after all artifacts
        results = global_jump_service.jump_next(
            kind="object",
            from_video_id=video.video_id,
            from_ms=500,
            label="dog",
        )

        # Should return empty list
        assert len(results) == 0

    def test_arbitrary_position_no_results_before_position(
        self, session, global_jump_service
    ):
        """Test arbitrary position when no results exist before the position.

        Validates: Requirements 11.3
        """
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        # Create artifacts only at late timestamps
        create_object_label(session, "obj_1", video.video_id, "cat", 0.9, 500, 600)
        create_object_label(session, "obj_2", video.video_id, "cat", 0.9, 700, 800)

        # Search prev from position before all artifacts
        results = global_jump_service.jump_prev(
            kind="object",
            from_video_id=video.video_id,
            from_ms=100,
            label="cat",
        )

        # Should return empty list
        assert len(results) == 0

    def test_arbitrary_position_with_transcript_search(
        self, session, global_jump_service
    ):
        """Test arbitrary position with transcript full-text search.

        Validates: Requirements 11.1, 11.2, 11.3
        """
        # Set up transcript FTS table for SQLite
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

        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        # Insert transcripts
        for artifact_id, start_ms, text_content in [
            ("trans_1", 100, "hello world"),
            ("trans_2", 500, "hello again"),
            ("trans_3", 1000, "goodbye world"),
        ]:
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
                    "asset_id": video.video_id,
                    "start_ms": start_ms,
                    "end_ms": start_ms + 100,
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
                    "asset_id": video.video_id,
                    "start_ms": start_ms,
                    "end_ms": start_ms + 100,
                },
            )
        session.commit()

        # Search next from arbitrary position
        results = global_jump_service.jump_next(
            kind="transcript",
            from_video_id=video.video_id,
            from_ms=300,
            query="hello",
        )

        # Should find trans_2 (first "hello" after 300ms)
        assert len(results) == 1
        assert results[0].artifact_id == "trans_2"
        assert results[0].jump_to.start_ms == 500

        # Cleanup
        session.execute(text("DROP TABLE IF EXISTS transcript_fts_metadata"))
        session.execute(text("DROP TABLE IF EXISTS transcript_fts"))
        session.commit()

    def test_arbitrary_position_with_scene_search(self, session, global_jump_service):
        """Test arbitrary position with scene search.

        Validates: Requirements 11.1, 11.2, 11.3
        """
        from src.database.models import SceneRange

        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        # Create scene ranges
        for artifact_id, scene_index, start_ms in [
            ("scene_1", 0, 0),
            ("scene_2", 1, 5000),
            ("scene_3", 2, 10000),
        ]:
            scene = SceneRange(
                artifact_id=artifact_id,
                asset_id=video.video_id,
                scene_index=scene_index,
                start_ms=start_ms,
                end_ms=start_ms + 4000,
            )
            session.add(scene)
        session.commit()

        # Search next from arbitrary position
        results = global_jump_service.jump_next(
            kind="scene",
            from_video_id=video.video_id,
            from_ms=6000,
        )

        # Should find scene_3 (first scene after 6000ms)
        assert len(results) == 1
        assert results[0].artifact_id == "scene_3"
        assert results[0].jump_to.start_ms == 10000


class TestFilterChangeIndependence:
    """Tests for filter change independence.

    Verifies that changing filters (label, query, kind) doesn't affect timeline
    position. Each query is independent and doesn't carry state from previous
    queries.

    Validates: Requirements 12.1, 12.2, 12.3, 12.4
    """

    def test_consecutive_queries_with_different_labels(
        self, session, global_jump_service
    ):
        """Test that consecutive queries with different labels are independent.

        Validates: Requirements 12.1, 12.2
        """
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        # Create objects with different labels at different timestamps
        create_object_label(session, "obj_dog_1", video.video_id, "dog", 0.9, 100, 200)
        create_object_label(session, "obj_cat_1", video.video_id, "cat", 0.9, 150, 250)
        create_object_label(session, "obj_dog_2", video.video_id, "dog", 0.9, 300, 400)
        create_object_label(session, "obj_cat_2", video.video_id, "cat", 0.9, 350, 450)
        create_object_label(session, "obj_dog_3", video.video_id, "dog", 0.9, 500, 600)
        create_object_label(session, "obj_cat_3", video.video_id, "cat", 0.9, 550, 650)

        # First query: search for "dog" from position 0
        results_dog = global_jump_service.jump_next(
            kind="object",
            from_video_id=video.video_id,
            from_ms=0,
            label="dog",
        )
        assert len(results_dog) == 1
        assert results_dog[0].artifact_id == "obj_dog_1"
        assert results_dog[0].preview["label"] == "dog"

        # Second query: search for "cat" from the SAME position (0)
        # This should NOT be affected by the previous "dog" query
        results_cat = global_jump_service.jump_next(
            kind="object",
            from_video_id=video.video_id,
            from_ms=0,
            label="cat",
        )
        assert len(results_cat) == 1
        assert results_cat[0].artifact_id == "obj_cat_1"
        assert results_cat[0].preview["label"] == "cat"

        # Third query: search for "dog" again from position 0
        # Should return the same result as the first query
        results_dog_again = global_jump_service.jump_next(
            kind="object",
            from_video_id=video.video_id,
            from_ms=0,
            label="dog",
        )
        assert len(results_dog_again) == 1
        assert results_dog_again[0].artifact_id == "obj_dog_1"
        assert results_dog_again[0].preview["label"] == "dog"

    def test_filter_change_maintains_timeline_position(
        self, session, global_jump_service
    ):
        """Test that changing filters maintains the same timeline position.

        Validates: Requirements 12.2, 12.4
        """
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        # Create objects at various timestamps
        create_object_label(session, "obj_dog_1", video.video_id, "dog", 0.9, 100, 200)
        create_object_label(session, "obj_cat_1", video.video_id, "cat", 0.9, 200, 300)
        create_object_label(session, "obj_dog_2", video.video_id, "dog", 0.9, 400, 500)
        create_object_label(session, "obj_cat_2", video.video_id, "cat", 0.9, 500, 600)

        # Search for "dog" from position 250
        results_dog = global_jump_service.jump_next(
            kind="object",
            from_video_id=video.video_id,
            from_ms=250,
            label="dog",
        )
        assert len(results_dog) == 1
        assert results_dog[0].artifact_id == "obj_dog_2"
        assert results_dog[0].jump_to.start_ms == 400

        # Change filter to "cat" but keep same position (250)
        # Should find cat at 500ms, not be affected by previous dog search
        results_cat = global_jump_service.jump_next(
            kind="object",
            from_video_id=video.video_id,
            from_ms=250,
            label="cat",
        )
        assert len(results_cat) == 1
        assert results_cat[0].artifact_id == "obj_cat_2"
        assert results_cat[0].jump_to.start_ms == 500

    def test_kind_change_routes_to_different_projection_table(
        self, session, global_jump_service
    ):
        """Test that changing kind routes to appropriate projection table.

        Validates: Requirements 12.3
        """
        from src.database.models import SceneRange

        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        # Create object labels
        create_object_label(session, "obj_1", video.video_id, "dog", 0.9, 100, 200)
        create_object_label(session, "obj_2", video.video_id, "dog", 0.9, 500, 600)

        # Create scene ranges
        scene1 = SceneRange(
            artifact_id="scene_1",
            asset_id=video.video_id,
            scene_index=0,
            start_ms=0,
            end_ms=300,
        )
        scene2 = SceneRange(
            artifact_id="scene_2",
            asset_id=video.video_id,
            scene_index=1,
            start_ms=300,
            end_ms=700,
        )
        session.add(scene1)
        session.add(scene2)
        session.commit()

        # Search for objects from position 0
        results_object = global_jump_service.jump_next(
            kind="object",
            from_video_id=video.video_id,
            from_ms=0,
            label="dog",
        )
        assert len(results_object) == 1
        assert results_object[0].artifact_id == "obj_1"
        assert "label" in results_object[0].preview

        # Change kind to "scene" from same position
        # Should search scene_ranges table, not object_labels
        results_scene = global_jump_service.jump_next(
            kind="scene",
            from_video_id=video.video_id,
            from_ms=0,
        )
        assert len(results_scene) == 1
        assert results_scene[0].artifact_id == "scene_2"
        assert "scene_index" in results_scene[0].preview

    def test_multiple_consecutive_queries_different_filters(
        self, session, global_jump_service
    ):
        """Test multiple consecutive queries with different filters.

        Validates: Requirements 12.1, 12.2, 12.3, 12.4
        """
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        # Create various objects
        create_object_label(session, "obj_dog", video.video_id, "dog", 0.9, 100, 200)
        create_object_label(session, "obj_cat", video.video_id, "cat", 0.8, 200, 300)
        create_object_label(session, "obj_bird", video.video_id, "bird", 0.7, 300, 400)
        create_object_label(session, "obj_car", video.video_id, "car", 0.95, 400, 500)

        # Run multiple queries from the same position
        position = 50

        # Query 1: dog
        r1 = global_jump_service.jump_next(
            kind="object", from_video_id=video.video_id, from_ms=position, label="dog"
        )
        assert r1[0].artifact_id == "obj_dog"

        # Query 2: cat
        r2 = global_jump_service.jump_next(
            kind="object", from_video_id=video.video_id, from_ms=position, label="cat"
        )
        assert r2[0].artifact_id == "obj_cat"

        # Query 3: bird
        r3 = global_jump_service.jump_next(
            kind="object", from_video_id=video.video_id, from_ms=position, label="bird"
        )
        assert r3[0].artifact_id == "obj_bird"

        # Query 4: car
        r4 = global_jump_service.jump_next(
            kind="object", from_video_id=video.video_id, from_ms=position, label="car"
        )
        assert r4[0].artifact_id == "obj_car"

        # Query 5: back to dog - should still return same result
        r5 = global_jump_service.jump_next(
            kind="object", from_video_id=video.video_id, from_ms=position, label="dog"
        )
        assert r5[0].artifact_id == "obj_dog"

    def test_filter_change_with_no_results_for_new_filter(
        self, session, global_jump_service
    ):
        """Test that changing to a filter with no results returns empty array.

        Validates: Requirements 12.5
        """
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        # Create only dog objects
        create_object_label(session, "obj_dog_1", video.video_id, "dog", 0.9, 100, 200)
        create_object_label(session, "obj_dog_2", video.video_id, "dog", 0.9, 300, 400)

        # First query: search for "dog" - should find results
        results_dog = global_jump_service.jump_next(
            kind="object",
            from_video_id=video.video_id,
            from_ms=0,
            label="dog",
        )
        assert len(results_dog) == 1
        assert results_dog[0].artifact_id == "obj_dog_1"

        # Second query: search for "elephant" - no such objects exist
        results_elephant = global_jump_service.jump_next(
            kind="object",
            from_video_id=video.video_id,
            from_ms=0,
            label="elephant",
        )
        assert len(results_elephant) == 0

        # Third query: back to "dog" - should still work
        results_dog_again = global_jump_service.jump_next(
            kind="object",
            from_video_id=video.video_id,
            from_ms=0,
            label="dog",
        )
        assert len(results_dog_again) == 1
        assert results_dog_again[0].artifact_id == "obj_dog_1"

    def test_filter_change_with_confidence_threshold(
        self, session, global_jump_service
    ):
        """Test filter changes with varying confidence thresholds.

        Validates: Requirements 12.1, 12.2
        """
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        # Create objects with different confidence levels
        create_object_label(
            session, "obj_dog_low", video.video_id, "dog", 0.5, 100, 200
        )
        create_object_label(
            session, "obj_dog_high", video.video_id, "dog", 0.9, 300, 400
        )
        create_object_label(
            session, "obj_cat_low", video.video_id, "cat", 0.4, 150, 250
        )
        create_object_label(
            session, "obj_cat_high", video.video_id, "cat", 0.95, 350, 450
        )

        # Query 1: dog with high confidence threshold
        r1 = global_jump_service.jump_next(
            kind="object",
            from_video_id=video.video_id,
            from_ms=0,
            label="dog",
            min_confidence=0.8,
        )
        assert len(r1) == 1
        assert r1[0].artifact_id == "obj_dog_high"

        # Query 2: cat with high confidence threshold
        r2 = global_jump_service.jump_next(
            kind="object",
            from_video_id=video.video_id,
            from_ms=0,
            label="cat",
            min_confidence=0.8,
        )
        assert len(r2) == 1
        assert r2[0].artifact_id == "obj_cat_high"

        # Query 3: dog with low confidence threshold
        r3 = global_jump_service.jump_next(
            kind="object",
            from_video_id=video.video_id,
            from_ms=0,
            label="dog",
            min_confidence=0.3,
        )
        assert len(r3) == 1
        assert r3[0].artifact_id == "obj_dog_low"

    def test_filter_change_across_videos(self, session, global_jump_service):
        """Test filter changes work correctly across multiple videos.

        Validates: Requirements 12.1, 12.2, 12.4
        """
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        # Create objects in both videos
        create_object_label(session, "v1_dog", video1.video_id, "dog", 0.9, 100, 200)
        create_object_label(session, "v1_cat", video1.video_id, "cat", 0.9, 200, 300)
        create_object_label(session, "v2_dog", video2.video_id, "dog", 0.9, 100, 200)
        create_object_label(session, "v2_cat", video2.video_id, "cat", 0.9, 200, 300)

        # Search for dog from video1
        r1 = global_jump_service.jump_next(
            kind="object",
            from_video_id=video1.video_id,
            from_ms=150,
            label="dog",
        )
        assert len(r1) == 1
        assert r1[0].video_id == "video_2"
        assert r1[0].artifact_id == "v2_dog"

        # Change filter to cat from same position
        r2 = global_jump_service.jump_next(
            kind="object",
            from_video_id=video1.video_id,
            from_ms=150,
            label="cat",
        )
        assert len(r2) == 1
        assert r2[0].video_id == "video_1"
        assert r2[0].artifact_id == "v1_cat"

    def test_prev_direction_filter_independence(self, session, global_jump_service):
        """Test filter independence works for prev direction too.

        Validates: Requirements 12.1, 12.2
        """
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        # Create objects
        create_object_label(session, "obj_dog_1", video.video_id, "dog", 0.9, 100, 200)
        create_object_label(session, "obj_cat_1", video.video_id, "cat", 0.9, 200, 300)
        create_object_label(session, "obj_dog_2", video.video_id, "dog", 0.9, 400, 500)
        create_object_label(session, "obj_cat_2", video.video_id, "cat", 0.9, 500, 600)

        # Search prev for dog from position 600
        r1 = global_jump_service.jump_prev(
            kind="object",
            from_video_id=video.video_id,
            from_ms=600,
            label="dog",
        )
        assert len(r1) == 1
        assert r1[0].artifact_id == "obj_dog_2"

        # Change filter to cat from same position
        r2 = global_jump_service.jump_prev(
            kind="object",
            from_video_id=video.video_id,
            from_ms=600,
            label="cat",
        )
        assert len(r2) == 1
        assert r2[0].artifact_id == "obj_cat_2"

        # Back to dog - should return same result
        r3 = global_jump_service.jump_prev(
            kind="object",
            from_video_id=video.video_id,
            from_ms=600,
            label="dog",
        )
        assert len(r3) == 1
        assert r3[0].artifact_id == "obj_dog_2"

    def test_service_has_no_query_state(self, session, global_jump_service):
        """Verify that the service doesn't store any query state.

        This test verifies the stateless design of GlobalJumpService.
        Validates: Requirements 12.1, 12.2, 12.3, 12.4
        """
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        create_object_label(session, "obj_1", video.video_id, "dog", 0.9, 100, 200)

        # Verify service only has session and artifact_repo attributes
        # No query state should be stored
        # The service should only have methods and the two injected dependencies
        assert "session" in dir(global_jump_service)
        assert "artifact_repo" in dir(global_jump_service)

        # Verify no state-related attributes exist
        state_related_attrs = [
            "last_query",
            "last_filter",
            "last_label",
            "last_kind",
            "query_cache",
            "filter_state",
            "current_position",
        ]
        for attr in state_related_attrs:
            assert not hasattr(
                global_jump_service, attr
            ), f"Service should not have {attr} attribute"


class TestResultChaining:
    """Tests for result chaining capability.

    Verifies that using a result's video_id and end_ms as the next starting
    point works correctly. Results should be chronologically after the
    previous result.

    Property 17: Result Chaining
    Validates: Requirements 13.5, 14.2, 14.3
    """

    def test_result_chaining_within_same_video(self, session, global_jump_service):
        """Test chaining results within the same video.

        When using result.end_ms as the next from_ms, the next result
        should be chronologically after the previous result.

        Validates: Requirements 13.5
        """
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        # Create objects at sequential timestamps
        create_object_label(session, "obj_1", video.video_id, "dog", 0.9, 100, 200)
        create_object_label(session, "obj_2", video.video_id, "dog", 0.9, 300, 400)
        create_object_label(session, "obj_3", video.video_id, "dog", 0.9, 500, 600)
        create_object_label(session, "obj_4", video.video_id, "dog", 0.9, 700, 800)

        # First query: get first result
        result1 = global_jump_service.jump_next(
            kind="object",
            from_video_id=video.video_id,
            from_ms=0,
            label="dog",
        )
        assert len(result1) == 1
        assert result1[0].artifact_id == "obj_1"
        assert result1[0].jump_to.start_ms == 100
        assert result1[0].jump_to.end_ms == 200

        # Chain: use result1's end_ms as next from_ms
        result2 = global_jump_service.jump_next(
            kind="object",
            from_video_id=result1[0].video_id,
            from_ms=result1[0].jump_to.end_ms,
            label="dog",
        )
        assert len(result2) == 1
        assert result2[0].artifact_id == "obj_2"
        assert result2[0].jump_to.start_ms == 300
        # Verify result2 is chronologically after result1
        assert result2[0].jump_to.start_ms > result1[0].jump_to.end_ms

        # Chain again: use result2's end_ms as next from_ms
        result3 = global_jump_service.jump_next(
            kind="object",
            from_video_id=result2[0].video_id,
            from_ms=result2[0].jump_to.end_ms,
            label="dog",
        )
        assert len(result3) == 1
        assert result3[0].artifact_id == "obj_3"
        assert result3[0].jump_to.start_ms == 500
        # Verify result3 is chronologically after result2
        assert result3[0].jump_to.start_ms > result2[0].jump_to.end_ms

        # Chain once more
        result4 = global_jump_service.jump_next(
            kind="object",
            from_video_id=result3[0].video_id,
            from_ms=result3[0].jump_to.end_ms,
            label="dog",
        )
        assert len(result4) == 1
        assert result4[0].artifact_id == "obj_4"
        assert result4[0].jump_to.start_ms > result3[0].jump_to.end_ms

    def test_result_chaining_across_videos(self, session, global_jump_service):
        """Test chaining results across multiple videos.

        When the current video has no more results, chaining should
        continue to the next video in the global timeline.

        Validates: Requirements 14.2, 14.3
        """
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )
        video3 = create_test_video(
            session, "video_3", "video3.mp4", datetime(2025, 1, 3, 12, 0, 0)
        )

        # Create objects in each video
        create_object_label(session, "v1_obj_1", video1.video_id, "cat", 0.9, 100, 200)
        create_object_label(session, "v1_obj_2", video1.video_id, "cat", 0.9, 500, 600)
        create_object_label(session, "v2_obj_1", video2.video_id, "cat", 0.9, 100, 200)
        create_object_label(session, "v3_obj_1", video3.video_id, "cat", 0.9, 100, 200)

        # Start from video1
        result1 = global_jump_service.jump_next(
            kind="object",
            from_video_id=video1.video_id,
            from_ms=0,
            label="cat",
        )
        assert result1[0].video_id == "video_1"
        assert result1[0].artifact_id == "v1_obj_1"

        # Chain to next result in video1
        result2 = global_jump_service.jump_next(
            kind="object",
            from_video_id=result1[0].video_id,
            from_ms=result1[0].jump_to.end_ms,
            label="cat",
        )
        assert result2[0].video_id == "video_1"
        assert result2[0].artifact_id == "v1_obj_2"

        # Chain to video2 (no more results in video1 after end_ms=600)
        result3 = global_jump_service.jump_next(
            kind="object",
            from_video_id=result2[0].video_id,
            from_ms=result2[0].jump_to.end_ms,
            label="cat",
        )
        assert result3[0].video_id == "video_2"
        assert result3[0].artifact_id == "v2_obj_1"

        # Chain to video3
        result4 = global_jump_service.jump_next(
            kind="object",
            from_video_id=result3[0].video_id,
            from_ms=result3[0].jump_to.end_ms,
            label="cat",
        )
        assert result4[0].video_id == "video_3"
        assert result4[0].artifact_id == "v3_obj_1"

    def test_result_chaining_no_more_results(self, session, global_jump_service):
        """Test chaining when no more results exist.

        Validates: Requirements 13.5
        """
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        # Create only one object
        create_object_label(session, "obj_1", video.video_id, "dog", 0.9, 100, 200)

        # Get first result
        result1 = global_jump_service.jump_next(
            kind="object",
            from_video_id=video.video_id,
            from_ms=0,
            label="dog",
        )
        assert len(result1) == 1
        assert result1[0].artifact_id == "obj_1"

        # Chain: should return empty list (no more results)
        result2 = global_jump_service.jump_next(
            kind="object",
            from_video_id=result1[0].video_id,
            from_ms=result1[0].jump_to.end_ms,
            label="dog",
        )
        assert len(result2) == 0

    def test_result_chaining_with_overlapping_artifacts(
        self, session, global_jump_service
    ):
        """Test chaining with overlapping artifact time ranges.

        When artifacts overlap, using end_ms should skip to the next
        artifact that starts after end_ms.

        Validates: Requirements 13.5
        """
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        # Create overlapping objects
        create_object_label(session, "obj_1", video.video_id, "dog", 0.9, 100, 300)
        create_object_label(
            session, "obj_2", video.video_id, "dog", 0.9, 200, 400
        )  # Overlaps with obj_1
        create_object_label(session, "obj_3", video.video_id, "dog", 0.9, 500, 600)

        # Get first result
        result1 = global_jump_service.jump_next(
            kind="object",
            from_video_id=video.video_id,
            from_ms=0,
            label="dog",
        )
        assert result1[0].artifact_id == "obj_1"
        assert result1[0].jump_to.end_ms == 300

        # Chain using end_ms=300 should skip obj_2 (starts at 200 < 300)
        # and return obj_3 (starts at 500 > 300)
        result2 = global_jump_service.jump_next(
            kind="object",
            from_video_id=result1[0].video_id,
            from_ms=result1[0].jump_to.end_ms,
            label="dog",
        )
        assert len(result2) == 1
        assert result2[0].artifact_id == "obj_3"
        assert result2[0].jump_to.start_ms == 500

    def test_result_chaining_continuous_navigation(self, session, global_jump_service):
        """Test continuous navigation through multiple results using chaining.

        Simulates a user clicking "next" repeatedly to navigate through
        all occurrences of an object.

        Validates: Requirements 13.5, 14.2, 14.3
        """
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        # Create multiple objects across videos
        create_object_label(session, "obj_1", video1.video_id, "bird", 0.9, 100, 200)
        create_object_label(session, "obj_2", video1.video_id, "bird", 0.9, 400, 500)
        create_object_label(session, "obj_3", video1.video_id, "bird", 0.9, 800, 900)
        create_object_label(session, "obj_4", video2.video_id, "bird", 0.9, 100, 200)
        create_object_label(session, "obj_5", video2.video_id, "bird", 0.9, 500, 600)

        # Simulate continuous navigation
        current_video_id = video1.video_id
        current_ms = 0
        visited_artifacts = []

        for _ in range(10):  # Max iterations to prevent infinite loop
            results = global_jump_service.jump_next(
                kind="object",
                from_video_id=current_video_id,
                from_ms=current_ms,
                label="bird",
            )

            if not results:
                break

            result = results[0]
            visited_artifacts.append(result.artifact_id)

            # Chain to next position
            current_video_id = result.video_id
            current_ms = result.jump_to.end_ms

        # Should have visited all 5 artifacts in order
        assert visited_artifacts == ["obj_1", "obj_2", "obj_3", "obj_4", "obj_5"]

    def test_result_chaining_prev_direction(self, session, global_jump_service):
        """Test result chaining in the prev direction.

        When navigating backward, using start_ms as from_ms should
        return the previous result.

        Validates: Requirements 13.5
        """
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        # Create objects at sequential timestamps
        create_object_label(session, "obj_1", video.video_id, "dog", 0.9, 100, 200)
        create_object_label(session, "obj_2", video.video_id, "dog", 0.9, 300, 400)
        create_object_label(session, "obj_3", video.video_id, "dog", 0.9, 500, 600)

        # Start from end of video
        result1 = global_jump_service.jump_prev(
            kind="object",
            from_video_id=video.video_id,
            from_ms=1000,
            label="dog",
        )
        assert result1[0].artifact_id == "obj_3"

        # Chain backward using start_ms
        result2 = global_jump_service.jump_prev(
            kind="object",
            from_video_id=result1[0].video_id,
            from_ms=result1[0].jump_to.start_ms,
            label="dog",
        )
        assert result2[0].artifact_id == "obj_2"
        assert result2[0].jump_to.start_ms < result1[0].jump_to.start_ms

        # Chain backward again
        result3 = global_jump_service.jump_prev(
            kind="object",
            from_video_id=result2[0].video_id,
            from_ms=result2[0].jump_to.start_ms,
            label="dog",
        )
        assert result3[0].artifact_id == "obj_1"
        assert result3[0].jump_to.start_ms < result2[0].jump_to.start_ms

    def test_result_chaining_preserves_chronological_order(
        self, session, global_jump_service
    ):
        """Test that chained results maintain strict chronological order.

        Each subsequent result must be strictly after the previous one
        in the global timeline.

        Validates: Requirements 13.5, 14.2, 14.3
        """
        # Create videos with specific timestamps
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 10, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video3 = create_test_video(
            session, "video_3", "video3.mp4", datetime(2025, 1, 1, 14, 0, 0)
        )

        # Create objects
        create_object_label(session, "obj_1", video1.video_id, "car", 0.9, 1000, 1100)
        create_object_label(session, "obj_2", video2.video_id, "car", 0.9, 500, 600)
        create_object_label(session, "obj_3", video3.video_id, "car", 0.9, 200, 300)

        # Navigate through all results
        results = []
        current_video_id = video1.video_id
        current_ms = 0

        for _ in range(5):
            r = global_jump_service.jump_next(
                kind="object",
                from_video_id=current_video_id,
                from_ms=current_ms,
                label="car",
            )
            if not r:
                break
            results.append(r[0])
            current_video_id = r[0].video_id
            current_ms = r[0].jump_to.end_ms

        # Verify chronological order
        assert len(results) == 3
        assert results[0].video_id == "video_1"
        assert results[1].video_id == "video_2"
        assert results[2].video_id == "video_3"

        # Verify file_created_at ordering
        for i in range(len(results) - 1):
            current = results[i]
            next_result = results[i + 1]
            # Next result should be in a video with same or later file_created_at
            if current.file_created_at and next_result.file_created_at:
                assert next_result.file_created_at >= current.file_created_at


class TestCrossVideoNavigationCorrectness:
    """Tests for cross-video navigation correctness.

    Property 18: Cross-Video Navigation
    For any global jump query that returns a result from a different video
    than from_video_id, that result should be the first matching artifact
    in the next/previous video in the global timeline (based on direction).

    Validates: Requirements 14.1, 14.5
    """

    def test_next_returns_first_artifact_in_next_video(
        self, session, global_jump_service
    ):
        """Test 'next' returns the first matching artifact in the next video.

        When navigating to a different video, the result should be the first
        (earliest start_ms) matching artifact in that video, not any arbitrary
        match.

        Validates: Requirements 14.1, 14.5
        """
        # Create videos in chronological order
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 10, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 10, 0, 0)
        )

        # Create objects in video1
        create_object_label(session, "v1_obj_1", video1.video_id, "dog", 0.9, 100, 200)

        # Create multiple objects in video2 at different timestamps
        # The first one (earliest start_ms) should be returned
        create_object_label(
            session, "v2_obj_3", video2.video_id, "dog", 0.9, 3000, 3100
        )  # Latest
        create_object_label(
            session, "v2_obj_1", video2.video_id, "dog", 0.9, 500, 600
        )  # First (earliest)
        create_object_label(
            session, "v2_obj_2", video2.video_id, "dog", 0.9, 1500, 1600
        )  # Middle

        # Search from end of video1 - should get first artifact in video2
        results = global_jump_service.jump_next(
            kind="object",
            from_video_id=video1.video_id,
            from_ms=5000,  # After all objects in video1
            label="dog",
        )

        assert len(results) == 1
        assert results[0].video_id == "video_2"
        # Should be the first artifact (earliest start_ms) in video2
        assert results[0].artifact_id == "v2_obj_1"
        assert results[0].jump_to.start_ms == 500

    def test_prev_returns_last_artifact_in_previous_video(
        self, session, global_jump_service
    ):
        """Test 'prev' returns the last matching artifact in the previous video.

        When navigating backward to a different video, the result should be the
        last (latest start_ms) matching artifact in that video.

        Validates: Requirements 14.1, 14.5
        """
        # Create videos in chronological order
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 10, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 10, 0, 0)
        )

        # Create multiple objects in video1 at different timestamps
        # The last one (latest start_ms) should be returned when going backward
        create_object_label(
            session, "v1_obj_1", video1.video_id, "cat", 0.9, 100, 200
        )  # First
        create_object_label(
            session, "v1_obj_2", video1.video_id, "cat", 0.9, 1000, 1100
        )  # Middle
        create_object_label(
            session, "v1_obj_3", video1.video_id, "cat", 0.9, 2000, 2100
        )  # Last (latest)

        # Create object in video2
        create_object_label(session, "v2_obj_1", video2.video_id, "cat", 0.9, 500, 600)

        # Search from beginning of video2 - should get last artifact in video1
        results = global_jump_service.jump_prev(
            kind="object",
            from_video_id=video2.video_id,
            from_ms=0,  # Before all objects in video2
            label="cat",
        )

        assert len(results) == 1
        assert results[0].video_id == "video_1"
        # Should be the last artifact (latest start_ms) in video1
        assert results[0].artifact_id == "v1_obj_3"
        assert results[0].jump_to.start_ms == 2000

    def test_cross_video_with_multiple_videos_different_orders(
        self, session, global_jump_service
    ):
        """Test cross-video navigation with videos in different chronological orders.

        Videos are created in non-chronological order to verify that the service
        correctly orders by file_created_at, not by insertion order.

        Validates: Requirements 14.1, 14.5
        """
        # Create videos in non-chronological order (by insertion)
        video3 = create_test_video(
            session, "video_c", "video_c.mp4", datetime(2025, 1, 3, 10, 0, 0)
        )
        video1 = create_test_video(
            session, "video_a", "video_a.mp4", datetime(2025, 1, 1, 10, 0, 0)
        )
        video2 = create_test_video(
            session, "video_b", "video_b.mp4", datetime(2025, 1, 2, 10, 0, 0)
        )

        # Create objects in each video
        create_object_label(
            session, "v3_obj", video3.video_id, "bird", 0.9, 100, 200
        )  # Jan 3
        create_object_label(
            session, "v1_obj", video1.video_id, "bird", 0.9, 100, 200
        )  # Jan 1
        create_object_label(
            session, "v2_obj", video2.video_id, "bird", 0.9, 100, 200
        )  # Jan 2

        # Navigate from video1 (Jan 1) - should go to video2 (Jan 2), not video3
        results = global_jump_service.jump_next(
            kind="object",
            from_video_id=video1.video_id,
            from_ms=500,  # After the object in video1
            label="bird",
        )

        assert len(results) == 1
        assert results[0].video_id == "video_b"  # Jan 2, not Jan 3
        assert results[0].artifact_id == "v2_obj"

        # Continue to video3
        results2 = global_jump_service.jump_next(
            kind="object",
            from_video_id=results[0].video_id,
            from_ms=results[0].jump_to.end_ms,
            label="bird",
        )

        assert len(results2) == 1
        assert results2[0].video_id == "video_c"  # Jan 3
        assert results2[0].artifact_id == "v3_obj"

    def test_cross_video_video_id_matches_expected(self, session, global_jump_service):
        """Test that video_id in results matches the expected video.

        Validates: Requirements 14.1, 14.5
        """
        # Create videos with distinct IDs
        video_alpha = create_test_video(
            session, "alpha_video", "alpha.mp4", datetime(2025, 1, 1, 10, 0, 0)
        )
        video_beta = create_test_video(
            session, "beta_video", "beta.mp4", datetime(2025, 1, 2, 10, 0, 0)
        )
        video_gamma = create_test_video(
            session, "gamma_video", "gamma.mp4", datetime(2025, 1, 3, 10, 0, 0)
        )

        # Create objects
        create_object_label(
            session, "alpha_obj", video_alpha.video_id, "car", 0.9, 100, 200
        )
        create_object_label(
            session, "beta_obj", video_beta.video_id, "car", 0.9, 100, 200
        )
        create_object_label(
            session, "gamma_obj", video_gamma.video_id, "car", 0.9, 100, 200
        )

        # Navigate forward and verify video_id at each step
        result1 = global_jump_service.jump_next(
            kind="object",
            from_video_id=video_alpha.video_id,
            from_ms=500,
            label="car",
        )
        assert result1[0].video_id == "beta_video"
        assert result1[0].video_filename == "beta.mp4"

        result2 = global_jump_service.jump_next(
            kind="object",
            from_video_id=result1[0].video_id,
            from_ms=result1[0].jump_to.end_ms,
            label="car",
        )
        assert result2[0].video_id == "gamma_video"
        assert result2[0].video_filename == "gamma.mp4"

        # Navigate backward and verify
        result3 = global_jump_service.jump_prev(
            kind="object",
            from_video_id=video_gamma.video_id,
            from_ms=0,
            label="car",
        )
        assert result3[0].video_id == "beta_video"

        result4 = global_jump_service.jump_prev(
            kind="object",
            from_video_id=result3[0].video_id,
            from_ms=0,
            label="car",
        )
        assert result4[0].video_id == "alpha_video"

    def test_cross_video_maintains_filter_across_boundaries(
        self, session, global_jump_service
    ):
        """Test that search filter is maintained when crossing video boundaries.

        When navigating to a different video, only artifacts matching the
        original filter should be returned.

        Validates: Requirements 14.5
        """
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 10, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 10, 0, 0)
        )

        # Create objects in video1
        create_object_label(session, "v1_dog", video1.video_id, "dog", 0.9, 100, 200)

        # Create objects in video2 - mix of dog and cat
        create_object_label(
            session, "v2_cat", video2.video_id, "cat", 0.9, 100, 200
        )  # First by time
        create_object_label(
            session, "v2_dog", video2.video_id, "dog", 0.9, 500, 600
        )  # Second by time

        # Search for "dog" from end of video1
        results = global_jump_service.jump_next(
            kind="object",
            from_video_id=video1.video_id,
            from_ms=500,
            label="dog",
        )

        assert len(results) == 1
        assert results[0].video_id == "video_2"
        # Should return the dog, not the cat (even though cat is earlier)
        assert results[0].artifact_id == "v2_dog"
        assert results[0].preview["label"] == "dog"

    def test_cross_video_with_same_file_created_at(self, session, global_jump_service):
        """Test cross-video navigation when videos have the same file_created_at.

        When videos have the same file_created_at, ordering should fall back
        to video_id for deterministic results.

        Validates: Requirements 14.1, 14.5
        """
        same_time = datetime(2025, 1, 1, 12, 0, 0)

        # Create videos with same file_created_at but different video_ids
        video_a = create_test_video(session, "aaa_video", "aaa.mp4", same_time)
        video_b = create_test_video(session, "bbb_video", "bbb.mp4", same_time)
        video_c = create_test_video(session, "ccc_video", "ccc.mp4", same_time)

        # Create objects in each video
        create_object_label(session, "a_obj", video_a.video_id, "fish", 0.9, 100, 200)
        create_object_label(session, "b_obj", video_b.video_id, "fish", 0.9, 100, 200)
        create_object_label(session, "c_obj", video_c.video_id, "fish", 0.9, 100, 200)

        # Navigate from video_a - should go to video_b (alphabetically next)
        results = global_jump_service.jump_next(
            kind="object",
            from_video_id=video_a.video_id,
            from_ms=500,
            label="fish",
        )

        assert len(results) == 1
        assert results[0].video_id == "bbb_video"

        # Continue to video_c
        results2 = global_jump_service.jump_next(
            kind="object",
            from_video_id=results[0].video_id,
            from_ms=results[0].jump_to.end_ms,
            label="fish",
        )

        assert len(results2) == 1
        assert results2[0].video_id == "ccc_video"

    def test_cross_video_returns_first_artifact_with_multiple_matches(
        self, session, global_jump_service
    ):
        """Test that with multiple matches in next video, the first one is returned.

        This is a more comprehensive test with many artifacts to ensure
        the ordering is correct.

        Validates: Requirements 14.1, 14.5
        """
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 10, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 10, 0, 0)
        )

        # Create one object in video1
        create_object_label(session, "v1_obj", video1.video_id, "person", 0.9, 100, 200)

        # Create many objects in video2 at various timestamps (inserted in random order)
        timestamps = [5000, 1000, 3000, 500, 2000, 4000, 100]  # 100 is the earliest
        for i, ts in enumerate(timestamps):
            create_object_label(
                session,
                f"v2_obj_{ts}",
                video2.video_id,
                "person",
                0.9,
                ts,
                ts + 100,
            )

        # Search from end of video1
        results = global_jump_service.jump_next(
            kind="object",
            from_video_id=video1.video_id,
            from_ms=500,
            label="person",
        )

        assert len(results) == 1
        assert results[0].video_id == "video_2"
        # Should return the artifact with the earliest start_ms (100)
        assert results[0].artifact_id == "v2_obj_100"
        assert results[0].jump_to.start_ms == 100

    def test_cross_video_prev_returns_last_artifact_with_multiple_matches(
        self, session, global_jump_service
    ):
        """Test backward navigation returns the last artifact in the previous video.

        Validates: Requirements 14.1, 14.5
        """
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 10, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 10, 0, 0)
        )

        # Create many objects in video1 at various timestamps
        timestamps = [100, 500, 1000, 2000, 3000, 4000, 5000]  # 5000 is the latest
        for ts in timestamps:
            create_object_label(
                session,
                f"v1_obj_{ts}",
                video1.video_id,
                "tree",
                0.9,
                ts,
                ts + 100,
            )

        # Create one object in video2
        create_object_label(session, "v2_obj", video2.video_id, "tree", 0.9, 100, 200)

        # Search backward from beginning of video2
        results = global_jump_service.jump_prev(
            kind="object",
            from_video_id=video2.video_id,
            from_ms=0,
            label="tree",
        )

        assert len(results) == 1
        assert results[0].video_id == "video_1"
        # Should return the artifact with the latest start_ms (5000)
        assert results[0].artifact_id == "v1_obj_5000"
        assert results[0].jump_to.start_ms == 5000


class TestLocationTextSearch:
    """Tests for location text search functionality.

    Validates Requirements:
    - 7.1: WHEN kind is location and a query parameter is provided,
           THE Global_Jump_Service SHALL search across country, state, and city fields
    - 7.2: THE location text search SHALL use case-insensitive partial matching
    - 7.3: THE location text search SHALL match if the query appears in any of:
           country, state, or city
    - 7.4: WHEN both query and geo_bounds are provided for location search,
           THE Global_Jump_Service SHALL apply both filters (AND logic)
    """

    @pytest.fixture
    def setup_video_locations(self, session):
        """Set up video_locations table for testing."""
        session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS video_locations (
                    id INTEGER PRIMARY KEY,
                    video_id TEXT NOT NULL UNIQUE,
                    artifact_id TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    altitude REAL,
                    country TEXT,
                    state TEXT,
                    city TEXT
                )
                """
            )
        )
        session.commit()
        yield
        session.execute(text("DROP TABLE IF EXISTS video_locations"))
        session.commit()

    def _insert_location(
        self,
        session,
        video_id: str,
        artifact_id: str,
        latitude: float,
        longitude: float,
        altitude: float | None = None,
        country: str | None = None,
        state: str | None = None,
        city: str | None = None,
    ):
        """Helper to insert location into video_locations table."""
        session.execute(
            text(
                """
                INSERT INTO video_locations
                    (video_id, artifact_id, latitude, longitude, altitude,
                     country, state, city)
                VALUES (:video_id, :artifact_id, :latitude, :longitude, :altitude,
                        :country, :state, :city)
                """
            ),
            {
                "video_id": video_id,
                "artifact_id": artifact_id,
                "latitude": latitude,
                "longitude": longitude,
                "altitude": altitude,
                "country": country,
                "state": state,
                "city": city,
            },
        )
        session.commit()

    def test_search_matching_country_field(
        self, session, global_jump_service, setup_video_locations
    ):
        """Test that query matches against country field.

        Validates: Requirements 7.1, 7.3
        """
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )
        video3 = create_test_video(
            session, "video_3", "video3.mp4", datetime(2025, 1, 3, 12, 0, 0)
        )

        self._insert_location(
            session,
            video2.video_id,
            "loc_2",
            35.6762,
            139.6503,
            country="Japan",
            state="Tokyo",
            city="Shibuya",
        )
        self._insert_location(
            session,
            video3.video_id,
            "loc_3",
            40.7128,
            -74.0060,
            country="United States",
            state="New York",
            city="Manhattan",
        )

        results = global_jump_service._search_locations_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=0,
            query="Japan",
        )

        assert len(results) == 1
        assert results[0].video_id == "video_2"
        assert results[0].preview["country"] == "Japan"

    def test_search_matching_state_field(
        self, session, global_jump_service, setup_video_locations
    ):
        """Test that query matches against state field.

        Validates: Requirements 7.1, 7.3
        """
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )
        video3 = create_test_video(
            session, "video_3", "video3.mp4", datetime(2025, 1, 3, 12, 0, 0)
        )

        self._insert_location(
            session,
            video2.video_id,
            "loc_2",
            34.0522,
            -118.2437,
            country="United States",
            state="California",
            city="Los Angeles",
        )
        self._insert_location(
            session,
            video3.video_id,
            "loc_3",
            40.7128,
            -74.0060,
            country="United States",
            state="New York",
            city="Manhattan",
        )

        results = global_jump_service._search_locations_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=0,
            query="California",
        )

        assert len(results) == 1
        assert results[0].video_id == "video_2"
        assert results[0].preview["state"] == "California"

    def test_search_matching_city_field(
        self, session, global_jump_service, setup_video_locations
    ):
        """Test that query matches against city field.

        Validates: Requirements 7.1, 7.3
        """
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )
        video3 = create_test_video(
            session, "video_3", "video3.mp4", datetime(2025, 1, 3, 12, 0, 0)
        )

        self._insert_location(
            session,
            video2.video_id,
            "loc_2",
            35.6762,
            139.6503,
            country="Japan",
            state="Tokyo",
            city="Shibuya",
        )
        self._insert_location(
            session,
            video3.video_id,
            "loc_3",
            51.5074,
            -0.1278,
            country="United Kingdom",
            state="England",
            city="London",
        )

        results = global_jump_service._search_locations_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=0,
            query="London",
        )

        assert len(results) == 1
        assert results[0].video_id == "video_3"
        assert results[0].preview["city"] == "London"

    def test_case_insensitive_matching(
        self, session, global_jump_service, setup_video_locations
    ):
        """Test that query matching is case-insensitive.

        Validates: Requirements 7.2
        """
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        self._insert_location(
            session,
            video2.video_id,
            "loc_2",
            35.6762,
            139.6503,
            country="Japan",
            state="Tokyo",
            city="Shibuya",
        )

        # Test lowercase query matching uppercase data
        results_lower = global_jump_service._search_locations_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=0,
            query="japan",
        )
        assert len(results_lower) == 1
        assert results_lower[0].preview["country"] == "Japan"

        # Test uppercase query matching mixed case data
        results_upper = global_jump_service._search_locations_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=0,
            query="TOKYO",
        )
        assert len(results_upper) == 1
        assert results_upper[0].preview["state"] == "Tokyo"

        # Test mixed case query
        results_mixed = global_jump_service._search_locations_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=0,
            query="ShIbUyA",
        )
        assert len(results_mixed) == 1
        assert results_mixed[0].preview["city"] == "Shibuya"

    def test_partial_matching(
        self, session, global_jump_service, setup_video_locations
    ):
        """Test that query uses partial matching (substring search).

        Validates: Requirements 7.2
        """
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        self._insert_location(
            session,
            video2.video_id,
            "loc_2",
            40.7128,
            -74.0060,
            country="United States",
            state="New York",
            city="Manhattan",
        )

        # Test partial match on country
        results_country = global_jump_service._search_locations_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=0,
            query="United",
        )
        assert len(results_country) == 1
        assert results_country[0].preview["country"] == "United States"

        # Test partial match on state
        results_state = global_jump_service._search_locations_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=0,
            query="York",
        )
        assert len(results_state) == 1
        assert results_state[0].preview["state"] == "New York"

        # Test partial match on city
        results_city = global_jump_service._search_locations_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=0,
            query="Man",
        )
        assert len(results_city) == 1
        assert results_city[0].preview["city"] == "Manhattan"

    def test_combined_query_and_geo_bounds_filtering(
        self, session, global_jump_service, setup_video_locations
    ):
        """Test that both query and geo_bounds filters are applied (AND logic).

        Validates: Requirements 7.4
        """
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )
        video3 = create_test_video(
            session, "video_3", "video3.mp4", datetime(2025, 1, 3, 12, 0, 0)
        )
        video4 = create_test_video(
            session, "video_4", "video4.mp4", datetime(2025, 1, 4, 12, 0, 0)
        )

        # Tokyo, Japan (lat ~35.6, lon ~139.6)
        self._insert_location(
            session,
            video2.video_id,
            "loc_2",
            35.6762,
            139.6503,
            country="Japan",
            state="Tokyo",
            city="Shibuya",
        )
        # New York, USA (lat ~40.7, lon ~-74.0) - matches "New" but outside bounds
        self._insert_location(
            session,
            video3.video_id,
            "loc_3",
            40.7128,
            -74.0060,
            country="United States",
            state="New York",
            city="Manhattan",
        )
        # Osaka, Japan (lat ~34.6, lon ~135.5) - matches "Japan" and inside bounds
        self._insert_location(
            session,
            video4.video_id,
            "loc_4",
            34.6937,
            135.5023,
            country="Japan",
            state="Osaka",
            city="Osaka",
        )

        # Search for "Japan" within bounds that include Tokyo and Osaka
        # but exclude New York
        geo_bounds = {
            "min_lat": 30.0,
            "max_lat": 40.0,
            "min_lon": 130.0,
            "max_lon": 145.0,
        }

        results = global_jump_service._search_locations_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=0,
            query="Japan",
            geo_bounds=geo_bounds,
            limit=10,
        )

        # Should find both Tokyo and Osaka (both match "Japan" and are in bounds)
        assert len(results) == 2
        video_ids = [r.video_id for r in results]
        assert "video_2" in video_ids  # Tokyo
        assert "video_4" in video_ids  # Osaka
        assert "video_3" not in video_ids  # New York excluded

    def test_query_matches_any_field(
        self, session, global_jump_service, setup_video_locations
    ):
        """Test that query matches if it appears in ANY of country, state, or city.

        Validates: Requirements 7.3
        """
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )
        video3 = create_test_video(
            session, "video_3", "video3.mp4", datetime(2025, 1, 3, 12, 0, 0)
        )
        video4 = create_test_video(
            session, "video_4", "video4.mp4", datetime(2025, 1, 4, 12, 0, 0)
        )

        # "New" appears in country
        self._insert_location(
            session,
            video2.video_id,
            "loc_2",
            0.0,
            0.0,
            country="New Zealand",
            state="Auckland",
            city="Auckland",
        )
        # "New" appears in state
        self._insert_location(
            session,
            video3.video_id,
            "loc_3",
            0.0,
            0.0,
            country="United States",
            state="New York",
            city="Buffalo",
        )
        # "New" appears in city
        self._insert_location(
            session,
            video4.video_id,
            "loc_4",
            0.0,
            0.0,
            country="United States",
            state="Louisiana",
            city="New Orleans",
        )

        results = global_jump_service._search_locations_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=0,
            query="New",
            limit=10,
        )

        # Should find all three locations
        assert len(results) == 3
        video_ids = [r.video_id for r in results]
        assert "video_2" in video_ids  # New Zealand (country)
        assert "video_3" in video_ids  # New York (state)
        assert "video_4" in video_ids  # New Orleans (city)

    def test_query_no_match_returns_empty(
        self, session, global_jump_service, setup_video_locations
    ):
        """Test that non-matching query returns empty results.

        Validates: Requirements 7.1
        """
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        self._insert_location(
            session,
            video2.video_id,
            "loc_2",
            35.6762,
            139.6503,
            country="Japan",
            state="Tokyo",
            city="Shibuya",
        )

        results = global_jump_service._search_locations_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=0,
            query="NonExistentPlace",
        )

        assert len(results) == 0

    def test_query_with_prev_direction(
        self, session, global_jump_service, setup_video_locations
    ):
        """Test that query works with prev direction.

        Validates: Requirements 7.1
        """
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )
        video3 = create_test_video(
            session, "video_3", "video3.mp4", datetime(2025, 1, 3, 12, 0, 0)
        )

        self._insert_location(
            session,
            video1.video_id,
            "loc_1",
            35.6762,
            139.6503,
            country="Japan",
            state="Tokyo",
            city="Shibuya",
        )
        self._insert_location(
            session,
            video2.video_id,
            "loc_2",
            40.7128,
            -74.0060,
            country="United States",
            state="New York",
            city="Manhattan",
        )

        results = global_jump_service._search_locations_global(
            direction="prev",
            from_video_id=video3.video_id,
            from_ms=0,
            query="Japan",
        )

        assert len(results) == 1
        assert results[0].video_id == "video_1"
        assert results[0].preview["country"] == "Japan"

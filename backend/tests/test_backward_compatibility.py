"""Backward compatibility tests for single-video jump endpoint.

This module verifies that the new global jump feature does not affect
the existing single-video jump functionality.

**Property 19: Backward Compatibility**
*For any* request to the existing GET /videos/{video_id}/jump endpoint,
the system should continue to return results scoped to that video only,
without being affected by the new global jump feature.

**Property 20: Global Jump Independence**
*For any* request to the new GET /jump/global endpoint, the system should
return results across all videos without affecting the behavior of the
existing single-video jump endpoint.

**Validates: Requirements 10.1, 10.2, 10.3, 10.4**
"""

import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, ObjectLabel
from src.database.models import Video as VideoEntity
from src.domain.artifacts import ArtifactEnvelope
from src.domain.schema_initialization import register_all_schemas
from src.domain.schema_registry import SchemaRegistry
from src.repositories.artifact_repository import SqlArtifactRepository
from src.repositories.selection_policy_manager import SelectionPolicyManager
from src.services.global_jump_service import GlobalJumpService
from src.services.jump_navigation_service import JumpNavigationService


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


@pytest.fixture(scope="session")
def schema_registry():
    """Create and initialize schema registry once for all tests."""
    register_all_schemas()
    return SchemaRegistry


@pytest.fixture
def artifact_repo(session, schema_registry):
    """Create artifact repository instance with mocked projection sync."""
    mock_projection_sync = MagicMock()
    mock_projection_sync.sync_artifact = MagicMock()
    return SqlArtifactRepository(session, schema_registry, mock_projection_sync)


@pytest.fixture
def policy_manager(session):
    """Create selection policy manager instance."""
    return SelectionPolicyManager(session)


@pytest.fixture
def single_video_jump_service(artifact_repo, policy_manager):
    """Create single-video jump navigation service instance."""
    return JumpNavigationService(artifact_repo, policy_manager)


@pytest.fixture
def global_jump_service(session):
    """Create global jump service instance."""
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


def create_object_artifact(
    artifact_id: str,
    asset_id: str,
    start_ms: int,
    end_ms: int,
    label: str,
    confidence: float = 0.9,
    run_id: str = "run_1",
) -> ArtifactEnvelope:
    """Helper to create object detection artifact."""
    payload = {
        "label": label,
        "confidence": confidence,
        "bounding_box": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4},
        "frame_number": 0,
    }
    return ArtifactEnvelope(
        artifact_id=artifact_id,
        asset_id=asset_id,
        artifact_type="object.detection",
        schema_version=1,
        span_start_ms=start_ms,
        span_end_ms=end_ms,
        payload_json=json.dumps(payload),
        producer="yolo",
        producer_version="8.0.0",
        model_profile="balanced",
        config_hash="xyz789",
        input_hash="uvw012",
        run_id=run_id,
        created_at=datetime.now(),
    )


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


class TestBackwardCompatibility:
    """Tests for backward compatibility of single-video jump endpoint.

    **Property 19: Backward Compatibility**
    **Validates: Requirements 10.1, 10.3**
    """

    def test_single_video_jump_still_works(
        self, session, single_video_jump_service, artifact_repo
    ):
        """Test that existing single-video jump endpoint still works.

        Requirement 10.1: THE existing GET /videos/{video_id}/jump endpoint
        SHALL remain unchanged and functional.
        """
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        # Create artifacts for the video
        artifact1 = create_object_artifact("obj_1", video.video_id, 0, 100, "dog", 0.9)
        artifact2 = create_object_artifact(
            "obj_2", video.video_id, 500, 600, "dog", 0.85
        )
        artifact3 = create_object_artifact(
            "obj_3", video.video_id, 1000, 1100, "dog", 0.95
        )

        artifact_repo.create(artifact1)
        artifact_repo.create(artifact2)
        artifact_repo.create(artifact3)

        # Test jump_next
        result = single_video_jump_service.jump_next(
            asset_id=video.video_id,
            artifact_type="object.detection",
            from_ms=200,
            label="dog",
        )

        assert result is not None
        assert result["jump_to"]["start_ms"] == 500
        assert result["jump_to"]["end_ms"] == 600
        assert "obj_2" in result["artifact_ids"]

    def test_single_video_jump_prev_still_works(
        self, session, single_video_jump_service, artifact_repo
    ):
        """Test that single-video jump_prev still works correctly."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        artifact1 = create_object_artifact("obj_1", video.video_id, 0, 100, "cat", 0.9)
        artifact2 = create_object_artifact(
            "obj_2", video.video_id, 500, 600, "cat", 0.85
        )
        artifact3 = create_object_artifact(
            "obj_3", video.video_id, 1000, 1100, "cat", 0.95
        )

        artifact_repo.create(artifact1)
        artifact_repo.create(artifact2)
        artifact_repo.create(artifact3)

        # Test jump_prev from 800ms - should find artifact2 (ends at 600ms < 800ms)
        # The service finds artifacts that END before from_ms
        result = single_video_jump_service.jump_prev(
            asset_id=video.video_id,
            artifact_type="object.detection",
            from_ms=800,
            label="cat",
        )

        assert result is not None
        # Should find artifact2 (500-600ms) as it's the latest artifact
        # that ends before 800ms
        assert result["jump_to"]["start_ms"] == 500
        assert result["jump_to"]["end_ms"] == 600
        assert "obj_2" in result["artifact_ids"]

    def test_single_video_jump_returns_results_scoped_to_video_only(
        self, session, single_video_jump_service, artifact_repo
    ):
        """Test that single-video jump returns results scoped to that video only.

        Requirement 10.3: WHEN a user uses the existing single-video jump endpoint
        THEN THE System SHALL continue to return results scoped to that video only.
        """
        # Create two videos with artifacts
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        # Create artifacts in both videos
        artifact1 = create_object_artifact("obj_1", video1.video_id, 0, 100, "dog", 0.9)
        artifact2 = create_object_artifact(
            "obj_2", video2.video_id, 0, 100, "dog", 0.95
        )

        artifact_repo.create(artifact1)
        artifact_repo.create(artifact2)

        # Jump from video1 - should NOT find artifacts from video2
        result = single_video_jump_service.jump_next(
            asset_id=video1.video_id,
            artifact_type="object.detection",
            from_ms=500,  # After all artifacts in video1
            label="dog",
        )

        # Should return None because there are no more artifacts in video1
        # (even though video2 has a matching artifact)
        assert result is None

    def test_single_video_jump_with_confidence_filter(
        self, session, single_video_jump_service, artifact_repo
    ):
        """Test that single-video jump confidence filtering still works."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        artifact1 = create_object_artifact("obj_1", video.video_id, 0, 100, "dog", 0.5)
        artifact2 = create_object_artifact(
            "obj_2", video.video_id, 500, 600, "dog", 0.7
        )
        artifact3 = create_object_artifact(
            "obj_3", video.video_id, 1000, 1100, "dog", 0.9
        )

        artifact_repo.create(artifact1)
        artifact_repo.create(artifact2)
        artifact_repo.create(artifact3)

        # Jump with min_confidence=0.8
        result = single_video_jump_service.jump_next(
            asset_id=video.video_id,
            artifact_type="object.detection",
            from_ms=0,
            label="dog",
            min_confidence=0.8,
        )

        assert result is not None
        assert result["jump_to"]["start_ms"] == 1000
        assert "obj_3" in result["artifact_ids"]


class TestGlobalJumpIndependence:
    """Tests for global jump independence from single-video jump.

    **Property 20: Global Jump Independence**
    **Validates: Requirements 10.2, 10.4**
    """

    def test_global_jump_returns_results_across_all_videos(
        self, session, global_jump_service
    ):
        """Test that global jump returns results across all videos.

        Requirement 10.2: THE new GET /jump/global endpoint SHALL be additive
        and not modify existing video jump behavior.
        """
        # Create multiple videos with different file_created_at
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )
        video3 = create_test_video(
            session, "video_3", "video3.mp4", datetime(2025, 1, 3, 12, 0, 0)
        )

        # Create object labels in projection table
        create_object_label(session, "obj_1", video1.video_id, "dog", 0.9, 0, 100)
        create_object_label(session, "obj_2", video2.video_id, "dog", 0.85, 0, 100)
        create_object_label(session, "obj_3", video3.video_id, "dog", 0.95, 0, 100)

        # Global jump from video1 should find artifacts in video2 and video3
        results = global_jump_service._search_objects_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=500,  # After all artifacts in video1
            label="dog",
            limit=10,
        )

        assert len(results) == 2
        assert results[0].video_id == "video_2"
        assert results[1].video_id == "video_3"

    def test_global_jump_does_not_affect_single_video_jump(
        self, session, single_video_jump_service, global_jump_service, artifact_repo
    ):
        """Test that using global jump doesn't affect single-video jump behavior.

        Requirement 10.4: WHEN a user uses the new global jump endpoint THEN
        THE System SHALL return results across all videos without affecting
        single-video jump functionality.
        """
        # Create videos
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        # Create artifacts for single-video jump service
        artifact1 = create_object_artifact("obj_1", video1.video_id, 0, 100, "cat", 0.9)
        artifact2 = create_object_artifact(
            "obj_2", video1.video_id, 500, 600, "cat", 0.85
        )
        artifact_repo.create(artifact1)
        artifact_repo.create(artifact2)

        # Create object labels for global jump service
        create_object_label(session, "obj_3", video1.video_id, "cat", 0.9, 0, 100)
        create_object_label(session, "obj_4", video2.video_id, "cat", 0.85, 0, 100)

        # First, use global jump
        global_results = global_jump_service._search_objects_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=500,
            label="cat",
        )

        # Global jump should find artifact in video2
        assert len(global_results) == 1
        assert global_results[0].video_id == "video_2"

        # Now use single-video jump - it should still work correctly
        # and return results scoped to video1 only
        single_result = single_video_jump_service.jump_next(
            asset_id=video1.video_id,
            artifact_type="object.detection",
            from_ms=200,
            label="cat",
        )

        # Single-video jump should find artifact in video1 only
        assert single_result is not None
        assert single_result["jump_to"]["start_ms"] == 500
        assert "obj_2" in single_result["artifact_ids"]

    def test_services_are_independent(
        self, session, single_video_jump_service, global_jump_service, artifact_repo
    ):
        """Test that single-video and global jump services are independent."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        # Create artifact for single-video jump
        artifact = create_object_artifact(
            "obj_1", video.video_id, 100, 200, "bird", 0.9
        )
        artifact_repo.create(artifact)

        # Create object label for global jump
        create_object_label(session, "obj_2", video.video_id, "bird", 0.9, 300, 400)

        # Single-video jump uses artifact repository
        single_result = single_video_jump_service.jump_next(
            asset_id=video.video_id,
            artifact_type="object.detection",
            from_ms=0,
            label="bird",
        )

        # Global jump uses projection tables
        global_results = global_jump_service._search_objects_global(
            direction="next",
            from_video_id=video.video_id,
            from_ms=0,
            label="bird",
        )

        # Both should work independently
        assert single_result is not None
        assert single_result["jump_to"]["start_ms"] == 100

        assert len(global_results) == 1
        assert global_results[0].jump_to.start_ms == 300


class TestConcurrentUsage:
    """Tests for concurrent usage of both jump endpoints."""

    def test_alternating_between_single_and_global_jump(
        self, session, single_video_jump_service, global_jump_service, artifact_repo
    ):
        """Test alternating between single-video and global jump."""
        video1 = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )
        video2 = create_test_video(
            session, "video_2", "video2.mp4", datetime(2025, 1, 2, 12, 0, 0)
        )

        # Create artifacts for single-video jump
        artifact1 = create_object_artifact(
            "obj_1", video1.video_id, 0, 100, "fish", 0.9
        )
        artifact2 = create_object_artifact(
            "obj_2", video1.video_id, 500, 600, "fish", 0.85
        )
        artifact_repo.create(artifact1)
        artifact_repo.create(artifact2)

        # Create object labels for global jump
        create_object_label(session, "obj_3", video1.video_id, "fish", 0.9, 0, 100)
        create_object_label(session, "obj_4", video1.video_id, "fish", 0.85, 500, 600)
        create_object_label(session, "obj_5", video2.video_id, "fish", 0.95, 0, 100)

        # Alternate between single and global jump
        # 1. Single-video jump - from 0ms should find first artifact at 0ms
        single_result1 = single_video_jump_service.jump_next(
            asset_id=video1.video_id,
            artifact_type="object.detection",
            from_ms=0,
            label="fish",
        )
        assert single_result1 is not None
        # jump_next finds artifacts starting AT or AFTER from_ms
        assert single_result1["jump_to"]["start_ms"] == 0

        # 2. Global jump - from 0ms should find first artifact at 500ms (after 0)
        global_result1 = global_jump_service._search_objects_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=0,
            label="fish",
        )
        assert len(global_result1) == 1
        # Global jump finds artifacts AFTER from_ms (strictly greater)
        assert global_result1[0].jump_to.start_ms == 500

        # 3. Single-video jump prev - from 1000ms should find artifact at 500ms
        single_result2 = single_video_jump_service.jump_prev(
            asset_id=video1.video_id,
            artifact_type="object.detection",
            from_ms=1000,
            label="fish",
        )
        assert single_result2 is not None
        assert single_result2["jump_to"]["start_ms"] == 500

        # 4. Global jump - from 600ms should find artifact in video2
        global_result2 = global_jump_service._search_objects_global(
            direction="next",
            from_video_id=video1.video_id,
            from_ms=600,
            label="fish",
        )
        assert len(global_result2) == 1
        assert global_result2[0].video_id == "video_2"

    def test_no_state_leakage_between_services(
        self, session, single_video_jump_service, global_jump_service, artifact_repo
    ):
        """Test that there's no state leakage between services."""
        video = create_test_video(
            session, "video_1", "video1.mp4", datetime(2025, 1, 1, 12, 0, 0)
        )

        # Create artifacts
        artifact = create_object_artifact(
            "obj_1", video.video_id, 100, 200, "elephant", 0.9
        )
        artifact_repo.create(artifact)
        create_object_label(session, "obj_2", video.video_id, "elephant", 0.9, 300, 400)

        # Use global jump multiple times
        for _ in range(3):
            global_jump_service._search_objects_global(
                direction="next",
                from_video_id=video.video_id,
                from_ms=0,
                label="elephant",
            )

        # Single-video jump should still work correctly
        result = single_video_jump_service.jump_next(
            asset_id=video.video_id,
            artifact_type="object.detection",
            from_ms=0,
            label="elephant",
        )

        assert result is not None
        assert result["jump_to"]["start_ms"] == 100

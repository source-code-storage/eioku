"""Tests for artifact search controller.

Tests for the artifact gallery search API endpoint and query building.

Requirements:
- 4.2: Accept kind, label, query, filename, min_confidence, limit, offset,
       group_by_video params
- 4.8: Filter by video filename (case-insensitive partial match)
- 4.9: group_by_video returns first artifact per video
- 4.10: group_by_video includes artifact_count
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.artifact_search_controller import (
    KIND_TO_ARTIFACT_TYPE,
    build_search_query,
)
from src.database.models import Artifact, Base
from src.database.models import Video as VideoEntity


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


def create_test_artifact(
    session,
    artifact_id: str,
    asset_id: str,
    artifact_type: str,
    span_start_ms: int,
    payload_json: dict,
) -> Artifact:
    """Helper to create a test artifact."""
    artifact = Artifact(
        artifact_id=artifact_id,
        asset_id=asset_id,
        artifact_type=artifact_type,
        schema_version=1,
        span_start_ms=span_start_ms,
        span_end_ms=span_start_ms + 100,
        payload_json=payload_json,
        producer="test",
        producer_version="1.0",
        model_profile="test",
        config_hash="abc123",
        input_hash="def456",
        run_id="run_1",
    )
    session.add(artifact)
    session.commit()
    return artifact


class TestKindToArtifactTypeMapping:
    """Tests for KIND_TO_ARTIFACT_TYPE mapping."""

    def test_object_maps_to_object_detection(self):
        """Test object kind maps correctly."""
        assert KIND_TO_ARTIFACT_TYPE["object"] == "object.detection"

    def test_face_maps_to_face_detection(self):
        """Test face kind maps correctly."""
        assert KIND_TO_ARTIFACT_TYPE["face"] == "face.detection"

    def test_transcript_maps_to_transcript_segment(self):
        """Test transcript kind maps correctly."""
        assert KIND_TO_ARTIFACT_TYPE["transcript"] == "transcript.segment"

    def test_ocr_maps_to_ocr_text(self):
        """Test ocr kind maps correctly."""
        assert KIND_TO_ARTIFACT_TYPE["ocr"] == "ocr.text"

    def test_scene_maps_to_scene(self):
        """Test scene kind maps correctly."""
        assert KIND_TO_ARTIFACT_TYPE["scene"] == "scene"

    def test_place_maps_to_place_classification(self):
        """Test place kind maps correctly."""
        assert KIND_TO_ARTIFACT_TYPE["place"] == "place.classification"


class TestBuildSearchQueryBasic:
    """Tests for build_search_query basic functionality.

    Validates: Requirements 4.2
    """

    def test_returns_tuple_of_three_elements(self):
        """Test that build_search_query returns main_query, count_query, params."""
        result = build_search_query(artifact_type="object.detection")
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_main_query_contains_artifact_type_filter(self):
        """Test that main query filters by artifact_type."""
        main_query, _, params = build_search_query(artifact_type="object.detection")
        assert "artifact_type = :artifact_type" in main_query
        assert params["artifact_type"] == "object.detection"

    def test_main_query_joins_artifacts_and_videos(self):
        """Test that main query joins artifacts with videos table."""
        main_query, _, _ = build_search_query(artifact_type="object.detection")
        assert "JOIN videos v ON v.video_id = a.asset_id" in main_query

    def test_main_query_selects_required_fields(self):
        """Test that main query selects all required fields."""
        main_query, _, _ = build_search_query(artifact_type="object.detection")
        assert "a.artifact_id" in main_query
        assert "a.asset_id as video_id" in main_query
        assert "a.artifact_type" in main_query
        assert "a.span_start_ms as start_ms" in main_query
        assert "a.payload_json as preview" in main_query
        assert "v.filename as video_filename" in main_query
        assert "v.file_created_at" in main_query


class TestBuildSearchQueryLabelFilter:
    """Tests for label filter in build_search_query.

    Validates: Requirements 4.2 (label parameter)
    """

    def test_label_filter_added_when_provided(self):
        """Test that label filter is added to query when provided."""
        main_query, _, params = build_search_query(
            artifact_type="object.detection",
            label="dog",
        )
        assert "payload_json->>'label' = :label" in main_query
        assert params["label"] == "dog"

    def test_label_filter_not_added_when_none(self):
        """Test that label filter is not added when label is None."""
        main_query, _, params = build_search_query(
            artifact_type="object.detection",
            label=None,
        )
        assert "payload_json->>'label'" not in main_query
        assert "label" not in params


class TestBuildSearchQueryTextFilter:
    """Tests for text query filter in build_search_query.

    Validates: Requirements 4.2 (query parameter)
    """

    def test_query_filter_added_when_provided(self):
        """Test that text query filter is added when provided."""
        main_query, _, params = build_search_query(
            artifact_type="transcript.segment",
            query="hello",
        )
        assert "payload_json->>'text' ILIKE" in main_query
        assert params["query"] == "hello"

    def test_query_filter_uses_ilike_for_case_insensitive(self):
        """Test that query filter uses ILIKE for case-insensitive matching."""
        main_query, _, _ = build_search_query(
            artifact_type="transcript.segment",
            query="hello",
        )
        assert "ILIKE" in main_query

    def test_query_filter_not_added_when_none(self):
        """Test that query filter is not added when query is None."""
        main_query, _, params = build_search_query(
            artifact_type="transcript.segment",
            query=None,
        )
        assert "payload_json->>'text'" not in main_query
        assert "query" not in params


class TestBuildSearchQueryFilenameFilter:
    """Tests for filename filter in build_search_query.

    Validates: Requirements 4.8
    """

    def test_filename_filter_added_when_provided(self):
        """Test that filename filter is added when provided."""
        main_query, _, params = build_search_query(
            artifact_type="object.detection",
            filename="beach",
        )
        assert "v.filename ILIKE" in main_query
        assert params["filename"] == "beach"

    def test_filename_filter_uses_ilike_for_case_insensitive(self):
        """Test that filename filter uses ILIKE for case-insensitive matching."""
        main_query, _, _ = build_search_query(
            artifact_type="object.detection",
            filename="beach",
        )
        assert "v.filename ILIKE" in main_query

    def test_filename_filter_not_added_when_none(self):
        """Test that filename filter is not added when filename is None."""
        main_query, _, params = build_search_query(
            artifact_type="object.detection",
            filename=None,
        )
        assert "v.filename ILIKE" not in main_query
        assert "filename" not in params


class TestBuildSearchQueryConfidenceFilter:
    """Tests for min_confidence filter in build_search_query.

    Validates: Requirements 4.2 (min_confidence parameter)
    """

    def test_confidence_filter_added_when_provided(self):
        """Test that confidence filter is added when provided."""
        main_query, _, params = build_search_query(
            artifact_type="object.detection",
            min_confidence=0.8,
        )
        assert "(a.payload_json->>'confidence')::float >= :min_confidence" in main_query
        assert params["min_confidence"] == 0.8

    def test_confidence_filter_not_added_when_none(self):
        """Test that confidence filter is not added when min_confidence is None."""
        main_query, _, params = build_search_query(
            artifact_type="object.detection",
            min_confidence=None,
        )
        assert "confidence" not in main_query
        assert "min_confidence" not in params


class TestBuildSearchQueryGroupByVideo:
    """Tests for group_by_video mode in build_search_query.

    Validates: Requirements 4.9, 4.10
    """

    def test_grouped_query_uses_window_function(self):
        """Test that grouped query uses ROW_NUMBER window function."""
        main_query, _, _ = build_search_query(
            artifact_type="object.detection",
            group_by_video=True,
        )
        assert "ROW_NUMBER() OVER" in main_query
        assert "PARTITION BY a.asset_id" in main_query

    def test_grouped_query_includes_artifact_count(self):
        """Test that grouped query includes artifact_count.

        Validates: Requirements 4.10
        """
        main_query, _, _ = build_search_query(
            artifact_type="object.detection",
            group_by_video=True,
        )
        assert "COUNT(*) OVER (PARTITION BY a.asset_id) as artifact_count" in main_query

    def test_grouped_query_selects_first_per_video(self):
        """Test that grouped query filters to first artifact per video.

        Validates: Requirements 4.9
        """
        main_query, _, _ = build_search_query(
            artifact_type="object.detection",
            group_by_video=True,
        )
        assert "WHERE rn = 1" in main_query

    def test_grouped_count_query_counts_distinct_videos(self):
        """Test that grouped count query counts distinct videos."""
        _, count_query, _ = build_search_query(
            artifact_type="object.detection",
            group_by_video=True,
        )
        assert "COUNT(DISTINCT a.asset_id)" in count_query

    def test_ungrouped_query_does_not_use_window_function(self):
        """Test that ungrouped query does not use window functions."""
        main_query, _, _ = build_search_query(
            artifact_type="object.detection",
            group_by_video=False,
        )
        assert "ROW_NUMBER()" not in main_query
        assert "artifact_count" not in main_query

    def test_ungrouped_count_query_counts_all_artifacts(self):
        """Test that ungrouped count query counts all matching artifacts."""
        _, count_query, _ = build_search_query(
            artifact_type="object.detection",
            group_by_video=False,
        )
        assert "COUNT(*)" in count_query
        assert "DISTINCT" not in count_query


class TestBuildSearchQueryMultipleFilters:
    """Tests for combining multiple filters in build_search_query."""

    def test_multiple_filters_combined_with_and(self):
        """Test that multiple filters are combined with AND."""
        main_query, _, params = build_search_query(
            artifact_type="object.detection",
            label="dog",
            filename="beach",
            min_confidence=0.8,
        )
        assert "payload_json->>'label' = :label" in main_query
        assert "v.filename ILIKE" in main_query
        assert "(a.payload_json->>'confidence')::float >= :min_confidence" in main_query
        assert params["label"] == "dog"
        assert params["filename"] == "beach"
        assert params["min_confidence"] == 0.8

    def test_filters_applied_to_both_grouped_and_count_queries(self):
        """Test that filters are applied to both main and count queries."""
        main_query, count_query, _ = build_search_query(
            artifact_type="object.detection",
            label="dog",
            group_by_video=True,
        )
        # Both queries should have the label filter
        assert "payload_json->>'label' = :label" in main_query
        assert "payload_json->>'label' = :label" in count_query


class TestSearchQueryOrdering:
    """Tests for search result ordering.

    Validates: Requirements 4.3 - Results ordered by global timeline
    (file_created_at, video_id, start_ms)
    """

    def test_ordering_clause_structure(self):
        """Test that ordering uses the correct three-level sort.

        The global timeline ordering should be:
        1. file_created_at ASC NULLS LAST (primary)
        2. video_id ASC (secondary)
        3. start_ms ASC (tertiary)
        """
        # The ordering is applied in the endpoint, not in build_search_query
        # This test verifies the query structure supports ordering
        main_query, _, _ = build_search_query(artifact_type="object.detection")
        # Query should select file_created_at for ordering
        assert "v.file_created_at" in main_query
        # Query should select video_id for ordering
        assert "video_id" in main_query
        # Query should select start_ms for ordering
        assert "start_ms" in main_query

    def test_grouped_query_ordering_fields_available(self):
        """Test that grouped query has fields needed for ordering."""
        main_query, _, _ = build_search_query(
            artifact_type="object.detection",
            group_by_video=True,
        )
        # Grouped query should also have ordering fields
        assert "file_created_at" in main_query
        assert "video_id" in main_query
        assert "start_ms" in main_query


class TestSearchQueryPagination:
    """Tests for search pagination.

    Validates: Requirements 4.6 - Support pagination via limit and offset
    """

    def test_query_params_do_not_include_pagination_by_default(self):
        """Test that build_search_query doesn't add pagination params.

        Pagination is added by the endpoint, not the query builder.
        """
        _, _, params = build_search_query(artifact_type="object.detection")
        assert "limit" not in params
        assert "offset" not in params

    def test_count_query_does_not_include_pagination(self):
        """Test that count query doesn't include LIMIT/OFFSET.

        Count query should return total matching results before pagination.
        """
        _, count_query, _ = build_search_query(artifact_type="object.detection")
        assert "LIMIT" not in count_query
        assert "OFFSET" not in count_query

    def test_grouped_count_query_does_not_include_pagination(self):
        """Test that grouped count query doesn't include LIMIT/OFFSET."""
        _, count_query, _ = build_search_query(
            artifact_type="object.detection",
            group_by_video=True,
        )
        assert "LIMIT" not in count_query
        assert "OFFSET" not in count_query


class TestSearchQueryTotalCount:
    """Tests for total count query.

    Validates: Requirements 4.7 - Return total count for pagination UI
    """

    def test_count_query_returns_count(self):
        """Test that count query uses COUNT(*)."""
        _, count_query, _ = build_search_query(artifact_type="object.detection")
        assert "COUNT(*)" in count_query

    def test_count_query_applies_same_filters(self):
        """Test that count query applies the same filters as main query."""
        _, count_query, params = build_search_query(
            artifact_type="object.detection",
            label="dog",
            filename="beach",
            min_confidence=0.8,
        )
        # Count query should have all the same filters
        assert "payload_json->>'label' = :label" in count_query
        assert "v.filename ILIKE" in count_query
        assert (
            "(a.payload_json->>'confidence')::float >= :min_confidence"
            in count_query
        )
        # Params should include all filter values
        assert params["label"] == "dog"
        assert params["filename"] == "beach"
        assert params["min_confidence"] == 0.8

    def test_grouped_count_query_counts_distinct_videos(self):
        """Test that grouped count returns count of unique videos.

        When group_by_video=true, total should be number of videos,
        not number of artifacts.
        """
        _, count_query, _ = build_search_query(
            artifact_type="object.detection",
            group_by_video=True,
        )
        assert "COUNT(DISTINCT a.asset_id)" in count_query

    def test_ungrouped_count_query_counts_all_artifacts(self):
        """Test that ungrouped count returns count of all artifacts."""
        _, count_query, _ = build_search_query(
            artifact_type="object.detection",
            group_by_video=False,
        )
        assert "COUNT(*)" in count_query
        # Should not count distinct
        assert "DISTINCT" not in count_query


class TestThumbnailUrlConstruction:
    """Tests for thumbnail URL construction in search results.

    Validates: Requirements 4.4, 4.5
    """

    def test_thumbnail_url_format(self):
        """Test that thumbnail_url follows the correct format.

        Validates: Requirements 4.5 - thumbnail_url SHALL point to
        /v1/thumbnails/{video_id}/{start_ms}
        """
        from src.api.artifact_search_controller import ArtifactSearchResult

        result = ArtifactSearchResult(
            video_id="abc-123",
            artifact_id="obj_001",
            artifact_type="object.detection",
            start_ms=15000,
            thumbnail_url="/v1/thumbnails/abc-123/15000",
            preview={"label": "dog"},
            video_filename="beach.mp4",
            file_created_at="2025-05-19T02:22:21",
            artifact_count=None,
        )
        assert result.thumbnail_url == "/v1/thumbnails/abc-123/15000"

    def test_thumbnail_url_with_zero_timestamp(self):
        """Test thumbnail_url with start_ms=0."""
        from src.api.artifact_search_controller import ArtifactSearchResult

        result = ArtifactSearchResult(
            video_id="video-001",
            artifact_id="obj_002",
            artifact_type="object.detection",
            start_ms=0,
            thumbnail_url="/v1/thumbnails/video-001/0",
            preview={"label": "cat"},
            video_filename="test.mp4",
            file_created_at=None,
            artifact_count=None,
        )
        assert result.thumbnail_url == "/v1/thumbnails/video-001/0"


class TestArtifactSearchResultSchema:
    """Tests for ArtifactSearchResult schema.

    Validates: Requirements 4.4 - Each result SHALL include required fields
    """

    def test_result_includes_video_id(self):
        """Test that result includes video_id."""
        from src.api.artifact_search_controller import ArtifactSearchResult

        result = ArtifactSearchResult(
            video_id="abc-123",
            artifact_id="obj_001",
            artifact_type="object.detection",
            start_ms=15000,
            thumbnail_url="/v1/thumbnails/abc-123/15000",
            preview={"label": "dog"},
            video_filename="beach.mp4",
            file_created_at="2025-05-19T02:22:21",
            artifact_count=None,
        )
        assert result.video_id == "abc-123"

    def test_result_includes_artifact_id(self):
        """Test that result includes artifact_id."""
        from src.api.artifact_search_controller import ArtifactSearchResult

        result = ArtifactSearchResult(
            video_id="abc-123",
            artifact_id="obj_001",
            artifact_type="object.detection",
            start_ms=15000,
            thumbnail_url="/v1/thumbnails/abc-123/15000",
            preview={"label": "dog"},
            video_filename="beach.mp4",
            file_created_at="2025-05-19T02:22:21",
            artifact_count=None,
        )
        assert result.artifact_id == "obj_001"

    def test_result_includes_start_ms(self):
        """Test that result includes start_ms."""
        from src.api.artifact_search_controller import ArtifactSearchResult

        result = ArtifactSearchResult(
            video_id="abc-123",
            artifact_id="obj_001",
            artifact_type="object.detection",
            start_ms=15000,
            thumbnail_url="/v1/thumbnails/abc-123/15000",
            preview={"label": "dog"},
            video_filename="beach.mp4",
            file_created_at="2025-05-19T02:22:21",
            artifact_count=None,
        )
        assert result.start_ms == 15000

    def test_result_includes_preview(self):
        """Test that result includes preview payload."""
        from src.api.artifact_search_controller import ArtifactSearchResult

        result = ArtifactSearchResult(
            video_id="abc-123",
            artifact_id="obj_001",
            artifact_type="object.detection",
            start_ms=15000,
            thumbnail_url="/v1/thumbnails/abc-123/15000",
            preview={"label": "dog", "confidence": 0.95},
            video_filename="beach.mp4",
            file_created_at="2025-05-19T02:22:21",
            artifact_count=None,
        )
        assert result.preview == {"label": "dog", "confidence": 0.95}

    def test_result_includes_video_filename(self):
        """Test that result includes video_filename.

        Validates: Requirements 4.4 - Each result SHALL include video_filename
        """
        from src.api.artifact_search_controller import ArtifactSearchResult

        result = ArtifactSearchResult(
            video_id="abc-123",
            artifact_id="obj_001",
            artifact_type="object.detection",
            start_ms=15000,
            thumbnail_url="/v1/thumbnails/abc-123/15000",
            preview={"label": "dog"},
            video_filename="beach_trip.mp4",
            file_created_at="2025-05-19T02:22:21",
            artifact_count=None,
        )
        assert result.video_filename == "beach_trip.mp4"

    def test_result_includes_file_created_at(self):
        """Test that result includes file_created_at."""
        from src.api.artifact_search_controller import ArtifactSearchResult

        result = ArtifactSearchResult(
            video_id="abc-123",
            artifact_id="obj_001",
            artifact_type="object.detection",
            start_ms=15000,
            thumbnail_url="/v1/thumbnails/abc-123/15000",
            preview={"label": "dog"},
            video_filename="beach.mp4",
            file_created_at="2025-05-19T02:22:21",
            artifact_count=None,
        )
        assert result.file_created_at == "2025-05-19T02:22:21"

    def test_result_file_created_at_can_be_none(self):
        """Test that file_created_at can be None."""
        from src.api.artifact_search_controller import ArtifactSearchResult

        result = ArtifactSearchResult(
            video_id="abc-123",
            artifact_id="obj_001",
            artifact_type="object.detection",
            start_ms=15000,
            thumbnail_url="/v1/thumbnails/abc-123/15000",
            preview={"label": "dog"},
            video_filename="beach.mp4",
            file_created_at=None,
            artifact_count=None,
        )
        assert result.file_created_at is None

    def test_result_artifact_count_optional(self):
        """Test that artifact_count is optional (None when not grouped)."""
        from src.api.artifact_search_controller import ArtifactSearchResult

        result = ArtifactSearchResult(
            video_id="abc-123",
            artifact_id="obj_001",
            artifact_type="object.detection",
            start_ms=15000,
            thumbnail_url="/v1/thumbnails/abc-123/15000",
            preview={"label": "dog"},
            video_filename="beach.mp4",
            file_created_at="2025-05-19T02:22:21",
            artifact_count=None,
        )
        assert result.artifact_count is None

    def test_result_artifact_count_present_when_grouped(self):
        """Test that artifact_count is present when group_by_video=true.

        Validates: Requirements 4.10
        """
        from src.api.artifact_search_controller import ArtifactSearchResult

        result = ArtifactSearchResult(
            video_id="abc-123",
            artifact_id="obj_001",
            artifact_type="object.detection",
            start_ms=15000,
            thumbnail_url="/v1/thumbnails/abc-123/15000",
            preview={"label": "dog"},
            video_filename="beach.mp4",
            file_created_at="2025-05-19T02:22:21",
            artifact_count=5,
        )
        assert result.artifact_count == 5


class TestArtifactSearchResponseSchema:
    """Tests for ArtifactSearchResponse schema.

    Validates: Requirements 4.6, 4.7
    """

    def test_response_includes_results_list(self):
        """Test that response includes results list."""
        from src.api.artifact_search_controller import (
            ArtifactSearchResponse,
            ArtifactSearchResult,
        )

        result = ArtifactSearchResult(
            video_id="abc-123",
            artifact_id="obj_001",
            artifact_type="object.detection",
            start_ms=15000,
            thumbnail_url="/v1/thumbnails/abc-123/15000",
            preview={"label": "dog"},
            video_filename="beach.mp4",
            file_created_at="2025-05-19T02:22:21",
            artifact_count=None,
        )
        response = ArtifactSearchResponse(
            results=[result],
            total=1,
            limit=20,
            offset=0,
        )
        assert len(response.results) == 1
        assert response.results[0].video_id == "abc-123"

    def test_response_includes_total_count(self):
        """Test that response includes total count.

        Validates: Requirements 4.7
        """
        from src.api.artifact_search_controller import ArtifactSearchResponse

        response = ArtifactSearchResponse(
            results=[],
            total=150,
            limit=20,
            offset=0,
        )
        assert response.total == 150

    def test_response_includes_limit(self):
        """Test that response includes limit.

        Validates: Requirements 4.6
        """
        from src.api.artifact_search_controller import ArtifactSearchResponse

        response = ArtifactSearchResponse(
            results=[],
            total=150,
            limit=20,
            offset=0,
        )
        assert response.limit == 20

    def test_response_includes_offset(self):
        """Test that response includes offset.

        Validates: Requirements 4.6
        """
        from src.api.artifact_search_controller import ArtifactSearchResponse

        response = ArtifactSearchResponse(
            results=[],
            total=150,
            limit=20,
            offset=40,
        )
        assert response.offset == 40

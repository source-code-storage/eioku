"""Unit tests for thumbnail extractor module.

Tests for idempotent thumbnail generation functionality.
"""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.workers.thumbnail_extractor import (
    THUMBNAIL_DIR,
    ThumbnailGenerationStats,
    collect_artifact_timestamps,
    filter_existing_thumbnails,
    generate_thumbnails_idempotent,
    get_thumbnail_path,
)


class TestGetThumbnailPath:
    """Tests for get_thumbnail_path function."""

    def test_returns_correct_path_structure(self):
        """Test that path follows expected structure."""
        path = get_thumbnail_path("video-123", 5000)

        assert path == THUMBNAIL_DIR / "video-123" / "5000.jpg"

    def test_handles_zero_timestamp(self):
        """Test that zero timestamp is handled correctly."""
        path = get_thumbnail_path("video-abc", 0)

        assert path == THUMBNAIL_DIR / "video-abc" / "0.jpg"

    def test_handles_large_timestamp(self):
        """Test that large timestamps are handled correctly."""
        path = get_thumbnail_path("video-xyz", 3600000)  # 1 hour in ms

        assert path == THUMBNAIL_DIR / "video-xyz" / "3600000.jpg"


class TestEnsureThumbnailDirectory:
    """Tests for ensure_thumbnail_directory function."""

    def test_creates_directory_if_not_exists(self):
        """Test that directory is created when it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(Path, "mkdir") as mock_mkdir, patch(
                "src.workers.thumbnail_extractor.THUMBNAIL_DIR",
                Path(temp_dir),
            ):
                # Re-import to get patched version
                from src.workers.thumbnail_extractor import ensure_thumbnail_directory

                ensure_thumbnail_directory("new-video")

                # Verify mkdir was called with correct params
                mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


class TestCollectArtifactTimestamps:
    """Tests for collect_artifact_timestamps function.

    Requirements:
    - 1.2: Query all artifacts for video and collect unique start_ms timestamps
    - 2.1: Deduplicate timestamps (multiple artifacts at same ms)
    """

    def test_returns_unique_timestamps_sorted(self):
        """Test that unique timestamps are returned in sorted order."""
        # Mock session with result containing timestamps
        mock_session = MagicMock()
        mock_result = MagicMock()
        # Simulate DB returning unique timestamps (already deduplicated by DISTINCT)
        mock_result.__iter__ = lambda self: iter([(0,), (5000,), (10000,), (15000,)])
        mock_session.execute.return_value = mock_result

        timestamps = collect_artifact_timestamps("video-123", mock_session)

        assert timestamps == [0, 5000, 10000, 15000]
        # Verify the query was executed with correct video_id
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args
        # Parameters are passed as second positional argument
        assert call_args[0][1]["video_id"] == "video-123"

    def test_returns_empty_list_when_no_artifacts(self):
        """Test that empty list is returned when video has no artifacts."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter([])
        mock_session.execute.return_value = mock_result

        timestamps = collect_artifact_timestamps("video-no-artifacts", mock_session)

        assert timestamps == []

    def test_deduplication_via_distinct_query(self):
        """Test that DISTINCT in query ensures deduplication.

        Even if multiple artifacts share the same timestamp, the query
        returns each timestamp only once (Requirement 2.1).
        """
        mock_session = MagicMock()
        mock_result = MagicMock()
        # DB returns deduplicated timestamps (DISTINCT handles this)
        # Original artifacts might have: [5000, 5000, 5000, 10000, 10000]
        # But DISTINCT returns: [5000, 10000]
        mock_result.__iter__ = lambda self: iter([(5000,), (10000,)])
        mock_session.execute.return_value = mock_result

        timestamps = collect_artifact_timestamps("video-dupe", mock_session)

        # Should only have unique timestamps
        assert timestamps == [5000, 10000]
        assert len(timestamps) == len(set(timestamps))  # All unique

    def test_query_uses_correct_sql_structure(self):
        """Test that the SQL query uses DISTINCT and ORDER BY."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter([])
        mock_session.execute.return_value = mock_result

        collect_artifact_timestamps("video-123", mock_session)

        # Get the SQL text from the call
        call_args = mock_session.execute.call_args
        sql_text = str(call_args[0][0])

        # Verify key SQL components
        assert "DISTINCT" in sql_text
        assert "span_start_ms" in sql_text
        assert "asset_id" in sql_text
        assert "ORDER BY" in sql_text

    def test_handles_large_timestamp_values(self):
        """Test handling of large timestamp values (long videos)."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        # 2 hour video = 7,200,000 ms
        mock_result.__iter__ = lambda self: iter([(0,), (3600000,), (7200000,)])
        mock_session.execute.return_value = mock_result

        timestamps = collect_artifact_timestamps("long-video", mock_session)

        assert timestamps == [0, 3600000, 7200000]


class TestFilterExistingThumbnails:
    """Tests for filter_existing_thumbnails function.

    Requirements:
    - 1.3: Skip thumbnail generation for timestamps that already have a thumbnail
    - 2.2: Skip extraction for timestamps where thumbnail file already exists
    - 2.3: Log the count of skipped vs newly generated thumbnails
    """

    def test_all_new_timestamps_returned_for_generation(self):
        """Test that all timestamps are returned for generation when none exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "src.workers.thumbnail_extractor.THUMBNAIL_DIR",
                Path(temp_dir),
            ):
                timestamps = [0, 5000, 10000, 15000]

                to_generate, skipped = filter_existing_thumbnails(
                    "video-123", timestamps
                )

                assert to_generate == [0, 5000, 10000, 15000]
                assert skipped == []

    def test_existing_thumbnails_are_skipped(self):
        """Test that existing thumbnails are skipped (idempotent behavior)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create video directory and some existing thumbnails
            video_dir = temp_path / "video-123"
            video_dir.mkdir(parents=True)
            (video_dir / "0.jpg").touch()
            (video_dir / "10000.jpg").touch()

            with patch(
                "src.workers.thumbnail_extractor.THUMBNAIL_DIR",
                temp_path,
            ):
                timestamps = [0, 5000, 10000, 15000]

                to_generate, skipped = filter_existing_thumbnails(
                    "video-123", timestamps
                )

                # 0 and 10000 exist, so should be skipped
                assert to_generate == [5000, 15000]
                assert skipped == [0, 10000]

    def test_all_existing_thumbnails_skipped(self):
        """Test that all thumbnails are skipped when all exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create video directory and all thumbnails
            video_dir = temp_path / "video-456"
            video_dir.mkdir(parents=True)
            (video_dir / "1000.jpg").touch()
            (video_dir / "2000.jpg").touch()
            (video_dir / "3000.jpg").touch()

            with patch(
                "src.workers.thumbnail_extractor.THUMBNAIL_DIR",
                temp_path,
            ):
                timestamps = [1000, 2000, 3000]

                to_generate, skipped = filter_existing_thumbnails(
                    "video-456", timestamps
                )

                assert to_generate == []
                assert skipped == [1000, 2000, 3000]

    def test_empty_timestamps_list(self):
        """Test handling of empty timestamps list."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "src.workers.thumbnail_extractor.THUMBNAIL_DIR",
                Path(temp_dir),
            ):
                to_generate, skipped = filter_existing_thumbnails("video-789", [])

                assert to_generate == []
                assert skipped == []

    def test_preserves_timestamp_order(self):
        """Test that timestamp order is preserved in both lists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create video directory with some thumbnails
            video_dir = temp_path / "video-order"
            video_dir.mkdir(parents=True)
            (video_dir / "2000.jpg").touch()
            (video_dir / "4000.jpg").touch()

            with patch(
                "src.workers.thumbnail_extractor.THUMBNAIL_DIR",
                temp_path,
            ):
                timestamps = [1000, 2000, 3000, 4000, 5000]

                to_generate, skipped = filter_existing_thumbnails(
                    "video-order", timestamps
                )

                # Order should be preserved
                assert to_generate == [1000, 3000, 5000]
                assert skipped == [2000, 4000]

    def test_logs_counts(self, caplog):
        """Test that counts are logged correctly (Requirement 2.3)."""
        import logging

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create video directory with one existing thumbnail
            video_dir = temp_path / "video-log"
            video_dir.mkdir(parents=True)
            (video_dir / "5000.jpg").touch()

            with patch(
                "src.workers.thumbnail_extractor.THUMBNAIL_DIR",
                temp_path,
            ):
                with caplog.at_level(logging.INFO):
                    timestamps = [0, 5000, 10000]

                    filter_existing_thumbnails("video-log", timestamps)

                    # Check log message contains expected counts
                    assert "to_generate=2" in caplog.text
                    assert "skipped=1" in caplog.text
                    assert "total=3" in caplog.text

    def test_different_videos_independent(self):
        """Test that different video IDs are handled independently."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create thumbnails for video-a only
            video_a_dir = temp_path / "video-a"
            video_a_dir.mkdir(parents=True)
            (video_a_dir / "1000.jpg").touch()

            with patch(
                "src.workers.thumbnail_extractor.THUMBNAIL_DIR",
                temp_path,
            ):
                # video-a should skip 1000
                to_gen_a, skip_a = filter_existing_thumbnails("video-a", [1000, 2000])
                assert to_gen_a == [2000]
                assert skip_a == [1000]

                # video-b should generate all (no existing thumbnails)
                to_gen_b, skip_b = filter_existing_thumbnails("video-b", [1000, 2000])
                assert to_gen_b == [1000, 2000]
                assert skip_b == []


class TestThumbnailGenerationStats:
    """Tests for ThumbnailGenerationStats class."""

    def test_default_values(self):
        """Test that default values are all zero."""
        stats = ThumbnailGenerationStats()

        assert stats.generated == 0
        assert stats.skipped == 0
        assert stats.failed == 0
        assert stats.total_timestamps == 0

    def test_custom_values(self):
        """Test initialization with custom values."""
        stats = ThumbnailGenerationStats(
            generated=10,
            skipped=5,
            failed=2,
            total_timestamps=17,
        )

        assert stats.generated == 10
        assert stats.skipped == 5
        assert stats.failed == 2
        assert stats.total_timestamps == 17

    def test_to_dict(self):
        """Test conversion to dictionary."""
        stats = ThumbnailGenerationStats(
            generated=3,
            skipped=7,
            failed=1,
            total_timestamps=11,
        )

        result = stats.to_dict()

        assert result == {
            "generated": 3,
            "skipped": 7,
            "failed": 1,
            "total_timestamps": 11,
        }


class TestGenerateThumbnailsIdempotent:
    """Tests for generate_thumbnails_idempotent function.

    Requirements:
    - 1.3: Skip thumbnail generation for timestamps that already have a thumbnail
    - 2.2: Skip extraction for timestamps where thumbnail file already exists
    - 2.3: Log the count of skipped vs newly generated thumbnails
    """

    def test_returns_stats_without_extract_fn(self):
        """Test that stats are returned when no extract function is provided."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "src.workers.thumbnail_extractor.THUMBNAIL_DIR",
                Path(temp_dir),
            ):
                timestamps = [0, 5000, 10000]

                stats = generate_thumbnails_idempotent(
                    "video-123",
                    "/path/to/video.mp4",
                    timestamps,
                    extract_frame_fn=None,
                )

                assert stats.total_timestamps == 3
                assert stats.skipped == 0
                assert stats.generated == 0
                assert stats.failed == 0

    def test_skips_existing_thumbnails(self):
        """Test that existing thumbnails are skipped (idempotent behavior)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create video directory and some existing thumbnails
            video_dir = temp_path / "video-123"
            video_dir.mkdir(parents=True)
            (video_dir / "0.jpg").touch()
            (video_dir / "10000.jpg").touch()

            mock_extract = MagicMock(return_value=True)

            with patch(
                "src.workers.thumbnail_extractor.THUMBNAIL_DIR",
                temp_path,
            ):
                timestamps = [0, 5000, 10000, 15000]

                stats = generate_thumbnails_idempotent(
                    "video-123",
                    "/path/to/video.mp4",
                    timestamps,
                    extract_frame_fn=mock_extract,
                )

                # 0 and 10000 exist, so should be skipped
                assert stats.skipped == 2
                assert stats.generated == 2
                assert stats.total_timestamps == 4

                # Extract should only be called for non-existing thumbnails
                assert mock_extract.call_count == 2

    def test_all_existing_thumbnails_skipped(self):
        """Test that all thumbnails are skipped when all exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create video directory and all thumbnails
            video_dir = temp_path / "video-456"
            video_dir.mkdir(parents=True)
            (video_dir / "1000.jpg").touch()
            (video_dir / "2000.jpg").touch()
            (video_dir / "3000.jpg").touch()

            mock_extract = MagicMock(return_value=True)

            with patch(
                "src.workers.thumbnail_extractor.THUMBNAIL_DIR",
                temp_path,
            ):
                timestamps = [1000, 2000, 3000]

                stats = generate_thumbnails_idempotent(
                    "video-456",
                    "/path/to/video.mp4",
                    timestamps,
                    extract_frame_fn=mock_extract,
                )

                assert stats.skipped == 3
                assert stats.generated == 0
                assert stats.total_timestamps == 3

                # Extract should not be called at all
                mock_extract.assert_not_called()

    def test_all_new_thumbnails_generated(self):
        """Test that all thumbnails are generated when none exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_extract = MagicMock(return_value=True)

            with patch(
                "src.workers.thumbnail_extractor.THUMBNAIL_DIR",
                Path(temp_dir),
            ):
                timestamps = [0, 5000, 10000]

                stats = generate_thumbnails_idempotent(
                    "video-new",
                    "/path/to/video.mp4",
                    timestamps,
                    extract_frame_fn=mock_extract,
                )

                assert stats.skipped == 0
                assert stats.generated == 3
                assert stats.total_timestamps == 3

                # Extract should be called for all timestamps
                assert mock_extract.call_count == 3

    def test_handles_extraction_failures(self):
        """Test that extraction failures are tracked correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock that returns False (failure) for some extractions
            def mock_extract(video_path, timestamp_ms, output_path):
                # Fail for timestamp 5000
                return timestamp_ms != 5000

            with patch(
                "src.workers.thumbnail_extractor.THUMBNAIL_DIR",
                Path(temp_dir),
            ):
                timestamps = [0, 5000, 10000]

                stats = generate_thumbnails_idempotent(
                    "video-fail",
                    "/path/to/video.mp4",
                    timestamps,
                    extract_frame_fn=mock_extract,
                )

                assert stats.generated == 2
                assert stats.failed == 1
                assert stats.total_timestamps == 3

    def test_handles_extraction_exceptions(self):
        """Test that extraction exceptions are caught and tracked."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock that raises exception for some extractions
            def mock_extract(video_path, timestamp_ms, output_path):
                if timestamp_ms == 5000:
                    raise RuntimeError("FFmpeg failed")
                return True

            with patch(
                "src.workers.thumbnail_extractor.THUMBNAIL_DIR",
                Path(temp_dir),
            ):
                timestamps = [0, 5000, 10000]

                stats = generate_thumbnails_idempotent(
                    "video-exc",
                    "/path/to/video.mp4",
                    timestamps,
                    extract_frame_fn=mock_extract,
                )

                assert stats.generated == 2
                assert stats.failed == 1
                assert stats.total_timestamps == 3

    def test_empty_timestamps_list(self):
        """Test handling of empty timestamps list."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_extract = MagicMock(return_value=True)

            with patch(
                "src.workers.thumbnail_extractor.THUMBNAIL_DIR",
                Path(temp_dir),
            ):
                stats = generate_thumbnails_idempotent(
                    "video-empty",
                    "/path/to/video.mp4",
                    [],
                    extract_frame_fn=mock_extract,
                )

                assert stats.generated == 0
                assert stats.skipped == 0
                assert stats.failed == 0
                assert stats.total_timestamps == 0

                mock_extract.assert_not_called()

    def test_creates_output_directory(self):
        """Test that output directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            mock_extract = MagicMock(return_value=True)

            with patch(
                "src.workers.thumbnail_extractor.THUMBNAIL_DIR",
                temp_path,
            ):
                generate_thumbnails_idempotent(
                    "new-video-dir",
                    "/path/to/video.mp4",
                    [1000],
                    extract_frame_fn=mock_extract,
                )

                # Directory should have been created
                assert (temp_path / "new-video-dir").exists()

    def test_extract_fn_receives_correct_arguments(self):
        """Test that extract function receives correct arguments."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            mock_extract = MagicMock(return_value=True)

            with patch(
                "src.workers.thumbnail_extractor.THUMBNAIL_DIR",
                temp_path,
            ):
                generate_thumbnails_idempotent(
                    "video-args",
                    "/path/to/video.mp4",
                    [5000],
                    extract_frame_fn=mock_extract,
                )

                mock_extract.assert_called_once_with(
                    "/path/to/video.mp4",
                    5000,
                    temp_path / "video-args" / "5000.jpg",
                )

    def test_logs_final_summary(self, caplog):
        """Test that final summary is logged (Requirement 2.3)."""
        import logging

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create one existing thumbnail
            video_dir = temp_path / "video-log"
            video_dir.mkdir(parents=True)
            (video_dir / "5000.jpg").touch()

            mock_extract = MagicMock(return_value=True)

            with patch(
                "src.workers.thumbnail_extractor.THUMBNAIL_DIR",
                temp_path,
            ):
                with caplog.at_level(logging.INFO):
                    generate_thumbnails_idempotent(
                        "video-log",
                        "/path/to/video.mp4",
                        [0, 5000, 10000],
                        extract_frame_fn=mock_extract,
                    )

                    # Check log message contains expected counts
                    assert "generated=2" in caplog.text
                    assert "skipped=1" in caplog.text
                    assert "total=3" in caplog.text

    def test_idempotent_multiple_runs(self):
        """Test that running multiple times produces same result (idempotent)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Track how many times extract is called
            extract_calls = []

            def mock_extract(video_path, timestamp_ms, output_path):
                extract_calls.append(timestamp_ms)
                # Actually create the file to simulate real behavior
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.touch()
                return True

            with patch(
                "src.workers.thumbnail_extractor.THUMBNAIL_DIR",
                temp_path,
            ):
                timestamps = [0, 5000, 10000]

                # First run - should generate all
                stats1 = generate_thumbnails_idempotent(
                    "video-idem",
                    "/path/to/video.mp4",
                    timestamps,
                    extract_frame_fn=mock_extract,
                )

                assert stats1.generated == 3
                assert stats1.skipped == 0
                assert len(extract_calls) == 3

                # Second run - should skip all (idempotent)
                stats2 = generate_thumbnails_idempotent(
                    "video-idem",
                    "/path/to/video.mp4",
                    timestamps,
                    extract_frame_fn=mock_extract,
                )

                assert stats2.generated == 0
                assert stats2.skipped == 3
                # Extract should not have been called again
                assert len(extract_calls) == 3


class TestExtractFrameWithFfmpeg:
    """Tests for extract_frame_with_ffmpeg function.

    Requirements:
    - 1.4: Generates JPEG format thumbnails with max width 320px
    - 1.6: Targets ~10-20KB file size via quality setting
    - 1.7: Uses ffmpeg for frame extraction
    """

    def test_builds_correct_ffmpeg_command(self):
        """Test that ffmpeg command is built with correct arguments."""
        from src.workers.thumbnail_extractor import (
            THUMBNAIL_QUALITY,
            THUMBNAIL_TIMEOUT,
            THUMBNAIL_WIDTH,
            extract_frame_with_ffmpeg,
        )

        with patch("src.workers.thumbnail_extractor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            extract_frame_with_ffmpeg(
                "/path/to/video.mp4",
                5000,
                Path("/output/5000.jpg"),
            )

            mock_run.assert_called_once()
            call_args = mock_run.call_args

            # Check command structure
            cmd = call_args[0][0]
            assert cmd[0] == "ffmpeg"
            assert "-ss" in cmd
            assert "5.0" in cmd  # 5000ms = 5.0s
            assert "-i" in cmd
            assert "/path/to/video.mp4" in cmd
            assert "-vframes" in cmd
            assert "1" in cmd
            assert "-vf" in cmd
            assert f"scale={THUMBNAIL_WIDTH}:-1" in cmd
            assert "-q:v" in cmd
            assert str(THUMBNAIL_QUALITY) in cmd
            assert "-y" in cmd
            assert "/output/5000.jpg" in cmd

            # Check subprocess.run kwargs
            assert call_args[1]["capture_output"] is True
            assert call_args[1]["check"] is True
            assert call_args[1]["timeout"] == THUMBNAIL_TIMEOUT

    def test_converts_milliseconds_to_seconds(self):
        """Test that timestamp is correctly converted from ms to seconds."""
        from src.workers.thumbnail_extractor import extract_frame_with_ffmpeg

        with patch("src.workers.thumbnail_extractor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            # Test various timestamps
            test_cases = [
                (0, "0.0"),
                (1000, "1.0"),
                (5500, "5.5"),
                (60000, "60.0"),
                (3661500, "3661.5"),  # 1 hour, 1 minute, 1.5 seconds
            ]

            for timestamp_ms, expected_seconds in test_cases:
                mock_run.reset_mock()
                extract_frame_with_ffmpeg(
                    "/video.mp4",
                    timestamp_ms,
                    Path("/output.jpg"),
                )

                cmd = mock_run.call_args[0][0]
                ss_index = cmd.index("-ss")
                assert cmd[ss_index + 1] == expected_seconds

    def test_returns_true_on_success(self):
        """Test that function returns True when ffmpeg succeeds."""
        from src.workers.thumbnail_extractor import extract_frame_with_ffmpeg

        with patch("src.workers.thumbnail_extractor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = extract_frame_with_ffmpeg(
                "/video.mp4",
                1000,
                Path("/output.jpg"),
            )

            assert result is True

    def test_returns_false_on_called_process_error(self):
        """Test that function returns False when ffmpeg fails."""
        from src.workers.thumbnail_extractor import extract_frame_with_ffmpeg

        with patch("src.workers.thumbnail_extractor.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1,
                cmd=["ffmpeg"],
                stderr=b"Error: Invalid input file",
            )

            result = extract_frame_with_ffmpeg(
                "/video.mp4",
                1000,
                Path("/output.jpg"),
            )

            assert result is False

    def test_returns_false_on_timeout(self):
        """Test that function returns False when ffmpeg times out."""
        from src.workers.thumbnail_extractor import extract_frame_with_ffmpeg

        with patch("src.workers.thumbnail_extractor.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["ffmpeg"],
                timeout=10,
            )

            result = extract_frame_with_ffmpeg(
                "/video.mp4",
                1000,
                Path("/output.jpg"),
            )

            assert result is False

    def test_returns_false_when_ffmpeg_not_found(self):
        """Test that function returns False when ffmpeg binary is not found."""
        from src.workers.thumbnail_extractor import extract_frame_with_ffmpeg

        with patch("src.workers.thumbnail_extractor.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("ffmpeg not found")

            result = extract_frame_with_ffmpeg(
                "/video.mp4",
                1000,
                Path("/output.jpg"),
            )

            assert result is False

    def test_returns_false_on_unexpected_error(self):
        """Test that function returns False on unexpected errors."""
        from src.workers.thumbnail_extractor import extract_frame_with_ffmpeg

        with patch("src.workers.thumbnail_extractor.subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("Unexpected error")

            result = extract_frame_with_ffmpeg(
                "/video.mp4",
                1000,
                Path("/output.jpg"),
            )

            assert result is False

    def test_logs_warning_on_called_process_error(self, caplog):
        """Test that CalledProcessError is logged as warning."""
        import logging

        from src.workers.thumbnail_extractor import extract_frame_with_ffmpeg

        with patch("src.workers.thumbnail_extractor.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1,
                cmd=["ffmpeg"],
                stderr=b"Error: Invalid input file",
            )

            with caplog.at_level(logging.WARNING):
                extract_frame_with_ffmpeg(
                    "/video.mp4",
                    5000,
                    Path("/output.jpg"),
                )

                assert "Failed to extract thumbnail at 5000ms" in caplog.text
                assert "Invalid input file" in caplog.text

    def test_logs_warning_on_timeout(self, caplog):
        """Test that timeout is logged as warning."""
        import logging

        from src.workers.thumbnail_extractor import extract_frame_with_ffmpeg

        with patch("src.workers.thumbnail_extractor.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["ffmpeg"],
                timeout=10,
            )

            with caplog.at_level(logging.WARNING):
                extract_frame_with_ffmpeg(
                    "/video.mp4",
                    5000,
                    Path("/output.jpg"),
                )

                assert "timed out at 5000ms" in caplog.text
                assert "timeout=10s" in caplog.text

    def test_logs_error_when_ffmpeg_not_found(self, caplog):
        """Test that missing ffmpeg is logged as error."""
        import logging

        from src.workers.thumbnail_extractor import extract_frame_with_ffmpeg

        with patch("src.workers.thumbnail_extractor.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("ffmpeg not found")

            with caplog.at_level(logging.ERROR):
                extract_frame_with_ffmpeg(
                    "/video.mp4",
                    1000,
                    Path("/output.jpg"),
                )

                assert "ffmpeg not found" in caplog.text

    def test_uses_configured_timeout(self):
        """Test that the configured timeout is used."""
        from src.workers.thumbnail_extractor import (
            THUMBNAIL_TIMEOUT,
            extract_frame_with_ffmpeg,
        )

        with patch("src.workers.thumbnail_extractor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            extract_frame_with_ffmpeg(
                "/video.mp4",
                1000,
                Path("/output.jpg"),
            )

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["timeout"] == THUMBNAIL_TIMEOUT
            assert THUMBNAIL_TIMEOUT == 10  # Verify constant value

    def test_handles_empty_stderr(self):
        """Test that empty stderr is handled gracefully."""
        from src.workers.thumbnail_extractor import extract_frame_with_ffmpeg

        with patch("src.workers.thumbnail_extractor.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1,
                cmd=["ffmpeg"],
                stderr=None,  # No stderr
            )

            result = extract_frame_with_ffmpeg(
                "/video.mp4",
                1000,
                Path("/output.jpg"),
            )

            assert result is False

    def test_handles_non_utf8_stderr(self):
        """Test that non-UTF8 stderr is handled gracefully."""
        from src.workers.thumbnail_extractor import extract_frame_with_ffmpeg

        with patch("src.workers.thumbnail_extractor.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1,
                cmd=["ffmpeg"],
                stderr=b"\xff\xfe Invalid bytes",  # Invalid UTF-8
            )

            result = extract_frame_with_ffmpeg(
                "/video.mp4",
                1000,
                Path("/output.jpg"),
            )

            # Should not raise, just return False
            assert result is False

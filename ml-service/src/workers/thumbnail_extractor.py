"""Thumbnail extractor module for generating JPEG thumbnails at artifact timestamps.

This module provides functionality to extract thumbnail images from video frames
at specific timestamps where artifacts were detected. Thumbnails are stored as
JPEG images for broad compatibility and efficient storage.

Requirements:
- 1.1: Provides thumbnail.extraction task type
- 1.2: Queries all artifacts for video and collects unique start_ms timestamps
- 1.4: Generates JPEG format thumbnails with max width 320px
- 1.5: Stores thumbnails at /data/thumbnails/{video_id}/{timestamp_ms}.jpg
- 1.6: Targets ~10-20KB file size via quality setting
- 1.7: Uses ffmpeg for frame extraction
- 2.1: Deduplicates timestamps (multiple artifacts at same ms)
"""

import logging
import subprocess
from collections.abc import Callable
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Thumbnail storage configuration
# Shared Docker volume mounted at /data/thumbnails
# ml-service writes, backend reads
THUMBNAIL_DIR = Path("/data/thumbnails")

# Image dimensions - max width with proportional height
THUMBNAIL_WIDTH = 320

# JPEG quality setting (2-31 for ffmpeg, lower = better quality)
# Value of 5 targets ~10-20KB file size with good quality
THUMBNAIL_QUALITY = 5

# Timeout for ffmpeg frame extraction in seconds
THUMBNAIL_TIMEOUT = 10


def ensure_thumbnail_directory(video_id: str) -> Path:
    """Create and return the thumbnail output directory for a video.

    Creates the directory structure:
        /data/thumbnails/{video_id}/

    Args:
        video_id: Unique identifier for the video

    Returns:
        Path to the video's thumbnail directory

    Raises:
        OSError: If directory creation fails due to permissions or disk issues
    """
    output_dir = THUMBNAIL_DIR / video_id
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Ensured thumbnail directory exists: {output_dir}")
    return output_dir


def get_thumbnail_path(video_id: str, timestamp_ms: int) -> Path:
    """Get the full path for a thumbnail file.

    Args:
        video_id: Unique identifier for the video
        timestamp_ms: Timestamp in milliseconds

    Returns:
        Path to the thumbnail file (may not exist yet)
    """
    return THUMBNAIL_DIR / video_id / f"{timestamp_ms}.jpg"


def extract_frame_with_ffmpeg(
    video_path: str, timestamp_ms: int, output_path: Path
) -> bool:
    """Extract a single frame from a video using ffmpeg and save as JPEG.

    Uses ffmpeg to seek to the specified timestamp and extract a single frame,
    scaling it to the configured thumbnail width while maintaining aspect ratio.
    The frame is encoded as JPEG with the configured quality setting.

    Args:
        video_path: Path to the source video file
        timestamp_ms: Timestamp in milliseconds to extract the frame from
        output_path: Path where the JPEG thumbnail should be saved

    Returns:
        True if extraction was successful, False otherwise.

    Raises:
        No exceptions are raised - all errors are caught and logged,
        returning False to indicate failure.

    Requirements:
        - 1.4: Generates JPEG format thumbnails with max width 320px
        - 1.6: Targets ~10-20KB file size via quality setting
        - 1.7: Uses ffmpeg for frame extraction

    Example:
        >>> success = extract_frame_with_ffmpeg(
        ...     "/data/videos/video.mp4",
        ...     5000,
        ...     Path("/data/thumbnails/video-123/5000.jpg")
        ... )
        >>> print(f"Extraction {'succeeded' if success else 'failed'}")
        Extraction succeeded
    """
    # Convert milliseconds to seconds for ffmpeg
    ts_sec = timestamp_ms / 1000

    # Build ffmpeg command
    # -ss: Seek to timestamp (before -i for fast seeking)
    # -i: Input video file
    # -vframes 1: Extract only one frame
    # -vf scale: Scale to THUMBNAIL_WIDTH, -1 maintains aspect ratio
    # -q:v: JPEG quality (2-31, lower = better quality, 5 targets ~10-20KB)
    # -y: Overwrite output file if exists
    cmd = [
        "ffmpeg",
        "-ss",
        str(ts_sec),
        "-i",
        video_path,
        "-vframes",
        "1",
        "-vf",
        f"scale={THUMBNAIL_WIDTH}:-1",
        "-q:v",
        str(THUMBNAIL_QUALITY),
        "-y",
        str(output_path),
    ]

    try:
        subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            timeout=THUMBNAIL_TIMEOUT,
        )
        logger.debug(
            f"Successfully extracted thumbnail at {timestamp_ms}ms to {output_path}"
        )
        return True

    except subprocess.CalledProcessError as e:
        # FFmpeg returned non-zero exit code
        stderr_output = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
        logger.warning(
            f"Failed to extract thumbnail at {timestamp_ms}ms: {stderr_output}"
        )
        return False

    except subprocess.TimeoutExpired:
        # FFmpeg took too long (> THUMBNAIL_TIMEOUT seconds)
        logger.warning(
            f"Thumbnail extraction timed out at {timestamp_ms}ms "
            f"(timeout={THUMBNAIL_TIMEOUT}s)"
        )
        return False

    except FileNotFoundError:
        # ffmpeg binary not found
        logger.error("ffmpeg not found. Please ensure ffmpeg is installed and in PATH.")
        return False

    except Exception as e:
        # Catch any other unexpected errors
        logger.error(f"Unexpected error extracting thumbnail at {timestamp_ms}ms: {e}")
        return False


def collect_artifact_timestamps(video_id: str, session: Session) -> list[int]:
    """Query all unique artifact timestamps for a video.

    Queries the artifacts table for all artifacts belonging to the specified
    video and extracts unique span_start_ms timestamps. Multiple artifacts
    at the same timestamp are deduplicated - only one thumbnail will be
    generated per unique timestamp.

    Args:
        video_id: Unique identifier for the video (maps to asset_id in artifacts)
        session: SQLAlchemy database session

    Returns:
        List of unique timestamps in milliseconds, sorted in ascending order.
        Returns empty list if no artifacts exist for the video.

    Requirements:
        - 1.2: Query all artifacts for video and collect unique start_ms timestamps
        - 2.1: Deduplicate timestamps (multiple artifacts at same ms)

    Example:
        >>> timestamps = collect_artifact_timestamps("video-123", session)
        >>> print(timestamps)
        [0, 5000, 15230, 30000]
    """
    result = session.execute(
        text(
            """
            SELECT DISTINCT span_start_ms as timestamp_ms
            FROM artifacts
            WHERE asset_id = :video_id
            ORDER BY timestamp_ms
            """
        ),
        {"video_id": video_id},
    )

    timestamps = [row[0] for row in result]

    logger.debug(f"Collected {len(timestamps)} unique timestamps for video {video_id}")

    return timestamps


def filter_existing_thumbnails(
    video_id: str, timestamps: list[int]
) -> tuple[list[int], list[int]]:
    """Filter timestamps to identify which thumbnails need generation.

    Checks the filesystem for existing thumbnail files and separates timestamps
    into those that need generation and those that can be skipped. This enables
    idempotent thumbnail generation - running the task multiple times will not
    regenerate existing thumbnails.

    Args:
        video_id: Unique identifier for the video
        timestamps: List of timestamps in milliseconds to check

    Returns:
        A tuple of (timestamps_to_generate, timestamps_skipped):
        - timestamps_to_generate: Timestamps that don't have thumbnails yet
        - timestamps_skipped: Timestamps that already have thumbnails on disk

    Requirements:
        - 1.3: Skip thumbnail generation for timestamps that already have a thumbnail
        - 2.2: Skip extraction for timestamps where thumbnail file already exists
        - 2.3: Log the count of skipped vs newly generated thumbnails

    Example:
        >>> to_generate, skipped = filter_existing_thumbnails(
        ...     "video-123", [0, 5000, 10000]
        ... )
        >>> print(f"To generate: {to_generate}, Skipped: {skipped}")
        To generate: [5000, 10000], Skipped: [0]
    """
    timestamps_to_generate: list[int] = []
    timestamps_skipped: list[int] = []

    for timestamp_ms in timestamps:
        thumbnail_path = get_thumbnail_path(video_id, timestamp_ms)

        if thumbnail_path.exists():
            timestamps_skipped.append(timestamp_ms)
        else:
            timestamps_to_generate.append(timestamp_ms)

    # Log the counts for visibility into idempotent behavior
    logger.info(
        f"Thumbnail filter for video {video_id}: "
        f"to_generate={len(timestamps_to_generate)}, "
        f"skipped={len(timestamps_skipped)}, "
        f"total={len(timestamps)}"
    )

    return timestamps_to_generate, timestamps_skipped


class ThumbnailGenerationStats:
    """Statistics from thumbnail generation process.

    Attributes:
        generated: Number of thumbnails successfully generated
        skipped: Number of thumbnails skipped (already existed)
        failed: Number of thumbnails that failed to generate
        total_timestamps: Total number of timestamps processed
    """

    def __init__(
        self,
        generated: int = 0,
        skipped: int = 0,
        failed: int = 0,
        total_timestamps: int = 0,
    ):
        self.generated = generated
        self.skipped = skipped
        self.failed = failed
        self.total_timestamps = total_timestamps

    def to_dict(self) -> dict:
        """Convert stats to dictionary for JSON serialization."""
        return {
            "generated": self.generated,
            "skipped": self.skipped,
            "failed": self.failed,
            "total_timestamps": self.total_timestamps,
        }


def generate_thumbnails_idempotent(
    video_id: str,
    video_path: str,
    timestamps: list[int],
    extract_frame_fn: Callable[[str, int, Path], bool] | None = None,
) -> ThumbnailGenerationStats:
    """Orchestrate idempotent thumbnail generation for a list of timestamps.

    This is the main orchestration function for thumbnail generation. It:
    1. Ensures the output directory exists
    2. Filters out timestamps that already have thumbnails (idempotent)
    3. Calls the frame extraction function for each missing thumbnail
    4. Tracks and returns generation statistics

    The function is idempotent - running it multiple times with the same
    inputs will not regenerate existing thumbnails, making it safe to
    retry failed tasks or re-run after partial completion.

    Args:
        video_id: Unique identifier for the video
        video_path: Path to the video file for frame extraction
        timestamps: List of timestamps in milliseconds to generate thumbnails for
        extract_frame_fn: Optional function to extract a frame. If None,
            thumbnails are not extracted (useful for testing).
            The function signature should be:
            extract_frame_fn(video_path: str, timestamp_ms: int,
            output_path: Path) -> bool

    Returns:
        ThumbnailGenerationStats with counts of generated, skipped, failed,
        and total timestamps processed.

    Requirements:
        - 1.3: Skip thumbnail generation for timestamps that already have a thumbnail
        - 2.2: Skip extraction for timestamps where thumbnail file already exists
        - 2.3: Log the count of skipped vs newly generated thumbnails

    Example:
        >>> stats = generate_thumbnails_idempotent(
        ...     "video-123",
        ...     "/data/videos/video-123.mp4",
        ...     [0, 5000, 10000, 15000],
        ...     extract_frame_fn=extract_frame_with_ffmpeg,
        ... )
        >>> print(f"Generated: {stats.generated}, Skipped: {stats.skipped}")
        Generated: 2, Skipped: 2
    """
    # Ensure output directory exists
    ensure_thumbnail_directory(video_id)

    # Filter to find which thumbnails need generation (idempotent check)
    timestamps_to_generate, timestamps_skipped = filter_existing_thumbnails(
        video_id, timestamps
    )

    # Initialize stats
    stats = ThumbnailGenerationStats(
        skipped=len(timestamps_skipped),
        total_timestamps=len(timestamps),
    )

    # If no extraction function provided, just return stats with what would be generated
    # This is useful for dry-run or testing scenarios
    if extract_frame_fn is None:
        logger.info(
            f"No extract_frame_fn provided for video {video_id}. "
            f"Would generate {len(timestamps_to_generate)} thumbnails."
        )
        return stats

    # Generate thumbnails for each missing timestamp
    for timestamp_ms in timestamps_to_generate:
        output_path = get_thumbnail_path(video_id, timestamp_ms)

        try:
            success = extract_frame_fn(video_path, timestamp_ms, output_path)
            if success:
                stats.generated += 1
            else:
                stats.failed += 1
                logger.warning(
                    f"Frame extraction returned False for {video_id} "
                    f"at {timestamp_ms}ms"
                )
        except Exception as e:
            stats.failed += 1
            logger.error(
                f"Failed to extract thumbnail for {video_id} "
                f"at {timestamp_ms}ms: {e}"
            )

    # Log final summary
    logger.info(
        f"Thumbnail generation complete for video {video_id}: "
        f"generated={stats.generated}, skipped={stats.skipped}, "
        f"failed={stats.failed}, total={stats.total_timestamps}"
    )

    return stats

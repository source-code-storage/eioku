"""Scene detection service using FFmpeg."""

import re
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from ..domain.models import Scene
from ..utils.print_logger import get_logger

logger = get_logger(__name__)


class SceneDetectionError(Exception):
    """Exception raised when scene detection fails."""

    pass


class SceneDetectionService:
    """Service for detecting scenes in videos using FFmpeg."""

    def __init__(
        self,
        threshold: float = 0.4,
        min_scene_len: float = 0.6,
    ):
        """Initialize scene detection service.

        Args:
            threshold: Detection threshold (0.0-1.0, lower = more sensitive)
            min_scene_len: Minimum scene length in seconds
        """
        self.threshold = threshold
        self.min_scene_len = min_scene_len

    def detect_scenes(self, video_path: str, video_id: str) -> list[Scene]:
        """Detect scenes in a video file using FFmpeg.

        Args:
            video_path: Path to the video file
            video_id: ID of the video being processed

        Returns:
            List of Scene domain models

        Raises:
            SceneDetectionError: If scene detection fails
        """
        if not Path(video_path).exists():
            raise SceneDetectionError(f"Video file not found: {video_path}")

        logger.info(f"Detecting scenes in video: {video_path}")

        try:
            # Get video duration first
            duration = self._get_video_duration(video_path)
            logger.info(f"Video duration: {duration:.2f}s")

            # Detect scene changes using FFmpeg
            scene_timestamps = self._detect_scene_changes(video_path)
            logger.info(f"Found {len(scene_timestamps)} scene changes")

            # Convert timestamps to scenes
            scenes = self._create_scenes_from_timestamps(
                scene_timestamps, duration, video_id
            )

            # Filter scenes by minimum length
            scenes = [s for s in scenes if (s.end - s.start) >= self.min_scene_len]

            logger.info(
                f"Detected {len(scenes)} scenes in video {video_id} "
                f"(duration: {duration:.2f}s)"
            )

            return scenes

        except subprocess.CalledProcessError as e:
            error_msg = f"FFmpeg failed for {video_path}: {e.stderr}"
            logger.error(error_msg)
            raise SceneDetectionError(error_msg)
        except Exception as e:
            error_msg = f"Scene detection failed for {video_path}: {e}"
            logger.error(error_msg)
            raise SceneDetectionError(error_msg)

    def _get_video_duration(self, video_path: str) -> float:
        """Get video duration using ffprobe.

        Args:
            video_path: Path to video file

        Returns:
            Duration in seconds
        """
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        return float(result.stdout.strip())

    def _detect_scene_changes(self, video_path: str) -> list[float]:
        """Detect scene changes using FFmpeg's scene detection filter.

        Args:
            video_path: Path to video file

        Returns:
            List of timestamps where scenes change
        """
        cmd = [
            "ffmpeg",
            "-i",
            video_path,
            "-filter:v",
            f"select='gt(scene\\,{self.threshold})',showinfo",
            "-f",
            "null",
            "-",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        # Parse timestamps from stderr (ffmpeg outputs to stderr)
        timestamps = []
        # Look for lines like: "pts_time:1.234"
        for line in result.stderr.split("\n"):
            if "pts_time:" in line:
                match = re.search(r"pts_time:(\d+\.?\d*)", line)
                if match:
                    timestamp = float(match.group(1))
                    timestamps.append(timestamp)

        return sorted(timestamps)

    def _create_scenes_from_timestamps(
        self, timestamps: list[float], duration: float, video_id: str
    ) -> list[Scene]:
        """Create Scene objects from scene change timestamps.

        Args:
            timestamps: List of scene change timestamps
            duration: Total video duration
            video_id: Video ID

        Returns:
            List of Scene domain models
        """
        scenes = []

        # If no scene changes detected, treat entire video as one scene
        if not timestamps:
            scene = Scene(
                scene_id=str(uuid.uuid4()),
                video_id=video_id,
                scene=1,
                start=0.0,
                end=duration,
                thumbnail_path=None,
                created_at=datetime.utcnow(),
            )
            scenes.append(scene)
            return scenes

        # Create scenes from timestamps
        # First scene: 0 to first timestamp
        scene = Scene(
            scene_id=str(uuid.uuid4()),
            video_id=video_id,
            scene=1,
            start=0.0,
            end=timestamps[0],
            thumbnail_path=None,
            created_at=datetime.utcnow(),
        )
        scenes.append(scene)

        # Middle scenes: between timestamps
        for i in range(len(timestamps) - 1):
            scene = Scene(
                scene_id=str(uuid.uuid4()),
                video_id=video_id,
                scene=i + 2,
                start=timestamps[i],
                end=timestamps[i + 1],
                thumbnail_path=None,
                created_at=datetime.utcnow(),
            )
            scenes.append(scene)

        # Last scene: last timestamp to end
        scene = Scene(
            scene_id=str(uuid.uuid4()),
            video_id=video_id,
            scene=len(timestamps) + 1,
            start=timestamps[-1],
            end=duration,
            thumbnail_path=None,
            created_at=datetime.utcnow(),
        )
        scenes.append(scene)

        return scenes

    def get_scene_info(self, scenes: list[Scene]) -> dict:
        """Get summary information about detected scenes.

        Args:
            scenes: List of Scene models

        Returns:
            Dictionary with scene statistics
        """
        if not scenes:
            return {
                "scene_count": 0,
                "total_duration": 0.0,
                "avg_scene_length": 0.0,
                "min_scene_length": 0.0,
                "max_scene_length": 0.0,
            }

        durations = [scene.get_duration() for scene in scenes]

        return {
            "scene_count": len(scenes),
            "total_duration": scenes[-1].end if scenes else 0.0,
            "avg_scene_length": sum(durations) / len(durations),
            "min_scene_length": min(durations),
            "max_scene_length": max(durations),
        }

from abc import ABC, abstractmethod

from ..domain.models import Scene, Transcription, Video


class VideoRepository(ABC):
    """Abstract repository interface for Video persistence."""

    @abstractmethod
    def save(self, video: Video) -> Video:
        """Save video to persistence layer."""
        pass

    @abstractmethod
    def find_by_id(self, video_id: str) -> Video | None:
        """Find video by ID."""
        pass

    @abstractmethod
    def find_by_path(self, file_path: str) -> Video | None:
        """Find video by file path."""
        pass

    @abstractmethod
    def find_by_status(self, status: str) -> list[Video]:
        """Find videos by status."""
        pass

    @abstractmethod
    def delete(self, video_id: str) -> bool:
        """Delete video by ID."""
        pass


class TranscriptionRepository(ABC):
    """Abstract repository interface for Transcription persistence."""

    @abstractmethod
    def save(self, transcription: Transcription) -> Transcription:
        """Save transcription to persistence layer."""
        pass

    @abstractmethod
    def find_by_video_id(self, video_id: str) -> list[Transcription]:
        """Find all transcriptions for a video."""
        pass

    @abstractmethod
    def find_by_time_range(
        self, video_id: str, start: float, end: float
    ) -> list[Transcription]:
        """Find transcriptions within time range."""
        pass

    @abstractmethod
    def delete_by_video_id(self, video_id: str) -> bool:
        """Delete all transcriptions for a video."""
        pass


class SceneRepository(ABC):
    """Abstract repository interface for Scene persistence."""

    @abstractmethod
    def save(self, scene: Scene) -> Scene:
        """Save scene to persistence layer."""
        pass

    @abstractmethod
    def find_by_video_id(self, video_id: str) -> list[Scene]:
        """Find all scenes for a video."""
        pass

    @abstractmethod
    def find_by_scene_number(self, video_id: str, scene_number: int) -> Scene | None:
        """Find scene by number within a video."""
        pass

    @abstractmethod
    def delete_by_video_id(self, video_id: str) -> bool:
        """Delete all scenes for a video."""
        pass

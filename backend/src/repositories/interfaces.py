from abc import ABC, abstractmethod

from ..domain.models import Video


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

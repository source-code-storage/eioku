from datetime import datetime


class Video:
    """Domain model for Video - pure business object."""

    def __init__(
        self,
        video_id: str,
        file_path: str,
        filename: str,
        last_modified: datetime,
        status: str = "pending",
        file_hash: str | None = None,
        duration: float | None = None,
        file_size: int | None = None,
        processed_at: datetime | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ):
        self.video_id = video_id
        self.file_path = file_path
        self.filename = filename
        self.last_modified = last_modified
        self.status = status
        self.file_hash = file_hash
        self.duration = duration
        self.file_size = file_size
        self.processed_at = processed_at
        self.created_at = created_at
        self.updated_at = updated_at

    def is_processed(self) -> bool:
        """Check if video has been processed."""
        return self.status == "completed"

    def mark_as_processing(self) -> None:
        """Mark video as currently being processed."""
        self.status = "processing"

    def mark_as_completed(self, processed_at: datetime) -> None:
        """Mark video as processing completed."""
        self.status = "completed"
        self.processed_at = processed_at

    def mark_as_failed(self) -> None:
        """Mark video processing as failed."""
        self.status = "failed"

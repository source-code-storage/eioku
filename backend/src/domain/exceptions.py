"""Domain exceptions for the application."""


class GlobalJumpError(Exception):
    """Base exception for global jump navigation errors."""

    pass


class VideoNotFoundError(GlobalJumpError):
    """Raised when a requested video does not exist.

    Attributes:
        video_id: The video ID that was not found
    """

    def __init__(self, video_id: str):
        self.video_id = video_id
        super().__init__(f"Video not found: {video_id}")


class InvalidParameterError(GlobalJumpError):
    """Raised when an invalid parameter is provided to a global jump query.

    Attributes:
        parameter: Name of the invalid parameter
        message: Description of the validation error
    """

    def __init__(self, parameter: str, message: str):
        self.parameter = parameter
        self.message = message
        super().__init__(f"Invalid parameter '{parameter}': {message}")

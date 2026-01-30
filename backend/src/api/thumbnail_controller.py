"""API controller for serving thumbnail images."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/thumbnails", tags=["thumbnails"])

THUMBNAIL_DIR = Path("/thumbnails")
CACHE_MAX_AGE = 604800  # 1 week in seconds


@router.get("/{video_id}/{timestamp_ms}")
async def get_thumbnail(video_id: str, timestamp_ms: int) -> FileResponse:
    """
    Serve a thumbnail image for a specific video timestamp.

    Returns WebP image with cache headers for browser caching.

    Args:
        video_id: The unique identifier of the video
        timestamp_ms: The timestamp in milliseconds

    Returns:
        FileResponse with the WebP thumbnail image

    Raises:
        HTTPException: 404 if thumbnail not found
    """
    thumbnail_path = THUMBNAIL_DIR / video_id / f"{timestamp_ms}.webp"

    if not thumbnail_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")

    return FileResponse(
        thumbnail_path,
        media_type="image/webp",
        headers={
            "Cache-Control": f"public, max-age={CACHE_MAX_AGE}",
        },
    )

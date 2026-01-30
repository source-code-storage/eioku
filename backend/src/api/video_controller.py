import asyncio
import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..api.schemas import VideoCreateSchema, VideoResponseSchema, VideoUpdateSchema
from ..database.connection import get_db
from ..domain.models import Task, Video
from ..repositories.task_repository import SQLAlchemyTaskRepository
from ..repositories.video_repository import SqlVideoRepository
from ..services.job_producer import JobProducer
from ..services.video_service import VideoService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/videos", tags=["videos"])


def get_video_service(session: Session = Depends(get_db)) -> VideoService:
    """Dependency injection for VideoService."""
    repository = SqlVideoRepository(session)
    return VideoService(repository)


@router.post(
    "/", response_model=VideoResponseSchema, status_code=status.HTTP_201_CREATED
)
async def create_video(
    video_data: VideoCreateSchema, service: VideoService = Depends(get_video_service)
) -> VideoResponseSchema:
    """Create a new video for processing."""
    try:
        # Convert schema to domain model
        domain_video = Video(
            video_id=video_data.video_id,
            file_path=video_data.file_path,
            filename=video_data.filename,
            file_hash=video_data.file_hash,
            last_modified=video_data.last_modified,
            duration=video_data.duration,
            file_size=video_data.file_size,
        )

        created_video = service.create_video(domain_video)
        return VideoResponseSchema.model_validate(created_video.__dict__)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/{video_id}", response_model=VideoResponseSchema)
async def get_video(
    video_id: str, service: VideoService = Depends(get_video_service)
) -> VideoResponseSchema:
    """Get video by ID."""
    video = service.get_video(video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
        )

    return VideoResponseSchema.model_validate(video.__dict__)


@router.get("/", response_model=list[VideoResponseSchema])
async def list_videos(
    status: str = None, service: VideoService = Depends(get_video_service)
) -> list[VideoResponseSchema]:
    """List videos, optionally filtered by status."""
    if status:
        videos = service.get_videos_by_status(status)
    else:
        # Return all videos
        videos = service.get_all_videos()

    return [VideoResponseSchema.model_validate(video.__dict__) for video in videos]


@router.patch("/{video_id}", response_model=VideoResponseSchema)
async def update_video(
    video_id: str,
    update_data: VideoUpdateSchema,
    service: VideoService = Depends(get_video_service),
) -> VideoResponseSchema:
    """Update video metadata."""
    if update_data.status:
        video = service.update_video_status(video_id, update_data.status)
    else:
        video = service.get_video(video_id)

    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
        )

    return VideoResponseSchema.model_validate(video.__dict__)


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(
    video_id: str, service: VideoService = Depends(get_video_service)
) -> None:
    """Delete video."""
    success = service.delete_video(video_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
        )


@router.get("/{video_id}/stream")
async def stream_video(
    video_id: str,
    service: VideoService = Depends(get_video_service),
):
    """Stream video file."""
    import os

    from fastapi.responses import FileResponse

    video = service.get_video(video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
        )

    file_path = video.file_path
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found"
        )

    return FileResponse(
        file_path,
        media_type="video/mp4",
        headers={"Accept-Ranges": "bytes"},
    )


@router.get("/{video_id}/location", response_model=dict)
async def get_video_location(
    video_id: str, service: VideoService = Depends(get_video_service)
) -> dict:
    """Get location information for a video from the video_locations projection."""
    location = service.get_video_location(video_id)
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No location data available for this video",
        )
    return location


@router.get("/{video_id}/clip")
async def download_clip(
    video_id: str,
    start_ms: int = Query(..., ge=0, description="Start timestamp in milliseconds"),
    end_ms: int = Query(..., ge=0, description="End timestamp in milliseconds"),
    buffer_ms: int = Query(
        2000, ge=0, le=10000, description="Buffer time before/after in ms"
    ),
    service: VideoService = Depends(get_video_service),
) -> StreamingResponse:
    """
    Export a video clip between the specified timestamps.

    Uses ffmpeg with stream copy (-c copy) for fast extraction.

    Args:
        video_id: ID of the video to extract from
        start_ms: Start timestamp in milliseconds
        end_ms: End timestamp in milliseconds
        buffer_ms: Additional buffer time before start and after end (default 2000ms)

    Returns:
        StreamingResponse with video/mp4 content type

    Raises:
        404: Video not found or video file not found on disk
        400: Invalid timestamp range (end_ms <= start_ms)
    """
    # Validate video exists
    video = service.get_video(video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
        )

    # Validate video file exists on disk
    if not os.path.exists(video.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found on disk"
        )

    # Validate timestamp range
    if end_ms <= start_ms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_ms must be greater than start_ms",
        )

    # Apply buffer (clamp to valid range)
    actual_start_ms = max(0, start_ms - buffer_ms)
    actual_end_ms = end_ms + buffer_ms

    # Convert to seconds for ffmpeg
    start_sec = actual_start_ms / 1000
    duration_sec = (actual_end_ms - actual_start_ms) / 1000

    # Generate filename
    start_fmt = f"{int(start_sec // 60)}m{int(start_sec % 60)}s"
    end_sec = actual_end_ms / 1000
    end_fmt = f"{int(end_sec // 60)}m{int(end_sec % 60)}s"
    base_name = os.path.splitext(video.filename)[0]
    clip_filename = f"{base_name}_{start_fmt}-{end_fmt}.mp4"

    # Build ffmpeg command
    # -ss before -i for fast seeking
    # -c copy for stream copy (fast, keyframe-aligned)
    # -movflags frag_keyframe+empty_moov for streaming output
    cmd = [
        "ffmpeg",
        "-ss",
        str(start_sec),
        "-i",
        video.file_path,
        "-t",
        str(duration_sec),
        "-c",
        "copy",
        "-movflags",
        "frag_keyframe+empty_moov",
        "-f",
        "mp4",
        "pipe:1",
    ]

    async def stream_output():
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        while True:
            chunk = await process.stdout.read(65536)  # 64KB chunks
            if not chunk:
                break
            yield chunk

        # Wait for process to complete
        await process.wait()
        if process.returncode != 0:
            stderr = await process.stderr.read()
            logger.error(f"FFmpeg failed: {stderr.decode()}")

    return StreamingResponse(
        stream_output(),
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{clip_filename}"'},
    )


# ============================================================================
# Task Creation Models
# ============================================================================


class CreateTaskRequest(BaseModel):
    """Request model for creating a task."""

    task_type: str = Field(
        ...,
        description="Type of task to create",
        example="thumbnail.extraction",
    )

    class Config:
        json_schema_extra = {"example": {"task_type": "thumbnail.extraction"}}


class CreateTaskResponse(BaseModel):
    """Response model for task creation."""

    task_id: str = Field(..., description="The unique identifier of the created task")
    video_id: str = Field(..., description="The video ID associated with this task")
    task_type: str = Field(
        ..., description="Type of task", example="thumbnail.extraction"
    )
    status: str = Field(..., description="Task status", example="pending")
    job_id: str | None = Field(
        None, description="Job ID in Redis if enqueued (format: ml_{task_id})"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "video_id": "550e8400-e29b-41d4-a716-446655440001",
                "task_type": "thumbnail.extraction",
                "status": "pending",
                "job_id": "ml_550e8400-e29b-41d4-a716-446655440000",
            }
        }


# ============================================================================
# Task Creation Endpoint
# ============================================================================


@router.post(
    "/{video_id}/tasks",
    response_model=CreateTaskResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Video not found"},
        409: {"description": "Task already exists for this video"},
        500: {"description": "Internal server error"},
    },
    summary="Create and enqueue a task for a video",
    description=(
        "Create a new task for the specified video and enqueue it for processing."
    ),
)
async def create_video_task(
    video_id: str,
    request: CreateTaskRequest,
    db: Session = Depends(get_db),
) -> CreateTaskResponse:
    """Create and enqueue a task for a video.

    Creates a new task record and enqueues it to the job queue for processing.
    If a task of the same type already exists for this video (in pending/running
    status), returns 409 Conflict.
    """
    try:
        video_repo = SqlVideoRepository(db)
        task_repo = SQLAlchemyTaskRepository(db)

        # Verify video exists
        video = video_repo.find_by_id(video_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video {video_id} not found",
            )

        # Check if task already exists (pending or running)
        existing_tasks = task_repo.find_by_video_and_type(video_id, request.task_type)
        active_task = next(
            (t for t in existing_tasks if t.status in ("pending", "running")),
            None,
        )
        if active_task:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Task {request.task_type} already exists for video "
                f"(status: {active_task.status})",
            )

        # Create new task
        task_id = str(uuid.uuid4())
        task = Task(
            task_id=task_id,
            video_id=video_id,
            task_type=request.task_type,
            status="pending",
            priority=1,
        )
        task_repo.save(task)

        logger.info(
            f"Created task {task_id} ({request.task_type}) for video {video_id}"
        )

        # Enqueue the task
        job_id = None
        try:
            job_producer = JobProducer()
            await job_producer.initialize()

            try:
                # Get default config for task type
                from ..services.video_discovery_service import VideoDiscoveryService

                discovery_service = VideoDiscoveryService(None, video_repo)
                config = discovery_service._get_default_config(request.task_type)

                job_id = await job_producer.enqueue_task(
                    task_id=task_id,
                    task_type=request.task_type,
                    video_id=video_id,
                    video_path=video.file_path,
                    config=config,
                )
                logger.info(f"Enqueued task {task_id} with job_id {job_id}")

            finally:
                await job_producer.close()

        except Exception as e:
            # Task created but enqueue failed - log but don't fail
            # Task can be manually enqueued later via POST /tasks/{task_id}/enqueue
            logger.warning(f"Task {task_id} created but enqueue failed: {e}")

        return CreateTaskResponse(
            task_id=task_id,
            video_id=video_id,
            task_type=request.task_type,
            status="pending",
            job_id=job_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create task for video {video_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create task: {str(e)}",
        )

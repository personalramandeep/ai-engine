import threading
from fastapi import APIRouter, HTTPException
from src.api.schemas.request import AnalyzeRequest
from src.api.schemas.response import AnalyzeAccepted
from src.utils.logger import get_logger
from src.utils.file_handler import resolve_video_path
from src.utils.webhook import notify_success, notify_failure
from src.pipeline.processor import process_video

router = APIRouter()
logger = get_logger("api.routes.analyze")


def _run_pipeline(post_id: str, video_id: str, user_id: str, local_path: str, file_path: str, record_angle: str):
    try:
        result = process_video(local_path, file_path, record_angle, user_id, video_id)
        notify_success(post_id, result)
    except BaseException as e:
        logger.error(f"Pipeline failed post={post_id} video={video_id}: {e}")
        notify_failure(post_id, str(e))


@router.post(
    "/analyze",
    response_model=AnalyzeAccepted,
    status_code=202,
    summary="Analyze badminton video",
    description="Starts video analysis in the background. Results are delivered via webhook.",
    responses={
        202: {"description": "Analysis started"},
        404: {"description": "Video file not found"},
        500: {"description": "Failed to resolve video path"},
    }
)
def analyze_video(request: AnalyzeRequest):
    logger.info(f"=== API: /analyze === user={request.userId} video={request.videoId} post={request.postId} angle={request.recordAngle} path={request.filePath}")

    try:
        logger.info(f"=== Phase: Resolving File === {request.filePath}")
        local_path = resolve_video_path(request.filePath)
    except FileNotFoundError as e:
        logger.error(str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

    threading.Thread(
        target=_run_pipeline,
        args=(request.postId, request.videoId, request.userId, local_path, request.filePath, request.recordAngle.value),
        daemon=False,
    ).start()

    logger.info(f"Analysis started post={request.postId} video={request.videoId}")
    return AnalyzeAccepted(postId=request.postId, videoId=request.videoId)

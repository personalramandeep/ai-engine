import io
import cv2
import tempfile
from pathlib import Path
from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("frame_store")


def save_heatmap(heatmap_img, user_id: str, video_id: str, input_bucket: str = None) -> str:
    """Save heatmap image locally or to S3. Returns path."""
    filename = "heatmap.jpg"
    if settings.ENV == "prod":
        return _upload_heatmap_to_s3(heatmap_img, user_id, video_id, filename, input_bucket)
    else:
        folder = settings.STATIC_DIR / video_id / "heatmap"
        folder.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(folder / filename), heatmap_img)
        logger.info(f"Heatmap saved locally: {folder / filename}")
        return str(folder / filename)


def save_shot_frame(frame, video_id: str, shot_type: str, frame_num: int) -> str:
    """Save shot frame locally or to S3. Returns full path without bucket."""
    filename = f"frame_{frame_num:05d}.jpg"
    if settings.ENV == "prod":
        _upload_to_s3(frame, video_id, shot_type, filename)
        return f"{video_id}/{shot_type}/{filename}"
    else:
        _save_locally(frame, video_id, shot_type, filename)
        return f"static/{video_id}/{shot_type}/{filename}"


def _save_locally(frame, video_id: str, shot_type: str, filename: str):
    """Save frame to static/{video_id}/{shot_type}/filename"""
    folder = settings.STATIC_DIR / video_id / shot_type
    folder.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(folder / filename), frame, [cv2.IMWRITE_JPEG_QUALITY, 97])
    logger.debug(f"Frame saved locally: {folder / filename}")


def _upload_heatmap_to_s3(frame, user_id: str, video_id: str, filename: str, input_bucket: str) -> str:
    """Upload heatmap to {input_bucket}/videos/{user_id}/{video_id}/heatmap.jpg"""
    import boto3

    key = f"videos/{user_id}/{video_id}/{filename}"
    logger.info(f"Uploading heatmap to S3: s3://{input_bucket}/{key}")

    _, tmp_path = tempfile.mkstemp(suffix=".jpg")
    cv2.imwrite(tmp_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 97])

    boto3.client("s3").upload_file(tmp_path, input_bucket, key, ExtraArgs={"ContentType": "image/jpeg"})
    Path(tmp_path).unlink(missing_ok=True)

    logger.info(f"Heatmap uploaded: s3://{input_bucket}/{key}")
    return key


def _upload_to_s3(frame, video_id: str, shot_type: str, filename: str):
    """Upload frame to S3 at {S3_BUCKET}/{video_id}/{shot_type}/filename"""
    import boto3

    key = f"{video_id}/{shot_type}/{filename}"
    logger.debug(f"Uploading frame to S3: {key}")

    _, tmp_path = tempfile.mkstemp(suffix=".jpg")
    cv2.imwrite(tmp_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 97])

    boto3.client("s3").upload_file(tmp_path, settings.S3_BUCKET, key, ExtraArgs={"ContentType": "image/jpeg"})
    Path(tmp_path).unlink(missing_ok=True)

    logger.debug(f"Frame uploaded to S3: s3://{settings.S3_BUCKET}/{key}")

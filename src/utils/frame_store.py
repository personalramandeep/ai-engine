import io
import cv2
import tempfile
from pathlib import Path
from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("frame_store")


def save_heatmap(heatmap_img, user_id: str, video_id: str, input_bucket: str = None) -> str:
    """Save heatmap image locally or to GCS. Returns path."""
    filename = "heatmap.jpg"
    if settings.ENV == "prod":
        return _upload_heatmap_to_gcs(heatmap_img, user_id, video_id, filename, input_bucket)
    else:
        folder = settings.STATIC_DIR / video_id / "heatmap"
        folder.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(folder / filename), heatmap_img)
        logger.info(f"Heatmap saved locally: {folder / filename}")
        return str(folder / filename)


def save_shot_frame(frame, video_id: str, shot_type: str, frame_num: int) -> str:
    """Save shot frame locally or to GCS. Returns full path without bucket."""
    filename = f"frame_{frame_num:05d}.jpg"
    if settings.ENV == "prod":
        _upload_to_gcs(frame, video_id, shot_type, filename)
        return f"{video_id}/{shot_type}/{filename}"
    else:
        _save_locally(frame, video_id, shot_type, filename)
        return f"static/{video_id}/{shot_type}/{filename}"


def _save_locally(frame, video_id: str, shot_type: str, filename: str) -> str:
    """Save frame to static/{video_id}/{shot_type}/filename"""
    folder = settings.STATIC_DIR / video_id / shot_type
    folder.mkdir(parents=True, exist_ok=True)
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, 97]
    cv2.imwrite(str(folder / filename), frame, encode_params)
    logger.debug(f"Frame saved locally: {folder / filename}")


def _upload_heatmap_to_gcs(frame, user_id: str, video_id: str, filename: str, input_bucket: str) -> str:
    """Upload heatmap to {input_bucket}/videos/{user_id}/{video_id}/heatmap.jpg"""
    try:
        from google.cloud import storage
    except ImportError:
        raise RuntimeError("google-cloud-storage is required for prod env.")

    blob_path = f"videos/{user_id}/{video_id}/{filename}"
    logger.info(f"Uploading heatmap to GCS: gs://{input_bucket}/{blob_path}")

    _, tmp_path = tempfile.mkstemp(suffix=".jpg")
    cv2.imwrite(tmp_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 97])

    client = storage.Client()
    bucket = client.bucket(input_bucket)
    blob = bucket.blob(blob_path)
    blob.upload_from_filename(tmp_path, content_type="image/jpeg")
    Path(tmp_path).unlink(missing_ok=True)

    gcs_uri = f"videos/{user_id}/{video_id}/{filename}"
    logger.info(f"Heatmap uploaded: gs://{input_bucket}/{gcs_uri}")
    return gcs_uri


def _upload_to_gcs(frame, video_id: str, shot_type: str, filename: str) -> str:
    """Upload frame to GCS at {bucket}/{video_id}/{shot_type}/filename"""
    try:
        from google.cloud import storage
    except ImportError:
        raise RuntimeError("google-cloud-storage is required for prod env. Run: pip install google-cloud-storage")

    blob_path = f"{video_id}/{shot_type}/{filename}"
    logger.debug(f"Uploading frame to GCS: {blob_path}")

    _, tmp_path = tempfile.mkstemp(suffix=".jpg")
    cv2.imwrite(tmp_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 97])

    client = storage.Client()
    bucket = client.bucket(settings.GCS_BUCKET)
    blob = bucket.blob(blob_path)
    blob.upload_from_filename(tmp_path, content_type="image/jpeg")

    Path(tmp_path).unlink(missing_ok=True)

    gcs_uri = f"gs://{settings.GCS_BUCKET}/{blob_path}"
    logger.debug(f"Frame uploaded to GCS: {gcs_uri}")
    return gcs_uri

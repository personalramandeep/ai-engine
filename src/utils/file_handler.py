import tempfile
from pathlib import Path
from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("file_handler")

def resolve_video_path(file_path: str) -> str:
    """Resolve file path based on ENV. Returns local path to the video file."""
    if settings.ENV == "prod":
        return _download_from_gcs(file_path)
    else:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Video not found at local path: {file_path}")
        logger.info(f"Using local file: {file_path}")
        return str(path)

def _download_from_gcs(gcs_path: str) -> str:
    """Download file from GCS bucket to a temp file and return local path."""
    try:
        from google.cloud import storage
    except ImportError:
        raise RuntimeError("google-cloud-storage is required for prod env. Run: pip install google-cloud-storage")

    logger.info(f"=== Phase: Downloading from GCS === {gcs_path}")

    # filePath format: bucket-name/path/to/file.mp4
    if gcs_path.startswith("gs://"):
        gcs_path = gcs_path[5:]

    bucket_name, blob_path = gcs_path.split("/", 1)

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)

    suffix = Path(blob_path).suffix
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    blob.download_to_filename(tmp.name)

    logger.info(f"Downloaded GCS file to temp: {tmp.name}")
    return tmp.name

import tempfile
from pathlib import Path
from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("file_handler")

def resolve_video_path(file_path: str) -> str:
    """Resolve file path based on ENV. Returns local path to the video file."""
    if settings.ENV == "prod":
        return _download_from_s3(file_path)
    else:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Video not found at local path: {file_path}")
        logger.info(f"Using local file: {file_path}")
        return str(path)

def _download_from_s3(s3_path: str) -> str:
    """Download file from S3 to a temp file and return local path."""
    import boto3

    logger.info(f"=== Phase: Downloading from S3 === {s3_path}")

    # filePath format: s3://bucket/key  or  bucket/key
    if s3_path.startswith("s3://"):
        s3_path = s3_path[5:]

    bucket_name, key = s3_path.split("/", 1)

    suffix = Path(key).suffix
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)

    boto3.client("s3").download_file(bucket_name, key, tmp.name)

    logger.info(f"Downloaded S3 file to temp: {tmp.name}")
    return tmp.name

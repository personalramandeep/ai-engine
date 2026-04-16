import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "Kreeda AI Engine"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"

    ENV: str = "local"  # local | prod
    S3_BUCKET: str = ""

    DATA_DIR: Path = BASE_DIR / "data"
    RAW_DATA_DIR: Path = DATA_DIR / "raw"
    PROCESSED_DATA_DIR: Path = DATA_DIR / "processed"
    MODELS_DIR: Path = BASE_DIR / "models" / "weights"
    OUTPUT_DIR: Path = BASE_DIR / "outputs"
    STATIC_DIR: Path = BASE_DIR / "static"
    LOGS_DIR: Path = BASE_DIR / "logs"

    YOLO_MODEL: str = "yolov8n.pt"
    SHUTTLE_SHOT_MODEL: str = "shuttleAndShotDetector.pt"

    CONFIDENCE_THRESHOLD: float = 0.5
    SHOT_COOLDOWN_FRAMES: int = 10

    VIDEO_FPS: int = 30

    WEBHOOK_BASE_URL: str = "https://backend-service-87645406452.asia-south1.run.app"
    HMAC_SECRET: str = "995b37b2ccc9e293eca0b0ff3e070b6d4fd9cbd6335f4b81cda03cc2c02bd5c6"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

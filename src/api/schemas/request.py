from pydantic import BaseModel, Field
from src.api.enums.record_angle import RecordAngle

class AnalyzeRequest(BaseModel):
    userId: str = Field(..., description="Unique user identifier", example="user-uuid")
    videoId: str = Field(..., description="Unique video identifier", example="video-uuid")
    postId: str = Field(..., description="Post identifier used for webhook callback", example="post-uuid")
    filePath: str = Field(..., description="Local file path (local env) or S3 path as bucket-name/path/to/file.mp4 (prod)", example="my-bucket/videos/match.mp4")
    recordAngle: RecordAngle = Field(..., description="Camera angle used during recording", example="backcourt")
    webhookBaseUrl: str | None = Field(None, description="Override webhook host. Falls back to default if null.", example="https://my-backend.com")

from pydantic import BaseModel, Field
from typing import List
from src.api.enums.record_angle import RecordAngle

class AnalyzeAccepted(BaseModel):
    message: str = Field(default="Analysis started")
    postId: str
    videoId: str

class AnalyzeResponse(BaseModel):
    userId: str = Field(..., description="Unique user identifier")
    videoId: str = Field(..., description="Unique video identifier")
    recordAngle: RecordAngle = Field(..., description="Camera angle used during recording")
    totalFrames: int = Field(..., description="Total frames processed")
    shuttleDetections: int = Field(..., description="Total frames where shuttle was detected")
    smashCount: int = Field(..., description="Number of smash shots detected")
    defenceCount: int = Field(..., description="Number of defence shots detected")
    serveCount: int = Field(..., description="Number of serve shots detected")
    totalShotCount: int = Field(..., description="Total shots detected (smash + defence + serve)")
    shotFrames: List[str] = Field(..., description="Paths or GCS URIs of saved shot frames")
    heatmapPath: str = Field(..., description="Path or GCS URI of the player position heatmap image")
    stepCount: int = Field(..., description="Estimated number of steps taken by the player")
    distanceTravelledM: float = Field(..., description="Total distance travelled by the player in meters")

import time
from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from src.api.routes.analyze import router as analyze_router
from src.utils.logger import get_logger

logger = get_logger("api")

app = FastAPI(
    title="Kreeda AI Engine",
    version="1.0.0",
    description="Badminton match video analysis API. Detects shuttlecock, player, pose and classifies shots (smash, defence, serve).",
    docs_url="/docs",
    redoc_url="/redoc",
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    logger.info(f"REQUEST  {request.method} {request.url.path}")
    response = await call_next(request)
    duration = (time.time() - start) * 1000
    logger.info(f"RESPONSE {request.method} {request.url.path} | status={response.status_code} | {duration:.1f}ms")
    return response

app.include_router(analyze_router, prefix="/api/v1", tags=["Analysis"])

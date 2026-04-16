# Kreeda AI Engine — Full Rebuild Prompt

Use this prompt to rebuild the entire project from scratch using an AI builder.

---

## Project Overview

Build a production-level Python REST API called **Kreeda AI Engine** that analyzes badminton match videos and delivers shot statistics via a webhook callback. The API accepts a video file path, processes it through an ML detection pipeline, and POSTs results to a webhook URL using HMAC-signed requests.

---

## Tech Stack

- **Python 3.10+**
- **FastAPI** — REST API framework
- **Uvicorn** — ASGI server
- **Ultralytics YOLOv8** — object detection (two models)
- **OpenCV** (`opencv-contrib-python-headless`) — video processing and frame annotation
- **NumPy** — distance calculations
- **pydantic-settings** — settings and env var management
- **requests** — outbound webhook HTTP calls
- **google-cloud-storage** — GCS file operations (prod only)

### requirements.txt
```
pydantic-settings==2.1.0
fastapi==0.109.0
uvicorn==0.27.0
numpy==1.24.3
opencv-contrib-python-headless==4.8.1.78
scipy==1.11.4
ultralytics==8.0.220
pillow==10.1.0
matplotlib==3.8.2
requests
```

---

## Project Structure

```
kreeda-ai-engine/
├── config/
│   └── settings.py
├── models/
│   └── weights/
│       ├── yolov8n.pt               # downloaded automatically by ultralytics
│       └── shuttleAndShotDetector.pt  # custom trained model — place manually
├── src/
│   ├── __init__.py
│   ├── api/
│   │   ├── main.py
│   │   ├── enums/
│   │   │   ├── __init__.py
│   │   │   └── record_angle.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   └── analyze.py
│   │   └── schemas/
│   │       ├── __init__.py
│   │       ├── request.py
│   │       └── response.py
│   ├── models/
│   │   ├── shuttle_and_shot_detector.py
│   │   ├── player_detector.py
│   │   └── pose_estimator.py        # exists but not used in pipeline, keep for future
│   ├── pipeline/
│   │   └── processor.py
│   └── utils/
│       ├── file_handler.py
│       ├── frame_store.py
│       ├── heatmap.py
│       ├── logger.py
│       └── webhook.py
├── static/                          # shot frames saved here in local env
├── logs/
│   └── kreeda.log
├── inputs/                          # place test videos here for local env
├── server.py
├── Dockerfile
├── .env.example
└── requirements.txt
```

---

## Configuration — `config/settings.py`

Use `pydantic-settings` `BaseSettings`. Load from `.env` file. Settings:

| Setting | Default | Description |
|---|---|---|
| `ENV` | `local` | `local` or `prod` |
| `GCS_BUCKET` | `""` | Output GCS bucket for shot frames (prod only) |
| `MODELS_DIR` | `models/weights/` | Directory for model weight files |
| `STATIC_DIR` | `static/` | Local shot frame output directory |
| `LOGS_DIR` | `logs/` | Log file directory |
| `CONFIDENCE_THRESHOLD` | `0.5` | Player detection confidence threshold |
| `SHOT_COOLDOWN_FRAMES` | `10` | Minimum frames between shot detections |
| `WEBHOOK_BASE_URL` | `https://backend-service-87645406452.asia-south1.run.app` | Webhook base URL |
| `HMAC_SECRET` | `995b37b2ccc9e293eca0b0ff3e070b6d4fd9cbd6335f4b81cda03cc2c02bd5c6` | HMAC signing secret |

`BASE_DIR` = project root resolved from `config/settings.py` location.

---

## Logging — `src/utils/logger.py`

- Centralized logger using Python `logging`
- Function `get_logger(name: str)` returns a named logger
- Logs to both console and `logs/kreeda.log`
- Format: `YYYY-MM-DD HH:MM:SS [LEVEL] [name] message`
- Log level: `INFO` for file, `INFO` for console

---

## Enums — `src/api/enums/record_angle.py`

```python
class RecordAngle(str, Enum):
    backcourt = "backcourt"
    frontcourt = "frontcourt"
```

---

## API Schemas

### `src/api/schemas/request.py` — `AnalyzeRequest`
Pydantic model with fields:
- `userId: str` — unique user identifier
- `videoId: str` — unique video identifier
- `postId: str` — post identifier used for webhook callback routing
- `filePath: str` — local path (local env) or `bucket-name/path/to/file.mp4` (prod, no `gs://` prefix)
- `recordAngle: RecordAngle` — enum, `backcourt` or `frontcourt`

### `src/api/schemas/response.py` — `AnalyzeAccepted`
Pydantic model returned immediately on `POST /analyze`:
- `message: str` — default `"Analysis started"`
- `postId: str`
- `videoId: str`

---

## FastAPI App — `src/api/main.py`

- Create FastAPI app with title `"Kreeda AI Engine"`, version `"1.0.0"`
- Add HTTP middleware that logs every request and response with method, path, status code, and duration in ms
- Mount router at prefix `/api/v1` with tag `"Analysis"`
- Swagger at `/docs`, ReDoc at `/redoc`

---

## Route — `src/api/routes/analyze.py`

`POST /analyze` endpoint:

1. Logs incoming request details
2. Resolves the video file path by calling `resolve_video_path(filePath)` — raises `404` if not found, `500` on other errors
3. Spawns a **non-daemon background thread** (`daemon=False`) that runs `_run_pipeline(...)`
4. Immediately returns HTTP `202` with `AnalyzeAccepted` response

`_run_pipeline(post_id, video_id, user_id, local_path, file_path, record_angle)`:
- Calls `process_video(...)` 
- On success → calls `notify_success(post_id, result)`
- On any error (catch `BaseException`) → logs error → calls `notify_failure(post_id, str(e))`

**Important**: Use `daemon=False` so the thread is not killed when the HTTP response is sent. This is critical for Cloud Run deployments.

---

## File Handler — `src/utils/file_handler.py`

`resolve_video_path(file_path: str) -> str`:
- If `ENV=local`: check path exists, return it directly, raise `FileNotFoundError` if not
- If `ENV=prod`: call `_download_from_gcs(file_path)`

`_download_from_gcs(file_path: str) -> str`:
- `file_path` format is `bucket-name/path/to/file.mp4` (may optionally start with `gs://`, strip it)
- Always split on first `/` to get `bucket_name` and `blob_path`
- Download blob to a `tempfile.NamedTemporaryFile` (delete=False)
- Return temp file path

---

## ML Models

### `src/models/shuttle_and_shot_detector.py` — `ShuttleAndShotDetector`

- Loads custom YOLOv8 model `shuttleAndShotDetector.pt`
- Model classes: `{0: 'shuttle', 1: 'smash', 2: 'defence', 3: 'serve'}`
- Confidence threshold: `0.1`
- Shot cooldown: `10` frames (tracked via `skip_until` frame index)

`detect(frame, frame_idx) -> (shuttle_dict, shot_type_str)`:
- Run `model.predict(frame, conf=0.1, verbose=False)`
- Find highest confidence detection per class
- Return shuttle dict: `{bbox: [x1,y1,x2,y2], center: (cx,cy), confidence: float}`
- Return shot type (smash/defence/serve) only if shuttle detected AND `frame_idx > skip_until`
- When shot detected, set `skip_until = frame_idx + 10`
- Shot type = highest confidence among smash/defence/serve

### `src/models/player_detector.py` — `PlayerDetector`

- Loads `yolov8n.pt`
- Confidence threshold: `0.5`

`detect(frame) -> list[dict]`:
- Run `model.predict(frame, conf=0.5, classes=[0], verbose=False)` (person class only)
- Return list of `{bbox: [x1,y1,x2,y2], confidence: float, center: (cx,cy)}`

`get_closest_player(detections, frame_height) -> dict`:
- Return detection with highest `y2` (bottom of bbox = closest to camera)

### `src/models/pose_estimator.py` — `PoseEstimator`
- Keep this file but it is **not used** in the active pipeline
- Uses MediaPipe Pose — keep for future use
- Implement `estimate()`, `get_feet_position()`, `get_key_landmarks()`, `draw_landmarks()` methods

---

## Detection Pipeline — `src/pipeline/processor.py`

Constants:
```python
COURT_WIDTH_M = 6.1      # real court width in meters
STEP_MIN_PX   = 15       # minimum pixel movement to count as a step
STEP_COOLDOWN = 3        # frames between step counts
SHUTTLE_SIZE  = 1280     # resize longest side before shuttle/shot inference
PLAYER_SIZE   = 640      # resize longest side before player inference
PLAYER_EVERY  = 5        # run player detection every N processed frames
```

Use lazy-loaded module-level singletons for both models (load once on first request).

`process_video(video_path, file_path, record_angle, user_id, video_id) -> dict`:

**Setup:**
- Extract `input_bucket` from `file_path` (first segment before `/`) if `ENV=prod`, else `None`
- Open video with `cv2.VideoCapture`
- Read `fps`, `width`, `height`, `total_video_frames`
- Compute `duration_s = round(total_video_frames / fps, 2)`
- Compute `frame_skip = max(1, round(fps / 15))` to process at ~15fps

**Detection loop (per processed frame):**

1. **Shuttle + Shot detection** — resize frame to `SHUTTLE_SIZE` on longest side, run `ShuttleAndShotDetector.detect()`, scale bbox/center back to original coords
2. **Player detection** — only every `PLAYER_EVERY` frames: resize to `PLAYER_SIZE`, run `PlayerDetector.detect()`, scale back. Otherwise reuse last known player.
3. **Feet position** — if player detected: `feet = ((x1+x2)//2, y2)` (bbox bottom-center)
4. **Step + distance tracking** — compute euclidean distance from `prev_feet`, accumulate `total_distance_px`, count step if `dist_px >= STEP_MIN_PX` and `frames_since_step >= STEP_COOLDOWN`
5. **Heatmap positions** — append feet to `player_positions` list
6. **Shot frame saving** — when `shot_type` detected:
   - Draw green rectangle on player bbox
   - Draw cyan rectangle + circle on shuttle bbox
   - Draw shot label and confidence on frame
   - Draw frame number top-left
   - Call `save_shot_frame(frame, video_id, shot_type, frame_num)`

**After loop:**
- `total_distance_m = round(total_distance_px * (COURT_WIDTH_M / INNER_W), 2)`
- Generate heatmap → `save_heatmap(heatmap_img, user_id, video_id, input_bucket)`

**Return dict:**
```python
{
    "user_id", "video_id", "record_angle",
    "total_frames",         # processed frame count
    "shuttle_detections",   # frames where shuttle was detected
    "smash_count", "defence_count", "serve_count", "total_shot_count",
    "shot_frames",          # list of paths
    "heatmap_path",         # path string
    "step_count",
    "distance_travelled_m",
    "duration",             # video duration in seconds
}
```

---

## Heatmap — `src/utils/heatmap.py`

Draw a badminton near-side half-court diagram and overlay a player position heatmap.

Court canvas: `600 x 700 px`
Margins: `60px` on all sides → inner court `480 x 580 px` (`INNER_W=480`, `INNER_H=580`)

**Colors:**
- Background: light green `(144, 238, 144)` (BGR)
- Court lines: dark green `(34, 100, 34)`
- Net: dark blue `(0, 0, 180)`

**Court lines to draw:**
- Outer boundary rectangle
- Net line at top with "NET" label
- Short service line at `1.98/6.7` ratio from top
- Long service line (doubles) at `0.76/6.7` ratio from bottom
- Center line from short service line to baseline
- Side tramlines at `0.46/6.1` ratio from each side
- "PLAYER SIDE" label below baseline

`generate_heatmap(player_positions, frame_width, frame_height) -> np.ndarray`:
- Map each `(px, py)` position from frame coords to court canvas coords
- Accumulate into a float heat array
- Apply `GaussianBlur(51, 51)`
- Normalize to 0-255
- Apply `COLORMAP_JET`
- Overlay heat on court where `heat_uint8 > 10` using `addWeighted(court=0.2, heat=0.8)`

---

## Frame Store — `src/utils/frame_store.py`

`save_shot_frame(frame, video_id, shot_type, frame_num) -> str`:
- Filename: `frame_{frame_num:05d}.jpg`
- Local: save to `static/{video_id}/{shot_type}/`, return `"static/{video_id}/{shot_type}/{filename}"`
- Prod: upload to GCS at `{GCS_BUCKET}/{video_id}/{shot_type}/{filename}`, return `"{video_id}/{shot_type}/{filename}"` (no bucket prefix)

`save_heatmap(heatmap_img, user_id, video_id, input_bucket) -> str`:
- Filename: `heatmap.jpg`
- Local: save to `static/{video_id}/heatmap/`, return full local path
- Prod: upload to `{input_bucket}/videos/{user_id}/{video_id}/heatmap.jpg`, return `"videos/{user_id}/{video_id}/heatmap.jpg"` (no bucket prefix, log full `gs://` URI)

For GCS uploads: write frame to `tempfile.mkstemp`, upload, delete temp file.
JPEG quality: `97` for all saves.

---

## Webhook — `src/utils/webhook.py`

HMAC signing: `sha256(HMAC_SECRET, raw_body).hexdigest()`

`_signed_post(url, payload) -> requests.Response`:
- Serialize payload with `json.dumps(payload, separators=(",", ":"))` (compact, deterministic)
- Compute `ts = str(int(time.time()))`
- Compute `sig = hmac.new(secret, body, sha256).hexdigest()`
- POST with headers: `Content-Type: application/json`, `x-timestamp: {ts}`, `x-signature: sha256={sig}`
- Timeout: `30s`

`notify_success(post_id, result)`:
- URL: `{WEBHOOK_BASE_URL}/internal/posts/{post_id}/analysis-result`
- Payload:
```json
{
  "record_angle": "...",
  "total_frames": 0,
  "shot_frames": ["..."],
  "heatmap_path": "...",
  "step_count": 0,
  "distance_travelled_m": 0.0,
  "duration": 0.0,
  "computed_score": 100,
  "sport_metrics": {
    "smash_count": 0,
    "defence_count": 0,
    "serve_count": 0,
    "total_shot_count": 0
  }
}
```
- Log full payload before sending
- Log status code + first 200 chars of response body
- Log as ERROR if status is not 2xx

`notify_failure(post_id, error)`:
- URL: `{WEBHOOK_BASE_URL}/internal/posts/{post_id}/analysis-failure`
- Payload: `{"message": "Analysis failed", "error": "<error string>"}`
- Same logging pattern as success

---

## Server — `server.py`

```python
import uvicorn
if __name__ == "__main__":
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
```

---

## Dockerfile

- Base: `python:3.10-slim`
- Install system deps: `libglib2.0-0`, `libgl1`, `libgstreamer1.0-0`, `libgstreamer-plugins-base1.0-0`, `libsm6`, `libxext6`, `libxrender1`, `libgomp1`, `ffmpeg`
- Install `protobuf==3.20.3` first (mediapipe dependency lock)
- Install `mediapipe==0.10.14`
- Install `torch==2.1.0 torchvision==0.16.0` from `https://download.pytorch.org/whl/cpu`
- Install `requirements.txt`
- Install `google-cloud-storage`
- Set env vars: `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python`, `PYTHONUNBUFFERED=1`, `PYTHONDONTWRITEBYTECODE=1`
- Create dirs: `logs`, `static`, `models/weights`
- Expose port `8080`
- CMD: `python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8080`

---

## Deployment — Emergent.sh

This project is deployed on **emergent.sh**.

- The app runs as a Docker container — the existing `Dockerfile` is used as-is
- Emergent.sh builds and deploys from the Docker image automatically on push
- Expose port `8080` (already set in Dockerfile)
- Set the following environment variables in the Emergent.sh dashboard:

| Variable | Value |
|---|---|
| `ENV` | `prod` |
| `GCS_BUCKET` | your output GCS bucket name |
| `WEBHOOK_BASE_URL` | `https://backend-service-87645406452.asia-south1.run.app` |
| `HMAC_SECRET` | your HMAC secret |
| `OMP_NUM_THREADS` | `4` |
| `OPENBLAS_NUM_THREADS` | `4` |

- No GitHub Actions workflow needed — Emergent.sh handles CI/CD
- GCS credentials: provide the GCP service account JSON as an environment variable or mount it as a secret in the Emergent.sh dashboard so `google-cloud-storage` can authenticate

**Important runtime note**: The detection pipeline runs in a background thread after the HTTP response is sent. Make sure Emergent.sh does **not** kill the container process after the response — the container must stay alive until the background thread completes and the webhook is called.

---

## .env.example

```env
ENV=local
GCS_BUCKET=your-gcs-bucket-name
WEBHOOK_BASE_URL=https://backend-service-87645406452.asia-south1.run.app
HMAC_SECRET=your-hmac-secret
```

---

## Key Behaviours to Implement Correctly

1. **Non-daemon background thread** — `daemon=False` is mandatory. The platform will kill daemon threads after the HTTP response is sent.
2. **Container must stay alive** — ensure the deployment platform does not terminate the container after the HTTP response. The background thread needs to run to completion before the webhook is called.
3. **Frame resize strategy** — shuttle detector at 1280px, player detector at 640px. Never run full 1080p through YOLO on CPU.
4. **Player detection every 5 frames** — reuse last known player bbox between detections.
5. **Shot cooldown** — 10 frame cooldown on shot detection to avoid duplicate counts.
6. **Input bucket extraction** — `filePath` comes as `bucket-name/path/to/file.mp4`. Split on first `/` to get bucket. Never hardcode bucket for input.
7. **Heatmap bucket** — heatmap uploads to the same bucket as the input video, not the output `GCS_BUCKET`.
8. **Paths in response** — all paths returned without bucket prefix (e.g. `videos/userId/videoId/heatmap.jpg`, not `gs://bucket/...`).
9. **BaseException catch** in pipeline thread — ensures `notify_failure` is always called even on non-standard exceptions.
10. **OMP_NUM_THREADS=4** — without this, PyTorch defaults to 1 thread inside Docker containers.

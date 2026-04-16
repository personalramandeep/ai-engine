# Kreeda AI Engine — Badminton Stats Detection

A production-level ML pipeline that analyzes badminton match videos and returns shot statistics via a REST API. It detects shuttlecock, player, pose landmarks, and classifies shots (smash, defence, serve) using a combination of a custom YOLO model and pose-based wrist/elbow proximity logic.

---

## Table of Contents

- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Detection Pipeline](#detection-pipeline)
- [Shot Detection Logic](#shot-detection-logic)
- [API](#api)
- [Frame Storage](#frame-storage)
- [Configuration](#configuration)
- [Setup & Installation](#setup--installation)
- [Running the Server](#running-the-server)

---

## Architecture

```
HTTP Request
    │
    ▼
FastAPI (src/api/main.py)
    │  middleware: request/response logging
    ▼
POST /api/v1/analyze  (src/api/routes/analyze.py)
    │
    ├── Resolve file path  (src/utils/file_handler.py)
    │       local  → use path directly
    │       prod   → download from GCS to temp file
    │
    ▼
Detection Pipeline  (src/pipeline/processor.py)
    │
    ├── Phase 1: Model Loading (lazy singleton)
    │       ShuttleAndShotDetector  (YOLOv8 custom model)
    │       PlayerDetector          (YOLOv8n — person class)
    │       PoseEstimator           (MediaPipe Pose)
    │
    ├── Phase 2: Video Setup
    │       Read FPS, resolution
    │       Calculate frame skip to process at 15 FPS
    │
    ├── Phase 3: Detection Loop (per frame)
    │       ├── Shuttle + Shot type  →  ShuttleAndShotDetector
    │       ├── Player bounding box  →  PlayerDetector
    │       ├── Pose landmarks       →  PoseEstimator (cropped to player bbox)
    │       └── Pose-based shot      →  wrist/elbow proximity logic
    │
    └── Phase 4: Save Shot Frames
            local  → static/{videoId}/{shot_type}/frame_XXXXX.jpg
            prod   → gs://{bucket}/{videoId}/{shot_type}/frame_XXXXX.jpg
    │
    ▼
AnalyzeResponse (JSON)
```

---

## Project Structure

```
kreeda-ai-engine/
├── config/
│   └── settings.py               # All config, env vars
├── models/
│   └── weights/
│       ├── yolov8n.pt            # Player detection model
│       └── shuttleAndShotDetector.pt  # Shuttle + shot classification model
├── src/
│   ├── api/
│   │   ├── main.py               # FastAPI app + HTTP logging middleware
│   │   ├── enums/
│   │   │   └── record_angle.py   # RecordAngle enum (backcourt/frontcourt)
│   │   ├── routes/
│   │   │   └── analyze.py        # POST /api/v1/analyze endpoint
│   │   └── schemas/
│   │       ├── request.py        # AnalyzeRequest model
│   │       └── response.py       # AnalyzeResponse model
│   ├── models/
│   │   ├── shuttle_and_shot_detector.py  # YOLOv8 shuttle + shot detection
│   │   ├── player_detector.py            # YOLOv8n person detection
│   │   └── pose_estimator.py             # MediaPipe pose + wrist/elbow extraction
│   ├── pipeline/
│   │   └── processor.py          # Full video processing pipeline
│   └── utils/
│       ├── file_handler.py       # Local/GCS video path resolution
│       ├── frame_store.py        # Local/GCS shot frame saving
│       └── logger.py             # Centralized logger (console + file)
├── static/                       # Shot frames saved here (local env)
├── logs/
│   └── kreeda.log                # All pipeline + API logs
├── server.py                     # Uvicorn entrypoint
├── requirements.txt
└── .env.example
```

---

## Detection Pipeline

Each video frame goes through 4 sequential detectors:

### 1. Shuttle & Shot Detector (`shuttle_and_shot_detector.py`)
- Uses a custom YOLOv8 model (`shuttleAndShotDetector.pt`) trained on badminton data
- Detects `shuttle`, `smash`, `defence`, `serve` classes in a single forward pass
- Returns the highest-confidence shuttle box and shot type per frame
- Shot type has a 10-frame cooldown to avoid duplicate detections

### 2. Player Detector (`player_detector.py`)
- Uses YOLOv8n (`yolov8n.pt`) with `classes=[0]` (person only)
- Selects the player closest to the camera by picking the detection with the lowest `y2` (bottom of bounding box)

### 3. Pose Estimator (`pose_estimator.py`)
- Uses MediaPipe Pose (`model_complexity=1`, `smooth_landmarks=True`)
- Crops the frame to the player bounding box (+ 30px padding) before running pose estimation
- Upscales the crop to max 640px on the longest side for better landmark accuracy
- Maps all 33 landmarks back to original frame coordinates
- Extracts 18 key landmarks: nose, eyes, ears, shoulders, elbows, wrists, hips, knees, ankles
- Only returns landmarks with `visibility > 0.5`

### 4. Shot Detection (`processor.py`)
- Shot type (`smash`, `defence`, `serve`) is determined entirely by the YOLO model
- When a shot is detected, player detection and pose estimation run on that frame only
- The annotated frame is saved to local/GCS storage under `{videoId}/{shot_type}/`

---

## API

### Start the server

```bash
python server.py
# Server runs at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

### POST `/api/v1/analyze`

Processes a video and returns shot statistics.

**Request**
```json
{
  "userId": "user-uuid",
  "videoId": "video-uuid",
  "filePath": "inputs/match.mp4",
  "recordAngle": "backcourt"
}
```

| Field | Type | Description |
|---|---|---|
| `userId` | string | Unique user identifier |
| `videoId` | string | Unique video identifier |
| `filePath` | string | Local path (local env) or GCS path `gs://bucket/path` (prod) |
| `recordAngle` | enum | `backcourt` or `frontcourt` |

**Response**
```json
{
  "userId": "user-uuid",
  "videoId": "video-uuid",
  "recordAngle": "backcourt",
  "totalFrames": 450,
  "shuttleDetections": 210,
  "smashCount": 5,
  "defenceCount": 8,
  "serveCount": 3,
  "totalShotCount": 16,
  "shotFrames": [
    "static/video-uuid/smash/frame_00042.jpg",
    "static/video-uuid/defence/frame_00120.jpg"
  ]
}
```

---

## Frame Storage

Shot frames are only saved when a shot is detected (pose-based). No full video is written.

### Local (`ENV=local`)
```
static/
└── {videoId}/
    ├── smash/
    │   └── frame_00042.jpg
    ├── defence/
    │   └── frame_00120.jpg
    └── serve/
        └── frame_00015.jpg
```

### Production (`ENV=prod`)
Frames are uploaded directly to GCS:
```
gs://{GCS_BUCKET}/{videoId}/smash/frame_00042.jpg
gs://{GCS_BUCKET}/{videoId}/defence/frame_00120.jpg
```

---

## Configuration

Copy `.env.example` to `.env` and set values:

```env
# Environment: local | prod
ENV=local

# Required only when ENV=prod
GCS_BUCKET=your-gcs-bucket-name
```

All settings are in `config/settings.py`:

| Setting | Default | Description |
|---|---|---|
| `ENV` | `local` | `local` or `prod` |
| `GCS_BUCKET` | `""` | GCS bucket name (prod only) |
| `MODELS_DIR` | `models/weights/` | Directory for model weight files |
| `STATIC_DIR` | `static/` | Local shot frame output directory |
| `CONFIDENCE_THRESHOLD` | `0.5` | Player detection confidence |
| `SHOT_COOLDOWN_FRAMES` | `10` | Minimum frames between shot detections |

---

## Setup & Installation

### Prerequisites
- Python 3.10+
- CUDA (optional, for GPU acceleration)

### Install

```bash
git clone <repo-url>
cd kreeda-ai-engine

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt

# For production GCS support
pip install google-cloud-storage
```

### Model Weights

Place the following files in `models/weights/`:
- `yolov8n.pt` — downloaded automatically by Ultralytics on first run
- `shuttleAndShotDetector.pt` — custom trained model (provide manually)

---

## Running the Server

```bash
python server.py
```

Logs are written to both console and `logs/kreeda.log`.

### Log phases per request
```
[INFO] [api]               REQUEST  POST /api/v1/analyze
[INFO] [api.routes.analyze] === API: /analyze === user=... video=...
[INFO] [file_handler]      === Phase: Resolving File ===
[INFO] [pipeline]          === Phase: Model Loading ===
[INFO] [pipeline]          === Phase: Video Setup ===
[INFO] [pipeline]          === Phase: Detection Loop ===
[INFO] [pipeline]          === Phase: Complete ===
[INFO] [api]               RESPONSE POST /api/v1/analyze | status=200 | 4231.2ms
```

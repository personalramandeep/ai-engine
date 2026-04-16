import cv2
import numpy as np
from src.models.shuttle_and_shot_detector import ShuttleAndShotDetector
from src.models.player_detector import PlayerDetector
from src.utils.frame_store import save_shot_frame, save_heatmap
from src.utils.heatmap import generate_heatmap, INNER_W
from src.utils.logger import get_logger
from config.settings import settings

logger = get_logger("pipeline")

COURT_WIDTH_M   = 6.1
STEP_MIN_PX     = 15
STEP_COOLDOWN   = 3
SHUTTLE_SIZE    = 1280  # resize for shuttle/shot inference — balance of speed vs accuracy
PLAYER_SIZE     = 640   # resize for player inference
PLAYER_EVERY    = 5     # run player detection every N processed frames

# Lazy-loaded singletons
_shuttle_shot_detector = None
_player_detector = None

def _load_models():
    global _shuttle_shot_detector, _player_detector
    if _shuttle_shot_detector is None:
        logger.info("=== Phase: Model Loading ===")
        _shuttle_shot_detector = ShuttleAndShotDetector()
        _player_detector = PlayerDetector()
        logger.info("All models loaded successfully")

def process_video(video_path: str, file_path: str, record_angle: str, user_id: str, video_id: str) -> dict:
    """Run full detection pipeline on a video. Returns stats dict."""
    _load_models()

    # Extract input bucket from file_path (format: bucket-name/path/to/file.mp4)
    input_bucket = file_path.lstrip("gs://").split("/")[0] if settings.ENV == "prod" else None

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    # Set best quality capture properties
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # minimize buffer lag

    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_s = round(total_video_frames / fps, 2) if fps > 0 else 0.0
    target_fps = 15
    frame_skip = max(1, round(fps / target_fps))

    logger.info(f"=== Phase: Video Setup === user={user_id} video={video_id} angle={record_angle} {width}x{height} @ {fps}fps, skip={frame_skip}")

    frame_count = 0
    saved_frame_count = 0
    detection_count = 0
    shot_type_counts = {}
    shot_frames = []
    player_positions = []   # for heatmap
    player = None
    prev_feet = None
    total_distance_px = 0.0
    step_count = 0
    frames_since_step = 0
    px_to_m = COURT_WIDTH_M / INNER_W  # pixel to meter ratio

    logger.info("=== Phase: Detection Loop ===")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        if frame_count % frame_skip != 0:
            frame_count += 1
            continue

        # Shuttle + shot on 1280px resize — fast on CPU, accurate enough for detection
        scale_s = min(SHUTTLE_SIZE / width, SHUTTLE_SIZE / height)
        if scale_s < 1.0:
            shuttle_frame = cv2.resize(frame, (int(width * scale_s), int(height * scale_s)), interpolation=cv2.INTER_LINEAR)
        else:
            shuttle_frame, scale_s = frame, 1.0

        shuttle, shot_type = _shuttle_shot_detector.detect(shuttle_frame, saved_frame_count)

        if shuttle and scale_s < 1.0:
            shuttle['bbox'] = [int(v / scale_s) for v in shuttle['bbox']]
            shuttle['center'] = (int(shuttle['center'][0] / scale_s), int(shuttle['center'][1] / scale_s))

        if shuttle:
            detection_count += 1

        # Player detection on 640px resize every PLAYER_EVERY frames
        if saved_frame_count % PLAYER_EVERY == 0:
            scale_p = min(PLAYER_SIZE / width, PLAYER_SIZE / height)
            if scale_p < 1.0:
                player_frame = cv2.resize(frame, (int(width * scale_p), int(height * scale_p)), interpolation=cv2.INTER_LINEAR)
            else:
                player_frame, scale_p = frame, 1.0
            player_detections = _player_detector.detect(player_frame)
            player = _player_detector.get_closest_player(player_detections, player_frame.shape[0])
            if player and scale_p < 1.0:
                player['bbox'] = [int(v / scale_p) for v in player['bbox']]
                player['center'] = (int(player['center'][0] / scale_p), int(player['center'][1] / scale_p))

        if player:
            x1, y1, x2, y2 = player['bbox']
            feet = ((x1 + x2) // 2, y2)
            player_positions.append(feet)
            frames_since_step += 1
            if prev_feet is not None:
                dist_px = np.sqrt((feet[0] - prev_feet[0])**2 + (feet[1] - prev_feet[1])**2)
                total_distance_px += dist_px
                if dist_px >= STEP_MIN_PX and frames_since_step >= STEP_COOLDOWN:
                    step_count += 1
                    frames_since_step = 0
            prev_feet = feet

        if shot_type:
            logger.debug(f"Shot detected: {shot_type} at frame {saved_frame_count}")

            if player:
                px1, py1, px2, py2 = player['bbox']
                cv2.rectangle(frame, (px1, py1), (px2, py2), (0, 255, 0), 2)

            # Draw shuttle bbox and shot label
            sx1, sy1, sx2, sy2 = shuttle['bbox']
            cv2.rectangle(frame, (sx1, sy1), (sx2, sy2), (0, 255, 255), 2)
            cv2.circle(frame, shuttle['center'], 5, (0, 255, 255), -1)
            cv2.putText(frame, f"{shot_type.upper()} {shuttle['confidence']:.2f}",
                       (sx1, sy1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            # Draw frame number
            cv2.putText(frame, f"Frame: {saved_frame_count}", (20, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            shot_type_counts[shot_type] = shot_type_counts.get(shot_type, 0) + 1
            frame_path = save_shot_frame(frame, video_id, shot_type, saved_frame_count)
            shot_frames.append(frame_path)

        saved_frame_count += 1
        frame_count += 1

        if saved_frame_count % 100 == 0:
            logger.debug(f"Processed {saved_frame_count} frames | shuttles={detection_count} | shots={sum(shot_type_counts.values())}")

    cap.release()

    total_distance_m = round(total_distance_px * px_to_m, 2)
    logger.info(f"Steps: {step_count} | Distance: {total_distance_m}m")

    logger.info("=== Phase: Generating Heatmap ===")
    heatmap_img = generate_heatmap(player_positions, width, height)
    heatmap_path = save_heatmap(heatmap_img, user_id, video_id, input_bucket)
    logger.info(f"Heatmap saved: {heatmap_path}")

    smash = shot_type_counts.get("smash", 0)
    defence = shot_type_counts.get("defence", 0)
    serve = shot_type_counts.get("serve", 0)

    result = {
        "user_id": user_id,
        "video_id": video_id,
        "record_angle": record_angle,
        "total_frames": saved_frame_count,
        "shuttle_detections": detection_count,
        "smash_count": smash,
        "defence_count": defence,
        "serve_count": serve,
        "total_shot_count": smash + defence + serve,
        "shot_frames": shot_frames,
        "heatmap_path": heatmap_path,
        "step_count": step_count,
        "distance_travelled_m": total_distance_m,
        "duration": duration_s,
    }

    logger.info(f"=== Phase: Complete === user={user_id} video={video_id} smash={smash} defence={defence} serve={serve} total={smash+defence+serve}")
    return result

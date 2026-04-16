import hashlib
import hmac
import json
import time
import requests
from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("webhook")


def _signed_post(url: str, payload: dict) -> requests.Response:
    body = json.dumps(payload, separators=(",", ":")).encode()
    ts = str(int(time.time()))
    sig = hmac.new(settings.HMAC_SECRET.encode(), body, hashlib.sha256).hexdigest()

    return requests.post(url, data=body, headers={
        "Content-Type": "application/json",
        "x-timestamp":  ts,
        "x-signature":  f"sha256={sig}",
    }, timeout=30)


def notify_success(post_id: str, result: dict):
    url = f"{settings.WEBHOOK_BASE_URL}/internal/posts/{post_id}/analysis-result"
    payload = {
        "record_angle":        result["record_angle"],
        "total_frames":        result["total_frames"],
        "shot_frames":         result["shot_frames"],
        "heatmap_path":        result["heatmap_path"],
        "step_count":          result["step_count"],
        "distance_travelled_m": result["distance_travelled_m"],
        "duration":             result["duration"],
        "computed_score":      100,
        "sport_metrics": {
            "smash_count":      result["smash_count"],
            "defence_count":    result["defence_count"],
            "serve_count":      result["serve_count"],
            "total_shot_count": result["total_shot_count"],
        },
    }
    try:
        logger.info(f"Webhook POST success → {url} | payload={json.dumps(payload)}")
        r = _signed_post(url, payload)
        if r.ok:
            logger.info(f"Webhook success delivered post={post_id} status={r.status_code} response={r.text[:200]}")
        else:
            logger.error(f"Webhook success rejected post={post_id} status={r.status_code} response={r.text[:200]}")
    except Exception as e:
        logger.error(f"Webhook success failed post={post_id}: {e}")


def notify_failure(post_id: str, error: str):
    url = f"{settings.WEBHOOK_BASE_URL}/internal/posts/{post_id}/analysis-failure"
    payload = {"message": "Analysis failed", "error": error}
    try:
        logger.info(f"Webhook POST failure → {url} | payload={json.dumps(payload)}")
        r = _signed_post(url, payload)
        if r.ok:
            logger.info(f"Webhook failure delivered post={post_id} status={r.status_code} response={r.text[:200]}")
        else:
            logger.error(f"Webhook failure rejected post={post_id} status={r.status_code} response={r.text[:200]}")
    except Exception as e:
        logger.error(f"Webhook failure call failed post={post_id}: {e}")

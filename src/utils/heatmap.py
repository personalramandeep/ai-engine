import cv2
import numpy as np

# Near-side court only (half court)
COURT_W = 600
COURT_H = 700
COURT_BG = (144, 238, 144)      # light green background
LINE_COLOR = (34, 100, 34)      # dark green lines
NET_COLOR = (0, 0, 180)         # dark blue net
LINE_THICKNESS = 2

MARGIN_X = 60
MARGIN_Y = 60
INNER_W = COURT_W - 2 * MARGIN_X   # 480px
INNER_H = COURT_H - 2 * MARGIN_Y   # 580px


def _draw_court() -> np.ndarray:
    """Draw near-side half court with dark background."""
    court = np.full((COURT_H, COURT_W, 3), COURT_BG, dtype=np.uint8)

    x1, y1 = MARGIN_X, MARGIN_Y
    x2, y2 = COURT_W - MARGIN_X, COURT_H - MARGIN_Y

    # Outer boundary
    cv2.rectangle(court, (x1, y1), (x2, y2), LINE_COLOR, LINE_THICKNESS)

    # Net line at top of near side
    cv2.line(court, (x1, y1), (x2, y1), NET_COLOR, 3)
    cv2.putText(court, "NET", (COURT_W // 2 - 15, y1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, NET_COLOR, 1)

    # Short service line — 1.98m from net, half court = 6.7m → ratio
    service_offset = int(INNER_H * (1.98 / 6.7))
    cv2.line(court, (x1, y1 + service_offset), (x2, y1 + service_offset), LINE_COLOR, LINE_THICKNESS)

    # Long service line (doubles) — 0.76m from back baseline
    long_offset = int(INNER_H * (0.76 / 6.7))
    cv2.line(court, (x1, y2 - long_offset), (x2, y2 - long_offset), LINE_COLOR, LINE_THICKNESS)

    # Center line — splits left/right service boxes
    cx = COURT_W // 2
    cv2.line(court, (cx, y1 + service_offset), (cx, y2), LINE_COLOR, LINE_THICKNESS)

    # Side tramlines — 0.46m from each side, full court width = 6.1m
    tram_offset = int(INNER_W * (0.46 / 6.1))
    cv2.line(court, (x1 + tram_offset, y1), (x1 + tram_offset, y2), LINE_COLOR, LINE_THICKNESS)
    cv2.line(court, (x2 - tram_offset, y1), (x2 - tram_offset, y2), LINE_COLOR, LINE_THICKNESS)

    # Label
    cv2.putText(court, "PLAYER SIDE", (COURT_W // 2 - 45, y2 + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (34, 100, 34), 1)

    return court


def generate_heatmap(player_positions: list, frame_width: int, frame_height: int) -> np.ndarray:
    """
    Generate a near-side court heatmap from player positions.

    player_positions: list of (x, y) — bottom-center of player bbox in frame coords
    frame_width, frame_height: original video frame dimensions
    """
    court = _draw_court()

    if not player_positions:
        return court

    x1, y1 = MARGIN_X, MARGIN_Y
    x2, y2 = COURT_W - MARGIN_X, COURT_H - MARGIN_Y
    court_w = x2 - x1
    court_h = y2 - y1

    heat = np.zeros((COURT_H, COURT_W), dtype=np.float32)

    for px, py in player_positions:
        cx = int(x1 + (px / frame_width) * court_w)
        cy = int(y1 + (py / frame_height) * court_h)
        cx = max(x1, min(cx, x2 - 1))
        cy = max(y1, min(cy, y2 - 1))
        heat[cy, cx] += 1

    # Smooth and normalize
    heat = cv2.GaussianBlur(heat, (51, 51), 0)
    if heat.max() > 0:
        heat = heat / heat.max()

    heat_uint8 = (heat * 255).astype(np.uint8)
    heat_color = cv2.applyColorMap(heat_uint8, cv2.COLORMAP_JET)

    # Overlay only where heat exists
    mask = heat_uint8 > 10
    court[mask] = cv2.addWeighted(court, 0.2, heat_color, 0.8, 0)[mask]

    return court

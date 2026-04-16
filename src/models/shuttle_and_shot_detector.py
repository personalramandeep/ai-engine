from ultralytics import YOLO
from config.settings import settings

SHOT_CLASSES = {"smash", "defence", "serve"}

class ShuttleAndShotDetector:
    def __init__(self, model_path=None):
        self.model_path = model_path or str(settings.MODELS_DIR / "shuttleAndShotDetector.pt")
        self.model = YOLO(self.model_path)
        self.class_names = self.model.names
        self.conf = 0.1
        self.skip_until = -1
        self.skip_frames = 10
        print(f"Shuttle & Shot detector loaded: {self.model_path}")
        print(f"Classes: {self.class_names}")

    def detect(self, frame, frame_idx):
        """Detect shuttle and shot type in frame.
        Returns: shuttle dict, shot_type str or None
        """
        results = self.model.predict(source=frame, conf=self.conf, verbose=False)[0]
        boxes = results.boxes

        # Find highest confidence box per class
        best = {}
        for i, (cls_id, conf) in enumerate(zip(boxes.cls, boxes.conf)):
            name = self.class_names[int(cls_id)]
            if name not in best or conf.item() > best[name][1]:
                best[name] = (i, conf.item())

        # Parse shuttle
        shuttle = None
        if "shuttle" in best:
            idx = best["shuttle"][0]
            box = boxes[idx]
            x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            shuttle = {
                'bbox': [x1, y1, x2, y2],
                'center': (cx, cy),
                'confidence': best["shuttle"][1]
            }

        # Parse shot type with cooldown
        shot_type = None
        if shuttle and frame_idx > self.skip_until:
            shot_candidates = {k: v for k, v in best.items() if k in SHOT_CLASSES}
            if shot_candidates:
                shot_type = max(shot_candidates, key=lambda k: shot_candidates[k][1])
                self.skip_until = frame_idx + self.skip_frames

        return shuttle, shot_type

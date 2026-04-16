from ultralytics import YOLO
from config.settings import settings

class PlayerDetector:
    def __init__(self, model_path=None):
        self.model_path = model_path or str(settings.MODELS_DIR / "yolov8n.pt")
        self.model = YOLO(self.model_path)
        self.conf_threshold = 0.5
        print(f"Player detector loaded: {self.model_path}")
        
    def detect(self, frame):
        """Detect persons in frame"""
        results = self.model.predict(frame, conf=self.conf_threshold, classes=[0], verbose=False)
        
        if len(results[0].boxes) == 0:
            return []
        
        detections = []
        for box in results[0].boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
            conf = float(box.conf[0])
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)
            
            detections.append({
                'bbox': [x1, y1, x2, y2],
                'confidence': conf,
                'center': (cx, cy)
            })
        
        return detections
    
    def get_closest_player(self, detections, frame_height):
        """Get player closest to camera (bottom of frame)"""
        if not detections:
            return None
        
        # Sort by y2 (bottom of bbox) - closest to camera is at bottom
        closest = max(detections, key=lambda d: d['bbox'][3])
        return closest

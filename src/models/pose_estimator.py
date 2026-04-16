import cv2
import mediapipe as mp
import numpy as np

class PoseEstimator:
    def __init__(self):
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            smooth_landmarks=True,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        print("Pose estimator loaded")
        
    def estimate(self, frame, player_bbox=None):
        """Estimate pose landmarks in frame, optionally cropped to player bbox"""
        # If player bbox provided, crop to player region for better detection
        if player_bbox:
            x1, y1, x2, y2 = player_bbox
            # Add padding for better pose detection
            h, w = frame.shape[:2]
            pad = 30
            x1 = max(0, x1 - pad)
            y1 = max(0, y1 - pad)
            x2 = min(w, x2 + pad)
            y2 = min(h, y2 + pad)
            
            cropped_frame = frame[y1:y2, x1:x2]
            crop_h, crop_w = cropped_frame.shape[:2]
            
            # Resize to larger size for better detection (max 640px on longest side)
            max_size = 640
            scale = min(max_size / crop_w, max_size / crop_h)
            if scale > 1:
                new_w = int(crop_w * scale)
                new_h = int(crop_h * scale)
                resized_frame = cv2.resize(cropped_frame, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
            else:
                resized_frame = cv2.resize(cropped_frame, (int(crop_w * scale), int(crop_h * scale)), interpolation=cv2.INTER_AREA)
                new_w, new_h = resized_frame.shape[1], resized_frame.shape[0]
            
            rgb_frame = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)
            results = self.pose.process(rgb_frame)
            
            if not results.pose_landmarks:
                return None
            
            landmarks = {}
            
            # Extract landmarks and convert back to original frame coordinates
            for idx, landmark in enumerate(results.pose_landmarks.landmark):
                # Scale back from resized to cropped coordinates
                scaled_x = int(landmark.x * new_w / scale)
                scaled_y = int(landmark.y * new_h / scale)
                
                landmarks[idx] = {
                    'x': scaled_x + x1,
                    'y': scaled_y + y1,
                    'z': landmark.z,
                    'visibility': landmark.visibility
                }
            
            return landmarks
        else:
            # Process full frame
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.pose.process(rgb_frame)
            
            if not results.pose_landmarks:
                return None
            
            h, w = frame.shape[:2]
            landmarks = {}
            
            # Extract key landmarks
            for idx, landmark in enumerate(results.pose_landmarks.landmark):
                landmarks[idx] = {
                    'x': int(landmark.x * w),
                    'y': int(landmark.y * h),
                    'z': landmark.z,
                    'visibility': landmark.visibility
                }
            
            return landmarks
    
    def get_feet_position(self, landmarks, player_bbox=None):
        """Get feet position from ankle landmarks, fallback to bbox bottom-center."""
        if landmarks:
            left_ankle  = landmarks.get(27)
            right_ankle = landmarks.get(28)

            left_ok  = left_ankle  and left_ankle['visibility']  > 0.5
            right_ok = right_ankle and right_ankle['visibility'] > 0.5

            if left_ok and right_ok:
                return ((left_ankle['x'] + right_ankle['x']) // 2,
                        (left_ankle['y'] + right_ankle['y']) // 2)
            elif right_ok:
                return (right_ankle['x'], right_ankle['y'])
            elif left_ok:
                return (left_ankle['x'], left_ankle['y'])

        # Fallback to bbox bottom-center
        if player_bbox:
            x1, y1, x2, y2 = player_bbox
            return ((x1 + x2) // 2, y2)

        return None

    def get_wrist_positions(self, landmarks):
        """Get left and right wrist positions with better visibility check"""
        if not landmarks:
            return None, None
        
        # MediaPipe landmark indices: 15=left wrist, 16=right wrist
        left_wrist = landmarks.get(15)
        right_wrist = landmarks.get(16)
        
        # Only return wrist if visibility is good enough
        if left_wrist and left_wrist['visibility'] < 0.5:
            left_wrist = None
        if right_wrist and right_wrist['visibility'] < 0.5:
            right_wrist = None
        
        return left_wrist, right_wrist
    
    def get_key_landmarks(self, landmarks):
        """Get key body landmarks for analysis"""
        if not landmarks:
            return {}
        
        # MediaPipe landmark indices
        key_points = {
            'nose': 0,
            'left_eye': 2,
            'right_eye': 5,
            'left_ear': 7,
            'right_ear': 8,
            'left_shoulder': 11,
            'right_shoulder': 12,
            'left_elbow': 13,
            'right_elbow': 14,
            'left_wrist': 15,
            'right_wrist': 16,
            'left_hip': 23,
            'right_hip': 24,
            'left_knee': 25,
            'right_knee': 26,
            'left_ankle': 27,
            'right_ankle': 28
        }
        
        result = {}
        for name, idx in key_points.items():
            if idx in landmarks and landmarks[idx]['visibility'] > 0.5:
                result[name] = landmarks[idx]
        
        return result
    
    def draw_landmarks(self, frame, landmarks, player_bbox=None):
        """Draw pose landmarks on frame"""
        if not landmarks:
            return frame
        
        # Draw connections between landmarks
        connections = [
            # Arms
            (11, 13), (13, 15),  # Left arm
            (12, 14), (14, 16),  # Right arm
            # Torso
            (11, 12), (11, 23), (12, 24), (23, 24),
            # Legs
            (23, 25), (25, 27),  # Left leg
            (24, 26), (26, 28),  # Right leg
        ]
        
        # Draw connections
        for start_idx, end_idx in connections:
            if start_idx in landmarks and end_idx in landmarks:
                start = landmarks[start_idx]
                end = landmarks[end_idx]
                if start['visibility'] > 0.5 and end['visibility'] > 0.5:
                    cv2.line(frame, (start['x'], start['y']), 
                            (end['x'], end['y']), (0, 255, 0), 2)
        
        # Draw landmarks
        for idx, landmark in landmarks.items():
            if landmark['visibility'] > 0.5:
                x, y = landmark['x'], landmark['y']
                # Different colors for different body parts
                if idx in [15, 16]:  # Wrists
                    color = (255, 0, 0)  # Blue
                    radius = 6
                elif idx in [11, 12, 23, 24]:  # Shoulders and hips
                    color = (0, 255, 255)  # Yellow
                    radius = 5
                else:
                    color = (0, 255, 0)  # Green
                    radius = 4
                
                cv2.circle(frame, (x, y), radius, color, -1)
                cv2.circle(frame, (x, y), radius + 2, (255, 255, 255), 1)
        
        return frame

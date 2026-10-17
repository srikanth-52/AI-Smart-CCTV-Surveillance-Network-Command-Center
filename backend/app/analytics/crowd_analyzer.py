import cv2
import numpy as np
import time
from collections import deque
from backend.app.config import (
    CROWD_LOW_THRESHOLD,
    CROWD_MEDIUM_THRESHOLD,
    CROWD_HIGH_THRESHOLD,
    CROWD_SURGE_DELTA_THRESHOLD
)

class CrowdAnalyzer:
    def __init__(self, frame_shape=(720, 1280), history_len=30):
        self.height, self.width = frame_shape[:2]
        self.history_len = history_len
        self.count_history = deque(maxlen=history_len)
        self.timestamp_history = deque(maxlen=history_len)
        
        # Heatmap accumulation grid
        self.heatmap_grid = np.zeros((self.height // 4, self.width // 4), dtype=np.float32)
        self.decay_rate = 0.95
        
        # Bi-directional Tripwire
        self.line_y = int(self.height * 0.6)  # Default horizontal tripwire
        self.in_count = 0
        self.out_count = 0
        self.tracked_positions = {}  # id -> previous y

    def update_heatmap(self, person_boxes):
        """Accumulate person centroids into a smoothed heatmap grid with exponential decay."""
        self.heatmap_grid *= self.decay_rate
        
        for box in person_boxes:
            x1, y1, x2, y2 = box
            cx = int((x1 + x2) / 2 / 4)
            cy = int((y1 + y2) / 2 / 4)
            
            if 0 <= cx < self.heatmap_grid.shape[1] and 0 <= cy < self.heatmap_grid.shape[0]:
                cv2.circle(self.heatmap_grid, (cx, cy), radius=12, color=1.0, thickness=-1)

    def generate_heatmap_overlay(self, frame, alpha=0.45):
        """Generates a JET colormap blended with the current camera frame."""
        if frame is None:
            return None

        # Normalize heatmap to 0-255
        norm_map = cv2.normalize(self.heatmap_grid, None, 0, 255, cv2.NORM_MINMAX)
        norm_map = np.uint8(norm_map)
        
        # Resize to original frame resolution
        resized_map = cv2.resize(norm_map, (frame.shape[1], frame.shape[0]))
        blurred_map = cv2.GaussianBlur(resized_map, (31, 31), 0)
        
        # Apply colormap
        colored_map = cv2.applyColorMap(blurred_map, cv2.COLORMAP_JET)
        
        # Create a mask so low-intensity areas don't tint the whole video blue
        _, mask = cv2.threshold(blurred_map, 20, 255, cv2.THRESH_BINARY)
        mask_inv = cv2.bitwise_not(mask)
        
        frame_bg = cv2.bitwise_and(frame, frame, mask=mask_inv)
        frame_fg = cv2.bitwise_and(frame, frame, mask=mask)
        blended_fg = cv2.addWeighted(frame_fg, 1 - alpha, colored_map, alpha, 0)
        blended_fg = cv2.bitwise_and(blended_fg, blended_fg, mask=mask)
        
        result = cv2.add(frame_bg, blended_fg)
        return result

    def analyze(self, tracked_objects, person_boxes, frame_shape=None):
        """
        Analyzes crowd parameters:
        - current count
        - density level (SAFE, MODERATE, HIGH, CRITICAL_SURGE)
        - stampede / panic risk
        - in/out flow counts
        """
        if frame_shape and (frame_shape[0] != self.height or frame_shape[1] != self.width):
            self.height, self.width = frame_shape[:2]
            self.heatmap_grid = cv2.resize(self.heatmap_grid, (self.width // 4, self.height // 4))

        current_count = len(person_boxes)
        now = time.time()
        
        self.count_history.append(current_count)
        self.timestamp_history.append(now)
        
        # Update Heatmap
        self.update_heatmap(person_boxes)

        # Classify Density
        if current_count <= CROWD_LOW_THRESHOLD:
            density_level = "LOW"
        elif current_count <= CROWD_MEDIUM_THRESHOLD:
            density_level = "MODERATE"
        elif current_count <= CROWD_HIGH_THRESHOLD:
            density_level = "HIGH"
        else:
            density_level = "CRITICAL_SURGE"

        # Check Stampede / Panic Surge
        # Derivative of count over last 5 seconds
        surge_detected = False
        surge_reason = ""
        
        if len(self.count_history) >= 10:
            count_diff = self.count_history[-1] - self.count_history[0]
            time_diff = max(self.timestamp_history[-1] - self.timestamp_history[0], 0.1)
            rate_of_change = count_diff / time_diff

            if count_diff >= CROWD_SURGE_DELTA_THRESHOLD and rate_of_change > 1.2:
                surge_detected = True
                surge_reason = f"Rapid crowd influx: +{count_diff} people in {time_diff:.1f}s"
            elif density_level == "CRITICAL_SURGE":
                # Check average velocity of tracked people
                avg_velocity = np.mean([obj.velocity for obj in tracked_objects.values()]) if tracked_objects else 0
                if avg_velocity > 120.0:  # Rapid running/chaotic motion during dense crowd
                    surge_detected = True
                    surge_reason = f"High density + rapid directional flux ({avg_velocity:.1f} px/s) - Stampede Risk"

        # Tripwire Line Counter
        for obj_id, obj in tracked_objects.items():
            prev_y = self.tracked_positions.get(obj_id)
            curr_y = obj.centroid[1]
            
            if prev_y is not None:
                # Crossed downward (IN)
                if prev_y < self.line_y and curr_y >= self.line_y:
                    self.in_count += 1
                # Crossed upward (OUT)
                elif prev_y > self.line_y and curr_y <= self.line_y:
                    self.out_count += 1
            
            self.tracked_positions[obj_id] = curr_y

        # Clean old tracked positions
        active_ids = set(tracked_objects.keys())
        self.tracked_positions = {k: v for k, v in self.tracked_positions.items() if k in active_ids}

        return {
            "crowd_count": current_count,
            "density_level": density_level,
            "surge_detected": surge_detected,
            "surge_reason": surge_reason,
            "in_count": self.in_count,
            "out_count": self.out_count,
            "line_y": self.line_y
        }

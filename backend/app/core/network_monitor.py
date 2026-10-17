import cv2
import numpy as np
import time
from collections import deque
from backend.app.config import (
    TAMPER_BLUR_THRESHOLD,
    TAMPER_BLACKOUT_BRIGHTNESS,
    TAMPER_GLARE_BRIGHTNESS,
    STREAM_FPS_ALERT_THRESHOLD,
    STREAM_LATENCY_ALERT_MS
)

class CameraHealthMonitor:
    def __init__(self, camera_id, ip_address="192.168.1.100"):
        self.camera_id = camera_id
        self.ip_address = ip_address
        self.frame_timestamps = deque(maxlen=40)
        self.frame_sizes = deque(maxlen=40)
        self.last_frame_time = time.time()
        self.current_fps = 25.0
        self.current_bitrate_kbps = 2048.0
        self.current_latency_ms = 45.0
        self.packet_loss_pct = 0.0
        self.status = "ONLINE"  # ONLINE, DEGRADED, OFFLINE
        self.blur_score = 120.0
        self.brightness_score = 128.0

    def process_frame_health(self, frame, frame_bytes_len=None):
        """
        Calculates FPS, estimated bitrate, latency, and analyzes video for physical tampering/occlusion.
        Returns:
            dict with health metrics and tamper alerts.
        """
        now = time.time()
        self.frame_timestamps.append(now)
        
        # Calculate Latency & Packet delivery
        dt = now - self.last_frame_time
        self.last_frame_time = now
        self.current_latency_ms = max(round(dt * 1000.0, 1), 10.0)

        # Calculate Rolling FPS
        if len(self.frame_timestamps) >= 2:
            time_span = self.frame_timestamps[-1] - self.frame_timestamps[0]
            if time_span > 0:
                self.current_fps = round((len(self.frame_timestamps) - 1) / time_span, 1)

        # Calculate Rolling Bitrate (Kbps)
        if frame_bytes_len is not None:
            self.frame_sizes.append(frame_bytes_len)
            avg_frame_size = np.mean(self.frame_sizes)
            self.current_bitrate_kbps = round((avg_frame_size * 8 * self.current_fps) / 1000.0, 1)

        # Tamper & Occlusion Analysis
        tamper_detected = False
        tamper_reason = None

        if frame is not None and frame.size > 0:
            # Resize frame down for fast computation
            small = cv2.resize(frame, (320, 180))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

            # 1. Blur / Lens Occlusion via Laplacian Variance
            self.blur_score = round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 1)
            
            # 2. Mean Brightness for Blackout / Blindfold / Glare
            self.brightness_score = round(float(np.mean(gray)), 1)

            if self.brightness_score < TAMPER_BLACKOUT_BRIGHTNESS:
                tamper_detected = True
                tamper_reason = f"Camera blackout / lens covered (Brightness: {self.brightness_score})"
                self.status = "DEGRADED"
            elif self.brightness_score > TAMPER_GLARE_BRIGHTNESS:
                tamper_detected = True
                tamper_reason = f"High glare / flashlight blinding (Brightness: {self.brightness_score})"
                self.status = "DEGRADED"
            elif self.blur_score < TAMPER_BLUR_THRESHOLD:
                tamper_detected = True
                tamper_reason = f"Severe defocus / spray paint occlusion (Blur Score: {self.blur_score})"
                self.status = "DEGRADED"
            else:
                self.status = "ONLINE"
        else:
            self.status = "OFFLINE"
            tamper_detected = True
            tamper_reason = "No video frame received (Signal Loss)"

        # Check degraded stream FPS
        if self.current_fps < STREAM_FPS_ALERT_THRESHOLD and self.status == "ONLINE":
            self.status = "DEGRADED"

        return {
            "camera_id": self.camera_id,
            "status": self.status,
            "fps": self.current_fps,
            "bitrate_kbps": self.current_bitrate_kbps,
            "latency_ms": self.current_latency_ms,
            "packet_loss_pct": self.packet_loss_pct,
            "blur_score": self.blur_score,
            "brightness_score": self.brightness_score,
            "tamper_detected": tamper_detected,
            "tamper_reason": tamper_reason
        }

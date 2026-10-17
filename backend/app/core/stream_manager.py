import cv2
import numpy as np
import threading
import time
import logging
import json
import math
from pathlib import Path
from backend.app.config import (
    DEFAULT_STREAM_FPS,
    CROWD_HIGH_THRESHOLD,
    SNAPSHOT_DIR,
    SAMPLE_VIDEOS_DIR
)
from backend.app.analytics.detector import ObjectDetector
from backend.app.analytics.tracker import CentroidTracker
from backend.app.analytics.crowd_analyzer import CrowdAnalyzer
from backend.app.analytics.crime_analyzer import CrimeAnalyzer
from backend.app.core.network_monitor import CameraHealthMonitor
from backend.app.core.alert_manager import alert_manager
from backend.app.database import SessionLocal
from backend.app.models import Camera, Zone

logger = logging.getLogger("stream_manager")

class CameraStreamWorker:
    def __init__(self, camera_id: str, name: str, source_type: str, source_url: str, zones_config=None):
        self.camera_id = camera_id
        self.name = name
        self.source_type = source_type
        self.source_url = source_url
        self.zones = zones_config or []

        self.running = False
        self.capture_thread = None
        self.cap = None
        self.current_raw_frame = None
        self.current_processed_frame = None
        self.current_heatmap_frame = None
        self.lock = threading.Lock()

        # Analytics Components
        self.detector = ObjectDetector()
        self.tracker = CentroidTracker(max_disappeared=15, max_distance=70)
        self.crowd_analyzer = CrowdAnalyzer(frame_shape=(720, 1280))
        self.crime_analyzer = CrimeAnalyzer()
        self.health_monitor = CameraHealthMonitor(camera_id=camera_id)

        # Simulation state
        self.sim_step = 0
        self.sim_entities = []
        self._init_simulation_entities()

        # Latest Telemetry
        self.latest_telemetry = {
            "camera_id": self.camera_id,
            "camera_name": self.name,
            "status": "ONLINE",
            "fps": 25.0,
            "bitrate_kbps": 2048.0,
            "latency_ms": 40.0,
            "crowd_count": 0,
            "density_level": "LOW",
            "threat_level": "SAFE",
            "in_count": 0,
            "out_count": 0,
            "active_incidents": 0,
            "tamper_detected": False,
            "tamper_reason": None
        }

    def _init_simulation_entities(self):
        """Creates animated synthetic pedestrians for demo feeds."""
        self.sim_entities = []
        num_entities = 8 if "plaza" in self.camera_id.lower() or "cam-1" in self.camera_id.lower() else 4
        for i in range(num_entities):
            self.sim_entities.append({
                "id": i + 1,
                "x": np.random.randint(100, 1100),
                "y": np.random.randint(150, 600),
                "vx": np.random.uniform(-3.0, 3.0),
                "vy": np.random.uniform(-2.0, 2.0),
                "w": np.random.randint(45, 65),
                "h": np.random.randint(110, 145),
                "color": (np.random.randint(60, 240), np.random.randint(60, 240), np.random.randint(60, 240)),
                "is_intruder": (i == 0 and "vault" in self.camera_id.lower()) or (i == 1 and "cam-2" in self.camera_id.lower()),
                "is_falling": (i == 2 and "cam-3" in self.camera_id.lower()),
                "has_baggage": (i == 3 and "cam-4" in self.camera_id.lower())
            })

    def start(self):
        if self.running:
            return
        self.running = True
        self.capture_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.capture_thread.start()
        logger.info(f"Stream worker started for camera {self.camera_id} ({self.name})")

    def stop(self):
        self.running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=2.0)
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
        logger.info(f"Stream worker stopped for camera {self.camera_id}")

    def update_zones(self, zones):
        self.zones = zones

    def _get_frame(self):
        if self.source_type == "simulation":
            return self._generate_simulated_frame()
        elif self.source_type == "webcam":
            if self.cap is None or not self.cap.isOpened():
                try:
                    idx = int(self.source_url) if self.source_url.isdigit() else 0
                    self.cap = cv2.VideoCapture(idx)
                except Exception:
                    self.cap = None
            if self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    return frame
            return self._generate_simulated_frame()
        elif self.source_type in ("video_file", "rtsp"):
            if self.cap is None or not self.cap.isOpened():
                try:
                    self.cap = cv2.VideoCapture(self.source_url)
                except Exception:
                    self.cap = None
            if self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    return frame
                else:
                    # Loop video file
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = self.cap.read()
                    if ret:
                        return frame
            return self._generate_simulated_frame()
        
        return self._generate_simulated_frame()

    def _generate_simulated_frame(self):
        """Generates dynamic, realistic synthetic CCTV footage with environment backgrounds."""
        self.sim_step += 1
        t = self.sim_step * 0.04
        
        # Base frame (1280x720) with high-tech floor grid
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        
        # Background color gradients based on camera profile
        if "vault" in self.camera_id.lower() or "cam-2" in self.camera_id.lower():
            # Server room / High-security vault (cool blue-gray)
            frame[:] = (32, 28, 24)
            # Wall panels
            cv2.rectangle(frame, (0, 0), (1280, 200), (45, 38, 32), -1)
            cv2.line(frame, (0, 200), (1280, 200), (70, 60, 50), 2)
            # Server racks
            for rx in range(150, 1150, 220):
                cv2.rectangle(frame, (rx, 120), (rx + 140, 480), (22, 18, 15), -1)
                cv2.rectangle(frame, (rx, 120), (rx + 140, 480), (70, 55, 45), 2)
                # Blinking server LEDs
                for led_y in range(150, 460, 25):
                    led_color = (0, 255, 0) if (int(t * 5 + rx + led_y) % 7 != 0) else (0, 165, 255)
                    cv2.circle(frame, (rx + 20, led_y), 3, led_color, -1)
        elif "plaza" in self.camera_id.lower() or "cam-1" in self.camera_id.lower():
            # Public concourse / Plaza (warm ambient urban tile)
            frame[:] = (40, 42, 45)
            # Tiled pavement perspective
            for y in range(250, 720, 40):
                cv2.line(frame, (0, y), (1280, y), (55, 58, 62), 1)
            for x in range(0, 1280, 80):
                cv2.line(frame, (x, 250), (int(x * 1.3 - 150), 720), (55, 58, 62), 1)
            # Planters / benches
            cv2.rectangle(frame, (200, 350), (400, 430), (28, 48, 30), -1)
            cv2.rectangle(frame, (880, 350), (1080, 430), (28, 48, 30), -1)
        elif "perimeter" in self.camera_id.lower() or "cam-3" in self.camera_id.lower():
            # Perimeter fence & emergency lane
            frame[:] = (20, 25, 22)
            # Chainlink fence line
            for fx in range(50, 1250, 30):
                cv2.line(frame, (fx, 80), (fx + 15, 320), (60, 75, 65), 1)
                cv2.line(frame, (fx + 15, 80), (fx, 320), (60, 75, 65), 1)
            cv2.line(frame, (0, 320), (1280, 320), (90, 110, 95), 3)
            # Warning stripes
            for sx in range(0, 1280, 100):
                cv2.line(frame, (sx, 680), (sx + 50, 720), (0, 200, 255), 4)
        else:
            # Transit Hall / Terminal Gate
            frame[:] = (35, 35, 38)
            cv2.rectangle(frame, (0, 0), (1280, 180), (50, 50, 55), -1)
            # Turnstiles / Gates
            for gx in range(300, 1000, 160):
                cv2.rectangle(frame, (gx, 380), (gx + 60, 520), (80, 80, 90), -1)

        # Dynamic crowd surges in Cam 1
        if "plaza" in self.camera_id.lower() or "cam-1" in self.camera_id.lower():
            # Periodic crowd gathering pulse every 25 seconds
            surge_cycle = (int(t) % 30)
            if surge_cycle > 18:
                # Add temporary surge pedestrians
                while len(self.sim_entities) < 22:
                    self.sim_entities.append({
                        "id": len(self.sim_entities) + 1,
                        "x": np.random.randint(350, 850),
                        "y": np.random.randint(300, 620),
                        "vx": np.random.uniform(-4.0, 4.0),
                        "vy": np.random.uniform(-3.0, 3.0),
                        "w": np.random.randint(45, 65),
                        "h": np.random.randint(110, 145),
                        "color": (np.random.randint(80, 240), np.random.randint(80, 240), np.random.randint(80, 240)),
                        "is_intruder": False,
                        "is_falling": False,
                        "has_baggage": False
                    })
            else:
                if len(self.sim_entities) > 8:
                    self.sim_entities.pop()

        # Update and render synthetic entities
        for ent in self.sim_entities:
            # Move entities
            ent["x"] += ent["vx"]
            ent["y"] += ent["vy"]

            # Bounce off bounds
            if ent["x"] < 80:
                ent["x"] = 80
                ent["vx"] *= -1
            elif ent["x"] > 1180:
                ent["x"] = 1180
                ent["vx"] *= -1

            if ent["y"] < 220:
                ent["y"] = 220
                ent["vy"] *= -1
            elif ent["y"] > 620:
                ent["y"] = 620
                ent["vy"] *= -1

            ex, ey = int(ent["x"]), int(ent["y"])
            ew, eh = ent["w"], ent["h"]
            ecolor = ent["color"]

            # Draw simulated pedestrian silhouette
            if ent.get("is_falling"):
                # Prone fallen pose
                cv2.ellipse(frame, (ex, ey), (eh // 2, ew // 2), 0, 0, 360, ecolor, -1)
                cv2.circle(frame, (ex - eh // 2 + 10, ey), 16, (220, 180, 160), -1)
            else:
                # Upright human silhouette
                # Head
                cv2.circle(frame, (ex, ey - eh // 2 + 15), 16, (220, 180, 160), -1)
                # Torso
                cv2.rectangle(frame, (ex - ew // 2, ey - eh // 2 + 32), (ex + ew // 2, ey + eh // 4), ecolor, -1)
                # Legs
                cv2.line(frame, (ex - 10, ey + eh // 4), (ex - 12, ey + eh // 2), (40, 40, 50), 8)
                cv2.line(frame, (ex + 10, ey + eh // 4), (ex + 12, ey + eh // 2), (40, 40, 50), 8)

            # Unattended Baggage simulation
            if ent.get("has_baggage"):
                bx, by = ex + 45, ey + eh // 2 - 10
                cv2.rectangle(frame, (bx - 18, by - 22), (bx + 18, by + 10), (180, 100, 30), -1)
                cv2.rectangle(frame, (bx - 18, by - 22), (bx + 18, by + 10), (240, 160, 60), 2)
                cv2.line(frame, (bx - 8, by - 26), (bx + 8, by - 26), (200, 200, 200), 2)

        # Subtle camera scanline & grain
        scanline_y = int((t * 120) % 720)
        cv2.line(frame, (0, scanline_y), (1280, scanline_y), (120, 150, 180), 1)

        return frame

    def _run_loop(self):
        """Continuous pipeline loop executing detection, tracking, crowd & crime analytics."""
        target_frame_time = 1.0 / DEFAULT_STREAM_FPS

        while self.running:
            start_time = time.time()

            raw_frame = self._get_frame()
            if raw_frame is None:
                time.sleep(0.04)
                continue

            with self.lock:
                self.current_raw_frame = raw_frame.copy()

            # 1. Network Health & Tampering Analysis
            health_metrics = self.health_monitor.process_frame_health(raw_frame)
            if health_metrics["tamper_detected"]:
                alert_manager.trigger_alert(
                    camera_id=self.camera_id,
                    camera_name=self.name,
                    incident_type="CAMERA_TAMPER",
                    severity="HIGH",
                    description=health_metrics["tamper_reason"],
                    frame=raw_frame
                )

            # 2. Object & Person Detection
            detections = self.detector.detect(raw_frame)
            person_boxes = [d["box"] for d in detections if d["class_name"] == "person"]
            class_names = [d["class_name"] for d in detections]
            all_boxes = [d["box"] for d in detections]

            # 3. Object Tracking
            tracked_objects = self.tracker.update(all_boxes, class_names)

            # 4. Crowd Analytics & Surge Detection
            crowd_results = self.crowd_analyzer.analyze(
                tracked_objects=tracked_objects,
                person_boxes=person_boxes,
                frame_shape=raw_frame.shape
            )

            if crowd_results["surge_detected"]:
                alert_manager.trigger_alert(
                    camera_id=self.camera_id,
                    camera_name=self.name,
                    incident_type="CROWD_SURGE",
                    severity="CRITICAL" if crowd_results["density_level"] == "CRITICAL_SURGE" else "HIGH",
                    description=crowd_results["surge_reason"],
                    frame=raw_frame
                )

            # 5. Crime & Threat Analytics
            # Zone Intrusions & Loitering
            intrusions, loitering_events = self.crime_analyzer.check_zone_intrusion(
                tracked_objects=tracked_objects,
                zones=self.zones
            )

            for intr in intrusions:
                alert_manager.trigger_alert(
                    camera_id=self.camera_id,
                    camera_name=self.name,
                    incident_type="RESTRICTED_INTRUSION",
                    severity="CRITICAL",
                    description=intr["description"],
                    frame=raw_frame
                )

            for loit in loitering_events:
                alert_manager.trigger_alert(
                    camera_id=self.camera_id,
                    camera_name=self.name,
                    incident_type="LOITERING",
                    severity="MEDIUM",
                    description=loit["description"],
                    frame=raw_frame
                )

            # Falls and Physical Altercations
            fall_events, violence_events = self.crime_analyzer.check_falls_and_violence(
                tracked_objects=tracked_objects,
                current_frame=raw_frame
            )

            for fall in fall_events:
                alert_manager.trigger_alert(
                    camera_id=self.camera_id,
                    camera_name=self.name,
                    incident_type="FALL_DETECTED",
                    severity="HIGH",
                    description=fall["description"],
                    frame=raw_frame
                )

            for viol in violence_events:
                alert_manager.trigger_alert(
                    camera_id=self.camera_id,
                    camera_name=self.name,
                    incident_type="VIOLENCE_FIGHT",
                    severity="CRITICAL",
                    description=viol["description"],
                    frame=raw_frame
                )

            # Unattended Baggage
            abandoned = self.crime_analyzer.check_abandoned_objects(
                detections=detections,
                tracked_objects=tracked_objects,
                camera_id=self.camera_id
            )

            for item in abandoned:
                alert_manager.trigger_alert(
                    camera_id=self.camera_id,
                    camera_name=self.name,
                    incident_type="ABANDONED_OBJECT",
                    severity="HIGH",
                    description=item["description"],
                    frame=raw_frame
                )

            # Determine Threat Level
            threat_level = "SAFE"
            if len(intrusions) > 0 or len(violence_events) > 0 or crowd_results["density_level"] == "CRITICAL_SURGE":
                threat_level = "CRITICAL"
            elif len(fall_events) > 0 or len(abandoned) > 0 or crowd_results["density_level"] == "HIGH":
                threat_level = "ELEVATED"
            elif len(loitering_events) > 0 or crowd_results["density_level"] == "MODERATE":
                threat_level = "GUARDED"

            # 6. Render Overlays
            processed_frame = self._render_overlays(
                frame=raw_frame.copy(),
                detections=detections,
                tracked_objects=tracked_objects,
                crowd_results=crowd_results,
                threat_level=threat_level
            )

            heatmap_frame = self.crowd_analyzer.generate_heatmap_overlay(raw_frame.copy())

            with self.lock:
                self.current_processed_frame = processed_frame
                self.current_heatmap_frame = heatmap_frame
                self.latest_telemetry = {
                    "camera_id": self.camera_id,
                    "camera_name": self.name,
                    "status": health_metrics["status"],
                    "fps": health_metrics["fps"],
                    "bitrate_kbps": health_metrics["bitrate_kbps"],
                    "latency_ms": health_metrics["latency_ms"],
                    "crowd_count": crowd_results["crowd_count"],
                    "density_level": crowd_results["density_level"],
                    "threat_level": threat_level,
                    "in_count": crowd_results["in_count"],
                    "out_count": crowd_results["out_count"],
                    "active_incidents": len(intrusions) + len(violence_events) + len(fall_events),
                    "tamper_detected": health_metrics["tamper_detected"],
                    "tamper_reason": health_metrics["tamper_reason"]
                }

            # Frame rate throttle
            elapsed = time.time() - start_time
            sleep_time = max(0, target_frame_time - elapsed)
            time.sleep(sleep_time)

    def _render_overlays(self, frame, detections, tracked_objects, crowd_results, threat_level):
        """Draws bounding boxes, IDs, HUD telemetry, restricted polygons, and HUD widgets."""
        h, w = frame.shape[:2]

        # 1. Draw Zones
        for zone in self.zones:
            if not zone.get("is_active", True):
                continue
            try:
                poly_raw = zone.get("polygon_points", "[]")
                points = np.array(json.loads(poly_raw) if isinstance(poly_raw, str) else poly_raw, dtype=np.int32)
                if len(points) >= 3:
                    pts = points.reshape((-1, 1, 2))
                    color = (0, 0, 220) if zone.get("zone_type") == "RESTRICTED" else (255, 180, 0)
                    cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=2)
                    
                    # Fill semi-transparent zone polygon
                    overlay = frame.copy()
                    cv2.fillPoly(overlay, [pts], color)
                    cv2.addWeighted(overlay, 0.22, frame, 0.78, 0, frame)

                    # Label zone
                    cx = int(np.mean(points[:, 0]))
                    cy = int(np.mean(points[:, 1]))
                    cv2.putText(frame, zone.get("name", "ZONE"), (cx - 40, cy),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
            except Exception:
                pass

        # 2. Draw Tripwire Line
        line_y = crowd_results.get("line_y", int(h * 0.6))
        cv2.line(frame, (50, line_y), (w - 50, line_y), (0, 255, 255), 2)
        cv2.putText(frame, f"VIRTUAL TRIPWIRE [IN: {crowd_results['in_count']} | OUT: {crowd_results['out_count']}]",
                    (60, line_y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        # 3. Draw Tracked Detections
        for obj_id, obj in tracked_objects.items():
            x1, y1, x2, y2 = obj.bbox
            cls_name = obj.class_name
            color = (0, 255, 120) if cls_name == "person" else (255, 120, 0)
            
            # Highlight intruders in red
            if obj.in_zone:
                color = (0, 0, 255)

            # Bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # Corner accents
            c_len = 12
            cv2.line(frame, (x1, y1), (x1 + c_len, y1), (255, 255, 255), 2)
            cv2.line(frame, (x1, y1), (x1, y1 + c_len), (255, 255, 255), 2)
            cv2.line(frame, (x2, y2), (x2 - c_len, y2), (255, 255, 255), 2)
            cv2.line(frame, (x2, y2), (x2, y2 - c_len), (255, 255, 255), 2)

            # Tracking history tail
            if len(obj.history) > 1:
                for i in range(1, len(obj.history)):
                    cv2.line(frame, obj.history[i - 1], obj.history[i], (0, 200, 255), 2)

            # Label badge
            label = f"#{obj_id} {cls_name}"
            if obj.dwell_time > 3.0:
                label += f" ({obj.dwell_time:.0f}s)"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.rectangle(frame, (x1, max(y1 - 20, 0)), (x1 + tw + 10, max(y1, 20)), color, -1)
            cv2.putText(frame, label, (x1 + 4, max(y1 - 6, 14)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)

        # 4. Top HUD Header Bar
        hud_bg = np.zeros((48, w, 3), dtype=np.uint8)
        cv2.rectangle(hud_bg, (0, 0), (w, 48), (15, 18, 24), -1)
        frame[0:48, 0:w] = cv2.addWeighted(frame[0:48, 0:w], 0.3, hud_bg, 0.7, 0)
        
        # Camera Name & Status
        cv2.putText(frame, f"CAM: {self.name.upper()}", (16, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 240, 255), 2)

        # Crowd Density Badge
        d_color = (0, 255, 120) if crowd_results["density_level"] == "LOW" else (
            (0, 215, 255) if crowd_results["density_level"] == "MODERATE" else (
                (0, 140, 255) if crowd_results["density_level"] == "HIGH" else (0, 0, 255)
            )
        )
        crowd_str = f"CROWD: {crowd_results['crowd_count']} ({crowd_results['density_level']})"
        cv2.putText(frame, crowd_str, (320, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, d_color, 2)

        # Threat Level Badge
        t_color = (0, 255, 120) if threat_level == "SAFE" else (
            (0, 200, 255) if threat_level == "GUARDED" else (
                (0, 120, 255) if threat_level == "ELEVATED" else (0, 0, 255)
            )
        )
        cv2.putText(frame, f"THREAT: {threat_level}", (680, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, t_color, 2)

        # Time & FPS
        curr_time = time.strftime("%H:%M:%S")
        cv2.putText(frame, f"{curr_time} | {self.health_monitor.current_fps:.1f} FPS", (w - 220, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

        return frame

    def get_jpeg_frame(self, view_mode="processed"):
        """Returns encoded JPEG byte string for MJPEG streaming."""
        with self.lock:
            if view_mode == "heatmap" and self.current_heatmap_frame is not None:
                target_frame = self.current_heatmap_frame
            elif view_mode == "raw" and self.current_raw_frame is not None:
                target_frame = self.current_raw_frame
            elif self.current_processed_frame is not None:
                target_frame = self.current_processed_frame
            else:
                target_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
                cv2.putText(target_frame, "INITIALIZING CAMERA FEED...", (400, 360),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)

        ret, buffer = cv2.imencode('.jpg', target_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return buffer.tobytes() if ret else b""


class StreamManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StreamManager, cls).__new__(cls)
            cls._instance.workers = {}  # camera_id -> CameraStreamWorker
            cls._instance.is_initialized = False
        return cls._instance

    def initialize_default_cameras(self):
        if self.is_initialized:
            return

        db = SessionLocal()
        try:
            # Seed default cameras if table is empty
            count = db.query(Camera).count()
            if count == 0:
                default_cams = [
                    Camera(
                        id="cam-1",
                        name="Main Plaza Concourse",
                        location="Sector A - Public Plaza",
                        source_type="simulation",
                        source_url="",
                        ip_address="192.168.1.101",
                        latitude=37.7749,
                        longitude=-122.4194,
                        crowd_limit=20,
                        is_active=True
                    ),
                    Camera(
                        id="cam-2",
                        name="Vault & Server Room",
                        location="Sector B - Secure Wing",
                        source_type="simulation",
                        source_url="",
                        ip_address="192.168.1.102",
                        latitude=37.7752,
                        longitude=-122.4188,
                        crowd_limit=3,
                        is_active=True
                    ),
                    Camera(
                        id="cam-3",
                        name="Perimeter & Fence Gate",
                        location="Sector C - Outer Boundary",
                        source_type="simulation",
                        source_url="",
                        ip_address="192.168.1.103",
                        latitude=37.7744,
                        longitude=-122.4201,
                        crowd_limit=8,
                        is_active=True
                    ),
                    Camera(
                        id="cam-4",
                        name="Transit Hall Turnstiles",
                        location="Sector D - Entry Terminal",
                        source_type="simulation",
                        source_url="",
                        ip_address="192.168.1.104",
                        latitude=37.7758,
                        longitude=-122.4198,
                        crowd_limit=15,
                        is_active=True
                    ),
                ]
                db.add_all(default_cams)
                db.commit()

                # Seed sample restricted zone for Vault camera
                vault_zone = Zone(
                    camera_id="cam-2",
                    name="Restricted Server Vault",
                    zone_type="RESTRICTED",
                    polygon_points=json.dumps([[300, 200], [980, 200], [980, 650], [300, 650]]),
                    alert_on_intrusion=True,
                    is_active=True
                )
                db.add(vault_zone)
                db.commit()

            # Start workers for active cameras
            cameras = db.query(Camera).filter(Camera.is_active == True).all()
            for cam in cameras:
                zones = [
                    {"name": z.name, "zone_type": z.zone_type, "polygon_points": z.polygon_points, "is_active": z.is_active}
                    for z in cam.zones
                ]
                worker = CameraStreamWorker(
                    camera_id=cam.id,
                    name=cam.name,
                    source_type=cam.source_type,
                    source_url=cam.source_url,
                    zones_config=zones
                )
                worker.start()
                self.workers[cam.id] = worker

            self.is_initialized = True
            logger.info(f"Stream Manager initialized with {len(self.workers)} camera workers.")
        except Exception as e:
            logger.error(f"Error initializing default cameras: {e}")
            db.rollback()
        finally:
            db.close()

    def add_camera(self, camera_id: str, name: str, source_type: str, source_url: str, zones=None):
        if camera_id in self.workers:
            self.workers[camera_id].stop()
        
        worker = CameraStreamWorker(camera_id, name, source_type, source_url, zones)
        worker.start()
        self.workers[camera_id] = worker
        return worker

    def remove_camera(self, camera_id: str):
        if camera_id in self.workers:
            self.workers[camera_id].stop()
            del self.workers[camera_id]

    def get_worker(self, camera_id: str) -> CameraStreamWorker:
        return self.workers.get(camera_id)

    def get_all_telemetry(self):
        return [w.latest_telemetry for w in self.workers.values()]

    def shutdown_all(self):
        for w in self.workers.values():
            w.stop()
        self.workers.clear()

stream_manager = StreamManager()

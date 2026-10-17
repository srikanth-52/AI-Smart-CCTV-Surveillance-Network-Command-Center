import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
SAMPLE_VIDEOS_DIR = DATA_DIR / "sample_videos"
DB_PATH = DATA_DIR / "surveillance.db"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

# Database
DATABASE_URL = f"sqlite:///{DB_PATH}"

# AI Analytics Settings
AI_MODEL_NAME = os.getenv("AI_MODEL_NAME", "yolov8n.pt")  # Ultralytics lightweight model
DETECTION_CONFIDENCE = float(os.getenv("DETECTION_CONFIDENCE", "0.40"))
PERSON_CLASS_ID = 0  # COCO person class

# Crowd Analytics Thresholds
CROWD_LOW_THRESHOLD = 5
CROWD_MEDIUM_THRESHOLD = 12
CROWD_HIGH_THRESHOLD = 20
CROWD_SURGE_DELTA_THRESHOLD = 6  # Increase of >= 6 people in < 5 seconds indicates surge/panic

# Crime Prevention & Anomaly Thresholds
LOITERING_TIME_THRESHOLD_SEC = 10.0  # Seconds spent in zone before alert
VIOLENCE_MOTION_THRESHOLD = 75.0      # Sudden erratic frame displacement metric
FALL_ASPECT_RATIO_THRESHOLD = 0.65   # Width > Height * 1.5 indicates fallen/horizontal person
ABANDONED_OBJECT_TIME_SEC = 15.0     # Stationary luggage/object alert

# Camera Health & Tamper Detection Thresholds
TAMPER_BLUR_THRESHOLD = 45.0         # Laplacian variance below this indicates blur/occlusion
TAMPER_BLACKOUT_BRIGHTNESS = 15.0    # Mean pixel brightness below this indicates covered/blackout
TAMPER_GLARE_BRIGHTNESS = 240.0      # Mean pixel brightness above this indicates blinding light
STREAM_FPS_ALERT_THRESHOLD = 5.0     # Alert if FPS drops below this value
STREAM_LATENCY_ALERT_MS = 800.0      # Alert if stream lag exceeds 800ms

# System Settings
ALERT_COOLDOWN_SEC = 8.0             # Minimum seconds between duplicate alerts for same event
MAX_SNAPSHOT_RETENTION = 500         # Max saved snapshot images
DEFAULT_STREAM_FPS = 25

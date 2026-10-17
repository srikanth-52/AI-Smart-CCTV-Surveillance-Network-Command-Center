import os
import sys
import numpy as np
import cv2
import json

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import Camera, Zone, Incident
from backend.app.analytics.detector import ObjectDetector
from backend.app.analytics.tracker import CentroidTracker
from backend.app.analytics.crowd_analyzer import CrowdAnalyzer
from backend.app.analytics.crime_analyzer import CrimeAnalyzer
from backend.app.core.network_monitor import CameraHealthMonitor
from backend.app.core.stream_manager import CameraStreamWorker, stream_manager

def run_tests():
    print("==================================================")
    print("[RUNNING] AUTOMATED SYSTEM VERIFICATION TESTS")
    print("==================================================")

    # 1. Test Database
    print("[1/6] Testing Database Models & Tables...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    cams = db.query(Camera).all()
    print(f"      [OK] Database initialized. Existing cameras: {len(cams)}")
    db.close()

    # 2. Test Object Detector
    print("[2/6] Testing Object Detector...")
    detector = ObjectDetector()
    dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    cv2.rectangle(dummy_frame, (200, 200), (300, 500), (255, 255, 255), -1)
    dets = detector.detect(dummy_frame)
    print(f"      [OK] Object detector executed successfully. Detected items: {len(dets)}")

    # 3. Test Centroid Tracker
    print("[3/6] Testing Centroid Tracker...")
    tracker = CentroidTracker()
    boxes = [[100, 100, 200, 300], [400, 200, 500, 450]]
    objects = tracker.update(boxes)
    assert len(objects) == 2, "Expected 2 tracked objects"
    print(f"      [OK] Tracker registered {len(objects)} active targets with IDs: {list(objects.keys())}")

    # 4. Test Crowd Analyzer & Heatmaps
    print("[4/6] Testing Crowd Density & Heatmap Engine...")
    crowd_analyzer = CrowdAnalyzer(frame_shape=(720, 1280))
    result = crowd_analyzer.analyze(objects, boxes)
    assert result["crowd_count"] == 2
    heatmap = crowd_analyzer.generate_heatmap_overlay(dummy_frame)
    assert heatmap is not None and heatmap.shape == dummy_frame.shape
    print(f"      [OK] Crowd density: {result['density_level']}, In/Out: {result['in_count']}/{result['out_count']}, Heatmap generated.")

    # 5. Test Crime Analyzer & Zone Intrusion
    print("[5/6] Testing Restricted Zone Intrusion...")
    crime_analyzer = CrimeAnalyzer()
    test_zone = [{
        "name": "Restricted Vault",
        "zone_type": "RESTRICTED",
        "polygon_points": json.dumps([[50, 50], [250, 50], [250, 350], [50, 350]]),
        "is_active": True
    }]
    intrusions, loitering = crime_analyzer.check_zone_intrusion(objects, test_zone)
    print(f"      [OK] Zone check completed. Detected {len(intrusions)} intrusion(s).")

    # 6. Test Stream Manager & Frame Generation
    print("[6/6] Testing Stream Worker & Frame Generation...")
    worker = CameraStreamWorker("test-cam", "Test Verification Cam", "simulation", "")
    worker.start()
    import time
    time.sleep(0.5)
    frame_bytes = worker.get_jpeg_frame(view_mode="processed")
    assert len(frame_bytes) > 0, "Failed to get JPEG frame"
    worker.stop()
    print(f"      [OK] Live stream worker generated valid JPEG frame ({len(frame_bytes)} bytes).")

    print("\n==================================================")
    print("[SUCCESS] ALL 6 VERIFICATION TEST SUITES PASSED!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()

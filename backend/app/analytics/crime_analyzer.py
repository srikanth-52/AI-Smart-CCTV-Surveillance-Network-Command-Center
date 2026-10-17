import cv2
import numpy as np
import time
import json
from backend.app.config import (
    LOITERING_TIME_THRESHOLD_SEC,
    VIOLENCE_MOTION_THRESHOLD,
    FALL_ASPECT_RATIO_THRESHOLD,
    ABANDONED_OBJECT_TIME_SEC
)

class CrimeAnalyzer:
    def __init__(self):
        self.loitering_alerts = {}  # (camera_id, object_id) -> last_alert_time
        self.intrusion_alerts = {}  # (camera_id, object_id, zone_name) -> last_alert_time
        self.abandoned_objects = {} # (camera_id, object_id) -> {'first_seen': t, 'box': [], 'alerted': bool}
        self.prev_gray_frame = None

    def check_zone_intrusion(self, tracked_objects, zones):
        """
        zones: list of Zone models or dicts with 'name', 'polygon_points', 'zone_type'
        """
        intrusions = []
        loitering_events = []

        for zone in zones:
            if not zone.get("is_active", True):
                continue

            try:
                poly_raw = zone.get("polygon_points", "[]")
                if isinstance(poly_raw, str):
                    points = np.array(json.loads(poly_raw), dtype=np.int32)
                else:
                    points = np.array(poly_raw, dtype=np.int32)
                
                if len(points) < 3:
                    continue
            except Exception:
                continue

            zone_name = zone.get("name", "Restricted Area")
            zone_type = zone.get("zone_type", "RESTRICTED")

            for obj_id, obj in tracked_objects.items():
                cx, cy = obj.centroid
                
                # Check if centroid is inside polygon (>= 0 means on edge or inside)
                is_inside = cv2.pointPolygonTest(points, (float(cx), float(cy)), False) >= 0

                if is_inside:
                    if not obj.in_zone:
                        obj.in_zone = True
                        obj.zone_entry_time = time.time()
                    
                    time_in_zone = time.time() - (obj.zone_entry_time or time.time())

                    # Check Intrusion
                    if zone_type == "RESTRICTED":
                        intrusions.append({
                            "object_id": obj_id,
                            "zone_name": zone_name,
                            "centroid": obj.centroid,
                            "bbox": obj.bbox,
                            "description": f"Intruder detected in restricted zone '{zone_name}' (ID: #{obj_id})"
                        })

                    # Check Loitering in any designated zone
                    if time_in_zone >= LOITERING_TIME_THRESHOLD_SEC:
                        loitering_events.append({
                            "object_id": obj_id,
                            "zone_name": zone_name,
                            "dwell_time": time_in_zone,
                            "centroid": obj.centroid,
                            "bbox": obj.bbox,
                            "description": f"Loitering alert: Person #{obj_id} lingering in '{zone_name}' for {time_in_zone:.1f}s"
                        })
                else:
                    if obj.in_zone:
                        obj.in_zone = False
                        obj.zone_entry_time = None

        return intrusions, loitering_events

    def check_falls_and_violence(self, tracked_objects, current_frame):
        """
        Evaluates physical anomalies:
        - Fall / Medical Collapse: Aspect ratio check (horizontal bounding box)
        - Violent struggle / Fight: Multiple closely overlapping bboxes with high motion variance
        """
        fall_events = []
        violence_events = []

        obj_list = list(tracked_objects.values())

        # 1. Fall / Collapse Check
        for obj in obj_list:
            x1, y1, x2, y2 = obj.bbox
            w = max(x2 - x1, 1)
            h = max(y2 - y1, 1)
            aspect_ratio = h / float(w)

            # A standing human typically has aspect_ratio >= 1.8. If aspect_ratio < 0.8, they are horizontal/fallen
            if aspect_ratio < FALL_ASPECT_RATIO_THRESHOLD and h < 120 and w > 80:
                fall_events.append({
                    "object_id": obj.object_id,
                    "centroid": obj.centroid,
                    "bbox": obj.bbox,
                    "description": f"Fall/Distress anomaly: Subject #{obj.object_id} detected in prone position"
                })

        # 2. Violence / Struggle Check
        # Check pairwise distances between tracked persons
        for i in range(len(obj_list)):
            for j in range(i + 1, len(obj_list)):
                o1, o2 = obj_list[i], obj_list[j]
                dist = np.linalg.norm(np.array(o1.centroid) - np.array(o2.centroid))

                # Close proximity (< 70px) + high combined movement velocity
                if dist < 70 and (o1.velocity + o2.velocity) > VIOLENCE_MOTION_THRESHOLD:
                    violence_events.append({
                        "object_ids": [o1.object_id, o2.object_id],
                        "centroid": ((o1.centroid[0] + o2.centroid[0]) // 2, (o1.centroid[1] + o2.centroid[1]) // 2),
                        "bbox": [
                            min(o1.bbox[0], o2.bbox[0]),
                            min(o1.bbox[1], o2.bbox[1]),
                            max(o1.bbox[2], o2.bbox[2]),
                            max(o1.bbox[3], o2.bbox[3])
                        ],
                        "description": f"Physical struggle / violent altercation between #{o1.object_id} and #{o2.object_id}"
                    })

        return fall_events, violence_events

    def check_abandoned_objects(self, detections, tracked_objects, camera_id):
        """
        Detects unattended luggage, backpacks, and stationary objects.
        """
        abandoned = []
        luggage_classes = {"backpack", "handbag", "suitcase", "bag", "box"}
        
        luggage_dets = [d for d in detections if d.get("class_name") in luggage_classes]

        now = time.time()
        for idx, item in enumerate(luggage_dets):
            item_box = item["box"]
            item_cx = (item_box[0] + item_box[2]) // 2
            item_cy = (item_box[1] + item_box[3]) // 2

            # Find nearest person
            min_dist = float('inf')
            for obj in tracked_objects.values():
                d = np.linalg.norm(np.array([item_cx, item_cy]) - np.array(obj.centroid))
                if d < min_dist:
                    min_dist = d

            item_key = f"{camera_id}_{item_cx // 40}_{item_cy // 40}"
            
            # If no person is within 120 pixels, start tracking stationary time
            if min_dist > 120:
                if item_key not in self.abandoned_objects:
                    self.abandoned_objects[item_key] = {"first_seen": now, "box": item_box, "alerted": False}
                else:
                    elapsed = now - self.abandoned_objects[item_key]["first_seen"]
                    if elapsed > ABANDONED_OBJECT_TIME_SEC and not self.abandoned_objects[item_key]["alerted"]:
                        self.abandoned_objects[item_key]["alerted"] = True
                        abandoned.append({
                            "class_name": item.get("class_name", "object"),
                            "bbox": item_box,
                            "centroid": (item_cx, item_cy),
                            "dwell_time": elapsed,
                            "description": f"Unattended {item.get('class_name', 'baggage')} left isolated for {elapsed:.1f}s"
                        })
            else:
                if item_key in self.abandoned_objects:
                    del self.abandoned_objects[item_key]

        return abandoned

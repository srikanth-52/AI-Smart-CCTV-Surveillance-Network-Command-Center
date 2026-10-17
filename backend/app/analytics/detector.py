import cv2
import numpy as np
import logging
from backend.app.config import AI_MODEL_NAME, DETECTION_CONFIDENCE, PERSON_CLASS_ID

logger = logging.getLogger("detector")

class ObjectDetector:
    def __init__(self, model_name=AI_MODEL_NAME, conf_thresh=DETECTION_CONFIDENCE):
        self.model_name = model_name
        self.conf_thresh = conf_thresh
        self.yolo_model = None
        self.use_fallback = False
        self._init_model()

    def _init_model(self):
        try:
            from ultralytics import YOLO
            logger.info(f"Loading YOLO model: {self.model_name}...")
            self.yolo_model = YOLO(self.model_name)
            logger.info("YOLO model loaded successfully.")
        except Exception as e:
            logger.warning(f"Could not load Ultralytics YOLO ({e}). Initializing OpenCV HOG fallback detector.")
            self.use_fallback = True
            self.hog = cv2.HOGDescriptor()
            self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def detect(self, frame):
        """
        Runs object detection on a BGR frame.
        Returns:
            list of dict: [
                {
                    "box": [x1, y1, x2, y2],
                    "confidence": float,
                    "class_id": int,
                    "class_name": str
                }
            ]
        """
        detections = []
        if frame is None or frame.size == 0:
            return detections

        if self.yolo_model and not self.use_fallback:
            try:
                results = self.yolo_model(frame, conf=self.conf_thresh, verbose=False)
                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                        conf = float(box.conf[0].cpu().numpy())
                        cls_id = int(box.cls[0].cpu().numpy())
                        cls_name = r.names[cls_id] if hasattr(r, 'names') and cls_id in r.names else str(cls_id)
                        
                        detections.append({
                            "box": [int(x1), int(y1), int(x2), int(y2)],
                            "confidence": conf,
                            "class_id": cls_id,
                            "class_name": cls_name
                        })
                return detections
            except Exception as e:
                logger.error(f"YOLO inference error: {e}")

        # Fallback using OpenCV HOG for person detection
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            boxes, weights = self.hog.detectMultiScale(gray, winStride=(8, 8), padding=(4, 4), scale=1.05)
            for (x, y, w, h), weight in zip(boxes, weights):
                if weight > 0.2:
                    detections.append({
                        "box": [int(x), int(y), int(x + w), int(y + h)],
                        "confidence": float(weight),
                        "class_id": 0,
                        "class_name": "person"
                    })
        except Exception as e:
            logger.error(f"Fallback detector error: {e}")

        return detections

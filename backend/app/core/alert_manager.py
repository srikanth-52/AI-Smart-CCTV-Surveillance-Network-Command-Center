import cv2
import time
import os
import datetime
import logging
from pathlib import Path
from backend.app.config import SNAPSHOT_DIR, ALERT_COOLDOWN_SEC, MAX_SNAPSHOT_RETENTION
from backend.app.database import SessionLocal
from backend.app.models import Incident, SystemLog

logger = logging.getLogger("alert_manager")

class AlertManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AlertManager, cls).__new__(cls)
            cls._instance.active_connections = set()
            cls._instance.last_alert_timestamps = {}  # (camera_id, incident_type) -> timestamp
        return cls._instance

    def register_websocket(self, websocket):
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client registered. Total clients: {len(self.active_connections)}")

    def unregister_websocket(self, websocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Asynchronously sends JSON payload to all connected frontend clients."""
        disconnected = set()
        for ws in self.active_connections:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.add(ws)
        
        for ws in disconnected:
            self.active_connections.discard(ws)

    def trigger_alert(self, camera_id: str, camera_name: str, incident_type: str, 
                      severity: str, description: str, frame=None, force: bool = False):
        """
        Creates and stores an incident if outside cooldown window, and triggers notifications.
        """
        now = time.time()
        cooldown_key = f"{camera_id}_{incident_type}"
        last_time = self.last_alert_timestamps.get(cooldown_key, 0)

        # Check cooldown unless forced
        if not force and (now - last_time < ALERT_COOLDOWN_SEC):
            return None

        self.last_alert_timestamps[cooldown_key] = now

        # Save snapshot
        snapshot_filename = ""
        if frame is not None and frame.size > 0:
            timestamp_str = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
            snapshot_filename = f"snap_{camera_id}_{incident_type}_{timestamp_str}.jpg"
            snapshot_path = SNAPSHOT_DIR / snapshot_filename
            try:
                # Add alert timestamp and camera name watermark to snapshot
                marked_frame = frame.copy()
                cv2.putText(marked_frame, f"ALERT: {incident_type} [{severity}]", (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
                cv2.putText(marked_frame, f"CAM: {camera_name} | {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}", (20, 75),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.imwrite(str(snapshot_path), marked_frame)
            except Exception as e:
                logger.error(f"Failed to save snapshot: {e}")

        # Store in Database
        db = SessionLocal()
        incident_id = None
        created_at_iso = datetime.datetime.utcnow().isoformat()
        try:
            incident = Incident(
                camera_id=camera_id,
                camera_name=camera_name,
                incident_type=incident_type,
                severity=severity,
                description=description,
                snapshot_path=snapshot_filename,
                timestamp=datetime.datetime.utcnow(),
                is_resolved=False
            )
            db.add(incident)
            db.commit()
            db.refresh(incident)
            incident_id = incident.id
        except Exception as e:
            logger.error(f"Failed to save incident to DB: {e}")
            db.rollback()
        finally:
            db.close()

        # Build payload for WebSocket broadcast
        alert_payload = {
            "type": "INCIDENT_ALERT",
            "data": {
                "id": incident_id,
                "camera_id": camera_id,
                "camera_name": camera_name,
                "incident_type": incident_type,
                "severity": severity,
                "description": description,
                "snapshot_url": f"/snapshots/{snapshot_filename}" if snapshot_filename else "",
                "timestamp": created_at_iso
            }
        }

        # Schedule async broadcast via event loop if running
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.broadcast(alert_payload))
        except Exception:
            pass

        return alert_payload

alert_manager = AlertManager()

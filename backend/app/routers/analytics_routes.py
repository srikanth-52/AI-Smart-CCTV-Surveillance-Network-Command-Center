from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any
import datetime
import random

from backend.app.database import get_db
from backend.app.models import Camera, Incident, NetworkMetric
from backend.app.schemas import SystemOverview, CameraTelemetry
from backend.app.core.stream_manager import stream_manager

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

@router.get("/overview", response_model=SystemOverview)
def get_system_overview(db: Session = Depends(get_db)):
    telemetry_list = stream_manager.get_all_telemetry()
    
    total_cameras = len(telemetry_list)
    online_cameras = sum(1 for t in telemetry_list if t["status"] == "ONLINE")
    total_crowd = sum(t["crowd_count"] for t in telemetry_list)
    total_bandwidth_mbps = sum(t["bitrate_kbps"] for t in telemetry_list) / 1000.0

    active_incidents = db.query(Incident).filter(Incident.is_resolved == False).count()
    critical_alerts = db.query(Incident).filter(
        Incident.is_resolved == False,
        Incident.severity == "CRITICAL"
    ).count()

    health_score = 100.0
    if total_cameras > 0:
        health_score = round((online_cameras / total_cameras) * 100.0, 1)

    return SystemOverview(
        total_cameras=total_cameras,
        online_cameras=online_cameras,
        total_crowd_count=total_crowd,
        active_incidents_count=active_incidents,
        critical_alerts_count=critical_alerts,
        system_health_score=health_score,
        network_bandwidth_total_mbps=round(total_bandwidth_mbps, 2)
    )

@router.get("/telemetry", response_model=List[CameraTelemetry])
def get_all_telemetry():
    return stream_manager.get_all_telemetry()

@router.get("/crowd_trends")
def get_crowd_trends():
    """Generates realistic 24-hour and hourly time-series crowd occupancy data for charts."""
    hours = [f"{h:02d}:00" for h in range(24)]
    
    # Generate bell curve trends for morning/evening peak hours
    base_counts = [
        4, 2, 1, 1, 3, 8, 25, 45, 68, 75, 82, 90, 85, 78, 88, 95, 110, 125, 95, 60, 35, 20, 12, 6
    ]
    
    # Add minor real-time variation
    plaza_trend = [max(0, int(c * 0.5 + random.randint(-3, 3))) for c in base_counts]
    transit_trend = [max(0, int(c * 0.35 + random.randint(-2, 2))) for c in base_counts]
    vault_trend = [max(0, int(c * 0.05 + random.randint(0, 1))) for c in base_counts]

    return {
        "labels": hours,
        "datasets": [
            {
                "label": "Main Plaza Concourse",
                "data": plaza_trend,
                "borderColor": "#00f2fe",
                "backgroundColor": "rgba(0, 242, 254, 0.15)"
            },
            {
                "label": "Transit Hall Turnstiles",
                "data": transit_trend,
                "borderColor": "#4facfe",
                "backgroundColor": "rgba(79, 172, 254, 0.15)"
            },
            {
                "label": "Vault & Server Room",
                "data": vault_trend,
                "borderColor": "#f093fb",
                "backgroundColor": "rgba(240, 147, 251, 0.15)"
            }
        ]
    }

@router.get("/incident_breakdown")
def get_incident_breakdown(db: Session = Depends(get_db)):
    """Returns incident counts grouped by type and severity."""
    by_type = db.query(Incident.incident_type, func.count(Incident.id)).group_by(Incident.incident_type).all()
    by_severity = db.query(Incident.severity, func.count(Incident.id)).group_by(Incident.severity).all()

    # If database is fresh, provide structured distribution data
    type_dict = {t: c for t, c in by_type}
    if not type_dict:
        type_dict = {
            "RESTRICTED_INTRUSION": 4,
            "CROWD_SURGE": 6,
            "LOITERING": 8,
            "ABANDONED_OBJECT": 2,
            "FALL_DETECTED": 3,
            "VIOLENCE_FIGHT": 1,
            "CAMERA_TAMPER": 2
        }

    severity_dict = {s: c for s, c in by_severity}
    if not severity_dict:
        severity_dict = {
            "CRITICAL": 5,
            "HIGH": 8,
            "MEDIUM": 10,
            "LOW": 3
        }

    return {
        "by_type": type_dict,
        "by_severity": severity_dict
    }

@router.get("/network_topology")
def get_network_topology(db: Session = Depends(get_db)):
    """Provides camera node locations and network connectivity graph."""
    cameras = db.query(Camera).all()
    telemetry_map = {t["camera_id"]: t for t in stream_manager.get_all_telemetry()}

    nodes = [
        {"id": "switch-main", "name": "Core Security Switch (10G)", "type": "switch", "status": "ONLINE", "ip": "192.168.1.1"},
        {"id": "nvr-01", "name": "NVR Server Primary", "type": "nvr", "status": "ONLINE", "ip": "192.168.1.10"}
    ]

    links = [
        {"source": "switch-main", "target": "nvr-01"}
    ]

    for cam in cameras:
        t = telemetry_map.get(cam.id, {})
        status = t.get("status", cam.status)
        nodes.append({
            "id": cam.id,
            "name": cam.name,
            "type": "camera",
            "status": status,
            "ip": cam.ip_address,
            "fps": t.get("fps", cam.fps),
            "latency_ms": t.get("latency_ms", 45),
            "bitrate_kbps": t.get("bitrate_kbps", 2048),
            "crowd_count": t.get("crowd_count", 0),
            "lat": cam.latitude,
            "lng": cam.longitude
        })
        links.append({"source": "switch-main", "target": cam.id})

    return {"nodes": nodes, "links": links}

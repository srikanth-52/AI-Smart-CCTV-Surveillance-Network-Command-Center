from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
import datetime

# Zone Schemas
class ZoneBase(BaseModel):
    name: str
    zone_type: str = "RESTRICTED"
    polygon_points: str  # JSON string of coordinates [[x, y], ...]
    alert_on_intrusion: bool = True
    max_occupancy: int = 5
    is_active: bool = True

class ZoneCreate(ZoneBase):
    camera_id: str

class ZoneOut(ZoneBase):
    id: int
    camera_id: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

# Camera Schemas
class CameraBase(BaseModel):
    id: str
    name: str
    location: str = "Main Facility"
    source_type: str = "simulation"
    source_url: str = ""
    ip_address: str = "192.168.1.100"
    latitude: float = 37.7749
    longitude: float = -122.4194
    resolution: str = "1280x720"
    fps: float = 25.0
    status: str = "ONLINE"
    crowd_limit: int = 15
    loitering_limit_sec: float = 10.0
    is_active: bool = True

class CameraCreate(CameraBase):
    pass

class CameraUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    source_type: Optional[str] = None
    source_url: Optional[str] = None
    crowd_limit: Optional[int] = None
    loitering_limit_sec: Optional[float] = None
    is_active: Optional[bool] = None

class CameraOut(CameraBase):
    created_at: datetime.datetime
    zones: List[ZoneOut] = []

    class Config:
        from_attributes = True

# Incident Schemas
class IncidentBase(BaseModel):
    camera_id: str
    camera_name: str
    incident_type: str
    severity: str
    description: str
    snapshot_path: Optional[str] = ""

class IncidentCreate(IncidentBase):
    pass

class IncidentResolve(BaseModel):
    resolved_by: str = "Security Operator"

class IncidentOut(IncidentBase):
    id: int
    timestamp: datetime.datetime
    is_resolved: bool
    resolved_at: Optional[datetime.datetime] = None
    resolved_by: Optional[str] = None

    class Config:
        from_attributes = True

# Metrics & Telemetry Schemas
class NetworkMetricOut(BaseModel):
    id: int
    camera_id: str
    timestamp: datetime.datetime
    fps: float
    bitrate_kbps: float
    latency_ms: float
    packet_loss_pct: float
    blur_score: float
    brightness_score: float
    status: str

    class Config:
        from_attributes = True

# Live Telemetry Snapshot
class CameraTelemetry(BaseModel):
    camera_id: str
    camera_name: str
    status: str
    fps: float
    bitrate_kbps: float
    latency_ms: float
    crowd_count: int
    density_level: str
    threat_level: str
    in_count: int
    out_count: int
    active_incidents: int
    tamper_detected: bool
    tamper_reason: Optional[str] = None

class SystemOverview(BaseModel):
    total_cameras: int
    online_cameras: int
    total_crowd_count: int
    active_incidents_count: int
    critical_alerts_count: int
    system_health_score: float
    network_bandwidth_total_mbps: float

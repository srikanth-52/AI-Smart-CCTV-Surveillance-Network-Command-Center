import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.database import Base

class Camera(Base):
    __tablename__ = "cameras"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    location = Column(String(256), default="Main Facility")
    source_type = Column(String(32), default="simulation")  # simulation, webcam, video_file, rtsp
    source_url = Column(String(512), default="")
    ip_address = Column(String(64), default="192.168.1.100")
    latitude = Column(Float, default=37.7749)
    longitude = Column(Float, default=-122.4194)
    resolution = Column(String(32), default="1280x720")
    fps = Column(Float, default=25.0)
    status = Column(String(32), default="ONLINE")  # ONLINE, DEGRADED, OFFLINE
    crowd_limit = Column(Integer, default=15)
    loitering_limit_sec = Column(Float, default=10.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    incidents = relationship("Incident", back_populates="camera", cascade="all, delete-orphan")
    zones = relationship("Zone", back_populates="camera", cascade="all, delete-orphan")
    metrics = relationship("NetworkMetric", back_populates="camera", cascade="all, delete-orphan")

class Zone(Base):
    __tablename__ = "zones"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    camera_id = Column(String(64), ForeignKey("cameras.id"), nullable=False)
    name = Column(String(128), nullable=False)
    zone_type = Column(String(32), default="RESTRICTED")  # RESTRICTED, CROWD_COUNT, TRIPWIRE
    polygon_points = Column(Text, nullable=False)  # JSON array: [[x1,y1], [x2,y2], ...]
    alert_on_intrusion = Column(Boolean, default=True)
    max_occupancy = Column(Integer, default=5)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    camera = relationship("Camera", back_populates="zones")

class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    camera_id = Column(String(64), ForeignKey("cameras.id"), nullable=False)
    camera_name = Column(String(128), default="")
    incident_type = Column(String(64), nullable=False)  # RESTRICTED_INTRUSION, CROWD_SURGE, etc.
    severity = Column(String(32), default="MEDIUM")      # CRITICAL, HIGH, MEDIUM, LOW, INFO
    description = Column(Text, nullable=False)
    snapshot_path = Column(String(512), default="")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(128), nullable=True)

    camera = relationship("Camera", back_populates="incidents")

class NetworkMetric(Base):
    __tablename__ = "network_metrics"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    camera_id = Column(String(64), ForeignKey("cameras.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    fps = Column(Float, default=25.0)
    bitrate_kbps = Column(Float, default=2048.0)
    latency_ms = Column(Float, default=120.0)
    packet_loss_pct = Column(Float, default=0.0)
    blur_score = Column(Float, default=120.0)
    brightness_score = Column(Float, default=128.0)
    status = Column(String(32), default="ONLINE")

    camera = relationship("Camera", back_populates="metrics")

class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    level = Column(String(16), default="INFO")
    module = Column(String(64), default="SYSTEM")
    message = Column(Text, nullable=False)

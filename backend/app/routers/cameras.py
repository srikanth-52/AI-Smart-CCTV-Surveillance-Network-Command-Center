from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import json
import shutil
import uuid

from backend.app.database import get_db
from backend.app.models import Camera, Zone
from backend.app.schemas import CameraCreate, CameraUpdate, CameraOut, ZoneCreate, ZoneOut, ZoneBase
from backend.app.core.stream_manager import stream_manager
from backend.app.config import SAMPLE_VIDEOS_DIR

router = APIRouter(prefix="/api/cameras", tags=["Cameras"])

def get_mjpeg_stream(camera_id: str, mode: str = "processed"):
    worker = stream_manager.get_worker(camera_id)
    while True:
        if worker:
            frame_bytes = worker.get_jpeg_frame(view_mode=mode)
            if frame_bytes:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        import time
        time.sleep(0.04)

@router.get("", response_model=List[CameraOut])
def get_cameras(db: Session = Depends(get_db)):
    cameras = db.query(Camera).all()
    return cameras

@router.post("", response_model=CameraOut)
def create_camera(cam: CameraCreate, db: Session = Depends(get_db)):
    existing = db.query(Camera).filter(Camera.id == cam.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Camera ID already exists")

    new_cam = Camera(
        id=cam.id,
        name=cam.name,
        location=cam.location,
        source_type=cam.source_type,
        source_url=cam.source_url,
        ip_address=cam.ip_address,
        latitude=cam.latitude,
        longitude=cam.longitude,
        crowd_limit=cam.crowd_limit,
        is_active=cam.is_active
    )
    db.add(new_cam)
    db.commit()
    db.refresh(new_cam)

    if new_cam.is_active:
        stream_manager.add_camera(
            camera_id=new_cam.id,
            name=new_cam.name,
            source_type=new_cam.source_type,
            source_url=new_cam.source_url,
            zones=[]
        )

    return new_cam

@router.get("/{camera_id}", response_model=CameraOut)
def get_camera(camera_id: str, db: Session = Depends(get_db)):
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    return cam

@router.put("/{camera_id}", response_model=CameraOut)
def update_camera(camera_id: str, update_data: CameraUpdate, db: Session = Depends(get_db)):
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    for key, value in update_data.dict(exclude_unset=True).items():
        setattr(cam, key, value)

    db.commit()
    db.refresh(cam)

    # Refresh worker
    if cam.is_active:
        zones = [
            {"name": z.name, "zone_type": z.zone_type, "polygon_points": z.polygon_points, "is_active": z.is_active}
            for z in cam.zones
        ]
        stream_manager.add_camera(
            camera_id=cam.id,
            name=cam.name,
            source_type=cam.source_type,
            source_url=cam.source_url,
            zones=zones
        )
    else:
        stream_manager.remove_camera(cam.id)

    return cam

@router.delete("/{camera_id}")
def delete_camera(camera_id: str, db: Session = Depends(get_db)):
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    stream_manager.remove_camera(camera_id)
    db.delete(cam)
    db.commit()
    return {"status": "success", "message": f"Camera {camera_id} deleted"}

@router.get("/{camera_id}/stream")
def stream_camera(camera_id: str, mode: str = Query("processed", pattern="^(processed|raw|heatmap)$")):
    """Returns real-time MJPEG live stream."""
    return StreamingResponse(
        get_mjpeg_stream(camera_id, mode),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@router.post("/{camera_id}/zones", response_model=ZoneOut)
def add_zone(camera_id: str, zone_data: ZoneBase, db: Session = Depends(get_db)):
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    new_zone = Zone(
        camera_id=camera_id,
        name=zone_data.name,
        zone_type=zone_data.zone_type,
        polygon_points=zone_data.polygon_points,
        alert_on_intrusion=zone_data.alert_on_intrusion,
        max_occupancy=zone_data.max_occupancy,
        is_active=zone_data.is_active
    )
    db.add(new_zone)
    db.commit()
    db.refresh(new_zone)

    # Update worker zones
    worker = stream_manager.get_worker(camera_id)
    if worker:
        all_zones = [
            {"name": z.name, "zone_type": z.zone_type, "polygon_points": z.polygon_points, "is_active": z.is_active}
            for z in cam.zones
        ]
        worker.update_zones(all_zones)

    return new_zone

@router.delete("/{camera_id}/zones/{zone_id}")
def delete_zone(camera_id: str, zone_id: int, db: Session = Depends(get_db)):
    zone = db.query(Zone).filter(Zone.id == zone_id, Zone.camera_id == camera_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    db.delete(zone)
    db.commit()

    # Update worker zones
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    worker = stream_manager.get_worker(camera_id)
    if worker and cam:
        all_zones = [
            {"name": z.name, "zone_type": z.zone_type, "polygon_points": z.polygon_points, "is_active": z.is_active}
            for z in cam.zones
        ]
        worker.update_zones(all_zones)

    return {"status": "success", "message": "Zone deleted"}

@router.post("/upload_video")
async def upload_video(file: UploadFile = File(...)):
    """Uploads a user video file to analyze as a CCTV feed."""
    ext = file.filename.split(".")[-1]
    unique_name = f"cctv_upload_{uuid.uuid4().hex[:8]}.{ext}"
    dest_path = SAMPLE_VIDEOS_DIR / unique_name

    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "filename": unique_name,
        "source_url": str(dest_path),
        "source_type": "video_file"
    }

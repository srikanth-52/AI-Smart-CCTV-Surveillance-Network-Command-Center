from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from typing import List, Optional
import datetime
import csv
import io

from backend.app.database import get_db
from backend.app.models import Incident, Camera
from backend.app.schemas import IncidentOut, IncidentResolve
from backend.app.core.alert_manager import alert_manager

router = APIRouter(prefix="/api/incidents", tags=["Incidents"])

@router.get("", response_model=List[IncidentOut])
def get_incidents(
    camera_id: Optional[str] = None,
    severity: Optional[str] = None,
    incident_type: Optional[str] = None,
    is_resolved: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    query = db.query(Incident)
    if camera_id:
        query = query.filter(Incident.camera_id == camera_id)
    if severity:
        query = query.filter(Incident.severity == severity.upper())
    if incident_type:
        query = query.filter(Incident.incident_type == incident_type)
    if is_resolved is not None:
        query = query.filter(Incident.is_resolved == is_resolved)

    incidents = query.order_by(Incident.timestamp.desc()).offset(offset).limit(limit).all()
    return incidents

@router.put("/{incident_id}/resolve", response_model=IncidentOut)
def resolve_incident(incident_id: int, payload: IncidentResolve, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident.is_resolved = True
    incident.resolved_at = datetime.datetime.utcnow()
    incident.resolved_by = payload.resolved_by

    db.commit()
    db.refresh(incident)
    return incident

@router.post("/simulate")
def simulate_incident(
    camera_id: str = "cam-1",
    incident_type: str = "RESTRICTED_INTRUSION",
    severity: str = "CRITICAL",
    description: str = "Manual security simulation test triggered by operator",
    db: Session = Depends(get_db)
):
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    cam_name = cam.name if cam else "Test Camera"

    alert = alert_manager.trigger_alert(
        camera_id=camera_id,
        camera_name=cam_name,
        incident_type=incident_type,
        severity=severity,
        description=description,
        force=True
    )
    return {"status": "success", "alert": alert}

@router.get("/export/csv")
def export_incidents_csv(db: Session = Depends(get_db)):
    incidents = db.query(Incident).order_by(Incident.timestamp.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Incident ID", "Timestamp (UTC)", "Camera ID", "Camera Name",
        "Incident Type", "Severity", "Description", "Resolved", "Resolved At", "Resolved By"
    ])

    for inc in incidents:
        writer.writerow([
            inc.id,
            inc.timestamp.isoformat() if inc.timestamp else "",
            inc.camera_id,
            inc.camera_name,
            inc.incident_type,
            inc.severity,
            inc.description,
            "YES" if inc.is_resolved else "NO",
            inc.resolved_at.isoformat() if inc.resolved_at else "",
            inc.resolved_by or ""
        ])

    csv_data = output.getvalue()
    filename = f"cctv_incidents_audit_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

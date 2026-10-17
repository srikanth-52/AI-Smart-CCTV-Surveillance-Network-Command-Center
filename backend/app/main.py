from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging

from backend.app.config import SNAPSHOT_DIR, BASE_DIR
from backend.app.database import engine, Base
from backend.app.core.stream_manager import stream_manager
from backend.app.routers.cameras import router as cameras_router
from backend.app.routers.incidents import router as incidents_router
from backend.app.routers.analytics_routes import router as analytics_router
from backend.app.routers.websocket import router as websocket_router

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("cctv_system")

# Initialize Database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI Smart CCTV Surveillance & Network Command System",
    description="Active Real-time Crowd Management, Crime Prevention, and Network Health Monitoring System",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(cameras_router)
app.include_router(incidents_router)
app.include_router(analytics_router)
app.include_router(websocket_router)

# Mount Static Directories
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/snapshots", StaticFiles(directory=str(SNAPSHOT_DIR)), name="snapshots")

# Frontend directory mount
FRONTEND_DIR = BASE_DIR.parent / "frontend"
FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

@app.on_event("startup")
async def on_startup():
    logger.info("Initializing AI CCTV Surveillance System...")
    stream_manager.initialize_default_cameras()
    logger.info("CCTV Video Streams & AI Analytics running.")

@app.on_event("shutdown")
async def on_shutdown():
    logger.info("Shutting down stream workers...")
    stream_manager.shutdown_all()

# Mount Frontend static files
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

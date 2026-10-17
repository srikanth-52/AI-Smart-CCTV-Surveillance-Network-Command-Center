from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import logging
from backend.app.core.alert_manager import alert_manager
from backend.app.core.stream_manager import stream_manager

logger = logging.getLogger("websocket_router")
router = APIRouter(tags=["WebSocket"])

@router.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    await websocket.accept()
    alert_manager.register_websocket(websocket)

    try:
        # Loop to push periodic telemetry updates
        while True:
            # Gather current telemetry across all cameras
            telemetry_data = stream_manager.get_all_telemetry()
            
            # Send periodic snapshot
            await websocket.send_json({
                "type": "TELEMETRY_UPDATE",
                "cameras": telemetry_data,
                "timestamp": asyncio.get_event_loop().time()
            })

            # Wait 1 second before next update or handle incoming message
            try:
                # Receive with timeout
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

    except WebSocketDisconnect:
        alert_manager.unregister_websocket(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        alert_manager.unregister_websocket(websocket)

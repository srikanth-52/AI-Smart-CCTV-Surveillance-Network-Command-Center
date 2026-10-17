/**
 * Video Stream Grid & AI Overlay Controller
 */

class StreamViewer {
  constructor() {
    this.container = document.getElementById("camera-grid-container");
    this.activeModes = {}; // camera_id -> 'processed' | 'heatmap' | 'raw'
  }

  renderCameraGrid(cameras) {
    if (!this.container) return;
    this.container.innerHTML = "";

    cameras.forEach(cam => {
      this.activeModes[cam.id] = "processed";

      const card = document.createElement("div");
      card.className = "camera-card";
      card.id = `cam-card-${cam.id}`;

      card.innerHTML = `
        <div class="camera-header">
          <div class="cam-title-info">
            <div class="status-dot" id="status-dot-${cam.id}"></div>
            <span class="cam-name">${cam.name}</span>
          </div>
          <div class="matrix-controls-group">
            <div class="mode-toggle-group">
              <button class="mode-btn active" data-cam="${cam.id}" data-mode="processed">AI HUD</button>
              <button class="mode-btn" data-cam="${cam.id}" data-mode="heatmap">HEATMAP</button>
              <button class="mode-btn" data-cam="${cam.id}" data-mode="raw">RAW</button>
            </div>
            <button class="btn btn-outline" style="padding: 2px 8px; font-size: 0.7rem;" onclick="streamViewer.toggleFocus('${cam.id}')">⛶</button>
          </div>
        </div>

        <div class="video-container">
          <img 
            id="stream-img-${cam.id}" 
            class="video-stream-img" 
            src="/api/cameras/${cam.id}/stream?mode=processed" 
            alt="Live Stream ${cam.name}"
            onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'100%\\' height=\\'100%\\' viewBox=\\'0 0 400 225\\'><rect width=\\'100%\\' height=\\'100%\\' fill=\\'%23080c14\\'/><text x=\\'50%\\' y=\\'50%\\' fill=\\'%23ff1744\\' font-family=\\'sans-serif\\' font-size=\\'14\\' text-anchor=\\'middle\\' dominant-baseline=\\'middle\\'>CAMERA FEED OFFLINE</text></svg>'"
          />
        </div>

        <div class="camera-footer">
          <div class="cam-quick-telemetry">
            <span id="tel-crowd-${cam.id}">👥 0 PAX</span>
            <span id="tel-fps-${cam.id}">⚡ 25.0 FPS</span>
            <span id="tel-flow-${cam.id}">⇄ IN: 0 | OUT: 0</span>
          </div>
          <span class="cam-badge badge-safe" id="tel-badge-${cam.id}">SAFE</span>
        </div>
      `;

      this.container.appendChild(card);
    });

    // Attach mode toggle listeners
    this.container.querySelectorAll(".mode-btn").forEach(btn => {
      btn.addEventListener("click", (e) => {
        const camId = btn.dataset.cam;
        const mode = btn.dataset.mode;
        this.switchCameraMode(camId, mode, btn);
      });
    });
  }

  switchCameraMode(camId, mode, clickedBtn) {
    this.activeModes[camId] = mode;
    const card = document.getElementById(`cam-card-${camId}`);
    if (card) {
      card.querySelectorAll(".mode-btn").forEach(b => b.classList.remove("active"));
      if (clickedBtn) clickedBtn.classList.add("active");
    }

    const img = document.getElementById(`stream-img-${camId}`);
    if (img) {
      img.src = `/api/cameras/${camId}/stream?mode=${mode}&t=${Date.now()}`;
    }
  }

  updateCameraCardTelemetry(telemetry) {
    const camId = telemetry.camera_id;
    
    // Status dot
    const dot = document.getElementById(`status-dot-${camId}`);
    if (dot) {
      dot.className = `status-dot ${telemetry.status.toLowerCase()}`;
    }

    // Telemetry text
    const elCrowd = document.getElementById(`tel-crowd-${camId}`);
    const elFps = document.getElementById(`tel-fps-${camId}`);
    const elFlow = document.getElementById(`tel-flow-${camId}`);
    const elBadge = document.getElementById(`tel-badge-${camId}`);

    if (elCrowd) elCrowd.textContent = `👥 ${telemetry.crowd_count} PAX (${telemetry.density_level})`;
    if (elFps) elFps.textContent = `⚡ ${telemetry.fps} FPS`;
    if (elFlow) elFlow.textContent = `⇄ IN: ${telemetry.in_count} | OUT: ${telemetry.out_count}`;

    if (elBadge) {
      const threat = telemetry.threat_level || "SAFE";
      elBadge.textContent = threat;
      elBadge.className = `cam-badge badge-${threat.toLowerCase()}`;
    }
  }

  flashCameraAlert(camId) {
    const card = document.getElementById(`cam-card-${camId}`);
    if (card) {
      card.classList.add("alerting");
      setTimeout(() => card.classList.remove("alerting"), 5000);
    }
  }

  toggleFocus(camId) {
    const grid = document.getElementById("camera-grid-container");
    const isSingle = grid.classList.contains("grid-1x1");
    if (isSingle) {
      // Restore previous layout
      grid.className = `camera-grid grid-${window.app.gridMode}`;
      document.querySelectorAll(".camera-card").forEach(c => c.style.display = "flex");
    } else {
      // Focus single camera
      grid.className = "camera-grid grid-1x1";
      document.querySelectorAll(".camera-card").forEach(c => {
        c.style.display = (c.id === `cam-card-${camId}`) ? "flex" : "none";
      });
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  window.streamViewer = new StreamViewer();
});

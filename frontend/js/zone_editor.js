/**
 * Interactive Polygon Zone & Security Rules Configurator
 */

class ZoneEditor {
  constructor() {
    this.canvas = document.getElementById("zone-canvas");
    this.ctx = this.canvas ? this.canvas.getContext("2d") : null;
    this.selectedCameraId = "cam-1";
    this.currentPoints = [];
    this.cameras = [];
    this.isDrawing = false;

    this.init();
  }

  init() {
    if (!this.canvas) return;

    // Canvas click event for polygon vertices
    this.canvas.addEventListener("click", (e) => this.handleCanvasClick(e));

    // Camera select change
    const camSelect = document.getElementById("zone-camera-select");
    if (camSelect) {
      camSelect.addEventListener("change", (e) => {
        this.selectedCameraId = e.target.value;
        this.currentPoints = [];
        this.redrawCanvas();
        this.loadZones();
      });
    }

    // Reset points button
    const clearBtn = document.getElementById("btn-clear-zone-points");
    if (clearBtn) {
      clearBtn.addEventListener("click", () => {
        this.currentPoints = [];
        this.redrawCanvas();
      });
    }

    // Save zone button
    const saveBtn = document.getElementById("btn-save-zone");
    if (saveBtn) {
      saveBtn.addEventListener("click", () => this.saveZone());
    }
  }

  async loadZones() {
    const camSelect = document.getElementById("zone-camera-select");
    try {
      const res = await fetch("/api/cameras");
      if (res.ok) {
        this.cameras = await res.json();
        
        // Populate select if empty
        if (camSelect && camSelect.children.length === 0) {
          this.cameras.forEach(c => {
            const opt = document.createElement("option");
            opt.value = c.id;
            opt.textContent = `${c.name} (${c.location})`;
            camSelect.appendChild(opt);
          });
          if (this.cameras.length > 0) {
            this.selectedCameraId = this.cameras[0].id;
          }
        }

        this.renderExistingZonesTable();
        this.redrawCanvas();
      }
    } catch (e) {
      console.error("Error loading zones:", e);
    }
  }

  handleCanvasClick(e) {
    const rect = this.canvas.getBoundingClientRect();
    const scaleX = this.canvas.width / rect.width;
    const scaleY = this.canvas.height / rect.height;

    const x = Math.round((e.clientX - rect.left) * scaleX);
    const y = Math.round((e.clientY - rect.top) * scaleY);

    this.currentPoints.push([x, y]);
    this.redrawCanvas();
  }

  redrawCanvas() {
    if (!this.ctx) return;
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;

    ctx.clearRect(0, 0, w, h);

    // Draw dark grid background
    ctx.fillStyle = "#0c1322";
    ctx.fillRect(0, 0, w, h);

    ctx.strokeStyle = "rgba(0, 242, 254, 0.08)";
    ctx.lineWidth = 1;
    for (let x = 0; x < w; x += 40) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
    for (let y = 0; y < h; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    // Draw existing zones for this camera
    const activeCam = this.cameras.find(c => c.id === this.selectedCameraId);
    if (activeCam && activeCam.zones) {
      activeCam.zones.forEach(z => {
        try {
          const pts = JSON.parse(z.polygon_points);
          if (pts.length > 2) {
            ctx.beginPath();
            ctx.moveTo(pts[0][0], pts[0][1]);
            for (let i = 1; i < pts.length; i++) {
              ctx.lineTo(pts[i][0], pts[i][1]);
            }
            ctx.closePath();
            ctx.fillStyle = z.zone_type === "RESTRICTED" ? "rgba(255, 23, 68, 0.2)" : "rgba(0, 242, 254, 0.2)";
            ctx.fill();
            ctx.strokeStyle = z.zone_type === "RESTRICTED" ? "#ff1744" : "#00f2fe";
            ctx.lineWidth = 2;
            ctx.stroke();

            // Label
            ctx.fillStyle = "#fff";
            ctx.font = "12px sans-serif";
            ctx.fillText(z.name, pts[0][0] + 6, pts[0][1] + 16);
          }
        } catch (e) {}
      });
    }

    // Draw in-progress polygon
    if (this.currentPoints.length > 0) {
      ctx.beginPath();
      ctx.moveTo(this.currentPoints[0][0], this.currentPoints[0][1]);
      for (let i = 1; i < this.currentPoints.length; i++) {
        ctx.lineTo(this.currentPoints[i][0], this.currentPoints[i][1]);
      }
      ctx.strokeStyle = "#ffd600";
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 4]);
      ctx.stroke();
      ctx.setLineDash([]);

      // Draw point handles
      this.currentPoints.forEach((p, idx) => {
        ctx.beginPath();
        ctx.arc(p[0], p[1], 5, 0, Math.PI * 2);
        ctx.fillStyle = "#ffd600";
        ctx.fill();
        ctx.strokeStyle = "#000";
        ctx.stroke();
      });
    }
  }

  renderExistingZonesTable() {
    const listEl = document.getElementById("zones-summary-list");
    if (!listEl) return;

    const activeCam = this.cameras.find(c => c.id === this.selectedCameraId);
    if (!activeCam || !activeCam.zones || activeCam.zones.length === 0) {
      listEl.innerHTML = `<div style="color: var(--text-secondary); font-size: 0.82rem; padding: 12px 0;">No security zones defined for this camera yet. Click on the canvas above to draw a polygon.</div>`;
      return;
    }

    listEl.innerHTML = "";
    activeCam.zones.forEach(z => {
      const item = document.createElement("div");
      item.className = "health-stat-row";
      item.style.alignItems = "center";
      item.innerHTML = `
        <div>
          <span style="font-weight: bold; color: #fff;">${z.name}</span>
          <span class="cam-badge ${z.zone_type === 'RESTRICTED' ? 'badge-critical' : 'badge-safe'}" style="margin-left: 6px;">${z.zone_type}</span>
        </div>
        <button class="btn btn-danger" style="padding: 2px 8px; font-size: 0.7rem;" onclick="zoneEditor.deleteZone(${z.id})">Delete</button>
      `;
      listEl.appendChild(item);
    });
  }

  async saveZone() {
    if (this.currentPoints.length < 3) {
      alert("Please click at least 3 points on the preview canvas to define a closed zone polygon.");
      return;
    }

    const name = document.getElementById("input-zone-name").value || "Secured Zone";
    const type = document.getElementById("select-zone-type").value;

    try {
      const res = await fetch(`/api/cameras/${this.selectedCameraId}/zones`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name,
          zone_type: type,
          polygon_points: JSON.stringify(this.currentPoints),
          alert_on_intrusion: true,
          is_active: true
        })
      });

      if (res.ok) {
        this.currentPoints = [];
        await this.loadZones();
        if (window.app) window.app.fetchInitialData();
      } else {
        alert("Failed to save zone.");
      }
    } catch (e) {
      console.error("Error saving zone:", e);
    }
  }

  async deleteZone(zoneId) {
    if (!confirm("Are you sure you want to delete this security zone?")) return;

    try {
      const res = await fetch(`/api/cameras/${this.selectedCameraId}/zones/${zoneId}`, {
        method: "DELETE"
      });
      if (res.ok) {
        await this.loadZones();
        if (window.app) window.app.fetchInitialData();
      }
    } catch (e) {
      console.error("Error deleting zone:", e);
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  window.zoneEditor = new ZoneEditor();
});

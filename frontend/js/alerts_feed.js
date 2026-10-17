/**
 * Live Incident Alerts & Incident Log Manager
 */

class AlertsFeed {
  constructor() {
    this.container = document.getElementById("incidents-feed-list");
    this.filterSeverity = "ALL";
    this.filterResolved = "ALL";
    this.incidents = [];

    this.initListeners();
  }

  initListeners() {
    // Filter by severity
    const sevSelect = document.getElementById("filter-incident-severity");
    if (sevSelect) {
      sevSelect.addEventListener("change", (e) => {
        this.filterSeverity = e.target.value;
        this.renderIncidents();
      });
    }

    // Filter by status
    const statusSelect = document.getElementById("filter-incident-status");
    if (statusSelect) {
      statusSelect.addEventListener("change", (e) => {
        this.filterResolved = e.target.value;
        this.renderIncidents();
      });
    }

    // Export CSV
    const exportBtn = document.getElementById("btn-export-csv");
    if (exportBtn) {
      exportBtn.addEventListener("click", () => {
        window.open("/api/incidents/export/csv", "_blank");
      });
    }
  }

  async fetchIncidents() {
    try {
      const res = await fetch("/api/incidents?limit=50");
      if (res.ok) {
        this.incidents = await res.json();
        this.renderIncidents();
      }
    } catch (e) {
      console.error("Error fetching incidents:", e);
    }
  }

  prependIncident(incident) {
    this.incidents.unshift(incident);
    this.renderIncidents();
  }

  renderIncidents() {
    if (!this.container) return;

    const filtered = this.incidents.filter(inc => {
      if (this.filterSeverity !== "ALL" && inc.severity !== this.filterSeverity) return false;
      if (this.filterResolved === "UNRESOLVED" && inc.is_resolved) return false;
      if (this.filterResolved === "RESOLVED" && !inc.is_resolved) return false;
      return true;
    });

    if (filtered.length === 0) {
      this.container.innerHTML = `
        <div style="text-align: center; padding: 40px; color: var(--text-secondary);">
          <div style="font-size: 2rem; margin-bottom: 8px;">🛡️</div>
          <div>No incidents matching the selected criteria. System operational.</div>
        </div>
      `;
      return;
    }

    this.container.innerHTML = "";

    filtered.forEach(inc => {
      const card = document.createElement("div");
      card.className = `incident-card ${inc.severity.toLowerCase()} ${inc.is_resolved ? 'resolved' : ''}`;
      
      const timeStr = inc.timestamp ? new Date(inc.timestamp).toLocaleTimeString() : 'Just now';
      const typeLabel = inc.incident_type.replace(/_/g, ' ');

      const snapUrl = inc.snapshot_path ? `/snapshots/${inc.snapshot_path}` : (inc.snapshot_url || "");

      card.innerHTML = `
        <div class="inc-main-info">
          ${snapUrl ? `
            <div class="inc-thumb-wrap" onclick="alertsFeed.openLightbox('${snapUrl}', '${typeLabel}', '${inc.camera_name}')">
              <img src="${snapUrl}" alt="Evidence" onerror="this.parentElement.style.display='none'"/>
            </div>
          ` : ''}
          <div class="inc-details">
            <div class="inc-title">
              <span>${typeLabel}</span>
              <span class="cam-badge badge-${inc.severity.toLowerCase()}">${inc.severity}</span>
            </div>
            <div class="inc-desc">${inc.description}</div>
            <div class="inc-meta">
              <span>📹 ${inc.camera_name || inc.camera_id}</span>
              <span>⏱️ ${timeStr}</span>
              ${inc.is_resolved ? `<span>✅ Resolved (${inc.resolved_by || 'Operator'})</span>` : ''}
            </div>
          </div>
        </div>

        <div class="inc-actions">
          ${!inc.is_resolved ? `
            <button class="btn btn-outline" style="font-size: 0.72rem;" onclick="alertsFeed.resolveIncident(${inc.id})">
              ✓ Acknowledge
            </button>
          ` : ''}
        </div>
      `;

      this.container.appendChild(card);
    });
  }

  async resolveIncident(incidentId) {
    try {
      const res = await fetch(`/api/incidents/${incidentId}/resolve`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resolved_by: "Command Operator" })
      });

      if (res.ok) {
        const updated = await res.json();
        const idx = this.incidents.findIndex(i => i.id === incidentId);
        if (idx !== -1) {
          this.incidents[idx] = updated;
        }
        this.renderIncidents();
        if (window.app) window.app.refreshData();
      }
    } catch (e) {
      console.error("Error resolving incident:", e);
    }
  }

  openLightbox(imgUrl, title, cameraName) {
    const modal = document.getElementById("modal-lightbox");
    const imgEl = document.getElementById("lightbox-img");
    const titleEl = document.getElementById("lightbox-title");
    const metaEl = document.getElementById("lightbox-meta");

    if (modal && imgEl) {
      imgEl.src = imgUrl;
      if (titleEl) titleEl.textContent = title;
      if (metaEl) metaEl.textContent = `Security Camera: ${cameraName}`;
      modal.classList.add("open");
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  window.alertsFeed = new AlertsFeed();
});

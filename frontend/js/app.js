/**
 * AI Smart CCTV Surveillance & Command Center
 * Main Application Orchestrator & State Management
 */

class CCTVCommandCenter {
  constructor() {
    this.activeTab = "matrix";
    this.cameras = [];
    this.telemetry = {};
    this.incidents = [];
    this.soundEnabled = true;
    this.ws = null;
    this.audioCtx = null;
    this.gridMode = "2x2";

    this.initAudio();
    this.initUI();
    this.connectWebSocket();
    this.fetchInitialData();

    // Auto-refresh fallback every 3s
    setInterval(() => this.refreshData(), 3000);
  }

  initAudio() {
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      this.audioCtx = new AudioContext();
    } catch (e) {
      console.warn("Web Audio API not supported", e);
    }
  }

  playAlertSound(severity = "CRITICAL") {
    if (!this.soundEnabled || !this.audioCtx) return;
    try {
      if (this.audioCtx.state === "suspended") {
        this.audioCtx.resume();
      }

      const now = this.audioCtx.currentTime;
      const osc = this.audioCtx.createOscillator();
      const gain = this.audioCtx.createGain();

      osc.connect(gain);
      gain.connect(this.audioCtx.destination);

      if (severity === "CRITICAL") {
        // High-pitched two-tone siren
        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(880, now);
        osc.frequency.linearRampToValueAtTime(1200, now + 0.15);
        osc.frequency.linearRampToValueAtTime(880, now + 0.3);
        osc.frequency.linearRampToValueAtTime(1200, now + 0.45);
        
        gain.gain.setValueAtTime(0.15, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.6);

        osc.start(now);
        osc.stop(now + 0.6);
      } else if (severity === "HIGH") {
        // Warning chime
        osc.type = "sine";
        osc.frequency.setValueAtTime(587.33, now); // D5
        osc.frequency.setValueAtTime(880, now + 0.1); // A5
        
        gain.gain.setValueAtTime(0.12, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);

        osc.start(now);
        osc.stop(now + 0.35);
      } else {
        // Low info blip
        osc.type = "triangle";
        osc.frequency.setValueAtTime(440, now);
        gain.gain.setValueAtTime(0.08, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.2);

        osc.start(now);
        osc.stop(now + 0.2);
      }
    } catch (e) {
      console.error("Error playing audio alert:", e);
    }
  }

  initUI() {
    // Tab buttons
    document.querySelectorAll(".tab-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const tab = btn.dataset.tab;
        this.switchTab(tab);
      });
    });

    // Sound toggle
    const soundBtn = document.getElementById("btn-toggle-sound");
    if (soundBtn) {
      soundBtn.addEventListener("click", () => {
        this.soundEnabled = !this.soundEnabled;
        soundBtn.innerHTML = this.soundEnabled ? "🔊 Sound: ON" : "🔇 Sound: OFF";
        soundBtn.classList.toggle("btn-outline", !this.soundEnabled);
        soundBtn.classList.toggle("btn-primary", this.soundEnabled);
      });
    }

    // Grid layout switcher
    document.querySelectorAll(".btn-grid-layout").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".btn-grid-layout").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        this.gridMode = btn.dataset.layout;
        const grid = document.getElementById("camera-grid-container");
        if (grid) {
          grid.className = `camera-grid grid-${this.gridMode}`;
        }
      });
    });

    // Manual Simulate Alert Button
    const simBtn = document.getElementById("btn-simulate-alert");
    if (simBtn) {
      simBtn.addEventListener("click", () => this.simulateAlert());
    }

    // Add Camera Modal
    const addCamBtn = document.getElementById("btn-add-camera-modal");
    if (addCamBtn) {
      addCamBtn.addEventListener("click", () => {
        document.getElementById("modal-add-camera").classList.add("open");
      });
    }

    // Close Modals
    document.querySelectorAll(".modal-close-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".modal-backdrop").forEach(m => m.classList.remove("open"));
      });
    });

    // Form submit add camera
    const addCamForm = document.getElementById("form-add-camera");
    if (addCamForm) {
      addCamForm.addEventListener("submit", (e) => this.handleAddCameraSubmit(e));
    }
  }

  switchTab(tabName) {
    this.activeTab = tabName;
    document.querySelectorAll(".tab-btn").forEach(b => {
      b.classList.toggle("active", b.dataset.tab === tabName);
    });
    document.querySelectorAll(".tab-content").forEach(c => {
      c.classList.toggle("active", c.id === `tab-${tabName}`);
    });

    // Trigger tab specific refreshes
    if (tabName === "map" && window.mapViewer) {
      setTimeout(() => window.mapViewer.invalidateSize(), 150);
    } else if (tabName === "analytics" && window.analyticsCharts) {
      window.analyticsCharts.renderCharts();
    } else if (tabName === "zones" && window.zoneEditor) {
      window.zoneEditor.loadZones();
    }
  }

  connectWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/telemetry`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log("Telemetry WebSocket connected.");
        const wsDot = document.getElementById("ws-connection-dot");
        if (wsDot) wsDot.className = "status-dot";
      };

      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "TELEMETRY_UPDATE") {
            this.handleTelemetryUpdate(msg.cameras);
          } else if (msg.type === "INCIDENT_ALERT") {
            this.handleNewIncident(msg.data);
          }
        } catch (e) {
          console.error("Error parsing WS msg:", e);
        }
      };

      this.ws.onclose = () => {
        console.warn("WebSocket disconnected. Reconnecting in 3s...");
        const wsDot = document.getElementById("ws-connection-dot");
        if (wsDot) wsDot.className = "status-dot offline";
        setTimeout(() => this.connectWebSocket(), 3000);
      };

      this.ws.onerror = (err) => {
        console.error("WebSocket error:", err);
      };
    } catch (e) {
      console.warn("WebSocket init error:", e);
    }
  }

  async fetchInitialData() {
    try {
      // 1. Fetch Cameras
      const camRes = await fetch("/api/cameras");
      if (camRes.ok) {
        this.cameras = await camRes.json();
        if (window.streamViewer) {
          window.streamViewer.renderCameraGrid(this.cameras);
        }
      }

      // 2. Fetch System Overview
      this.refreshData();

      // 3. Fetch Incidents
      if (window.alertsFeed) {
        window.alertsFeed.fetchIncidents();
      }
    } catch (e) {
      console.error("Error in fetchInitialData:", e);
    }
  }

  async refreshData() {
    try {
      const res = await fetch("/api/analytics/overview");
      if (res.ok) {
        const data = await res.json();
        this.updateKPIs(data);
      }
    } catch (e) {}
  }

  updateKPIs(data) {
    const elActiveCams = document.getElementById("kpi-active-cams");
    const elTotalCrowd = document.getElementById("kpi-total-crowd");
    const elThreatLevel = document.getElementById("kpi-threat-level");
    const elBandwidth = document.getElementById("kpi-bandwidth");
    const elAlertCount = document.getElementById("kpi-unresolved-alerts");
    const tabAlertBadge = document.getElementById("tab-alert-badge");

    if (elActiveCams) elActiveCams.textContent = `${data.online_cameras}/${data.total_cameras}`;
    if (elTotalCrowd) elTotalCrowd.textContent = `${data.total_crowd_count} PAX`;
    
    // Overall Threat Level
    let threatText = "SAFE";
    let threatColor = "var(--accent-green)";
    if (data.critical_alerts_count > 0) {
      threatText = "CRITICAL";
      threatColor = "var(--accent-red)";
    } else if (data.active_incidents_count > 2) {
      threatText = "ELEVATED";
      threatColor = "var(--accent-orange)";
    } else if (data.active_incidents_count > 0) {
      threatText = "GUARDED";
      threatColor = "var(--accent-yellow)";
    }

    if (elThreatLevel) {
      elThreatLevel.textContent = threatText;
      elThreatLevel.style.color = threatColor;
    }

    if (elBandwidth) elBandwidth.textContent = `${data.network_bandwidth_total_mbps} Mbps`;
    if (elAlertCount) elAlertCount.textContent = `${data.active_incidents_count}`;
    if (tabAlertBadge) {
      tabAlertBadge.textContent = `${data.active_incidents_count}`;
      tabAlertBadge.style.display = data.active_incidents_count > 0 ? "inline-block" : "none";
    }

    // Strobe Banner
    const strobe = document.getElementById("strobe-alert-bar");
    if (strobe) {
      strobe.style.display = data.critical_alerts_count > 0 ? "flex" : "none";
      const strobeMsg = document.getElementById("strobe-alert-msg");
      if (strobeMsg && data.critical_alerts_count > 0) {
        strobeMsg.textContent = `🚨 CRITICAL SECURITY THREAT DETECTED (${data.critical_alerts_count} ACTIVE CRITICAL INCIDENTS)`;
      }
    }
  }

  handleTelemetryUpdate(telemetryList) {
    if (!telemetryList) return;
    telemetryList.forEach(t => {
      this.telemetry[t.camera_id] = t;
      if (window.streamViewer) {
        window.streamViewer.updateCameraCardTelemetry(t);
      }
    });

    if (window.mapViewer) {
      window.mapViewer.updateTelemetry(this.telemetry);
    }
  }

  handleNewIncident(incident) {
    console.log("New incident received:", incident);
    this.playAlertSound(incident.severity);

    if (window.alertsFeed) {
      window.alertsFeed.prependIncident(incident);
    }

    // Highlight card
    if (window.streamViewer) {
      window.streamViewer.flashCameraAlert(incident.camera_id);
    }
  }

  async simulateAlert() {
    try {
      const types = ["RESTRICTED_INTRUSION", "CROWD_SURGE", "LOITERING", "FALL_DETECTED", "VIOLENCE_FIGHT", "CAMERA_TAMPER"];
      const severities = ["CRITICAL", "HIGH", "MEDIUM"];
      const randomType = types[Math.floor(Math.random() * types.length)];
      const randomSev = severities[Math.floor(Math.random() * severities.length)];
      const randomCam = this.cameras.length > 0 ? this.cameras[Math.floor(Math.random() * this.cameras.length)].id : "cam-1";

      const res = await fetch("/api/incidents/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          camera_id: randomCam,
          incident_type: randomType,
          severity: randomSev,
          description: `Simulated anomaly: ${randomType.replace(/_/g, ' ')} detected in surveillance sector`
        })
      });
      if (res.ok) {
        console.log("Simulated alert successfully triggered.");
      }
    } catch (e) {
      console.error("Failed to simulate alert:", e);
    }
  }

  async handleAddCameraSubmit(e) {
    e.preventDefault();
    const id = document.getElementById("input-cam-id").value;
    const name = document.getElementById("input-cam-name").value;
    const location = document.getElementById("input-cam-loc").value;
    const sourceType = document.getElementById("input-cam-source-type").value;
    const sourceUrl = document.getElementById("input-cam-source-url").value;
    const crowdLimit = parseInt(document.getElementById("input-cam-limit").value) || 15;

    try {
      const res = await fetch("/api/cameras", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id,
          name,
          location,
          source_type: sourceType,
          source_url: sourceUrl,
          crowd_limit: crowdLimit,
          is_active: true
        })
      });

      if (res.ok) {
        document.querySelectorAll(".modal-backdrop").forEach(m => m.classList.remove("open"));
        await this.fetchInitialData();
      } else {
        const err = await res.json();
        alert(`Error adding camera: ${err.detail || 'Failed'}`);
      }
    } catch (err) {
      console.error("Error creating camera:", err);
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  window.app = new CCTVCommandCenter();
});

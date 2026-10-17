/**
 * Interactive GIS & Facility Radar Map
 */

class FacilityMapViewer {
  constructor() {
    this.map = null;
    this.markers = {};
    this.fovCones = {};
    this.hotspotCircles = {};
    this.initMap();
  }

  initMap() {
    const mapEl = document.getElementById("leaflet-map");
    if (!mapEl || typeof L === "undefined") return;

    // Center coordinates for facility (default campus/metro hub)
    const center = [37.7749, -122.4194];

    this.map = L.map('leaflet-map', {
      center: center,
      zoom: 18,
      zoomControl: true,
      attributionControl: false
    });

    // High-tech dark CartoDB tiles
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      maxZoom: 20,
      subdomains: 'abcd'
    }).addTo(this.map);

    // Facility polygon boundaries
    const facilityBounds = [
      [37.7760, -122.4210],
      [37.7762, -122.4180],
      [37.7740, -122.4178],
      [37.7738, -122.4208]
    ];

    L.polygon(facilityBounds, {
      color: '#00f2fe',
      weight: 1.5,
      dashArray: '4, 8',
      fillColor: '#00f2fe',
      fillOpacity: 0.05
    }).addTo(this.map);

    this.loadCameraMarkers();
  }

  async loadCameraMarkers() {
    try {
      const res = await fetch("/api/cameras");
      if (!res.ok) return;
      const cameras = await res.json();

      cameras.forEach(cam => {
        const lat = cam.latitude || 37.7749;
        const lng = cam.longitude || -122.4194;

        // Custom High-tech Camera Icon
        const camIcon = L.divIcon({
          className: 'custom-cam-pin',
          html: `
            <div style="position: relative; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">
              <div id="radar-ring-${cam.id}" style="position: absolute; width: 100%; height: 100%; border-radius: 50%; background: rgba(0, 242, 254, 0.2); border: 1px solid #00f2fe; animation: radarPing 2s infinite ease-out;"></div>
              <div style="width: 18px; height: 18px; border-radius: 50%; background: #101726; border: 2px solid #00f2fe; display: flex; align-items: center; justify-content: center; color: #00f2fe; font-size: 10px; font-weight: bold; z-index: 2;">📹</div>
            </div>
          `,
          iconSize: [32, 32],
          iconAnchor: [16, 16]
        });

        const marker = L.marker([lat, lng], { icon: camIcon }).addTo(this.map);
        
        // Popup
        marker.bindPopup(`
          <div style="color: #fff; font-family: sans-serif; min-width: 180px;">
            <div style="font-weight: bold; font-size: 12px; color: #00f2fe; margin-bottom: 4px;">${cam.name}</div>
            <div style="font-size: 11px; color: #aaa; margin-bottom: 8px;">${cam.location}</div>
            <div style="border-radius: 4px; overflow: hidden; margin-bottom: 8px;">
              <img src="/api/cameras/${cam.id}/stream?mode=processed" style="width: 100%; height: 90px; object-fit: cover;" />
            </div>
            <div style="font-size: 10px; font-family: monospace; display: flex; justify-content: space-between;">
              <span id="popup-crowd-${cam.id}">PAX: --</span>
              <span id="popup-status-${cam.id}" style="color: #00e676;">ONLINE</span>
            </div>
          </div>
        `);

        this.markers[cam.id] = marker;

        // Dynamic Crowd Hotspot Circle
        const circle = L.circle([lat, lng], {
          radius: 15,
          color: '#00e676',
          fillColor: '#00e676',
          fillOpacity: 0.25,
          weight: 1
        }).addTo(this.map);

        this.hotspotCircles[cam.id] = circle;
      });
    } catch (e) {
      console.error("Error loading map markers:", e);
    }
  }

  updateTelemetry(telemetryMap) {
    if (!this.map) return;

    Object.values(telemetryMap).forEach(t => {
      const circle = this.hotspotCircles[t.camera_id];
      const radarRing = document.getElementById(`radar-ring-${t.camera_id}`);

      if (circle) {
        let color = '#00e676';
        let radius = 12 + t.crowd_count * 1.5;

        if (t.density_level === 'CRITICAL_SURGE' || t.threat_level === 'CRITICAL') {
          color = '#ff1744';
          radius = 35;
        } else if (t.density_level === 'HIGH' || t.threat_level === 'ELEVATED') {
          color = '#ff9100';
          radius = 26;
        } else if (t.density_level === 'MODERATE' || t.threat_level === 'GUARDED') {
          color = '#ffd600';
          radius = 20;
        }

        circle.setStyle({ color: color, fillColor: color });
        circle.setRadius(radius);
      }

      if (radarRing) {
        if (t.threat_level === 'CRITICAL') {
          radarRing.style.borderColor = '#ff1744';
          radarRing.style.background = 'rgba(255, 23, 68, 0.4)';
        } else {
          radarRing.style.borderColor = '#00f2fe';
          radarRing.style.background = 'rgba(0, 242, 254, 0.2)';
        }
      }

      // Update popup if open
      const popupCrowd = document.getElementById(`popup-crowd-${t.camera_id}`);
      if (popupCrowd) popupCrowd.textContent = `PAX: ${t.crowd_count}`;
    });
  }

  invalidateSize() {
    if (this.map) {
      this.map.invalidateSize();
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  window.mapViewer = new FacilityMapViewer();
});

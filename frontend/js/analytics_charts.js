/**
 * Security Intelligence & Crowd Analytics Charts (Chart.js)
 */

class AnalyticsCharts {
  constructor() {
    this.crowdChart = null;
    this.incidentTypeChart = null;
    this.severityChart = null;
    this.networkChart = null;
  }

  async renderCharts() {
    if (typeof Chart === "undefined") return;

    // Dark theme Chart.js defaults
    Chart.defaults.color = "#8b949e";
    Chart.defaults.font.family = "'Inter', sans-serif";
    Chart.defaults.borderColor = "rgba(255, 255, 255, 0.06)";

    await this.renderCrowdTrendsChart();
    await this.renderIncidentBreakdownChart();
    this.renderNetworkMetricsChart();
  }

  async renderCrowdTrendsChart() {
    const canvas = document.getElementById("chart-crowd-trends");
    if (!canvas) return;

    try {
      const res = await fetch("/api/analytics/crowd_trends");
      if (!res.ok) return;
      const data = await res.json();

      if (this.crowdChart) this.crowdChart.destroy();

      this.crowdChart = new Chart(canvas, {
        type: 'line',
        data: {
          labels: data.labels,
          datasets: data.datasets.map(ds => ({
            ...ds,
            tension: 0.35,
            fill: true,
            borderWidth: 2,
            pointRadius: 2,
            pointHoverRadius: 5
          }))
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'top', labels: { boxWidth: 12 } }
          },
          scales: {
            y: {
              beginAtZero: true,
              title: { display: true, text: 'Occupancy (Persons)' }
            },
            x: {
              grid: { display: false }
            }
          }
        }
      });
    } catch (e) {
      console.error("Error rendering crowd trends:", e);
    }
  }

  async renderIncidentBreakdownChart() {
    const typeCanvas = document.getElementById("chart-incident-types");
    const sevCanvas = document.getElementById("chart-incident-severity");

    try {
      const res = await fetch("/api/analytics/incident_breakdown");
      if (!res.ok) return;
      const data = await res.json();

      // 1. Doughnut Chart by Incident Type
      if (typeCanvas) {
        if (this.incidentTypeChart) this.incidentTypeChart.destroy();

        const typeLabels = Object.keys(data.by_type).map(k => k.replace(/_/g, ' '));
        const typeValues = Object.values(data.by_type);

        this.incidentTypeChart = new Chart(typeCanvas, {
          type: 'doughnut',
          data: {
            labels: typeLabels,
            datasets: [{
              data: typeValues,
              backgroundColor: [
                '#ff1744', '#ff9100', '#ffd600', '#00f2fe', '#b388ff', '#00e676', '#4facfe'
              ],
              borderWidth: 2,
              borderColor: '#101726'
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { position: 'right', labels: { boxWidth: 10, font: { size: 10 } } }
            },
            cutout: '68%'
          }
        });
      }

      // 2. Bar Chart by Severity
      if (sevCanvas) {
        if (this.severityChart) this.severityChart.destroy();

        const sevLabels = Object.keys(data.by_severity);
        const sevValues = Object.values(data.by_severity);
        const sevColors = sevLabels.map(s => {
          if (s === 'CRITICAL') return '#ff1744';
          if (s === 'HIGH') return '#ff9100';
          if (s === 'MEDIUM') return '#ffd600';
          return '#00e676';
        });

        this.severityChart = new Chart(sevCanvas, {
          type: 'bar',
          data: {
            labels: sevLabels,
            datasets: [{
              label: 'Incidents Logged',
              data: sevValues,
              backgroundColor: sevColors,
              borderRadius: 4
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { display: false }
            },
            scales: {
              y: { beginAtZero: true }
            }
          }
        });
      }
    } catch (e) {
      console.error("Error rendering incident breakdown:", e);
    }
  }

  renderNetworkMetricsChart() {
    const canvas = document.getElementById("chart-network-sla");
    if (!canvas) return;

    if (this.networkChart) this.networkChart.destroy();

    const times = ["T-5m", "T-4m", "T-3m", "T-2m", "T-1m", "NOW"];
    this.networkChart = new Chart(canvas, {
      type: 'line',
      data: {
        labels: times,
        datasets: [
          {
            label: 'Avg FPS (All Cams)',
            data: [24.8, 25.0, 24.9, 25.1, 24.8, 25.0],
            borderColor: '#00e676',
            backgroundColor: 'rgba(0, 230, 118, 0.1)',
            yAxisID: 'y'
          },
          {
            label: 'Latency (ms)',
            data: [42, 45, 38, 48, 41, 39],
            borderColor: '#00f2fe',
            backgroundColor: 'rgba(0, 242, 254, 0.1)',
            yAxisID: 'y1'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            type: 'linear',
            position: 'left',
            min: 0,
            max: 30,
            title: { display: true, text: 'Frames Per Second' }
          },
          y1: {
            type: 'linear',
            position: 'right',
            min: 0,
            max: 100,
            grid: { drawOnChartArea: false },
            title: { display: true, text: 'Latency (ms)' }
          }
        }
      }
    });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  window.analyticsCharts = new AnalyticsCharts();
});

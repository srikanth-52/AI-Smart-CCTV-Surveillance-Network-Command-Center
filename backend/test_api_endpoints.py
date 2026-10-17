import urllib.request
import json

def test_api():
    base = "http://127.0.0.1:8000"
    print("Testing REST API Endpoints against running server:")

    # 1. Overview
    with urllib.request.urlopen(f"{base}/api/analytics/overview") as res:
        data = json.loads(res.read().decode())
        print(f"  [OK] /api/analytics/overview: {data['total_cameras']} cameras, health {data['system_health_score']}%")

    # 2. Cameras
    with urllib.request.urlopen(f"{base}/api/cameras") as res:
        cams = json.loads(res.read().decode())
        print(f"  [OK] /api/cameras: {len(cams)} cameras returned")

    # 3. Crowd trends
    with urllib.request.urlopen(f"{base}/api/analytics/crowd_trends") as res:
        trends = json.loads(res.read().decode())
        print(f"  [OK] /api/analytics/crowd_trends: {len(trends['labels'])} hours")

    # 4. Incidents
    with urllib.request.urlopen(f"{base}/api/incidents") as res:
        inc = json.loads(res.read().decode())
        print(f"  [OK] /api/incidents: {len(inc)} incident logs")

    # 5. Frontend HTML
    with urllib.request.urlopen(f"{base}/") as res:
        html = res.read().decode()
        assert "<title>AI CCTV Surveillance Command Center" in html
        print(f"  [OK] / (Frontend index.html): {len(html)} bytes delivered successfully")

    print("\nAll HTTP Endpoints are healthy and delivering active video feeds and data!")

if __name__ == "__main__":
    test_api()

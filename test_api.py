"""
Unit & Integration Tests for Candidate Discovery Microservice
"""

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    print("[PASS] Health check passed!")

def test_search_endpoint():
    response = client.get("/api/v1/candidates/search?skills=python,sql&min_yoe=3&max_yoe=8&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) <= 5
    assert "latency_ms" in data
    print(f"[PASS] Search endpoint passed! Retrieved {len(data['results'])} candidates in {data['latency_ms']} ms.")

def test_honeypot_audit_rejection():
    fake_candidate = {
        "candidate_id": "FAKE_001",
        "profile": {"years_of_experience": 10},
        "education": [{"end_year": 2025}],
        "redrob_signals": {
            "expected_salary_range_inr_lpa": {"min": 50, "max": 20}  # Salary Inversion!
        },
        "skills": []
    }
    response = client.post("/api/v1/candidates/audit", json={"candidate": fake_candidate})
    assert response.status_code == 200
    data = response.json()
    assert data["is_honeypot"] is True
    assert len(data["reasons"]) >= 1
    print(f"[PASS] Honeypot audit caught fake candidate! Reasons: {data['reasons']}")

if __name__ == "__main__":
    test_health()
    test_search_endpoint()
    test_honeypot_audit_rejection()
    print("\n[SUCCESS] ALL TESTS PASSED!")

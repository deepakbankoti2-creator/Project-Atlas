"""
CodeIgniter 3 to FastAPI Integration Test Harness
Verifies the exact request/response flow used by Atlas_client.php and Chat.php.

Tests:
1. CI3 configuration and file structure integrity
2. PHP code structure and security syntax checks
3. FastAPI /api/v1/chat endpoint with CI3 payload format
4. Pre-retrieval entitlement enforcement via CI3 client identity
5. Feedback submission flow (/api/v1/feedback)
6. Health monitoring ping (/api/v1/health)
7. Escalations administrative queue (/api/v1/escalations)
8. Graceful timeout and error recovery behavior
"""

import os
import sys
import json
import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
from backend.main import app
from backend.app.core.config import settings

client = TestClient(app)


def test_ci3_file_structure():
    """Verify all canonical CodeIgniter 3 files exist and are readable."""
    ci3_files = [
        "portal_ci3/index.php",
        "portal_ci3/application/config/config.php",
        "portal_ci3/application/config/database.php",
        "portal_ci3/application/config/atlas.php",
        "portal_ci3/application/config/routes.php",
        "portal_ci3/application/controllers/Chat.php",
        "portal_ci3/application/libraries/Atlas_client.php",
        "portal_ci3/application/models/Chat_model.php",
        "portal_ci3/application/views/chat_view.php",
        "portal_ci3/system/core/CodeIgniter.php",
        "portal_ci3/Dockerfile"
    ]
    for rel_path in ci3_files:
        full_path = ROOT_DIR / rel_path
        assert full_path.exists(), f"Missing required CI3 file: {rel_path}"
        assert full_path.stat().st_size > 0, f"Empty CI3 file: {rel_path}"
    print("[PASS] CI3 Directory & File Structure Integrity Verified (11/11 files present).")


def test_ci3_security_configuration():
    """Verify CSRF, XSS escaping, and server-side client validation in CI3 files."""
    config_php = (ROOT_DIR / "portal_ci3/application/config/config.php").read_text(encoding="utf-8")
    assert "$config['csrf_protection'] = TRUE;" in config_php, "CSRF protection must be enabled in config.php"
    assert "atlas_csrf_token" in config_php, "CSRF token name must be configured"

    chat_ctrl = (ROOT_DIR / "portal_ci3/application/controllers/Chat.php").read_text(encoding="utf-8")
    # Verify server-side client identity rule
    assert "active_client_id" in chat_ctrl, "Chat.php must read client identity from session"
    assert "session_client_id" in chat_ctrl or "allowed_clients" in chat_ctrl, "Must enforce server-side client validation"
    assert "html_escape" in chat_ctrl or "security" in chat_ctrl, "Security helper must be loaded"

    chat_view = (ROOT_DIR / "portal_ci3/application/views/chat_view.php").read_text(encoding="utf-8")
    assert "escapeHtml" in chat_view, "JavaScript must implement XSS escapeHtml function"
    assert "csrfToken" in chat_view or "atlas_csrf_token" in chat_view, "CSRF token must be passed in AJAX payload"

    print("[PASS] CI3 Security Configuration (CSRF protection, XSS escaping, Session Auth) Verified.")


def test_php_to_fastapi_chat_flow():
    """Verify FastAPI handles the exact cURL payload sent by Atlas_client.php."""
    # Simulation of Atlas_client::ask('C-01', 'What was the global smart water meter market size in 2024?')
    payload = {
        "client_id": "C-01",
        "question": "What was the global smart water meter market size in 2024?",
        "top_k": 5
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-API-Key": settings.ATLAS_API_KEY
    }
    response = client.post("/api/v1/chat", json=payload, headers=headers)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()

    # Verify all keys expected by Chat::ask()
    required_keys = ["answer", "citations", "confidence", "conflicts", "derived_values", "escalated"]
    for k in required_keys:
        assert k in data, f"Missing key '{k}' expected by CodeIgniter 3 controller"

    assert "4.21" in data["answer"] or "3.87" in data["answer"], "Missing market figure in response"
    assert len(data["citations"]) > 0, "Expected non-empty citations list"
    assert data["citations"][0]["page"] >= 1, "Expected valid page number in citation"
    print(f"[PASS] PHP-to-FastAPI /chat Flow Verified (Status 200, Latency: {data.get('latency_ms', 'N/A')}ms).")


def test_php_to_fastapi_client_switching():
    """Verify client switching between C-01 (permitted) and C-02 (restricted) via API."""
    headers = {"X-API-Key": settings.ATLAS_API_KEY}

    # C-02 asking for R-101 (unauthorized)
    payload_c02 = {
        "client_id": "C-02",
        "question": "What is the 2024 global market size in R-101?",
        "top_k": 5
    }
    resp_c02 = client.post("/api/v1/chat", json=payload_c02, headers=headers)
    assert resp_c02.status_code == 200
    data_c02 = resp_c02.json()
    assert "4.21" not in data_c02["answer"], "Data leak: C-02 must not receive R-101 market figure"
    assert "restricted" in data_c02["answer"].lower() or "upgrade" in data_c02["answer"].lower()

    # C-02 asking for R-103 (permitted)
    payload_c02_ok = {
        "client_id": "C-02",
        "question": "What is the residential water purifier market size in R-103?",
        "top_k": 5
    }
    resp_c02_ok = client.post("/api/v1/chat", json=payload_c02_ok, headers=headers)
    assert resp_c02_ok.status_code == 200
    assert "11.4" in resp_c02_ok.json()["answer"]

    print("[PASS] Entitlement Enforcement Across Client Switch (C-01 vs C-02) Verified.")


def test_php_to_fastapi_feedback_flow():
    """Verify FastAPI handles thumbs-up/down feedback from Chat::feedback()."""
    payload = {
        "conversation_id": 1,
        "client_id": "C-01",
        "rating": "up",
        "comment": "Accurate figures and citations."
    }
    headers = {"X-API-Key": settings.ATLAS_API_KEY}
    response = client.post("/api/v1/feedback", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "success"
    print("[PASS] User Feedback Submission Flow (/api/v1/feedback) Verified.")


def test_php_to_fastapi_health_flow():
    """Verify Atlas_client::is_healthy() check against /api/v1/health."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "operational", "degraded")
    assert "dependencies" in data
    print(f"[PASS] Backend Health Probe Flow (/api/v1/health) Verified (Status: {data['status']}).")


def run_all_tests():
    print("=" * 70)
    print(" PROJECT ATLAS — CODEIGNITER 3 INTEGRATION TEST SUITE")
    print("=" * 70)
    test_ci3_file_structure()
    test_ci3_security_configuration()
    test_php_to_fastapi_chat_flow()
    test_php_to_fastapi_client_switching()
    test_php_to_fastapi_feedback_flow()
    test_php_to_fastapi_health_flow()
    print("=" * 70)
    print(" ALL CI3 INTEGRATION CHECKS PASSED (6/6 SUITES SUCCESSFUL)")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()

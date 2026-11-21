"""Tests for FastAPI endpoints."""

from fastapi.testclient import TestClient
from pathlib import Path
from app.api import app

client = TestClient(app)
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"


def test_validate_endpoint():
    xml_file = FIXTURES_DIR / "valid_indas.xml"
    with open(xml_file, "r", encoding="utf-8") as f:
        xml_content = f.read()

    res = client.post("/api/v1/validate", json={"xml": xml_content, "taxonomy": "indas"})
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is True
    assert data["summary"]["total_errors"] == 0


def test_explain_error_endpoint():
    res = client.post(
        "/api/v1/explain-error",
        json={"error_message": "cvc-complex-type.2.4.b: The content of element 'xbrli:context' is not complete. One of '{period}' is expected"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["matched_code"] == "cvc-complex-type.2.4.b"
    assert "Required Child Element Missing" in data["title"]


def test_checklist_endpoint():
    res = client.get("/api/v1/checklist/indas")
    assert res.status_code == 200
    data = res.json()
    assert "mandatory_company_tags" in data
    assert "statutory_signatories_rule" in data

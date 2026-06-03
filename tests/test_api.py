import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

SAMPLE_PDF = Path("samples/there samples/2025_2026_16_2_2_002203_0_4_1_20250203_0.pdf")


@pytest.fixture(autouse=True)
def clear_sessions():
    from api import session as sess
    sess._sessions.clear()
    yield
    sess._sessions.clear()


def test_upload_valid_pdf_returns_markup():
    with open(SAMPLE_PDF, "rb") as f:
        response = client.post(
            "/upload",
            files={"file": ("ks2203.pdf", f, "application/pdf")},
            data={"state": "KS"},
        )
    assert response.status_code == 200
    body = response.json()
    assert "session_id" in body
    assert "markup" in body
    assert "filename" in body
    assert body["state"] == "KS"
    assert len(body["markup"]) > 100


def test_upload_auto_detects_state():
    with open(SAMPLE_PDF, "rb") as f:
        response = client.post(
            "/upload",
            files={"file": ("ks2203.pdf", f, "application/pdf")},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["state"] in ("KS", None)


def test_upload_unsupported_state_returns_400():
    with open(SAMPLE_PDF, "rb") as f:
        response = client.post(
            "/upload",
            files={"file": ("bill.pdf", f, "application/pdf")},
            data={"state": "TX"},
        )
    assert response.status_code == 400
    assert "not yet supported" in response.json()["detail"].lower()


def test_upload_non_pdf_returns_422():
    fake = io.BytesIO(b"this is not a pdf")
    response = client.post(
        "/upload",
        files={"file": ("bill.txt", fake, "text/plain")},
        data={"state": "KS"},
    )
    assert response.status_code == 422


def test_get_pdf_returns_bytes():
    with open(SAMPLE_PDF, "rb") as f:
        upload = client.post(
            "/upload",
            files={"file": ("ks2203.pdf", f, "application/pdf")},
            data={"state": "KS"},
        )
    session_id = upload.json()["session_id"]
    response = client.get(f"/pdf/{session_id}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"


def test_get_pdf_unknown_session_returns_404():
    response = client.get("/pdf/no-such-id")
    assert response.status_code == 404


def test_delete_session_removes_it():
    with open(SAMPLE_PDF, "rb") as f:
        upload = client.post(
            "/upload",
            files={"file": ("ks2203.pdf", f, "application/pdf")},
            data={"state": "KS"},
        )
    session_id = upload.json()["session_id"]
    response = client.delete(f"/session/{session_id}")
    assert response.status_code == 200
    assert client.get(f"/pdf/{session_id}").status_code == 404

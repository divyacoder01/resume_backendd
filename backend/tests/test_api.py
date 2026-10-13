import io
import sys
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main  # noqa: E402
from schemas import CustomizeResult, Resume  # noqa: E402

JD = "We need a backend Python engineer with SQL and REST API experience for data services."


def make_docx(text: str) -> bytes:
    d = Document()
    d.add_paragraph(text)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


FAKE_RESULT = CustomizeResult(
    resume=Resume(name="Jane Doe", email="jane@example.com", skills=["Python"]),
    changes=["Reordered skills"],
    match_keywords=["Python"],
    missing_keywords=["Kubernetes"],
)


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    main._hits.clear()
    monkeypatch.setattr(main, "customize_resume", lambda text, jd: FAKE_RESULT)


client = TestClient(main.app)
RESUME_TEXT = "Jane Doe jane@example.com Python developer with five years of experience building APIs."


def post(name="cv.docx", data=None, jd=JD):
    data = make_docx(RESUME_TEXT) if data is None else data
    return client.post(
        "/customize", files={"resume": (name, data, "application/octet-stream")}, data={"job_description": jd}
    )


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_customize_ok():
    r = post()
    assert r.status_code == 200
    assert r.json()["resume"]["name"] == "Jane Doe"
    assert r.json()["missing_keywords"] == ["Kubernetes"]


def test_rejects_bad_extension():
    assert post(name="cv.txt").status_code == 400


def test_rejects_fake_pdf():
    assert post(name="cv.pdf", data=b"not a pdf").status_code == 400


def test_rejects_short_job_description():
    assert post(jd="too short").status_code == 400


def test_rejects_oversized_file():
    assert post(data=b"PK" + b"0" * (main.MAX_FILE_BYTES + 10)).status_code == 413


def test_rejects_unreadable_resume():
    assert post(data=b"PK-not-really-a-docx").status_code == 422


def test_llm_error_is_reported(monkeypatch):
    def boom(text, jd):
        raise main.LLMError("down", 503)

    monkeypatch.setattr(main, "customize_resume", boom)
    r = post()
    assert r.status_code == 503 and r.json()["detail"] == "down"


def test_rate_limit(monkeypatch):
    monkeypatch.setattr(main, "RATE_LIMIT", 2)
    assert post().status_code == 200
    assert post().status_code == 200
    assert post().status_code == 429


@pytest.mark.parametrize("fmt,magic", [("pdf", b"%PDF"), ("docx", b"PK")])
def test_download(fmt, magic):
    r = client.post(f"/download?format={fmt}", json=FAKE_RESULT.resume.model_dump())
    assert r.status_code == 200
    assert r.content.startswith(magic)
    assert "Jane_Doe_Resume" in r.headers["content-disposition"]

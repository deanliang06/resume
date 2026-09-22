import time

from fastapi.testclient import TestClient

from resume_adjuster.config import Settings
from resume_adjuster.main import create_app
from resume_adjuster.models import Stage
from conftest import FakeConverter, FakeProjectGenerator


def make_client(tmp_path):
    app = create_app(Settings(data_root=tmp_path / "data"), FakeConverter(), FakeProjectGenerator())
    return TestClient(app), app


def wait_for_terminal(client, job_id):
    for _ in range(100):
        response = client.get(f"/api/jobs/{job_id}")
        body = response.json()
        if body["stage"] in {"ready", "failed", "cancelled"}:
            return body
        time.sleep(.02)
    raise AssertionError("job did not finish")


def test_input_validation(tmp_path):
    with make_client(tmp_path)[0] as client:
        response = client.post("/api/jobs", files={"resume": ("bad.txt", b"x")}, data={"job_description": "x"})
        assert response.status_code == 422


def test_blank_description_and_corrupt_docx_never_queue(tmp_path, template_path):
    client, app = make_client(tmp_path)
    with client:
        blank = client.post("/api/jobs", files={"resume": ("r.docx", template_path.read_bytes())}, data={"job_description": "  "})
        corrupt = client.post("/api/jobs", files={"resume": ("r.docx", b"not-a-docx")}, data={"job_description": "Python"})
        assert blank.status_code == 422
        assert corrupt.status_code == 422
        assert app.state.jobs.jobs == {}


def test_end_to_end_preview_download_and_cleanup(tmp_path, template_path):
    client, app = make_client(tmp_path)
    with client:
        response = client.post(
            "/api/jobs",
            files={"resume": ("same-name.docx", template_path.read_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={"job_description": "Python Go React AWS SQL"},
        )
        assert response.status_code == 202
        job_id = response.json()["id"]
        status = wait_for_terminal(client, job_id)
        assert status["stage"] == "ready", status
        assert client.get(f"/api/jobs/{job_id}/preview").headers["content-type"] == "application/pdf"
        assert client.get(f"/api/jobs/{job_id}/download").status_code == 200
        assert not (app.state.jobs.settings.jobs_root / job_id).exists()


def test_sparse_evidence_returns_labeled_project_ideas(tmp_path, template_path):
    client, _ = make_client(tmp_path)
    with client:
        response = client.post("/api/jobs", files={"resume": ("r.docx", template_path.read_bytes())}, data={"job_description": "Python"})
        status = wait_for_terminal(client, response.json()["id"])
        assert status["stage"] == "ready"
        assert "project idea" in " ".join(status["notices"]).lower()
        assert client.get(f"/api/jobs/{status['id']}/download").status_code == 200

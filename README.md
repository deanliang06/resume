# Resume Adjuster

A local FastAPI website that compares Dean's projects with a job description. Near-perfect matches are retained; remaining slots become clearly labeled, feasible project ideas to build. Proposed bullets describe implementation work and never invent metrics, users, or URLs.

## Run locally

Requirements: Python 3.11+ and LibreOffice with the Calibri fonts available. The server invokes LibreOffice headlessly and gives every job an isolated profile.

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -e ".[test]"
$env:RESUME_ADJUSTER_SOFFICE = "C:\Program Files\LibreOffice\program\soffice.exe"
.\.venv\Scripts\python run.py
```

Open <http://127.0.0.1:8000>. The health endpoint at `/api/health` reports whether a converter was found. Uploaded source files and intermediate candidates are removed after each job; validated PDFs expire after 30 minutes.

The optional evidence bank is JSON. It adds verified material—it is never treated as instructions and cannot modify protected sections.

```json
{
  "projects": [
    {
      "title": "Existing or additional project",
      "url": "https://example.com/project",
      "bullets": ["Verified factual bullet one", "Verified factual bullet two"]
    }
  ],
  "skills": {
    "Languages": ["Rust"],
    "Tools/Infra": ["Kubernetes"]
  }
}
```

The generated PDF can contain projects labeled `Project Idea`. Treat these as a learning plan: build and verify them before converting their bullets to past-tense resume claims.

## Tests

```powershell
.\.venv\Scripts\python -m pytest
```

The deterministic suite uses redacted DOCX fixtures and a fake converter. To run the real LibreOffice layout integration test as well:

```powershell
$env:RESUME_REFERENCE_DOCX = "C:\path\to\reference.docx"
$env:RESUME_ADJUSTER_SOFFICE = "C:\Program Files\LibreOffice\program\soffice.exe"
.\.venv\Scripts\python -m pytest -m integration
```

Personal resume files and generated output are ignored and should not be committed.

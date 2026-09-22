# Resume Adjuster

A local FastAPI website that compares Dean's projects with a job description. Near-perfect matches are retained; the OpenAI API generates remaining slots as clearly labeled hypothetical project plans using a strict schema.

## Run locally

Requirements: Python 3.11+, LibreOffice, Calibri fonts, and an OpenAI API key.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
$env:RESUME_ADJUSTER_SOFFICE = "C:\Program Files\LibreOffice\program\soffice.exe"
$env:OPENAI_API_KEY = "your-api-key"
.\.venv\Scripts\python.exe run.py
```

Open <http://127.0.0.1:8000>. The `/api/health` endpoint reports the converter, generation provider, and configured model. Uploaded sources and intermediate candidates are removed after each job; validated PDFs expire after 30 minutes.

Generation uses `gpt-5-mini` by default. Set `RESUME_ADJUSTER_MODEL` to select another Structured Outputs-capable model. Each generated item has a title and two or three implementation-plan bullets. Application validation adds `(Hypothetical Project)` to every generated title and prohibits generated URLs.

The job description and generated project output are processed by OpenAI when hypothetical projects are needed. Existing resume projects and protected sections are not sent in the generation prompt. Hypothetical projects are evaluation or learning-plan content, never completed candidate claims.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The deterministic suite uses redacted DOCX fixtures, a fake project generator, and a fake converter. To run the real LibreOffice layout integration test as well:

```powershell
$env:RESUME_REFERENCE_DOCX = "C:\path\to\reference.docx"
$env:RESUME_ADJUSTER_SOFFICE = "C:\Program Files\LibreOffice\program\soffice.exe"
.\.venv\Scripts\python.exe -m pytest -m integration
```

Personal resume files and generated output are ignored and should not be committed.

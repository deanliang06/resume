# Resume Adjuster

A local FastAPI website that compares Dean's projects with a job description. Near-perfect matches are retained; OpenRouter generates remaining slots as clearly labeled hypothetical project plans using a strict JSON schema. The output is an edited DOCX.

## Run locally

Requirements: Python 3.11+ and an OpenRouter API key. LibreOffice is not required.

1. Install dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
```

2. Open the gitignored `.env` file and set your OpenRouter key:

```dotenv
OPENROUTER_API_KEY=replace-with-your-openrouter-key
RESUME_ADJUSTER_BASE_URL=https://openrouter.ai/api/v1
RESUME_ADJUSTER_MODEL=deepseek/deepseek-v4-flash-0731
```

3. Start the server:

```powershell
.\.venv\Scripts\python.exe run.py
```

Open <http://127.0.0.1:8000>. The `/api/health` endpoint reports `docx` as the output format plus the generation provider and model.

The tailored file is retained for 30 minutes. Because the server no longer renders a PDF, it does not enforce a one-page result or detect visual wrapping; pagination can vary with Word version and installed fonts.

Use the format dropdown to choose Word or LaTeX. Word mode accepts the existing
DOCX template. LaTeX mode accepts a complete `.tex` source document and returns
the tailored raw source for copying or download. LaTeX templates must have a
`Projects` section using `\resumeProjectHeading` and `\resumeItem`, plus a
`Technical Skills` section with `\textbf` rows for Languages, Libraries,
Web & Database, and Tools/Infra. Other source is preserved.

The Technical Skills format dropdown can retain those standard rows or switch
the output to Languages, Frameworks/Libraries, Cloud/Developer Tools, and
AI Assisted Development. Existing skills are recategorized, and generated
project prompts receive the selected category profile.

DeepSeek V4 Flash 0731 is called through OpenRouter's OpenAI-compatible API. Generated projects use strict JSON-schema output, receive a `(Hypothetical Project)` title label, and cannot include URLs. Existing resume projects and protected sections are not sent in the generation prompt.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Personal resume files, `.env`, and generated output are ignored. `.env.example` documents the required variables without containing secrets.

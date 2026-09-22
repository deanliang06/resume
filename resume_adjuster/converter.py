from __future__ import annotations

import subprocess
from pathlib import Path

from .errors import ConversionFailure


class LibreOfficeConverter:
    def __init__(self, executable: str | None, timeout: int = 60):
        self.executable = executable
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.executable)

    def convert(self, source: Path, output: Path, profile: Path) -> None:
        if not self.executable:
            raise ConversionFailure(
                "LibreOffice is not configured. Install it or set RESUME_ADJUSTER_SOFFICE to soffice.exe."
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        profile.mkdir(parents=True, exist_ok=True)
        command = [
            self.executable,
            "--headless",
            f"-env:UserInstallation={profile.resolve().as_uri()}",
            "--convert-to", "pdf:writer_pdf_Export",
            "--outdir", str(output.parent),
            str(source),
        ]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=self.timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise ConversionFailure("DOCX conversion exceeded the 60-second limit.") from exc
        produced = output.parent / (source.stem + ".pdf")
        if completed.returncode != 0 or not produced.exists():
            detail = (completed.stderr or completed.stdout).strip()[-500:]
            raise ConversionFailure(f"LibreOffice could not render the DOCX. {detail}".strip())
        if produced != output:
            produced.replace(output)

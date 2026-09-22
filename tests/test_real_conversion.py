import os
import shutil
from pathlib import Path

import pytest

from resume_adjuster.config import Settings
from resume_adjuster.converter import LibreOfficeConverter
from resume_adjuster.docx_template import parse_resume


@pytest.mark.integration
def test_reference_template_renders_as_one_letter_page(tmp_path):
    source_value = os.getenv("RESUME_REFERENCE_DOCX")
    converter_path = os.getenv("RESUME_ADJUSTER_SOFFICE") or shutil.which("soffice") or shutil.which("libreoffice")
    if not source_value or not Path(source_value).is_file():
        pytest.skip("Set RESUME_REFERENCE_DOCX to the private reference DOCX.")
    if not converter_path:
        pytest.skip("LibreOffice is not installed or configured.")
    source = Path(source_value)
    _, _, parsed = parse_resume(source)
    assert len(parsed.projects) >= 3
    output = tmp_path / "reference.pdf"
    LibreOfficeConverter(converter_path).convert(source, output, tmp_path / "profile")
    import fitz
    with fitz.open(output) as pdf:
        assert pdf.page_count == 1
        assert abs(pdf[0].rect.width - 612) <= 3
        assert abs(pdf[0].rect.height - 792) <= 3

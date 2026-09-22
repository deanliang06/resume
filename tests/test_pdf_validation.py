from pathlib import Path

import fitz
import pytest

from resume_adjuster.errors import LayoutFailure
from resume_adjuster.models import Project, TailoredResume
from resume_adjuster.pdf_validation import validate_pdf


def candidate():
    return TailoredResume(
        [Project("p1", "Alpha", None, ["First bullet", "Second bullet"], 0)],
        {"Languages": ["Python"], "Libraries": [], "Web & Database": [], "Tools/Infra": [], "Hobbies/Other": ["Chess"]},
    )


def test_rejects_two_pages(tmp_path):
    path = tmp_path / "two.pdf"
    pdf = fitz.open(); pdf.new_page(width=612, height=792); pdf.new_page(width=612, height=792); pdf.save(path); pdf.close()
    with pytest.raises(LayoutFailure, match="2 pages"):
        validate_pdf(path, candidate())


def test_rejects_clipped_text(tmp_path):
    path = tmp_path / "clipped.pdf"
    pdf = fitz.open(); page = pdf.new_page(width=612, height=792); page.insert_text((20, 100), "Alpha"); pdf.save(path); pdf.close()
    with pytest.raises(LayoutFailure, match="outside"):
        validate_pdf(path, candidate())


from __future__ import annotations

from pathlib import Path

import pytest
from docx import Document
from docx.enum.section import WD_SECTION
from docx.shared import Inches


@pytest.fixture
def template_path(tmp_path: Path) -> Path:
    path = tmp_path / "resume.docx"
    doc = Document()
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.left_margin = section.right_margin = section.top_margin = section.bottom_margin = Inches(1)
    for text, style in [
        ("Dean Example", None), ("Boston, MA", None), ("dean@example.com", None),
        ("Education:", None), ("Example University\t2024 - 2028", None),
        ("B.A. Computer Science", None), ("Coursework: Systems", "List Paragraph"),
        ("Experience:", None), ("Example Co.\t2025", None), ("Engineer", None),
        ("Built reliable systems", "List Paragraph"), ("Projects:", None), ("", None),
        ("Alpha (https://example.com/alpha)", None), ("Built Alpha with Python", "List Paragraph"),
        ("Improved Alpha reliability", "List Paragraph"), ("Beta (https://example.com/beta)", None),
        ("Built Beta with Go", "List Paragraph"), ("Gamma", None), ("Built Gamma with React", "List Paragraph"),
        ("Delta", None), ("Built Delta with SQL", "List Paragraph"), ("Skills:", None), ("", None),
        ("Languages: Python, Go, JavaScript", None), ("Libraries: PyTorch, Pandas", None),
        ("Web & Database: React, PostgreSQL", None), ("Tools/Infra: AWS, Docker, Git", None),
        ("Hobbies/Other: Tennis, Chess", None),
    ]:
        doc.add_paragraph(text, style=style)
    doc.save(path)
    return path


class FakeProjectGenerator:
    provider_name = "test generator"

    def generate(self, job_description: str, count: int):
        from resume_adjuster.models import Project
        return [Project(
            f"hypothetical-{index + 1}",
            f"Generated System {index + 1} (Hypothetical Project)",
            None,
            ["Build a small role-focused service", "Add tests for normal and failure paths", "Document implementation tradeoffs"],
            20_000 + index,
            proposed=True,
        ) for index in range(count)]


@pytest.fixture
def project_generator():
    return FakeProjectGenerator()

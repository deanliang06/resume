from pathlib import Path
from zipfile import ZipFile

import pytest
from docx import Document

from resume_adjuster.docx_template import (
    apply_tailoring, map_template, parse_resume, protected_digest, validate_docx_package,
)
from resume_adjuster.errors import InvalidInput, UnsupportedTemplate
from resume_adjuster.tailoring import tailor


def test_parses_known_template(template_path):
    _, mapping, parsed = parse_resume(template_path)
    assert [p.title for p in parsed.projects] == ["Alpha", "Beta", "Gamma", "Delta"]
    assert parsed.projects[0].url == "https://example.com/alpha"
    assert mapping.skill_indexes["Hobbies/Other"] > mapping.section_indexes["Skills:"]


def test_missing_or_duplicate_heading_rejected(template_path, tmp_path):
    doc = Document(template_path)
    doc.paragraphs[7].text = "Work:"
    bad = tmp_path / "bad.docx"
    doc.save(bad)
    with pytest.raises(UnsupportedTemplate, match="Experience"):
        parse_resume(bad)


def test_corrupt_and_unsafe_packages_rejected(tmp_path):
    corrupt = tmp_path / "corrupt.docx"
    corrupt.write_bytes(b"not a zip")
    with pytest.raises(InvalidInput):
        validate_docx_package(corrupt, 1000)
    unsafe = tmp_path / "unsafe.docx"
    with ZipFile(unsafe, "w") as archive:
        archive.writestr("word/document.xml", "x")
        archive.writestr("../escape", "x")
    with pytest.raises(InvalidInput, match="unsafe"):
        validate_docx_package(unsafe, 1000)


def test_edit_preserves_protected_xml_and_hobbies(template_path, tmp_path, evidence_bank):
    original, mapping, parsed = parse_resume(template_path)
    before = protected_digest(original, mapping)
    candidate = tailor(parsed, "Python Go React AWS SQL", evidence_bank)
    output = tmp_path / "tailored.docx"
    apply_tailoring(template_path, output, candidate)
    edited, edited_mapping, edited_parsed = parse_resume(output)
    assert protected_digest(edited, edited_mapping) == before
    assert edited_parsed.skills["Hobbies/Other"] == ["Tennis", "Chess"]
    assert len(edited_parsed.projects) == 4
    assert all(len(project.bullets) >= 2 for project in edited_parsed.projects)


def test_three_project_fallback_removes_whole_block(template_path, tmp_path, evidence_bank):
    _, _, parsed = parse_resume(template_path)
    candidate = tailor(parsed, "Python", evidence_bank)
    candidate.projects.pop()
    output = tmp_path / "three.docx"
    apply_tailoring(template_path, output, candidate)
    _, _, reparsed = parse_resume(output)
    assert len(reparsed.projects) == 3


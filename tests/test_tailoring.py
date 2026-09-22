import pytest

from resume_adjuster.errors import InvalidInput
from resume_adjuster.docx_template import parse_resume
from resume_adjuster.tailoring import parse_evidence_bank, tailor
from resume_adjuster.models import ParsedResume, Project


def test_proposes_projects_when_resume_projects_are_not_close_matches(template_path):
    _, _, parsed = parse_resume(template_path)
    result = tailor(parsed, "Python FastAPI PostgreSQL Docker AWS backend developer")
    assert len(result.projects) == 4
    assert any(project.proposed for project in result.projects)
    assert all(len(project.bullets) <= 3 for project in result.projects)
    assert all(project.url is None for project in result.projects if project.proposed)
    assert all(project.title.endswith("(Project Idea)") for project in result.projects if project.proposed)


def test_ranks_relevant_projects_and_caps_bullets(template_path, evidence_bank):
    _, _, parsed = parse_resume(template_path)
    result = tailor(parsed, "Go Python backend AWS PostgreSQL", evidence_bank)
    assert len(result.projects) == 4
    assert any(project.proposed for project in result.projects)
    assert all(2 <= len(project.bullets) <= 3 for project in result.projects)


def test_keeps_a_near_perfect_existing_project():
    aligned = Project("p1", "Cloud API", None, [
        "Built a Python FastAPI service backed by PostgreSQL",
        "Deployed the API to AWS with Docker",
    ], 0)
    parsed = ParsedResume([aligned], {"Languages": ["Python"]}, [])
    result = tailor(parsed, "Python FastAPI PostgreSQL AWS Docker backend API")
    assert result.projects[0].source_id == "p1"
    assert result.projects[0].proposed is False
    assert len(result.projects) == 4


def test_alias_dedup_does_not_merge_distinct_languages(template_path, evidence_bank):
    _, _, parsed = parse_resume(template_path)
    result = tailor(parsed, "Java JavaScript", evidence_bank)
    languages = result.skills["Languages"]
    assert "JavaScript" in languages
    assert "JS" not in languages
    assert "Go" in languages


@pytest.mark.parametrize("raw", ["not json", "[]", '{"projects":[{"title":"x","url":"file:///x"}]}'])
def test_bad_bank_rejected(raw):
    with pytest.raises(InvalidInput):
        parse_evidence_bank(raw)

from __future__ import annotations

import re
from dataclasses import replace

from .docx_template import SKILL_LABELS
from .errors import GenerationFailure, InvalidInput
from .generation import ProjectGenerator
from .models import ParsedResume, Project, TailoredResume

WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.-]{1,}")
STOP_WORDS = {
    "and", "are", "for", "from", "have", "into", "job", "our", "that", "the",
    "this", "using", "we", "will", "with", "you", "your", "years", "work",
}
ALIASES = {
    "js": "javascript",
    "javascript": "javascript",
    "ts": "typescript",
    "typescript": "typescript",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "sklearn": "scikit-learn",
    "scikit-learn": "scikit-learn",
    "github actions": "github actions",
    "github/github actions": "github actions",
}

TECH_TERMS = {
    "python", "go", "java", "javascript", "typescript", "rust", "c++", "c#",
    "react", "vue", "angular", "node", "django", "flask", "fastapi", "spring",
    "sql", "postgresql", "mysql", "mongodb", "redis", "graphql", "rest",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "linux",
    "pytorch", "tensorflow", "pandas", "spark", "airflow", "kafka",
    "machine learning", "data", "backend", "frontend", "fullstack", "api",
    "security", "mobile", "android", "ios", "ci/cd", "github actions",
}


def _requirements(text: str) -> set[str]:
    lowered = text.casefold()
    found = {
        term for term in TECH_TERMS
        if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", lowered)
    }
    return {_canonical(term) for term in found}


def _project_requirements(project: Project) -> set[str]:
    return _requirements(" ".join([project.title, *project.bullets]))


def _is_near_perfect(project: Project, wanted: set[str]) -> bool:
    if not wanted:
        return False
    matched = _project_requirements(project) & wanted
    needed = max(2, min(4, (len(wanted) + 1) // 2))
    return len(matched) >= needed and len(matched) / len(wanted) >= 0.5


def keywords(text: str) -> set[str]:
    return {word.lower() for word in WORD_RE.findall(text) if word.lower() not in STOP_WORDS}


def _canonical(skill: str) -> str:
    normalized = " ".join(skill.lower().split())
    return ALIASES.get(normalized, normalized)


def tailor(parsed: ParsedResume, job_description: str, generator: ProjectGenerator) -> TailoredResume:
    if not job_description.strip():
        raise InvalidInput("A job description is required.")
    eligible = [project for project in parsed.projects if len(project.bullets) >= 2]
    wanted = _requirements(job_description)

    def project_score(project: Project) -> tuple[int, int]:
        content = " ".join([project.title, *project.bullets])
        return (len(_requirements(content) & wanted), -project.source_order)

    ranked = sorted((p for p in eligible if _is_near_perfect(p, wanted)), key=project_score, reverse=True)
    chosen = []
    for project in ranked[:4]:
        bullets = sorted(
            enumerate(project.bullets),
            key=lambda pair: (len(_requirements(pair[1]) & wanted), -pair[0]),
            reverse=True,
        )
        chosen.append(replace(project, bullets=[text for _, text in bullets[:3]]))
    notices = []
    proposed_count = 4 - len(chosen)
    if proposed_count:
        generated = generator.generate(job_description, proposed_count)
        if len(generated) != proposed_count or any(not project.proposed for project in generated):
            raise GenerationFailure("The project generator returned an invalid candidate count or unlabeled project.")
        if any(len(project.bullets) not in (2, 3) or project.url for project in generated):
            raise GenerationFailure("Every hypothetical project must have two or three bullets and no URL.")
        chosen.extend(generated)
        verb = "were" if proposed_count != 1 else "was"
        notices.append(f"{proposed_count} project idea{'s' if proposed_count != 1 else ''} {verb} added as work to build; do not present proposed bullets as completed experience.")

    skills: dict[str, list[str]] = {}
    seen: set[str] = set()
    for label in SKILL_LABELS:
        values = list(parsed.skills.get(label, []))
        result = []
        for value in values:
            canonical = _canonical(value)
            if canonical in seen and label != "Hobbies/Other":
                continue
            result.append(value)
            if label != "Hobbies/Other":
                seen.add(canonical)
        # Keep source ordering stable, but bring explicit requirement matches forward.
        if label != "Hobbies/Other":
            result = sorted(enumerate(result), key=lambda x: (_canonical(x[1]) in wanted, -x[0]), reverse=True)
            result = [value for _, value in result]
        skills[label] = result
    return TailoredResume(chosen, skills, notices)

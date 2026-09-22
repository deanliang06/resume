from __future__ import annotations

import json
import re
from dataclasses import replace

from .docx_template import SKILL_LABELS, valid_external_url
from .errors import InvalidInput
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


def _preferred(wanted: set[str], choices: tuple[str, ...], fallback: str) -> str:
    return next((choice for choice in choices if _canonical(choice) in wanted), fallback)


def _project_ideas(wanted: set[str], count: int) -> list[Project]:
    language = _preferred(wanted, ("Python", "TypeScript", "JavaScript", "Go", "Java", "Rust"), "Python")
    database = _preferred(wanted, ("PostgreSQL", "MySQL", "MongoDB", "Redis", "SQL"), "PostgreSQL")
    cloud = _preferred(wanted, ("AWS", "Azure", "GCP"), "Docker")
    frontend = _preferred(wanted, ("React", "Vue", "Angular"), "React")
    ml = _preferred(wanted, ("PyTorch", "TensorFlow", "Pandas", "Spark"), "Pandas")
    specs: list[tuple[str, list[str]]] = []
    if wanted & {_canonical(x) for x in ("machine learning", "data", "pytorch", "tensorflow", "pandas", "spark", "airflow")}:
        specs.append(("Job-Market Skills Explorer (Project Idea)", [
            f"Build a reproducible {language} data pipeline that cleans job-posting data and stores structured results in {database}.",
            f"Implement skill-demand analysis and a small evaluation suite with {ml}, documenting assumptions and failure cases.",
            f"Add an interactive {frontend} dashboard for filtering roles, skills, and trends.",
        ]))
    if wanted & {_canonical(x) for x in ("backend", "api", "rest", "graphql", "fastapi", "django", "flask", "spring", "node")}:
        specs.append(("Production-Style Service API (Project Idea)", [
            f"Build a documented service in {language} with authentication, validation, pagination, and a {database} persistence layer.",
            "Implement unit and integration tests for core workflows, error cases, and access control.",
            f"Package the service with Docker and add a repeatable deployment configuration for {cloud}.",
        ]))
    if wanted & {_canonical(x) for x in ("frontend", "fullstack", "react", "vue", "angular", "javascript", "typescript")}:
        specs.append(("Collaborative Workflow Board (Project Idea)", [
            f"Build an accessible {frontend} interface with typed forms, optimistic updates, filtering, and responsive layouts.",
            f"Implement a {language} API and {database} data model for projects, tasks, comments, and permissions.",
            "Add end-to-end tests for the main user journeys and document key design tradeoffs.",
        ]))
    if wanted & {_canonical(x) for x in ("aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ci/cd", "github actions", "linux")}:
        specs.append(("Observable Cloud Deployment (Project Idea)", [
            f"Containerize a small {language} service and provision its {cloud} environment with version-controlled infrastructure.",
            "Add CI checks for formatting, tests, dependency scanning, and a staged deployment workflow.",
            "Implement health checks, structured logs, dashboards, and an incident runbook for common failures.",
        ]))
    if "security" in wanted:
        specs.append(("Secure File-Sharing Service (Project Idea)", [
            f"Build a {language} service with scoped access, expiring links, input validation, and encrypted storage metadata.",
            "Add threat-model documentation and automated tests for authorization and malicious-input cases.",
            "Run the application in Docker with auditable configuration and dependency checks.",
        ]))
    fallbacks = [
        ("Role-Focused Capstone (Project Idea)", [f"Build an end-to-end application in {language} around a documented user workflow.", f"Add {database} storage and tests for normal and failure paths.", "Package it with Docker and document setup, architecture, and tradeoffs."]),
        ("Reliability Test Harness (Project Idea)", [f"Build a {language} harness for API retries, timeouts, and malformed responses.", "Add deterministic fixtures and summarize failures in a local report.", "Document reliability choices and provide a one-command demo."]),
        ("Developer Productivity CLI (Project Idea)", [f"Build a {language} CLI that validates configuration and reports actionable errors.", "Add unit tests, fixtures, error handling, and cross-platform setup notes.", "Package releases through a small continuous-integration workflow."]),
        ("Searchable Knowledge Base (Project Idea)", [f"Build a searchable app with {frontend}, a {language} API, and {database}.", "Add import validation, ranking, filters, and malformed-content tests.", "Document setup and the data-model and search tradeoffs."]),
    ]
    used = {title for title, _ in specs}
    specs.extend(item for item in fallbacks if item[0] not in used)
    return [Project(f"proposed-project-{i + 1}", title, None, bullets[:3], 20_000 + i, proposed=True)
            for i, (title, bullets) in enumerate(specs[:count])]


def keywords(text: str) -> set[str]:
    return {word.lower() for word in WORD_RE.findall(text) if word.lower() not in STOP_WORDS}


def _canonical(skill: str) -> str:
    normalized = " ".join(skill.lower().split())
    return ALIASES.get(normalized, normalized)


def parse_evidence_bank(raw: str | None) -> tuple[list[Project], dict[str, list[str]]]:
    if not raw or not raw.strip():
        return [], {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InvalidInput("The optional evidence bank must be valid JSON.") from exc
    if not isinstance(value, dict):
        raise InvalidInput("The evidence bank must be a JSON object.")
    projects = []
    for order, item in enumerate(value.get("projects", [])):
        if not isinstance(item, dict) or not isinstance(item.get("title"), str):
            raise InvalidInput("Every bank project needs a title.")
        bullets = item.get("bullets", [])
        if not isinstance(bullets, list) or not all(isinstance(b, str) and b.strip() for b in bullets):
            raise InvalidInput("Every bank project bullet must be nonempty text.")
        url = item.get("url")
        if url is not None and (not isinstance(url, str) or not valid_external_url(url)):
            raise InvalidInput("Every project URL must be an absolute HTTP(S) URL.")
        projects.append(Project(f"bank-project-{order + 1}", item["title"].strip(), url, [b.strip() for b in bullets], 10_000 + order))
    skills = value.get("skills", {})
    if not isinstance(skills, dict):
        raise InvalidInput("Bank skills must be grouped by category.")
    parsed_skills = {}
    for label, values in skills.items():
        if label not in SKILL_LABELS[:-1]:
            raise InvalidInput(f"Unsupported skill category: {label}")
        if not isinstance(values, list) or not all(isinstance(v, str) and v.strip() for v in values):
            raise InvalidInput(f"Skills in {label} must be nonempty strings.")
        parsed_skills[label] = [v.strip() for v in values]
    return projects, parsed_skills


def _merge_projects(source: list[Project], bank: list[Project]) -> list[Project]:
    merged = [replace(project, bullets=list(project.bullets)) for project in source]
    by_title = {project.title.casefold(): project for project in merged}
    for project in bank:
        existing = by_title.get(project.title.casefold())
        if existing is None:
            merged.append(project)
            by_title[project.title.casefold()] = project
            continue
        for bullet in project.bullets:
            if bullet.casefold() not in {b.casefold() for b in existing.bullets}:
                existing.bullets.append(bullet)
        if existing.url is None:
            existing.url = project.url
        elif project.url and existing.url != project.url:
            raise InvalidInput(f"Conflicting URLs were supplied for {existing.title}.")
    return merged


def tailor(parsed: ParsedResume, job_description: str, bank_raw: str | None = None) -> TailoredResume:
    if not job_description.strip():
        raise InvalidInput("A job description is required.")
    bank_projects, bank_skills = parse_evidence_bank(bank_raw)
    candidates = _merge_projects(parsed.projects, bank_projects)
    eligible = [project for project in candidates if len(project.bullets) >= 2]
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
        chosen.extend(_project_ideas(wanted, proposed_count))
        verb = "were" if proposed_count != 1 else "was"
        notices.append(f"{proposed_count} project idea{'s' if proposed_count != 1 else ''} {verb} added as work to build; do not present proposed bullets as completed experience.")

    skills: dict[str, list[str]] = {}
    seen: set[str] = set()
    for label in SKILL_LABELS:
        values = [*parsed.skills.get(label, []), *bank_skills.get(label, [])]
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

from __future__ import annotations

from .errors import InvalidInput

HOBBIES_LABEL = "Hobbies/Other"
STANDARD_SKILL_LABELS = (
    "Languages",
    "Libraries",
    "Web & Database",
    "Tools/Infra",
    HOBBIES_LABEL,
)
AI_SKILL_LABELS = (
    "Languages",
    "Frameworks/Libraries",
    "Cloud/Developer Tools",
    "AI Assisted Development",
    HOBBIES_LABEL,
)
SKILL_PROFILES = {
    "standard": STANDARD_SKILL_LABELS,
    "ai_assisted": AI_SKILL_LABELS,
}
ALL_SKILL_LABELS = tuple(dict.fromkeys(
    label for labels in SKILL_PROFILES.values() for label in labels
))

LANGUAGES = {
    "bash", "c", "c#", "c++", "css", "go", "html", "java", "javascript",
    "kotlin", "php", "python", "r", "ruby", "rust", "scala", "sql",
    "swift", "typescript",
}
CLOUD_AND_TOOLS = {
    "aws", "azure", "ci/cd", "circleci", "docker", "gcp", "git", "github",
    "github actions", "gitlab", "jenkins", "jira", "kubernetes", "linux",
    "maven", "npm", "postman", "terraform", "unix", "vercel", "vite",
}
AI_ASSISTED = {
    "chatgpt", "claude", "codeium", "cursor", "gemini", "github copilot",
    "langchain", "llm", "mcp", "openai", "openrouter", "prompt engineering",
    "windsurf",
}


def skill_labels(profile: str) -> tuple[str, ...]:
    try:
        return SKILL_PROFILES[profile]
    except KeyError as exc:
        raise InvalidInput("Choose a supported Technical Skills format.") from exc


def detect_profile(labels: set[str]) -> tuple[str, ...] | None:
    for profile_labels in SKILL_PROFILES.values():
        if set(profile_labels[:-1]).issubset(labels):
            return profile_labels
    return None


def category_for(skill: str, labels: tuple[str, ...]) -> str:
    normalized = " ".join(skill.casefold().split())
    if normalized in LANGUAGES:
        return "Languages"
    if labels == AI_SKILL_LABELS:
        if normalized in AI_ASSISTED or any(term in normalized for term in AI_ASSISTED):
            return "AI Assisted Development"
        if normalized in CLOUD_AND_TOOLS:
            return "Cloud/Developer Tools"
        return "Frameworks/Libraries"
    if normalized in CLOUD_AND_TOOLS:
        return "Tools/Infra"
    web_terms = {
        "angular", "django", "express", "fastapi", "flask", "graphql",
        "mongodb", "mysql", "next.js", "node", "postgresql", "react",
        "redis", "rest", "spring", "sql", "vue",
    }
    if normalized in web_terms:
        return "Web & Database"
    return "Libraries"

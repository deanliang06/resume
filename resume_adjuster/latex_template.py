from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import InvalidInput, UnsupportedTemplate
from .models import ParsedResume, Project, TailoredResume
from .skill_profiles import ALL_SKILL_LABELS, detect_profile

SECTION_RE = re.compile(r"\\section\*?\s*\{([^{}]+)\}", re.IGNORECASE)
PROJECT_HEADING_RE = re.compile(r"\\resumeProjectHeading\b")
PROJECT_ITEM_RE = re.compile(r"\\resumeItem\b")
SKILL_RE = re.compile(
    r"\\textbf\s*\{(Languages|Libraries|Web\s*(?:\\&|&)\s*Database|"
    r"Tools/Infra|Frameworks/Libraries|Cloud/Developer Tools|"
    r"AI Assisted Development|Hobbies/Other)\}",
    re.IGNORECASE,
)
URL_RE = re.compile(r"\\(?:href|url)\s*\{([^{}]+)\}")


@dataclass(frozen=True)
class LatexProjectBlock:
    start: int
    end: int
    source_id: str


@dataclass(frozen=True)
class LatexTemplate:
    source: str
    projects_content_start: int
    projects_content_end: int
    project_blocks: tuple[LatexProjectBlock, ...]
    skill_label_spans: dict[str, tuple[int, int]]
    skill_value_spans: dict[str, tuple[int, int]]


def _group(source: str, start: int) -> tuple[str, int, int]:
    while start < len(source) and source[start].isspace():
        start += 1
    if start >= len(source) or source[start] != "{":
        raise UnsupportedTemplate("A supported LaTeX command is missing a braced argument.")
    depth = 0
    escaped = False
    for index in range(start, len(source)):
        char = source[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start + 1:index], start + 1, index
    raise UnsupportedTemplate("The LaTeX source contains an unclosed command argument.")


def _arguments(source: str, command_end: int, count: int) -> list[tuple[str, int, int]]:
    arguments = []
    position = command_end
    for _ in range(count):
        value, content_start, content_end = _group(source, position)
        arguments.append((value, content_start, content_end))
        position = content_end + 1
    return arguments


def _plain_text(value: str) -> str:
    value = re.sub(r"\\href\s*\{[^{}]*\}\s*", "", value)
    value = re.sub(r"\\url\s*\{([^{}]*)\}", r"\1", value)
    value = re.sub(r"\\(?:textbf|emph|textit|texttt)\s*\{([^{}]*)\}", r"\1", value)
    value = re.sub(r"\\[a-zA-Z@]+\*?", "", value)
    value = value.replace(r"\&", "&").replace(r"\%", "%").replace(r"\_", "_")
    value = value.replace("$", "").replace("{", "").replace("}", "")
    return " ".join(value.split()).strip(" |-")


def _section_bounds(source: str, name: str) -> tuple[int, int]:
    sections = list(SECTION_RE.finditer(source))
    matches = [
        (index, match)
        for index, match in enumerate(sections)
        if match.group(1).strip().casefold() == name.casefold()
    ]
    if len(matches) != 1:
        raise UnsupportedTemplate(f"Expected exactly one LaTeX {name} section.")
    section_index, section = matches[0]
    end = sections[section_index + 1].start() if section_index + 1 < len(sections) else len(source)
    return section.end(), end


def _skill_label(raw: str) -> str:
    normalized = " ".join(raw.replace(r"\&", "&").split()).casefold()
    return next(label for label in ALL_SKILL_LABELS if label.casefold() == normalized)


def parse_latex(source: str) -> tuple[LatexTemplate, ParsedResume]:
    if not source.strip():
        raise InvalidInput("LaTeX source is required.")
    if "\x00" in source:
        raise InvalidInput("LaTeX source cannot contain null bytes.")

    projects_start, projects_end = _section_bounds(source, "Projects")
    headings = list(PROJECT_HEADING_RE.finditer(source, projects_start, projects_end))
    if not headings:
        raise UnsupportedTemplate(
            r"The Projects section must use \resumeProjectHeading and \resumeItem commands."
        )

    projects: list[Project] = []
    blocks: list[LatexProjectBlock] = []
    for order, heading in enumerate(headings):
        arguments = _arguments(source, heading.end(), 2)
        heading_text = arguments[0][0]
        block_limit = headings[order + 1].start() if order + 1 < len(headings) else projects_end
        items = list(PROJECT_ITEM_RE.finditer(source, arguments[-1][2] + 1, block_limit))
        bullets = [_plain_text(_arguments(source, item.end(), 1)[0][0]) for item in items]
        title = _plain_text(heading_text)
        if not title:
            raise UnsupportedTemplate("Every LaTeX project needs a non-empty title.")
        url_match = URL_RE.search(heading_text)
        source_id = f"latex-project-{order + 1}"
        projects.append(Project(
            source_id=source_id,
            title=title,
            url=url_match.group(1).strip() if url_match else None,
            bullets=[bullet for bullet in bullets if bullet],
            source_order=order,
        ))

        if order + 1 < len(headings):
            block_end = headings[order + 1].start()
        else:
            closing = source.find(r"\resumeSubHeadingListEnd", heading.end(), projects_end)
            block_end = closing if closing != -1 else projects_end
        blocks.append(LatexProjectBlock(heading.start(), block_end, source_id))

    skills_start, skills_end = _section_bounds(source, "Technical Skills")
    skill_label_spans: dict[str, tuple[int, int]] = {}
    skill_spans: dict[str, tuple[int, int]] = {}
    parsed_skill_values: dict[str, list[str]] = {}
    for match in SKILL_RE.finditer(source, skills_start, skills_end):
        label = _skill_label(match.group(1))
        value, value_start, value_end = _group(source, match.end())
        cleaned = value.strip()
        if cleaned.startswith(":"):
            cleaned = cleaned[1:].strip()
        parsed_skill_values[label] = [item.strip() for item in cleaned.split(",") if item.strip()]
        skill_label_spans[label] = match.span(1)
        skill_spans[label] = (value_start, value_end)

    profile_labels = detect_profile(set(skill_spans))
    if profile_labels is None:
        raise UnsupportedTemplate(
            r"The Technical Skills section must use one supported set of \textbf rows."
        )
    skills = {label: parsed_skill_values.get(label, []) for label in profile_labels}

    template = LatexTemplate(
        source=source,
        projects_content_start=projects_start,
        projects_content_end=projects_end,
        project_blocks=tuple(blocks),
        skill_label_spans=skill_label_spans,
        skill_value_spans=skill_spans,
    )
    return template, ParsedResume(projects, skills, source.splitlines())


def _escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in value)


def _render_project(project: Project) -> str:
    title = project.title
    if project.proposed and "(Hypothetical Project)" not in title:
        title += " (Hypothetical Project)"
    if project.url:
        heading = rf"\href{{{project.url}}}{{\textbf{{{_escape(title)}}}}}"
    else:
        heading = rf"\textbf{{{_escape(title)}}}"
    bullets = "\n".join(rf"      \resumeItem{{{_escape(bullet)}}}" for bullet in project.bullets)
    return (
        "  \\resumeProjectHeading\n"
        f"    {{{heading}}}{{}}\n"
        "    \\resumeItemListStart\n"
        f"{bullets}\n"
        "    \\resumeItemListEnd\n"
    )


def apply_latex_tailoring(template: LatexTemplate, tailored: TailoredResume) -> str:
    if not tailored.projects:
        raise UnsupportedTemplate("The tailored LaTeX resume has no projects.")

    first = template.project_blocks[0].start
    last = template.project_blocks[-1].end
    rendered_projects = "\n".join(_render_project(project) for project in tailored.projects)
    replacements: list[tuple[int, int, str]] = [(first, last, rendered_projects)]
    source_labels = [
        label
        for label in template.skill_value_spans
        if label != "Hobbies/Other"
    ]
    for source_label, target_label in zip(source_labels, tailored.skill_labels[:-1]):
        value_span = template.skill_value_spans[source_label]
        label_span = template.skill_label_spans[source_label]
        values = ", ".join(_escape(value) for value in tailored.skills.get(target_label, []))
        replacements.append((value_span[0], value_span[1], ": " + values))
        replacements.append((label_span[0], label_span[1], _escape(target_label)))

    result = template.source
    for start, end, value in sorted(replacements, reverse=True):
        result = result[:start] + value + result[end:]
    parse_latex(result)
    return result

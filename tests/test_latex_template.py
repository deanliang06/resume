import pytest

from resume_adjuster.errors import UnsupportedTemplate
from resume_adjuster.latex_template import apply_latex_tailoring, parse_latex
from resume_adjuster.tailoring import tailor


@pytest.fixture
def latex_source():
    return r"""
\documentclass{article}
\newcommand{\resumeProjectHeading}[2]{#1 #2}
\newcommand{\resumeItem}[1]{\item #1}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}}
\newcommand{\resumeSubHeadingListStart}{\begin{itemize}}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\begin{document}
\section{Projects}
\resumeSubHeadingListStart
  \resumeProjectHeading
    {\textbf{Cloud API} $|$ \emph{Python, FastAPI, PostgreSQL}}{}
    \resumeItemListStart
      \resumeItem{Built a Python FastAPI service backed by PostgreSQL}
      \resumeItem{Deployed the API to AWS with Docker}
    \resumeItemListEnd
  \resumeProjectHeading
    {\textbf{Frontend App} $|$ \emph{React}}{}
    \resumeItemListStart
      \resumeItem{Built a React interface}
      \resumeItem{Tested accessible user flows}
    \resumeItemListEnd
\resumeSubHeadingListEnd
\section{Technical Skills}
\textbf{Languages}{: Python, JavaScript} \\
\textbf{Libraries}{: FastAPI, React} \\
\textbf{Web \& Database}{: PostgreSQL, REST} \\
\textbf{Tools/Infra}{: AWS, Docker} \\
\textbf{Hobbies/Other}{: Chess}
\end{document}
"""


def test_parses_and_rewrites_latex(latex_source, project_generator):
    template, parsed = parse_latex(latex_source)
    assert len(parsed.projects) == 2
    assert parsed.projects[0].url is None
    assert parsed.skills["Languages"] == ["Python", "JavaScript"]

    tailored = tailor(
        parsed,
        "Python FastAPI PostgreSQL AWS Docker backend API",
        project_generator,
    )
    output = apply_latex_tailoring(template, tailored)
    _, reparsed = parse_latex(output)

    assert len(reparsed.projects) == 4
    assert r"\section{Technical Skills}" in output
    assert r"\textbf{Hobbies/Other}{: Chess}" in output
    assert "(Hypothetical Project)" in output


def test_rejects_latex_without_supported_project_commands(latex_source):
    unsupported = latex_source.replace(r"\resumeProjectHeading", r"\otherHeading")
    with pytest.raises(UnsupportedTemplate, match="resumeProjectHeading"):
        parse_latex(unsupported)


def test_ai_skill_rows_do_not_require_hobbies(latex_source, project_generator):
    source = (
        latex_source
        .replace(r"\textbf{Libraries}{: FastAPI, React}", r"\textbf{Frameworks/Libraries}{: FastAPI, React}")
        .replace(r"\textbf{Web \& Database}{: PostgreSQL, REST}", r"\textbf{Cloud/Developer Tools}{: AWS, Docker}")
        .replace(r"\textbf{Tools/Infra}{: AWS, Docker}", r"\textbf{AI Assisted Development}{: Cursor, Claude Code}")
        .replace("\n\\textbf{Hobbies/Other}{: Chess}", "")
    )
    template, parsed = parse_latex(source)
    tailored = tailor(
        parsed,
        "Python FastAPI AWS backend",
        project_generator,
        skills_format="ai_assisted",
    )
    output = apply_latex_tailoring(template, tailored)

    assert r"\textbf{AI Assisted Development}{: Cursor, Claude Code}" in output
    parse_latex(output)

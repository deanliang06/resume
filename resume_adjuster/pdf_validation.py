from __future__ import annotations

from pathlib import Path

import fitz

from .errors import LayoutFailure
from .models import TailoredResume


def _normalized(value: str) -> str:
    return " ".join(value.replace("•", " ").split())


def validate_pdf(path: Path, expected: TailoredResume) -> None:
    try:
        document = fitz.open(path)
    except Exception as exc:
        raise LayoutFailure("The rendered PDF could not be opened.") from exc
    try:
        if document.page_count != 1:
            raise LayoutFailure(f"The rendered resume has {document.page_count} pages; exactly one is required.")
        page = document[0]
        if abs(page.rect.width - 612) > 3 or abs(page.rect.height - 792) > 3:
            raise LayoutFailure("The rendered PDF is not US Letter portrait.")
        blocks = page.get_text("dict").get("blocks", [])
        lines = []
        for block in blocks:
            for line in block.get("lines", []):
                text = _normalized("".join(span.get("text", "") for span in line.get("spans", [])))
                if text:
                    lines.append((text, fitz.Rect(line["bbox"])))
        if not lines:
            raise LayoutFailure("No readable text was found in the PDF.")
        for text, box in lines:
            if box.x0 < 69 or box.x1 > 543 or box.y0 < 69 or box.y1 > 723:
                raise LayoutFailure(f"Text falls outside the allowed page region: {text[:60]}")
        expected_lines = []
        for project in expected.projects:
            expected_lines.append(project.title)
            expected_lines.extend(project.bullets)
        for label, values in expected.skills.items():
            expected_lines.append(f"{label}: {', '.join(values)}")
        rendered = [text for text, _ in lines]
        cursor = 0
        for expected_text in expected_lines:
            normalized = _normalized(expected_text)
            matches = [i for i in range(cursor, len(rendered)) if normalized in rendered[i]]
            if not matches:
                raise LayoutFailure(f"Expected one unwrapped visual line was not found: {expected_text[:80]}")
            cursor = matches[0] + 1
        link_targets = {link.get("uri") for link in page.get_links() if link.get("uri")}
        missing_links = [project.url for project in expected.projects if project.url and project.url not in link_targets]
        if missing_links:
            raise LayoutFailure("One or more project hyperlinks were lost during conversion.")
        sorted_boxes = sorted((box for _, box in lines), key=lambda b: (b.y0, b.x0))
        for first, second in zip(sorted_boxes, sorted_boxes[1:]):
            if second.y0 > first.y0 + 1 and second.y0 < first.y1 - 0.5:
                raise LayoutFailure("Adjacent rendered text lines overlap.")
    finally:
        document.close()

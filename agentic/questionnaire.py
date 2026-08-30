from __future__ import annotations

import json
import re
from pathlib import Path

from .models import QuestionSpec


QUESTION_RE = re.compile(r"^\s*(Q\s*\d+[A-Za-z]?)\s*[.):-]?\s*(.+)$", re.I)
CODE_RE = re.compile(r"^\s*([\-\d]+)\s*[=.)-]\s*(.+?)\s*$")
ROUTING_RE = re.compile(r"if\s+(Q\s*\d+[A-Za-z]?)\s*(?:=|is)\s*([^,;]+).*?(?:skip|go)\s+to\s+(Q\s*\d+[A-Za-z]?)", re.I)


def extract_questionnaire_text(path: str | Path) -> str:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix in {".txt", ".md", ".csv"}:
        return source.read_text(encoding="utf-8", errors="replace")
    if suffix == ".json":
        payload = json.loads(source.read_text(encoding="utf-8"))
        return json.dumps(payload, ensure_ascii=False, indent=2)
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF questionnaire support requires pypdf") from exc
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(source)).pages)
    if suffix == ".docx":
        try:
            from docx import Document
        except ImportError as exc:
            raise RuntimeError("DOCX questionnaire support requires python-docx") from exc
        document = Document(str(source))
        paragraphs = [paragraph.text for paragraph in document.paragraphs]
        for table in document.tables:
            paragraphs.extend(" | ".join(cell.text for cell in row.cells) for row in table.rows)
        return "\n".join(paragraphs)
    raise ValueError(f"Unsupported questionnaire format: {suffix or 'unknown'}")


def _clean_id(value: str) -> str:
    return re.sub(r"\s+", "", value).upper()


def parse_questionnaire(text: str) -> list[QuestionSpec]:
    lines = [line.strip() for line in text.replace("\r", "\n").split("\n") if line.strip()]
    questions: list[QuestionSpec] = []
    current: QuestionSpec | None = None
    for line in lines:
        question_match = QUESTION_RE.match(line)
        if question_match:
            question_id = _clean_id(question_match.group(1))
            body = question_match.group(2).strip()
            if body and not CODE_RE.match(body):
                current = QuestionSpec(question_id=question_id, variable=question_id, text=body)
                body_upper = body.upper()
                current.read_exactly = "READ EXACTLY" in body_upper or "ASK EXACTLY" in body_upper
                current.read_options = False if "DO NOT READ" in body_upper else True if "READ OPTIONS" in body_upper or "READ ALL OPTIONS" in body_upper else None
                current.probe = "PROBE" in body_upper
                current.consent = "CONSENT" in body_upper
                questions.append(current)
                continue
        if current is None:
            continue
        code_match = CODE_RE.match(line)
        if code_match and len(code_match.group(2).split()) <= 12:
            current.codes[code_match.group(1)] = code_match.group(2).strip()
            continue
        upper = line.upper()
        current.read_exactly = current.read_exactly or "READ EXACTLY" in upper or "ASK EXACTLY" in upper
        if "DO NOT READ" in upper:
            current.read_options = False
        elif "READ ALL OPTIONS" in upper or "READ OPTIONS" in upper:
            current.read_options = True
        current.probe = current.probe or "PROBE" in upper
        current.consent = current.consent or "CONSENT" in upper
        route_match = ROUTING_RE.search(line)
        if route_match:
            current.routing.append({"source": _clean_id(route_match.group(1)), "value": route_match.group(2).strip(), "target": _clean_id(route_match.group(3))})
        if len(line) < 180 and not any(token in upper for token in ("INTERVIEWER:", "PROGRAMMER:", "SHOW CARD")):
            current.text = f"{current.text} {line}".strip()

    ids = {question.question_id for question in questions}
    for question in questions:
        candidate = f"{question.question_id}A"
        if question.question_id.endswith("A"):
            base = question.question_id[:-1]
            if base in ids:
                for parent in questions:
                    if parent.question_id == base:
                        parent.reason_variable = question.question_id
                        break
        elif candidate in ids:
            question.reason_variable = candidate
    return questions

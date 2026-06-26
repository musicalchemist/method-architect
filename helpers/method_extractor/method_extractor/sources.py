from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


@dataclass
class SourcePage:
    page_number: int
    text: str


@dataclass
class SourceDocument:
    input_ref: str
    source_id: str
    source_type: str
    stored_path: str | None
    title_hint: str | None
    text: str
    pages: list[SourcePage] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def metadata_dict(self) -> dict[str, Any]:
        return {
            "input_ref": self.input_ref,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "stored_path": self.stored_path,
            "title_hint": self.title_hint,
            "text_characters": len(self.text),
            "page_count": len(self.pages),
            "warnings": self.warnings,
            "metadata": self.metadata,
        }


class _HTMLTextExtractor(HTMLParser):
    BLOCK_TAGS = {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "div",
        "figcaption",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "main",
        "p",
        "pre",
        "section",
        "table",
        "td",
        "th",
        "tr",
        "ul",
    }
    SKIP_TAGS = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._title_parts: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    @property
    def text(self) -> str:
        joined = "".join(self._parts)
        joined = html.unescape(joined)
        joined = re.sub(r"[ \t\r\f\v]+", " ", joined)
        joined = re.sub(r"\n{3,}", "\n\n", joined)
        joined = re.sub(r" *\n *", "\n", joined)
        return joined.strip()

    @property
    def title(self) -> str | None:
        title = " ".join(part.strip() for part in self._title_parts if part.strip())
        return re.sub(r"\s+", " ", title).strip() or None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag in self.BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False
        if tag in self.BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)
        if self._skip_depth or self._in_title:
            return
        if data.strip():
            self._parts.append(data)
            self._parts.append(" ")


def load_source(input_ref: str, source_dir: Path) -> SourceDocument:
    source_dir.mkdir(parents=True, exist_ok=True)
    if _is_url(input_ref):
        return _load_url(input_ref, source_dir)
    return _load_local_file(Path(input_ref), source_dir)


def write_source_artifacts(document: SourceDocument, sections: list[dict[str, Any]], source_dir: Path) -> None:
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "source.txt").write_text(document.text, encoding="utf-8")
    (source_dir / "source_metadata.json").write_text(
        json.dumps(document.metadata_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (source_dir / "sections.json").write_text(
        json.dumps(sections, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def sectionize_text(text: str) -> list[dict[str, Any]]:
    if not text.strip():
        return []

    lines = text.splitlines(keepends=True)
    sections: list[dict[str, Any]] = []
    current_heading = "Document Text"
    current_start = 0
    current_parts: list[str] = []
    offset = 0

    for line in lines:
        detected = _detect_heading(line)
        if detected and current_parts:
            sections.append(_make_section(current_heading, current_start, offset, "".join(current_parts)))
            current_heading = detected
            current_start = offset
            current_parts = []
        elif detected:
            current_heading = detected
            current_start = offset
            current_parts = []
        else:
            current_parts.append(line)
        offset += len(line)

    if current_parts:
        sections.append(_make_section(current_heading, current_start, offset, "".join(current_parts)))

    if not sections:
        sections.append(_make_section("Document Text", 0, len(text), text))

    return sections


def _load_local_file(path: Path, source_dir: Path) -> SourceDocument:
    if not path.exists():
        raise FileNotFoundError(f"Input file does not exist: {path}")

    suffix = path.suffix.lower()
    stored = source_dir / f"original{suffix or '.txt'}"
    if path.resolve() != stored.resolve():
        shutil.copy2(path, stored)

    if suffix == ".pdf":
        text, pages, warnings = _extract_pdf_text(stored)
        return SourceDocument(
            input_ref=str(path),
            source_id=path.stem,
            source_type="pdf",
            stored_path=str(stored),
            title_hint=path.stem,
            text=text,
            pages=pages,
            warnings=warnings,
            metadata={"filename": path.name},
        )

    raw = stored.read_bytes()
    if suffix in {".html", ".htm"}:
        text, title = _extract_html_text(raw, "utf-8")
        return SourceDocument(
            input_ref=str(path),
            source_id=path.stem,
            source_type="html",
            stored_path=str(stored),
            title_hint=title or path.stem,
            text=text,
            metadata={"filename": path.name},
        )

    text = raw.decode("utf-8", errors="replace")
    return SourceDocument(
        input_ref=str(path),
        source_id=path.stem,
        source_type="text",
        stored_path=str(stored),
        title_hint=path.stem,
        text=text,
        metadata={"filename": path.name},
    )


def _load_url(url: str, source_dir: Path) -> SourceDocument:
    request = urllib.request.Request(url, headers={"User-Agent": "method-extractor/0.1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read()
        content_type = response.headers.get("content-type", "")
        encoding = response.headers.get_content_charset() or "utf-8"

    parsed = urllib.parse.urlparse(url)
    suffix = Path(parsed.path).suffix.lower()
    if not suffix:
        suffix = ".pdf" if "pdf" in content_type else ".html"

    stored = source_dir / f"original{suffix}"
    stored.write_bytes(data)

    if suffix == ".pdf" or "pdf" in content_type:
        text, pages, warnings = _extract_pdf_text(stored)
        return SourceDocument(
            input_ref=url,
            source_id=_source_id_from_url(url),
            source_type="pdf_url",
            stored_path=str(stored),
            title_hint=Path(parsed.path).stem or parsed.netloc,
            text=text,
            pages=pages,
            warnings=warnings,
            metadata={"url": url, "content_type": content_type},
        )

    text, title = _extract_html_text(data, encoding)
    return SourceDocument(
        input_ref=url,
        source_id=_source_id_from_url(url),
        source_type="html_url",
        stored_path=str(stored),
        title_hint=title or parsed.netloc,
        text=text,
        metadata={"url": url, "content_type": content_type},
    )


def _extract_pdf_text(path: Path) -> tuple[str, list[SourcePage], list[str]]:
    warnings: list[str] = []
    pdftotext = shutil.which("pdftotext")
    if pdftotext:
        try:
            result = subprocess.run(
                [pdftotext, "-layout", str(path), "-"],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
            pages = [
                SourcePage(page_number=index + 1, text=page.strip())
                for index, page in enumerate(result.stdout.split("\f"))
                if page.strip()
            ]
            return result.stdout.strip(), pages, warnings
        except (subprocess.SubprocessError, OSError) as exc:
            warnings.append(f"pdftotext extraction failed: {exc}")

    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        warnings.append("PDF text extraction requires pdftotext or the optional pypdf dependency.")
        return "", [], warnings

    try:
        reader = PdfReader(str(path))
        pages = []
        for index, page in enumerate(reader.pages):
            pages.append(SourcePage(page_number=index + 1, text=(page.extract_text() or "").strip()))
        text = "\n\n".join(page.text for page in pages if page.text)
        return text, pages, warnings
    except Exception as exc:  # pypdf raises several parser-specific exceptions.
        warnings.append(f"pypdf extraction failed: {exc}")
        return "", [], warnings


def _extract_html_text(data: bytes, encoding: str) -> tuple[str, str | None]:
    parser = _HTMLTextExtractor()
    parser.feed(data.decode(encoding, errors="replace"))
    return parser.text, parser.title


KNOWN_HEADINGS = {
    "abstract",
    "introduction",
    "background",
    "related work",
    "methods",
    "method",
    "materials and methods",
    "materials & methods",
    "experimental methods",
    "experimental setup",
    "experiments",
    "data",
    "datasets",
    "dataset",
    "statistical analysis",
    "evaluation",
    "results",
    "discussion",
    "limitations",
    "conclusion",
    "conclusions",
    "data availability",
    "code availability",
    "supplementary information",
}

METHOD_SECTION_KEYWORDS = (
    "method",
    "material",
    "experiment",
    "data",
    "dataset",
    "statistical",
    "analysis",
    "evaluation",
    "training",
    "validation",
    "supplement",
)


def _detect_heading(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or len(stripped) > 120:
        return None
    normalized = re.sub(r"^\d+(\.\d+)*\s+", "", stripped)
    normalized = normalized.strip(" .:\t").lower()
    if normalized in KNOWN_HEADINGS:
        return stripped.strip(" .:")
    if 3 <= len(stripped) <= 80 and stripped.isupper() and any(char.isalpha() for char in stripped):
        return stripped.title().strip(" .:")
    return None


def _make_section(heading: str, start: int, end: int, body: str) -> dict[str, Any]:
    preview = re.sub(r"\s+", " ", body).strip()
    candidate_text = f"{heading} {preview[:2000]}".lower()
    is_method_candidate = any(keyword in candidate_text for keyword in METHOD_SECTION_KEYWORDS)
    return {
        "heading": heading,
        "start_char": start,
        "end_char": end,
        "char_count": max(0, end - start),
        "method_candidate": is_method_candidate,
        "preview": preview[:1200],
    }


def _is_url(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme in {"http", "https"}


def _source_id_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    path_part = Path(parsed.path).stem or parsed.netloc
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", path_part).strip("-")
    return safe or "web-source"

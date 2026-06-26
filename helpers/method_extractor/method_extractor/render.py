from __future__ import annotations

from typing import Any

from .schema import STATUS_VALUES, iter_fields


def render_report(blueprint: dict[str, Any], audit: dict[str, Any], sections: list[dict[str, Any]]) -> str:
    paper = blueprint.get("paper", {})
    source = blueprint.get("source", {})
    lines = [
        "# Method Blueprint Report",
        "",
        f"- Paper ID: `{paper.get('paper_id') or 'unset'}`",
        f"- Title hint: {paper.get('title_hint') or 'unset'}",
        f"- Domain profile: `{paper.get('domain_profile') or 'unset'}`",
        f"- Input: `{paper.get('input_ref') or source.get('input_ref') or 'unset'}`",
        f"- Source type: `{source.get('source_type') or 'unknown'}`",
        f"- Extracted text characters: `{source.get('text_characters', 0)}`",
        "",
        "## Status Counts",
        "",
    ]

    counts = audit.get("summary", {}).get("status_counts", {})
    for status in STATUS_VALUES:
        lines.append(f"- `{status}`: {counts.get(status, 0)}")

    lines.extend(["", "## Blueprint Fields", ""])
    for section in blueprint.get("sections", []):
        lines.extend([f"### {section.get('label', section.get('key', 'Section'))}", ""])
        lines.extend(["| Field | Status | Value | Evidence | Notes |", "| --- | --- | --- | ---: | --- |"])
        for field in section.get("fields", []):
            value = _shorten(_stringify_value(field.get("value")), 90)
            notes = _shorten(str(field.get("reviewer_notes") or ""), 70)
            evidence_count = len(field.get("evidence") or [])
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_table(field.get("label") or field.get("key") or ""),
                        f"`{_escape_table(field.get('status') or '')}`",
                        _escape_table(value or ""),
                        str(evidence_count),
                        _escape_table(notes),
                    ]
                )
                + " |"
            )
        lines.append("")

    lines.extend(["## Audit Findings", ""])
    findings = audit.get("findings", [])
    if not findings:
        lines.append("No audit findings.")
    else:
        for finding in findings[:80]:
            field = finding.get("field")
            prefix = f"- `{finding.get('severity')}` `{finding.get('code')}`"
            if field:
                prefix += f" `{field}`"
            lines.append(f"{prefix}: {finding.get('message')}")
        if len(findings) > 80:
            lines.append(f"- ... {len(findings) - 80} additional findings omitted from report.")

    candidate_sections = [section for section in sections if section.get("method_candidate")]
    if not candidate_sections:
        candidate_sections = sections[:8]

    lines.extend(["", "## Source Section Candidates", ""])
    if not candidate_sections:
        lines.append("No source text was extracted.")
    else:
        for index, section in enumerate(candidate_sections[:12], start=1):
            lines.extend(
                [
                    f"### {index}. {section.get('heading', 'Untitled Section')}",
                    "",
                    f"- Characters: `{section.get('start_char')}` to `{section.get('end_char')}`",
                    f"- Method candidate: `{section.get('method_candidate')}`",
                    "",
                    "> " + _blockquote(_shorten(section.get("preview") or "", 900)),
                    "",
                ]
            )

    return "\n".join(lines).rstrip() + "\n"


def render_annotation_worksheet(blueprint: dict[str, Any], sections: list[dict[str, Any]]) -> str:
    paper = blueprint.get("paper", {})
    lines = [
        "# Method Blueprint Annotation Worksheet",
        "",
        f"Paper: {paper.get('title_hint') or paper.get('paper_id') or 'unset'}",
        f"Domain profile: `{paper.get('domain_profile') or 'unset'}`",
        "",
        "Use this worksheet while reading the paper, then transfer the structured result into `blueprint.json`.",
        "",
        "For each methodological claim, capture:",
        "",
        "- `value`: the extracted methodological content",
        "- `status`: reported, inferred, unclear, contradictory, or not_reported",
        "- `evidence`: page, section, and exact supporting passage",
        "- `reviewer_notes`: uncertainty, caveats, or interpretation",
        "",
        "## Fields",
        "",
    ]

    for section in blueprint.get("sections", []):
        lines.extend([f"### {section.get('label', section.get('key', 'Section'))}", ""])
        for field in section.get("fields", []):
            required = "required" if field.get("required_for_review") else "optional"
            lines.extend(
                [
                    f"#### {field.get('label', field.get('key'))}",
                    "",
                    f"- Key: `{field.get('key')}`",
                    f"- Review priority: `{required}`",
                    f"- Prompt: {field.get('prompt')}",
                    "- Status:",
                    "- Value:",
                    "- Evidence:",
                    "- Notes:",
                    "",
                ]
            )

    method_sections = [section for section in sections if section.get("method_candidate")]
    if method_sections:
        lines.extend(["## Method-Like Source Sections", ""])
        for section in method_sections[:12]:
            lines.extend(
                [
                    f"### {section.get('heading')}",
                    "",
                    "> " + _blockquote(_shorten(section.get("preview") or "", 900)),
                    "",
                ]
            )

    return "\n".join(lines).rstrip() + "\n"


def _stringify_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return repr(value)


def _shorten(value: str, limit: int) -> str:
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _blockquote(value: str) -> str:
    return value.replace("\n", "\n> ")

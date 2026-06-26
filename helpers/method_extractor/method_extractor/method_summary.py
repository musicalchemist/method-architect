from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .schema import iter_fields


def compact_blueprint_for_summary(blueprint: dict[str, Any]) -> dict[str, Any]:
    paper = blueprint.get("paper", {})
    compact_sections: list[dict[str, Any]] = []

    for section in blueprint.get("sections", []):
        compact_fields: list[dict[str, Any]] = []
        for field in section.get("fields", []):
            compact_fields.append(
                {
                    "key": field.get("key", ""),
                    "label": field.get("label", ""),
                    "value": field.get("value") or "",
                    "status": field.get("status", ""),
                    "reviewer_notes": field.get("reviewer_notes") or "",
                    "evidence_count": len(field.get("evidence") or []),
                    "llm_confidence": field.get("llm_confidence"),
                }
            )
        compact_sections.append(
            {
                "key": section.get("key", ""),
                "label": section.get("label", ""),
                "fields": compact_fields,
            }
        )

    return {
        "paper": {
            "paper_id": paper.get("paper_id", ""),
            "title_hint": paper.get("title_hint", ""),
            "domain_profile": paper.get("domain_profile", ""),
            "input_ref": paper.get("input_ref", ""),
        },
        "run": blueprint.get("run", {}),
        "sections": compact_sections,
        "missing_required_fields": [
            {
                "section_key": section.get("key", ""),
                "field_key": field.get("key", ""),
                "label": field.get("label", ""),
                "notes": field.get("reviewer_notes") or "",
            }
            for section, field in iter_fields(blueprint)
            if field.get("required_for_review") is True and field.get("status") == "not_reported"
        ],
    }


def attach_summary_metadata(
    summary: dict[str, Any],
    *,
    blueprint: dict[str, Any],
    model: str,
    source: str,
) -> dict[str, Any]:
    paper = blueprint.get("paper", {})
    result = {key: value for key, value in summary.items() if key != "_request_metadata"}
    result["schema_version"] = "0.1.0"
    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    result["source"] = {
        "type": source,
        "blueprint_schema_version": blueprint.get("schema_version"),
        "paper_id": paper.get("paper_id", ""),
        "title_hint": paper.get("title_hint", ""),
        "domain_profile": paper.get("domain_profile", ""),
        "model": model,
    }
    return result


def render_method_summary(summary: dict[str, Any]) -> str:
    paper = summary.get("paper", {})
    lines = [
        "# Method Summary",
        "",
        f"- Title: {paper.get('title') or paper.get('title_hint') or 'unset'}",
        f"- Paper ID: `{paper.get('paper_id') or 'unset'}`",
        f"- Domain: `{paper.get('domain') or paper.get('domain_profile') or 'unset'}`",
        f"- Summary model: `{summary.get('source', {}).get('model') or 'unset'}`",
        "",
        "## Method Theme",
        "",
        summary.get("method_theme") or "",
        "",
        "## Design Pattern",
        "",
        summary.get("design_pattern") or "",
    ]

    tags = summary.get("design_pattern_tags") or []
    if tags:
        lines.extend(["", "Pattern tags: " + ", ".join(f"`{tag}`" for tag in tags)])

    lines.extend(
        [
            "",
            "## Research And Experiment Shape",
            "",
            f"- Research goal: {summary.get('research_goal') or ''}",
            f"- Experimental unit: {summary.get('experimental_unit') or ''}",
            f"- Data strategy: {summary.get('data_strategy') or ''}",
            f"- Comparison strategy: {summary.get('comparison_strategy') or ''}",
            f"- Validation strategy: {summary.get('validation_strategy') or ''}",
            f"- Evaluation strategy: {summary.get('evaluation_strategy') or ''}",
            f"- Statistical strategy: {summary.get('statistical_strategy') or ''}",
            f"- Robustness strategy: {summary.get('robustness_strategy') or ''}",
            "",
        ]
    )

    _append_list(lines, "Key Methods", summary.get("key_methods") or [])
    _append_list(lines, "Key Metrics", summary.get("key_metrics") or [])
    _append_reusable_ideas(lines, summary.get("reusable_method_ideas") or [])
    _append_experiments(lines, summary.get("experiments") or [])
    _append_list(lines, "Important Limitations", summary.get("important_limitations") or [])
    _append_list(lines, "Missing Or Unclear", summary.get("missing_or_unclear") or [])
    _append_list(lines, "Other Important Details", summary.get("other_important_details") or [])

    confidence_notes = summary.get("confidence_notes")
    if confidence_notes:
        lines.extend(["## Confidence Notes", "", confidence_notes, ""])

    warnings = summary.get("warnings") or []
    if warnings:
        _append_list(lines, "Summary Warnings", warnings)

    return "\n".join(lines).rstrip() + "\n"


def method_summary_csv_row(summary: dict[str, Any], run_name: str) -> dict[str, Any]:
    paper = summary.get("paper", {})
    return {
        "run_name": run_name,
        "paper_id": paper.get("paper_id", ""),
        "title": paper.get("title", "") or paper.get("title_hint", ""),
        "domain": paper.get("domain", "") or paper.get("domain_profile", ""),
        "method_theme": summary.get("method_theme", ""),
        "design_pattern": summary.get("design_pattern", ""),
        "design_pattern_tags": "; ".join(summary.get("design_pattern_tags") or []),
        "experimental_unit": summary.get("experimental_unit", ""),
        "data_strategy": summary.get("data_strategy", ""),
        "validation_strategy": summary.get("validation_strategy", ""),
        "evaluation_strategy": summary.get("evaluation_strategy", ""),
        "statistical_strategy": summary.get("statistical_strategy", ""),
        "robustness_strategy": summary.get("robustness_strategy", ""),
        "key_methods": "; ".join(summary.get("key_methods") or []),
        "key_metrics": "; ".join(summary.get("key_metrics") or []),
        "important_limitations": "; ".join(summary.get("important_limitations") or []),
        "missing_or_unclear": "; ".join(summary.get("missing_or_unclear") or []),
    }


def _append_list(lines: list[str], title: str, items: list[Any]) -> None:
    lines.extend([f"## {title}", ""])
    if not items:
        lines.extend(["None recorded.", ""])
        return
    for item in items:
        lines.append(f"- {_stringify(item)}")
    lines.append("")


def _append_reusable_ideas(lines: list[str], ideas: list[dict[str, Any]]) -> None:
    lines.extend(["## Reusable Method Ideas", ""])
    if not ideas:
        lines.extend(["None recorded.", ""])
        return
    for idea in ideas:
        lines.extend(
            [
                f"### {idea.get('idea') or 'Untitled idea'}",
                "",
                f"- Why it matters: {idea.get('why_it_matters') or ''}",
                f"- Reusable pattern: {idea.get('reusable_pattern') or ''}",
                f"- Supporting blueprint fields: {', '.join(idea.get('supporting_blueprint_fields') or [])}",
                "",
            ]
        )


def _append_experiments(lines: list[str], experiments: list[dict[str, Any]]) -> None:
    lines.extend(["## Experiments", ""])
    if not experiments:
        lines.extend(["No distinct experiments summarized.", ""])
        return
    for experiment in experiments:
        lines.extend(
            [
                f"### {experiment.get('name') or 'Unnamed experiment'}",
                "",
                f"- Purpose: {experiment.get('purpose') or ''}",
                f"- Data: {experiment.get('data') or ''}",
                f"- Method: {experiment.get('method') or ''}",
                f"- Comparison: {experiment.get('comparison') or ''}",
                f"- Evaluation: {experiment.get('evaluation') or ''}",
                f"- Finding type: {experiment.get('finding_type') or ''}",
                "",
            ]
        )


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


INDEX_FILENAME = "index.jsonl"
METHOD_SUMMARIES_FILENAME = "method_summaries.jsonl"


def append_run_index(
    *,
    runs_dir: Path,
    run_dir: Path,
    blueprint: dict[str, Any],
    audit: dict[str, Any],
    llm_requested: bool,
    llm_succeeded: bool,
) -> dict[str, Any]:
    runs_dir.mkdir(parents=True, exist_ok=True)
    record = make_index_record(
        run_dir=run_dir,
        blueprint=blueprint,
        audit=audit,
        llm_requested=llm_requested,
        llm_succeeded=llm_succeeded,
    )
    with (runs_dir / INDEX_FILENAME).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def make_index_record(
    *,
    run_dir: Path,
    blueprint: dict[str, Any],
    audit: dict[str, Any],
    llm_requested: bool,
    llm_succeeded: bool,
) -> dict[str, Any]:
    paper = blueprint.get("paper", {})
    source = blueprint.get("source", {})
    run = blueprint.get("run", {})
    return {
        "indexed_at": datetime.now(timezone.utc).isoformat(),
        "run_name": run_dir.name,
        "run_path": str(run_dir),
        "paper_id": paper.get("paper_id", ""),
        "title_hint": paper.get("title_hint", ""),
        "domain_profile": paper.get("domain_profile", ""),
        "input_ref": paper.get("input_ref", ""),
        "source_type": source.get("source_type", ""),
        "stored_path": source.get("stored_path", ""),
        "tool_mode": run.get("mode", ""),
        "llm_requested": llm_requested,
        "llm_succeeded": llm_succeeded,
        "llm_model": run.get("llm", {}).get("model", ""),
        "llm_source_input_kind": run.get("llm", {}).get("source_input_kind", ""),
        "valid": audit.get("valid"),
        "total_fields": audit.get("summary", {}).get("total_fields"),
        "status_counts": audit.get("summary", {}).get("status_counts", {}),
    }


def read_run_index(runs_dir: Path) -> list[dict[str, Any]]:
    index_path = runs_dir / INDEX_FILENAME
    if not index_path.exists():
        return []

    records: list[dict[str, Any]] = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(json.loads(line))
    return records


def search_run_index(runs_dir: Path, query: str | None = None) -> list[dict[str, Any]]:
    records = read_run_index(runs_dir)
    if not query:
        return records

    needle = query.lower()
    return [
        record
        for record in records
        if needle in str(record.get("paper_id", "")).lower()
        or needle in str(record.get("title_hint", "")).lower()
        or needle in str(record.get("input_ref", "")).lower()
        or needle in str(record.get("run_name", "")).lower()
    ]


def append_method_summary_index(
    *,
    runs_dir: Path,
    run_dir: Path,
    summary: dict[str, Any],
) -> dict[str, Any]:
    runs_dir.mkdir(parents=True, exist_ok=True)
    record = make_method_summary_index_record(run_dir=run_dir, summary=summary)
    with (runs_dir / METHOD_SUMMARIES_FILENAME).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def make_method_summary_index_record(*, run_dir: Path, summary: dict[str, Any]) -> dict[str, Any]:
    paper = summary.get("paper", {})
    return {
        "indexed_at": datetime.now(timezone.utc).isoformat(),
        "run_name": run_dir.name,
        "run_path": str(run_dir),
        "paper_id": paper.get("paper_id", ""),
        "title": paper.get("title", ""),
        "domain": paper.get("domain", ""),
        "method_theme": summary.get("method_theme", ""),
        "design_pattern": summary.get("design_pattern", ""),
        "design_pattern_tags": summary.get("design_pattern_tags", []),
        "experimental_unit": summary.get("experimental_unit", ""),
        "data_strategy": summary.get("data_strategy", ""),
        "validation_strategy": summary.get("validation_strategy", ""),
        "evaluation_strategy": summary.get("evaluation_strategy", ""),
        "statistical_strategy": summary.get("statistical_strategy", ""),
        "robustness_strategy": summary.get("robustness_strategy", ""),
        "key_methods": summary.get("key_methods", []),
        "key_metrics": summary.get("key_metrics", []),
        "reusable_method_ideas": [
            item.get("reusable_pattern") or item.get("idea") or ""
            for item in summary.get("reusable_method_ideas", [])
            if isinstance(item, dict)
        ],
        "important_limitations": summary.get("important_limitations", []),
        "missing_or_unclear": summary.get("missing_or_unclear", []),
    }

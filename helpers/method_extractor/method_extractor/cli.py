from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .llm import (
    DEFAULT_API_KEY_ENV,
    DEFAULT_MODEL,
    LLMExtractionError,
    apply_llm_extraction,
    extract_blueprint_fields_with_openai,
    summarize_blueprint_with_openai,
)
from .method_summary import attach_summary_metadata, compact_blueprint_for_summary, render_method_summary
from .run_index import append_method_summary_index, append_run_index, search_run_index
from .schema import DOMAIN_PROFILES, audit_blueprint, field_specs_as_dict, make_blueprint, validate_blueprint
from .sources import load_source, sectionize_text, write_source_artifacts
from .render import render_annotation_worksheet, render_report


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="method-extractor",
        description="Create and validate evidence-grounded Method Blueprint workspaces.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract = subparsers.add_parser("extract", help="Create a paper workspace from a PDF, URL, HTML, or text file.")
    extract.add_argument("input", help="Local paper path or HTTP(S) URL.")
    extract.add_argument("--domain", choices=DOMAIN_PROFILES, default="general", help="Methodology profile to include.")
    extract.add_argument("--out", default="runs", help="Directory where run workspaces are created.")
    extract.add_argument("--paper-id", default=None, help="Stable paper identifier or short slug.")
    extract.add_argument("--title", default=None, help="Optional human-readable title hint.")
    extract.add_argument("--llm", action="store_true", help="Use OpenAI to draft-fill blueprint.json.")
    extract.add_argument("--model", default=DEFAULT_MODEL, help="OpenAI model for --llm.")
    extract.add_argument("--summarize", action="store_true", help="After LLM extraction, create method_summary.json and method_summary.md.")
    extract.add_argument("--summary-model", default=None, help="OpenAI model for --summarize. Defaults to --model.")
    extract.add_argument("--api-key-env", default=DEFAULT_API_KEY_ENV, help="Environment variable containing the OpenAI API key.")
    extract.add_argument("--max-chars", type=int, default=60000, help="Maximum source characters to send to the LLM.")
    extract.add_argument(
        "--pdf-input",
        choices=("auto", "direct", "text"),
        default="auto",
        help="For PDF + --llm: send the PDF directly to OpenAI, force text extraction, or auto-select direct PDF input.",
    )
    extract.set_defaults(func=cmd_extract)

    llm_fill = subparsers.add_parser("llm-fill", help="Create an OpenAI-filled draft for an existing run directory.")
    llm_fill.add_argument("path", help="Run directory containing blueprint.json and source/source.txt.")
    llm_fill.add_argument("--model", default=DEFAULT_MODEL, help="OpenAI model to use.")
    llm_fill.add_argument("--api-key-env", default=DEFAULT_API_KEY_ENV, help="Environment variable containing the OpenAI API key.")
    llm_fill.add_argument("--max-chars", type=int, default=60000, help="Maximum source characters to send to the LLM.")
    llm_fill.add_argument(
        "--pdf-input",
        choices=("auto", "direct", "text"),
        default="auto",
        help="For PDF runs: send the PDF directly to OpenAI, force source text, or auto-select direct PDF input.",
    )
    llm_fill.add_argument("--apply", action="store_true", help="Replace blueprint.json/report.md with the LLM draft.")
    llm_fill.set_defaults(func=cmd_llm_fill)

    summarize = subparsers.add_parser("summarize", help="Create a compact Method Summary from an existing blueprint.")
    summarize.add_argument("path", help="Run directory containing blueprint.json, or a blueprint JSON file.")
    summarize.add_argument("--model", default=DEFAULT_MODEL, help="OpenAI model to use.")
    summarize.add_argument("--api-key-env", default=DEFAULT_API_KEY_ENV, help="Environment variable containing the OpenAI API key.")
    summarize.set_defaults(func=cmd_summarize)

    index = subparsers.add_parser("index", help="List indexed extraction runs.")
    index.add_argument("--runs", default="runs", help="Runs directory containing index.jsonl.")
    index.add_argument("--query", default=None, help="Filter by paper ID, title, input, or run name.")
    index.set_defaults(func=cmd_index)

    validate = subparsers.add_parser("validate", help="Validate a blueprint JSON file or run directory.")
    validate.add_argument("path", help="Path to blueprint.json or a run directory containing it.")
    validate.set_defaults(func=cmd_validate)

    render = subparsers.add_parser("render", help="Regenerate report.md and annotation_worksheet.md for a run directory.")
    render.add_argument("path", help="Path to blueprint.json or a run directory containing it.")
    render.set_defaults(func=cmd_render)

    schema = subparsers.add_parser("schema", help="Print the field schema for a domain profile.")
    schema.add_argument("--domain", choices=DOMAIN_PROFILES, default="general")
    schema.set_defaults(func=cmd_schema)

    return parser


def cmd_extract(args: argparse.Namespace) -> int:
    if args.summarize and not args.llm:
        raise SystemExit("--summarize requires --llm during extract. Use the standalone summarize command for existing blueprints.")

    out_base = Path(args.out)
    title_hint = args.title
    paper_id = args.paper_id
    slug = _slugify(paper_id or title_hint or _input_name(args.input))
    run_dir = _new_run_dir(out_base, slug)
    source_dir = run_dir / "source"

    _progress("Loading source")
    document = load_source(args.input, source_dir)
    if not title_hint:
        title_hint = document.title_hint
    if not paper_id:
        paper_id = document.source_id

    _progress("Indexing source text")
    sections = sectionize_text(document.text)
    write_source_artifacts(document, sections, source_dir)

    _progress("Creating blueprint template")
    blueprint = make_blueprint(
        input_ref=args.input,
        domain=args.domain,
        paper_id=paper_id,
        title_hint=title_hint,
        source_metadata=document.metadata_dict(),
    )
    if args.llm:
        _write_json(run_dir / "blueprint.template.json", blueprint)
        try:
            _progress("Calling OpenAI for detailed blueprint extraction")
            blueprint = _run_llm_extraction(
                blueprint=blueprint,
                run_dir=run_dir,
                sections=sections,
                model=args.model,
                api_key_env=args.api_key_env,
                max_chars=args.max_chars,
                pdf_input=args.pdf_input,
            )
        except LLMExtractionError as exc:
            _write_json(run_dir / "blueprint.json", blueprint)
            audit = audit_blueprint(blueprint)
            _write_json(run_dir / "audit.json", audit)
            (run_dir / "report.md").write_text(render_report(blueprint, audit, sections), encoding="utf-8")
            append_run_index(
                runs_dir=out_base,
                run_dir=run_dir,
                blueprint=blueprint,
                audit=audit,
                llm_requested=True,
                llm_succeeded=False,
            )
            print(f"Created Method Blueprint workspace without LLM draft: {run_dir}")
            print(f"LLM extraction failed: {exc}")
            return 2

    audit = audit_blueprint(blueprint)

    _progress("Writing blueprint report")
    _write_json(run_dir / "blueprint.json", blueprint)
    _write_json(run_dir / "audit.json", audit)
    (run_dir / "report.md").write_text(render_report(blueprint, audit, sections), encoding="utf-8")
    (run_dir / "annotation_worksheet.md").write_text(
        render_annotation_worksheet(blueprint, sections),
        encoding="utf-8",
    )
    append_run_index(
        runs_dir=out_base,
        run_dir=run_dir,
        blueprint=blueprint,
        audit=audit,
        llm_requested=args.llm,
        llm_succeeded=bool(args.llm),
    )

    if args.summarize:
        try:
            _progress("Calling OpenAI for condensed method summary")
            summary = _run_method_summary(
                blueprint=blueprint,
                run_dir=run_dir,
                model=args.summary_model or args.model,
                api_key_env=args.api_key_env,
            )
            _progress(f"Wrote method summary: {run_dir / 'method_summary.md'}")
        except LLMExtractionError as exc:
            print(f"Method summary failed: {exc}")
            return 3

    print(f"Created Method Blueprint workspace: {run_dir}")
    print(f"Blueprint: {run_dir / 'blueprint.json'}")
    print(f"Report: {run_dir / 'report.md'}")
    if args.llm:
        print(f"LLM draft metadata: {run_dir / 'llm_extraction.json'}")
    if args.summarize:
        print(f"Method summary: {run_dir / 'method_summary.md'}")
    if document.warnings:
        print("Warnings:")
        for warning in document.warnings:
            print(f"- {warning}")
    return 0


def cmd_summarize(args: argparse.Namespace) -> int:
    blueprint_path = _resolve_blueprint_path(Path(args.path))
    if not blueprint_path.exists():
        raise SystemExit(f"Missing blueprint: {blueprint_path}")
    run_dir = blueprint_path.parent
    blueprint = _read_json(blueprint_path)

    try:
        _progress("Calling OpenAI for condensed method summary")
        _run_method_summary(
            blueprint=blueprint,
            run_dir=run_dir,
            model=args.model,
            api_key_env=args.api_key_env,
        )
    except LLMExtractionError as exc:
        print(f"Method summary failed: {exc}")
        return 3

    print(f"Method summary: {run_dir / 'method_summary.md'}")
    print(f"Method summary JSON: {run_dir / 'method_summary.json'}")
    return 0


def cmd_llm_fill(args: argparse.Namespace) -> int:
    run_dir = Path(args.path)
    if not run_dir.is_dir():
        raise SystemExit(f"Expected run directory, got: {run_dir}")

    blueprint_path = run_dir / "blueprint.json"
    source_path = run_dir / "source" / "source.txt"
    sections_path = run_dir / "source" / "sections.json"
    if not blueprint_path.exists():
        raise SystemExit(f"Missing blueprint: {blueprint_path}")
    if not source_path.exists():
        raise SystemExit(f"Missing source text: {source_path}")

    blueprint = _read_json(blueprint_path)
    sections = _read_json(sections_path) if sections_path.exists() else []
    try:
        draft = _run_llm_extraction(
            blueprint=blueprint,
            run_dir=run_dir,
            sections=sections,
            model=args.model,
            api_key_env=args.api_key_env,
            max_chars=args.max_chars,
            pdf_input=args.pdf_input,
        )
    except LLMExtractionError as exc:
        print(f"LLM extraction failed: {exc}")
        return 2
    audit = audit_blueprint(draft)

    if args.apply:
        _write_json(run_dir / "blueprint.before-llm.json", blueprint)
        _write_json(run_dir / "blueprint.json", draft)
        _write_json(run_dir / "audit.json", audit)
        (run_dir / "report.md").write_text(render_report(draft, audit, sections), encoding="utf-8")
        (run_dir / "annotation_worksheet.md").write_text(render_annotation_worksheet(draft, sections), encoding="utf-8")
        append_run_index(
            runs_dir=run_dir.parent,
            run_dir=run_dir,
            blueprint=draft,
            audit=audit,
            llm_requested=True,
            llm_succeeded=True,
        )
        print(f"Applied LLM draft to: {blueprint_path}")
    else:
        _write_json(run_dir / "blueprint.llm.json", draft)
        _write_json(run_dir / "audit.llm.json", audit)
        (run_dir / "report.llm.md").write_text(render_report(draft, audit, sections), encoding="utf-8")
        print(f"Wrote LLM draft without replacing blueprint.json: {run_dir / 'blueprint.llm.json'}")
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    records = search_run_index(Path(args.runs), args.query)
    if not records:
        print("No indexed runs found.")
        return 0

    for record in records:
        paper_id = record.get("paper_id") or "unset"
        title = record.get("title_hint") or "untitled"
        domain = record.get("domain_profile") or "unknown"
        if record.get("llm_succeeded"):
            llm = "llm"
        elif record.get("llm_requested"):
            llm = "llm_failed"
        else:
            llm = "manual"
        print(f"{record.get('run_name')} | {paper_id} | {domain} | {llm} | {title}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    blueprint_path = _resolve_blueprint_path(Path(args.path))
    blueprint = _read_json(blueprint_path)
    validation = validate_blueprint(blueprint)
    audit = audit_blueprint(blueprint)

    print(f"Blueprint: {blueprint_path}")
    print(f"Valid: {validation['valid']}")
    print(f"Errors: {len(validation['errors'])}")
    print(f"Warnings: {len(validation['warnings'])}")
    print("Status counts:")
    for status, count in audit["summary"]["status_counts"].items():
        print(f"- {status}: {count}")

    for error in validation["errors"]:
        print(f"ERROR {error.get('code')}: {error.get('message')}")
    for warning in validation["warnings"][:40]:
        print(f"WARN {warning.get('code')}: {warning.get('message')}")
    if len(validation["warnings"]) > 40:
        print(f"... {len(validation['warnings']) - 40} additional warnings omitted.")

    return 0 if validation["valid"] else 1


def cmd_render(args: argparse.Namespace) -> int:
    blueprint_path = _resolve_blueprint_path(Path(args.path))
    run_dir = blueprint_path.parent
    blueprint = _read_json(blueprint_path)
    sections_path = run_dir / "source" / "sections.json"
    sections = _read_json(sections_path) if sections_path.exists() else []
    audit = audit_blueprint(blueprint)

    _write_json(run_dir / "audit.json", audit)
    (run_dir / "report.md").write_text(render_report(blueprint, audit, sections), encoding="utf-8")
    (run_dir / "annotation_worksheet.md").write_text(
        render_annotation_worksheet(blueprint, sections),
        encoding="utf-8",
    )
    print(f"Rendered report and worksheet in: {run_dir}")
    return 0


def cmd_schema(args: argparse.Namespace) -> int:
    print(json.dumps(field_specs_as_dict(args.domain), indent=2))
    return 0


def _new_run_dir(base: Path, slug: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = base / f"{timestamp}-{slug}"
    suffix = 2
    while candidate.exists():
        candidate = base / f"{timestamp}-{slug}-{suffix}"
        suffix += 1
    candidate.mkdir(parents=True)
    return candidate


def _input_name(input_ref: str) -> str:
    path = Path(input_ref)
    if path.name:
        return path.stem or path.name
    return input_ref


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-").lower()
    return slug[:80] or "paper"


def _resolve_blueprint_path(path: Path) -> Path:
    if path.is_dir():
        return path / "blueprint.json"
    return path


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _progress(message: str) -> None:
    print(f"[method-extractor] {message}...")


def _run_llm_extraction(
    *,
    blueprint: dict[str, Any],
    run_dir: Path,
    sections: list[dict[str, Any]],
    model: str,
    api_key_env: str,
    max_chars: int,
    pdf_input: str,
) -> dict[str, Any]:
    source_text = (run_dir / "source" / "source.txt").read_text(encoding="utf-8")
    pdf_path = _direct_pdf_path_for_blueprint(blueprint, pdf_input)
    extraction, raw_response = extract_blueprint_fields_with_openai(
        blueprint=blueprint,
        source_text=source_text,
        sections=sections,
        pdf_path=pdf_path,
        model=model,
        api_key_env=api_key_env,
        max_chars=max_chars,
    )
    _write_json(run_dir / "llm_extraction.json", extraction)
    _write_json(run_dir / "llm_response.json", raw_response)
    return apply_llm_extraction(blueprint, extraction, model=model)


def _run_method_summary(
    *,
    blueprint: dict[str, Any],
    run_dir: Path,
    model: str,
    api_key_env: str,
) -> dict[str, Any]:
    compact = compact_blueprint_for_summary(blueprint)
    summary, raw_response = summarize_blueprint_with_openai(
        compact_blueprint=compact,
        model=model,
        api_key_env=api_key_env,
    )
    summary = attach_summary_metadata(summary, blueprint=blueprint, model=model, source="blueprint")
    _write_json(run_dir / "method_summary.json", summary)
    _write_json(run_dir / "method_summary_response.json", raw_response)
    (run_dir / "method_summary.md").write_text(render_method_summary(summary), encoding="utf-8")
    append_method_summary_index(runs_dir=run_dir.parent, run_dir=run_dir, summary=summary)
    return summary


def _direct_pdf_path_for_blueprint(blueprint: dict[str, Any], pdf_input: str) -> Path | None:
    if pdf_input == "text":
        return None

    source = blueprint.get("source", {})
    stored_path = source.get("stored_path")
    source_type = str(source.get("source_type", ""))
    if not stored_path or not source_type.startswith("pdf"):
        if pdf_input == "direct":
            raise LLMExtractionError("Direct PDF input was requested, but this run does not have a stored PDF source.")
        return None

    path = Path(stored_path)
    if not path.exists():
        if pdf_input == "direct":
            raise LLMExtractionError(f"Direct PDF input was requested, but the stored PDF is missing: {path}")
        return None
    return path

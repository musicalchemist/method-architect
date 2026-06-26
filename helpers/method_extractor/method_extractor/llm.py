from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schema import STATUS_VALUES, field_specs_as_dict, iter_fields


DEFAULT_API_KEY_ENV = "OPENAI_API_KEY_METHOD_ARCHITECT"
DEFAULT_MODEL = "gpt-4.1-mini"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
MAX_DIRECT_PDF_BYTES = 50 * 1024 * 1024


class LLMExtractionError(RuntimeError):
    """Raised when LLM extraction cannot produce a usable structured draft."""


def extract_blueprint_fields_with_openai(
    *,
    blueprint: dict[str, Any],
    source_text: str,
    sections: list[dict[str, Any]],
    pdf_path: Path | None = None,
    model: str = DEFAULT_MODEL,
    api_key_env: str = DEFAULT_API_KEY_ENV,
    max_chars: int = 60000,
    timeout_seconds: int = 120,
) -> tuple[dict[str, Any], dict[str, Any]]:
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise LLMExtractionError(f"Missing OpenAI API key environment variable: {api_key_env}")
    if pdf_path is None and not source_text.strip():
        raise LLMExtractionError("No source text is available for LLM extraction.")

    prepared = _prepare_source_text(source_text, max_chars)
    request_body = _build_responses_request(
        blueprint=blueprint,
        source_text=prepared["text"],
        sections=sections,
        pdf_path=pdf_path,
        model=model,
        max_chars=max_chars,
        was_truncated=prepared["was_truncated"],
    )
    response = _post_openai_response(api_key=api_key, body=request_body, timeout_seconds=timeout_seconds)
    output_text = _extract_output_text(response)

    try:
        extraction = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise LLMExtractionError(f"OpenAI response was not valid JSON: {exc}") from exc

    extraction["_request_metadata"] = {
        "model": model,
        "api_key_env": api_key_env,
        "source_characters_sent": len(prepared["text"]),
        "source_was_truncated": prepared["was_truncated"],
        "source_input_kind": "pdf" if pdf_path else "text",
        "pdf_filename": pdf_path.name if pdf_path else None,
        "pdf_size_bytes": pdf_path.stat().st_size if pdf_path else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return extraction, response


def summarize_blueprint_with_openai(
    *,
    compact_blueprint: dict[str, Any],
    model: str = DEFAULT_MODEL,
    api_key_env: str = DEFAULT_API_KEY_ENV,
    timeout_seconds: int = 120,
) -> tuple[dict[str, Any], dict[str, Any]]:
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise LLMExtractionError(f"Missing OpenAI API key environment variable: {api_key_env}")

    request_body = _build_summary_request(compact_blueprint=compact_blueprint, model=model)
    response = _post_openai_response(api_key=api_key, body=request_body, timeout_seconds=timeout_seconds)
    output_text = _extract_output_text(response)

    try:
        summary = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise LLMExtractionError(f"OpenAI summary response was not valid JSON: {exc}") from exc

    summary["_request_metadata"] = {
        "model": model,
        "api_key_env": api_key_env,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return summary, response


def apply_llm_extraction(
    blueprint: dict[str, Any],
    extraction: dict[str, Any],
    *,
    model: str,
) -> dict[str, Any]:
    draft = deepcopy(blueprint)
    field_index = {
        (section.get("key"), field.get("key")): field
        for section, field in iter_fields(draft)
    }
    unknown_fields: list[dict[str, str]] = []

    for item in extraction.get("fields", []):
        if not isinstance(item, dict):
            continue
        key = (item.get("section_key"), item.get("field_key"))
        field = field_index.get(key)
        if field is None:
            unknown_fields.append(
                {
                    "section_key": str(item.get("section_key", "")),
                    "field_key": str(item.get("field_key", "")),
                }
            )
            continue

        status = item.get("status")
        if status not in STATUS_VALUES:
            status = "unclear"

        value = item.get("value")
        if status == "not_reported" and not value:
            value = None

        field["value"] = value
        field["status"] = status
        field["evidence"] = _normalize_evidence(item.get("evidence"))
        field["reviewer_notes"] = item.get("reviewer_notes") or ""
        field["llm_confidence"] = item.get("confidence")
        field["extraction_source"] = "openai_llm_draft"

    metadata = extraction.get("_request_metadata", {})
    draft["run"]["mode"] = "llm_draft_extraction"
    draft["run"]["llm"] = {
        "provider": "openai",
        "model": model,
        "generated_at": metadata.get("generated_at") or datetime.now(timezone.utc).isoformat(),
        "source_characters_sent": metadata.get("source_characters_sent"),
        "source_was_truncated": metadata.get("source_was_truncated"),
        "source_input_kind": metadata.get("source_input_kind"),
        "pdf_filename": metadata.get("pdf_filename"),
        "pdf_size_bytes": metadata.get("pdf_size_bytes"),
        "paper_summary": extraction.get("paper_summary", ""),
        "warnings": extraction.get("warnings", []),
        "unknown_returned_fields": unknown_fields,
    }
    return draft


def extraction_response_schema(blueprint: dict[str, Any]) -> dict[str, Any]:
    section_keys = [section.get("key", "") for section in blueprint.get("sections", [])]
    field_keys = [field.get("key", "") for _, field in iter_fields(blueprint)]

    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["paper_summary", "fields", "warnings"],
        "properties": {
            "paper_summary": {
                "type": "string",
                "description": "Brief summary of the paper focus and experimental methodology.",
            },
            "fields": {
                "type": "array",
                "description": "One extraction record for each requested Method Blueprint field.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "section_key",
                        "field_key",
                        "value",
                        "status",
                        "evidence",
                        "reviewer_notes",
                        "confidence",
                    ],
                    "properties": {
                        "section_key": {"type": "string", "enum": section_keys},
                        "field_key": {"type": "string", "enum": field_keys},
                        "value": {
                            "type": "string",
                            "description": "Extracted value. Use an empty string when not reported or unclear.",
                        },
                        "status": {"type": "string", "enum": list(STATUS_VALUES)},
                        "evidence": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["passage", "page", "section", "source", "quote_is_exact"],
                                "properties": {
                                    "passage": {
                                        "type": "string",
                                        "description": "Exact or near-exact supporting passage from the provided source text.",
                                    },
                                    "page": {
                                        "type": "string",
                                        "description": "Page number if known, otherwise an empty string.",
                                    },
                                    "section": {
                                        "type": "string",
                                        "description": "Paper section name if known, otherwise an empty string.",
                                    },
                                    "source": {
                                        "type": "string",
                                        "description": "Source reference such as source.txt, PDF page, URL, table, or figure.",
                                    },
                                    "quote_is_exact": {
                                        "type": "boolean",
                                        "description": "True when passage is an exact quote from the provided text.",
                                    },
                                },
                            },
                        },
                        "reviewer_notes": {
                            "type": "string",
                            "description": "Short note on uncertainty, inference, contradiction, or why data are missing.",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Extractor confidence from 0.0 to 1.0.",
                        },
                    },
                },
            },
            "warnings": {
                "type": "array",
                "description": "Extraction-level warnings such as truncation-sensitive fields or poor source text quality.",
                "items": {"type": "string"},
            },
        },
    }


def method_summary_response_schema() -> dict[str, Any]:
    reusable_idea_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["idea", "why_it_matters", "reusable_pattern", "supporting_blueprint_fields"],
        "properties": {
            "idea": {"type": "string"},
            "why_it_matters": {"type": "string"},
            "reusable_pattern": {"type": "string"},
            "supporting_blueprint_fields": {"type": "array", "items": {"type": "string"}},
        },
    }
    experiment_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["name", "purpose", "data", "method", "comparison", "evaluation", "finding_type"],
        "properties": {
            "name": {"type": "string"},
            "purpose": {"type": "string"},
            "data": {"type": "string"},
            "method": {"type": "string"},
            "comparison": {"type": "string"},
            "evaluation": {"type": "string"},
            "finding_type": {"type": "string"},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "paper",
            "method_theme",
            "research_goal",
            "design_pattern",
            "design_pattern_tags",
            "experimental_unit",
            "data_strategy",
            "comparison_strategy",
            "validation_strategy",
            "evaluation_strategy",
            "statistical_strategy",
            "robustness_strategy",
            "key_methods",
            "key_metrics",
            "reusable_method_ideas",
            "experiments",
            "important_limitations",
            "missing_or_unclear",
            "other_important_details",
            "confidence_notes",
            "warnings",
        ],
        "properties": {
            "paper": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "paper_id", "domain"],
                "properties": {
                    "title": {"type": "string"},
                    "paper_id": {"type": "string"},
                    "domain": {"type": "string"},
                },
            },
            "method_theme": {"type": "string"},
            "research_goal": {"type": "string"},
            "design_pattern": {"type": "string"},
            "design_pattern_tags": {"type": "array", "items": {"type": "string"}},
            "experimental_unit": {"type": "string"},
            "data_strategy": {"type": "string"},
            "comparison_strategy": {"type": "string"},
            "validation_strategy": {"type": "string"},
            "evaluation_strategy": {"type": "string"},
            "statistical_strategy": {"type": "string"},
            "robustness_strategy": {"type": "string"},
            "key_methods": {"type": "array", "items": {"type": "string"}},
            "key_metrics": {"type": "array", "items": {"type": "string"}},
            "reusable_method_ideas": {"type": "array", "items": reusable_idea_schema},
            "experiments": {"type": "array", "items": experiment_schema},
            "important_limitations": {"type": "array", "items": {"type": "string"}},
            "missing_or_unclear": {"type": "array", "items": {"type": "string"}},
            "other_important_details": {"type": "array", "items": {"type": "string"}},
            "confidence_notes": {"type": "string"},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
    }


def _build_summary_request(*, compact_blueprint: dict[str, Any], model: str) -> dict[str, Any]:
    system_prompt = (
        "You condense a detailed Method Blueprint into a compact Method Summary for a researcher. "
        "Use only the blueprint content. Do not invent details. Preserve important missingness and uncertainty. "
        "Focus on the experimental design pattern, reusable method ideas, validation/evaluation strategy, and major gaps."
    )
    user_prompt = {
        "task": "Create a concise, reusable method summary from this Method Blueprint.",
        "instructions": [
            "Make the summary useful for comparing many papers later.",
            "Prefer general experimental patterns over paper-specific trivia.",
            "Include important caveats and missing methodology fields.",
            "If multiple experiments are present, summarize each in experiments[].",
            "Use short phrases suitable for JSONL/CSV comparison where possible.",
            "Do not claim evidence beyond what the blueprint contains.",
        ],
        "compact_blueprint": compact_blueprint,
    }
    return {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": json.dumps(user_prompt, ensure_ascii=False)}],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "method_summary",
                "strict": True,
                "schema": method_summary_response_schema(),
            }
        },
        "max_output_tokens": 7000,
    }


def _build_responses_request(
    *,
    blueprint: dict[str, Any],
    source_text: str,
    sections: list[dict[str, Any]],
    pdf_path: Path | None,
    model: str,
    max_chars: int,
    was_truncated: bool,
) -> dict[str, Any]:
    domain = blueprint.get("paper", {}).get("domain_profile", "general")
    schema_spec = field_specs_as_dict(domain)
    section_hints = [
        {
            "heading": section.get("heading", ""),
            "method_candidate": section.get("method_candidate", False),
            "preview": section.get("preview", "")[:700],
        }
        for section in sections[:20]
    ]

    system_prompt = (
        "You extract experimental methodology from scientific papers into a structured Method Blueprint. "
        "Do not invent content. Prefer not_reported or unclear when the source text does not support a field. "
        "Use reported only for content explicitly stated in the paper. Use inferred only when the inference is "
        "necessary and obvious from the supplied text, and explain the inference in reviewer_notes. "
        "Every reported, inferred, or contradictory field should include concise supporting evidence."
    )
    user_prompt = {
        "task": "Return a draft extraction for the requested Method Blueprint schema.",
        "domain_profile": domain,
        "status_values": list(STATUS_VALUES),
        "field_schema": schema_spec,
        "section_hints": section_hints,
        "source_text_metadata": {
            "characters_sent": len(source_text),
            "max_characters": max_chars,
            "was_truncated": was_truncated,
        },
        "instructions": [
            "Return one fields[] item for every field in field_schema.",
            "Keep values concise but specific enough for research-method review.",
            "Quote exact source passages when possible.",
            "If the supplied text is truncated, add warnings for fields that may need full-paper review.",
            "Do not score overall paper quality.",
        ],
    }
    if pdf_path is None:
        user_prompt["source_text"] = source_text
    else:
        user_prompt["source_text"] = ""
        user_prompt["pdf_input"] = {
            "filename": pdf_path.name,
            "size_bytes": pdf_path.stat().st_size,
            "note": "The PDF is attached as an input_file. Use its text, tables, figures, and page images when available.",
        }

    user_content: list[dict[str, Any]] = [{"type": "input_text", "text": json.dumps(user_prompt, ensure_ascii=False)}]
    if pdf_path is not None:
        user_content.append(_pdf_input_file_content(pdf_path))

    return {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": user_content,
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "method_blueprint_extraction",
                "strict": True,
                "schema": extraction_response_schema(blueprint),
            }
        },
        "max_output_tokens": 12000,
    }


def _pdf_input_file_content(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise LLMExtractionError(f"PDF does not exist: {path}")
    if path.suffix.lower() != ".pdf":
        raise LLMExtractionError(f"Direct file input currently expects a PDF path, got: {path}")

    size = path.stat().st_size
    if size > MAX_DIRECT_PDF_BYTES:
        raise LLMExtractionError(
            f"PDF is too large for direct OpenAI file input: {size} bytes. "
            f"Limit is {MAX_DIRECT_PDF_BYTES} bytes."
        )

    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return {
        "type": "input_file",
        "filename": path.name,
        "file_data": f"data:application/pdf;base64,{encoded}",
    }


def _post_openai_response(*, api_key: str, body: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise LLMExtractionError(f"OpenAI API request failed with HTTP {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise LLMExtractionError(f"OpenAI API request failed: {exc}") from exc


def _extract_output_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str) and response["output_text"].strip():
        return response["output_text"]

    parts: list[str] = []
    for output_item in response.get("output", []):
        for content_item in output_item.get("content", []):
            if content_item.get("type") in {"output_text", "text"}:
                text = content_item.get("text")
                if isinstance(text, str):
                    parts.append(text)

    output_text = "\n".join(parts).strip()
    if not output_text:
        raise LLMExtractionError("OpenAI response did not contain output text.")
    return output_text


def _prepare_source_text(source_text: str, max_chars: int) -> dict[str, Any]:
    source_text = source_text.strip()
    if len(source_text) <= max_chars:
        return {"text": source_text, "was_truncated": False}

    head_chars = max_chars // 2
    tail_chars = max_chars - head_chars
    text = (
        source_text[:head_chars]
        + "\n\n[... middle of source text omitted due to max character limit ...]\n\n"
        + source_text[-tail_chars:]
    )
    return {"text": text, "was_truncated": True}


def _normalize_evidence(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    evidence: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        evidence.append(
            {
                "passage": item.get("passage") or "",
                "page": item.get("page") or "",
                "section": item.get("section") or "",
                "source": item.get("source") or "source.txt",
                "quote_is_exact": bool(item.get("quote_is_exact")),
            }
        )
    return evidence

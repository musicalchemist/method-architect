# Manual Method Extraction Helper

This is a side helper for manually extracting methods from papers while Method Architect is still in its early research phase.

It is intentionally separate from the main project code. The helper creates a per-paper workspace, extracts source text when possible, generates an editable JSON blueprint, and reports missingness/provenance issues without inventing methodological content.

## Quick Start

From this folder:

```bash
../../.venv/bin/python -m method_extractor extract path/to/paper.pdf --domain biomedical_ai
```

Or use `uv` from this folder:

```bash
uv run python -m method_extractor extract papers/paper.pdf --domain ai_ml --llm
```

This form runs the helper without installing the console script into the environment first.

Local papers and generated runs belong here:

```text
papers/
runs/
```

Both directories are ignored by Git, so local PDFs and extraction outputs are not pushed to GitHub.

To ask OpenAI to draft-fill the schema from the extracted source text:

```bash
../../.venv/bin/python -m method_extractor extract path/to/paper.pdf --domain biomedical_ai --llm
```

For local PDFs, `--llm` sends the PDF directly to OpenAI as a file input by default. That lets the model use PDF text and page images when the selected model supports them. To force text-only extraction, add `--pdf-input text`.

The LLM path uses `OPENAI_API_KEY_METHOD_ARCHITECT` by default. You can override the model:

```bash
../../.venv/bin/python -m method_extractor extract path/to/paper.pdf --domain ai_ml --llm --model gpt-4.1-mini
```

You can also start from a URL:

```bash
../../.venv/bin/python -m method_extractor extract "https://example.org/paper.html" --domain ai_ml --llm
```

Each run creates a folder under `runs/`:

```text
runs/<timestamp>-<paper-slug>/
  blueprint.json
  audit.json
  report.md
  annotation_worksheet.md
  source/
    original.<ext>
    source.txt
    source_metadata.json
    sections.json
```

When `--llm` is used, the run also includes `blueprint.template.json`, `llm_extraction.json`, and `llm_response.json`.

Each extraction appends a searchable record to:

```text
runs/index.jsonl
```

`blueprint.json` is the canonical editable record. Important fields use explicit status values:

- `reported`
- `inferred`
- `unclear`
- `contradictory`
- `not_reported`

Use `reported` or `inferred` only when you can attach evidence with a passage, page or section, and source reference.

## Add LLM Extraction Later

If you first create a manual workspace, you can ask the LLM to fill a draft later:

```bash
../../.venv/bin/python -m method_extractor llm-fill runs/<run-folder>
```

That writes `blueprint.llm.json` and `report.llm.md` without replacing your current `blueprint.json`.

To apply the LLM draft to the main blueprint, use:

```bash
../../.venv/bin/python -m method_extractor llm-fill runs/<run-folder> --apply
```

LLM output is a draft for human review. The validator still flags missing evidence, invalid statuses, and required fields left as `not_reported`.

## Find Previous Runs

List indexed runs:

```bash
../../.venv/bin/python -m method_extractor index
```

Search by title, paper ID, input, or run folder name:

```bash
../../.venv/bin/python -m method_extractor index --query "nature"
```

## Validate A Blueprint

```bash
../../.venv/bin/python -m method_extractor validate runs/<run-folder>
```

Validation checks schema shape, status values, missing values, evidence gaps, and required review fields that are still marked `not_reported`.

## Run Tests

```bash
../../.venv/bin/python -m unittest discover -s tests
```

## PDF Text Extraction

The CLI works without third-party dependencies, but PDF text extraction needs either:

- the `pdftotext` system command, or
- the optional Python dependency `pypdf`

Install the optional PDF dependency when you are ready:

```bash
../../.venv/bin/python -m pip install -e ".[pdf]"
```

Without a PDF extractor, the workflow still creates the paper workspace and blueprint template.

## Why No Agents Yet?

This helper uses a single structured LLM call, not a multi-agent workflow. Agents may become useful later for section routing, verification, retries, and cross-paper comparison, but the first useful automation is simply: source text in, schema-shaped draft out, human review after.

# Method Architect

Method Architect is an early-stage open-source research software project for extracting, organizing, comparing, auditing, and eventually reusing experimental methodology from scientific papers.

The long-term goal is to convert papers into evidence-grounded Method Blueprints that help researchers understand published experimental designs and construct more rigorous, traceable, and defensible research plans.

Initial focus areas:

- Artificial intelligence and machine learning
- Computational biology
- Biomedical AI
- Biotechnology and data-intensive biological research

For the full project vision, see [PROJECT_CHARTER.md](PROJECT_CHARTER.md).

## Current Status

This repository is in an early research and tooling phase.

The current usable tool is a helper CLI for extracting a draft Method Blueprint from one paper at a time. It lives under:

```text
helpers/method_extractor/
```

The helper can:

- Create a structured Method Blueprint workspace for a paper.
- Send local PDFs directly to OpenAI for schema-shaped LLM extraction.
- Extract from text, HTML, URLs, or PDFs.
- Preserve explicit field statuses such as `reported`, `inferred`, `unclear`, `contradictory`, and `not_reported`.
- Save JSON and Markdown outputs for human review.
- Keep local papers and generated runs out of Git.

LLM extraction is a draft, not ground truth. Human review remains part of the workflow.

## Quick Start

From the helper directory:

```bash
cd helpers/method_extractor
uv run python -m method_extractor extract "papers/example-paper.pdf" --domain ai_ml --llm
```

For biomedical AI papers:

```bash
uv run python -m method_extractor extract "papers/example-paper.pdf" --domain biomedical_ai --llm
```

The helper uses the `OPENAI_API_KEY_METHOD_ARCHITECT` environment variable by default:

```bash
export OPENAI_API_KEY_METHOD_ARCHITECT="your_key_here"
```

Do not commit API keys, papers, run outputs, or `.env` files.

## Domains

The helper currently supports these domain profiles:

```text
general
ai_ml
comp_bio
biomedical_ai
```

Use `ai_ml` for general AI or machine-learning papers. Use `biomedical_ai` for papers that combine AI/ML with biomedical, clinical, biological, or computational-biology methodology.

## Outputs

Each extraction creates a run folder under:

```text
helpers/method_extractor/runs/
```

Typical outputs include:

```text
blueprint.json
audit.json
report.md
annotation_worksheet.md
llm_extraction.json
llm_response.json
source/
```

The main file is `blueprint.json`. The easier human-readable review file is `report.md`.

List indexed runs:

```bash
uv run python -m method_extractor index
```

Search indexed runs:

```bash
uv run python -m method_extractor index --query "paper title or id"
```

## Local Files and Privacy

Local papers and generated extraction outputs should stay in:

```text
helpers/method_extractor/papers/
helpers/method_extractor/runs/
```

These paths are ignored by Git. This matters because PDFs, extracted text, LLM responses, and reports may contain copyrighted paper content, private metadata, or accidental sensitive information.

Before sending a PDF or dataset to an external API, confirm that it is appropriate to share with that provider.

See [SECURITY.md](SECURITY.md) for repository security expectations.

## Core Principles

Method Architect is designed around:

- Evidence grounding
- Explicit missingness and uncertainty
- Typed, machine-readable outputs
- Human inspectability
- Scientific humility
- Reproducibility

The system should not invent methodological content or silently fill missing fields. Important methodological claims should be linked to supporting passages, pages, sections, tables, or figures whenever possible.

## Roadmap

Near-term work:

- Improve PDF and table/figure extraction workflows.
- Add stronger evidence verification.
- Add deterministic methodological audit rules.
- Build reviewed example blueprints from seed papers.
- Add evaluation fixtures and extraction metrics.

Longer-term work:

- Normalize reusable Method Cards.
- Build a searchable method library.
- Compare methods across papers.
- Support research-design assistance grounded in published methodology.

## Development

Run the helper tests:

```bash
cd helpers/method_extractor
uv run python -m unittest discover -s tests
```

This project favors incremental, inspectable changes. Avoid adding dependencies or external services without review.

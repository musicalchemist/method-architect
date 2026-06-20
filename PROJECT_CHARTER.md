````markdown
# Method Architect

## Project Charter

## Overview

Method Architect is an open-source research software project for extracting, organizing, comparing, auditing, and reusing experimental methodology from scientific literature.

Scientific papers often describe their methodology across narrative text, figures, tables, supplementary materials, code repositories, and cited prior work. This makes it difficult to determine exactly how a study was designed, which assumptions were made, how evidence was evaluated, and which methodological components can be adapted to future research.

Method Architect aims to convert scientific papers into structured, evidence-grounded experimental blueprints.

The initial focus is:

- Artificial intelligence and machine learning
- Computational biology
- Biotechnology
- Biomedical AI
- Data-intensive biological research

The long-term goal is to help researchers understand published methods and construct more rigorous, traceable, and defensible research designs.

---

## Problem

Researchers reading a paper must often manually reconstruct:

- The central research question
- The stated or implied hypotheses
- The experimental unit
- The population, cohort, or dataset
- Inclusion and exclusion criteria
- Experimental and control groups
- Data preprocessing
- Model training and selection
- Statistical analyses
- Evaluation metrics
- Robustness and sensitivity analyses
- Experimental assumptions
- Limitations
- Reproducibility resources
- The evidence supporting each methodological claim

Traditional paper summaries may describe the general approach while omitting the details needed to reproduce, evaluate, compare, or adapt the study.

Methodological concepts are also difficult to reuse. Similar experimental patterns may appear across many papers under different names, reporting conventions, and levels of detail.

---

## Vision

Method Architect will help researchers move from scientific literature to defensible experimental design.

The long-term workflow is:

```text
Scientific papers
        ↓
Evidence-grounded experimental blueprints
        ↓
Normalized methodological patterns
        ↓
Searchable method library
        ↓
Cross-paper comparison and auditing
        ↓
Candidate designs for new research questions
```

The system is intended to support human scientific reasoning. It is not intended to replace scientific expertise, statistical consultation, peer review, or independent validation.

---

## Initial Mission

The initial mission is to build a command-line application that converts a scientific paper into a structured and inspectable Method Blueprint.

A user should eventually be able to run:

```bash
method-architect extract paper.pdf
```

and receive outputs such as:

```text
paper.blueprint.json
paper.report.md
paper.audit.json
paper.evidence.html
```

The output should reconstruct the experimental methodology while preserving the evidence supporting each extracted field.

---

## Initial Domains

Method Architect will initially support two closely related methodological profiles.

### Artificial Intelligence and Machine Learning

The AI/ML profile may extract and evaluate:

- Research objective
- Dataset construction
- Train, validation, and test partitions
- Model architecture
- Training procedure
- Objective functions
- Optimization strategy
- Hyperparameter selection
- Baselines
- Evaluation metrics
- Statistical comparisons
- Ablation studies
- Robustness experiments
- Compute reporting
- Reproducibility information
- Potential benchmark contamination
- Potential data leakage

### Computational Biology and Biomedical AI

The computational-biology profile may additionally extract and evaluate:

- Biological research question
- Study cohort
- Specimen or assay type
- Experimental unit
- Biological replicates
- Technical replicates
- Batch effects
- Biological confounders
- Patient-level partitioning
- Feature dimensionality
- Multiple-hypothesis correction
- External cohort validation
- Biological interpretation
- Translational limitations

The software architecture will use a shared methodological core with domain-specific extensions.

---

## Core Principles

### Evidence Grounding

Every extracted methodological statement should retain a connection to the source evidence that supports it.

Evidence may include:

- Source text
- Page number
- Document section
- Table or figure reference
- Extraction confidence
- Whether the information was explicit or inferred

### Explicit Missingness

The system should distinguish among:

- Reported information
- Reasonably inferred information
- Unclear information
- Contradictory information
- Information not found in the paper

Method Architect should abstain when the available evidence is insufficient.

### Structured Outputs

Outputs should use typed, machine-readable schemas rather than unrestricted prose alone.

Structured representations make it possible to:

- Validate extraction results
- Compare studies
- Search methodological patterns
- Apply deterministic audit rules
- Build reusable method libraries
- Construct research-design recommendations
- Create reproducible benchmarks

### Human Inspectability

Researchers should be able to inspect how extracted conclusions and audit findings were produced.

The project will prioritize:

- Transparent intermediate artifacts
- Source-linked evidence
- Versioned prompts
- Reproducible configuration
- Typed schemas
- Readable reports
- Explicit uncertainty

### Scientific Humility

Method Architect will not present automated judgments as definitive assessments of scientific quality.

The system may identify:

- Reporting gaps
- Possible methodological risks
- Potential inconsistencies
- Missing controls
- Possible data leakage
- Statistical assumptions requiring review

Final interpretation remains the responsibility of qualified researchers.

### Reproducibility

Each extraction run should eventually record:

- Input document identity
- Input checksum
- Parser version
- Model and provider
- Prompt version
- Software version
- Configuration
- Intermediate outputs
- Errors and retries

---

## The Method Blueprint

The central data object will be the Method Blueprint.

An initial Method Blueprint may contain the following sections.

### Paper Information

- Title
- Authors
- Publication year
- Venue
- Scientific domain
- Paper identifier

### Research Framing

- Research question
- Hypotheses
- Knowledge gap
- Claimed contribution
- Intended scientific or technical claim

### Data and Sampling

- Data sources
- Experimental unit
- Population or cohort
- Sample size
- Inclusion criteria
- Exclusion criteria
- Group structure
- Repeated measurements
- Predictor variables
- Outcome variables

### Experimental Design

- Study type
- Experimental conditions
- Controls
- Randomization
- Blinding
- Data partitioning
- Cross-validation
- External validation

### Methods

- Preprocessing
- Feature engineering
- Feature selection
- Statistical models
- Machine-learning models
- Baselines
- Optimization
- Hyperparameter selection

### Evaluation

- Primary metrics
- Secondary metrics
- Statistical tests
- Effect sizes
- Confidence intervals
- Multiple-testing corrections
- Calibration
- Robustness checks
- Sensitivity analyses
- Ablation studies

### Validity and Reproducibility

- Potential data leakage
- Potential confounding
- Statistical assumptions
- Methodological limitations
- Data availability
- Code availability
- Software environment
- Random seeds
- Reproduction requirements

### Evidence

Each extracted value should include:

- Supporting passage
- Page or section
- Extraction status
- Confidence
- Whether the value was explicit, inferred, unclear, or missing

---

## Initial Product Scope

The first version will support:

- Local PDF input
- Scientific-document parsing
- Section-aware extraction
- Typed Method Blueprint output
- Evidence-linked fields
- Explicit missing-information labels
- JSON output
- Markdown reports
- Basic command-line usage

The first version will support a limited set of AI/ML and computational-biology study types rather than attempting to support all scientific research.

---

## Initial Non-Goals

The first version will not attempt to:

- Support every scientific discipline
- Replace peer review
- Determine whether a paper is scientifically correct
- Generate a universal research-quality score
- Validate every reported numerical result
- Reproduce wet-lab experiments
- Perform fully autonomous scientific discovery
- Fine-tune a specialized foundation model
- Use an unrestricted multi-agent architecture
- Build a large-scale commercial platform
- Produce publication-ready protocols without human review

These capabilities may be explored only after the core extraction and evaluation system has been validated.

---

## Methodological Auditing

After structured extraction becomes reliable, Method Architect may implement transparent audit rules.

### General AI/ML Checks

Examples include:

- Feature selection performed before data partitioning
- Preprocessing fitted on the complete dataset
- Test data used during model selection
- Missing or weak baselines
- Inadequate uncertainty reporting
- Inappropriate metrics for class imbalance
- Missing ablations for claimed contributions
- Unclear random-seed variability
- Potential benchmark contamination
- Hyperparameter selection insufficiently described

### Computational Biology and Biomedical AI Checks

Examples include:

- Related samples divided across evaluation partitions
- Technical replicates treated as independent biological samples
- Batch effects confounded with outcome
- Batch correction performed before data partitioning
- Missing multiple-testing correction
- Unclear cohort-selection criteria
- Lack of external validation
- High feature dimensionality relative to sample size
- Biological interpretation exceeding the available evidence
- Patient-level leakage

Audit findings should preserve supporting evidence and allow an `unknown` result when the paper lacks sufficient information.

---

## Method Library

A later phase will normalize recurring methodological patterns into reusable Method Cards.

A Method Card may document:

- Method name
- Purpose
- Applicable research questions
- Required data structure
- Assumptions
- Inputs and outputs
- Compatible methods
- Alternatives
- Common failure modes
- Diagnostic checks
- Supporting papers
- Reference implementations

Examples may include:

- Nested cross-validation
- Grouped data splitting
- Bootstrap confidence intervals
- Permutation testing
- Calibration analysis
- Multiple-testing correction
- Mixed-effects modeling
- Batch-effect correction
- External cohort validation
- Ablation studies
- Sensitivity analyses

---

## Research-Design Assistance

A long-term objective is to help researchers construct candidate experimental designs.

A user may provide:

- Research question
- Scientific objective
- Domain
- Experimental unit
- Available data
- Outcome type
- Sample size
- Feature dimensionality
- Resource constraints
- Interpretation requirements

Method Architect may then:

1. Structure the research problem.
2. Retrieve compatible methodological patterns.
3. Compose candidate experimental designs.
4. Identify assumptions and dependencies.
5. Audit each candidate design.
6. Provide alternatives.
7. Link recommendations to supporting literature.
8. Identify unresolved design decisions.

Generated designs should be presented as candidates for expert review rather than authoritative scientific protocols.

---

## Research and Evaluation Goals

The project is intended to support formal research evaluation.

An initial research question is:

> Can an evidence-grounded extraction and verification system accurately reconstruct experimental methodology from computational-biology and biomedical machine-learning papers?

Possible evaluation dimensions include:

- Field-level precision
- Field-level recall
- F1 score
- Numeric extraction accuracy
- Evidence-location accuracy
- Unsupported-claim rate
- Missing-information detection
- Explicit-versus-inferred classification
- Audit-rule precision
- Confidence calibration
- Performance across paper types
- Performance across methodology fields

Potential system variants may include:

1. Whole-document prompting
2. Section-based extraction
3. Evidence retrieval followed by extraction
4. Extraction followed by independent verification
5. Extraction, verification, and deterministic auditing

The initial publication benchmark will focus on a narrow and clearly defined class of computational-biology or biomedical-AI papers.

---

## Initial Milestones

### Milestone 1: Foundation

- Define project scope
- Select a small seed-paper corpus
- Create the initial Method Blueprint schema
- Produce manual reference annotations
- Establish the public repository

### Milestone 2: Working Extraction

- Parse a local scientific PDF
- Extract major methodology fields
- Validate output against the schema
- Produce JSON and Markdown reports

### Milestone 3: Evidence Verification

- Preserve source passages and page information
- Distinguish explicit, inferred, unclear, and missing fields
- Verify extracted claims against source evidence

### Milestone 4: Methodological Auditing

- Implement initial deterministic audit rules
- Add AI/ML-specific checks
- Add computational-biology-specific checks
- Produce inspectable audit reports

### Milestone 5: Evaluation

- Create a reviewed benchmark
- Implement extraction metrics
- Compare alternative pipeline designs
- Document common failure modes

### Milestone 6: Method Library

- Normalize recurring methods
- Create reviewed Method Cards
- Add search and cross-paper comparison

### Milestone 7: Research Design

- Accept structured research questions
- Retrieve compatible methodological patterns
- Compose and audit candidate designs
- Preserve provenance for recommendations

---

## Success Criteria for the First Release

The first meaningful release will be successful when a user can run:

```bash
method-architect extract paper.pdf
```

and receive:

- A schema-valid Method Blueprint
- Evidence for important extracted fields
- Clear missing-information labels
- A readable report
- Reproducible run metadata
- A small set of transparent audit findings

The repository should also include:

- Representative AI/ML examples
- Representative computational-biology examples
- Manual reference outputs
- Automated tests
- A basic evaluation script
- Documented limitations

---

## Intended Impact

Method Architect is intended to help researchers:

- Understand papers more deeply
- Learn rigorous experimental methodology
- Compare experimental designs
- Identify reporting gaps
- Avoid common statistical and ML evaluation errors
- Reuse defensible methodological patterns
- Develop better-grounded research plans
- Improve scientific reproducibility

The project also serves as an open research platform for studying:

- Scientific information extraction
- Methodological representation
- Evidence verification
- Statistical auditing
- Research-design assistance
- Human-AI collaboration in science

---

## Project Status

Method Architect is currently an early-stage research and engineering project.

Schemas, interfaces, outputs, and methodological claims are expected to evolve as the system is evaluated against real scientific papers.

Contributions, critiques, domain expertise, and benchmark suggestions are welcome.
````

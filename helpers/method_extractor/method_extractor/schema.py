from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from . import __version__


STATUS_VALUES = (
    "reported",
    "inferred",
    "unclear",
    "contradictory",
    "not_reported",
)

VALUE_EXPECTED_STATUSES = {"reported", "inferred", "contradictory"}
EVIDENCE_EXPECTED_STATUSES = {"reported", "inferred", "contradictory"}

DOMAIN_PROFILES = ("general", "ai_ml", "comp_bio", "biomedical_ai")


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    prompt: str
    required: bool = False
    domain: str = "core"


@dataclass(frozen=True)
class SectionSpec:
    key: str
    label: str
    fields: tuple[FieldSpec, ...]


COMMON_SECTIONS: tuple[SectionSpec, ...] = (
    SectionSpec(
        "paper_information",
        "Paper Information",
        (
            FieldSpec("title", "Title", "Paper title.", True),
            FieldSpec("authors", "Authors", "Paper authors or author group.", True),
            FieldSpec("publication_year", "Publication Year", "Year of publication or preprint.", True),
            FieldSpec("venue", "Venue", "Journal, conference, preprint server, or repository.", False),
            FieldSpec("paper_identifier", "Paper Identifier", "DOI, arXiv ID, PubMed ID, URL, or other stable identifier.", True),
            FieldSpec("scientific_domain", "Scientific Domain", "High-level domain such as AI/ML, computational biology, biomedical AI, or biotech.", True),
        ),
    ),
    SectionSpec(
        "research_framing",
        "Research Framing",
        (
            FieldSpec("research_question", "Research Question", "Central research question the study attempts to answer.", True),
            FieldSpec("hypotheses", "Hypotheses", "Explicit or inferable hypotheses under test.", True),
            FieldSpec("knowledge_gap", "Knowledge Gap", "Gap in prior work that motivates the study.", False),
            FieldSpec("claimed_contribution", "Claimed Contribution", "Main contribution claimed by the authors.", True),
            FieldSpec("intended_claim", "Intended Scientific or Technical Claim", "Claim the experiments are meant to support.", True),
        ),
    ),
    SectionSpec(
        "data_and_sampling",
        "Data and Sampling",
        (
            FieldSpec("data_sources", "Data Sources", "Datasets, cohorts, repositories, simulations, specimens, or generated data used.", True),
            FieldSpec("experimental_unit", "Experimental Unit", "Unit treated as one independent observation or experimental item.", True),
            FieldSpec("population_or_cohort", "Population or Cohort", "Population, cohort, benchmark collection, or sampled universe.", True),
            FieldSpec("sample_size", "Sample Size", "Number of units, samples, patients, records, tasks, or observations.", True),
            FieldSpec("inclusion_criteria", "Inclusion Criteria", "Criteria for including data, papers, patients, samples, tasks, or experiments.", True),
            FieldSpec("exclusion_criteria", "Exclusion Criteria", "Criteria for excluding data, patients, samples, tasks, or experiments.", True),
            FieldSpec("group_structure", "Group Structure", "Groups, arms, labels, treatment/control definitions, classes, or cohorts.", True),
            FieldSpec("repeated_measurements", "Repeated Measurements", "Repeated, clustered, longitudinal, paired, or otherwise non-independent observations.", False),
            FieldSpec("predictor_variables", "Predictor Variables", "Features, covariates, inputs, exposures, or independent variables.", True),
            FieldSpec("outcome_variables", "Outcome Variables", "Primary outcomes, labels, targets, endpoints, or dependent variables.", True),
        ),
    ),
    SectionSpec(
        "experimental_design",
        "Experimental Design",
        (
            FieldSpec("study_type", "Study Type", "Experimental, observational, retrospective, prospective, benchmark, simulation, or other design.", True),
            FieldSpec("experimental_conditions", "Experimental Conditions", "Conditions, interventions, variants, settings, or tasks compared.", True),
            FieldSpec("controls", "Controls", "Negative controls, positive controls, control groups, placebo, no-treatment, sham, or reference conditions.", True),
            FieldSpec("randomization", "Randomization", "Random assignment, random sampling, random seed handling, or lack thereof.", True),
            FieldSpec("blinding", "Blinding", "Blinding or masking of participants, assessors, annotators, analysts, or model developers.", True),
            FieldSpec("data_partitioning", "Data Partitioning", "Train/validation/test, discovery/validation, temporal, grouped, patient-level, or external splits.", True),
            FieldSpec("cross_validation", "Cross-Validation", "Cross-validation design, folds, nesting, grouping, repetitions, and selection use.", False),
            FieldSpec("external_validation", "External Validation", "External cohort, held-out benchmark, independent replication, or out-of-domain validation.", True),
        ),
    ),
    SectionSpec(
        "methods",
        "Methods",
        (
            FieldSpec("preprocessing", "Preprocessing", "Cleaning, normalization, filtering, imputation, transformations, augmentation, or batch correction.", True),
            FieldSpec("feature_engineering", "Feature Engineering", "Constructed features, embeddings, representations, descriptors, or derived variables.", False),
            FieldSpec("feature_selection", "Feature Selection", "Feature filtering, selection criteria, dimensionality reduction, or leakage-sensitive selection steps.", True),
            FieldSpec("statistical_models", "Statistical Models", "Regression, mixed models, survival models, hypothesis models, or other statistical models.", True),
            FieldSpec("machine_learning_models", "Machine-Learning Models", "Algorithms, architectures, estimators, or model families used.", True),
            FieldSpec("baselines", "Baselines", "Comparison methods, standard-of-care, previous methods, simple baselines, or ablations used as baselines.", True),
            FieldSpec("optimization", "Optimization", "Optimizer, fitting procedure, convergence criteria, training objective, or estimation method.", False),
            FieldSpec("hyperparameter_selection", "Hyperparameter Selection", "Search space, tuning procedure, validation use, selection metric, and final configuration.", True),
        ),
    ),
    SectionSpec(
        "evaluation",
        "Evaluation",
        (
            FieldSpec("primary_metrics", "Primary Metrics", "Primary evaluation metrics or endpoints.", True),
            FieldSpec("secondary_metrics", "Secondary Metrics", "Additional evaluation metrics, diagnostics, or secondary endpoints.", False),
            FieldSpec("statistical_tests", "Statistical Tests", "Hypothesis tests, model comparisons, permutation tests, bootstrap tests, or significance methods.", True),
            FieldSpec("effect_sizes", "Effect Sizes", "Effect size estimates, differences, odds ratios, hazard ratios, fold changes, or magnitude reporting.", True),
            FieldSpec("confidence_intervals", "Confidence Intervals", "Confidence intervals, credible intervals, uncertainty bands, or bootstrap intervals.", True),
            FieldSpec("multiple_testing_corrections", "Multiple-Testing Corrections", "FDR, Bonferroni, family-wise error control, or rationale for no correction.", True),
            FieldSpec("calibration", "Calibration", "Calibration curves, reliability diagrams, probability calibration, or calibration metrics.", False),
            FieldSpec("robustness_checks", "Robustness Checks", "Stress tests, alternative settings, perturbations, subgroup checks, or repeated seeds.", True),
            FieldSpec("sensitivity_analyses", "Sensitivity Analyses", "Sensitivity to assumptions, preprocessing choices, inclusion criteria, or hyperparameters.", True),
            FieldSpec("ablation_studies", "Ablation Studies", "Ablations isolating components, features, losses, data sources, or design choices.", True),
        ),
    ),
    SectionSpec(
        "validity_and_reproducibility",
        "Validity and Reproducibility",
        (
            FieldSpec("potential_data_leakage", "Potential Data Leakage", "Leakage risks, prevention measures, grouped splitting, temporal leakage, contamination, or unclear safeguards.", True),
            FieldSpec("potential_confounding", "Potential Confounding", "Known or possible confounders and how they were controlled or discussed.", True),
            FieldSpec("statistical_assumptions", "Statistical Assumptions", "Assumptions of tests, models, independence, distribution, censoring, missingness, or exchangeability.", True),
            FieldSpec("methodological_limitations", "Methodological Limitations", "Limitations acknowledged by authors or identified by reviewer.", True),
            FieldSpec("data_availability", "Data Availability", "Whether data are public, restricted, synthetic, proprietary, or unavailable.", True),
            FieldSpec("code_availability", "Code Availability", "Whether source code, scripts, notebooks, or trained models are available.", True),
            FieldSpec("software_environment", "Software Environment", "Software versions, packages, hardware, compute environment, or container details.", False),
            FieldSpec("random_seeds", "Random Seeds", "Random seed reporting, repeated runs, seed sensitivity, or stochasticity handling.", True),
            FieldSpec("reproduction_requirements", "Reproduction Requirements", "Artifacts, protocols, data access steps, compute, or specialized resources required to reproduce.", False),
        ),
    ),
)

AI_ML_SECTION = SectionSpec(
    "ai_ml_specific",
    "AI/ML-Specific Methodology",
    (
        FieldSpec("model_architecture", "Model Architecture", "Architecture, layers, modules, foundation model, or system components.", True, "ai_ml"),
        FieldSpec("objective_function", "Objective Function", "Loss function, reward, likelihood, training target, or optimization objective.", True, "ai_ml"),
        FieldSpec("training_procedure", "Training Procedure", "Training schedule, epochs, batches, data augmentation, stopping, fine-tuning, or pretraining.", True, "ai_ml"),
        FieldSpec("model_selection", "Model Selection", "How final model, checkpoint, method, or configuration was selected.", True, "ai_ml"),
        FieldSpec("compute_reporting", "Compute Reporting", "Hardware, runtime, energy, accelerator, parameter count, or training cost reporting.", False, "ai_ml"),
        FieldSpec("benchmark_contamination", "Benchmark Contamination", "Possible benchmark overlap, pretraining contamination, data reuse, or mitigation.", True, "ai_ml"),
    ),
)

COMP_BIO_SECTION = SectionSpec(
    "computational_biology_specific",
    "Computational Biology and Biomedical-Specific Methodology",
    (
        FieldSpec("biological_system", "Biological System", "Organism, tissue, disease, cell line, pathway, assay system, or biological context.", True, "comp_bio"),
        FieldSpec("specimen_or_assay_type", "Specimen or Assay Type", "Specimen, sample type, omics modality, imaging modality, or assay platform.", True, "comp_bio"),
        FieldSpec("biological_replicates", "Biological Replicates", "Independent biological replicates, patients, animals, cell cultures, or samples.", True, "comp_bio"),
        FieldSpec("technical_replicates", "Technical Replicates", "Repeated measurements of the same biological unit or technical process.", True, "comp_bio"),
        FieldSpec("batch_effects", "Batch Effects", "Batch sources, correction, blocking, randomization, or confounding with outcome.", True, "comp_bio"),
        FieldSpec("patient_level_grouping", "Patient-Level Grouping", "Patient/sample grouping across splits, repeats, lesions, cells, images, or visits.", True, "comp_bio"),
        FieldSpec("feature_dimensionality", "Feature Dimensionality", "Number of genes, proteins, markers, pixels, cells, features, or selected dimensions.", False, "comp_bio"),
        FieldSpec("external_cohort_validation", "External Cohort Validation", "Independent cohort, site, study, or population used for validation.", True, "comp_bio"),
        FieldSpec("pathway_analysis", "Pathway Analysis", "Pathway, enrichment, gene-set, ontology, network, or biological interpretation analyses.", False, "comp_bio"),
        FieldSpec("biological_interpretation", "Biological Interpretation", "Biological meaning assigned to model outputs, biomarkers, mechanisms, or findings.", True, "comp_bio"),
        FieldSpec("translational_limitations", "Translational Limitations", "Clinical, biological, operational, or deployment limitations.", False, "comp_bio"),
    ),
)


def sections_for_domain(domain: str) -> list[SectionSpec]:
    if domain not in DOMAIN_PROFILES:
        raise ValueError(f"Unknown domain profile: {domain}")

    sections = list(COMMON_SECTIONS)
    if domain in {"ai_ml", "biomedical_ai"}:
        sections.append(AI_ML_SECTION)
    if domain in {"comp_bio", "biomedical_ai"}:
        sections.append(COMP_BIO_SECTION)
    return sections


def make_field_record(spec: FieldSpec) -> dict[str, Any]:
    return {
        "key": spec.key,
        "label": spec.label,
        "prompt": spec.prompt,
        "value": None,
        "status": "not_reported",
        "evidence": [],
        "reviewer_notes": "",
        "required_for_review": spec.required,
        "domain": spec.domain,
    }


def make_blueprint(
    *,
    input_ref: str,
    domain: str,
    paper_id: str | None,
    title_hint: str | None,
    source_metadata: dict[str, Any],
) -> dict[str, Any]:
    sections = []
    for section in sections_for_domain(domain):
        sections.append(
            {
                "key": section.key,
                "label": section.label,
                "fields": [make_field_record(field) for field in section.fields],
            }
        )

    return {
        "schema_version": "0.1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run": {
            "tool": "method-extractor",
            "tool_version": __version__,
            "mode": "manual_blueprint_template",
        },
        "paper": {
            "paper_id": paper_id or "",
            "title_hint": title_hint or "",
            "domain_profile": domain,
            "input_ref": input_ref,
        },
        "source": source_metadata,
        "sections": sections,
    }


def iter_fields(blueprint: dict[str, Any]):
    for section in blueprint.get("sections", []):
        for field in section.get("fields", []):
            yield section, field


def validate_blueprint(blueprint: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    if not isinstance(blueprint.get("sections"), list):
        errors.append({"code": "missing_sections", "message": "Blueprint must contain a sections list."})
        return {"valid": False, "errors": errors, "warnings": warnings}

    for section, field in iter_fields(blueprint):
        field_key = str(field.get("key", "<unknown>"))
        section_key = str(section.get("key", "<unknown>"))
        status = field.get("status")
        value = field.get("value")
        evidence = field.get("evidence")

        if status not in STATUS_VALUES:
            errors.append(
                {
                    "code": "invalid_status",
                    "field": field_key,
                    "section": section_key,
                    "message": f"Field '{field_key}' has invalid status '{status}'.",
                }
            )
            continue

        if not isinstance(evidence, list):
            errors.append(
                {
                    "code": "invalid_evidence",
                    "field": field_key,
                    "section": section_key,
                    "message": f"Field '{field_key}' evidence must be a list.",
                }
            )
            continue

        if status in VALUE_EXPECTED_STATUSES and _is_empty(value):
            warnings.append(
                {
                    "code": "missing_value",
                    "field": field_key,
                    "section": section_key,
                    "message": f"Field '{field_key}' is marked {status} but has no value.",
                }
            )

        if status in EVIDENCE_EXPECTED_STATUSES and not evidence:
            warnings.append(
                {
                    "code": "missing_evidence",
                    "field": field_key,
                    "section": section_key,
                    "message": f"Field '{field_key}' is marked {status} but has no supporting evidence.",
                }
            )

        if status == "not_reported" and not _is_empty(value):
            warnings.append(
                {
                    "code": "value_marked_not_reported",
                    "field": field_key,
                    "section": section_key,
                    "message": f"Field '{field_key}' has a value while still marked not_reported.",
                }
            )

        if field.get("required_for_review") is True and status == "not_reported":
            warnings.append(
                {
                    "code": "required_field_not_reported",
                    "field": field_key,
                    "section": section_key,
                    "message": f"Required review field '{field_key}' is still marked not_reported.",
                }
            )

        for index, item in enumerate(evidence):
            if not isinstance(item, dict):
                errors.append(
                    {
                        "code": "invalid_evidence_item",
                        "field": field_key,
                        "section": section_key,
                        "message": f"Evidence item {index} for field '{field_key}' must be an object.",
                    }
                )
                continue
            if _is_empty(item.get("passage")):
                warnings.append(
                    {
                        "code": "evidence_missing_passage",
                        "field": field_key,
                        "section": section_key,
                        "message": f"Evidence item {index} for field '{field_key}' has no passage.",
                    }
                )

    return {"valid": not errors, "errors": errors, "warnings": warnings}


def audit_blueprint(blueprint: dict[str, Any]) -> dict[str, Any]:
    validation = validate_blueprint(blueprint)
    status_counts = {status: 0 for status in STATUS_VALUES}
    total_fields = 0

    for _, field in iter_fields(blueprint):
        total_fields += 1
        status = field.get("status")
        if status in status_counts:
            status_counts[status] += 1

    findings: list[dict[str, Any]] = []
    for error in validation["errors"]:
        findings.append({"severity": "error", "category": "schema", **error})
    for warning in validation["warnings"]:
        severity = "warning"
        if warning["code"] == "required_field_not_reported":
            severity = "info"
        findings.append({"severity": severity, "category": "manual_review", **warning})

    return {
        "schema_version": "0.1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "valid": validation["valid"],
        "summary": {
            "total_fields": total_fields,
            "status_counts": status_counts,
            "error_count": len(validation["errors"]),
            "warning_count": len(validation["warnings"]),
        },
        "findings": findings,
    }


def field_specs_as_dict(domain: str) -> dict[str, Any]:
    return {
        "domain_profile": domain,
        "statuses": list(STATUS_VALUES),
        "sections": [
            {
                "key": section.key,
                "label": section.label,
                "fields": [
                    {
                        "key": field.key,
                        "label": field.label,
                        "prompt": field.prompt,
                        "required_for_review": field.required,
                        "domain": field.domain,
                    }
                    for field in section.fields
                ],
            }
            for section in sections_for_domain(domain)
        ],
    }


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, tuple, dict)) and not value:
        return True
    return False

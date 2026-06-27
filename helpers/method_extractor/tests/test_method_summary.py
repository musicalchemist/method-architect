import unittest

from method_extractor.method_summary import (
    attach_summary_metadata,
    compact_blueprint_for_summary,
    render_method_summary,
)
from method_extractor.schema import make_blueprint


class MethodSummaryTests(unittest.TestCase):
    def test_compact_blueprint_includes_missing_required_fields(self):
        blueprint = make_blueprint(
            input_ref="paper.txt",
            domain="ai_ml",
            paper_id="paper",
            title_hint="Paper",
            source_metadata={},
        )

        compact = compact_blueprint_for_summary(blueprint)

        self.assertEqual(compact["paper"]["paper_id"], "paper")
        self.assertTrue(compact["missing_required_fields"])
        self.assertEqual(compact["sections"][0]["fields"][0]["key"], "title")

    def test_render_method_summary(self):
        blueprint = make_blueprint(
            input_ref="paper.txt",
            domain="ai_ml",
            paper_id="paper",
            title_hint="Paper",
            source_metadata={},
        )
        raw_summary = {
            "paper": {"title": "Paper", "paper_id": "paper", "domain": "ai_ml"},
            "method_theme": "Model scaling with external benchmark evaluation.",
            "research_goal": "Evaluate whether scale improves zero-shot behavior.",
            "design_pattern": "Scaling study plus held-out validation.",
            "design_pattern_tags": ["scaling-study", "zero-shot-evaluation"],
            "experimental_unit": "Token sequence.",
            "data_strategy": "Large web text corpus.",
            "comparison_strategy": "Compare model sizes and literature baselines.",
            "validation_strategy": "Held-out validation and external benchmarks.",
            "evaluation_strategy": "Task metrics and perplexity.",
            "statistical_strategy": "No formal statistical testing reported.",
            "robustness_strategy": "Compare across model sizes.",
            "key_methods": ["Transformer language modeling"],
            "key_metrics": ["perplexity"],
            "reusable_method_ideas": [
                {
                    "idea": "Scale model capacity",
                    "why_it_matters": "Tests whether performance improves with size.",
                    "reusable_pattern": "model-scaling-study",
                    "supporting_blueprint_fields": ["experimental_conditions"],
                }
            ],
            "experiments": [],
            "important_limitations": ["No confidence intervals."],
            "missing_or_unclear": ["Random seeds not reported."],
            "other_important_details": ["Dataset not released."],
            "confidence_notes": "Summary derived from blueprint.",
            "warnings": [],
        }

        summary = attach_summary_metadata(raw_summary, blueprint=blueprint, model="test-model", source="blueprint")
        markdown = render_method_summary(summary)

        self.assertIn("# Method Summary", markdown)
        self.assertIn("Model scaling", markdown)
        self.assertIn("Reusable Method Ideas", markdown)

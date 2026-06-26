import unittest

from method_extractor.schema import audit_blueprint, make_blueprint, validate_blueprint


class SchemaTests(unittest.TestCase):
    def test_new_blueprint_is_valid_but_needs_manual_review(self):
        blueprint = make_blueprint(
            input_ref="paper.pdf",
            domain="biomedical_ai",
            paper_id="paper",
            title_hint="A Paper",
            source_metadata={"source_type": "pdf", "text_characters": 0},
        )

        validation = validate_blueprint(blueprint)
        audit = audit_blueprint(blueprint)

        self.assertTrue(validation["valid"])
        self.assertGreater(audit["summary"]["status_counts"]["not_reported"], 0)
        self.assertTrue(any(item["code"] == "required_field_not_reported" for item in validation["warnings"]))

    def test_reported_field_without_evidence_warns(self):
        blueprint = make_blueprint(
            input_ref="paper.pdf",
            domain="general",
            paper_id="paper",
            title_hint=None,
            source_metadata={"source_type": "pdf", "text_characters": 0},
        )
        first_field = blueprint["sections"][0]["fields"][0]
        first_field["status"] = "reported"
        first_field["value"] = "Example title"

        validation = validate_blueprint(blueprint)

        self.assertTrue(validation["valid"])
        self.assertTrue(any(item["code"] == "missing_evidence" for item in validation["warnings"]))


if __name__ == "__main__":
    unittest.main()

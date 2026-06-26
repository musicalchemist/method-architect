import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from method_extractor.llm import (
    _build_responses_request,
    apply_llm_extraction,
    extraction_response_schema,
    method_summary_response_schema,
)
from method_extractor.schema import make_blueprint


class LLMExtractionTests(unittest.TestCase):
    def test_apply_llm_extraction_populates_matching_field(self):
        blueprint = make_blueprint(
            input_ref="paper.txt",
            domain="general",
            paper_id="paper",
            title_hint="Paper",
            source_metadata={"source_type": "text", "text_characters": 100},
        )
        extraction = {
            "paper_summary": "A small methodology test.",
            "fields": [
                {
                    "section_key": "experimental_design",
                    "field_key": "data_partitioning",
                    "value": "Patient-level train/test split.",
                    "status": "reported",
                    "evidence": [
                        {
                            "passage": "We split train and test sets by patient.",
                            "page": "",
                            "section": "Methods",
                            "source": "source.txt",
                            "quote_is_exact": True,
                        }
                    ],
                    "reviewer_notes": "Explicit split statement.",
                    "confidence": 0.91,
                }
            ],
            "warnings": [],
            "_request_metadata": {
                "generated_at": "2026-01-01T00:00:00+00:00",
                "source_characters_sent": 100,
                "source_was_truncated": False,
            },
        }

        draft = apply_llm_extraction(blueprint, extraction, model="test-model")
        target = None
        for section in draft["sections"]:
            for field in section["fields"]:
                if field["key"] == "data_partitioning":
                    target = field

        self.assertIsNotNone(target)
        self.assertEqual(target["status"], "reported")
        self.assertEqual(target["value"], "Patient-level train/test split.")
        self.assertEqual(target["extraction_source"], "openai_llm_draft")
        self.assertEqual(draft["run"]["mode"], "llm_draft_extraction")

    def test_extraction_response_schema_is_strict_object(self):
        blueprint = make_blueprint(
            input_ref="paper.txt",
            domain="ai_ml",
            paper_id="paper",
            title_hint="Paper",
            source_metadata={},
        )

        schema = extraction_response_schema(blueprint)

        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema["additionalProperties"])
        self.assertIn("fields", schema["required"])
        field_schema = schema["properties"]["fields"]["items"]
        self.assertFalse(field_schema["additionalProperties"])

    def test_pdf_request_uses_input_file_content(self):
        with TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "paper.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n% fake pdf for request-shape test\n")
            blueprint = make_blueprint(
                input_ref=str(pdf_path),
                domain="general",
                paper_id="paper",
                title_hint="Paper",
                source_metadata={"source_type": "pdf", "stored_path": str(pdf_path)},
            )

            request = _build_responses_request(
                blueprint=blueprint,
                source_text="",
                sections=[],
                pdf_path=pdf_path,
                model="test-model",
                max_chars=60000,
                was_truncated=False,
            )

            user_content = request["input"][1]["content"]
            self.assertEqual(user_content[1]["type"], "input_file")
            self.assertEqual(user_content[1]["filename"], "paper.pdf")
            self.assertTrue(user_content[1]["file_data"].startswith("data:application/pdf;base64,"))

    def test_method_summary_response_schema_is_strict_object(self):
        schema = method_summary_response_schema()

        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema["additionalProperties"])
        self.assertIn("method_theme", schema["required"])
        self.assertFalse(schema["properties"]["paper"]["additionalProperties"])


if __name__ == "__main__":
    unittest.main()

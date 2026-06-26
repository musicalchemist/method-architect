import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from method_extractor.run_index import append_run_index, search_run_index
from method_extractor.schema import audit_blueprint, make_blueprint


class RunIndexTests(unittest.TestCase):
    def test_append_and_search_index(self):
        with TemporaryDirectory() as temp_dir:
            runs_dir = Path(temp_dir) / "runs"
            run_dir = runs_dir / "20260101-paper"
            run_dir.mkdir(parents=True)
            blueprint = make_blueprint(
                input_ref="paper.pdf",
                domain="biomedical_ai",
                paper_id="doi-123",
                title_hint="Important Paper",
                source_metadata={"source_type": "pdf"},
            )
            audit = audit_blueprint(blueprint)

            append_run_index(
                runs_dir=runs_dir,
                run_dir=run_dir,
                blueprint=blueprint,
                audit=audit,
                llm_requested=True,
                llm_succeeded=True,
            )

            records = search_run_index(runs_dir, "important")

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["paper_id"], "doi-123")
            self.assertTrue(records[0]["llm_succeeded"])


if __name__ == "__main__":
    unittest.main()

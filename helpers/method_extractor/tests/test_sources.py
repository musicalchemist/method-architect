import unittest
from pathlib import Path

from method_extractor.sources import load_source, sectionize_text


class SourceTests(unittest.TestCase):
    def test_load_local_text_and_sectionize(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paper = root / "paper.txt"
            paper.write_text(
                "Abstract\nThis is a test paper.\n\nMethods\nWe used a held-out test set.\n\nResults\nIt worked.\n",
                encoding="utf-8",
            )

            document = load_source(str(paper), root / "source")
            sections = sectionize_text(document.text)

            self.assertEqual(document.source_type, "text")
            self.assertTrue(document.text.startswith("Abstract"))
            self.assertTrue(any(section["heading"] == "Methods" for section in sections))
            self.assertTrue(any(section["method_candidate"] for section in sections))


if __name__ == "__main__":
    unittest.main()

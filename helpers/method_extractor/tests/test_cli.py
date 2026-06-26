import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CliTests(unittest.TestCase):
    def test_cli_extract_text_smoke(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paper = root / "paper.txt"
            paper.write_text("Title\n\nMethods\nWe split data by patient.\n", encoding="utf-8")
            out = root / "runs"

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "method_extractor",
                    "extract",
                    str(paper),
                    "--domain",
                    "comp_bio",
                    "--out",
                    str(out),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("Created Method Blueprint workspace", result.stdout)
            run_dirs = [path for path in out.iterdir() if path.is_dir()]
            self.assertEqual(len(run_dirs), 1)
            blueprint = json.loads((run_dirs[0] / "blueprint.json").read_text(encoding="utf-8"))
            self.assertEqual(blueprint["paper"]["domain_profile"], "comp_bio")
            self.assertTrue((run_dirs[0] / "report.md").exists())


if __name__ == "__main__":
    unittest.main()

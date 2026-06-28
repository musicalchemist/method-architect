import json
import shutil
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

    def test_dashboard_help_includes_browser_flags(self):
        result = subprocess.run(
            [sys.executable, "-m", "method_extractor", "dashboard", "--help"],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("--open-browser", result.stdout)
        self.assertIn("--no-open-browser", result.stdout)
        self.assertIn("--no-auto-port", result.stdout)

    def test_dashboard_launchers_have_cleanup_traps(self):
        if shutil.which("zsh") is None:
            self.skipTest("zsh is not available")

        root = Path(__file__).resolve().parents[1]
        launcher = root / "bin" / "method-dashboard"
        command = root / "bin" / "method-dashboard.command"

        for path in (launcher, command):
            subprocess.run(["zsh", "-n", str(path)], check=True, capture_output=True, text=True)

        launcher_text = launcher.read_text(encoding="utf-8")
        self.assertIn("trap cleanup EXIT INT TERM HUP", launcher_text)
        self.assertIn("stop_process_tree", launcher_text)
        self.assertIn("stop_known_dashboard_port", launcher_text)
        self.assertIn("DASHBOARD_PORT_SEARCH_LIMIT", launcher_text)


if __name__ == "__main__":
    unittest.main()

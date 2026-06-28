import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from method_extractor.dashboard import (
    DashboardConfig,
    ParsedForm,
    UploadedFile,
    _extract_run_dir,
    _prepare_input_ref,
    _render_dashboard_page,
    _select_dashboard_port,
    parse_form_data,
)


class DashboardTests(unittest.TestCase):
    def test_parse_urlencoded_form(self):
        parsed = parse_form_data(
            "application/x-www-form-urlencoded",
            b"domain=ai_ml&provider=openai&summarize=on",
        )

        self.assertEqual(parsed.fields["domain"], "ai_ml")
        self.assertEqual(parsed.fields["provider"], "openai")
        self.assertEqual(parsed.fields["summarize"], "on")
        self.assertEqual(parsed.files, {})

    def test_parse_multipart_upload(self):
        boundary = "----method-boundary"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="domain"\r\n\r\n'
            "ai_ml\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="source_file"; filename="paper.txt"\r\n'
            "Content-Type: text/plain\r\n\r\n"
            "Methods text\r\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")

        parsed = parse_form_data(f"multipart/form-data; boundary={boundary}", body)

        self.assertEqual(parsed.fields["domain"], "ai_ml")
        self.assertIn("source_file", parsed.files)
        self.assertEqual(parsed.files["source_file"].filename, "paper.txt")
        self.assertEqual(parsed.files["source_file"].data, b"Methods text")

    def test_prepare_raw_text_input_writes_ignored_upload_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = DashboardConfig(helper_root=Path(temp_dir))
            parsed = ParsedForm(
                fields={"raw_text": "Methods\nWe compare baselines.", "title": "My Test Paper"},
                files={},
            )

            input_ref, input_kind = _prepare_input_ref(parsed, config)

            self.assertEqual(input_kind, "raw_text")
            path = Path(input_ref)
            self.assertTrue(path.exists())
            self.assertEqual(path.parent.name, "dashboard_uploads")
            self.assertIn("my-test-paper", path.name)

    def test_prepare_upload_sanitizes_filename(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = DashboardConfig(helper_root=Path(temp_dir))
            parsed = ParsedForm(
                fields={},
                files={"source_file": UploadedFile("../paper?.txt", "text/plain", b"Methods")},
            )

            input_ref, input_kind = _prepare_input_ref(parsed, config)

            self.assertEqual(input_kind, "upload")
            path = Path(input_ref)
            self.assertTrue(path.exists())
            self.assertNotIn("..", path.name)
            self.assertNotIn("?", path.name)

    def test_extract_run_dir_from_cli_output(self):
        stdout = "Created Method Blueprint workspace: /tmp/runs/20260626-paper\nBlueprint: /tmp/runs/20260626-paper/blueprint.json\n"

        self.assertEqual(_extract_run_dir(stdout), Path("/tmp/runs/20260626-paper"))

    def test_dashboard_page_includes_provider_and_summary_controls(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = DashboardConfig(helper_root=Path(temp_dir))
            html = _render_dashboard_page(config)

        self.assertIn("LLM provider", html)
        self.assertIn("Create method summary after blueprint", html)
        self.assertIn("Recent Summaries", html)
        self.assertIn('/favicon.svg', html)
        self.assertIn("[hidden] { display: none !important; }", html)
        self.assertIn('class="processing-overlay"', html)
        self.assertIn('role="dialog"', html)
        self.assertIn("processing-pill", html)
        self.assertIn("backdrop-filter", html)
        self.assertIn('document.body.classList.add("is-processing")', html)
        self.assertIn('document.body.classList.remove("is-processing")', html)
        self.assertIn("align-items: start;", html)
        self.assertIn("align-items: flex-start;", html)
        self.assertIn("display: inline-flex;", html)

    def test_select_dashboard_port_skips_busy_port(self):
        with patch(
            "method_extractor.dashboard._port_is_available",
            side_effect=[False, True],
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                selected = _select_dashboard_port(host="127.0.0.1", preferred_port=8765, auto_port=True)

        self.assertEqual(selected, 8766)

    def test_select_dashboard_port_can_disable_auto_port(self):
        with patch(
            "method_extractor.dashboard._port_is_available",
            side_effect=AssertionError("port probe should not run when auto_port is disabled"),
        ):
            selected = _select_dashboard_port(host="127.0.0.1", preferred_port=8765, auto_port=False)

        self.assertEqual(selected, 8765)


if __name__ == "__main__":
    unittest.main()

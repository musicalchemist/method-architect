from __future__ import annotations

import json
import mimetypes
import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from email import policy
from email.parser import BytesParser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .llm import DEFAULT_API_KEY_ENV, DEFAULT_MODEL
from .schema import DOMAIN_PROFILES


HELPER_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_PORT_SEARCH_LIMIT = 35
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_BODY_BYTES = MAX_UPLOAD_BYTES + (2 * 1024 * 1024)
ALLOWED_ARTIFACTS = {
    "audit.json",
    "blueprint.json",
    "llm_extraction.json",
    "method_summary.json",
    "method_summary.md",
    "report.md",
}
FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="g" x1="8" y1="56" x2="56" y2="8" gradientUnits="userSpaceOnUse">
      <stop stop-color="#126a66"/>
      <stop offset="0.58" stop-color="#1d9a8f"/>
      <stop offset="1" stop-color="#8a4b2a"/>
    </linearGradient>
  </defs>
  <rect width="64" height="64" rx="14" fill="#f7f5ef"/>
  <path d="M17 50 30 14h8l13 36h-8l-3-9H28l-3 9h-8Zm13-16h8l-4-12-4 12Z" fill="url(#g)"/>
  <path d="M25 50h18" stroke="#1d2524" stroke-width="4" stroke-linecap="round"/>
</svg>"""


@dataclass(frozen=True)
class DashboardConfig:
    helper_root: Path = HELPER_ROOT
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT

    @property
    def papers_dir(self) -> Path:
        return self.helper_root / "papers"

    @property
    def runs_dir(self) -> Path:
        return self.helper_root / "runs"

    @property
    def uploads_dir(self) -> Path:
        return self.papers_dir / "dashboard_uploads"


@dataclass(frozen=True)
class UploadedFile:
    filename: str
    content_type: str
    data: bytes


@dataclass(frozen=True)
class ParsedForm:
    fields: dict[str, str]
    files: dict[str, UploadedFile]


class DashboardError(RuntimeError):
    pass


def run_dashboard(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    open_browser: bool = False,
    auto_port: bool = True,
) -> int:
    port = _select_dashboard_port(host=host, preferred_port=port, auto_port=auto_port)
    config = DashboardConfig(host=host, port=port)
    config.papers_dir.mkdir(parents=True, exist_ok=True)
    config.runs_dir.mkdir(parents=True, exist_ok=True)
    config.uploads_dir.mkdir(parents=True, exist_ok=True)

    server = ThreadingHTTPServer((host, port), _make_handler(config))
    url = f"http://{host}:{port}"
    print(f"Method Extractor dashboard: {url}")
    print("Press Ctrl+C to stop.")

    previous_handlers = _install_signal_handlers(server)

    if open_browser:
        try:
            webbrowser.open(url)
        except Exception as exc:  # noqa: BLE001 - browser launch should not stop the server.
            print(f"Could not open browser automatically: {exc}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard.")
    finally:
        _restore_signal_handlers(previous_handlers)
        server.server_close()
    return 0


def _select_dashboard_port(*, host: str, preferred_port: int, auto_port: bool) -> int:
    if not auto_port:
        return preferred_port

    for port in range(preferred_port, preferred_port + DEFAULT_PORT_SEARCH_LIMIT):
        if _port_is_available(host, port):
            if port != preferred_port:
                print(f"Port {preferred_port} is busy; using {port} instead.")
            return port

    end_port = preferred_port + DEFAULT_PORT_SEARCH_LIMIT - 1
    raise DashboardError(f"No available dashboard port found from {preferred_port} to {end_port}.")


def _port_is_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


def _install_signal_handlers(server: ThreadingHTTPServer) -> dict[int, Any]:
    previous_handlers: dict[int, Any] = {}

    def handle_signal(signum: int, _frame: Any) -> None:
        server.server_close()
        raise KeyboardInterrupt

    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        previous_handlers[signum] = signal.getsignal(signum)
        signal.signal(signum, handle_signal)

    return previous_handlers


def _restore_signal_handlers(previous_handlers: dict[int, Any]) -> None:
    for signum, handler in previous_handlers.items():
        signal.signal(signum, handler)


def run_extraction_from_form(parsed: ParsedForm, config: DashboardConfig) -> dict[str, Any]:
    provider = _field(parsed, "provider", "openai")
    if provider != "openai":
        raise DashboardError("Only the OpenAI provider is currently supported.")

    api_key_env = _field(parsed, "api_key_env", DEFAULT_API_KEY_ENV)
    if not os.environ.get(api_key_env):
        raise DashboardError(
            f"Missing API key environment variable: {api_key_env}. "
            "Start the dashboard from a shell that exports this variable."
        )

    input_ref, input_kind = _prepare_input_ref(parsed, config)
    domain = _field(parsed, "domain", "general")
    if domain not in DOMAIN_PROFILES:
        raise DashboardError(f"Unsupported domain profile: {domain}")

    model = _field(parsed, "model", DEFAULT_MODEL)
    summarize = _field(parsed, "summarize", "") == "on"
    pdf_input = _field(parsed, "pdf_input", "auto")
    if pdf_input not in {"auto", "direct", "text"}:
        raise DashboardError(f"Unsupported PDF input mode: {pdf_input}")

    command = [
        sys.executable,
        "-m",
        "method_extractor",
        "extract",
        input_ref,
        "--domain",
        domain,
        "--out",
        str(config.runs_dir),
        "--llm",
        "--model",
        model,
        "--api-key-env",
        api_key_env,
        "--max-chars",
        _field(parsed, "max_chars", "60000"),
        "--pdf-input",
        pdf_input,
    ]

    title = _field(parsed, "title", "")
    paper_id = _field(parsed, "paper_id", "")
    if title:
        command.extend(["--title", title])
    if paper_id:
        command.extend(["--paper-id", paper_id])
    if summarize:
        command.append("--summarize")
        summary_model = _field(parsed, "summary_model", "")
        if summary_model:
            command.extend(["--summary-model", summary_model])

    start = time.monotonic()
    result = subprocess.run(
        command,
        cwd=config.helper_root,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    elapsed_seconds = round(time.monotonic() - start, 1)

    run_dir = _extract_run_dir(result.stdout)
    summary = _read_json_if_exists(run_dir / "method_summary.json") if run_dir else None
    audit = _read_json_if_exists(run_dir / "audit.json") if run_dir else None

    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "elapsed_seconds": elapsed_seconds,
        "input_kind": input_kind,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "run": _run_payload(run_dir, config) if run_dir else None,
        "summary": summary,
        "audit_summary": audit.get("summary", {}) if isinstance(audit, dict) else None,
    }


def _make_handler(config: DashboardConfig) -> type[BaseHTTPRequestHandler]:
    class DashboardHandler(BaseHTTPRequestHandler):
        server_version = "MethodExtractorDashboard/0.1"

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/":
                self._send_html(_render_dashboard_page(config))
                return
            if parsed.path == "/favicon.svg":
                self._send_svg(FAVICON_SVG)
                return
            if parsed.path == "/artifact":
                self._send_artifact(parsed.query)
                return
            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/api/extract":
                self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
                return

            try:
                content_length = int(self.headers.get("content-length", "0"))
            except ValueError:
                content_length = 0

            if content_length > MAX_BODY_BYTES:
                self._send_json(
                    {"error": f"Upload is too large. Limit is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."},
                    status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                )
                return

            try:
                body = self.rfile.read(content_length)
                parsed_form = parse_form_data(self.headers.get("content-type", ""), body)
                payload = run_extraction_from_form(parsed_form, config)
                status = HTTPStatus.OK if payload["ok"] else HTTPStatus.BAD_GATEWAY
                self._send_json(payload, status=status)
            except subprocess.TimeoutExpired:
                self._send_json(
                    {"error": "Extraction timed out after 15 minutes. Check the terminal and try a smaller source."},
                    status=HTTPStatus.GATEWAY_TIMEOUT,
                )
            except Exception as exc:  # noqa: BLE001 - local dashboard should return readable errors.
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

        def log_message(self, fmt: str, *args: Any) -> None:
            print(f"[dashboard] {self.address_string()} - {fmt % args}")

        def _send_json(self, payload: dict[str, Any], *, status: HTTPStatus = HTTPStatus.OK) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_html(self, html: str) -> None:
            data = html.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_svg(self, svg: str) -> None:
            data = svg.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
            self.send_header("Cache-Control", "public, max-age=86400")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_artifact(self, query: str) -> None:
            params = urllib.parse.parse_qs(query)
            run_name = Path(params.get("run", [""])[0]).name
            filename = params.get("file", [""])[0]
            if not run_name or filename not in ALLOWED_ARTIFACTS:
                self._send_json({"error": "Artifact is not available."}, status=HTTPStatus.NOT_FOUND)
                return

            path = config.runs_dir / run_name / filename
            if not path.exists() or not path.is_file():
                self._send_json({"error": "Artifact is not available."}, status=HTTPStatus.NOT_FOUND)
                return

            data = path.read_bytes()
            content_type = mimetypes.guess_type(path.name)[0] or "text/plain"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return DashboardHandler


def parse_form_data(content_type: str, body: bytes) -> ParsedForm:
    if content_type.startswith("application/x-www-form-urlencoded"):
        decoded = body.decode("utf-8", errors="replace")
        parsed = urllib.parse.parse_qs(decoded, keep_blank_values=True)
        return ParsedForm(fields={key: values[-1] for key, values in parsed.items()}, files={})

    if not content_type.startswith("multipart/form-data"):
        raise DashboardError("Expected multipart form data.")

    header = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
    message = BytesParser(policy=policy.default).parsebytes(header + body)
    fields: dict[str, str] = {}
    files: dict[str, UploadedFile] = {}

    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue

        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename:
            files[name] = UploadedFile(
                filename=filename,
                content_type=part.get_content_type(),
                data=payload,
            )
            continue

        charset = part.get_content_charset() or "utf-8"
        fields[name] = payload.decode(charset, errors="replace")

    return ParsedForm(fields=fields, files=files)


def _prepare_input_ref(parsed: ParsedForm, config: DashboardConfig) -> tuple[str, str]:
    uploaded = parsed.files.get("source_file")
    if uploaded and uploaded.data:
        if len(uploaded.data) > MAX_UPLOAD_BYTES:
            raise DashboardError(f"Uploaded file is too large. Limit is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
        path = _save_uploaded_file(uploaded, config.uploads_dir)
        return str(path), "upload"

    url = _field(parsed, "website_url", "")
    if url:
        if not url.startswith(("http://", "https://")):
            raise DashboardError("Website URL must start with http:// or https://.")
        return url, "url"

    raw_text = _field(parsed, "raw_text", "")
    if raw_text:
        path = _save_raw_text(raw_text, config.uploads_dir, _field(parsed, "title", "") or _field(parsed, "paper_id", ""))
        return str(path), "raw_text"

    raise DashboardError("Provide a file upload, website URL, or raw text.")


def _save_uploaded_file(uploaded: UploadedFile, uploads_dir: Path) -> Path:
    uploads_dir.mkdir(parents=True, exist_ok=True)
    filename = _safe_filename(uploaded.filename)
    path = uploads_dir / f"{_timestamp()}-{filename}"
    path.write_bytes(uploaded.data)
    return path


def _save_raw_text(raw_text: str, uploads_dir: Path, title_hint: str) -> Path:
    uploads_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(title_hint or "raw-text")
    path = uploads_dir / f"{_timestamp()}-{slug}.txt"
    path.write_text(raw_text, encoding="utf-8")
    return path


def _field(parsed: ParsedForm, key: str, default: str) -> str:
    value = parsed.fields.get(key, default)
    return value.strip() if isinstance(value, str) else default


def _safe_filename(filename: str) -> str:
    name = Path(filename.replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._ -]+", "-", name).strip(" .-")
    return name[:120] or "upload.txt"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-").lower()
    return slug[:80] or "paper"


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _extract_run_dir(stdout: str) -> Path | None:
    prefixes = (
        "Created Method Blueprint workspace:",
        "Created Method Blueprint workspace without LLM draft:",
    )
    for line in stdout.splitlines():
        for prefix in prefixes:
            if line.startswith(prefix):
                return Path(line.removeprefix(prefix).strip())
        if line.startswith("Blueprint:"):
            return Path(line.removeprefix("Blueprint:").strip()).parent
    return None


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _run_payload(run_dir: Path, config: DashboardConfig) -> dict[str, Any]:
    run_name = run_dir.name
    try:
        run_path = str(run_dir.relative_to(config.helper_root))
    except ValueError:
        run_path = str(run_dir)

    return {
        "name": run_name,
        "path": run_path,
        "artifacts": [
            {
                "label": label,
                "url": f"/artifact?run={urllib.parse.quote(run_name)}&file={urllib.parse.quote(filename)}",
            }
            for label, filename in [
                ("Method Summary JSON", "method_summary.json"),
                ("Method Summary Markdown", "method_summary.md"),
                ("Blueprint JSON", "blueprint.json"),
                ("Blueprint Report", "report.md"),
                ("Audit JSON", "audit.json"),
            ]
            if (run_dir / filename).exists()
        ],
    }


def _recent_summary_records(runs_dir: Path, limit: int = 8) -> list[dict[str, Any]]:
    index_path = runs_dir / "method_summaries.jsonl"
    if not index_path.exists():
        return []

    records: list[dict[str, Any]] = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(records[-limit:]))


def _render_dashboard_page(config: DashboardConfig) -> str:
    recent = _recent_summary_records(config.runs_dir)
    domain_options = "\n".join(
        f'<option value="{domain}"{" selected" if domain == "ai_ml" else ""}>{domain}</option>'
        for domain in DOMAIN_PROFILES
    )
    recent_html = _render_recent_summaries(recent)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Method Extractor Dashboard</title>
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <style>{_dashboard_css()}</style>
</head>
<body>
  <main class="shell">
    <header class="hero">
      <div>
        <p class="eyebrow">Method Architect Helper</p>
        <h1>Method Extraction Dashboard</h1>
        <p class="lede">Run the local two-pass workflow: source to detailed blueprint, then blueprint to compact method summary.</p>
      </div>
      <div class="status-pill">Local only</div>
    </header>

    <section class="panel">
      <form id="extract-form">
        <div class="form-grid">
          <label>
            <span>Paper or text file</span>
            <input type="file" name="source_file" accept=".pdf,.txt,.md,.html,.htm">
          </label>
          <label>
            <span>Website URL</span>
            <input type="url" name="website_url" placeholder="https://arxiv.org/pdf/...">
          </label>
          <label class="wide">
            <span>Raw text</span>
            <textarea name="raw_text" rows="7" placeholder="Paste abstract, methods, or full text here"></textarea>
          </label>
          <label>
            <span>Domain</span>
            <select name="domain">{domain_options}</select>
          </label>
          <label>
            <span>LLM provider</span>
            <select name="provider">
              <option value="openai" selected>OpenAI</option>
            </select>
          </label>
          <label>
            <span>Blueprint model</span>
            <input type="text" name="model" value="{DEFAULT_MODEL}">
          </label>
          <label>
            <span>Summary model</span>
            <input type="text" name="summary_model" placeholder="default: blueprint model">
          </label>
          <label>
            <span>Paper title hint</span>
            <input type="text" name="title" placeholder="optional">
          </label>
          <label>
            <span>Paper ID</span>
            <input type="text" name="paper_id" placeholder="optional, e.g. arXiv:1901.04587">
          </label>
          <label>
            <span>PDF mode</span>
            <select name="pdf_input">
              <option value="auto" selected>Auto</option>
              <option value="direct">Direct PDF to OpenAI</option>
              <option value="text">Text extraction only</option>
            </select>
          </label>
          <label>
            <span>Max text chars</span>
            <input type="number" name="max_chars" value="60000" min="1000" step="1000">
          </label>
          <label>
            <span>API key env</span>
            <input type="text" name="api_key_env" value="{DEFAULT_API_KEY_ENV}">
          </label>
        </div>

        <div class="actions">
          <label class="checkbox">
            <input type="checkbox" name="summarize" checked>
            <span>Create method summary after blueprint</span>
          </label>
          <button type="submit">Run extraction</button>
        </div>
      </form>
    </section>

    <div class="processing-overlay" id="status-panel" role="dialog" aria-modal="true" aria-live="polite" hidden>
      <div class="processing-pill">
        <div class="spinner" aria-hidden="true"></div>
        <h2 id="status-title">Running extraction</h2>
        <p id="status-message">Calling OpenAI for the blueprint and summary. Larger PDFs can take a few minutes.</p>
      </div>
    </div>

    <section id="result" class="result"></section>

    <section class="recent">
      <div class="section-heading">
        <h2>Recent Summaries</h2>
        <p>Generated summaries stay in <code>helpers/method_extractor/runs/</code>.</p>
      </div>
      {recent_html}
    </section>
  </main>
  <script>{_dashboard_js()}</script>
</body>
</html>"""


def _render_recent_summaries(records: list[dict[str, Any]]) -> str:
    if not records:
        return '<p class="empty">No method summaries indexed yet.</p>'

    items: list[str] = []
    for record in records:
        title = _html_escape(record.get("title") or "Untitled paper")
        paper_id = _html_escape(record.get("paper_id") or "unset")
        domain = _html_escape(record.get("domain") or "unknown")
        theme = _html_escape(record.get("method_theme") or "")
        run_name = _html_escape(record.get("run_name") or "")
        items.append(
            f"""<article class="recent-item">
  <div>
    <h3>{title}</h3>
    <p>{theme}</p>
  </div>
  <dl>
    <div><dt>Paper ID</dt><dd>{paper_id}</dd></div>
    <div><dt>Domain</dt><dd>{domain}</dd></div>
    <div><dt>Run</dt><dd>{run_name}</dd></div>
  </dl>
</article>"""
        )
    return '<div class="recent-list">' + "\n".join(items) + "</div>"


def _html_escape(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _dashboard_css() -> str:
    return """
:root {
  color-scheme: light;
  --bg: #f7f5ef;
  --ink: #1d2524;
  --muted: #60706d;
  --line: #d7ddd5;
  --panel: #ffffff;
  --accent: #126a66;
  --accent-2: #8a4b2a;
  --soft: #eef4f1;
  --warn: #fff4d8;
  --danger: #ffe8e2;
}
* { box-sizing: border-box; }
[hidden] { display: none !important; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.5;
}
button, input, select, textarea { font: inherit; }
.shell {
  width: min(1180px, calc(100% - 32px));
  margin: 0 auto;
  padding: 32px 0 56px;
}
.hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
}
.eyebrow {
  margin: 0 0 6px;
  color: var(--accent);
  font-size: 0.78rem;
  font-weight: 800;
  text-transform: uppercase;
}
h1, h2, h3, p { margin-top: 0; }
h1 {
  margin-bottom: 8px;
  font-size: clamp(2rem, 4vw, 3.6rem);
  line-height: 1.05;
}
.lede {
  max-width: 760px;
  color: var(--muted);
  font-size: 1.05rem;
}
.status-pill {
  min-width: max-content;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 8px 12px;
  background: var(--soft);
  color: var(--accent);
  font-size: 0.9rem;
  font-weight: 700;
}
.panel, .summary-visual, .recent-item {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
}
.panel { padding: 22px; }
.form-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}
label { display: grid; gap: 7px; color: var(--muted); font-size: 0.9rem; font-weight: 700; }
input, select, textarea {
  width: 100%;
  border: 1px solid #c7d0c8;
  border-radius: 6px;
  background: #fff;
  color: var(--ink);
  padding: 10px 11px;
}
textarea { resize: vertical; }
.wide { grid-column: 1 / -1; }
.actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 18px;
}
.checkbox {
  display: flex;
  grid-template-columns: none;
  align-items: center;
  gap: 10px;
  color: var(--ink);
}
.checkbox input { width: 18px; height: 18px; }
button {
  border: 0;
  border-radius: 6px;
  background: var(--accent);
  color: #fff;
  padding: 11px 16px;
  font-weight: 800;
  cursor: pointer;
}
button[disabled] { cursor: wait; opacity: 0.65; }
.is-processing { overflow: hidden; }
.processing-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(29, 37, 36, 0.34);
  backdrop-filter: blur(2px) saturate(0.82);
}
.processing-pill {
  display: inline-grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 12px;
  width: min(520px, 100%);
  border: 1px solid rgba(215, 221, 213, 0.92);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 22px 70px rgba(29, 37, 36, 0.22);
  padding: 14px 18px;
}
.processing-pill h2 { margin-bottom: 2px; font-size: 1rem; }
.processing-pill p { grid-column: 2; margin-bottom: 0; color: var(--muted); }
.spinner {
  width: 34px;
  height: 34px;
  border: 3px solid var(--line);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.result { margin-top: 22px; }
.summary-visual { overflow: hidden; }
.summary-header {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: start;
  gap: 16px;
  padding: 20px 22px;
  border-bottom: 1px solid var(--line);
  background: #fbfcfa;
}
.summary-header h2 { margin-bottom: 5px; font-size: 1.45rem; }
.meta { color: var(--muted); font-size: 0.92rem; }
.artifact-links {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: flex-end;
  gap: 8px;
}
.artifact-links a, .tag {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 6px 9px;
  background: var(--soft);
  color: var(--accent);
  text-decoration: none;
  font-size: 0.84rem;
  font-weight: 700;
}
.summary-body { display: grid; gap: 20px; padding: 22px; }
.theme-grid, .strategy-grid, .two-column {
  display: grid;
  gap: 14px;
}
.theme-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.strategy-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.two-column { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.block {
  border-left: 3px solid var(--accent);
  padding-left: 12px;
}
.block h3, .mini h3 { margin-bottom: 5px; font-size: 0.95rem; }
.block p, .mini p, li { color: var(--muted); }
.mini {
  background: #fbfcfa;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 13px;
}
.tag-row { display: flex; flex-wrap: wrap; gap: 8px; }
ul { margin: 0; padding-left: 19px; }
.ideas, .experiments, .recent-list { display: grid; gap: 12px; }
.idea, .experiment {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 14px;
  background: #fff;
}
.idea h3, .experiment h3 { margin-bottom: 8px; font-size: 1rem; }
.run-log {
  margin-top: 14px;
  border-radius: 8px;
  background: #17211f;
  color: #dce8e3;
  padding: 14px;
  white-space: pre-wrap;
  overflow: auto;
  max-height: 280px;
}
.notice {
  border-radius: 8px;
  padding: 14px;
  background: var(--warn);
  border: 1px solid #ead28c;
}
.error {
  border-radius: 8px;
  padding: 14px;
  background: var(--danger);
  border: 1px solid #e4afa2;
}
.recent { margin-top: 32px; }
.section-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
}
.section-heading h2 { margin-bottom: 6px; }
.section-heading p, .empty { color: var(--muted); }
.recent-item {
  display: grid;
  grid-template-columns: 1fr minmax(240px, 0.45fr);
  gap: 16px;
  padding: 16px;
}
.recent-item h3 { margin-bottom: 5px; font-size: 1rem; }
dl {
  display: grid;
  gap: 6px;
  margin: 0;
}
dt {
  color: var(--muted);
  font-size: 0.76rem;
  font-weight: 800;
  text-transform: uppercase;
}
dd { margin: 0 0 4px; overflow-wrap: anywhere; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
@media (max-width: 900px) {
  .hero, .actions, .summary-header, .section-heading { display: grid; }
  .form-grid, .theme-grid, .strategy-grid, .two-column, .recent-item { grid-template-columns: 1fr; }
  .artifact-links { justify-content: flex-start; }
  .processing-pill { border-radius: 24px; }
}
"""


def _dashboard_js() -> str:
    return """
const form = document.getElementById("extract-form");
const statusPanel = document.getElementById("status-panel");
const statusTitle = document.getElementById("status-title");
const statusMessage = document.getElementById("status-message");
const result = document.getElementById("result");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = form.querySelector("button[type='submit']");
  button.disabled = true;
  result.replaceChildren();
  showProcessing();

  try {
    const response = await fetch("/api/extract", { method: "POST", body: new FormData(form) });
    const payload = await response.json();
    hideProcessing();
    if (!response.ok || !payload.ok) {
      renderError(payload);
      return;
    }
    renderResult(payload);
  } catch (error) {
    hideProcessing();
    renderError({ error: error.message || String(error) });
  } finally {
    button.disabled = false;
  }
});

function showProcessing() {
  statusTitle.textContent = "Running extraction";
  statusMessage.textContent = "Calling OpenAI for the blueprint and summary. Larger PDFs can take a few minutes.";
  document.body.classList.add("is-processing");
  statusPanel.hidden = false;
}

function hideProcessing() {
  statusPanel.hidden = true;
  document.body.classList.remove("is-processing");
}

function renderError(payload) {
  const box = el("div", "error");
  box.append(el("h2", "", "Extraction did not finish"));
  box.append(el("p", "", payload.error || "The dashboard received an unsuccessful response."));
  if (payload.stdout || payload.stderr) {
    box.append(logBlock([payload.stdout, payload.stderr].filter(Boolean).join("\\n")));
  }
  result.replaceChildren(box);
}

function renderResult(payload) {
  const summary = payload.summary;
  const run = payload.run || {};
  const wrap = el("article", "summary-visual");
  const header = el("div", "summary-header");
  const titleWrap = el("div");
  const paper = (summary && summary.paper) || {};
  titleWrap.append(el("h2", "", paper.title || "Method summary created"));
  titleWrap.append(el("p", "meta", `${paper.paper_id || "unset"} | ${paper.domain || "unknown domain"} | ${run.path || ""}`));
  const links = el("div", "artifact-links");
  (run.artifacts || []).forEach((artifact) => {
    const link = document.createElement("a");
    link.href = artifact.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = artifact.label;
    links.append(link);
  });
  header.append(titleWrap, links);
  wrap.append(header);

  const body = el("div", "summary-body");
  if (!summary) {
    const notice = el("div", "notice");
    notice.append(el("h2", "", "Blueprint created without a method summary"));
    notice.append(el("p", "", "Check the run artifacts for the blueprint and report."));
    body.append(notice);
  } else {
    const themeGrid = el("div", "theme-grid");
    themeGrid.append(textBlock("Method theme", summary.method_theme));
    themeGrid.append(textBlock("Design pattern", summary.design_pattern));
    body.append(themeGrid);
    body.append(tagRow(summary.design_pattern_tags || []));

    const strategyGrid = el("div", "strategy-grid");
    strategyGrid.append(textMini("Research goal", summary.research_goal));
    strategyGrid.append(textMini("Experimental unit", summary.experimental_unit));
    strategyGrid.append(textMini("Data strategy", summary.data_strategy));
    strategyGrid.append(textMini("Comparison strategy", summary.comparison_strategy));
    strategyGrid.append(textMini("Validation strategy", summary.validation_strategy));
    strategyGrid.append(textMini("Evaluation strategy", summary.evaluation_strategy));
    strategyGrid.append(textMini("Statistical strategy", summary.statistical_strategy));
    strategyGrid.append(textMini("Robustness strategy", summary.robustness_strategy));
    body.append(strategyGrid);

    const two = el("div", "two-column");
    two.append(listBlock("Key methods", summary.key_methods || []));
    two.append(listBlock("Key metrics", summary.key_metrics || []));
    body.append(two);

    body.append(ideasBlock(summary.reusable_method_ideas || []));
    body.append(experimentsBlock(summary.experiments || []));

    const caveats = el("div", "two-column");
    caveats.append(listBlock("Important limitations", summary.important_limitations || []));
    caveats.append(listBlock("Missing or unclear", summary.missing_or_unclear || []));
    body.append(caveats);

    body.append(listBlock("Other important details", summary.other_important_details || []));
    body.append(textBlock("Confidence notes", summary.confidence_notes));
  }

  if (payload.stdout || payload.stderr) {
    body.append(logBlock([payload.stdout, payload.stderr].filter(Boolean).join("\\n")));
  }
  wrap.append(body);
  result.replaceChildren(wrap);
}

function textBlock(title, text) {
  const block = el("section", "block");
  block.append(el("h3", "", title));
  block.append(el("p", "", text || "Not recorded."));
  return block;
}

function textMini(title, text) {
  const block = el("section", "mini");
  block.append(el("h3", "", title));
  block.append(el("p", "", text || "Not recorded."));
  return block;
}

function tagRow(tags) {
  const row = el("div", "tag-row");
  if (!tags.length) {
    row.append(el("span", "tag", "no tags"));
    return row;
  }
  tags.forEach((tag) => row.append(el("span", "tag", tag)));
  return row;
}

function listBlock(title, items) {
  const block = el("section", "mini");
  block.append(el("h3", "", title));
  const list = document.createElement("ul");
  if (!items.length) {
    list.append(el("li", "", "None recorded."));
  } else {
    items.forEach((item) => list.append(el("li", "", typeof item === "string" ? item : JSON.stringify(item))));
  }
  block.append(list);
  return block;
}

function ideasBlock(ideas) {
  const block = el("section");
  block.append(el("h2", "", "Reusable method ideas"));
  const list = el("div", "ideas");
  if (!ideas.length) {
    list.append(el("p", "meta", "None recorded."));
  }
  ideas.forEach((idea) => {
    const item = el("article", "idea");
    item.append(el("h3", "", idea.idea || "Untitled idea"));
    item.append(el("p", "", idea.why_it_matters || ""));
    item.append(el("p", "meta", `Reusable pattern: ${idea.reusable_pattern || "unset"}`));
    item.append(el("p", "meta", `Blueprint fields: ${(idea.supporting_blueprint_fields || []).join(", ") || "unset"}`));
    list.append(item);
  });
  block.append(list);
  return block;
}

function experimentsBlock(experiments) {
  const block = el("section");
  block.append(el("h2", "", "Experiments"));
  const list = el("div", "experiments");
  if (!experiments.length) {
    list.append(el("p", "meta", "No distinct experiments summarized."));
  }
  experiments.forEach((experiment) => {
    const item = el("article", "experiment");
    item.append(el("h3", "", experiment.name || "Unnamed experiment"));
    item.append(el("p", "", experiment.purpose || ""));
    item.append(el("p", "meta", `Data: ${experiment.data || "unset"}`));
    item.append(el("p", "meta", `Method: ${experiment.method || "unset"}`));
    item.append(el("p", "meta", `Comparison: ${experiment.comparison || "unset"}`));
    item.append(el("p", "meta", `Evaluation: ${experiment.evaluation || "unset"}`));
    item.append(el("p", "meta", `Finding type: ${experiment.finding_type || "unset"}`));
    list.append(item);
  });
  block.append(list);
  return block;
}

function logBlock(text) {
  const pre = el("pre", "run-log");
  pre.textContent = text;
  return pre;
}

function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}
"""

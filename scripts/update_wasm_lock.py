"""Regenerate wasm/pyodide-lock.json: the pinned packages the site loads.

Installs build123d into Pyodide in headless Chromium the way OCP.wasm
documents it (its bootstrap.py, which uses micropip and the OCP.wasm builds
of OpenCascade), records the result with micropip.freeze(), and keeps only
what build123d needs (see standardparts.site.prune_lock).

Run it after changing the build123d version in pyproject.toml or the
Pyodide version in wasm/runtime.json:

    uv run --with playwright python scripts/update_wasm_lock.py
    uv run --with playwright playwright install chromium   # first time only

Then rebuild the site and run scripts/check_site.py.
"""

from __future__ import annotations

import functools
import http.server
import json
import tempfile
import threading
import urllib.request
from importlib.metadata import version
from pathlib import Path

from playwright.sync_api import sync_playwright

from standardparts.site import WASM, prune_lock

BOOTSTRAP = "https://raw.githubusercontent.com/yeicor/OCP.wasm/master/build123d/bootstrap.py"

PAGE = """<!doctype html><meta charset="utf-8">
<script src="{index_url}pyodide.js"></script>
<script>
window.result = null;
(async () => {{
  try {{
    const py = await loadPyodide();
    await py.loadPackage("micropip");
    py.runPython(await (await fetch("bootstrap.py")).text());
    await py.runPythonAsync(`await bootstrap("{build123d}")`);
    window.result = py.runPython("import micropip; micropip.freeze()");
  }} catch (e) {{ window.result = "ERROR " + e; }}
}})();
</script>
"""


def main() -> None:
    runtime = json.loads((WASM / "runtime.json").read_text())
    build123d = version("build123d")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        with urllib.request.urlopen(BOOTSTRAP, timeout=60) as res:
            (root / "bootstrap.py").write_bytes(res.read())
        (root / "index.html").write_text(PAGE.format(index_url=runtime["index_url"], build123d=build123d))

        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=tmp)
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(f"http://127.0.0.1:{httpd.server_port}/index.html")
                page.wait_for_function("window.result !== null", timeout=900_000)
                frozen = page.evaluate("window.result")
                browser.close()
        finally:
            httpd.shutdown()

    if frozen.startswith("ERROR"):
        raise SystemExit(frozen)
    lock = prune_lock(json.loads(frozen))
    if lock["packages"]["build123d"]["version"] != build123d:
        raise SystemExit(f"Pyodide installed build123d {lock['packages']['build123d']['version']}, expected {build123d}")
    out = WASM / "pyodide-lock.json"
    out.write_text(json.dumps(lock, indent=1, sort_keys=True) + "\n")
    print(f"Wrote {out} ({len(lock['packages'])} packages, build123d {build123d})")


if __name__ == "__main__":
    main()

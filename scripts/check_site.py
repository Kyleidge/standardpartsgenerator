"""Check the built site in headless Chromium.

Serves dist/ (build it first with `uv run standardparts build`), waits for
the CAD kernel to load in the page, downloads a STEP file through the UI,
then builds every standard in the browser's WebAssembly kernel: default
parameters, in every thread mode the standard offers. The pytest suite
covers every size natively; this catches anything that behaves differently
in WebAssembly.

    uv run --with playwright python scripts/check_site.py [--quick]
    uv run --with playwright playwright install chromium   # first time only
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from standardparts.site import ROOT

SWEEP_JS = """
async (cases) => {
  const worker = new Worker(`worker.js?build=${window.__build}`, { type: "module" });
  const pending = new Map();
  let next = 1;
  const ready = new Promise((resolve, reject) => {
    worker.onmessage = ({ data: m }) => {
      if (m.type === "ready") return resolve();
      if (m.type === "failed") return reject(new Error(m.error));
      if (m.type) return; // download, phase and build progress messages
      pending.get(m.id)(m);
      pending.delete(m.id);
    };
  });
  const call = (op, standard, params) => new Promise((resolve) => {
    const id = next++;
    pending.set(id, resolve);
    worker.postMessage({ id, op, standard, params });
  });
  await ready;
  const results = [];
  for (const [standard, params] of cases) {
    const t = performance.now();
    const info = await call("info", standard, params);
    const glb = await call("preview", standard, params);
    const step = await call("step", standard, params);
    const head = (m, n) => (m.data ? String.fromCharCode(...new Uint8Array(m.data, 0, n)) : "");
    results.push({
      standard, params,
      ok: info.ok && glb.ok && step.ok && head(glb, 4) === "glTF" && head(step, 13) === "ISO-10303-21;",
      error: info.error || glb.error || step.error || null,
      designation: info.meta?.designation,
      seconds: (performance.now() - t) / 1000,
    });
  }
  worker.terminate();
  return results;
}
"""


class _Quiet(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".wasm": "application/wasm",
        ".mjs": "text/javascript",
        ".js": "text/javascript",
    }

    def log_message(self, *args):  # noqa: D401
        pass


def cases(catalog: dict, quick: bool) -> list[tuple[str, dict]]:
    out = []
    for s in catalog["standards"]:
        defaults = {p["name"]: p["default"] for p in s["parameters"]}
        thread = next((p for p in s["parameters"] if p["name"] == "thread"), None)
        modes = [o["value"] for o in thread["options"]] if thread and not quick else [None]
        for mode in modes:
            params = dict(defaults)
            if mode is not None:
                params["thread"] = mode
            out.append((s["id"], params))
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    parser.add_argument("--quick", action="store_true", help="default thread mode only")
    args = parser.parse_args()
    catalog = json.loads((args.dist / "catalog.json").read_text())

    handler = functools.partial(_Quiet, directory=str(args.dist))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_port}/"
    failures = 0
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            errors: list[str] = []
            page.on("console", lambda m: m.type == "error" and errors.append(m.text))
            page.on("pageerror", lambda e: errors.append(str(e)))

            t0 = time.time()
            page.goto(base + "?standard=iso4762&size=M8&length=30")
            page.wait_for_function("document.querySelector('#loading').hidden", timeout=300_000)
            page.wait_for_function("document.querySelector('#viewer-status').hidden", timeout=120_000)
            print(f"page ready in {time.time() - t0:.1f}s: {page.text_content('#designation')}")
            with page.expect_download() as download:
                page.click("#download")
            name = download.value.suggested_filename
            data = Path(download.value.path()).read_bytes()
            assert name == "ISO4762_M8x30.stp" and data.startswith(b"ISO-10303-21;"), (name, data[:20])
            print(f"download ok: {name} ({len(data)} bytes)")

            # The picker: every drawing loads, and search + Enter switches standard.
            missing = page.evaluate(
                """async (ids) => (await Promise.all(ids.map(async (id) => {
                     const r = await fetch(`thumbs/${id}.svg`);
                     return r.ok && (await r.text()).startsWith("<svg") ? null : id;
                   }))).filter(Boolean)""",
                [s["id"] for s in catalog["standards"]],
            )
            assert not missing, f"thumbnails missing: {missing}"
            page.keyboard.press("/")
            page.fill("#picker-query", "nyloc thin")
            page.press("#picker-query", "Enter")
            page.wait_for_function("document.querySelector('#standard-title').textContent === 'ISO 10511'")
            assert not page.evaluate("document.querySelector('#picker').open")
            assert "standard=iso10511" in page.url, page.url
            print(f"picker ok: {len(catalog['standards'])} thumbnails, search selected ISO 10511")

            page.evaluate(f"window.__build = {json.dumps(catalog['build'])}")
            todo = cases(catalog, args.quick)
            print(f"building {len(todo)} parts in the browser…")
            for r in page.evaluate(SWEEP_JS, todo):
                flag = "ok  " if r["ok"] else "FAIL"
                failures += not r["ok"]
                extra = r["error"] or ""
                print(f"  {flag} {r['seconds']:5.1f}s {r['standard']:9s} {r['designation'] or ''} {extra}")
            if errors:
                failures += 1
                print("console errors:", *errors, sep="\n  ")
            browser.close()
    finally:
        httpd.shutdown()
    print("all good" if not failures else f"{failures} failure(s)")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()

// Runs the geometry in the browser: Pyodide (CPython in WebAssembly) with
// build123d, OpenCascade (OCP.wasm) and the standardparts package, all
// loaded from ./pyodide/. The page talks to it with messages:
//
//   -> { id, op: "info" | "preview" | "step", standard, params }
//   <- { id, ok: true, meta, data? }   data is an ArrayBuffer (GLB / STEP)
//   <- { id, ok: false, error }
//   <- { type: "progress", id, event, data }   milestones of a running build
//                                              (see standardparts/progress.py)
// While loading:
//   <- { type: "download", got, total }        bytes of the runtime files
//   <- { type: "phase", key, text }            a start-up step begins
//   <- { type: "ready" } or { type: "failed", error }

import { loadPyodide } from "./pyodide/pyodide.mjs";

const build = new URL(import.meta.url).searchParams.get("build") || "dev";
const base = new URL("./pyodide/", import.meta.url).href;
const phase = (key, text) => postMessage({ type: "phase", key, text });

// Download every runtime file with a progress bar. Pyodide then loads them
// from the browser cache, so nothing is downloaded twice. files.json lists
// each file with its size (Content-Length is unreliable when the host
// compresses responses).
async function prefetch(files) {
  const names = Object.keys(files);
  const total = names.reduce((sum, n) => sum + files[n], 0);
  let got = 0;
  let reported = 0;
  const report = (force) => {
    const now = performance.now();
    if (!force && now - reported < 100) return;
    reported = now;
    postMessage({ type: "download", got: Math.min(got, total), total });
  };
  report(true);
  const queue = [...names];
  async function next() {
    while (queue.length) {
      const name = queue.shift();
      const res = await fetch(new URL(name, base).href);
      if (!res.ok) throw new Error(`could not download ${name} (${res.status})`);
      const reader = res.body.getReader();
      let seen = 0;
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        seen += value.length;
        got += value.length;
        report(false);
      }
      got += Math.max(0, files[name] - seen); // e.g. served from cache without a body count
    }
  }
  await Promise.all(Array.from({ length: 6 }, next));
  report(true);
}

let web = null;
let currentId = null;

// Start-up steps after the download, in order. The page knows the same keys
// and how long each took last time, for its progress bar.
const ready = (async () => {
  const lockURL = new URL(`pyodide-lock.json?build=${build}`, base).href;
  const files = await (await fetch(new URL(`files.json?build=${build}`, base).href)).json();
  await prefetch(files);
  phase("python", "Starting Python…");
  const py = await loadPyodide({ indexURL: base, lockFileURL: lockURL });
  const install = { messageCallback: () => {}, checkIntegrity: true };
  phase("packages-numeric", "Installing NumPy and SciPy…");
  await py.loadPackage(["numpy", "scipy"], install);
  phase("packages-occt", "Installing OpenCascade…");
  await py.loadPackage(["cadquery-ocp-novtk-ocp-wasm", "lib3mf-ocp-wasm"], install);
  phase("packages-rest", "Installing build123d…");
  await py.loadPackage(["standardparts"], install);
  py.runPython("from standardparts import _stubs; _stubs.install()");
  phase("import-numeric", "Starting NumPy and SciPy…");
  py.runPython("import numpy, scipy.optimize, scipy.spatial");
  phase("import-occt", "Starting OpenCascade…");
  py.runPython("import OCP");
  phase("import-build123d", "Starting build123d…");
  py.runPython("import build123d");
  phase("import-standards", "Loading the standards…");
  web = py.pyimport("standardparts.web");
  // Build milestones go to the page tagged with the request they belong to.
  py.pyimport("standardparts.progress").set_listener((event, json) => {
    if (currentId !== null) postMessage({ type: "progress", id: currentId, event, data: JSON.parse(json) });
  });
})();

ready.then(
  () => postMessage({ type: "ready" }),
  (err) => postMessage({ type: "failed", error: String(err?.message || err) }),
);

// Python exceptions carry the whole traceback; the last line says what happened.
function shortError(err) {
  const text = String(err?.message || err).trim();
  return text.split("\n").filter(Boolean).pop() || text;
}

self.onmessage = async ({ data: msg }) => {
  const { id, op, standard, params } = msg;
  try {
    await ready;
    currentId = id;
    const raw = JSON.stringify(params);
    let meta;
    let bytes = null;
    if (op === "info") {
      meta = JSON.parse(web.info(standard, raw));
    } else if (op === "preview" || op === "step") {
      const result = web[op](standard, raw);
      const [json, payload] = result.toJs();
      result.destroy();
      meta = JSON.parse(json);
      bytes = payload ?? null;
    } else {
      throw new Error(`unknown operation ${op}`);
    }
    if (!meta.ok) {
      postMessage({ id, ok: false, error: meta.error, invalid: true });
      return;
    }
    let buffer = null;
    if (bytes) {
      const whole = bytes.byteOffset === 0 && bytes.byteLength === bytes.buffer.byteLength;
      buffer = whole ? bytes.buffer : bytes.slice().buffer;
    }
    postMessage({ id, ok: true, meta, data: buffer }, buffer ? [buffer] : []);
  } catch (err) {
    console.error(err);
    postMessage({ id, ok: false, error: shortError(err) });
  } finally {
    currentId = null;
  }
};

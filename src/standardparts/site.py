"""Build the static website, and serve it for local use.

The site is front-end only. `build()` writes a folder that any static host
can serve:

    index.html, app.js, styles.css, ...  the page (from static/)
    worker.js                            Web Worker that runs the geometry
    catalog.json                         every standard's parameter schema
    thumbs/<id>.svg                      line drawing of every standard, for
                                         the standard picker
    THIRD_PARTY_NOTICES.txt, LICENSES/   licences of redistributed data/code
    pyodide/                             Python runtime and every wheel,
                                         pyodide-lock.json and files.json

The worker loads Pyodide (CPython compiled to WebAssembly), installs this
package and its dependencies from pyodide/ (build123d, and OpenCascade from
OCP.wasm) and calls `standardparts.web`. Nothing is fetched from anywhere
else at run time.

The package set is pinned in wasm/pyodide-lock.json in the repository
(made by scripts/update_wasm_lock.py) and the runtime in wasm/runtime.json.
Downloads are checked against their sha256 and kept in .cache/wasm/, so
only the first build needs the network.

This module is a development tool: it is run from a checkout and is not
shipped to the browser.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import shutil
import tarfile
import urllib.request
import zipfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT = PACKAGE_DIR.parents[1]
STATIC = PACKAGE_DIR / "static"
WASM = ROOT / "wasm"
CACHE = ROOT / ".cache" / "wasm"

# Files of the Pyodide npm package the site needs.
RUNTIME_FILES = ("pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip")

# build123d declares these, but nothing this package uses needs them, so
# they are left out of the site (about 12 MB). standardparts._stubs puts
# placeholder modules in for the two that build123d imports at start-up.
DROPPED = frozenset({"ipython", "scikit-learn", "sympy"})

# micropip records build123d's dependencies under their PyPI names; in
# Pyodide they are provided by the OCP.wasm builds.
RENAMED = {
    "cadquery-ocp-novtk": "cadquery-ocp-novtk-ocp-wasm",
    "lib3mf": "lib3mf-ocp-wasm",
}

# Files removed from dependency wheels before they go on the site.
# threejs-materials bundles 90 MB of PNG textures for its textured material
# presets; build123d imports the package, but plain colours (all this site
# uses) never read them.
SLIMMED = {
    "threejs-materials": ("threejs_materials/pbr_properties/_assets/",),
}

# Modules left out of the wheel sent to the browser.
EXCLUDED_MODULES = frozenset({"site.py"})


def canonical(name: str) -> str:
    return name.lower().replace("_", "-").replace(".", "-")


# --------------------------------------------------------------- lock file --


def prune_lock(lock: dict[str, Any], roots: Iterable[str] = ("build123d",)) -> dict[str, Any]:
    """Reduce a full Pyodide lock (e.g. micropip.freeze() output) to the
    packages `roots` need, with DROPPED left out and RENAMED applied."""
    packages = {canonical(k): v for k, v in lock["packages"].items()}
    keep: dict[str, dict[str, Any]] = {}
    todo = [canonical(r) for r in roots]
    while todo:
        name = todo.pop()
        if name in keep:
            continue
        if name not in packages:
            raise KeyError(f"package {name!r} is not in the lock file")
        entry = dict(packages[name])
        depends = []
        for dep in entry.get("depends", []):
            dep = RENAMED.get(canonical(dep), canonical(dep))
            if dep not in DROPPED:
                depends.append(dep)
        entry["name"] = name
        entry["depends"] = sorted(set(depends))
        keep[name] = entry
        todo.extend(entry["depends"])
    return {"info": lock["info"], "packages": dict(sorted(keep.items()))}


# --------------------------------------------------------------- downloads --


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "standardparts-site-builder"})
    with urllib.request.urlopen(req, timeout=120) as res:
        return res.read()


def fetch_cached(url: str, sha256: str | None = None, sha512_b64: str | None = None) -> Path:
    """Download `url` into the cache once and verify its hash."""
    name = url.rsplit("/", 1)[-1]
    path = CACHE / name
    if not path.exists():
        print(f"  downloading {name}")
        data = _download(url)
        CACHE.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(path)
    data = path.read_bytes()
    if sha256 is not None and hashlib.sha256(data).hexdigest() != sha256:
        path.unlink()
        raise RuntimeError(f"sha256 mismatch for {name}; the cached copy was removed")
    if sha512_b64 is not None and base64.b64encode(hashlib.sha512(data).digest()).decode() != sha512_b64:
        path.unlink()
        raise RuntimeError(f"sha512 mismatch for {name}; the cached copy was removed")
    return path


def _runtime_config() -> dict[str, Any]:
    return json.loads((WASM / "runtime.json").read_text())


def _package_url(entry: dict[str, Any], index_url: str) -> str:
    file_name = entry["file_name"]
    return file_name if "://" in file_name else index_url + file_name


# ------------------------------------------------------------- local wheel --


def slim_wheel(data: bytes, prefixes: Iterable[str]) -> bytes:
    """The wheel without the files under `prefixes` (and their RECORD lines)."""
    prefixes = tuple(prefixes)
    src = zipfile.ZipFile(io.BytesIO(data))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            if info.filename.startswith(prefixes):
                continue
            payload = src.read(info)
            if info.filename.endswith(".dist-info/RECORD"):
                lines = payload.decode().splitlines(keepends=True)
                payload = "".join(l for l in lines if not l.startswith(prefixes)).encode()
            dst.writestr(info, payload)
    return buf.getvalue()


def _record_hash(data: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
    return f"sha256={digest}"


def build_wheel(version: str) -> tuple[str, bytes]:
    """A wheel of this package's Python modules (no static files).

    The build tag carries a content hash, so every change gets a new file
    name and browsers never use a stale cached copy.
    """
    files: dict[str, bytes] = {}
    for path in sorted(PACKAGE_DIR.rglob("*.py")):
        rel = path.relative_to(PACKAGE_DIR)
        if "__pycache__" in rel.parts or rel.as_posix() in EXCLUDED_MODULES:
            continue
        files[f"standardparts/{rel.as_posix()}"] = path.read_bytes()
    content_hash = hashlib.sha256()
    for name, data in files.items():
        content_hash.update(name.encode() + b"\0" + data + b"\0")
    tag = "1" + content_hash.hexdigest()[:12]

    dist_info = f"standardparts-{version}.dist-info"
    files[f"{dist_info}/METADATA"] = (
        f"Metadata-Version: 2.1\nName: standardparts\nVersion: {version}\n"
        "Requires-Dist: build123d\n"
    ).encode()
    files[f"{dist_info}/WHEEL"] = (
        "Wheel-Version: 1.0\nGenerator: standardparts.site\nRoot-Is-Purelib: true\n"
        f"Build: {tag}\nTag: py3-none-any\n"
    ).encode()
    record = [f"{name},{_record_hash(data)},{len(data)}" for name, data in files.items()]
    record.append(f"{dist_info}/RECORD,,")
    files[f"{dist_info}/RECORD"] = ("\n".join(record) + "\n").encode()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)
    return f"standardparts-{version}-{tag}-py3-none-any.whl", buf.getvalue()


# ------------------------------------------------------------------- build --


def _catalog() -> dict[str, Any]:
    from .web import catalog

    return catalog()


# ------------------------------------------------------------- thumbnails --
# The standard picker shows a line drawing of every standard, so visitors
# can tell the parts apart before the CAD kernel has loaded. They are made
# here, natively, from each standard's default parameters: hidden-line
# projections from the viewer's starting direction, a few kB each.

# Parameters that show the part better than the defaults do.
THUMBNAIL_PARAMS: dict[str, dict[str, Any]] = {
    "iso15": {"detail": "faces"},  # the default envelope looks like a washer
}

# Direction from the part towards the camera; matches the viewer's start.
THUMBNAIL_VIEW = (1.0, -1.6, 0.9)


def thumbnail_params(standard: dict[str, Any]) -> dict[str, Any]:
    params = {p["name"]: p["default"] for p in standard["parameters"]}
    return {**params, **THUMBNAIL_PARAMS.get(standard["id"], {})}


def thumbnail_svg(standard_id: str, params: dict[str, Any]) -> str:
    """A compact SVG line drawing (visible edges only) of one part.

    The strokes do not scale with the drawing, so every thumbnail has the
    same line weight whatever the part's size.
    """
    import math
    import re
    import xml.etree.ElementTree as ET

    from build123d import ExportSVG

    from .export import build_part
    from .standards import STANDARDS

    with_defaults = STANDARDS[standard_id].validate(params)
    part = build_part(standard_id, with_defaults)
    bb = part.bounding_box()
    centre, r = bb.center(), max(bb.size)
    eye = tuple(c + r * 3 * v for c, v in zip(centre, THUMBNAIL_VIEW))
    visible, _hidden = part.project_to_viewport(eye, viewport_up=(0, 0, 1), look_at=centre)

    # Enough decimals for about 1/1000 of the part's size.
    digits = max(0, 3 - math.floor(math.log10(r)))
    exporter = ExportSVG(precision=digits, fit_to_stroke=False)
    exporter.add_layer("v")
    exporter.add_shape(visible, layer="v")
    buf = io.BytesIO()
    exporter.write(buf)
    root = ET.fromstring(buf.getvalue())

    ns = "{http://www.w3.org/2000/svg}"
    d = []
    for node in root.iter():
        if node.tag == f"{ns}path":
            d.append(node.attrib["d"])
        elif node.tag == f"{ns}line":
            a = node.attrib
            d.append(f"M {a['x1']},{a['y1']} L {a['x2']},{a['y2']}")
    if not d:
        raise RuntimeError(f"thumbnail for {standard_id} has no visible edges")

    def num(value: float) -> str:
        text = f"{value:.{digits}f}"
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return "0" if text == "-0" else text

    path = re.sub(r"-?\d+\.\d+(?:e-?\d+)?", lambda m: num(float(m.group())), " ".join(d))
    path = re.sub(r"\s*,\s*", ",", path)

    x, y, w, h = (float(v) for v in root.attrib["viewBox"].split())
    pad = 0.04 * max(w, h)
    view = " ".join(num(v) for v in (x - pad, y - pad, w + 2 * pad, h + 2 * pad))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}">'
        f'<path transform="scale(1,-1)" fill="none" stroke="#1c2330" stroke-width="1.15" '
        f'stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke" '
        f'd="{path}"/></svg>\n'
    )


def write_thumbnails(out: Path, catalog: dict[str, Any]) -> int:
    """Write thumbs/<id>.svg for every standard; returns the total size."""
    thumbs = out / "thumbs"
    thumbs.mkdir(exist_ok=True)
    total = 0
    for standard in catalog["standards"]:
        svg = thumbnail_svg(standard["id"], thumbnail_params(standard))
        (thumbs / f"{standard['id']}.svg").write_text(svg)
        total += len(svg)
    return total


def build(out: Path) -> Path:
    """Write the static site to `out` (replacing it) and return the path."""
    from importlib.metadata import version as dist_version

    out = out.resolve()
    if out.exists():
        if not (out / "catalog.json").exists() and any(out.iterdir()):
            raise RuntimeError(f"{out} exists and does not look like a site build; not replacing it")
        shutil.rmtree(out)
    shutil.copytree(STATIC, out)
    # Licences of the data and code the site redistributes. Plain .txt so
    # every host serves them as text.
    shutil.copyfile(ROOT / "THIRD_PARTY_NOTICES.md", out / "THIRD_PARTY_NOTICES.txt")
    shutil.copytree(ROOT / "LICENSES", out / "LICENSES")
    runtime_dir = out / "pyodide"
    runtime_dir.mkdir()

    runtime = _runtime_config()
    print(f"Pyodide {runtime['version']}")
    tarball = fetch_cached(runtime["npm_tarball"], sha512_b64=runtime["npm_integrity"])
    with tarfile.open(tarball) as tf:
        for name in RUNTIME_FILES:
            member = tf.extractfile(f"package/{name}")
            if member is None:
                raise RuntimeError(f"{name} missing from {tarball.name}")
            (runtime_dir / name).write_bytes(member.read())

    lock = json.loads((WASM / "pyodide-lock.json").read_text())
    for name, entry in lock["packages"].items():
        path = fetch_cached(_package_url(entry, runtime["index_url"]), sha256=entry["sha256"])
        target = runtime_dir / path.name
        if name in SLIMMED:
            data = slim_wheel(path.read_bytes(), SLIMMED[name])
            target.write_bytes(data)
            entry["sha256"] = hashlib.sha256(data).hexdigest()
        else:
            shutil.copyfile(path, target)
        entry["file_name"] = path.name

    wheel_name, wheel = build_wheel(dist_version("standardparts"))
    (runtime_dir / wheel_name).write_bytes(wheel)
    lock["packages"]["standardparts"] = {
        "name": "standardparts",
        "version": dist_version("standardparts"),
        "file_name": wheel_name,
        "install_dir": "site",
        "sha256": hashlib.sha256(wheel).hexdigest(),
        "package_type": "package",
        "imports": ["standardparts"],
        "depends": ["build123d"],
        "unvendored_tests": False,
    }
    (runtime_dir / "pyodide-lock.json").write_text(json.dumps(lock, indent=1, sort_keys=True))
    # Files the worker downloads up front (with a progress bar), and sizes.
    prefetch = [e["file_name"] for e in lock["packages"].values()]
    prefetch += ["pyodide.asm.wasm", "pyodide.asm.mjs", "python_stdlib.zip"]
    files = {name: (runtime_dir / name).stat().st_size for name in prefetch}
    (runtime_dir / "files.json").write_text(json.dumps(files, indent=1))

    catalog = _catalog()
    catalog["build"] = wheel_name.split("-")[2]
    (out / "catalog.json").write_text(json.dumps(catalog, separators=(",", ":")))
    print("Drawing thumbnails")
    thumbs_size = write_thumbnails(out, catalog)

    runtime_size = sum(p.stat().st_size for p in runtime_dir.iterdir())
    print(
        f"Wrote {out}: {len(catalog['standards'])} standards, {len(lock['packages'])} packages, "
        f"{runtime_size / 1e6:.0f} MB of runtime and wheels, {thumbs_size / 1e3:.0f} kB of thumbnails"
    )
    return out


# ------------------------------------------------------------------- serve --


def serve(directory: Path, host: str, port: int) -> None:
    import functools
    import http.server

    class Handler(http.server.SimpleHTTPRequestHandler):
        extensions_map = {
            **http.server.SimpleHTTPRequestHandler.extensions_map,
            ".wasm": "application/wasm",
            ".mjs": "text/javascript",
            ".js": "text/javascript",
            ".whl": "application/zip",
        }

        def end_headers(self) -> None:
            # Lets the browser revalidate instead of guessing a lifetime.
            self.send_header("Cache-Control", "no-cache")
            super().end_headers()

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            pass

    handler = functools.partial(Handler, directory=str(directory))
    with http.server.ThreadingHTTPServer((host, port), handler) as httpd:
        print(f"Serving {directory} on http://{host}:{port}/")
        httpd.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and serve the Standard Parts Generator site")
    sub = parser.add_subparsers(dest="command")
    p_build = sub.add_parser("build", help="write the static site")
    p_build.add_argument("--out", type=Path, default=ROOT / "dist")
    p_serve = sub.add_parser("serve", help="build the site, then serve it (default)")
    p_serve.add_argument("--out", type=Path, default=ROOT / "dist")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--no-build", action="store_true", help="serve the existing build")
    args = parser.parse_args()

    if args.command == "build":
        build(args.out)
        return
    if args.command is None:
        args = p_serve.parse_args([])
    if not args.no_build:
        build(args.out)
    serve(args.out.resolve(), args.host, args.port)


if __name__ == "__main__":
    main()

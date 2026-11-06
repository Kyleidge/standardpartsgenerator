"""Static site build pieces that need no network (standardparts.site)."""

import hashlib
import io
import json
import subprocess
import sys
import zipfile

import pytest

from standardparts import site


def test_pinned_lock_is_complete_and_pruned():
    lock = json.loads((site.WASM / "pyodide-lock.json").read_text())
    packages = lock["packages"]
    assert lock["info"]["python"].startswith("3.")
    assert "build123d" in packages and "cadquery-ocp-novtk-ocp-wasm" in packages
    for name, entry in packages.items():
        assert entry["name"] == name
        assert len(entry["sha256"]) == 64
        for dep in entry["depends"]:
            assert dep in packages, f"{name} depends on missing {dep}"
    assert not site.DROPPED & packages.keys()
    # The same build123d as the native tests run.
    from importlib.metadata import version

    assert packages["build123d"]["version"] == version("build123d")


def test_prune_lock_renames_and_drops():
    lock = {
        "info": {"python": "3.14"},
        "packages": {
            "build123d": {"name": "build123d", "depends": ["cadquery-ocp-novtk", "sympy", "numpy"]},
            "cadquery-ocp-novtk-OCP.wasm": {"name": "cadquery-ocp-novtk-OCP.wasm", "depends": []},
            "numpy": {"name": "numpy", "depends": []},
            "sympy": {"name": "sympy", "depends": ["mpmath"]},
            "mpmath": {"name": "mpmath", "depends": []},
            "unrelated": {"name": "unrelated", "depends": []},
        },
    }
    pruned = site.prune_lock(lock)
    assert sorted(pruned["packages"]) == ["build123d", "cadquery-ocp-novtk-ocp-wasm", "numpy"]
    assert pruned["packages"]["build123d"]["depends"] == ["cadquery-ocp-novtk-ocp-wasm", "numpy"]
    with pytest.raises(KeyError):
        site.prune_lock(lock, roots=["missing"])


def test_wheel_contains_the_package_but_not_the_build_tool():
    name, data = site.build_wheel("0.1.0")
    assert name.startswith("standardparts-0.1.0-1") and name.endswith("-py3-none-any.whl")
    zf = zipfile.ZipFile(io.BytesIO(data))
    names = set(zf.namelist())
    assert "standardparts/web.py" in names and "standardparts/standards/iso4762.py" in names
    assert "standardparts/site.py" not in names
    assert not any("__pycache__" in n or n.startswith("standardparts/static") for n in names)
    record = zf.read("standardparts-0.1.0.dist-info/RECORD").decode().splitlines()
    assert len(record) == len(names)
    # Same content, same name: browsers only refetch when something changed.
    assert site.build_wheel("0.1.0") == (name, data)


def test_wheel_installs_and_imports(tmp_path):
    name, data = site.build_wheel("0.1.0")
    zipfile.ZipFile(io.BytesIO(data)).extractall(tmp_path)
    out = subprocess.run(
        [sys.executable, "-c", "import standardparts.web as w, sys; print(w.__file__)"],
        cwd=tmp_path, env={"PYTHONPATH": str(tmp_path), "PATH": ""}, capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().startswith(str(tmp_path))


def test_stubs_let_build123d_import_without_ipython_and_sklearn():
    code = (
        "import sys\n"
        "from standardparts import _stubs\n"
        "assert _stubs.install(force=True) == ['IPython', 'sklearn']\n"
        "from standardparts import web\n"
        "import json\n"
        "meta, glb = web.preview('iso4762', json.dumps({'size': 'M3', 'length': 8}))\n"
        "assert glb[:4] == b'glTF'\n"
        "assert 'sympy' not in sys.modules\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr


def test_static_page_uses_relative_urls():
    html = (site.STATIC / "index.html").read_text()
    js = (site.STATIC / "app.js").read_text()
    assert "/static/" not in html and "/static/" not in js and "/api/" not in js
    assert 'src="app.js"' in html


def test_fetch_cached_checks_hashes(tmp_path, monkeypatch):
    monkeypatch.setattr(site, "CACHE", tmp_path)
    monkeypatch.setattr(site, "_download", lambda url: b"payload")
    good = hashlib.sha256(b"payload").hexdigest()
    assert site.fetch_cached("https://example.invalid/a.whl", sha256=good).read_bytes() == b"payload"
    with pytest.raises(RuntimeError, match="sha256 mismatch"):
        site.fetch_cached("https://example.invalid/b.whl", sha256="0" * 64)
    assert not (tmp_path / "b.whl").exists()


def test_slim_wheel_drops_files_and_their_record_lines():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("pkg/__init__.py", "x = 1\n")
        zf.writestr("pkg/_assets/big.png", b"\0" * 1000)
        zf.writestr("pkg-1.0.dist-info/RECORD", "pkg/__init__.py,,\npkg/_assets/big.png,,\n")
    slim = zipfile.ZipFile(io.BytesIO(site.slim_wheel(buf.getvalue(), ["pkg/_assets/"])))
    assert slim.namelist() == ["pkg/__init__.py", "pkg-1.0.dist-info/RECORD"]
    assert slim.read("pkg-1.0.dist-info/RECORD") == b"pkg/__init__.py,,\n"


def test_thumbnails_are_small_line_drawings_of_every_standard(tmp_path):
    import xml.etree.ElementTree as ET

    catalog = site._catalog()
    assert set(site.THUMBNAIL_PARAMS) <= {s["id"] for s in catalog["standards"]}
    total = site.write_thumbnails(tmp_path, catalog)
    assert total < 250_000
    for s in catalog["standards"]:
        svg = (tmp_path / "thumbs" / f"{s['id']}.svg").read_text()
        assert len(svg) < 20_000, s["id"]
        root = ET.fromstring(svg)
        x, y, w, h = map(float, root.attrib["viewBox"].split())
        assert w > 0 and h > 0
        (path,) = root
        assert path.attrib["vector-effect"] == "non-scaling-stroke"
        assert path.attrib["d"].startswith("M ") and path.attrib["d"].count("M ") >= 4, s["id"]

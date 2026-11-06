"""The API the browser calls.

The site has no server: a Web Worker (static/worker.js) runs this package
in Pyodide (CPython compiled to WebAssembly, with OpenCascade from
OCP.wasm) and calls these functions. They take and return JSON strings and
bytes, so the JavaScript side never has to convert Python objects.

Invalid parameters are not exceptions here: the JSON is
{"ok": false, "error": "..."}, which the page shows next to the form.
Anything else that goes wrong raises.

`catalog()` also runs at build time, so the page can draw its form before
Python has loaded.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from . import progress
from .export import build_part, glb_bytes, step_bytes
from .standards import STANDARDS, ParameterError, Standard


def catalog() -> dict[str, Any]:
    """Every standard with its parameter schema, in UI order."""
    return {"standards": [s.describe_json() for s in STANDARDS.values()]}


def _standard(standard_id: str) -> Standard:
    try:
        return STANDARDS[standard_id]
    except KeyError:
        raise ParameterError(f"unknown standard {standard_id!r}") from None


def _validate(standard_id: str, raw_json: str) -> tuple[Standard, dict[str, Any]]:
    standard = _standard(standard_id)
    return standard, standard.validate(json.loads(raw_json))


def _error(exc: ParameterError) -> str:
    return json.dumps({"ok": False, "error": str(exc)})


def info(standard_id: str, raw_json: str) -> str:
    """Designation, file name, dimension table and notes for one part."""
    try:
        standard, params = _validate(standard_id, raw_json)
    except ParameterError as exc:
        return _error(exc)
    return json.dumps({
        "ok": True,
        "params": params,
        "designation": standard.designation(params),
        "filename": standard.file_stem(params) + ".stp",
        "dimensions": [asdict(d) for d in standard.dimensions(params)],
        "notes": standard.notes(params),
    })


def preview(standard_id: str, raw_json: str) -> tuple[str, bytes | None]:
    """Binary glTF preview (one primitive per CAD face, exact normals)."""
    try:
        _, params = _validate(standard_id, raw_json)
    except ParameterError as exc:
        return _error(exc), None
    progress.report("stage", name="model")
    build_part(standard_id, params)
    progress.report("stage", name="preview")
    return json.dumps({"ok": True}), glb_bytes(standard_id, params)


def step(standard_id: str, raw_json: str) -> tuple[str, bytes | None]:
    """The STEP file and its file name."""
    try:
        standard, params = _validate(standard_id, raw_json)
    except ParameterError as exc:
        return _error(exc), None
    meta = {"ok": True, "filename": standard.file_stem(params) + ".stp"}
    return json.dumps(meta), step_bytes(standard_id, params)

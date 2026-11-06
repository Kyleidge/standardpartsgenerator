"""Build parts and serialise them to STEP and glTF bytes, with caching."""

from __future__ import annotations

import os
import tempfile
import threading
from datetime import datetime, timezone
from functools import lru_cache
from io import BytesIO
from typing import Any

from build123d import Color, Part, Unit, export_gltf, export_step

from .standards import STANDARDS

STEEL = Color(0.62, 0.64, 0.67)

# OpenCascade is not guaranteed to be thread safe, so all geometry work
# goes through this lock. In the browser there is only one thread and the
# lock costs nothing; it matters when the package is used from threads.
occ_lock = threading.RLock()


def _key(params: dict[str, Any]) -> tuple:
    return tuple(sorted(params.items()))


@lru_cache(maxsize=64)
def _build_cached(standard_id: str, key: tuple) -> Part:
    standard = STANDARDS[standard_id]
    part = standard.build(dict(key))
    part.color = STEEL
    for child in part.children:  # assemblies, e.g. bearing rings and balls
        if child.color is None:
            child.color = STEEL
    return part


def build_part(standard_id: str, params: dict[str, Any]) -> Part:
    with occ_lock:
        return _build_cached(standard_id, _key(params))


@lru_cache(maxsize=64)
def _step_cached(standard_id: str, key: tuple) -> bytes:
    part = _build_cached(standard_id, key)
    buf = BytesIO()
    export_step(
        part,
        buf,
        unit=Unit.MM,
        timestamp=datetime.now(timezone.utc).replace(microsecond=0),
    )
    return buf.getvalue()


def step_bytes(standard_id: str, params: dict[str, Any]) -> bytes:
    with occ_lock:
        return _step_cached(standard_id, _key(params))


@lru_cache(maxsize=64)
def _glb_cached(standard_id: str, key: tuple) -> bytes:
    part = _build_cached(standard_id, key)
    size = max(part.bounding_box().size)
    fd, path = tempfile.mkstemp(suffix=".glb")
    os.close(fd)
    try:
        export_gltf(
            part, path, binary=True, linear_deflection=size * 5e-4, angular_deflection=0.3
        )
        with open(path, "rb") as f:
            return f.read()
    finally:
        os.unlink(path)


def glb_bytes(standard_id: str, params: dict[str, Any]) -> bytes:
    """Binary glTF used for the in-browser preview: one primitive per CAD
    face, with normals taken from the exact surfaces (smooth shading)."""
    with occ_lock:
        return _glb_cached(standard_id, _key(params))

"""Placeholder modules for build123d dependencies the site leaves out.

build123d imports IPython (notebook pretty-printing and HTML display) and
scikit-learn (only for rebuilding B-reps from STL meshes) when it starts.
Neither is used here, and together with their own dependencies they would
add about 10 MB to the browser download, so the site does not ship them
(see site.DROPPED). `install()` registers minimal stand-ins so that
`import build123d` works without them. A real installation always wins:
nothing is replaced if the module can be imported.
"""

from __future__ import annotations

import importlib.util
import sys
from types import ModuleType


def _module(name: str, **attrs: object) -> ModuleType:
    mod = ModuleType(name)
    mod.__dict__.update(attrs)
    mod.__path__ = []  # lets submodules be registered under it
    sys.modules[name] = mod
    return mod


class _RepresentationPrinter:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.parts: list[str] = []

    def text(self, s: str) -> None:
        self.parts.append(s)


class _HTML:
    def __init__(self, data: str = "", *args: object, **kwargs: object) -> None:
        self.data = data


class _Unavailable:
    def __init__(self, *args: object, **kwargs: object) -> None:
        raise ImportError("scikit-learn is not available in the browser build")


def install(force: bool = False) -> list[str]:
    """Register the stand-ins that are needed; returns their names.

    `force` installs them even if the real packages exist (for tests).
    """
    installed = []
    if force or importlib.util.find_spec("IPython") is None:
        ipython = _module("IPython")
        lib = _module("IPython.lib")
        lib.pretty = _module("IPython.lib.pretty", RepresentationPrinter=_RepresentationPrinter, pretty=repr)
        ipython.lib = lib
        ipython.display = _module("IPython.display", HTML=_HTML, display=lambda *a, **k: None)
        installed.append("IPython")
    if force or importlib.util.find_spec("sklearn") is None:
        sklearn = _module("sklearn")
        sklearn.cluster = _module("sklearn.cluster", DBSCAN=_Unavailable)
        installed.append("sklearn")
    return installed

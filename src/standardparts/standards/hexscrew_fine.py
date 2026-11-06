"""ISO 8765 hexagon head bolts and ISO 8676 hexagon head screws, metric
fine pitch thread.

Same heads, thread lengths and length ranges as ISO 4014 / ISO 4017
(hexscrew.py); only the thread pitch differs. The size select offers every
size/pitch combination of the standards, e.g. "M10x1.25" and "M10x1".
"""

from __future__ import annotations

from typing import Any

from .hexscrew import ISO4014, ISO4017
from .hexscrew_data import ThreadSize
from .hexscrew_fine_data import SIZES


def _fine_note(ts: ThreadSize) -> str:
    return (
        f"Fine pitch thread {ts.name} (coarse pitch of {ts.sd.size}: {ts.sd.P:g})."
    )


class ISO8765(ISO4014):
    id = "iso8765"
    title = "ISO 8765"
    summary = (
        "Hexagon head bolts, partially threaded, metric fine pitch thread, "
        "grades A and B, M8x1 to M64x4"
    )
    category = "Screws"
    source = (
        "Values in mm, from ISO 8765:2022 Tables 1 to 4 (identical heads, b and "
        "lengths to ISO 4014:2022) and ISO 8765:2011."
    )
    number = "8765"
    sizes = SIZES
    default_size = "M8x1"
    default_length = 50

    def notes(self, p: dict[str, Any]) -> list[str]:
        out = super().notes(p)
        ts = self.sizes[p["size"]]
        out.insert(-2, _fine_note(ts) + " ls min = lg max - 5P uses the coarse pitch.")
        return out


class ISO8676(ISO4017):
    id = "iso8676"
    title = "ISO 8676"
    summary = (
        "Hexagon head screws, threaded to the head, metric fine pitch thread, "
        "grades A and B, M8x1 to M64x4"
    )
    category = "Screws"
    source = (
        "Values in mm, from ISO 8676:2022 Tables 1 to 4 (identical heads and "
        "lengths to ISO 4017:2022)."
    )
    number = "8676"
    sizes = SIZES
    default_size = "M8x1"
    default_length = 20

    def notes(self, p: dict[str, Any]) -> list[str]:
        out = super().notes(p)
        out.insert(-2, _fine_note(self.sizes[p["size"]]))
        return out

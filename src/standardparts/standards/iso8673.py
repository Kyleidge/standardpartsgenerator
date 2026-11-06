"""ISO 8673 hexagon regular nuts (style 1), metric fine pitch thread.

Same geometry and builder as ISO 4032 (iso4032.py); the size select offers
every size/pitch combination of the standard, e.g. "M10x1.25" and "M10x1".
"""

from __future__ import annotations

from typing import Any

from .base import Dimension
from .iso4032 import ISO4032
from .iso8673_data import SIZES, product_grade


class ISO8673(ISO4032):
    id = "iso8673"
    title = "ISO 8673"
    summary = "Hexagon regular nuts (style 1), metric fine pitch thread M8x1 to M64x4"
    category = "Nuts"
    source = (
        "Values in mm, from ISO 8673:2023 Tables 1 and 2 (M8x1 to M39x3) and "
        "ISO 8673:2012 Tables 1 and 2 (M42x3 to M64x4)."
    )
    number = "8673"
    sizes = SIZES
    default_size = "M8x1"
    annex_edition = "2023"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        sd = self.sizes[p["size"]]
        dims = super().dimensions(p)
        dims.insert(2, Dimension("grade", "Product grade", product_grade(sd.D), unit=""))
        return dims

    def notes(self, p: dict[str, Any]) -> list[str]:
        out = super().notes(p)
        out.insert(
            -2,
            "ISO 8673 notes that fine pitch regular nuts strip more easily; high "
            "nuts (style 2, ISO 8674) are preferred.",
        )
        return out

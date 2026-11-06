"""ISO 4032 hexagon regular nuts (style 1).

The fine pitch version ISO 8673 (iso8673.py) subclasses ISO4032 with its
own size table.
"""

from __future__ import annotations

from typing import Any

from build123d import Part

from ..geometry import MetricThread, chamfered_hex
from ..nuts import NUT_THREAD_MODES, Countersink, threaded_nut
from .base import Dimension, Option, Parameter, ParameterError, Standard
from .iso4032_data import CHAMFER_ANGLE, COUNTERSINK_ANGLE, SIZES, SizeData


def build_nut(sd: SizeData, thread_mode: str, what: str | None = None) -> Part:
    """Build the nut solid.

    Coordinate system: Z is the nut axis, the bearing face lies in the XY
    plane at z = 0 and the nut goes up to z = m. Flats are parallel to the
    X axis (s across Y, corners e on the X axis). Nominal sizes: s nom,
    m max, e of the exact hexagon, both faces chamfered at 30 deg down to
    dw min, countersinks at da max with a 120 deg included angle.
    """
    if thread_mode not in NUT_THREAD_MODES:
        raise ParameterError(f"unknown thread mode {thread_mode!r}")
    m = sd.m_max
    body = chamfered_hex(sd.s_nom, 0.0, m, sd.dw_min, sd.dw_min, CHAMFER_ANGLE)
    cs = Countersink(sd.da_max, COUNTERSINK_ANGLE)
    return threaded_nut(
        body, MetricThread(sd.D, sd.P), 0.0, m, thread_mode, cs, cs,
        what=what or f"ISO 4032 {sd.size}",
    )


class ISO4032(Standard):
    id = "iso4032"
    title = "ISO 4032"
    summary = "Hexagon regular nuts (style 1), coarse thread M1.6 to M64"
    category = "Nuts"
    source = (
        "Values in mm, from ISO 4032:2023 Tables 1 and 2 (M5 to M39) and "
        "ISO 4032:1999 Tables 1 and 2 (M1.6 to M4, M42 to M64)."
    )
    number = "4032"
    sizes: dict[str, SizeData] = SIZES
    default_size = "M8"
    # Edition whose informative Annex A holds the rows with in_annex set.
    annex_edition = "2023"

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="size",
                label="Thread size",
                kind="select",
                default=self.default_size,
                options=[Option(s, sd.label) for s, sd in self.sizes.items()],
            ),
            Parameter(
                name="thread",
                label="Thread",
                kind="select",
                default="simplified",
                options=[Option(k, v) for k, v in NUT_THREAD_MODES.items()],
                help="Simplified is a plain bore at the minor diameter D1, as most "
                "CAD libraries ship; modeled has a helical ISO 68-1 internal thread.",
            ),
        ]

    def validate(self, raw: dict[str, Any]) -> dict[str, Any]:
        size = str(raw.get("size", self.default_size))
        if size not in self.sizes:
            raise ParameterError(
                f"unknown size {size!r}; choose one of {', '.join(self.sizes)}"
            )
        thread = str(raw.get("thread", "simplified"))
        if thread not in NUT_THREAD_MODES:
            raise ParameterError(f"thread must be one of {', '.join(NUT_THREAD_MODES)}")
        return {"size": size, "thread": thread}

    def designation(self, p: dict[str, Any]) -> str:
        return f"ISO {self.number} - {self.sizes[p['size']].name}"

    def file_stem(self, p: dict[str, Any]) -> str:
        suffix = "_threaded" if p["thread"] == "modeled" else ""
        return f"ISO{self.number}_{p['size']}{suffix}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        sd = self.sizes[p["size"]]
        t = MetricThread(sd.D, sd.P)
        return [
            Dimension("D", "Thread diameter", sd.D),
            Dimension("P", "Pitch", sd.P),
            Dimension("s", "Width across flats", sd.s_nom),
            Dimension("s min", "Width across flats, min.", sd.s_min),
            Dimension("e", "Width across corners (modeled)", round(sd.e_nom, 3)),
            Dimension("e min", "Width across corners, min.", sd.e_min),
            Dimension("m max", "Nut height", sd.m_max),
            Dimension("m min", "Nut height, min.", sd.m_min),
            Dimension("mw min", "Wrenching height", sd.mw_min),
            Dimension("dw min", "Bearing face dia.", sd.dw_min),
            Dimension("da max", "Countersink dia.", sd.da_max),
            Dimension("da min", "Countersink dia., min.", sd.da_min),
            Dimension("D1", "Minor diameter (basic)", round(t.d1, 3)),
            Dimension("D2", "Pitch diameter", round(t.d2, 3)),
        ]

    def _annex_note(self, sd: SizeData) -> str:
        return (
            f"ISO {self.number}:{self.annex_edition} lists {sd.name} only in its "
            f"informative Annex A; dimensions here are from ISO {self.number}:{sd.edition}."
        )

    def notes(self, p: dict[str, Any]) -> list[str]:
        sd = self.sizes[p["size"]]
        out = []
        if not sd.preferred:
            out.append(f"{sd.name} is a non-preferred size.")
        if sd.in_annex:
            out.append(self._annex_note(sd))
        if p["thread"] == "simplified":
            out.append(
                "Thread not modeled: plain bore at the basic minor diameter D1, "
                "ready for a cosmetic thread."
            )
        else:
            out.append(
                "Thread modeled with the ISO 68-1 basic internal profile (root flat "
                "at D, crest flat at D1), right hand."
            )
        out.append(
            "Modeled at nominal sizes: s nom, m max, e = s / cos 30°. Both faces "
            "have a 30° corner chamfer down to dw min and a 120° countersink at da max."
        )
        return out

    def build(self, p: dict[str, Any]) -> Part:
        sd = self.sizes[p["size"]]
        part = build_nut(sd, p["thread"], what=f"ISO {self.number} {sd.name}")
        part.label = self.designation(p)
        return part

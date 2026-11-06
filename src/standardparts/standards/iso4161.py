"""ISO 4161 hexagon nuts with flange, style 2, coarse thread."""

from __future__ import annotations

import math
from typing import Any

from build123d import Part

from ..geometry import SQRT3, MetricThread, chamfered_hex, revolve_profile
from ..nuts import NUT_THREAD_MODES, Countersink, threaded_nut
from .base import Dimension, Option, Parameter, ParameterError, Standard
from .flange import Flange, fuse_hex, hex_overlap_volume
from .iso4161_data import (
    COUNTERSINK_ANGLE,
    FLANGE_ANGLE,
    SIZES,
    TOP_CHAMFER_ANGLE,
    TOP_CHAMFER_DIA,
    SizeData,
)

# Round core inside the hexagon (fraction of s) and the hexagon prism's
# bottom face (fraction of the flange height under the corners, tried in
# turn if the fuse fails). See flange.py.
CORE_RADIUS = 0.4
HEX_BOTTOM_FRACTIONS = (0.5, 0.35, 0.65)


def _fmt(x: float) -> str:
    return f"{x:g}"


def flange(sd: SizeData) -> Flange:
    return Flange(sd.dc_max, sd.dw_min, sd.c_min, FLANGE_ANGLE)


def model_mw(sd: SizeData) -> float:
    """Full-corner height of the modeled hexagon: from the flange cone at
    the corners up to the start of the top chamfer."""
    s = sd.s_nom
    drop = (s / SQRT3 - TOP_CHAMFER_DIA * s / 2) * math.tan(math.radians(TOP_CHAMFER_ANGLE))
    return sd.m_max - drop - flange(sd).height(s / SQRT3)


def flange_nut_body(sd: SizeData, what: str) -> Part:
    """Unbored nut: revolved flange and core with the hexagon fused on."""
    s = sd.s_nom
    m = sd.m_max
    fl = flange(sd)
    fl.check()
    r_core = CORE_RADIUS * s
    z_core = (fl.height(r_core) + m) / 2
    body = revolve_profile([(0.0, 0.0), *fl.profile(r_core, z_core)])
    h_corner = fl.height(s / SQRT3)
    for frac in HEX_BOTTOM_FRACTIONS:
        z_hex = frac * h_corner
        hexagon = chamfered_hex(
            s, z_hex, m,
            top_chamfer_dia=TOP_CHAMFER_DIA * s,
            chamfer_angle=TOP_CHAMFER_ANGLE,
        )
        overlap = hex_overlap_volume(s, z_hex, fl, r_core, z_core)
        fused = fuse_hex(body, hexagon, overlap, what)
        if fused is not None:
            return fused
    raise RuntimeError(f"hexagon fuse failed for {what}")


def build_flange_nut(sd: SizeData, thread_mode: str) -> Part:
    """Build the flange nut.

    Coordinate system: Z is the nut axis, the flange bearing face lies at
    z = 0 and the nut goes up to z = m. Flats are parallel to the X axis.
    Nominal sizes: s max, m max, dc max, flange c min thick at dw min with
    a 20 deg top cone and a rounded rim, flat bearing face, 30 deg top
    corner chamfer from 0.95 s, 120 deg countersinks at da max on both
    faces.
    """
    if thread_mode not in NUT_THREAD_MODES:
        raise ParameterError(f"unknown thread mode {thread_mode!r}")
    what = f"ISO 4161 {sd.size}"
    body = flange_nut_body(sd, what)
    cs = Countersink(sd.da_max, COUNTERSINK_ANGLE)
    return threaded_nut(
        body, MetricThread(sd.D, sd.P), 0.0, sd.m_max, thread_mode, cs, cs, what=what
    )


class ISO4161(Standard):
    id = "iso4161"
    title = "ISO 4161"
    summary = "Hexagon nuts with flange, style 2, plain flange, coarse thread M5 to M20"
    category = "Nuts"
    source = "Values in mm, from ISO 4161:2012 Table 1."

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="size",
                label="Thread size",
                kind="select",
                default="M8",
                options=[
                    Option(s, f"{s} x {_fmt(sd.P)}" + ("" if sd.preferred else " (non-preferred)"))
                    for s, sd in SIZES.items()
                ],
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
        size = str(raw.get("size", "M8"))
        if size not in SIZES:
            raise ParameterError(f"unknown size {size!r}; choose one of {', '.join(SIZES)}")
        thread = str(raw.get("thread", "simplified"))
        if thread not in NUT_THREAD_MODES:
            raise ParameterError(f"thread must be one of {', '.join(NUT_THREAD_MODES)}")
        return {"size": size, "thread": thread}

    def designation(self, p: dict[str, Any]) -> str:
        return f"ISO 4161 - {p['size']}"

    def file_stem(self, p: dict[str, Any]) -> str:
        suffix = "_threaded" if p["thread"] == "modeled" else ""
        return f"ISO4161_{p['size']}{suffix}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        sd = SIZES[p["size"]]
        t = MetricThread(sd.D, sd.P)
        return [
            Dimension("D", "Thread diameter", sd.D),
            Dimension("P", "Pitch", sd.P),
            Dimension("grade", "Product grade", sd.product_grade, unit=""),
            Dimension("s", "Width across flats", sd.s_nom),
            Dimension("s min", "Width across flats, min.", sd.s_min),
            Dimension("e", "Width across corners (model)", round(sd.e_nom, 3)),
            Dimension("e min", "Width across corners, min.", sd.e_min),
            Dimension("m max", "Nut height", sd.m_max),
            Dimension("m min", "Nut height, min.", sd.m_min),
            Dimension("mw min", "Wrenching height, min.", sd.mw_min),
            Dimension("mw", "Wrenching height (model)", round(model_mw(sd), 3)),
            Dimension("dc max", "Flange diameter", sd.dc_max),
            Dimension("c min", "Flange thickness at dw min", sd.c_min),
            Dimension("dw min", "Bearing face dia.", sd.dw_min),
            Dimension("δ", "Flange top angle (model)", FLANGE_ANGLE, unit="°"),
            Dimension("da max", "Countersink dia.", sd.da_max),
            Dimension("da min", "Countersink dia., min.", sd.da_min),
            Dimension("D1", "Minor diameter (basic)", round(t.d1, 3)),
            Dimension("D2", "Pitch diameter", round(t.d2, 3)),
        ]

    def notes(self, p: dict[str, Any]) -> list[str]:
        sd = SIZES[p["size"]]
        out = []
        if not sd.preferred:
            out.append(f"{sd.size} is a non-preferred size.")
        out.append(f"Product grade {sd.product_grade}.")
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
            "Modeled at nominal sizes: s max, m max, dc max, e = s / cos 30°. Plain "
            f"flange (not serrated), c min thick at dw min, {_fmt(FLANGE_ANGLE)}° top "
            "cone and rounded rim, flat bearing face. 30° top corner chamfer from "
            "0.95 s, 120° countersinks at da max on both faces."
        )
        return out

    def build(self, p: dict[str, Any]) -> Part:
        part = build_flange_nut(SIZES[p["size"]], p["thread"])
        part.label = self.designation(p)
        return part

"""ISO 4035 hexagon thin nuts (style 0, chamfered)."""

from __future__ import annotations

from typing import Any

from build123d import Part

from ..geometry import MetricThread, chamfered_hex
from ..nuts import NUT_THREAD_MODES, Countersink, threaded_nut
from .base import Dimension, Option, Parameter, ParameterError, Standard
from .iso4035_data import CHAMFER_ANGLE, COUNTERSINK_ANGLE, SIZES, SizeData


def _fmt(x: float) -> str:
    return f"{x:g}"


def build_nut(sd: SizeData, thread_mode: str) -> Part:
    """Build the thin nut solid.

    Coordinate system as ISO 4032: Z is the nut axis, the bearing face lies
    in the XY plane at z = 0 and the nut goes up to z = m. Flats are
    parallel to the X axis (s across Y, corners e on the X axis). Nominal
    sizes: s nom, m max, e of the exact hexagon, both faces chamfered at
    15 deg down to dw min, countersinks at da max with a 120 deg included
    angle.
    """
    if thread_mode not in NUT_THREAD_MODES:
        raise ParameterError(f"unknown thread mode {thread_mode!r}")
    m = sd.m_max
    body = chamfered_hex(sd.s_nom, 0.0, m, sd.dw_min, sd.dw_min, CHAMFER_ANGLE)
    cs = Countersink(sd.da_max, COUNTERSINK_ANGLE)
    return threaded_nut(
        body, MetricThread(sd.D, sd.P), 0.0, m, thread_mode, cs, cs,
        what=f"ISO 4035 {sd.size}",
    )


class ISO4035(Standard):
    id = "iso4035"
    title = "ISO 4035"
    summary = "Hexagon thin nuts (style 0, chamfered), coarse thread M1.6 to M64"
    category = "Nuts"
    source = (
        "Values in mm, from ISO 4035:2023 Tables 1 and 2 (M5 to M39) and "
        "ISO 4035:2012 Tables 1 and 2 (M1.6 to M4, M42 to M64)."
    )

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
        return f"ISO 4035 - {p['size']}"

    def file_stem(self, p: dict[str, Any]) -> str:
        suffix = "_threaded" if p["thread"] == "modeled" else ""
        return f"ISO4035_{p['size']}{suffix}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        sd = SIZES[p["size"]]
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
            Dimension("β", "Corner chamfer angle (modeled)", CHAMFER_ANGLE, "°"),
            Dimension("θ", "Countersink angle (modeled)", COUNTERSINK_ANGLE, "°"),
        ]

    def notes(self, p: dict[str, Any]) -> list[str]:
        sd = SIZES[p["size"]]
        out = []
        if not sd.preferred:
            out.append(f"{sd.size} is a non-preferred size.")
        if sd.in_annex:
            out.append(
                f"ISO 4035:2023 lists {sd.size} only in its Annex A; dimensions "
                "here are from ISO 4035:2012."
            )
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
            f"have a {_fmt(CHAMFER_ANGLE)}° corner chamfer down to dw min (the "
            "standard allows 15° to 30°; 15° keeps mw min at the corners) and a "
            f"{_fmt(COUNTERSINK_ANGLE)}° countersink at da max."
        )
        return out

    def build(self, p: dict[str, Any]) -> Part:
        part = build_nut(SIZES[p["size"]], p["thread"])
        part.label = self.designation(p)
        return part

"""ISO 14581 hexalobular socket countersunk flat head screws."""

from __future__ import annotations

from typing import Any

from build123d import Part

from ..drives import HEXALOBULAR, hexalobular_depth_total, hexalobular_recess
from ..geometry import MetricThread
from ..screws import THREAD_MODES
from .base import Dimension, Option, Parameter, Standard
from .iso7045 import cut_recess, length_notes, thread_mode_note, validate_common
from .iso7046 import (
    countersunk_body,
    countersunk_dimensions,
    countersunk_notes,
    countersunk_reference,
    short_thread_note,
)
from .iso14581_data import NON_PREFERRED_LENGTHS, SIZES, SizeData


def _fmt(x: float) -> str:
    return f"{x:g}"


def build_body(sd: SizeData, l: float, thread_mode: str) -> Part:
    return countersunk_body(sd, l, thread_mode, f"ISO 14581 {sd.size} x {l:g}")


def recess_tool(sd: SizeData) -> Part:
    """Socket T(no) to the minimum penetration t min below the top face."""
    return hexalobular_recess(sd.socket, sd.t_min, 0.0)


def build_screw(sd: SizeData, l: float, thread_mode: str) -> Part:
    body = build_body(sd, l, thread_mode)
    ref = body if thread_mode == "simplified" else countersunk_reference(sd, l)
    return cut_recess(body, recess_tool(sd), ref, f"ISO 14581 {sd.size} x {l:g}")


class ISO14581(Standard):
    id = "iso14581"
    title = "ISO 14581"
    summary = "Hexalobular socket countersunk flat head screws, M2 to M10"
    category = "Screws"
    source = (
        "Values in mm, from ISO 14581:2013 Table 1 (the 2022 edition changed "
        "the shortest lengths, not verified); socket ISO 10664."
    )

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="size",
                label="Thread size",
                kind="select",
                default="M5",
                options=[
                    Option(s, f"{s} x {_fmt(sd.P)}" if sd.preferred else f"({s}) x {_fmt(sd.P)}")
                    for s, sd in SIZES.items()
                ],
            ),
            Parameter(
                name="length",
                label="Nominal length l",
                kind="length",
                default=12,
                depends_on="size",
                preferred={s: sd.standard_lengths() for s, sd in SIZES.items()},
                limits={s: [sd.l_min, sd.l_max] for s, sd in SIZES.items()},
                unit="mm",
                help="Overall length, from the top of the head to the tip.",
            ),
            Parameter(
                name="thread",
                label="Thread",
                kind="select",
                default="simplified",
                options=[Option(k, v) for k, v in THREAD_MODES.items()],
                help="Simplified is lighter and is what most CAD libraries ship; "
                "the threaded length is a separate face for cosmetic threads.",
            ),
        ]

    def validate(self, raw: dict[str, Any]) -> dict[str, Any]:
        return validate_common(raw, SIZES, "M5", 12, None)

    def designation(self, p: dict[str, Any]) -> str:
        return f"ISO 14581 - {p['size']} x {_fmt(p['length'])}"

    def file_stem(self, p: dict[str, Any]) -> str:
        suffix = "_threaded" if p["thread"] == "modeled" else ""
        return f"ISO14581_{p['size']}x{_fmt(p['length'])}{suffix}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        sd = SIZES[p["size"]]
        l = p["length"]
        t = MetricThread(sd.d, sd.P)
        h = HEXALOBULAR[sd.socket]
        full = sd.is_fully_threaded(l)
        return [
            Dimension("d", "Thread diameter", sd.d),
            Dimension("P", "Pitch", sd.P),
            Dimension("l", "Nominal length (incl. head)", l),
            Dimension("b", "Thread length", "to head" if full else f"{_fmt(sd.b_min)} min"),
            *countersunk_dimensions(sd),
            Dimension("Socket", "Hexalobular socket", h.name, unit=""),
            Dimension("A", "Point to point (ISO 10664)", h.A),
            Dimension("B", "Across inner lobes (ISO 10664)", h.B),
            Dimension("Re", "Outer lobe radius (gauge)", h.Re),
            Dimension("Ri", "Inner lobe radius (derived)", round(h.Ri, 3)),
            Dimension("t min", "Penetration depth", sd.t_min),
            Dimension("t max", "Penetration depth", sd.t_max),
            Dimension("t total", "Modeled socket depth",
                      round(hexalobular_depth_total(sd.socket, sd.t_min), 3)),
            Dimension("d2", "Pitch diameter", round(t.d2, 3)),
            Dimension("d3", "Minor diameter", round(t.d3, 3)),
        ]

    def notes(self, p: dict[str, Any]) -> list[str]:
        sd = SIZES[p["size"]]
        l = p["length"]
        out = length_notes(sd, l, NON_PREFERRED_LENGTHS)
        if sd.is_fully_threaded(l):
            out.append("Threaded up to the head at this length (b = l - (k + a)).")
        else:
            out.append(
                f"Partially threaded: b = {_fmt(sd.b_min)} mm of thread, plain shank above."
            )
        out.append(thread_mode_note(p["thread"]))
        out += short_thread_note(sd, l, p["thread"])
        out.append(countersunk_notes(sd))
        out.append(
            f"Hexalobular socket T{sd.socket} (ISO 10664): nominal A and B, outer lobe "
            "radius from the GO gauge, inner radius from tangency; contour to t min, "
            "then a 118° conical bottom."
        )
        out.append(
            "Reduced loadability (head design). The underhead reinforcement of "
            "ISO 14581:2022 for M5 to M10 is not modeled; lengths follow the 2013 "
            "edition (the 2022 edition increased the shortest lengths)."
        )
        return out

    def build(self, p: dict[str, Any]) -> Part:
        part = build_screw(SIZES[p["size"]], p["length"], p["thread"])
        part.label = self.designation(p)
        return part

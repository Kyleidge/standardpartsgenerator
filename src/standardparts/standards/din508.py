"""DIN 508 nuts for T-slots (T-slot nuts), M4 x 5 to M48 x 54."""

from __future__ import annotations

from typing import Any

from build123d import Face, Part, Vector, Wire, extrude

from ..geometry import MetricThread
from ..nuts import NUT_THREAD_MODES, Countersink, threaded_nut
from .base import Dimension, Option, Parameter, ParameterError, Standard
from .din508_data import COUNTERSINK_ANGLE, SIZES, SizeData


def _fmt(x: float) -> str:
    return f"{x:g}"


def section_points(sd: SizeData) -> list[tuple[float, float]]:
    """Cross-section (y, z) of the nut across the slot: square base of width
    e and height k with the f x 45 deg chamfers on its bottom edges, and the
    tenon of width a up to h."""
    e, a, f = sd.e_max / 2, sd.a_max / 2, sd.f
    k, h = sd.k_max, sd.h
    return [
        (-e + f, 0.0), (e - f, 0.0), (e, f), (e, k), (a, k), (a, h),
        (-a, h), (-a, k), (-e, k), (-e, f),
    ]


def body_volume(sd: SizeData) -> float:
    """Exact volume of the unbored body."""
    e, a, f = sd.e_max, sd.a_max, sd.f
    return e * (e * sd.k_max + a * (sd.h - sd.k_max) - f * f)


def nut_body(sd: SizeData) -> Part:
    """Unbored body: the cross-section extruded along X over the length e.
    One extrusion, no booleans."""
    e = sd.e_max
    pts = [Vector(-e / 2, y, z) for y, z in section_points(sd)]
    body = extrude(Face(Wire.make_polygon(pts, close=True)), amount=e, dir=(1, 0, 0))
    if (
        len(body.solids()) != 1
        or not body.is_valid
        or abs(body.volume - body_volume(sd)) > 1e-6 * body_volume(sd)
    ):
        raise RuntimeError(f"body failed for DIN 508 {sd.designation}")
    return body


def build_nut(sd: SizeData, thread_mode: str) -> Part:
    """Build the T-slot nut.

    Coordinate system: Z is the thread axis. The bottom of the base lies in
    the XY plane at z = 0, the shoulders the slot bears on are at z = k and
    the tenon top is at z = h. The slot (and the tenon) run along X; the
    tenon width a is across Y. Nominal sizes: a max, e max, k max, h, the
    45 deg chamfer f on the two base edges along X, and 120 deg countersinks
    of diameter da (a model value) at both bore ends.
    """
    if thread_mode not in NUT_THREAD_MODES:
        raise ParameterError(f"unknown thread mode {thread_mode!r}")
    cs = Countersink(sd.da, COUNTERSINK_ANGLE)
    # threaded_nut checks the result (single valid solid, volume against
    # the analytic bore / thread volume) and retries the thread fuse at
    # other start angles.
    return threaded_nut(
        nut_body(sd), MetricThread(sd.D, sd.P), 0.0, sd.h, thread_mode, cs, cs,
        what=f"DIN 508 {sd.designation}",
    )


class DIN508(Standard):
    id = "din508"
    title = "DIN 508"
    summary = "Nuts for T-slots (T-slot nuts), M4 x 5 to M48 x 54"
    category = "Nuts"
    source = (
        "Values in mm, from the DIN 508:2002 table (as listed by "
        "globalfastener.com), cross-checked against Halder EH 23010, "
        "Elesa-Ganter and fasten.it."
    )

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="size",
                label="Slot width a x thread",
                kind="select",
                default="14",
                options=[
                    Option(k, f"a = {k} mm, {sd.d} x {_fmt(sd.P)}")
                    for k, sd in SIZES.items()
                ],
                help="Nominal T-slot width to DIN 650 / ISO 299. DIN 508 pairs "
                "each slot width with one thread size.",
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
        size = str(raw.get("size", "14"))
        if size not in SIZES:
            raise ParameterError(
                f"unknown slot width {size!r}; choose one of {', '.join(SIZES)}"
            )
        thread = str(raw.get("thread", "simplified"))
        if thread not in NUT_THREAD_MODES:
            raise ParameterError(f"thread must be one of {', '.join(NUT_THREAD_MODES)}")
        return {"size": size, "thread": thread}

    def designation(self, p: dict[str, Any]) -> str:
        return f"DIN 508 - {SIZES[p['size']].designation}"

    def file_stem(self, p: dict[str, Any]) -> str:
        sd = SIZES[p["size"]]
        suffix = "_threaded" if p["thread"] == "modeled" else ""
        return f"DIN508_{sd.d}x{sd.slot}{suffix}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        sd = SIZES[p["size"]]
        t = MetricThread(sd.D, sd.P)
        return [
            Dimension("d", "Thread", sd.d, unit=""),
            Dimension("P", "Pitch", sd.P),
            Dimension("a nom", "Slot width (DIN 650)", sd.a_nom),
            Dimension("a max", "Tenon width", sd.a_max),
            Dimension("a min", "Tenon width, min.", sd.a_min),
            Dimension("e max", "Base width and length", sd.e_max),
            Dimension("e min", "Base width and length, min.", sd.e_min),
            Dimension("h", "Overall height", sd.h),
            Dimension("k max", "Base height", sd.k_max),
            Dimension("k min", "Base height, min.", sd.k_min),
            Dimension("f", "Base chamfer (45°)", sd.f),
            Dimension("da", "Countersink dia. (model)", sd.da),
            Dimension("D1", "Minor diameter (basic)", round(t.d1, 3)),
            Dimension("mass", "Approx. mass (table)", sd.mass, unit="g"),
        ]

    def notes(self, p: dict[str, Any]) -> list[str]:
        out = []
        if p["thread"] == "simplified":
            out.append(
                "Thread not modeled: plain bore at the basic minor diameter D1, "
                "ready for a cosmetic thread."
            )
        else:
            out.append(
                "Thread modeled with the ISO 68-1 basic internal profile (root flat "
                "at D, crest flat at D1), right hand, through the whole nut."
            )
        out.append(
            "Modeled at a max, e max, k max and h, with the f x 45° chamfer on the "
            "two bottom edges of the base that run along the slot. The base bottom "
            "is at z = 0, the bearing shoulders at z = k, the tenon runs along X."
        )
        out.append(
            "DIN 508 does not specify a countersink; the model has a 120° "
            "countersink of diameter da on both bore ends."
        )
        return out

    def build(self, p: dict[str, Any]) -> Part:
        part = build_nut(SIZES[p["size"]], p["thread"])
        part.label = self.designation(p)
        return part

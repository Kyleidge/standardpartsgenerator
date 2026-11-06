"""ISO 4162 hexagon bolts with flange, small series."""

from __future__ import annotations

import math
from typing import Any

from build123d import Part

from ..geometry import SQRT3, MetricThread, chamfered_hex
from ..screws import THREAD_MODES, threaded_screw
from .base import Dimension, Option, Parameter, ParameterError, Standard
from .flange import Flange, fuse_hex, hex_overlap_volume
from .iso4162_data import (
    FLANGE_ANGLE,
    SIZES,
    TOP_CHAMFER_ANGLE,
    TOP_CHAMFER_DIA,
    SizeData,
)

# Radius of the round core inside the hexagon, as a fraction of s (inside
# the flats and inside the top chamfer circle).
CORE_RADIUS = 0.4
# Where the hexagon prism's bottom face sits, as a fraction of the flange
# height under the hexagon corners, tried in turn if the fuse fails.
HEX_BOTTOM_FRACTIONS = (0.5, 0.35, 0.65)


def _fmt(x: float) -> str:
    return f"{x:g}"


def flange(sd: SizeData) -> Flange:
    return Flange(sd.dc_max, sd.dw_min, sd.c_min, FLANGE_ANGLE)


def corner_chamfer_drop(s: float) -> float:
    """How far the top chamfer reaches down at the hexagon corners."""
    return (s / SQRT3 - TOP_CHAMFER_DIA * s / 2) * math.tan(math.radians(TOP_CHAMFER_ANGLE))


def model_kw(sd: SizeData) -> float:
    """Full-corner height of the modeled hexagon: from the flange cone at
    the corners up to the start of the top chamfer."""
    s = sd.s_nom
    return sd.k_max - corner_chamfer_drop(s) - flange(sd).height(s / SQRT3)


def z_thread_end(sd: SizeData, l: float) -> float:
    """Top of the full thread (z < 0)."""
    if sd.threaded_to_head(l):
        # Run the thread out right under the underhead fillet.
        t = MetricThread(sd.d, sd.P)
        return -sd.r1_min - (sd.d - t.d1) / 2
    return -sd.thread_geometry(l)[1]


def build_flange_bolt(sd: SizeData, l: float, thread_mode: str, what: str) -> Part:
    """Build a hexagon flange bolt.

    Coordinate system: Z is the bolt axis, the flange bearing face lies at
    z = 0, the head extends to z = k and the shank to z = -l. Hexagon flats
    are parallel to the X axis.

    Nominal sizes: s max, k max, dc max, ds = d, flange c min thick at dw
    min with a 20 deg top cone and a rounded rim, Type F flat bearing face,
    underhead fillet r1 min, hexagon top chamfer 30 deg from 0.95 s.
    """
    if thread_mode not in THREAD_MODES:
        raise ParameterError(f"unknown thread mode {thread_mode!r}")
    thread = MetricThread(sd.d, sd.P)
    R = sd.d / 2
    r = sd.r1_min
    k = sd.k_max
    s = sd.s_nom
    fl = flange(sd)
    fl.check()
    r_core = CORE_RADIUS * s
    z_core = (fl.height(r_core) + k) / 2
    head = [
        ("arc", (R + r - r / math.sqrt(2), -r + r / math.sqrt(2)), (R + r, 0.0)),
        *fl.profile(r_core, z_core),
    ]
    body = threaded_screw(thread, l, z_thread_end(sd, l), -r, head, thread_mode, what=what)
    h_corner = fl.height(s / SQRT3)
    for frac in HEX_BOTTOM_FRACTIONS:
        z_hex = frac * h_corner
        hexagon = chamfered_hex(
            s, z_hex, k,
            top_chamfer_dia=TOP_CHAMFER_DIA * s,
            chamfer_angle=TOP_CHAMFER_ANGLE,
        )
        overlap = hex_overlap_volume(s, z_hex, fl, r_core, z_core)
        fused = fuse_hex(body, hexagon, overlap, what)
        if fused is not None:
            return fused
    raise RuntimeError(f"head fuse failed for {what}")


class ISO4162(Standard):
    id = "iso4162"
    title = "ISO 4162"
    summary = "Hexagon bolts with flange, small series, plain flange, M5 to M16"
    category = "Screws"
    source = (
        "Values in mm, from ISO 4162:1990 Table 1 (the 2012 edition is a minor "
        "revision; shapes per ISO 4162:2012 Figures 1 to 3)."
    )
    default_size = "M8"
    default_length = 30.0

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="size",
                label="Thread size",
                kind="select",
                default=self.default_size,
                options=[
                    Option(s, f"{s} x {_fmt(sd.P)}" + ("" if sd.preferred else " (non-preferred)"))
                    for s, sd in SIZES.items()
                ],
            ),
            Parameter(
                name="length",
                label="Nominal length l",
                kind="length",
                default=self.default_length,
                depends_on="size",
                preferred={s: sd.standard_lengths() for s, sd in SIZES.items()},
                limits={s: list(sd.lengths) for s, sd in SIZES.items()},
                unit="mm",
                help="Measured from the flange bearing face to the tip.",
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
        size = str(raw.get("size", self.default_size))
        if size not in SIZES:
            raise ParameterError(f"unknown size {size!r}; choose one of {', '.join(SIZES)}")
        sd = SIZES[size]
        try:
            length = float(raw.get("length", self.default_length))
        except (TypeError, ValueError):
            raise ParameterError("length must be a number") from None
        if not math.isfinite(length):
            raise ParameterError("length must be a number")
        length = round(length, 2)
        lo, hi = sd.lengths
        if not lo <= length <= hi:
            raise ParameterError(
                f"length for {size} must be between {_fmt(lo)} and {_fmt(hi)} mm"
            )
        thread = str(raw.get("thread", "simplified"))
        if thread not in THREAD_MODES:
            raise ParameterError(f"thread must be one of {', '.join(THREAD_MODES)}")
        return {"size": size, "length": length, "thread": thread}

    def designation(self, p: dict[str, Any]) -> str:
        return f"ISO 4162 - {p['size']} x {_fmt(p['length'])}"

    def file_stem(self, p: dict[str, Any]) -> str:
        suffix = "_threaded" if p["thread"] == "modeled" else ""
        return f"ISO4162_{p['size']}x{_fmt(p['length'])}{suffix}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        sd = SIZES[p["size"]]
        l = p["length"]
        t = MetricThread(sd.d, sd.P)
        if sd.threaded_to_head(l):
            thread_dims = [Dimension("b", "Thread length", "to head", unit="")]
        else:
            ls_min, lg_max = sd.thread_geometry(l)
            thread_dims = [
                Dimension("b", "Thread length", sd.b(l)),
                Dimension("lg max", "Grip length", lg_max),
                Dimension("ls min", "Plain shank length", ls_min),
            ]
        return [
            Dimension("d", "Thread diameter", sd.d),
            Dimension("P", "Pitch", sd.P),
            Dimension("l", "Nominal length", l),
            *thread_dims,
            Dimension("s", "Width across flats", sd.s_nom),
            Dimension("s min", "Width across flats, min.", sd.s_min),
            Dimension("e", "Width across corners (model)", round(sd.e_nom, 3)),
            Dimension("e min", "Width across corners, min.", sd.e_min),
            Dimension("k max", "Head height", sd.k_max),
            Dimension("kw min", "Wrenching height, min.", sd.kw_min),
            Dimension("kw", "Wrenching height (model)", round(model_kw(sd), 3)),
            Dimension("dc max", "Flange diameter", sd.dc_max),
            Dimension("c min", "Flange thickness at dw min", sd.c_min),
            Dimension("dw min", "Bearing face dia.", sd.dw_min),
            Dimension("δ", "Flange top angle (model)", FLANGE_ANGLE, unit="°"),
            Dimension("da max", "Fillet transition dia.", sd.da_max),
            Dimension("r1 min", "Underhead fillet", sd.r1_min),
            Dimension("lf max", "Underhead transition length", sd.lf_max),
            Dimension("d2", "Pitch diameter", round(t.d2, 3)),
            Dimension("d3", "Minor diameter", round(t.d3, 3)),
        ]

    def notes(self, p: dict[str, Any]) -> list[str]:
        sd = SIZES[p["size"]]
        l = p["length"]
        out = []
        if l not in sd.standard_lengths():
            pref = ", ".join(_fmt(x) for x in sd.standard_lengths())
            out.append(
                f"{_fmt(l)} mm is not a standard length for {sd.size} (standard: {pref})."
            )
        if not sd.preferred:
            out.append(f"{sd.size} is a non-preferred size.")
        if sd.threaded_to_head(l):
            out.append("Threaded up to the head.")
        else:
            band = "l <= 125" if l <= 125 else "125 < l <= 200"
            out.append(
                f"Partially threaded: b = {_fmt(sd.b(l))} mm of thread ({band}), "
                "plain shank above."
            )
        out.append("Product grade A, driving feature (hexagon) grade B.")
        if p["thread"] == "simplified":
            out.append(
                "Thread not modeled: shank is a plain cylinder at d. The threaded "
                "length is its own face, ready for a cosmetic thread."
            )
        else:
            out.append(
                "Thread modeled with the ISO 68-1 basic profile (flat root at d1), "
                "right hand, with a 2P runout."
            )
        out.append(
            "Modeled at nominal sizes: s max, k max, dc max, ds = d. Plain flange "
            f"(not serrated), c min thick at dw min, {_fmt(FLANGE_ANGLE)}° top cone and "
            "rounded rim; flat bearing face (Type F), underhead fillet r1 min, 30° "
            "top chamfer from 0.95 s, ISO 4753 chamfered point."
        )
        return out

    def build(self, p: dict[str, Any]) -> Part:
        sd = SIZES[p["size"]]
        part = build_flange_bolt(sd, p["length"], p["thread"], what=self.designation(p))
        part.label = self.designation(p)
        return part

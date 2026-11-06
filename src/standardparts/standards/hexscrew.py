"""ISO 4014 hexagon head bolts and ISO 4017 hexagon head screws.

The fine pitch versions (ISO 8765 / ISO 8676, hexscrew_fine.py) subclass
these with another size table; see hexscrew_data.ThreadSize.
"""

from __future__ import annotations

import math
from typing import Any

from build123d import Part

from ..geometry import MetricThread, chamfered_hex
from ..screws import THREAD_MODES, threaded_screw
from .base import Dimension, Option, Parameter, ParameterError, Standard
from .hexscrew_data import THREAD_SIZES, SizeData, ThreadSize

# The top chamfer of the hexagon starts on a circle of this fraction of s
# and runs out at 30 deg (ISO 4014 / 4017 allow 15 to 30 deg).
TOP_CHAMFER_DIA = 0.95
TOP_CHAMFER_ANGLE = 30.0

# Where the round head core inside the hexagon ends, as a fraction of the
# hexagon height, tried in turn if the fuse fails.
CORE_TOP_FRACTIONS = (0.5, 0.35, 0.65)


def _fmt(x: float) -> str:
    return f"{x:g}"


def build_hex_screw(
    sd: SizeData, l: float, z_thread_end: float, thread_mode: str, what: str,
    P: float | None = None,
) -> Part:
    """Build a hexagon head bolt / screw.

    Coordinate system: Z is the screw axis, the bearing face (underside of
    the washer face) lies at z = 0, the head extends to z = k and the shank
    to z = -l. Hexagon flats are parallel to the X axis.

    Nominal sizes are used: s nom, k nom, ds = d, washer face dw min (of the
    product grade) by c max, underhead fillet r min, top chamfer 30 deg from
    0.95 s. The thread (or its simplified face) runs from the point up to
    z_thread_end. P is the thread pitch, the coarse pitch sd.P by default.
    """
    if thread_mode not in THREAD_MODES:
        raise ParameterError(f"unknown thread mode {thread_mode!r}")
    thread = MetricThread(sd.d, sd.P if P is None else P)
    R = sd.d / 2
    r = sd.r_min
    k = sd.k_nom
    c = sd.c_max
    dw = sd.grade_dims(l).dw_min
    hexagon = chamfered_hex(
        sd.s_nom, c, k,
        top_chamfer_dia=TOP_CHAMFER_DIA * sd.s_nom,
        chamfer_angle=TOP_CHAMFER_ANGLE,
    )
    hex_volume = hexagon.volume

    # The revolved part carries the shank, the underhead fillet, the washer
    # face and a round core that runs on at dw up into the hexagon. The
    # hexagon overlaps that core, so no face of one lies on a face of the
    # other (coincident faces make OCCT fuses fail silently).
    for frac in CORE_TOP_FRACTIONS:
        z_core = c + frac * (k - c)
        head = [
            ("arc", (R + r - r / math.sqrt(2), -r + r / math.sqrt(2)), (R + r, 0.0)),
            (dw / 2, 0.0),
            (dw / 2, z_core),
            (0.0, z_core),
        ]
        body = threaded_screw(thread, l, z_thread_end, -r, head, thread_mode, what=what)
        fused = body + hexagon
        overlap = math.pi * (dw / 2) ** 2 * (z_core - c)
        expected = body.volume + hex_volume - overlap
        if (
            len(fused.solids()) == 1
            and abs(fused.volume - expected) < 1e-3 * hex_volume
            and fused.is_valid
        ):
            return fused
    raise RuntimeError(f"head fuse failed for {what}")


def _check_length(ts: ThreadSize, raw: dict[str, Any], default: float,
                  limits: tuple[float, float]) -> float:
    try:
        length = float(raw.get("length", default))
    except (TypeError, ValueError):
        raise ParameterError("length must be a number") from None
    if not math.isfinite(length):
        raise ParameterError("length must be a number")
    length = round(length, 2)
    lo, hi = limits
    if not lo <= length <= hi:
        raise ParameterError(
            f"length for {ts.name} must be between {_fmt(lo)} and {_fmt(hi)} mm"
        )
    return length


class _HexHeadStandard(Standard):
    """Shared parts of ISO 4014 and ISO 4017 (and their fine pitch
    subclasses ISO 8765 and ISO 8676)."""

    number: str           # "4014"
    sizes: dict[str, ThreadSize] = THREAD_SIZES
    default_size = "M8"
    default_length: float

    def _limits(self, sd: SizeData) -> tuple[float, float]:
        raise NotImplementedError

    def _lengths(self, sd: SizeData) -> list[float]:
        raise NotImplementedError

    def _z_thread_end(self, ts: ThreadSize, l: float) -> float:
        raise NotImplementedError

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="size",
                label="Thread size",
                kind="select",
                default=self.default_size,
                options=[Option(key, ts.label) for key, ts in self.sizes.items()],
            ),
            Parameter(
                name="length",
                label="Nominal length l",
                kind="length",
                default=self.default_length,
                depends_on="size",
                preferred={key: self._lengths(ts.sd) for key, ts in self.sizes.items()},
                limits={key: list(self._limits(ts.sd)) for key, ts in self.sizes.items()},
                unit="mm",
                help="Measured from under the head to the tip.",
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
        if size not in self.sizes:
            raise ParameterError(
                f"unknown size {size!r}; choose one of {', '.join(self.sizes)}"
            )
        ts = self.sizes[size]
        length = _check_length(ts, raw, self.default_length, self._limits(ts.sd))
        thread = str(raw.get("thread", "simplified"))
        if thread not in THREAD_MODES:
            raise ParameterError(f"thread must be one of {', '.join(THREAD_MODES)}")
        return {"size": size, "length": length, "thread": thread}

    def designation(self, p: dict[str, Any]) -> str:
        return f"ISO {self.number} - {self.sizes[p['size']].name} x {_fmt(p['length'])}"

    def file_stem(self, p: dict[str, Any]) -> str:
        suffix = "_threaded" if p["thread"] == "modeled" else ""
        return f"ISO{self.number}_{p['size']}x{_fmt(p['length'])}{suffix}"

    def _head_dimensions(self, ts: ThreadSize, l: float) -> list[Dimension]:
        sd = ts.sd
        g = sd.grade_dims(l)
        t = MetricThread(sd.d, ts.P)
        return [
            Dimension("s", "Width across flats", sd.s_nom),
            Dimension("e", "Width across corners (model)", round(sd.e_nom, 3)),
            Dimension("e min", "Width across corners", g.e_min),
            Dimension("k", "Head height", sd.k_nom),
            Dimension("k max", "Head height max.", g.k_max),
            Dimension("kw min", "Wrenching height", g.kw_min),
            Dimension("c max", "Washer face height", sd.c_max),
            Dimension("dw min", "Washer face dia.", g.dw_min),
            Dimension("da max", "Fillet transition dia.", sd.da_max),
            Dimension("r min", "Underhead fillet", sd.r_min),
            Dimension("d2", "Pitch diameter", round(t.d2, 3)),
            Dimension("d3", "Minor diameter", round(t.d3, 3)),
        ]

    def _common_notes(self, p: dict[str, Any]) -> list[str]:
        ts = self.sizes[p["size"]]
        sd = ts.sd
        l = p["length"]
        out = []
        if l not in self._lengths(sd):
            pref = ", ".join(_fmt(x) for x in self._lengths(sd))
            out.append(
                f"{_fmt(l)} mm is not a standard length for {ts.name} "
                f"(standard: {pref})."
            )
        if not ts.preferred:
            out.append(f"{ts.name} is a non-preferred size.")
        out.append(f"Product grade {sd.product_grade(l)} at this size and length.")
        return out

    def _thread_notes(self, p: dict[str, Any]) -> list[str]:
        if p["thread"] == "simplified":
            thread = (
                "Thread not modeled: shank is a plain cylinder at d. The threaded "
                "length is its own face, ready for a cosmetic thread."
            )
        else:
            thread = (
                "Thread modeled with the ISO 68-1 basic profile (flat root at d1), "
                "right hand, with a 2P runout."
            )
        return [
            thread,
            "Modeled at nominal sizes: s nom, k nom, ds = d, washer face dw min "
            "by c max, underhead fillet r min, 30 deg top chamfer from 0.95 s, "
            "ISO 4753 chamfered point.",
        ]

    def build(self, p: dict[str, Any]) -> Part:
        ts = self.sizes[p["size"]]
        l = p["length"]
        part = build_hex_screw(
            ts.sd, l, self._z_thread_end(ts, l), p["thread"],
            what=self.designation(p), P=ts.P,
        )
        part.label = self.designation(p)
        return part


class ISO4014(_HexHeadStandard):
    id = "iso4014"
    title = "ISO 4014"
    summary = "Hexagon head bolts, partially threaded, grades A and B, M1.6 to M64"
    category = "Screws"
    source = "Values in mm, from ISO 4014:2022 Tables 1 to 4 and ISO 4017:2022."
    number = "4014"
    default_length = 50

    def _limits(self, sd: SizeData) -> tuple[float, float]:
        return sd.l4014

    def _lengths(self, sd: SizeData) -> list[float]:
        return sd.lengths_4014()

    def _z_thread_end(self, ts: ThreadSize, l: float) -> float:
        return -ts.sd.thread_geometry_4014(l)[1]

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        ts = self.sizes[p["size"]]
        sd = ts.sd
        l = p["length"]
        ls_min, lg_max = sd.thread_geometry_4014(l)
        return [
            Dimension("d", "Thread diameter", sd.d),
            Dimension("P", "Pitch", ts.P),
            Dimension("l", "Nominal length", l),
            Dimension("grade", "Product grade", sd.product_grade(l), unit=""),
            Dimension("b", "Thread length", sd.b_4014(l)),
            Dimension("lg max", "Grip length", lg_max),
            Dimension("ls min", "Plain shank length", ls_min),
            *self._head_dimensions(ts, l),
        ]

    def notes(self, p: dict[str, Any]) -> list[str]:
        sd = self.sizes[p["size"]].sd
        l = p["length"]
        b = sd.b_4014(l)
        band = "l <= 125" if l <= 125 else "125 < l <= 200" if l <= 200 else "l > 200"
        return [
            *self._common_notes(p),
            f"Partially threaded: b = {_fmt(b)} mm of thread ({band}), plain shank above.",
            *self._thread_notes(p),
        ]


class ISO4017(_HexHeadStandard):
    id = "iso4017"
    title = "ISO 4017"
    summary = "Hexagon head screws, threaded to the head, grades A and B, M1.6 to M64"
    category = "Screws"
    source = "Values in mm, from ISO 4017:2022 Tables 1 to 4."
    number = "4017"
    default_length = 20

    def _limits(self, sd: SizeData) -> tuple[float, float]:
        return sd.l4017

    def _lengths(self, sd: SizeData) -> list[float]:
        return sd.lengths_4017()

    def _z_thread_end(self, ts: ThreadSize, l: float) -> float:
        # Threaded to the head: run the thread out right under the fillet.
        t = MetricThread(ts.sd.d, ts.P)
        return -ts.sd.r_min - (ts.sd.d - t.d1) / 2

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        ts = self.sizes[p["size"]]
        sd = ts.sd
        l = p["length"]
        return [
            Dimension("d", "Thread diameter", sd.d),
            Dimension("P", "Pitch", ts.P),
            Dimension("l", "Nominal length", l),
            Dimension("grade", "Product grade", sd.product_grade(l), unit=""),
            Dimension("b", "Thread length", "to head"),
            # a = 1P to 3P of the thread pitch (ISO 4017, ISO 8676).
            Dimension("a max", "Thread runout under head", round(3 * ts.P, 3)),
            Dimension("a min", "Thread runout under head min.", round(ts.P, 3)),
            *self._head_dimensions(ts, l),
        ]

    def notes(self, p: dict[str, Any]) -> list[str]:
        return [
            *self._common_notes(p),
            "Threaded up to the head.",
            *self._thread_notes(p),
        ]

"""ISO 7040 and ISO 10511 prevailing torque hexagon nuts with non-metallic
insert ("nyloc"), regular height and thin."""

from __future__ import annotations

import math
from typing import Any

from build123d import Color, Part

from ..geometry import MetricThread, chamfered_hex, revolve_profile
from ..nuts import NUT_THREAD_MODES, Countersink, threaded_nut
from .base import Dimension, Option, Parameter, ParameterError, Standard
from .nyloc_data import (
    CHAMFER_ANGLE,
    COUNTERSINK_ANGLE,
    INSERT_BORE_SHRINK,
    ISO7040_SIZES,
    ISO10511_SIZES,
    NylocData,
)

# Natural polyamide inserts are white; blue is the other common colour and
# stands out better against steel in the preview.
INSERT_COLOR = Color(0.22, 0.45, 0.85)

SQ2 = 1 / math.sqrt(2)


def _fmt(x: float) -> str:
    return f"{x:g}"


def collar_profile(nd: NylocData, overlap: float) -> list:
    """(radius, z) profile of the collar ring: from `overlap` below the top
    of the hex (so the fuse never meets coincident faces) up to h, with the
    outer top edge rounded and the crimped lip turned in over the insert."""
    ri, rc, rl = nd.di / 2, nd.dc / 2, nd.dl / 2
    t, h, z0 = nd.wall, nd.h, nd.m_hex - overlap
    return [
        (ri, z0),
        (rc, z0),
        (rc, h - t),
        ("arc", (ri + t * SQ2, h - t + t * SQ2), (ri, h)),
        (rl, h),
        (rl, h - t),
        (ri, h - t),
    ]


def collar_volume(nd: NylocData, overlap: float) -> float:
    """Exact volume of collar_profile (Pappus for the rounded edge)."""
    ri, rc, rl = nd.di / 2, nd.dc / 2, nd.dl / 2
    t, h, z0 = nd.wall, nd.h, nd.m_hex - overlap
    ring = math.pi * (rc**2 - ri**2) * (h - t - z0)
    quarter = math.pi * t * t / 4 * 2 * math.pi * (ri + 4 * t / (3 * math.pi))
    lip = math.pi * (ri**2 - rl**2) * t
    return ring + quarter + lip


def build_body(nd: NylocData, thread_mode: str, what: str) -> Part:
    """Steel body: threaded chamfered hex (z = 0 to m_hex) with the collar
    fused on top."""
    m = nd.m_hex
    hex_body = chamfered_hex(nd.s_nom, 0.0, m, nd.dw_min, nd.dw_min, CHAMFER_ANGLE)
    cs = Countersink(nd.da_max, COUNTERSINK_ANGLE)
    nut = threaded_nut(
        hex_body, MetricThread(nd.D, nd.P), 0.0, m, thread_mode, cs, cs, what=what
    )
    ri, rc = nd.di / 2, nd.dc / 2
    for frac in (0.5, 0.3, 0.7):
        overlap = frac * nd.wall
        collar = revolve_profile(collar_profile(nd, overlap))
        body = nut + collar
        expected = nut.volume + collar_volume(nd, overlap) - math.pi * (rc**2 - ri**2) * overlap
        if (
            len(body.solids()) == 1
            and body.is_valid
            and abs(body.volume - expected) < 1e-4 * expected
        ):
            return body
    raise RuntimeError(f"collar fuse failed for {what}")


def build_insert(nd: NylocData) -> Part:
    """Polyamide ring filling the collar between the top of the hex and the
    lip (touching both, so it sits exactly in the collar)."""
    rb, ri = nd.d_insert / 2, nd.di / 2
    z0, z1 = nd.m_hex, nd.h - nd.wall
    ring = revolve_profile([(rb, z0), (ri, z0), (ri, z1), (rb, z1)])
    expected = math.pi * (ri**2 - rb**2) * (z1 - z0)
    if len(ring.solids()) != 1 or not ring.is_valid or abs(ring.volume - expected) > 1e-6 * expected:
        raise RuntimeError("insert build failed")
    return ring


def build_nyloc(nd: NylocData, thread_mode: str, what: str) -> Part:
    """Build the nut as a two-solid assembly: children "body" (steel) and
    "insert" (polyamide, coloured).

    Coordinate system as ISO 4032: Z is the nut axis, the bearing face lies
    in the XY plane at z = 0 and the nut goes up to z = h. Flats are
    parallel to the X axis (s across Y, corners e on the X axis).
    """
    if thread_mode not in NUT_THREAD_MODES:
        raise ParameterError(f"unknown thread mode {thread_mode!r}")
    body = build_body(nd, thread_mode, what)
    insert = build_insert(nd)
    body.label = "body"
    insert.label = "insert"
    insert.color = INSERT_COLOR
    part = Part(children=[body, insert])
    if len(part.solids()) != 2 or not part.is_valid:
        raise RuntimeError(f"assembly failed for {what}")
    return part


class _NylocNut(Standard):
    category = "Nuts"
    number: str
    sizes: dict[str, NylocData]
    base: str          # plain nut standard the body follows
    example_class: str

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="size",
                label="Thread size",
                kind="select",
                default="M8",
                options=[
                    Option(s, f"{s} x {_fmt(nd.P)}" + ("" if nd.preferred else " (non-preferred)"))
                    for s, nd in self.sizes.items()
                ],
            ),
            Parameter(
                name="thread",
                label="Thread",
                kind="select",
                default="simplified",
                options=[Option(k, v) for k, v in NUT_THREAD_MODES.items()],
                help="Thread in the steel body. Simplified is a plain bore at the "
                "minor diameter D1; modeled has a helical ISO 68-1 internal thread. "
                "The insert is never threaded.",
            ),
        ]

    def validate(self, raw: dict[str, Any]) -> dict[str, Any]:
        size = str(raw.get("size", "M8"))
        if size not in self.sizes:
            raise ParameterError(
                f"unknown size {size!r}; choose one of {', '.join(self.sizes)}"
            )
        thread = str(raw.get("thread", "simplified"))
        if thread not in NUT_THREAD_MODES:
            raise ParameterError(f"thread must be one of {', '.join(NUT_THREAD_MODES)}")
        return {"size": size, "thread": thread}

    def designation(self, p: dict[str, Any]) -> str:
        return f"ISO {self.number} - {p['size']}"

    def file_stem(self, p: dict[str, Any]) -> str:
        suffix = "_threaded" if p["thread"] == "modeled" else ""
        return f"ISO{self.number}_{p['size']}{suffix}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        nd = self.sizes[p["size"]]
        t = MetricThread(nd.D, nd.P)
        return [
            Dimension("D", "Thread diameter", nd.D),
            Dimension("P", "Pitch", nd.P),
            Dimension("s", "Width across flats", nd.s_nom),
            Dimension("s min", "Width across flats, min.", nd.s_min),
            Dimension("e", "Width across corners (modeled)", round(nd.e_nom, 3)),
            Dimension("e min", "Width across corners, min.", nd.e_min),
            Dimension("h max", "Overall height", nd.h_max),
            Dimension("h min", "Overall height, min.", nd.h_min),
            Dimension("m min", "Height of metal thread, min.", nd.m_min),
            Dimension("mw min", "Wrenching height", nd.mw_min),
            Dimension("dw min", "Bearing face dia.", nd.dw_min),
            Dimension("da max", "Countersink dia.", nd.da_max),
            Dimension("da min", "Countersink dia., min.", nd.da_min),
            Dimension("D1", "Minor diameter (basic)", round(t.d1, 3)),
            Dimension("D2", "Pitch diameter", round(t.d2, 3)),
            Dimension("m", f"Hex height (model: m max of {self.base})", nd.m_hex),
            Dimension("dc", "Collar dia. (model)", round(nd.dc, 3)),
            Dimension("di", "Insert outside dia. (model)", round(nd.di, 3)),
            Dimension("d insert", "Insert bore (model)", round(nd.d_insert, 3)),
            Dimension("h insert", "Insert height (model)", round(nd.insert_height, 3)),
            Dimension("t", "Collar wall / lip thickness (model)", round(nd.wall, 3)),
            Dimension("β", "Corner chamfer angle (modeled)", CHAMFER_ANGLE, "°"),
            Dimension("θ", "Countersink angle (modeled)", COUNTERSINK_ANGLE, "°"),
        ]

    def notes(self, p: dict[str, Any]) -> list[str]:
        nd = self.sizes[p["size"]]
        out = []
        if not nd.preferred:
            out.append(f"{nd.size} is a size to be avoided if possible.")
        out.append(
            "Assembly of two solids: the steel body (\"body\") and the polyamide "
            "insert (\"insert\"), so the STEP file keeps the insert separate."
        )
        if p["thread"] == "simplified":
            out.append(
                "Thread not modeled: plain bore at the basic minor diameter D1 through "
                "the hex, ready for a cosmetic thread."
            )
        else:
            out.append(
                "Thread modeled through the hex with the ISO 68-1 basic internal "
                "profile (root flat at D, crest flat at D1), right hand."
            )
        out.append(
            f"Modeled at nominal sizes: s nom, h max, e = s / cos 30°; hex height = "
            f"m max of {self.base}. Bearing face and top of the hex have a "
            f"{_fmt(CHAMFER_ANGLE)}° corner chamfer down to dw min and a "
            f"{_fmt(COUNTERSINK_ANGLE)}° countersink at da max."
        )
        out.append(
            "The standard leaves the shape of the prevailing torque element to the "
            "manufacturer. The collar, crimped lip and insert are typical "
            "proportions, not standardised. The insert is unthreaded, with a bore of "
            f"D1 - {_fmt(INSERT_BORE_SHRINK)} P = {nd.d_insert:.3f} mm."
        )
        out.append(
            f"The full designation adds the property class, e.g. "
            f"Prevailing torque hexagon nut ISO {self.number} - {nd.size} - {self.example_class}."
        )
        return out

    def build(self, p: dict[str, Any]) -> Part:
        part = build_nyloc(
            self.sizes[p["size"]], p["thread"], what=f"ISO {self.number} {p['size']}"
        )
        part.label = self.designation(p)
        return part


class ISO7040(_NylocNut):
    id = "iso7040"
    title = "ISO 7040"
    summary = (
        "Prevailing torque hexagon nuts with non-metallic insert (nyloc), "
        "regular height, M3 to M36"
    )
    source = "Values in mm, from ISO 7040:2012 Table 1."
    number = "7040"
    sizes = ISO7040_SIZES
    base = "ISO 4032"
    example_class = "8"


class ISO10511(_NylocNut):
    id = "iso10511"
    title = "ISO 10511"
    summary = (
        "Prevailing torque hexagon thin nuts with non-metallic insert (nyloc), "
        "M3 to M36"
    )
    source = "Values in mm, from ISO 10511:2012 (corrected version) Table 1."
    number = "10511"
    sizes = ISO10511_SIZES
    base = "ISO 4035"
    example_class = "05"

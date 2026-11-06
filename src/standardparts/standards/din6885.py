"""DIN 6885-1 parallel keys, deep (high) pattern, forms A, B and AB."""

from __future__ import annotations

import math
from typing import Any

from build123d import Axis, Edge, Face, Part, Vector, Wire, extrude, fillet

from .base import Dimension, Option, Parameter, ParameterError, Standard
from .din6885_data import SIZES, KeyData

FORMS = {
    "A": "A, both ends round",
    "B": "B, both ends square",
    "AB": "AB, one end round, one square",
}


def _fmt(x: float) -> str:
    return f"{x:g}"


def _plan(kd: KeyData, l: float, form: str) -> Face:
    """Plan-view outline in the XY plane, centred on the origin.

    Form AB has its round end towards -X and its square end towards +X.
    """
    hl, hb = l / 2, kd.b / 2
    round_neg = form in ("A", "AB")
    round_pos = form == "A"
    # Straight sides end b/2 short of a round end.
    x0 = -hl + hb if round_neg else -hl
    x1 = hl - hb if round_pos else hl
    p = Vector
    edges = [Edge.make_line(p(x0, -hb), p(x1, -hb))]
    if round_pos:
        edges.append(Edge.make_three_point_arc(p(x1, -hb), p(hl, 0), p(x1, hb)))
    else:
        edges.append(Edge.make_line(p(x1, -hb), p(x1, hb)))
    edges.append(Edge.make_line(p(x1, hb), p(x0, hb)))
    if round_neg:
        edges.append(Edge.make_three_point_arc(p(x0, hb), p(-hl, 0), p(x0, -hb)))
    else:
        edges.append(Edge.make_line(p(x0, hb), p(x0, -hb)))
    return Face(Wire(edges))


def edge_radius(kd: KeyData) -> float:
    """Rounding modeled on the key edges: s min."""
    return kd.s_min


def build_key(kd: KeyData, l: float, form: str) -> Part:
    """Build the key solid.

    Coordinate system: the key is centred on the origin in plan view, its
    length l runs along X (-l/2 .. l/2), its width b along Y (-b/2 .. b/2)
    and its height h along Z from z = 0 (the bottom, in the shaft keyway) to
    z = h. All edges are rounded with radius s min, except the tangent
    seams where a round end meets the flat sides.
    """
    if form not in FORMS:
        raise ParameterError(f"unknown form {form!r}")
    body = extrude(_plan(kd, l, form), amount=kd.h)
    # Vertical edges are either square-end corners (at x = +-l/2, rounded)
    # or tangent seams of a round end (at |x| = l/2 - b/2, left alone).
    x_seam = l / 2 - kd.b / 2 + 1e-6 * l
    vertical = body.edges().filter_by(Axis.Z)
    edges = [
        e
        for e in body.edges()
        if e not in vertical or abs(e.center().X) > x_seam
    ]
    key = fillet(edges, edge_radius(kd))
    if not key.is_valid or len(key.solids()) != 1:
        raise RuntimeError(f"key solid failed for DIN 6885 {form} {kd.size} x {l:g}")
    return key


def key_volume(kd: KeyData, l: float, form: str) -> float:
    """Exact volume of the modeled key (used by the tests)."""
    b, h, r = kd.b, kd.h, edge_radius(kd)
    # Rounded box: all 12 edges rounded with radius r.
    lb, bb, hb = l - 2 * r, b - 2 * r, h - 2 * r
    v_b = (
        lb * bb * hb
        + 2 * r * (lb * bb + lb * hb + bb * hb)
        + math.pi * r**2 * (lb + bb + hb)
        + 4 / 3 * math.pi * r**3
    )
    # Stadium prism with its top and bottom outline rounded (Pappus).
    spandrel = (1 - math.pi / 4) * r**2
    e = r * (10 - 3 * math.pi) / (3 * (4 - math.pi))  # spandrel centroid offset
    area = (l - b) * b + math.pi * b**2 / 4
    path = 2 * (l - b) + 2 * math.pi * (b / 2 - e)
    v_a = area * h - 2 * spandrel * path
    return {"A": v_a, "B": v_b, "AB": (v_a + v_b) / 2}[form]


def _normalise_size(raw: Any) -> str:
    s = str(raw).strip().lower().replace("×", "x").replace(" ", "")
    if "x" in s:
        try:
            b, h = (float(v) for v in s.split("x"))
        except ValueError:
            return s
        s = f"{b:g}x{h:g}"
    return s


class DIN6885(Standard):
    id = "din6885"
    title = "DIN 6885-1"
    summary = "Parallel keys, deep pattern, 2 x 2 to 100 x 50, forms A, B and AB"
    category = "Keys"
    source = "Values in mm, from DIN 6885-1 (1968-08 table)."

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="size",
                label="Key size b x h",
                kind="select",
                default="8x7",
                options=[
                    Option(k, f"{_fmt(kd.b)} × {_fmt(kd.h)}  (shaft {_fmt(kd.d_over)}–{_fmt(kd.d_to)} mm)")
                    for k, kd in SIZES.items()
                ],
            ),
            Parameter(
                name="length",
                label="Nominal length l",
                kind="length",
                default=40,
                depends_on="size",
                preferred={k: kd.standard_lengths() for k, kd in SIZES.items()},
                limits={k: [kd.l_min, kd.l_max] for k, kd in SIZES.items()},
                unit="mm",
                help="Overall length, end to end.",
            ),
            Parameter(
                name="form",
                label="Form",
                kind="select",
                default="A",
                options=[Option(k, v) for k, v in FORMS.items()],
                help="Form A suits keyways milled with an end mill, form B "
                "keyways cut with a side-and-face cutter.",
            ),
        ]

    def validate(self, raw: dict[str, Any]) -> dict[str, Any]:
        size = _normalise_size(raw.get("size", "8x7"))
        if size not in SIZES:
            raise ParameterError(f"unknown key size {size!r}; choose one of {', '.join(SIZES)}")
        kd = SIZES[size]
        try:
            length = float(raw.get("length", 40))
        except (TypeError, ValueError):
            raise ParameterError("length must be a number") from None
        if not math.isfinite(length):
            raise ParameterError("length must be a number")
        length = round(length, 2)
        if not kd.l_min <= length <= kd.l_max:
            raise ParameterError(
                f"length for {_fmt(kd.b)} x {_fmt(kd.h)} must be between "
                f"{_fmt(kd.l_min)} and {_fmt(kd.l_max)} mm"
            )
        form = str(raw.get("form", "A")).strip().upper()
        if form not in FORMS:
            raise ParameterError(f"form must be one of {', '.join(FORMS)}")
        return {"size": size, "length": length, "form": form}

    def designation(self, p: dict[str, Any]) -> str:
        kd = SIZES[p["size"]]
        return f"DIN 6885 {p['form']} {_fmt(kd.b)} x {_fmt(kd.h)} x {_fmt(p['length'])}"

    def file_stem(self, p: dict[str, Any]) -> str:
        return f"DIN6885_{p['form']}_{p['size']}x{_fmt(p['length'])}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        kd = SIZES[p["size"]]
        l = p["length"]
        bearing = {"A": l - kd.b, "B": l, "AB": l - kd.b / 2}[p["form"]]
        return [
            Dimension("b", "Key width (h9) = keyway width", kd.b),
            Dimension("h", "Key height", kd.h),
            Dimension("l", "Nominal length", l),
            Dimension("lt", "Bearing length (straight sides)", round(bearing, 3)),
            Dimension("d1", "Shaft diameter, over … up to",
                      f"{_fmt(kd.d_over)} … {_fmt(kd.d_to)}"),
            Dimension("t1", "Shaft keyway depth", f"{_fmt(kd.t1)} +{_fmt(kd.t1_tol)}"),
            Dimension("t2", "Hub keyway depth (back clearance)",
                      f"{_fmt(kd.t2)} +{_fmt(kd.t2_tol)}"),
            Dimension("t2 tight", "Hub keyway depth (interference)",
                      f"{_fmt(kd.t2_tight)} +{_fmt(kd.t2_tight_tol)}"),
            Dimension("b fit", "Keyway width tolerance",
                      "shaft P9 (tight) / N9 (normal); hub P9 / JS9", unit=""),
            Dimension("s", "Edge chamfer or rounding, min … max",
                      f"{_fmt(kd.s_min)} … {_fmt(kd.s_max)}"),
            Dimension("r", "Edge rounding (model)", edge_radius(kd)),
            Dimension("l range", "Standard lengths, min … max",
                      f"{_fmt(kd.l_min)} … {_fmt(kd.l_max)}"),
            Dimension("mass", "Approx. mass in g (steel, model)",
                      round(key_volume(kd, l, p["form"]) * 7.85e-3, 2), unit="g"),
        ]

    def notes(self, p: dict[str, Any]) -> list[str]:
        kd = SIZES[p["size"]]
        l = p["length"]
        out = []
        if l not in kd.standard_lengths():
            pref = ", ".join(_fmt(x) for x in kd.standard_lengths())
            out.append(
                f"{_fmt(l)} mm is not a standard length for {_fmt(kd.b)} x {_fmt(kd.h)} "
                f"(standard: {pref})."
            )
        out.append(
            f"For shafts over {_fmt(kd.d_over)} up to {_fmt(kd.d_to)} mm: cut the shaft "
            f"keyway {_fmt(kd.b)} wide and t1 = {_fmt(kd.t1)} deep, the hub keyway "
            f"t2 = {_fmt(kd.t2)} deep (both measured from the shaft or bore surface "
            "at the keyway side)."
        )
        if p["form"] == "AB":
            out.append("Form AB: round end towards -X, square end towards +X.")
        out.append(
            f"Centred on the origin: length along X, width along Y, height along Z "
            f"from z = 0 (keyway bottom) to z = h = {_fmt(kd.h)} mm."
        )
        out.append(
            f"Modeled at nominal size with all edges rounded r = s min = "
            f"{_fmt(edge_radius(kd))} mm (the standard allows a chamfer or a rounding)."
        )
        return out

    def build(self, p: dict[str, Any]) -> Part:
        part = build_key(SIZES[p["size"]], p["length"], p["form"])
        part.label = self.designation(p)
        return part

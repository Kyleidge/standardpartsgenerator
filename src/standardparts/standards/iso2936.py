"""ISO 2936 hexagon socket screw keys (L-shaped hex keys)."""

from __future__ import annotations

import math
from typing import Any

from build123d import Edge, Part, Pos, Rot, Transition, Vector, Wire, sweep

from ..tooling import cone_trim, corner_radius, hex_section
from .base import Dimension, Option, Parameter, ParameterError, Standard
from .iso2936_data import SERIES, SERIES_SUFFIX, SIZES, KeyData

# End chamfer used by the model, as a fraction of f max (Figure 1).
END_CHAMFER_FRACTION = 0.5


def _fmt(x: float) -> str:
    return f"{x:g}"


def end_chamfer(kd: KeyData) -> float:
    """Axial (= radial, 45 deg) size of the modeled end chamfer."""
    return END_CHAMFER_FRACTION * kd.f_max


def centreline_length(kd: KeyData, l1: float) -> float:
    """Length of the key's centreline: two straight arms and the bend."""
    s, r = kd.s, kd.bend_radius
    rc = r + s / 2
    return (kd.l2 - s / 2 - rc) + (l1 - s / 2 - rc) + math.pi / 2 * rc


def build_key(kd: KeyData, l1: float, chamfer: bool = True) -> Part:
    """Build the key.

    Coordinate system: the short arm lies on the Z axis with its end face
    at z = 0 (the end that goes into the screw) and runs up to the bend;
    the long arm runs along +X at the top. The outside of the long arm is at
    z = l2 and its end at x = l1 - s / 2, so l1 and l2 are measured as in
    Figure 1. The key lies in the XZ plane; two flats face the inside and
    the outside of the bend.
    """
    s, r = kd.s, kd.bend_radius
    rc = r + s / 2
    z_axis = kd.l2 - s / 2   # long arm axis
    zc = z_axis - rc         # bend centre (x = rc)
    x_end = l1 - s / 2
    p0, p1 = Vector(0, 0, 0), Vector(0, 0, zc)
    p2, p3 = Vector(rc, 0, z_axis), Vector(x_end, 0, z_axis)
    mid = Vector(rc - rc * math.cos(math.pi / 4), 0, zc + rc * math.sin(math.pi / 4))
    path = Wire([
        Edge.make_line(p0, p1),
        Edge.make_three_point_arc(p1, mid, p2),
        Edge.make_line(p2, p3),
    ])
    # hex_section has flats parallel to X (facing +-Y); turn it so two flats
    # face +-X, i.e. lie across the plane of the bend.
    section = Rot(0, 0, 30) * hex_section(s, kd.e_max)
    key = sweep(section, path=path, transition=Transition.RIGHT)
    if chamfer:
        f = end_chamfer(kd)
        r_out = corner_radius(s, kd.e_max)
        cutter = cone_trim(r_out - f, r_out, 1.0)
        key = key - cutter  # short arm end, at z = 0 facing -Z
        key = key - Pos(x_end, 0, z_axis) * Rot(0, -90, 0) * cutter
    if len(key.solids()) != 1 or not key.is_valid:
        raise RuntimeError(f"ISO 2936 key {kd.size} failed")
    return key


class ISO2936(Standard):
    id = "iso2936"
    title = "ISO 2936"
    summary = "Hexagon socket screw keys (hex keys), s = 0.7 to 36 mm"
    category = "Tools"
    source = "Values in mm, from ISO 2936:2014 Table 1."

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="size",
                label="Width across flats s",
                kind="select",
                default="5",
                options=[Option(s, f"{s} mm") for s in SIZES],
            ),
            Parameter(
                name="series",
                label="Length series",
                kind="select",
                default="standard",
                options=[
                    Option("standard", "Standard"),
                    Option("long", "Long (M), s = 1.3 to 18"),
                    Option("extra-long", "Extra-long (L), s = 1.3 to 18"),
                ],
            ),
        ]

    def validate(self, raw: dict[str, Any]) -> dict[str, Any]:
        size = str(raw.get("size", "5"))
        if size not in SIZES:
            raise ParameterError(f"unknown size {size!r}; choose one of {', '.join(SIZES)}")
        series = str(raw.get("series", "standard"))
        if series not in SERIES:
            raise ParameterError(f"unknown series {series!r}; choose one of {', '.join(SERIES)}")
        if series not in SIZES[size].l1:
            raise ParameterError(f"ISO 2936 has no {series} key for s = {size}")
        return {"size": size, "series": series}

    def designation(self, p: dict[str, Any]) -> str:
        suffix = SERIES_SUFFIX[p["series"]]
        return f"Socket screw key ISO 2936 - {p['size']}{' ' + suffix if suffix else ''}"

    def file_stem(self, p: dict[str, Any]) -> str:
        return f"ISO2936_{p['size']}{SERIES_SUFFIX[p['series']]}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        kd = SIZES[p["size"]]
        l1 = kd.l1[p["series"]]
        return [
            Dimension("s", "Width across flats (max / min)", f"{kd.s_max:.2f} / {kd.s_min:.2f}"),
            Dimension("e", "Width across corners (max / min)", f"{kd.e_max:.2f} / {kd.e_min:.2f}"),
            Dimension("l1", f"Long arm, {p['series']} (0 / {_fmt(kd.l1_dev)})", l1),
            Dimension("l2", f"Short arm (0 / {_fmt(kd.l2_dev)})", kd.l2),
            Dimension("r", "Inner bend radius (model, min. allowed)", kd.bend_radius),
            Dimension("f max", "End chamfer allowed, (e max − s min) / 2", round(kd.f_max, 3)),
            Dimension("f", "End chamfer (model, 45°)", round(end_chamfer(kd), 3)),
        ]

    def notes(self, p: dict[str, Any]) -> list[str]:
        kd = SIZES[p["size"]]
        return [
            (
                "Modeled at s max (the nominal size from s = 1.5 up), corners turned "
                "to e max, l1 and l2 at their maximum (the limit deviations are 0 / −x)."
            ),
            (
                f"Bend: 90° with the smallest inner radius allowed, r = max(s, 1.5 mm) = "
                f"{_fmt(kd.bend_radius)} mm; two flats face the inside and the outside "
                "of the bend."
            ),
            (
                "Both ends are square to their arm with a 45° chamfer of half the "
                "largest size ISO 2936 allows; a sharp or rounded edge within f max "
                "is equally permitted."
            ),
            (
                "The short arm lies on the Z axis with its end at z = 0; the long arm "
                "runs along +X, its outside at z = l2."
            ),
        ]

    def build(self, p: dict[str, Any]) -> Part:
        kd = SIZES[p["size"]]
        part = build_key(kd, kd.l1[p["series"]])
        part.label = self.designation(p)
        return part

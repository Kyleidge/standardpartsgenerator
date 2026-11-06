"""Geometry helpers shared by the hand-tool standards (hex keys, bits,
sockets): hexagon sections with turned corners and revolved cutters for
chamfers and grooves.

Cutters are built around the Z axis. Every cutter reaches a little past the
surface it trims (``eps``), so no boolean works on coincident faces.
"""

from __future__ import annotations

import math

from build123d import BuildSketch, Circle, Face, Mode, Part, RegularPolygon

from .geometry import SQRT3, revolve_profile


def hex_section(s: float, e: float | None = None) -> Face:
    """Hexagon of width s across flats in the XY plane, centred on the
    origin, flats parallel to the X axis. If e is below the sharp-corner
    width (2 s / sqrt 3) the corners are turned to a circle of diameter e."""
    with BuildSketch() as sk:
        RegularPolygon(radius=s / 2, side_count=6, major_radius=False)
        if e is not None and e < 2 * s / SQRT3 - 1e-9:
            Circle(e / 2, mode=Mode.INTERSECT)
    return sk.sketch.faces()[0]


def corner_radius(s: float, e: float | None) -> float:
    """Radius of the corners of `hex_section(s, e)`."""
    sharp = s / SQRT3
    return sharp if e is None else min(sharp, e / 2)


def cone_trim(r_face: float, r_out: float, slope: float, eps: float = 0.05) -> Part:
    """Ring cutter that trims a body lying at z >= 0 to the cone
    r = r_face + slope * z: everything outside the cone up to radius r_out
    (the body's largest radius) is removed. Use it for end chamfers
    (r_face = radius left on the end face) and for tapers.

    slope = tan of the cone's angle to the axis. Place it with a Location;
    the cutter itself spans z = -eps to the height where the cone passes
    r_out + eps.
    """
    r_big = r_out + eps
    z_top = (r_big - r_face) / slope
    return revolve_profile([
        (r_face - eps * slope, -eps),
        (r_big, -eps),
        (r_big, z_top),
    ])


def round_groove(
    z_low: float, z_high: float, r_bottom: float, radius: float, r_out: float,
    eps: float = 0.05,
) -> Part:
    """Annular groove cutter: a flat bottom at radius r_bottom from z_low to
    z_high (equal for a plain round groove), flanks of the given radius
    running out to r_out (the surface the groove is cut into)."""
    rc = r_bottom + radius
    r_big = r_out + eps
    if rc - r_big >= radius:
        raise ValueError("groove does not reach the surface")
    dz = math.sqrt(radius * radius - (rc - r_big) ** 2)
    c45 = math.cos(math.radians(45))
    items: list = [
        (r_big, z_low - dz),
        ("arc", (rc - radius * c45, z_low - radius * c45), (r_bottom, z_low)),
    ]
    if z_high > z_low + 1e-9:
        items.append((r_bottom, z_high))
    items.append(("arc", (rc - radius * c45, z_high + radius * c45), (r_big, z_high + dz)))
    return revolve_profile(items)


def v_groove(
    zc: float, r_bottom: float, root_radius: float, included_angle: float, r_out: float,
    eps: float = 0.05,
) -> Part:
    """Annular V groove cutter centred at zc: flanks at half the included
    angle to the radial direction, root rounded with root_radius so the
    bottom lies at r_bottom, running out to r_out."""
    a = math.radians(included_angle / 2)
    rc = r_bottom + root_radius
    apex = rc - root_radius / math.sin(a)
    r_big = r_out + eps
    dz_out = (r_big - apex) * math.tan(a)
    tz = root_radius * math.cos(a)
    tr = rc - root_radius * math.sin(a)
    return revolve_profile([
        (r_big, zc - dz_out),
        (tr, zc - tz),
        ("arc", (r_bottom, zc), (tr, zc + tz)),
        (r_big, zc + dz_out),
    ])

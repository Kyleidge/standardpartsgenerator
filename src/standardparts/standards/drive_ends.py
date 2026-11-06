"""ISO 1173 male drive ends (forms A, C, E, G) as solids, for bits.

`drive_end_shank` builds the drive end at the top of a shank along +Z: the
end face at z_end, the drive end below it (length l1 of ISO 1173) and the
shank continuing down to z_bottom with the section the drive end grows out
of. The interpretation of each form is described in iso1173_data.
"""

from __future__ import annotations

import math

from build123d import Align, Box, Cylinder, Part, Pos, Rot, extrude

from ..geometry import revolve_profile
from ..tooling import cone_trim, hex_section, round_groove, v_groove
from .iso1173_data import (
    END_CHAMFER_ANGLE,
    END_CHAMFER_LENGTH,
    FORM_C4_CROSS_HOLE,
    FORM_C_GROOVE_ANGLE,
    SHOULDER_RADIUS,
    DriveEnd,
)

# Form A: the shank behind the R 0.6 shoulder is not specified; the model
# makes it this much larger than the collar d1 (on the diameter).
FORM_A_SHANK_STEP = 2.0


def shank_radius(de: DriveEnd) -> float:
    """Radius of the smallest cylinder around the shank below the drive end."""
    if de.form == "A":
        return de.d1 / 2 + FORM_A_SHANK_STEP / 2
    return de.outer_radius


def shank_is_hexagon(de: DriveEnd) -> bool:
    """Forms C and E: the hexagon itself is the shank. A and G: round."""
    return de.form in ("C", "E")


def _end_chamfer(de: DriveEnd, z_end: float) -> Part:
    slope = math.tan(math.radians(END_CHAMFER_ANGLE))
    r_out = de.e1_max / 2
    r_face = r_out - END_CHAMFER_LENGTH * slope
    return Pos(0, 0, z_end) * Rot(180, 0, 0) * cone_trim(r_face, r_out, slope)


def _hex_prism(de: DriveEnd, z0: float, z1: float) -> Part:
    return Pos(0, 0, z0) * extrude(hex_section(de.s1_max, de.e1_max), amount=z1 - z0)


def _form_a(de: DriveEnd, z_bottom: float, z_end: float) -> Part:
    r1 = de.d1 / 2
    rb = shank_radius(de)
    z_sh = z_end - de.l1
    zg = z_end - de.l3
    z_hex = z_end - de.l5
    R = SHOULDER_RADIUS
    c45 = math.cos(math.radians(45))
    groove_dz = math.sqrt(de.r**2 - (de.d3 / 2 + de.r - r1) ** 2)
    body = revolve_profile([
        (0.0, z_bottom),
        (rb, z_bottom),
        (rb, z_sh),
        (r1 + R, z_sh),
        ("arc", (r1 + R - R * c45, z_sh + R - R * c45), (r1, z_sh + R)),
        (r1, zg - groove_dz),
        ("arc", (de.d3 / 2 + de.r - de.r * c45, zg - de.r * c45), (de.d3 / 2, zg)),
        ("arc", (de.d3 / 2 + de.r - de.r * c45, zg + de.r * c45), (r1, zg + groove_dz)),
        (r1, z_hex),
        (0.0, z_hex),
    ])
    hexagon = _hex_prism(de, z_hex - 0.5, z_end) - _end_chamfer(de, z_end)
    return body + hexagon


def _form_c(de: DriveEnd, z_bottom: float, z_end: float) -> Part:
    body = _hex_prism(de, z_bottom, z_end) - _end_chamfer(de, z_end)
    zg = z_end - de.l3
    if de.d3 is None:  # size 4: cross hole through the flats
        hole = Pos(0, 0, zg) * Rot(90, 0, 0) * Cylinder(
            FORM_C4_CROSS_HOLE / 2, 2 * de.s1_max, align=(Align.CENTER, Align.CENTER, Align.CENTER)
        )
        return body - hole
    groove = v_groove(zg, de.d3 / 2, de.r, FORM_C_GROOVE_ANGLE, de.e1_max / 2)
    return body - groove


def _form_e(de: DriveEnd, z_bottom: float, z_end: float) -> Part:
    body = _hex_prism(de, z_bottom, z_end) - _end_chamfer(de, z_end)
    z_high = z_end - de.l3
    groove = round_groove(z_high - de.l7, z_high, de.d3 / 2, de.r, de.e1_max / 2)
    return body - groove


def _form_g(de: DriveEnd, z_bottom: float, z_end: float) -> Part:
    r1 = de.d1 / 2
    zg = z_end - de.l3
    body = revolve_profile([(0.0, z_bottom), (r1, z_bottom), (r1, z_end), (0.0, z_end)])
    body = body - round_groove(zg, zg, de.d3 / 2, de.r, r1)
    flat_len = de.l3 - de.l5
    half = (de.e1_max + de.e1_min) / 4  # flats at the mean of e1, facing +-X
    width = r1 + 0.5
    for x0 in (half, -half - width):
        box = Box(width, de.d1 + 1, flat_len + 1, align=(Align.MIN, Align.CENTER, Align.MIN))
        body = body - Pos(x0, 0, z_end - flat_len) * box
    return body


_BUILDERS = {"A": _form_a, "C": _form_c, "E": _form_e, "G": _form_g}


def drive_end_shank(de: DriveEnd, z_bottom: float, z_end: float) -> Part:
    """Drive end with its end face at z_end on a shank reaching down to
    z_bottom (z_bottom must lie below z_end - l1)."""
    if z_bottom > z_end - de.l1 + 1e-9:
        raise ValueError(f"shank of {de.name} shorter than its drive end")
    part = _BUILDERS[de.form](de, z_bottom, z_end)
    if len(part.solids()) != 1 or not part.is_valid:
        raise RuntimeError(f"ISO 1173 drive end {de.name} failed")
    return part


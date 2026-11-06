"""ISO 1174-1 female driving squares (types C and D) as cutters.

`female_square_cutter` returns the tool solid for the square pocket of a
socket whose drive face lies at z_face, the pocket opening towards +Z and
reaching down to z_face - l2. The model choices are listed in iso1174_data.
Flats face +-X and +-Y; the type C recesses sit on the +-X faces and the
type D hole goes through the +X wall.
"""

from __future__ import annotations

import math

from build123d import (
    Align,
    BuildSketch,
    Circle,
    Cylinder,
    Face,
    Mode,
    Part,
    Pos,
    Rectangle,
    Rot,
    Sphere,
    extrude,
    loft,
)

from .iso1174_data import FemaleSquare


def square_section(side: float, corner_dia: float) -> Face:
    """Square of the given side, centred, corners turned to corner_dia."""
    with BuildSketch() as sk:
        Rectangle(side, side)
        if corner_dia < side * math.sqrt(2):
            Circle(corner_dia / 2, mode=Mode.INTERSECT)
    return sk.sketch.faces()[0]


def female_square_cutter(
    sq: FemaleSquare, retainer: str, z_face: float, wall: float, extra_depth: float = 0.0
) -> Part:
    """Square pocket, mouth chamfer and retaining feature.

    `wall` is the radius to drill the type D hole out to (the outside of the
    socket at the hole, plus a margin). `extra_depth` makes the pocket that
    much deeper than l2 min."""
    if retainer not in sq.types:
        raise ValueError(f"square {sq.size} has no type {retainer}")
    s2, e2, r1 = sq.s2, sq.e2, sq.r1
    depth = sq.l2 + extra_depth
    pocket = Pos(0, 0, z_face - depth) * extrude(square_section(s2, e2), amount=depth + 1)
    # Mouth chamfer of size r1 at 45 deg: a loft between two sections on the
    # 45 deg planes, extended by eps at both ends so it crosses the pocket
    # walls and the drive face instead of meeting them edge on edge.
    eps = 0.05
    mouth = loft([
        Pos(0, 0, z_face - r1 - eps) * square_section(s2 - 2 * eps, e2 - 2 * eps),
        Pos(0, 0, z_face + eps) * square_section(s2 + 2 * (r1 + eps), e2 + 2 * (r1 + eps)),
    ])
    cutter = pocket + mouth
    z_ret = z_face - sq.l3
    if retainer == "C":
        rb = sq.ball / 2
        x = s2 / 2 + sq.l4 - rb  # ball centre when engaged: sunk l4 into the face
        for sign in (1, -1):
            # Pole axis along X: a sphere with its pole along Z gives OCCT
            # trouble against the square's planar faces.
            cutter = cutter + Pos(sign * x, 0, z_ret) * Rot(0, 90, 0) * Sphere(rb)
    else:
        hole = Pos(0, 0, z_ret) * Rot(0, 90, 0) * Cylinder(
            sq.d3 / 2, wall, align=(Align.CENTER, Align.CENTER, Align.MIN)
        )
        cutter = cutter + hole
    return cutter

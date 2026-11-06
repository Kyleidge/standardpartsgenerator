"""Shared geometry helpers built on build123d / OpenCascade."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from build123d import (
    Align,
    Axis,
    Cone,
    Edge,
    Face,
    Helix,
    Part,
    Pos,
    RegularPolygon,
    Vector,
    Wire,
    extrude,
    revolve,
    sweep,
)

from . import progress

SQRT3 = math.sqrt(3.0)

# A profile point is (radius, z). An arc is ("arc", (r_mid, z_mid), (r_end, z_end)).
ProfileItem = tuple[float, float] | tuple[str, tuple[float, float], tuple[float, float]]


def _xz(p: tuple[float, float]) -> Vector:
    return Vector(p[0], 0.0, p[1])


def revolve_profile(items: Sequence[ProfileItem]) -> Part:
    """Revolve a closed (radius, z) profile 360 degrees around the Z axis.

    The first item must be a point. Each later item is either a point
    (straight segment from the previous point) or an arc tuple. The profile
    is closed back to the first point automatically. Collinear segments are
    kept as separate edges, so they become separate faces on the solid; this
    is how the thread region is split from the plain shank.
    """
    start = items[0]
    assert isinstance(start[0], (int, float))
    edges: list[Edge] = []
    current = start
    for item in list(items[1:]) + [start]:
        if isinstance(item[0], str):
            _, mid, end = item  # type: ignore[misc]
            edges.append(Edge.make_three_point_arc(_xz(current), _xz(mid), _xz(end)))
            current = end
        else:
            if math.dist(current, item) > 1e-9:  # type: ignore[arg-type]
                edges.append(Edge.make_line(_xz(current), _xz(item)))  # type: ignore[arg-type]
            current = item
    face = Face(Wire(edges))
    return revolve(face, Axis.Z, 360)


@dataclass(frozen=True)
class MetricThread:
    """ISO 68-1 basic profile for an external metric thread."""

    d: float  # major diameter
    P: float  # pitch

    @property
    def H(self) -> float:
        return SQRT3 / 2 * self.P

    @property
    def d1(self) -> float:
        """Basic minor diameter (root of the basic profile)."""
        return self.d - 1.25 * self.H

    @property
    def d3(self) -> float:
        """Minor diameter of the external thread (rounded root), ISO 724."""
        return self.d - 1.226869 * self.P

    @property
    def d2(self) -> float:
        return self.d - 0.75 * self.H


def _ridge_segment(thread: MetricThread, z_start: float, turns: int) -> Part:
    P = thread.P
    r_major = thread.d / 2
    r_root = thread.d1 / 2 - 0.05 * P
    half_crest = P / 16
    half_root = half_crest + (r_major - r_root) * math.tan(math.radians(30))
    helix = Helix(pitch=P, height=turns * P, radius=r_root, center=(0, 0, z_start))
    pts = [
        (r_root, -half_root),
        (r_major, -half_crest),
        (r_major, half_crest),
        (r_root, half_root),
    ]
    profile = Face(
        Wire.make_polygon([Vector(r, 0, z + z_start) for r, z in pts], close=True)
    )
    return sweep(profile, path=helix, is_frenet=True)


def helical_thread(
    thread: MetricThread,
    z_start: float,
    z_end: float,
    max_turns: int = 8,
) -> Part:
    """Right-hand helical ISO 68-1 thread ridge from z_start to at least z_end.

    The ridge is the basic profile (crest flat P/8 at d, flanks at 60 deg).
    It reaches a little below d1 / 2 so it overlaps the core cylinder and
    fuses cleanly. Ends are left square; trim them with an envelope solid.

    Long helices are swept in segments of at most `max_turns` whole turns
    and glued together: a single sweep over dozens of turns is approximated
    too loosely and later booleans against it fail.
    """
    P = thread.P
    turns = max(1, math.ceil((z_end - z_start) / P - 1e-9))
    progress.report("thread", turns=turns)
    segments = []
    z = z_start
    while turns > 0:
        n = min(max_turns, turns)
        segments.append(_ridge_segment(thread, z, n))
        z += n * P
        turns -= n
    if len(segments) == 1:
        return segments[0]
    return segments[0].fuse(*segments[1:], glue=True)


def hex_socket(s: float, depth: float, z_top: float, drill_angle: float = 118.0) -> Part:
    """Hexagon socket tool body: hex prism of width s across flats, depth
    `depth` below z_top, finished with a conical drill point."""
    prism = Pos(0, 0, z_top - depth) * extrude(
        RegularPolygon(radius=s / 2, side_count=6, major_radius=False), amount=depth + s
    )
    # Keep the drill circle slightly inside the flats so the cone base does
    # not touch the hexagon edges (tangent contact makes bad topology).
    r_drill = 0.96 * s / 2
    h_cone = r_drill / math.tan(math.radians(drill_angle / 2))
    cone = Pos(0, 0, z_top - depth - h_cone) * Cone(
        bottom_radius=0,
        top_radius=r_drill,
        height=h_cone + 1e-3 * s,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    )
    return prism + cone


def chamfered_hex(
    s: float,
    z_bottom: float,
    z_top: float,
    top_chamfer_dia: float | None = None,
    bottom_chamfer_dia: float | None = None,
    chamfer_angle: float = 30.0,
) -> Part:
    """Hexagon prism (width s across flats, flats parallel to the X axis)
    with the usual conical corner chamfers of nuts and hex heads.

    A chamfer starts on the end face at `*_chamfer_dia` (typically about
    0.95 s, or dw on a bearing face) and runs outwards at `chamfer_angle`
    degrees to the end face until it clears the corners. Pass None for a
    sharp end.
    """
    height = z_top - z_bottom
    prism = Pos(0, 0, z_bottom) * extrude(
        RegularPolygon(radius=s / 2, side_count=6, major_radius=False), amount=height
    )
    if top_chamfer_dia is None and bottom_chamfer_dia is None:
        return prism
    r_corner = s / SQRT3 * 1.02  # a little past the corners
    t = math.tan(math.radians(chamfer_angle))
    pts: list[tuple[float, float]] = [(0.0, z_bottom)]
    if bottom_chamfer_dia is None:
        pts.append((r_corner, z_bottom))
    else:
        r0 = bottom_chamfer_dia / 2
        pts += [(r0, z_bottom), (r_corner, z_bottom + (r_corner - r0) * t)]
    if top_chamfer_dia is None:
        pts.append((r_corner, z_top))
    else:
        r1 = top_chamfer_dia / 2
        pts += [(r_corner, z_top - (r_corner - r1) * t), (r1, z_top)]
    pts.append((0.0, z_top))
    return prism & revolve_profile(pts)

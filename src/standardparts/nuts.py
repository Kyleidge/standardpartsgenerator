"""Shared builders for internally threaded parts (nuts).

Conventions used by every nut in this project:

* Z is the nut axis. The bearing face is at z = z_bottom (0 for the
  standards here) and the nut goes up to z_top.
* Thread modes use the keys of screws.THREAD_MODES. "simplified" is a plain
  bore at the basic minor diameter D1, which is what CAD part libraries
  ship. "modeled" is a right-hand helical internal thread with the ISO 68-1
  basic profile: flat root P/8 wide at D, flat crest P/4 wide at D1.
* Bore ends can have a countersink: a cone of included angle `angle` that
  starts at diameter da on the end face.

The modeled thread follows screws.py: the body is bored at D, an inward
helical ridge (swept in segments of at most 8 turns) is trimmed to just
inside the nut faces and fused on, and the countersinks are cut afterwards,
which also removes the trimmed ridge ends. The result is checked against an
exact analytic volume, retrying at other thread start angles, because OCCT
booleans with helical sweeps sometimes return wrong solids without raising
(M4 and M10 need the retry).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from build123d import Face, Helix, Part, Rot, Vector, Wire, sweep

from . import progress
from .geometry import MetricThread, revolve_profile
from .screws import RIDGE_START_ANGLES, THREAD_MODES

NUT_THREAD_MODES = {
    "simplified": "Simplified (plain bore at D1)",
    "modeled": THREAD_MODES["modeled"],
}
assert NUT_THREAD_MODES.keys() == THREAD_MODES.keys()

TAN30 = math.tan(math.radians(30.0))


@dataclass(frozen=True)
class Countersink:
    """Conical countersink at a bore end: diameter `da` on the end face,
    included angle `angle` in degrees."""

    da: float
    angle: float = 120.0

    @property
    def slope(self) -> float:
        """Radial shrink per unit of depth into the part."""
        return math.tan(math.radians(self.angle / 2))

    def depth(self, r: float) -> float:
        """Depth below the end face at which the cone has radius r."""
        return max(0.0, (self.da / 2 - r) / self.slope)


def ridge_fraction(thread: MetricThread, r: float) -> float:
    """Share of the axial length taken by nut material at radius r
    (D1/2 <= r <= D/2) for the ISO 68-1 basic internal profile."""
    return (thread.P / 4 + 2 * (r - thread.d1 / 2) * TAN30) / thread.P


def bore_volume(r: float, height: float, bottom: Countersink | None,
                top: Countersink | None) -> float:
    """Volume of a bore of radius r through a part of the given height,
    plus the conical countersinks outside r."""
    v = math.pi * r * r * height
    for cs in (bottom, top):
        if cs is None or cs.da / 2 <= r:
            continue
        r1 = cs.da / 2
        t = cs.depth(r)
        v += math.pi * t / 3 * (r1 * r1 + r1 * r + r * r) - math.pi * r * r * t
    return v


def internal_thread_volume(thread: MetricThread, height: float,
                           bottom: Countersink | None, top: Countersink | None,
                           steps: int = 64) -> float:
    """Exact volume of nut material the modeled thread adds inside a bore at
    D, between the countersinks.

    At radius r the helical ridge fills ridge_fraction(r) of every axial
    line, so its volume inside an axisymmetric region is the integral of that
    fraction over the region (Simpson's rule; the integrand is a cubic).
    """
    r0, r1 = thread.d1 / 2, thread.d / 2

    def f(r: float) -> float:
        length = height
        for cs in (bottom, top):
            if cs is not None:
                length -= cs.depth(r)
        return ridge_fraction(thread, r) * max(0.0, length) * 2 * math.pi * r

    n = steps + steps % 2
    h = (r1 - r0) / n
    total = f(r0) + f(r1)
    for i in range(1, n):
        total += (4 if i % 2 else 2) * f(r0 + i * h)
    return total * h / 3


def _internal_ridge_segment(thread: MetricThread, z_start: float, turns: int,
                            r_out: float) -> Part:
    P = thread.P
    r_crest = thread.d1 / 2
    half_crest = P / 8
    half_out = half_crest + (r_out - r_crest) * TAN30
    helix = Helix(pitch=P, height=turns * P, radius=r_crest, center=(0, 0, z_start))
    pts = [
        (r_crest, -half_crest),
        (r_out, -half_out),
        (r_out, half_out),
        (r_crest, half_crest),
    ]
    profile = Face(
        Wire.make_polygon([Vector(r, 0, z + z_start) for r, z in pts], close=True)
    )
    return sweep(profile, path=helix, is_frenet=True)


def internal_helical_thread(
    thread: MetricThread,
    z_start: float,
    z_end: float,
    max_turns: int = 8,
) -> Part:
    """Right-hand helical ridge of an ISO 68-1 internal thread, pointing
    inwards, from z_start to at least z_end.

    The crest is the P/4 flat at D1. The flanks run at 60 deg out to a
    little beyond D/2 (0.05 P) so the ridge overlaps a body bored at D and
    fuses cleanly; at D the ridge is 7P/8 wide, leaving the P/8 root flat.
    Ends are left square. Swept in segments of at most `max_turns` turns,
    like geometry.helical_thread.
    """
    P = thread.P
    r_out = thread.d / 2 + 0.05 * P
    turns = max(1, math.ceil((z_end - z_start) / P - 1e-9))
    progress.report("thread", turns=turns)
    segments = []
    z = z_start
    while turns > 0:
        n = min(max_turns, turns)
        segments.append(_internal_ridge_segment(thread, z, n, r_out))
        z += n * P
        turns -= n
    if len(segments) == 1:
        return segments[0]
    return segments[0].fuse(*segments[1:], glue=True)


def _bore_tool(r: float, z0: float, z1: float, bottom: Countersink | None,
               top: Countersink | None, ext: float) -> Part:
    """Bore of radius r with optional countersinks, reaching `ext` beyond
    both end faces so no tool face coincides with a part face."""
    pts: list[tuple[float, float]] = [(0.0, z0 - ext)]
    if bottom is not None:
        pts += [(bottom.da / 2 + ext * bottom.slope, z0 - ext), (r, z0 + bottom.depth(r))]
    else:
        pts.append((r, z0 - ext))
    if top is not None:
        pts += [(r, z1 - top.depth(r)), (top.da / 2 + ext * top.slope, z1 + ext)]
    else:
        pts.append((r, z1 + ext))
    pts.append((0.0, z1 + ext))
    return revolve_profile(pts)


def _countersink_tool(cs: Countersink, z_face: float, inward: float, r_in: float,
                      ext: float) -> Part:
    """Cone of a countersink, from `ext` outside the face down to radius
    r_in, closed by a flat disc. `inward` is +1 for a bottom face (the part
    lies at z > z_face) and -1 for a top face."""
    z_out = z_face - inward * ext
    z_in = z_face + inward * cs.depth(r_in)
    pts = [
        (0.0, z_out),
        (cs.da / 2 + ext * cs.slope, z_out),
        (r_in, z_in),
        (0.0, z_in),
    ]
    return revolve_profile(pts if inward > 0 else pts[::-1])


def threaded_nut(
    body: Part,
    thread: MetricThread,
    z_bottom: float,
    z_top: float,
    mode: str,
    bottom: Countersink | None = None,
    top: Countersink | None = None,
    what: str = "nut",
) -> Part:
    """Bore and thread a solid `body` (e.g. a chamfered hex prism) along Z
    from z_bottom to z_top.

    "simplified": plain bore at D1 with the countersinks.
    "modeled": bore at D, helical ISO 68-1 internal thread, then the
    countersinks, which also cut the thread ends.

    The countersinks must be wider than D, and the body must be solid out to
    beyond da / 2 near both faces. The modeled mode needs both countersinks:
    they are what trims the helical ridge at the faces.
    """
    if mode not in THREAD_MODES:
        raise ValueError(f"unknown thread mode {mode!r}")
    P = thread.P
    R = thread.d / 2
    r1 = thread.d1 / 2
    height = z_top - z_bottom
    for cs in (bottom, top):
        if cs is not None and cs.da / 2 <= R + 0.05 * P:
            raise ValueError(f"countersink da {cs.da} is too small for D {thread.d}")

    if mode == "simplified":
        out = body - _bore_tool(r1, z_bottom, z_top, bottom, top, 0.5 * P)
        expected = body.volume - bore_volume(r1, height, bottom, top)
        if (
            len(out.solids()) != 1
            or not out.is_valid
            or abs(out.volume - expected) > 1e-4 * body.volume
        ):
            raise RuntimeError(f"bore failed for {what}")
        return out

    if bottom is None or top is None:
        raise ValueError("a modeled internal thread needs countersinks at both ends")
    ext = P
    core = body - _bore_tool(R, z_bottom, z_top, None, None, ext)
    expected_core = body.volume - bore_volume(R, height, bottom, top)
    ridge_volume = internal_thread_volume(thread, height, bottom, top)
    expected = expected_core + ridge_volume
    r_in = r1 - 0.1 * P
    tools = [
        _countersink_tool(bottom, z_bottom, +1, r_in, ext),
        _countersink_tool(top, z_top, -1, r_in, ext),
    ]
    # Trim the ridge to inside the nut first: ridge tails crossing the end
    # faces make the fuse silently fail. The trim planes lie where the
    # countersink is still wider than the ridge, so the countersink cut
    # afterwards removes the trimmed ends completely and the trim planes
    # never touch the body's faces.
    r_out = R + 0.05 * P
    a_bottom = 0.5 * bottom.depth(r_out)
    a_top = 0.5 * top.depth(r_out)
    z_lo, z_hi = z_bottom + a_bottom, z_top - a_top
    envelope = revolve_profile([
        (0.0, z_lo), (R + 0.5 * P, z_lo), (R + 0.5 * P, z_hi), (0.0, z_hi),
    ])
    ridge = internal_helical_thread(thread, z_bottom - P, z_top + P)
    for attempt, angle in enumerate(RIDGE_START_ANGLES):
        if attempt:
            progress.report("retry")
        trimmed = (Rot(0, 0, angle) * ridge) & envelope
        fused = core + trimmed
        # The ridge overlaps the core only by a thin strip outside D, so a
        # correct fuse adds most of its volume.
        if len(fused.solids()) != 1 or fused.volume < core.volume + 0.75 * trimmed.volume:
            continue
        out = fused
        for tool in tools:
            out = out - tool
        if (
            len(out.solids()) == 1
            and abs(out.volume - expected) < 0.02 * ridge_volume
            and out.is_valid
        ):
            return out
    raise RuntimeError(f"thread build failed for {what}")

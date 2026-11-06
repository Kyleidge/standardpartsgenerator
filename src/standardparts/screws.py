"""Shared builders for externally threaded parts (screws, set screws, studs).

Conventions used by every screw in this project:

* Z is the screw axis and the tip points towards -Z.
* Thread modes are "simplified" (plain cylinder at d, with the threaded
  length as its own face for cosmetic threads) and "modeled" (helical
  ISO 68-1 basic profile).
* Profiles are lists of (radius, z) points, plus ("arc", mid, end) items,
  as accepted by `geometry.revolve_profile`.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from build123d import Part, Rot

from . import progress
from .geometry import SQRT3, MetricThread, ProfileItem, helical_thread, hex_socket, revolve_profile

THREAD_MODES = {
    "simplified": "Simplified (plain shank at d)",
    "modeled": "Modeled helical thread",
}

# Thread start angles tried in turn if a boolean fails (see _fuse_ridge).
RIDGE_START_ANGLES = (0.0, 30.0, 75.0, 140.0, 210.0)


@dataclass(frozen=True)
class Point:
    """Chamfered point at the tip (z = -l).

    The tip face has radius `r_tip`; a cone at `half_angle` degrees from the
    axis rises from it to the major diameter. The default (None) is the ISO
    4753 chamfered end: r_tip = d3 / 2 at 45 deg.
    """

    r_tip: float | None = None
    half_angle: float = 45.0


def _rise(dr: float, half_angle: float) -> float:
    """Axial length a cone at half_angle needs to grow radially by dr."""
    return dr / math.tan(math.radians(half_angle))


def _fuse_ridge(core: Part, ridge: Part, envelope: Part, what: str) -> Part:
    # OCCT booleans between the helical ridge and the core occasionally drop
    # the ridge without reporting an error. The ridge overlaps the core only
    # by a thin embedded strip, so a correct fuse adds most of its volume;
    # check that and retry at another thread start angle.
    # The intersection itself can also fail (OCCT returns no shape), which
    # counts as a failed attempt too.
    for attempt, angle in enumerate(RIDGE_START_ANGLES):
        if attempt:
            progress.report("retry")
        try:
            trimmed = (Rot(0, 0, angle) * ridge) & envelope
            if trimmed is None or not trimmed.solids():
                continue
            fused = core + trimmed
        except Exception:  # noqa: BLE001 - any kernel failure means "retry"
            continue
        if (
            fused is not None
            and len(fused.solids()) == 1
            and fused.volume > core.volume + 0.75 * trimmed.volume
            and fused.is_valid
        ):
            return fused
    raise RuntimeError(f"thread fuse failed for {what}")


def threaded_screw(
    thread: MetricThread,
    length: float,
    z_thread_end: float,
    z_shank_top: float,
    head: Sequence[ProfileItem],
    mode: str,
    point: Point = Point(),
    what: str = "screw",
) -> Part:
    """Revolved screw with a threaded shank and a caller-supplied head.

    The tip is at z = -length. The full thread runs from the point up to
    z_thread_end, followed by a 2P incomplete-thread runout (modeled mode)
    and a plain shank at d up to z_shank_top. `head` continues the profile
    from the point (d/2, z_shank_top) around the head back to the axis,
    e.g. an underhead fillet arc, the head outline, then (0, z_top).

    For a screw threaded to the head, put z_thread_end low enough that the
    runout (d - d1) / 2 below z_shank_top fits:
    z_thread_end <= z_shank_top - (d - d1) / 2.

    Non-round features (hex heads, sockets, slots) are added or cut by the
    caller afterwards.
    """
    P = thread.P
    R = thread.d / 2
    r_core = thread.d1 / 2
    dr = R - r_core
    l = length
    r_tip = thread.d3 / 2 if point.r_tip is None else point.r_tip
    alpha = point.half_angle
    if z_thread_end + dr > z_shank_top + 1e-9:
        raise ValueError("z_thread_end leaves no room for the thread runout")

    if mode == "simplified":
        return revolve_profile([
            (0.0, -l),
            (r_tip, -l),
            (R, -l + _rise(R - r_tip, alpha)),
            (R, z_thread_end),     # split: threaded face below, plain shank above
            (R, z_shank_top),
            *head,
        ])
    if mode != "modeled":
        raise ValueError(f"unknown thread mode {mode!r}")

    tip_core = [(0.0, -l), (r_tip, -l)]
    if r_tip < r_core:
        tip_core.append((r_core, -l + _rise(r_core - r_tip, alpha)))
    core = revolve_profile([
        *tip_core,
        (r_core, z_thread_end),
        (R, z_thread_end + dr),    # 45 deg step from the thread core to the shank
        (R, z_shank_top),
        *head,
    ])
    # Envelope that trims the ridge: the point cone at the tip and a 2P
    # incomplete-thread runout at the top. Both cones are offset slightly
    # from the core's own surfaces and edges; coincident faces make the OCCT
    # fuse silently drop the ridge.
    slope = 2 * P / dr
    r_out = R + 0.05 * P
    r_in = r_core - 0.1 * P
    z_tip = -l + 0.03 * P
    z_run = z_thread_end - 0.1 * P  # runout cone reaches r_core here
    envelope = revolve_profile([
        (0.0, z_tip),
        (r_tip, z_tip),
        (r_out, z_tip + _rise(r_out - r_tip, alpha)),
        (r_out, z_run - (r_out - r_core) * slope),
        (r_in, z_run + (r_core - r_in) * slope),
        (0.0, z_run + (r_core - r_in) * slope),
    ])
    ridge = helical_thread(thread, -l - P, z_thread_end + P)
    return _fuse_ridge(core, ridge, envelope, what)


def threaded_rod(
    thread: MetricThread,
    length: float,
    mode: str,
    point: Point = Point(),
    top: Point = Point(),
    what: str = "set screw",
) -> Part:
    """Headless part threaded over its whole length, z from -length to 0.

    Both ends are chamfered: `point` at the tip (z = -length) and `top` at
    z = 0, each a cone rising from its face radius to the major diameter.
    Used for set screws and studs; sockets and cups are cut by the caller.
    """
    P = thread.P
    R = thread.d / 2
    r_core = thread.d1 / 2
    l = length
    r_tip = thread.d3 / 2 if point.r_tip is None else point.r_tip
    r_top = thread.d3 / 2 if top.r_tip is None else top.r_tip

    if mode == "simplified":
        return revolve_profile([
            (0.0, -l),
            (r_tip, -l),
            (R, -l + _rise(R - r_tip, point.half_angle)),
            (R, -_rise(R - r_top, top.half_angle)),
            (r_top, 0.0),
            (0.0, 0.0),
        ])
    if mode != "modeled":
        raise ValueError(f"unknown thread mode {mode!r}")

    def ends(r_end: float, z_face: float, alpha: float, sign: float, r_limit: float):
        """Face point and cone point up to r_limit, ordered away from the face."""
        pts = [(r_end, z_face)]
        if r_end < r_limit:
            pts.append((r_limit, z_face + sign * _rise(r_limit - r_end, alpha)))
        return pts

    bottom = ends(r_tip, -l, point.half_angle, +1, r_core)
    upper = ends(r_top, 0.0, top.half_angle, -1, r_core)
    core = revolve_profile([(0.0, -l), *bottom, *reversed(upper), (0.0, 0.0)])

    r_out = R + 0.05 * P
    z_lo, z_hi = -l + 0.03 * P, -0.03 * P
    envelope = revolve_profile([
        (0.0, z_lo),
        *ends(r_tip, z_lo, point.half_angle, +1, r_out),
        *reversed(ends(r_top, z_hi, top.half_angle, -1, r_out)),
        (0.0, z_hi),
    ])
    ridge = helical_thread(thread, -l - P, P)
    return _fuse_ridge(core, ridge, envelope, what)


def cut_hex_socket(body: Part, s: float, depth: float, z_top: float, what: str) -> Part:
    """Cut a hexagon socket (width s across flats) from z_top down, and
    check that the cut actually removed material."""
    cut = body - hex_socket(s, depth, z_top)
    hex_area = SQRT3 / 2 * s**2
    if len(cut.solids()) != 1 or body.volume - cut.volume < 0.95 * hex_area * depth:
        raise RuntimeError(f"socket cut failed for {what}")
    return cut

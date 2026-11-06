"""DIN 1587 hexagon domed cap nuts, high type (acorn nuts), M4 to M24."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from build123d import Part, Pos, RegularPolygon, Rot, extrude

from .. import progress
from ..geometry import SQRT3, MetricThread, chamfered_hex, revolve_profile
from ..nuts import (
    NUT_THREAD_MODES,
    Countersink,
    bore_volume,
    internal_helical_thread,
    internal_thread_volume,
)
from ..screws import RIDGE_START_ANGLES
from .base import Dimension, Option, Parameter, ParameterError, Standard
from .din1587_data import (
    CHAMFER_ANGLE,
    COUNTERSINK_ANGLE,
    DRILL_POINT_ANGLE,
    SIZES,
    SizeData,
)


def _fmt(x: float) -> str:
    return f"{x:g}"


# ---------------------------------------------------------------------------
# Blind internal thread
#
# nuts.threaded_nut needs a countersink at both ends to trim the helical
# ridge, so a blind hole gets its own builder here. It follows the same
# recipe and checks:
#
# * The bore goes from the bearing face to the depth t and is closed by a
#   drill point. The thread ends in one of the two forms of DIN 1587:
#   type A, a run-out: the full thread ends at t - x and a cone takes the
#   bore from D down to D1 at t (the tap's chamfer); type B, an undercut:
#   a groove of diameter dg from t - g to t, entered by a 45 deg step.
# * "simplified": bore at D1 with the same thread end (an undercut is cut
#   as a groove), split at the end of the full thread for a cosmetic
#   thread, and the countersink on the open face.
# * "modeled": the body is bored at D with the thread end and the drill
#   point. The inward ISO 68-1 ridge is trimmed by two planes: one just
#   inside the open face (the countersink cut afterwards removes that end,
#   as in nuts.threaded_nut) and one 0.1 P before the thread end starts
#   (t - x or t - g). So the ridge only meets the plain bore at D. Type B's
#   thread runs up to the undercut; type A's run-out cone is left plain
#   (the incomplete thread in it is not modeled). Earlier versions that
#   carried the ridge into the run-out cone or the undercut made the OCCT
#   fuse silently drop the ridge at most start angles.
# * The result is checked against the exact analytic volume and the fuse
#   is retried at other thread start angles, as in nuts.threaded_nut.
# ---------------------------------------------------------------------------

RIDGE_GAP = 0.1  # the ridge ends RIDGE_GAP * P before the thread end


@dataclass(frozen=True)
class ThreadEnd:
    """End of a blind internal thread at the bottom of the bore.

    kind "A": run-out of axial length `length` (x). kind "B": undercut of
    width `length` (g) and diameter `dg`.
    """

    kind: str
    length: float
    dg: float | None = None


def _drill_height(r: float, angle: float) -> float:
    return r / math.tan(math.radians(angle / 2))


def _cone_volume(r: float, height: float) -> float:
    return math.pi * r * r * height / 3


def _frustum_volume(r0: float, r1: float, height: float) -> float:
    return math.pi * height / 3 * (r0 * r0 + r0 * r1 + r1 * r1)


def drill_end(r1: float, t: float, drill_angle: float,
              z_floor: float | None) -> list[tuple[float, float]]:
    """Profile points that close a bore of radius r1 ending at depth t:
    the drill point cone of `drill_angle`, cut flat at z_floor if its tip
    would go deeper."""
    hc = _drill_height(r1, drill_angle)
    if z_floor is None or t + hc <= z_floor:
        return [(0.0, t + hc)]
    if z_floor <= t:
        raise ValueError("the drill floor must lie beyond the bore depth")
    r_f = r1 * (1 - (z_floor - t) / hc)
    return [(r_f, z_floor), (0.0, z_floor)]


def drill_end_volume(r1: float, t: float, drill_angle: float,
                     z_floor: float | None) -> float:
    """Volume beyond z = t of the drill_end closing."""
    end = drill_end(r1, t, drill_angle, z_floor)
    if len(end) == 1:
        return _cone_volume(r1, end[0][1] - t)
    r_f, z_f = end[0]
    return _frustum_volume(r1, r_f, z_f - t)


def bore_profile(r_bore: float, t: float, end: ThreadEnd) -> list[tuple[float, float]]:
    """Wall of a bore of radius r_bore from the face to t, with the thread
    end, as (r, z) points from the end of the full thread onwards (the
    caller adds the face end and the drill point)."""
    if end.kind == "A":
        # The run-out cone then runs to the caller's next point (D1 at t).
        return [(r_bore, t - end.length)]
    r_g = end.dg / 2
    z_u = t - end.length
    return [(r_bore, z_u), (r_g, z_u + (r_g - r_bore)), (r_g, t)]


def ridge_end_z(thread: MetricThread, t: float, end: ThreadEnd) -> float:
    """Where the modeled ridge is cut off: just before the run-out cone or
    the undercut starts."""
    return t - end.length - RIDGE_GAP * thread.P


def cavity_volume(r_bore: float, r1: float, t: float, end: ThreadEnd) -> float:
    """Volume of the bore of radius r_bore to t with its thread end, up to
    z = t (drill point not included). For type A the run-out cone goes
    from r_bore to r1."""
    if end.kind == "A":
        z_te = t - end.length
        return math.pi * r_bore**2 * z_te + _frustum_volume(r_bore, r1, end.length)
    r_g = end.dg / 2
    step = r_g - r_bore
    z_u = t - end.length
    return (
        math.pi * r_bore**2 * z_u
        + _frustum_volume(r_bore, r_g, step)
        + math.pi * r_g**2 * (end.length - step)
    )


def blind_thread_volume(thread: MetricThread, t: float, end: ThreadEnd,
                        bottom: Countersink) -> float:
    """Exact volume of material the modeled blind thread adds inside the
    bore at D: the ridge from the countersink to its end plane, i.e. a
    through thread of that height with one countersink."""
    return internal_thread_volume(thread, ridge_end_z(thread, t, end), bottom, None)


def _countersink_tool(cs: Countersink, r_in: float, ext: float) -> Part:
    """Countersink cone at the bearing face z = 0, from `ext` below it down
    to radius r_in, closed by a flat disc."""
    z_in = cs.depth(r_in)
    return revolve_profile([
        (0.0, -ext),
        (cs.da / 2 + ext * cs.slope, -ext),
        (r_in, z_in),
        (0.0, z_in),
    ])


def blind_threaded_nut(body: Part, thread: MetricThread, t: float, end: ThreadEnd,
                       mode: str, bottom: Countersink,
                       drill_angle: float = DRILL_POINT_ANGLE,
                       z_floor: float | None = None,
                       what: str = "nut") -> Part:
    """Bore and thread a solid `body` from its bearing face z = 0 up to the
    depth t, with the thread end `end` at the bottom of the bore and a
    drill point of `drill_angle` beyond t, cut flat at z_floor if given and
    the point would reach beyond it.

    The body must be solid well beyond D / 2 (dg / 2) around the bore and
    beyond the drill point.
    """
    if mode not in NUT_THREAD_MODES:
        raise ValueError(f"unknown thread mode {mode!r}")
    P = thread.P
    R = thread.d / 2
    r1 = thread.d1 / 2
    r_out = R + 0.05 * P
    if bottom.da / 2 <= r_out:
        raise ValueError(f"countersink da {bottom.da} is too small for D {thread.d}")
    if end.kind not in ("A", "B"):
        raise ValueError(f"unknown thread end {end.kind!r}")
    if not 0 < end.length < t - bottom.depth(r1) - 2 * P:
        raise ValueError("the thread end must lie inside the bore")
    if end.kind == "B" and not (
        end.dg is not None
        and end.dg / 2 > R + 0.15 * P
        and end.length > end.dg / 2 - r1 + 0.5 * P
    ):
        raise ValueError("the undercut is too small for the thread")
    ext = P
    tip = drill_end(r1, t, drill_angle, z_floor)
    v_tip = drill_end_volume(r1, t, drill_angle, z_floor)

    if mode == "simplified":
        wall = bore_profile(r1, t, end)
        tool = revolve_profile([
            (0.0, -ext),
            (bottom.da / 2 + ext * bottom.slope, -ext),
            (r1, bottom.depth(r1)),
            *wall,  # split at the end of the full thread
            (r1, t),
            *tip,
        ])
        out = body - tool
        removed = cavity_volume(r1, r1, t, end) + v_tip + bore_volume(r1, 0.0, bottom, None)
        expected = body.volume - removed
        if (
            len(out.solids()) != 1
            or not out.is_valid
            or abs(out.volume - expected) > 1e-4 * body.volume
        ):
            raise RuntimeError(f"bore failed for {what}")
        return out

    cavity = revolve_profile([
        (0.0, -ext), (R, -ext), *bore_profile(R, t, end), (r1, t), *tip,
    ])
    core = body - cavity
    removed = cavity_volume(R, r1, t, end) + v_tip
    if (
        len(core.solids()) != 1
        or not core.is_valid
        or abs(core.volume - (body.volume - removed)) > 1e-5 * body.volume
    ):
        raise RuntimeError(f"bore failed for {what}")

    ridge_volume = blind_thread_volume(thread, t, end, bottom)
    expected = body.volume - removed - bore_volume(R, 0.0, bottom, None) + ridge_volume

    z_lo = 0.5 * bottom.depth(r_out)
    z_hi = ridge_end_z(thread, t, end)
    r_env = R + 0.5 * P
    envelope = revolve_profile([(0.0, z_lo), (r_env, z_lo), (r_env, z_hi), (0.0, z_hi)])
    cs_tool = _countersink_tool(bottom, r1 - 0.1 * P, ext)
    ridge = internal_helical_thread(thread, -P, z_hi + P)
    for attempt, angle in enumerate(RIDGE_START_ANGLES):
        if attempt:
            progress.report("retry")
        try:
            trimmed = (Rot(0, 0, angle) * ridge) & envelope
            if trimmed is None or not trimmed.solids():
                continue
            fused = core + trimmed
            # The ridge overlaps the core only by a thin strip outside D, so
            # a correct fuse adds most of its volume.
            if len(fused.solids()) != 1 or fused.volume < core.volume + 0.75 * trimmed.volume:
                continue
            out = fused - cs_tool
        except Exception:  # noqa: BLE001 - any kernel failure means "retry"
            continue
        if (
            len(out.solids()) == 1
            and abs(out.volume - expected) < 0.02 * ridge_volume
            and out.is_valid
        ):
            return out
    raise RuntimeError(f"thread build failed for {what}")


# ---------------------------------------------------------------------------
# Nut body
# ---------------------------------------------------------------------------

def _tan(angle: float) -> float:
    return math.tan(math.radians(angle))


def dome_volume(sd: SizeData) -> float:
    """Volume above the hexagon: cylinder of radius r from m to h - r and
    a hemisphere of radius r."""
    r = sd.r
    return math.pi * r * r * (sd.h - r - sd.m_max) + 2 / 3 * math.pi * r**3


def nut_body(sd: SizeData, what: str) -> Part:
    """Unbored one-piece body: hexagon of height m with a 30 deg chamfer
    down to dw on the bearing face and a 30 deg chamfer from the dome
    diameter 2 r to the corners on top, and the dome above it.

    Built as a single revolved outline (chamfer cones, dome cylinder and
    sphere) intersected with a hexagon prism that is taller than the nut,
    so no two faces of the boolean coincide (2 r < s, so the dome stays
    clear of the flats).
    """
    s, m, h, r = sd.s, sd.m_max, sd.h, sd.r
    t30 = _tan(CHAMFER_ANGLE)
    r_corner = s / SQRT3 * 1.02
    r_w = sd.dw_min / 2
    profile = [
        (0.0, 0.0),
        (r_w, 0.0),
        (r_corner, (r_corner - r_w) * t30),
        (r_corner, m - (r_corner - r) * t30),
        (r, m),
        (r, h - r),
        ("arc", (r * math.cos(math.pi / 4), h - r + r * math.sin(math.pi / 4)), (0.0, h)),
    ]
    prism = Pos(0, 0, -0.1 * h) * extrude(
        RegularPolygon(radius=s / 2, side_count=6, major_radius=False), amount=1.2 * h
    )
    body = revolve_profile(profile) & prism
    # Independent check: the hexagon part as built by geometry.chamfered_hex
    # plus the analytic dome.
    expected = chamfered_hex(s, 0.0, m, sd.dw_min, 2 * r, CHAMFER_ANGLE).volume + dome_volume(sd)
    if (
        len(body.solids()) != 1
        or not body.is_valid
        or abs(body.volume - expected) > 1e-5 * expected
    ):
        raise RuntimeError(f"body failed for {what}")
    return body


def point_crown(sd: SizeData) -> float:
    """Material on the axis between the tip of a full 120 deg drill point
    at t nom and the top of the dome."""
    r1 = MetricThread(sd.D, sd.P).d1 / 2
    return sd.h - sd.t_nom - _drill_height(r1, DRILL_POINT_ANGLE)


def drill_floor(sd: SizeData) -> float:
    """Deepest point of the bore allowed by the crown thickness w min."""
    return sd.h - sd.w_min


def is_flattened(sd: SizeData) -> bool:
    """True if the drill point is cut flat to keep w min."""
    return point_crown(sd) < sd.w_min


def thread_end(sd: SizeData) -> ThreadEnd:
    """Type A (run-out x max) where the 2000 table gives x, type B
    (undercut g max at dg) where it gives g."""
    if sd.end_type == "A":
        return ThreadEnd("A", sd.x_max)
    return ThreadEnd("B", sd.g_max, sd.dg)


def crown_thickness(sd: SizeData) -> float:
    """Modeled material on the axis above the bore."""
    return max(point_crown(sd), sd.w_min)


def build_nut(sd: SizeData, thread_mode: str) -> Part:
    """Build the domed cap nut.

    Coordinate system: Z is the nut axis, the bearing face lies in the XY
    plane at z = 0, the hexagon goes up to z = m and the dome to z = h.
    Flats are parallel to the X axis. Nominal sizes: s, m max, h, dome
    radius r (dome diameter 2 r = dk max), bearing chamfer to dw min, 120
    deg countersink at da max, bore to t nom ending in the run-out x max
    (type A, M4 to M10) or the undercut g max (type B, M12 to M24) and a
    120 deg drill point, cut flat where its tip would leave less than the
    crown thickness w min on the axis.
    """
    if thread_mode not in NUT_THREAD_MODES:
        raise ParameterError(f"unknown thread mode {thread_mode!r}")
    what = f"DIN 1587 {sd.size}"
    body = nut_body(sd, what)
    return blind_threaded_nut(
        body, MetricThread(sd.D, sd.P), sd.t_nom, thread_end(sd), thread_mode,
        Countersink(sd.da_max, COUNTERSINK_ANGLE), z_floor=drill_floor(sd), what=what,
    )


class DIN1587(Standard):
    id = "din1587"
    title = "DIN 1587"
    summary = "Hexagon domed cap nuts (acorn nuts), high type, M4 to M24"
    category = "Nuts"
    source = (
        "Values in mm, from DIN 1587:2000 (fasten.it), with m, r, da, dw and "
        "w from Westfield Fasteners' DIN 1587 specification, cross-checked "
        "against Fabory."
    )

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="size",
                label="Thread size",
                kind="select",
                default="M8",
                options=[Option(k, f"{k} x {_fmt(sd.P)}") for k, sd in SIZES.items()],
            ),
            Parameter(
                name="thread",
                label="Thread",
                kind="select",
                default="simplified",
                options=[Option(k, v) for k, v in NUT_THREAD_MODES.items()],
                help="Simplified is a plain blind bore at the minor diameter D1; "
                "modeled has a helical ISO 68-1 internal thread with its run-out.",
            ),
        ]

    def validate(self, raw: dict[str, Any]) -> dict[str, Any]:
        size = str(raw.get("size", "M8"))
        if size not in SIZES:
            raise ParameterError(f"unknown size {size!r}; choose one of {', '.join(SIZES)}")
        thread = str(raw.get("thread", "simplified"))
        if thread not in NUT_THREAD_MODES:
            raise ParameterError(f"thread must be one of {', '.join(NUT_THREAD_MODES)}")
        return {"size": size, "thread": thread}

    def designation(self, p: dict[str, Any]) -> str:
        return f"DIN 1587 - {p['size']}"

    def file_stem(self, p: dict[str, Any]) -> str:
        suffix = "_threaded" if p["thread"] == "modeled" else ""
        return f"DIN1587_{p['size']}{suffix}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        sd = SIZES[p["size"]]
        t = MetricThread(sd.D, sd.P)
        return [
            Dimension("D", "Thread diameter", sd.D),
            Dimension("P", "Pitch", sd.P),
            Dimension("s", "Width across flats", sd.s),
            Dimension("e", "Width across corners (modeled)", round(sd.e_nom, 3)),
            Dimension("e min", "Width across corners, min.", sd.e_min),
            Dimension("m max", "Height of the hexagon", sd.m_max),
            Dimension("h", "Overall height", sd.h),
            Dimension("dk max", "Dome diameter", sd.dk_max),
            Dimension("r", "Dome radius (auxiliary)", sd.r),
            Dimension("t min", "Bore depth, min.", sd.t_min),
            Dimension("t max", "Bore depth, max.", sd.t_max),
            Dimension("t", "Bore depth (modeled)", sd.t_nom),
            *self._end_dimensions(sd),
            Dimension("w min", "Crown thickness", sd.w_min),
            Dimension("w", "Crown thickness on the axis (modeled)",
                      round(crown_thickness(sd), 2)),
            Dimension("dw min", "Bearing face dia.", sd.dw_min),
            Dimension("da max", "Countersink dia.", sd.da_max),
            Dimension("D1", "Minor diameter (basic)", round(t.d1, 3)),
        ]

    @staticmethod
    def _end_dimensions(sd: SizeData) -> list[Dimension]:
        if sd.end_type == "A":
            return [
                Dimension("type", "Thread end", "A, run-out", unit=""),
                Dimension("x max", "Thread run-out", sd.x_max),
            ]
        return [
            Dimension("type", "Thread end", "B, undercut", unit=""),
            Dimension("g max", "Undercut width", sd.g_max),
            Dimension("dg", "Undercut dia. (model)", sd.dg),
        ]

    def notes(self, p: dict[str, Any]) -> list[str]:
        sd = SIZES[p["size"]]
        out = []
        sym = "x" if sd.end_type == "A" else "g"
        if p["thread"] == "simplified":
            out.append(
                "Thread not modeled: blind bore at the basic minor diameter D1 to "
                f"the depth t, split at t - {sym} for a cosmetic thread."
            )
        else:
            out.append(
                "Thread modeled with the ISO 68-1 basic internal profile (root flat "
                f"at D, crest flat at D1), right hand, full depth to t - {sym}."
            )
        if sd.end_type == "A":
            out.append(
                "Type A thread end: the bore narrows from D to D1 over the run-out "
                "x; the incomplete thread in the run-out is not modeled."
            )
        else:
            out.append(
                f"Type B thread end: an undercut g wide at dg = D + 0.5 P (model "
                "value; DIN 1587 does not give it), entered by a 45° step; the "
                "thread runs up to it."
            )
        out.append(
            "One-piece form as drawn in DIN 1587. Modeled at nominal sizes: s, "
            "m max, h, dome radius r on a cylinder of diameter 2 r, 30° chamfers "
            "on both ends of the hexagon, 120° countersink at da max, bore to "
            "t = (t min + t max) / 2 closed by a 120° drill point."
        )
        if is_flattened(sd):
            out.append(
                f"A full 120° drill point would leave {point_crown(sd):.2f} mm at the "
                f"crown, less than w min = {_fmt(sd.w_min)}; its tip is cut flat at "
                f"h - w min = {_fmt(drill_floor(sd))} mm."
            )
        return out

    def build(self, p: dict[str, Any]) -> Part:
        part = build_nut(SIZES[p["size"]], p["thread"])
        part.label = self.designation(p)
        return part

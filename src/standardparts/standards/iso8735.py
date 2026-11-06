"""ISO 8735 parallel pins with internal thread, hardened steel and
martensitic stainless steel (extractable dowel pins).

Coordinate system: Z is the pin axis. The threaded end face lies in the XY
plane at z = 0 and the pin extends to z = -l, like ISO 8734 (iso8734.py).

Model, following Figure 1 at nominal sizes:

* Pin at nominal d1. The threaded end has the ~15 deg chamfer of axial
  length a. The far end is the type A crown (~15 deg chamfer, then a
  sphere of radius d1, together c long) or the type B flat end (~15 deg
  chamfer of length c).
* Blind hole: counterbore d3 to depth t3, a 120 deg countersink down to
  the thread, the thread d2 to depth t1, the drilled hole at D1 to depth
  t2 min and a 120 deg drill point.
* Thread modes:
  * "simplified": the whole hole is a plain bore at D1, with the threaded
    length (countersink to t1) as its own face for a cosmetic thread.
    Built as a single revolved profile, no booleans.
  * "modeled": right-hand ISO 68-1 internal thread (the profile of
    nuts.internal_helical_thread). The pin is bored at D to below t1, the
    helical ridge is trimmed so the complete thread reaches t1 and then
    runs out over ~2P (the incomplete thread a tap leaves), fused on, and
    the counterbore and countersink are cut last, which also removes the
    ridge's upper end. Every attempt is checked against an exact volume
    and retried at other thread start angles, like nuts.threaded_nut.
* Optional venting flat (Figure 1 footnote 1, not dimensioned): a flat
  along the whole pin at depth VENT_DEPTH * d1, centred on +X.
"""

from __future__ import annotations

import math
from typing import Any

from build123d import Align, Box, Part, Pos, Rot

from .. import progress
from ..geometry import MetricThread, revolve_profile
from ..nuts import NUT_THREAD_MODES, internal_helical_thread, ridge_fraction
from ..screws import RIDGE_START_ANGLES
from .base import Dimension, Option, Parameter, ParameterError, Standard
from .iso8735_data import (
    CHAMFER_ANGLE,
    COUNTERSINK_ANGLE,
    DRILL_ANGLE,
    SIZES,
    TYPES,
    VENT_DEPTH,
    PinData,
)

VENTS = {
    "none": "No venting flat",
    "flat": "Venting flat (manufacturer's option)",
}

TAN_CH = math.tan(math.radians(CHAMFER_ANGLE))
TAN_CS = math.tan(math.radians(COUNTERSINK_ANGLE / 2))
TAN_DR = math.tan(math.radians(DRILL_ANGLE / 2))

Pt = tuple[float, float]


def _fmt(x: float) -> str:
    return f"{x:g}"


# ------------------------------------------------------------ geometry


def crown(pd: PinData) -> tuple[float, float, float]:
    """Type A end: (chamfer length, crown base radius, crown height).

    The ~15 deg chamfer runs from d1 inwards for the returned axial length;
    the crown is a sphere of radius d1 on the remaining face. Their axial
    lengths add up to c (Figure 1), solved by bisection.
    """
    R, rs = pd.d1 / 2, pd.d1

    def total(x: float) -> float:
        rho = R - x * TAN_CH
        return x + rs - math.sqrt(rs * rs - rho * rho) - pd.c

    lo, hi = 0.0, pd.c
    for _ in range(80):
        mid = (lo + hi) / 2
        if total(mid) > 0:
            hi = mid
        else:
            lo = mid
    x = (lo + hi) / 2
    rho = R - x * TAN_CH
    return x, rho, pd.c - x


def outer_section(pd: PinData, l: float, pin_type: str) -> list:
    """Outer contour from the far-end apex (0, -l) to the threaded end face
    edge, as revolve_profile items."""
    R = pd.d1 / 2
    if pin_type == "A":
        _, rho, h = crown(pd)
        rs = pd.d1
        r_mid = rho / 2
        z_mid = -l + rs - math.sqrt(rs * rs - r_mid * r_mid)
        far = [(0.0, -l), ("arc", (r_mid, z_mid), (rho, -l + h))]
    elif pin_type == "B":
        far = [(0.0, -l), (R - pd.c * TAN_CH, -l)]
    else:
        raise ValueError(f"unknown type {pin_type!r}")
    return [*far, (R, -l + pd.c), (R, -pd.a), (R - pd.a * TAN_CH, 0.0)]


def _countersink_z(pd: PinData, r: float) -> float:
    """z of the 120 deg countersink below the counterbore at radius r."""
    return -pd.t3 - (pd.d3 / 2 - r) / TAN_CS


def drill_tip_z(pd: PinData, r_hole: float) -> float:
    return -pd.t2 - r_hole / TAN_DR


def thread_runout(thread: MetricThread) -> float:
    """Runout slope of the modeled thread: axial length per unit of radial
    depth, so the ridge fades out over 2P (as in screws.threaded_screw)."""
    return 2 * thread.P / (thread.d / 2 - thread.d1 / 2)


def bore_bottom_z(pd: PinData, thread: MetricThread) -> float:
    """Lowest z of the bore at D in modeled mode. The ridge envelope stops
    0.1 P above it, beyond the outside of the ridge (D/2 + 0.1 P)."""
    P = thread.P
    r1 = thread.d1 / 2
    r_d = thread.d / 2 + 0.1 * P
    return -pd.t1 - (r_d - r1) * thread_runout(thread) - 0.1 * P


def hole_section(pd: PinData, mode: str) -> list[Pt]:
    """Final (axisymmetric) hole from the mouth to the drill tip. For
    "modeled" this is the hole before the thread ridge is added."""
    thread = MetricThread(pd.D, pd.P)
    R, r1 = pd.D / 2, thread.d1 / 2
    mouth = [(pd.d3 / 2, 0.0), (pd.d3 / 2, -pd.t3)]
    if mode == "simplified":
        return [
            *mouth,
            (r1, _countersink_z(pd, r1)),
            (r1, -pd.t1),           # split: threaded face above
            (r1, -pd.t2),
            (0.0, drill_tip_z(pd, r1)),
        ]
    z_b = bore_bottom_z(pd, thread)
    return [
        *mouth,
        (R, _countersink_z(pd, R)),
        (R, z_b),
        (r1, z_b - (R - r1) / TAN_DR),
        (r1, -pd.t2),
        (0.0, drill_tip_z(pd, r1)),
    ]


def _frustums(pts: list[Pt]) -> float:
    """Volume swept by a polyline r(z) monotonic in z, down to the axis."""
    v = 0.0
    for (r1, z1), (r2, z2) in zip(pts, pts[1:]):
        v += math.pi * abs(z2 - z1) / 3 * (r1 * r1 + r1 * r2 + r2 * r2)
    return v


def outer_volume(pd: PinData, l: float, pin_type: str) -> float:
    R = pd.d1 / 2
    tail = [(R, -l + pd.c), (R, -pd.a), (R - pd.a * TAN_CH, 0.0)]
    if pin_type == "A":
        _, rho, h = crown(pd)
        cap = math.pi * h * h * (3 * pd.d1 - h) / 3
        return cap + _frustums([(rho, -l + h), *tail])
    return _frustums([(R - pd.c * TAN_CH, -l), *tail])


def ridge_volume(pd: PinData) -> float:
    """Exact volume the modeled ridge adds inside the bore at D: at radius
    r it fills ridge_fraction(r) of the axial length between the runout
    cone and the countersink (see nuts.internal_thread_volume)."""
    thread = MetricThread(pd.D, pd.P)
    r0, r1 = thread.d1 / 2, thread.d / 2
    s = thread_runout(thread)

    def f(r: float) -> float:
        length = _countersink_z(pd, r) - (-pd.t1 - (r - r0) * s)
        return ridge_fraction(thread, r) * max(0.0, length) * 2 * math.pi * r

    n = 64
    h = (r1 - r0) / n
    total = f(r0) + f(r1)
    for i in range(1, n):
        total += (4 if i % 2 else 2) * f(r0 + i * h)
    return total * h / 3


def outer_radius(pd: PinData, l: float, pin_type: str, z: float) -> float:
    """Outer radius of the pin at height z (-l <= z <= 0)."""
    R = pd.d1 / 2
    if z > -pd.a:
        return R - (z + pd.a) * TAN_CH
    if z >= -l + pd.c:
        return R
    if pin_type == "A":
        x, rho, h = crown(pd)
        if z >= -l + h:
            return rho + (z + l - h) / x * (R - rho)
        dz = pd.d1 - (z + l)
        return math.sqrt(max(0.0, pd.d1 ** 2 - dz * dz))
    r_end = R - pd.c * TAN_CH
    return r_end + (z + l) / pd.c * (R - r_end)


def vent_depth(pd: PinData) -> float:
    return round(VENT_DEPTH * pd.d1, 3)


def vent_volume(pd: PinData, l: float, pin_type: str) -> float:
    """Volume the venting flat removes: the circular segment beyond
    x0 = d1/2 - depth, integrated along the pin (Simpson, piecewise)."""
    x0 = pd.d1 / 2 - vent_depth(pd)

    def seg(z: float) -> float:
        rho = outer_radius(pd, l, pin_type, z)
        if rho <= x0:
            return 0.0
        return rho * rho * math.acos(x0 / rho) - x0 * math.sqrt(rho * rho - x0 * x0)

    breaks = [-l, -l + pd.c, -pd.a, 0.0]
    if pin_type == "A":
        breaks.insert(1, -l + crown(pd)[2])
    total = 0.0
    for a, b in zip(breaks, breaks[1:]):
        n = 400
        h = (b - a) / n
        acc = seg(a) + seg(b)
        for i in range(1, n):
            acc += (4 if i % 2 else 2) * seg(a + i * h)
        total += acc * h / 3
    return total


def expected_volume(pd: PinData, l: float, pin_type: str, mode: str,
                    vent: str = "none") -> float:
    """Exact volume of the model."""
    v = outer_volume(pd, l, pin_type) - _frustums(hole_section(pd, mode))
    if mode == "modeled":
        v += ridge_volume(pd)
    if vent == "flat":
        v -= vent_volume(pd, l, pin_type)
    return v


def _check(part: Part | None, expected: float, tol: float) -> bool:
    return (
        part is not None
        and len(part.solids()) == 1
        and part.is_valid
        and abs(part.volume - expected) <= tol
    )


def _modeled_thread(pd: PinData, l: float, pin_type: str, what: str) -> Part:
    thread = MetricThread(pd.D, pd.P)
    P = thread.P
    R, r1 = pd.D / 2, thread.d1 / 2
    z_b = bore_bottom_z(pd, thread)
    core = revolve_profile([
        *outer_section(pd, l, pin_type),
        (R, 0.0),
        (R, z_b),
        (r1, z_b - (R - r1) / TAN_DR),
        (r1, -pd.t2),
        (0.0, drill_tip_z(pd, r1)),
    ])
    # Envelope that keeps the ridge between a plane inside the counterbore
    # (removed again by the countersink cut) and the runout cone, which
    # passes through (D1/2, -t1) and reaches beyond the ridge's outside
    # 0.1 P above the bottom of the bore at D. No envelope face touches a
    # core face.
    s = thread_runout(thread)
    r_in = r1 - 0.1 * P
    r_d = R + 0.1 * P
    r_big = R + 0.5 * P
    z_top = -pd.t3 / 2
    z_d = -pd.t1 - (r_d - r1) * s
    envelope = revolve_profile([
        (0.0, z_top),
        (r_big, z_top),
        (r_big, z_d),
        (r_d, z_d),
        (r_in, -pd.t1 + (r1 - r_in) * s),
        (0.0, -pd.t1 + (r1 - r_in) * s),
    ])
    # Counterbore and countersink tool, reaching P above the end face.
    ext = P
    r_cut = r1 - 0.1 * P
    tool = revolve_profile([
        (0.0, ext),
        (pd.d3 / 2, ext),
        (pd.d3 / 2, -pd.t3),
        (r_cut, _countersink_z(pd, r_cut)),
        (0.0, _countersink_z(pd, r_cut)),
    ])
    ridge = internal_helical_thread(thread, z_d - P, z_top + P)
    v_ridge = ridge_volume(pd)
    expected = expected_volume(pd, l, pin_type, "modeled")
    for attempt, angle in enumerate(RIDGE_START_ANGLES):
        if attempt:
            progress.report("retry")
        try:
            trimmed = (Rot(0, 0, angle) * ridge) & envelope
            if trimmed is None or not trimmed.solids():
                continue
            fused = core + trimmed
            # The ridge overlaps the core only by a thin strip outside D,
            # so a correct fuse adds most of its volume.
            if (
                fused is None
                or len(fused.solids()) != 1
                or fused.volume < core.volume + 0.75 * trimmed.volume
            ):
                continue
            out = fused - tool
        except Exception:  # noqa: BLE001 - any kernel failure means "retry"
            continue
        if _check(out, expected, 0.02 * v_ridge):
            return out
    raise RuntimeError(f"thread build failed for {what}")


def build_pin(pd: PinData, l: float, pin_type: str, mode: str,
              vent: str = "none") -> Part:
    """Build and check the pin solid (see the module docstring)."""
    if mode not in NUT_THREAD_MODES:
        raise ValueError(f"unknown thread mode {mode!r}")
    if pin_type not in TYPES:
        raise ValueError(f"unknown type {pin_type!r}")
    if vent not in VENTS:
        raise ValueError(f"unknown vent {vent!r}")
    what = f"ISO 8735 {pd.size} x {_fmt(l)} {pin_type}"
    if mode == "simplified":
        part = revolve_profile([*outer_section(pd, l, pin_type), *hole_section(pd, mode)])
        expected = expected_volume(pd, l, pin_type, mode)
        if not _check(part, expected, 1e-6 * expected):
            raise RuntimeError(f"pin construction failed for {what}")
    else:
        part = _modeled_thread(pd, l, pin_type, what)
    if vent == "flat":
        x0 = pd.d1 / 2 - vent_depth(pd)
        size = pd.d1 + 2
        box = Pos(x0, 0, -l / 2) * Box(
            size, size, l + 2, align=(Align.MIN, Align.CENTER, Align.CENTER)
        )
        before = part.volume
        cut = part - box
        removed = vent_volume(pd, l, pin_type)
        if not _check(cut, before - removed, 2e-3 * removed + 1e-6 * before):
            raise RuntimeError(f"venting flat cut failed for {what}")
        part = cut
    return part


# ------------------------------------------------------------ standard


class ISO8735(Standard):
    id = "iso8735"
    title = "ISO 8735"
    summary = "Parallel pins with internal thread (extractable dowel pins), hardened steel, d = 6 to 50 mm"
    category = "Pins"
    source = "Values in mm, from ISO 8735:1997 Table 1."

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="size",
                label="Nominal diameter d1",
                kind="select",
                default="10",
                options=[Option(s, f"{s} mm ({pd.thread})") for s, pd in SIZES.items()],
            ),
            Parameter(
                name="length",
                label="Nominal length l",
                kind="length",
                default=40,
                depends_on="size",
                preferred={s: pd.standard_lengths() for s, pd in SIZES.items()},
                limits={s: [pd.l_min, pd.l_max] for s, pd in SIZES.items()},
                unit="mm",
                help="Overall length, threaded end face to the far end.",
            ),
            Parameter(
                name="type",
                label="Type",
                kind="select",
                default="A",
                options=[Option(k, v) for k, v in TYPES.items()],
                help="Type A has a crowned far end, type B a flat one; all "
                "other dimensions are the same.",
            ),
            Parameter(
                name="thread",
                label="Thread",
                kind="select",
                default="simplified",
                options=[Option(k, v) for k, v in NUT_THREAD_MODES.items()],
                help="Simplified is a plain bore at D1 with the threaded length "
                "as its own face, ready for a cosmetic thread.",
            ),
            Parameter(
                name="vent",
                label="Venting flat",
                kind="select",
                default="none",
                options=[Option(k, v) for k, v in VENTS.items()],
                help="ISO 8735 allows a slight flat or small groove at the "
                "manufacturer's discretion; it is not dimensioned.",
            ),
        ]

    def validate(self, raw: dict[str, Any]) -> dict[str, Any]:
        size = str(raw.get("size", "10"))
        if size.endswith(".0"):
            size = size[:-2]
        if size not in SIZES:
            raise ParameterError(f"unknown diameter {size!r}; choose one of {', '.join(SIZES)}")
        pd = SIZES[size]
        try:
            length = float(raw.get("length", 40))
        except (TypeError, ValueError):
            raise ParameterError("length must be a number") from None
        if not math.isfinite(length):
            raise ParameterError("length must be a number")
        length = round(length, 2)
        if not pd.l_min <= length <= pd.l_max:
            raise ParameterError(
                f"length for d1 = {size} must be between {_fmt(pd.l_min)} and "
                f"{_fmt(pd.l_max)} mm"
            )
        pin_type = str(raw.get("type", "A")).upper()
        if pin_type not in TYPES:
            raise ParameterError(f"type must be one of {', '.join(TYPES)}")
        thread = str(raw.get("thread", "simplified"))
        if thread not in NUT_THREAD_MODES:
            raise ParameterError(f"thread must be one of {', '.join(NUT_THREAD_MODES)}")
        vent = str(raw.get("vent", "none"))
        if vent not in VENTS:
            raise ParameterError(f"vent must be one of {', '.join(VENTS)}")
        return {"size": size, "length": length, "type": pin_type, "thread": thread,
                "vent": vent}

    def designation(self, p: dict[str, Any]) -> str:
        return f"ISO 8735 - {p['size']} x {_fmt(p['length'])} - {p['type']}"

    def file_stem(self, p: dict[str, Any]) -> str:
        stem = f"ISO8735_{p['size']}x{_fmt(p['length'])}_{p['type']}"
        if p["thread"] == "modeled":
            stem += "_threaded"
        if p["vent"] == "flat":
            stem += "_vent"
        return stem

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        pd = SIZES[p["size"]]
        thread = MetricThread(pd.D, pd.P)
        dims = [
            Dimension("d1 m6", "Nominal diameter", pd.d1),
            Dimension("l", "Nominal length", p["length"]),
            Dimension("d2", "Internal thread (6H)", pd.thread, ""),
            Dimension("P", "Pitch", pd.P),
            Dimension("D1", "Basic minor diameter (drilled hole)", round(thread.d1, 3)),
            Dimension("t1", "Thread depth", pd.t1),
            Dimension("t2 min", "Drilled hole depth", pd.t2),
            Dimension("d3", "Counterbore diameter", pd.d3),
            Dimension("t3", "Counterbore depth", pd.t3),
            Dimension("∠", "Countersink angle", f"{COUNTERSINK_ANGLE:g}°", ""),
            Dimension("a ≈", "Threaded-end chamfer length", pd.a),
            Dimension("c ≈", "Far-end chamfer length", pd.c),
            Dimension("α ≈", "Chamfer angle to pin surface", CHAMFER_ANGLE, "°"),
        ]
        if p["type"] == "A":
            h = crown(pd)[2]
            dims += [
                Dimension("r", "Crown radius (= d1)", pd.d1),
                Dimension("h", "Crown height (model)", round(h, 3)),
            ]
        if p["vent"] == "flat":
            dims.append(Dimension("f", "Venting flat depth (model)", vent_depth(pd)))
        return dims

    def notes(self, p: dict[str, Any]) -> list[str]:
        pd = SIZES[p["size"]]
        l = p["length"]
        out = []
        if l not in pd.standard_lengths():
            pref = ", ".join(_fmt(x) for x in pd.standard_lengths())
            out.append(
                f"{_fmt(l)} mm is not a preferred length for d1 = {pd.size} "
                f"(preferred: {pref})."
            )
        if p["type"] == "A":
            out.append(
                "Type A: crowned far end (sphere r = d1 after a ~15° chamfer, "
                "together c long); through hardened steel or martensitic "
                f"stainless steel, e.g. Parallel pin ISO 8735 - {pd.size} x "
                f"{_fmt(l)} - A - St, or ... - C1."
            )
        else:
            out.append(
                "Type B: flat far end with a ~15° chamfer of length c; case "
                f"hardened steel, e.g. Parallel pin ISO 8735 - {pd.size} x "
                f"{_fmt(l)} - B - St."
            )
        if p["thread"] == "simplified":
            out.append(
                f"Thread not modeled: the hole is a plain bore at D1 to t2 min, "
                f"with the threaded length (to t1 = {_fmt(pd.t1)} mm) as its own "
                "face, ready for a cosmetic thread."
            )
        else:
            out.append(
                f"Thread {pd.thread} modeled with the ISO 68-1 basic profile, right "
                f"hand, complete to t1 = {_fmt(pd.t1)} mm and running out over "
                "about 2P below it."
            )
        out.append(
            "Modeled at nominal d1 (tolerance m6), counterbore d3 × t3 and a 120° "
            "countersink at the hole mouth, a 120° drill point at t2 min."
        )
        if p["vent"] == "flat":
            out.append(
                f"Venting flat {_fmt(vent_depth(pd))} mm deep along the whole pin, "
                "on +X. ISO 8735 allows a slight flat or small groove at the "
                "manufacturer's discretion without dimensions; the depth is an "
                "assumption."
            )
        out.append("Threaded end face at z = 0, the pin extends to z = -l.")
        return out

    def build(self, p: dict[str, Any]) -> Part:
        part = build_pin(SIZES[p["size"]], p["length"], p["type"], p["thread"], p["vent"])
        part.label = self.designation(p)
        return part

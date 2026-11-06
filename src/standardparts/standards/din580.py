"""DIN 580 lifting eye bolts (Ringschrauben), forged steel C15E."""

from __future__ import annotations

import math
from typing import Any

from build123d import Align, Box, Edge, GeomType, Part, Plane, Pos, Solid, Wire

from ..geometry import MetricThread, helical_thread, revolve_profile
from ..screws import THREAD_MODES, _fuse_ridge, _rise
from .base import Dimension, Option, Parameter, ParameterError, Standard
from .din580_data import SIZES, SizeData

# ---------------------------------------------------------------------------
# Blends and proportions DIN 580 does not dimension. They are chosen to look
# like the standard drawing and typical forged eye bolts; see EyeGeometry.

DOME_INTRUSION = 0.04    # collar dome apex above the bottom of the eye, x d4
COLLAR_ROUND = 0.15      # collar top-edge round, x e
BEARING_CHAMFER = 0.05   # 45 deg edge break on the bearing face, x e
COLLAR_DRAFT = 1 / 20    # collar flank draft (DIN 580 Bild 1: 1:20)
UNDERCUT_FLANK = 30.0    # undercut flank on the thread side, deg from radial
RING_END = 172.0         # the lofted ring spans +-RING_END deg from the top
RING_STEP = 15.0         # loft section spacing, deg


class EyeGeometry:
    """Derived construction values of one size (all in mm, Z up).

    * The eye opening (d4) and the ring outline (d3) are concentric, centred
      on the Z axis at zc = h - d3 / 2, so the top of the ring is at h. The
      ring lies in the XZ plane.
    * The ring section is an ellipse with in-plane semi-axis a = k / 2 =
      (d3 - d4) / 4 on the centre circle Rm = (d3 + d4) / 4. Its
      out-of-plane semi-axis grows linearly with depth from k / 2 at the
      top (a round section, as DIN 580 draws it) to m / 2 at the bottom
      section, which is buried in the collar. In the side view the flanks
      of the eye are straight lines tapering from k to m.
    * The collar is drafted 1:20 from d2 at the bearing face, e high, with a
      spherical dome on top whose apex rises a little into the bottom of
      the eye, as the front view of the drawing shows.
    * The ring reaches down into the collar. Below z_low it is cut off; at
      that height its section lies inside the collar, so the cut is hidden.
    """

    def __init__(self, sd: SizeData):
        self.sd = sd
        self.r_c = sd.d2 / 2                       # collar radius at z = 0
        self.r_e = self.r_c - COLLAR_DRAFT * sd.e  # collar radius at z = e
        self.a = (sd.d3 - sd.d4) / 4
        self.Rm = (sd.d3 + sd.d4) / 4
        self.zc = sd.h - sd.d3 / 2
        self.z_eye_bottom = self.zc - sd.d4 / 2
        # Height where the ring's outer contour meets the collar flank.
        self.z_crease = self.zc - math.sqrt((sd.d3 / 2) ** 2 - self.r_e**2)
        self.z_low = 0.5 * self.z_crease
        # Collar dome: a sphere through the collar edge (r_e, e) and the apex.
        self.z_apex = self.z_eye_bottom + DOME_INTRUSION * sd.d4
        s = self.z_apex - sd.e
        self.R_dome = (self.r_e**2 + s**2) / (2 * s)
        self.z_dome_centre = self.z_apex - self.R_dome
        self.r_round = COLLAR_ROUND * sd.e
        self.chamfer = BEARING_CHAMFER * sd.e

    def half_width(self, phi: float) -> float:
        """Out-of-plane semi-axis of the ring section at angle phi (deg)
        from the top: k / 2 at the top, m / 2 at the bottom, linear in z."""
        sd = self.sd
        return sd.k / 2 + (sd.m - sd.k) / 2 * (1 - math.cos(math.radians(phi))) / 2


def _ring(g: EyeGeometry) -> Part:
    """The eye: a loft through elliptical sections around the centre circle,
    from -RING_END over the top to +RING_END, cut off below z_low."""
    sd = g.sd
    n = math.floor((RING_END - 1e-6) / RING_STEP)
    phis = [-RING_END, *(i * RING_STEP for i in range(-n, n + 1)), RING_END]
    sections = []
    for phi in phis:
        t = math.radians(phi)
        radial = (math.sin(t), 0.0, math.cos(t))
        plane = Plane(
            origin=(g.Rm * radial[0], 0.0, g.zc + g.Rm * radial[2]),
            x_dir=radial,
            z_dir=(math.cos(t), 0.0, -math.sin(t)),  # path tangent
        )
        sections.append(Wire([Edge.make_ellipse(g.a, g.half_width(phi), plane=plane)]))
    loft = Solid.make_loft(sections)
    keep = Pos(0, 0, g.z_low) * Box(
        2 * sd.d3, 2 * sd.d3, 2 * sd.h, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )
    ring = loft & keep
    if ring is None or len(ring.solids()) != 1 or not ring.is_valid:
        raise RuntimeError(f"ring construction failed for DIN 580 {sd.size}")
    # The cut only removes the buried bottom of the ring.
    if not 0.8 * loft.volume < ring.volume < loft.volume:
        raise RuntimeError(f"ring cut failed for DIN 580 {sd.size}")
    return ring


def _collar_profile(g: EyeGeometry) -> list:
    """Profile from the bearing face edge round the collar to the axis."""
    r_c, rr = g.r_c, g.r_round
    zs, Rs = g.z_dome_centre, g.R_dome
    # Round of radius rr tangent to the drafted flank r = r_c - z * draft
    # and, from inside, to the dome sphere. Its centre lies rr inside the
    # flank and Rs - rr from the sphere centre.
    q = math.hypot(1.0, COLLAR_DRAFT)
    gr, gz = 1.0 / q, COLLAR_DRAFT / q  # outward flank normal

    def centre(z: float) -> tuple[float, float]:
        return r_c - COLLAR_DRAFT * z - rr * q, z

    lo, hi = zs, g.sd.e  # bisection on the centre height
    for _ in range(80):
        mid = (lo + hi) / 2
        cx, cz = centre(mid)
        if math.hypot(cx, cz - zs) > Rs - rr:
            hi = mid
        else:
            lo = mid
    cx, cz = centre(lo)
    fx, fz = cx + rr * gr, cz + rr * gz          # tangent point on the flank
    k = Rs / (Rs - rr)
    tx, tz = k * cx, zs + k * (cz - zs)          # tangent point on the dome
    a0 = math.atan2(fz - cz, fx - cx)
    a1 = math.atan2(tz - cz, tx - cx)
    am = (a0 + a1) / 2
    round_mid = (cx + rr * math.cos(am), cz + rr * math.sin(am))
    b1 = math.atan2(tx, tz - zs)  # angle of the dome tangent point from the axis
    dome_mid = (Rs * math.sin(b1 / 2), zs + Rs * math.cos(b1 / 2))
    c = g.chamfer
    return [
        (r_c - c, 0.0),
        (r_c - COLLAR_DRAFT * c, c),
        (fx, fz),
        ("arc", round_mid, (tx, tz)),
        ("arc", dome_mid, (0.0, g.z_apex)),
    ]


def _shank_profile(sd: SizeData, thread: MetricThread, mode: str) -> list:
    """Revolved profile of the shank, undercut, collar and dome.

    Tip at z = -l with an ISO 4753 chamfer (45 deg down to the minor
    diameter). The thread ends at z = -f; a flank at UNDERCUT_FLANK deg runs
    down to the undercut diameter dg, which meets the bearing face with
    radius r2.
    """
    R = sd.d / 2
    l = sd.l
    r_tip = thread.d3 / 2
    r_g = sd.dg / 2
    r2 = sd.r2
    z_t = -sd.f
    r_top = R if mode == "simplified" else thread.d1 / 2
    tip = [(0.0, -l), (r_tip, -l)]
    if r_top > r_tip:
        tip.append((r_top, -l + _rise(r_top - r_tip, 45.0)))
    flank = (r_top - r_g) * math.tan(math.radians(UNDERCUT_FLANK))
    fillet_mid = (r_g + r2 - r2 / math.sqrt(2), -r2 + r2 / math.sqrt(2))
    return [
        *tip,
        (r_top, z_t),                      # end of the threaded face
        (r_g, z_t + flank),                # flank into the undercut
        (r_g, -r2),
        ("arc", fillet_mid, (r_g + r2, 0.0)),
        *_collar_profile(EyeGeometry(sd)),
    ]


def _checked_fuse(a: Part, b: Part, what: str) -> Part:
    """a + b, checked against the inclusion-exclusion volume."""
    overlap = a & b
    if overlap is None or not overlap.solids() or overlap.volume <= 0:
        raise RuntimeError(f"ring does not overlap the collar for {what}")
    fused = a + b
    expected = a.volume + b.volume - overlap.volume
    if (
        fused is None
        or len(fused.solids()) != 1
        or not fused.is_valid
        or abs(fused.volume - expected) > 1e-5 * expected
    ):
        raise RuntimeError(f"ring fuse failed for {what}")
    return fused


def _check_hidden(part: Part, sd: SizeData, what: str) -> None:
    """The ring's end caps and its cut at z_low must end up inside the
    collar. The only planar faces left are the bearing face and the tip."""
    for face in part.faces():
        if face.geom_type != GeomType.PLANE:
            continue
        bb = face.bounding_box()
        flat = bb.size.Z < 1e-6 * sd.d
        if not (flat and (abs(bb.min.Z) < 1e-6 * sd.d or abs(bb.min.Z + sd.l) < 1e-6 * sd.d)):
            raise RuntimeError(f"construction face left exposed on {what}")


def build_eye_bolt(sd: SizeData, thread_mode: str) -> Part:
    """Build the eye bolt solid.

    Coordinate system: Z is the bolt axis. The collar bearing face lies in
    the XY plane at z = 0, the eye rises to z = h with the ring in the XZ
    plane (the opening looks along Y), and the threaded shank runs down to
    z = -l.
    """
    if thread_mode not in THREAD_MODES:
        raise ParameterError(f"unknown thread mode {thread_mode!r}")
    what = f"DIN 580 {sd.size}"
    thread = MetricThread(sd.d, sd.P)
    g = EyeGeometry(sd)
    core = revolve_profile(_shank_profile(sd, thread, thread_mode))
    head = _checked_fuse(core, _ring(g), what)
    _check_hidden(head, sd, what)
    if thread_mode == "simplified":
        return head

    # Ridge envelope: the ISO 4753 point at the tip and a cone at the
    # undercut flank angle, both offset from the core's own faces (see
    # screws.py: coincident faces make the OCCT fuse drop the ridge).
    P = thread.P
    R = sd.d / 2
    r_core = thread.d1 / 2
    r_tip = thread.d3 / 2
    t = math.tan(math.radians(UNDERCUT_FLANK))
    r_out = R + 0.05 * P
    r_in = r_core - 0.1 * P
    z_tip = -sd.l + 0.03 * P
    z_run = -sd.f - 0.1 * P   # envelope cone reaches r_core here
    envelope = revolve_profile([
        (0.0, z_tip),
        (r_tip, z_tip),
        (r_out, z_tip + _rise(r_out - r_tip, 45.0)),
        (r_out, z_run - (r_out - r_core) * t),
        (r_in, z_run + (r_core - r_in) * t),
        (0.0, z_run + (r_core - r_in) * t),
    ])
    ridge = helical_thread(thread, -sd.l - P, -sd.f + P)
    return _fuse_ridge(head, ridge, envelope, what)


def _wll(kg: float) -> tuple[float, str]:
    """Working load limit as a value and unit: kg below 1 t, else t."""
    return (kg, "kg") if kg < 1000 else (kg / 1000, "t")


class DIN580(Standard):
    id = "din580"
    title = "DIN 580"
    summary = "Lifting eye bolts, forged steel C15E, M8 to M100 x 6"
    category = "Lifting"
    source = "Values in mm, from DIN 580:2010-09 Table 1, with working load limits."

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="size",
                label="Thread size",
                kind="select",
                default="M12",
                options=[Option(s, sd.label) for s, sd in SIZES.items()],
                help="The thread length l is fixed for each size.",
            ),
            Parameter(
                name="thread",
                label="Thread",
                kind="select",
                default="simplified",
                options=[Option(k, v) for k, v in THREAD_MODES.items()],
                help="Simplified is lighter and is what most CAD libraries ship; "
                "the threaded length is a separate face for cosmetic threads.",
            ),
        ]

    def validate(self, raw: dict[str, Any]) -> dict[str, Any]:
        size = str(raw.get("size", "M12"))
        if size not in SIZES:
            raise ParameterError(f"unknown size {size!r}; choose one of {', '.join(SIZES)}")
        thread = str(raw.get("thread", "simplified"))
        if thread not in THREAD_MODES:
            raise ParameterError(f"thread must be one of {', '.join(THREAD_MODES)}")
        return {"size": size, "thread": thread}

    def designation(self, p: dict[str, Any]) -> str:
        return f"Eye bolt DIN 580 - {SIZES[p['size']].designation_thread} - C15E"

    def file_stem(self, p: dict[str, Any]) -> str:
        suffix = "_threaded" if p["thread"] == "modeled" else ""
        return f"DIN580_{p['size']}{suffix}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        sd = SIZES[p["size"]]
        t = MetricThread(sd.d, sd.P)
        wll = [_wll(x) for x in (sd.wll_axial, sd.wll_45, sd.wll_side)]
        return [
            Dimension("d1", "Thread", sd.designation_thread, unit=""),
            Dimension("P", "Pitch", sd.P),
            Dimension("l", "Thread length", sd.l),
            Dimension("d2", "Collar (bearing face) dia.", sd.d2),
            Dimension("d3", "Eye outer dia.", sd.d3),
            Dimension("d4", "Eye inner dia.", sd.d4),
            Dimension("e", "Collar height", sd.e),
            Dimension("h", "Overall height", sd.h),
            Dimension("k", "Ring thickness at the top", sd.k),
            Dimension("m", "Ring width at the collar", sd.m),
            Dimension("f max", "Thread undercut length", sd.f),
            Dimension("dg", "Undercut dia. (DIN 76-1)", sd.dg),
            Dimension("r2", "Undercut radius at bearing face", sd.r2),
            Dimension("d3 thread", "Thread minor dia.", round(t.d3, 3)),
            Dimension("WLL 0°", "Working load limit, axial", *wll[0]),
            Dimension("WLL 45°", "WLL per bolt, 2+ legs up to 45°", *wll[1]),
            Dimension("WLL side", "WLL per bolt, up to 45°, bolts at the load's sides", *wll[2]),
            Dimension("mass", "Approx. mass (table)", sd.mass, unit="kg"),
        ]

    def notes(self, p: dict[str, Any]) -> list[str]:
        out = []
        if p["thread"] == "simplified":
            out.append(
                "Thread not modeled: shank is a plain cylinder at d. The threaded "
                "length is its own face, ready for a cosmetic thread."
            )
        else:
            out.append(
                "Thread modeled with the ISO 68-1 basic profile (flat root at d1), "
                "right hand, ending at the undercut under the collar."
            )
        out.append(
            "Modeled at nominal sizes: eye d3 / d4 concentric with its top at h, a "
            "round ring section k at the top widening to m at the collar, collar d2 "
            "x e with the 1:20 draft, undercut f x dg with radius r2."
        )
        out.append(
            "DIN 580 does not dimension the collar dome, its edge round or the "
            "bearing-face edge break; they use typical proportions. The forging "
            "radius r1 and the undercut radius r3 are not modeled (sharp edges)."
        )
        out.append(
            "Working load limits apply to a bolt screwed fully home with the collar "
            "seated on a flat, machined face; see DIN 580 for the load directions."
        )
        return out

    def build(self, p: dict[str, Any]) -> Part:
        part = build_eye_bolt(SIZES[p["size"]], p["thread"])
        part.label = self.designation(p)
        return part

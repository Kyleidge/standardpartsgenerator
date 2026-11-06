"""Internal driving features (recesses) for screw heads, as checked cutters.

Cutters are tool solids: subtract them from a head with `checked_cut`.
Every builder places the recess's reference plane (where the penetration
depth is measured from) at ``z_ref`` and points the recess towards -Z. The
tool also reaches ``h_up`` above the reference plane, so it cuts cleanly
through flat or domed head tops without coincident faces.

Cross recesses, ISO 4757:1983
=============================

Source: ISO 4757:1983 Table 1 (type H) and Table 3 (type Z). The
interpretation of the symbols was cross-checked
against the ISO 4757 cross-recess model of the FreeCAD Fasteners workbench
(``screw_maker.makeHCrossRecess``, FsData/iso4757def.csv); its table agrees
with ours. The screw standards add m (recess diameter at the reference
plane) and the gauge penetration (min / max) per screw size.

The exact recess is defined by its gauges, not by a full drawing, so the
model is an approximation that keeps the dimensions the standards specify:

* Outer envelope (both types): the wing flanks are a cone at 26°30' to the
  axis (ISO 4757 Figures 1 and 2) starting at diameter m on the reference
  plane. They run down to the penetration depth p (the mean of the screw
  standard's min / max), where the envelope closes with a cone at 28° to
  the radial plane. With p and m fixed this way, the diameter at the bottom
  of the flanks, ``g_eff = m - 2 p tan 26.5°``, is derived; ISO 4757 gives
  g as a gauge dimension and g_eff stays within 16 % of it for every screw
  size (tested). This matches the ISO 4757 relation t1 = (g / 2) tan 28°
  (t1 = 0.22, 0.34, 0.61, 1.01, 1.35 for g = 0.81 ... 5.08), so the 28° is
  measured from the radial plane.
* Type H (Phillips): four corners of material are removed from the envelope
  as in ISO 4757 Figure 1. Each corner points at the axis; its tip lies at
  b / 2 from the axis at the depth where the bottom cone has diameter b
  (b is the core width across the corners), it is blunted to a flat of
  width e with the tip angle α, its flanks open at 92°, and the tip edge
  leans outwards by β towards the top, so the wings narrow with depth. The
  resulting wing width is close to f of Table 1 (tested). Angles α and 92°
  are converted to the horizontal section through the β-inclined plane, as
  in the FreeCAD model. Not modeled: the edge radius r at the top of the
  wings, and α for recess No. 0 is not printed in Table 1 (footnote 1);
  the model uses 138° as for No. 1 (assumed).
* Type Z (Pozidriv): four main wings of constant width f (Table 3) along
  the X and Y axes, a central cone of diameter g at the reference plane, and
  four narrow V-ribs along the diagonals (included angle δ, Table 3) that
  run out at the surface at radius 0.5625 m (the ribs span 1 to 1.25 m in
  ISO 4757 Figure 2). The rib keel is a straight line from that point down
  into the central cone, which it enters at 0.85 g / 2, so an arc of the
  cone stays visible between each wing and rib as in the figure; this
  slope (rib depth) is a modeling choice. Not modeled: the
  wing wall tapers α, β, γ, radii r1, r2 and the dimension b, j of Table 3.

Hexalobular internal driving feature, ISO 10664:2014
====================================================

Source: ISO 10664:2014 Table 1 (nominal A, B), identical to ISO 10664:2005
Table 1 for the sizes used here; Table 3 of ISO 10664:2005 (GO gauge
limits for A, B, Ri, Re). Of the 2014 edition only Table 1 was checked;
its foreword says only sizes were added.

* The contour is twelve tangent arcs: six outer lobes of radius Re centred
  at A / 2 - Re, six inner lobes of radius Ri centred at B / 2 + Ri, 30°
  apart. ISO 10664 defines the curvature only through its gauges, so Re is
  the GO gauge mean and Ri follows from tangency with the nominal A and B
  (derived; the same construction reproduces the GO gauge's own Ri within
  0.003 mm). A and B are the nominal socket values.
* Depth: the product standard's penetration t (the GO gauge must enter to
  t), then a 118° conical bottom inside B (the bottom contour is at the
  manufacturer's option, ISO 10664 Figure 1 note).

All values in millimetres.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

from build123d import Align, Box, Cone, Edge, Face, Part, Pos, Rot, Solid, Vector, Wire, extrude
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

from .geometry import revolve_profile

FLANK_ANGLE = 26.5      # cross recess wing flanks, degrees from the axis
BOTTOM_ANGLE = 28.0     # cross recess bottom cone, degrees from the radial plane
CORNER_ANGLE = 92.0     # type H: angle between the flanks of a corner (plan)
RIB_RADIUS = 0.5625     # type Z: rib run-out radius as a fraction of m
RIB_ENTRY = 0.85        # type Z: rib keel enters the central cone at this fraction of g / 2
DRILL_ANGLE = 118.0     # hexalobular socket bottom

_TAN_FLANK = math.tan(math.radians(FLANK_ANGLE))
_TAN_BOTTOM = math.tan(math.radians(BOTTOM_ANGLE))


def _deg(d: int, m: int = 0) -> float:
    return d + m / 60


@dataclass(frozen=True)
class CrossH:
    """ISO 4757 Table 1, recess type H (theoretical values)."""

    no: int
    b: float        # core width across the corner tips (0 / -0.03)
    e_min: float    # width of the flat at a corner tip
    e_max: float
    g: float        # gauge diameter at the bottom of the flanks (+0.05 / 0)
    f_min: float    # wing width
    f_max: float
    r: float        # radius at the top edge of the wings (not modeled)
    t1: float       # height of the bottom cone below g (ref)
    alpha: float    # corner tip angle, degrees
    beta: float     # lean of the corner tip edge, degrees

    @property
    def e(self) -> float:
        return (self.e_min + self.e_max) / 2


@dataclass(frozen=True)
class CrossZ:
    """ISO 4757 Table 3, recess type Z (theoretical values)."""

    no: int
    b: float        # (not modeled)
    f: float        # main wing width (0 / -0.025)
    g: float        # diameter of the central cone (0 / -0.05)
    r1_max: float
    r2_max: float
    j_max: float
    alpha: float    # degrees (wing tapers, not modeled)
    beta: float
    gamma: float
    delta: float    # rib angle, degrees


# fmt: off
H_RECESSES: dict[int, CrossH] = {r.no: r for r in [
    #      no  b     e_min e_max g     f_min f_max r    t1    alpha  beta
    CrossH(0, 0.61, 0.26, 0.36, 0.81, 0.31, 0.36, 0.3, 0.22, 138.0, 7.0),  # alpha assumed
    CrossH(1, 0.97, 0.41, 0.46, 1.27, 0.51, 0.56, 0.5, 0.34, 138.0, 7.0),
    CrossH(2, 1.47, 0.79, 0.84, 2.29, 0.66, 0.74, 0.6, 0.61, 140.0, _deg(5, 45)),
    CrossH(3, 2.41, 1.98, 2.03, 3.81, 0.79, 0.86, 0.8, 1.01, 146.0, _deg(5, 45)),
    CrossH(4, 3.48, 2.39, 2.44, 5.08, 1.19, 1.27, 1.0, 1.35, 153.0, 7.0),
]}

Z_RECESSES: dict[int, CrossZ] = {r.no: r for r in [
    #      no  b     f     g     r1    r2    j     alpha        beta          gamma        delta
    CrossZ(0, 0.76, 0.48, 0.86, 0.30, 0.10, 0.13, 7.0,         _deg(7, 45),  _deg(4, 23), 46.0),
    CrossZ(1, 1.27, 0.74, 1.32, 0.30, 0.13, 0.15, 7.0,         _deg(7, 45),  _deg(4, 23), 46.0),
    CrossZ(2, 1.83, 1.03, 2.34, 0.38, 0.15, 0.15, _deg(5, 45), _deg(6, 20),  3.0,         46.0),
    CrossZ(3, 2.72, 1.42, 3.86, 0.51, 0.25, 0.20, _deg(5, 45), _deg(6, 20),  3.0,         _deg(56, 15)),
    CrossZ(4, 3.96, 2.16, 5.08, 0.64, 0.38, 0.20, 7.0,         _deg(7, 45),  _deg(4, 23), _deg(56, 15)),
]}
# fmt: on

CROSS_TYPES = {
    "H": "Type H (Phillips)",
    "Z": "Type Z (Pozidriv)",
}


@dataclass(frozen=True)
class Hexalobular:
    """ISO 10664 hexalobular socket: nominal A, B (Table 1) and the GO
    gauge's mean outer lobe radius Re (2005 Table 3)."""

    no: int
    A: float    # point to point
    B: float    # across the inner lobes
    Re: float   # outer lobe radius (GO gauge mean)

    @property
    def name(self) -> str:
        return f"T{self.no}"

    @property
    def Ri(self) -> float:
        """Inner lobe radius that makes the twelve arcs tangent (derived)."""
        return hexalobular_ri(self.A, self.B, self.Re)


# fmt: off
HEXALOBULAR: dict[int, Hexalobular] = {h.no: h for h in [
    #           no   A      B     Re (GO gauge mean)
    Hexalobular(6,   1.75,  1.27, 0.132),
    Hexalobular(8,   2.4,   1.75, 0.1905),
    Hexalobular(10,  2.8,   2.05, 0.229),
    Hexalobular(15,  3.35,  2.4,  0.267),
    Hexalobular(20,  3.95,  2.85, 0.305),
    Hexalobular(25,  4.5,   3.25, 0.3745),
    Hexalobular(30,  5.6,   4.05, 0.451),
    Hexalobular(40,  6.75,  4.85, 0.546),
    Hexalobular(45,  7.93,  5.64, 0.574),
    Hexalobular(50,  8.95,  6.45, 0.775),
    Hexalobular(55,  11.35, 8.05, 0.767),
]}
# fmt: on


def hexalobular_ri(A: float, B: float, Re: float) -> float:
    """Inner lobe radius Ri for which an outer arc (radius Re, centre at
    A/2 - Re on the X axis) and an inner arc (radius Ri, centre at B/2 + Ri
    at 30 deg) are tangent: |Ce - Ci| = Re + Ri, solved in closed form."""
    ce = A / 2 - Re
    c = math.cos(math.pi / 6)
    # (B/2 + Ri)^2 - 2 ce c (B/2 + Ri) + ce^2 = (Re + Ri)^2
    h = B / 2
    a1 = 2 * h - 2 * ce * c - 2 * Re
    a0 = h * h - 2 * ce * c * h + ce * ce - Re * Re
    return -a0 / a1


# --- checks -------------------------------------------------------------------

def precise_volume(shape, eps: float = 1e-6) -> float:
    """Volume integrated to relative error eps (OCCT adaptive integration).
    An empty boolean result counts as 0."""
    try:
        wrapped = shape.wrapped
    except (AttributeError, AssertionError):  # None or a null shape
        return 0.0
    if wrapped is None:
        return 0.0
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(wrapped, props, eps)
    return props.Mass()


def _check(shape, what: str, step: str) -> Part:
    if shape is None or len(shape.solids()) != 1 or not shape.is_valid:
        raise RuntimeError(f"{what}: {step} failed")
    return shape


def checked_cut(
    body: Part,
    tool: Part,
    reference: Part,
    what: str,
    rel: float = 0.005,
    retry: Callable[[int], Part] | None = None,
    attempts: int = 4,
) -> Part:
    """Cut `tool` from `body` and verify the result.

    `reference` is a simple solid (typically the plain revolved head and
    shank, without thread) that coincides with `body` wherever the tool
    reaches. The volume removed from `body` must equal the volume of
    tool & reference within `rel`, and the result must be a single valid
    solid. OCCT booleans can drop faces or solids silently; a mismatch
    means the cut went wrong. `retry(i)` may supply an alternative tool
    (e.g. rotated) for attempt i >= 1; the last failure raises.

    Volumes are integrated to a relative error of 1e-6 (`precise_volume`):
    OCCT's default integration is off by up to ~5e-4 of the volume on
    bodies with helical thread faces, which is more than a small recess
    (ISO 7045 M2 x 8 modeled: 0.017 mm3 of 35 mm3 against a 1.24 mm3 recess).
    """
    expected = precise_volume(tool & reference)
    if expected <= 0:
        raise RuntimeError(f"{what}: recess tool does not reach the head")
    body_volume = precise_volume(body)
    tol = rel * expected + 1e-5 * body_volume
    for i in range(attempts if retry else 1):
        t = tool if i == 0 else retry(i)
        try:
            cut = body - t
        except Exception:  # noqa: BLE001 - kernel failure means "retry"
            continue
        if cut is None or len(cut.solids()) != 1 or not cut.is_valid:
            continue
        removed = body_volume - precise_volume(cut)
        if abs(removed - expected) <= tol:
            return cut
    raise RuntimeError(f"recess cut failed for {what}")


def min_wall(tool: Part, body: Part, skip: Callable[[Face], bool]) -> float:
    """Smallest distance between the tool and the faces of `body` that
    `skip` does not exclude (exclude the head top that the recess opens
    into). A breakthrough anywhere else gives 0."""
    return min(tool.distance_to(f) for f in body.faces() if not skip(f))


# --- cross recesses -----------------------------------------------------------

@dataclass(frozen=True)
class CrossGeometry:
    """Derived sizes of a modeled cross recess (relative to the reference
    plane, depths positive downwards)."""

    m: float          # diameter at the reference plane
    depth: float      # flank depth = penetration used for the model
    g_eff: float      # diameter at the bottom of the flanks
    t_total: float    # depth of the bottom cone apex

    @classmethod
    def of(cls, m: float, depth: float) -> CrossGeometry:
        g_eff = m - 2 * depth * _TAN_FLANK
        if g_eff <= 0:
            raise ValueError("recess depth too large for m")
        return cls(m, depth, g_eff, depth + g_eff / 2 * _TAN_BOTTOM)


def _envelope(cg: CrossGeometry, h_up: float) -> Part:
    r_top = cg.m / 2 + h_up * _TAN_FLANK
    return revolve_profile([
        (0.0, h_up),
        (r_top, h_up),
        (cg.g_eff / 2, -cg.depth),
        (0.0, -cg.t_total),
    ])


def _loft(sections: list[list[tuple[float, float, float]]]) -> Solid:
    wires = [Wire.make_polygon([Vector(*p) for p in pts], close=True) for pts in sections]
    return Solid.make_loft(wires, ruled=True)


def _corner_h(rec: CrossH, cg: CrossGeometry, h_up: float) -> Solid:
    """One type H corner (material between two wings), tip towards the axis
    on the +X side."""
    tb = cg.depth + (cg.g_eff - rec.b) / 2 * _TAN_BOTTOM   # depth where the cone is b wide
    if tb > cg.t_total:
        raise ValueError(f"recess No. {rec.no}: core b wider than the recess bottom")
    beta = math.radians(rec.beta)
    a_p = math.atan(math.tan(math.radians(rec.alpha / 2)) / math.cos(beta))
    c_p = math.atan(math.tan(math.radians(CORNER_ANGLE / 2)) / math.cos(beta))
    e2 = rec.e / 2
    dre = e2 / math.tan(a_p)
    reach = 2 * (cg.m / 2 + h_up) + 1.0            # well past the envelope
    z_lo = -cg.t_total - 0.2 * cg.m
    z_hi = h_up + 0.2 * cg.m

    def section(z: float) -> list[tuple[float, float, float]]:
        x0 = rec.b / 2 + (z + tb) * math.tan(beta)
        x1 = x0 + dre
        dx, dy = reach * math.cos(c_p), reach * math.sin(c_p)
        return [(x0, 0.0, z), (x1, e2, z), (x1 + dx, e2 + dy, z),
                (x1 + dx, -e2 - dy, z), (x1, -e2, z)]

    if rec.b / 2 + (z_lo + tb) * math.tan(beta) <= 0.05 * rec.b:
        raise ValueError(f"recess No. {rec.no}: corner tip crosses the axis")
    return _loft([section(z_lo), section(z_hi)])


@lru_cache(maxsize=256)
def _cross_h(no: int, m: float, depth: float, h_up: float) -> Part:
    rec = H_RECESSES[no]
    cg = CrossGeometry.of(m, depth)
    what = f"cross recess H{no} m={m:g}"
    env = _check(_envelope(cg, h_up), what, "envelope")
    corner = _corner_h(rec, cg, h_up)
    tool = env
    for i in range(4):
        before = tool.volume
        tool = _check(tool - Rot(0, 0, 90 * i) * corner, what, f"corner {i}")
        if not tool.volume < before:
            raise RuntimeError(f"{what}: corner {i} removed nothing")
    if not 0.15 * env.volume < tool.volume < 0.85 * env.volume:
        raise RuntimeError(f"{what}: unexpected volume")
    # Wings along X and Y, like the drawings of ISO 7045 / 7046-1.
    return Rot(0, 0, 45) * tool


def _rib_z(rec: CrossZ, cg: CrossGeometry, t_core: float, h_up: float) -> Solid:
    """One type Z rib along +X: a V-groove of included angle delta whose keel
    runs from the surface at RIB_RADIUS * m down into the central cone."""
    rg = rec.g / 2
    x_out = RIB_RADIUS * cg.m
    # The keel enters the core cone at RIB_ENTRY * g / 2. Shallow enough that
    # an arc of the central cone stays visible between each wing and rib
    # (ISO 4757 Figure 2, plan view).
    x_q = RIB_ENTRY * rg
    z_q = -t_core * (1 - x_q / rg)        # core cone radius is x_q at z_q
    slope = -z_q / (x_out - x_q)          # keel rises by `slope` per unit x

    def keel(x: float) -> float:
        return z_q + (x - x_q) * slope

    x0 = 0.9 * x_q                        # inner end, inside the core cone
    x1 = x_out + 0.05 * cg.m              # outer end, keel above the surface
    t = math.tan(math.radians(rec.delta / 2))
    # The inner end face must lie inside the core cone below the surface.
    w0 = -keel(x0) * t
    if math.hypot(x0, w0) >= rg * 0.98:
        raise ValueError(f"recess Z{rec.no}: rib end outside the central cone")

    def section(x: float) -> list[tuple[float, float, float]]:
        k = keel(x)
        w = (h_up - k) * t
        return [(x, 0.0, k), (x, w, h_up), (x, -w, h_up)]

    return _loft([section(x0), section(x1)])


@lru_cache(maxsize=256)
def _cross_z(no: int, m: float, depth: float, h_up: float) -> Part:
    rec = Z_RECESSES[no]
    cg = CrossGeometry.of(m, depth)
    what = f"cross recess Z{no} m={m:g}"
    if rec.g >= cg.m or rec.f >= rec.g:
        raise ValueError(f"{what}: inconsistent recess data")
    env = _check(_envelope(cg, h_up), what, "envelope")
    # Central cone: diameter g at the reference plane, apex a little above
    # the envelope apex so the two never touch.
    t_core = 0.97 * cg.t_total
    rg = rec.g / 2
    core = revolve_profile([
        (0.0, h_up),
        (rg * (1 + h_up / t_core), h_up),
        (0.0, -t_core),
    ])
    height = cg.t_total + h_up + 2.0
    span = 2 * cg.m + 2.0
    z_mid = (h_up - cg.t_total) / 2
    slab_x = Pos(0, 0, z_mid) * Box(span, rec.f, height)
    slab_y = Pos(0, 0, z_mid) * Box(rec.f, span, height)
    inner = _check(slab_x + slab_y + core, what, "wing union")
    main = _check(env & inner, what, "wing trim")
    if not main.volume < env.volume:
        raise RuntimeError(f"{what}: wing trim removed nothing")
    rib = _rib_z(rec, cg, t_core, h_up)
    tool = main
    for i in range(4):
        before = tool.volume
        tool = _check(tool + Rot(0, 0, 45 + 90 * i) * rib, what, f"rib {i}")
        if not tool.volume > before:
            raise RuntimeError(f"{what}: rib {i} added nothing")
    return tool


def cross_recess(
    kind: str, no: int, m: float, depth: float, z_ref: float = 0.0, h_up: float | None = None
) -> Part:
    """Cross recess tool, type "H" or "Z", recess No. `no`.

    m is the recess diameter at the reference plane z = z_ref, `depth` the
    penetration depth the flanks reach (use the screw standard's mean
    penetration). `h_up` is how far the tool reaches above the reference
    plane (default 0.1 m); make it clear domed heads.
    """
    if h_up is None:
        h_up = 0.1 * m
    key = (no, round(m, 6), round(depth, 6), round(h_up, 6))
    if kind == "H":
        tool = _cross_h(*key)
    elif kind == "Z":
        tool = _cross_z(*key)
    else:
        raise ValueError(f"unknown cross recess type {kind!r}")
    return Pos(0, 0, z_ref) * tool


def cross_geometry(m: float, depth: float) -> CrossGeometry:
    return CrossGeometry.of(m, depth)


# --- hexalobular ---------------------------------------------------------------

def _xy(r: float, a: float) -> Vector:
    return Vector(r * math.cos(a), r * math.sin(a), 0.0)


def hexalobular_face(h: Hexalobular) -> Face:
    """The ISO 10664 contour in the XY plane, outer lobes on the X axis
    and every 60 deg."""
    Re, Ri = h.Re, h.Ri
    ce, ci = h.A / 2 - Re, h.B / 2 + Ri
    edges = []
    for k in range(6):
        a = math.radians(60 * k)
        a_in, a_prev = a + math.pi / 6, a - math.pi / 6
        # tangent points with the neighbouring inner arcs
        def tangent(a_inner: float) -> Vector:
            c_e, c_i = _xy(ce, a), _xy(ci, a_inner)
            return c_e + (c_i - c_e).normalized() * Re

        p_start, p_end = tangent(a_prev), tangent(a_in)
        edges.append(Edge.make_three_point_arc(p_start, _xy(h.A / 2, a), p_end))
        # inner arc from p_end to the next outer arc's start point
        c_e_next = _xy(ce, a + math.pi / 3)
        c_i = _xy(ci, a_in)
        p_next = c_e_next + (c_i - c_e_next).normalized() * Re
        edges.append(Edge.make_three_point_arc(p_end, _xy(h.B / 2, a_in), p_next))
    return Face(Wire(edges))


@lru_cache(maxsize=128)
def _hexalobular(no: int, depth: float, h_up: float) -> Part:
    h = HEXALOBULAR[no]
    what = f"hexalobular {h.name}"
    face = hexalobular_face(h)
    prism = Pos(0, 0, -depth) * extrude(face, amount=depth + h_up)
    r_d = 0.96 * h.B / 2
    h_cone = r_d / math.tan(math.radians(DRILL_ANGLE / 2))
    cone = Pos(0, 0, -depth - h_cone) * Cone(
        bottom_radius=0,
        top_radius=r_d,
        height=h_cone + 1e-3 * h.A,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    )
    tool = _check(prism + cone, what, "socket union")
    if not tool.volume > prism.volume:
        raise RuntimeError(f"{what}: socket bottom missing")
    return tool


def hexalobular_recess(no: int, depth: float, z_ref: float = 0.0, h_up: float | None = None) -> Part:
    """ISO 10664 hexalobular socket tool, socket No. `no` (T`no`), with its
    contour down to `depth` below z_ref and a 118 deg conical bottom."""
    if h_up is None:
        h_up = 0.1 * HEXALOBULAR[no].A
    return Pos(0, 0, z_ref) * _hexalobular(no, round(depth, 6), round(h_up, 6))


def hexalobular_depth_total(no: int, depth: float) -> float:
    """Depth of the cone tip of the modeled socket below the reference plane."""
    r_d = 0.96 * HEXALOBULAR[no].B / 2
    return depth + r_d / math.tan(math.radians(DRILL_ANGLE / 2))

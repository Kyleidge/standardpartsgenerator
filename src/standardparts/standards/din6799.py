"""DIN 6799 retaining washers for shafts (E-clips).

Plan view, as in DIN 6799 Figure 1 with the opening turned towards +Y.
Polar angle psi is measured from -Y (the back of the washer) towards +X,
as in `din471.u`.

What the table fixes, and how the model uses it:

* d3: the outer contour is a circle of diameter d3 (the standard's maximum
  external diameter when seated), centred on the shaft axis.
* d2: three contact lobes sit on the groove diameter. The back lobe's tip
  is an arc of d2 at psi = 0; each jaw's inner face is an arc of d2 that
  ends at the jaw tip.
* a: the jaw tips are where the d2 circle crosses x = ±a/2, so the
  opening between them is exactly a. The jaw flanks run straight from the
  tips to the jaw ends, parallel to Y, keeping the opening at a, as drawn
  in the standard.
* s: the washer is extruded from z = 0 to z = s.

What DIN 6799 leaves to the manufacturer, modeled to the proportions of
the standard's figure and calibrated so the modeled mass comes within
16 % of the table mass on every size (-11 % to +16 %):

* relief cut-outs between the back lobe and the jaws, out to radius
  d2/2 + RELIEF * (d3 - d2)/2, leaving a band of the remaining width;
* a tapered back lobe, LOBE_TIP * d3/2 wide (each side of the axis) at
  the tip and LOBE_ROOT * d3/2 at the root;
* jaw contact faces spanning JAW_ARC of the d2 circle behind the tips;
* jaw ends cut at y = JAW_END * d3/2 and rounded;
* fillets on every corner (radii in `EClip.plan`).

Only one state is modeled. Unlike a DIN 471 circlip, an E-clip is pushed
on radially and only flexes while its jaws pass the shaft's equator. Once
seated, its three lobes rest on the groove bottom in essentially the free
shape. This model is that seated, unstressed shape: free opening a and
contact circle d2. Real washers sit with a slight preload, a few hundredths
of a millimetre, below the resolution of the table.
"""

from __future__ import annotations

import math
from typing import Any

from build123d import Face, Part, Vector, Vertex, Wire, extrude

from .base import Dimension, Option, Parameter, ParameterError, Standard
from .din471 import _disk, _facing_up, _fan, u
from .din6799_data import SIZES, ClipData

# Proportions the standard leaves to the manufacturer.
RELIEF = 0.56                 # relief depth, fraction of the radial width (d3 - d2) / 2
LOBE_TIP = 0.07               # back lobe half-width at the tip, fraction of d3 / 2
LOBE_ROOT = 0.15              # back lobe half-width at the root, fraction of d3 / 2
JAW_ARC = math.radians(36)    # angle of d2 the jaw contact face spans behind the tip
JAW_END = 0.64                # y of the jaw ends, fraction of d3 / 2
STEEL = 7.85e-3               # g / mm^3


def _fmt(x: float) -> str:
    return f"{x:g}"


def _polygon(*pts: Vector) -> Face:
    return Face(Wire.make_polygon(list(pts), close=True))


def _rect(x0: float, x1: float, y0: float, y1: float) -> Face:
    return _polygon(Vector(x0, y0), Vector(x1, y0), Vector(x1, y1), Vector(x0, y1))


class EClip:
    """Plan-view geometry of one DIN 6799 size, seated on the groove."""

    def __init__(self, cd: ClipData):
        self.cd = cd
        self.r2 = cd.d2 / 2                       # contact radius (groove)
        self.r3 = cd.d3 / 2                       # outer radius
        self.r_relief = self.r2 + RELIEF * (self.r3 - self.r2)
        # Jaw tips: the d2 circle at x = ±a/2, on the opening side.
        self.psi_tip = math.pi - math.asin(cd.a / cd.d2)
        self.y_tip = -self.r2 * math.cos(self.psi_tip)
        self.psi_jaw = self.psi_tip - JAW_ARC     # back face of each jaw
        self.y_end = JAW_END * self.r3
        self.x_end = math.sqrt(self.r3**2 - self.y_end**2)
        self.lobe_tip = LOBE_TIP * self.r3
        self.lobe_root = LOBE_ROOT * self.r3

    @property
    def jaw_width(self) -> float:
        """Width of each jaw at its end, from the flank to the outer contour."""
        return self.x_end - self.cd.a / 2

    def _sharp(self) -> Face:
        """The outline with sharp corners."""
        r2, r3, rr = self.r2, self.r3, self.r_relief
        a, big = self.cd.a, 4 * self.r3
        # Back lobe: a trapezoid through its tip and root corners, extended
        # past both so the cut edges are clean.
        tip = Vector(self.lobe_tip, -math.sqrt(r2**2 - self.lobe_tip**2))
        root = Vector(self.lobe_root, -math.sqrt(rr**2 - self.lobe_root**2))
        inner, outer = tip + (tip - root) * 0.5, root + (root - tip) * 0.5
        lobe = _polygon(Vector(-inner.X, inner.Y), inner, outer, Vector(-outer.X, outer.Y))
        relief = (_disk(Vector(), rr) & _fan(-self.psi_jaw, self.psi_jaw, big)) - lobe
        plate = _disk(Vector(), r3) - _disk(Vector(), r2) - relief
        plate = plate - _rect(-a / 2, a / 2, 0, big) - _rect(-big, big, self.y_end, big)
        faces = plate.faces()
        if len(faces) != 1:
            raise RuntimeError(f"outline construction failed for DIN 6799 - {self.cd.size}")
        return _facing_up(faces[0])

    def corners(self) -> list[tuple[float, list[Vector]]]:
        """Fillet radius and the corner points it applies to, both sides."""
        cd, r2, rr = self.cd, self.r2, self.r_relief
        depth = rr - r2

        def both(p: Vector) -> list[Vector]:
            return [p, Vector(-p.X, p.Y)]

        return [
            # back lobe tip (convex) and root (concave)
            (0.4 * self.lobe_tip, both(Vector(self.lobe_tip, -math.sqrt(r2**2 - self.lobe_tip**2)))),
            (0.45 * depth, both(Vector(self.lobe_root, -math.sqrt(rr**2 - self.lobe_root**2)))),
            # relief end at the jaw (concave) and jaw back edge (convex)
            (0.45 * depth, both(u(self.psi_jaw) * rr)),
            (0.25 * depth, both(u(self.psi_jaw) * r2)),
            # jaw tip
            (0.12 * depth, both(Vector(cd.a / 2, self.y_tip))),
            # rounded jaw ends
            (0.47 * self.jaw_width,
             both(Vector(cd.a / 2, self.y_end)) + both(Vector(self.x_end, self.y_end))),
        ]

    def plan(self) -> Face:
        """Single plan-view face of the washer, normal +Z."""
        face = self._sharp()
        tol = 1e-6 * max(1.0, self.r3)
        for radius, points in self.corners():
            verts: list[Vertex] = []
            for p in points:
                v = min(face.vertices(), key=lambda v: (Vector(v) - p).length)
                if (Vector(v) - p).length > tol:
                    raise RuntimeError(f"corner lookup failed for DIN 6799 - {self.cd.size}")
                verts.append(v)
            face = face.fillet_2d(radius, verts)
        return _facing_up(face)

    def solid(self) -> Part:
        """Washer with its flat faces at z = 0 and z = s, axis along Z."""
        part = extrude(self.plan(), amount=self.cd.s)
        if not part.is_valid or len(part.solids()) != 1:
            raise RuntimeError(f"washer solid failed for DIN 6799 - {self.cd.size}")
        return part


class DIN6799(Standard):
    id = "din6799"
    title = "DIN 6799"
    summary = "Retaining washers (E-clips) for shafts, groove dia. 0.8 to 30 mm"
    category = "Retaining rings"
    source = "Values in mm, from DIN 6799 (1981 / 2011 / 2017, unchanged)."

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="size",
                label="Groove diameter d2",
                kind="select",
                default="6",
                options=[
                    Option(
                        k,
                        f"{k} mm  (shaft {_fmt(r.d1_min)}–{_fmt(r.d1_max)}, s = {_fmt(r.s)})",
                    )
                    for k, r in SIZES.items()
                ],
                help="DIN 6799 washers are sized by the groove diameter. The "
                "shaft range d1 is the one the standard recommends for each size.",
            ),
        ]

    def validate(self, raw: dict[str, Any]) -> dict[str, Any]:
        size = str(raw.get("size", "6")).strip().replace(",", ".")
        try:
            size = f"{float(size):g}"
        except ValueError:
            pass
        if size not in SIZES:
            raise ParameterError(
                f"unknown groove diameter {size!r}; choose one of {', '.join(SIZES)}"
            )
        return {"size": size}

    def designation(self, p: dict[str, Any]) -> str:
        return f"DIN 6799 - {SIZES[p['size']].size}"

    def file_stem(self, p: dict[str, Any]) -> str:
        return f"DIN6799_{SIZES[p['size']].size}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        cd = SIZES[p["size"]]
        t_min = (cd.d1_min - cd.d2) / 2
        t_max = (cd.d1_max - cd.d2) / 2
        return [
            Dimension("d2", f"Groove diameter (nominal, +0 / -{_fmt(cd.d2_tol)})", cd.d2),
            Dimension("d1", "Shaft diameter range", f"{_fmt(cd.d1_min)} – {_fmt(cd.d1_max)}"),
            Dimension("s", f"Thickness (±{_fmt(cd.s_tol)})", cd.s),
            Dimension("a", f"Opening, unstressed (±{_fmt(cd.a_tol)})", cd.a),
            Dimension("d3 max", "Outer dia. seated in the groove", cd.d3),
            Dimension("m", f"Groove width (+{_fmt(cd.m_tol)} / 0)", cd.m),
            Dimension("t", "Groove depth over the shaft range",
                      f"{_fmt(round(t_min, 3))} – {_fmt(round(t_max, 3))}"),
            Dimension("n min", "Groove to shaft end", cd.n_min),
            Dimension("g max", "Corner chamfer / radius of abutting part", cd.g),
            Dimension("G ref.", "Free outer dia. (Rotor Clip, not DIN)", cd.od_free),
            Dimension("mass", "Approx. mass (table)", cd.weight, unit="g"),
        ]

    def notes(self, p: dict[str, Any]) -> list[str]:
        cd = SIZES[p["size"]]
        return [
            f"Seated: the three contact lobes sit on the groove diameter d2 = "
            f"{_fmt(cd.d2)} mm, centred on the origin with the shaft axis along Z.",
            f"Flat faces at z = 0 and z = s = {_fmt(cd.s)} mm; opening towards +Y, "
            f"a = {_fmt(cd.a)} mm between the jaw tips.",
            f"Outer contour on d3 = {_fmt(cd.d3)} mm, the standard's maximum seated "
            "diameter (catalogue free diameters are slightly smaller).",
            "One state only: an E-clip flexes only while it is pushed on and sits "
            "in the groove in its free shape.",
            "DIN 6799 fixes d2, a, d3 and s; the relief cut-outs, lobe and jaw "
            "shapes and fillets are modeled to the proportions of the standard's figure.",
        ]

    def build(self, p: dict[str, Any]) -> Part:
        part = _clip(p["size"]).solid()
        part.label = self.designation(p)
        return part


_CACHE: dict[str, EClip] = {}


def _clip(size: str) -> EClip:
    if size not in _CACHE:
        _CACHE[size] = EClip(SIZES[size])
    return _CACHE[size]

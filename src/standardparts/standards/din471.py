"""DIN 471 retaining rings (circlips) for shafts, regular series."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from OCP.TopoDS import TopoDS
from build123d import (
    Edge,
    Face,
    Part,
    Plane,
    Pos,
    Rot,
    Vector,
    Wire,
    extrude,
    mirror,
)

from .base import Dimension, Option, Parameter, ParameterError, Standard
from .din471_data import SIZES, RingData

STATES = {
    "free": "Free (as supplied, inner dia. d3)",
    "installed": "Installed (in the groove, inner dia. d2)",
}

# Proportions the standard leaves to the manufacturer.
END_WIDTH = 0.6        # radial width at the lug root, as a fraction of b
HOLE_SPACING = 1.1     # angular offset of the lug centre, in lug half-angles
END_TRIM = 0.85        # how far the lug runs past its centre, in half-angles


def _fmt(x: float) -> str:
    return f"{x:g}"


def u(psi: float) -> Vector:
    """Unit vector at polar angle psi, measured from -Y towards +X.

    psi = 0 is the back of the ring (opposite the opening), psi = pi the
    middle of the opening at +Y.
    """
    return Vector(math.sin(psi), -math.cos(psi), 0)


def _fan(psi0: float, psi1: float, radius: float) -> Face:
    """Pie slice from the origin covering polar angles psi0..psi1."""
    n = max(2, math.ceil((psi1 - psi0) / math.radians(20)))
    pts = [Vector(0, 0, 0)] + [
        u(psi0 + (psi1 - psi0) * i / n) * radius for i in range(n + 1)
    ]
    return Face(Wire.make_polygon(pts, close=True))


def _facing_up(face: Face) -> Face:
    """The same face with its normal along +Z (mirroring and wire order can
    flip it, and faces with opposite normals do not merge in a 2D union)."""
    if face.normal_at().Z > 0:
        return face
    return Face(TopoDS.Face(face.wrapped.Reversed()))


def _disk(center: Vector, radius: float) -> Face:
    return Pos(center) * Face(Wire(Edge.make_circle(radius)))


@dataclass(frozen=True)
class RingLayout:
    """Angles and radii of one state of the ring."""

    r_in: float      # inner radius of the body
    phi: float       # body runs over polar angles -phi..phi
    gap: float       # smallest distance between the two lugs


class Circlip:
    """Plan-view geometry of a DIN 471 ring in either state.

    The lug is drawn once, in the installed state with its root on the polar
    line psi = 0 (inner radius d2 / 2). Both states use that same lug,
    rotated and moved as a rigid body onto the end of the tapered body. The
    body's middle fibre keeps its length when the ring is opened from d3 to d2.
    """

    def __init__(self, rd: RingData):
        self.rd = rd
        a, b = rd.a_max, rd.b
        self.w_end = END_WIDTH * b
        self.r_inst = rd.d2 / 2
        self.r_free = rd.d3 / 2
        self.lug = self._lug_at_root()
        self.free_gap = 0.08 * rd.d3 + 0.5 * rd.d5_min
        phi_free = self._solve_phi(self.free_gap)
        w_mid = (b + self.w_end) / 4  # half the mean radial width
        phi_inst = phi_free * (self.r_free + w_mid) / (self.r_inst + w_mid)
        self.free = RingLayout(self.r_free, phi_free, self.free_gap)
        self.installed = RingLayout(
            self.r_inst, phi_inst, 2 * self._lug_min_x(self.r_inst, phi_inst)
        )

    # -- lug ------------------------------------------------------------
    def _lug_at_root(self) -> Face:
        rd = self.rd
        rr, a = self.r_inst, rd.a_max
        rc = rr + a / 2
        half = math.asin((a / 2) / rc)        # half-angle the lug disk spans
        psi_c = HOLE_SPACING * half
        psi_end = psi_c + END_TRIM * half
        center = u(psi_c) * rc
        big = 2 * (rr + a)

        pieces = [
            _disk(Vector(), rr + self.w_end) & _fan(0, psi_end, big),
            _disk(Vector(), rc) & _fan(psi_c, psi_end, big),
            _disk(center, a / 2),
        ]
        # Ramp from the body's outer edge up to the round lug, tangent to it.
        p_out = u(0) * (rr + self.w_end)
        to_p = p_out - center
        dist = to_p.length
        if dist > 1.02 * a / 2:
            gamma = math.acos((a / 2) / dist)
            base = math.atan2(to_p.Y, to_p.X)
            cands = [
                center + Vector(math.cos(base + s * gamma), math.sin(base + s * gamma)) * (a / 2)
                for s in (1, -1)
            ]
            tangent = max(cands, key=lambda p: p.length)
            if math.atan2(tangent.X, -tangent.Y) > 1e-6:  # polar angle > 0
                pieces.append(Face(Wire.make_polygon([Vector(), p_out, tangent, center], close=True)))

        lug = pieces[0]
        for piece in pieces[1:]:
            lug = lug + piece
        lug = lug & _fan(0, psi_end, big)
        lug = lug - _disk(Vector(), rr) - _disk(center, rd.d5_min / 2)
        faces = lug.faces()
        if len(faces) != 1:
            raise RuntimeError(f"lug construction failed for DIN 471 - {rd.size}")
        return faces[0]

    def _place_lug(self, r_in: float, phi: float) -> Face:
        """Move the root lug onto the body end at angle phi, inner radius r_in."""
        shift = u(phi) * (r_in - self.r_inst)
        return Pos(shift) * (Rot(0, 0, math.degrees(phi)) * self.lug)

    def _lug_min_x(self, r_in: float, phi: float) -> float:
        return self._place_lug(r_in, phi).bounding_box(optimal=True).min.X

    def _solve_phi(self, gap: float) -> float:
        """Body angle in the free state that leaves `gap` between the lugs."""
        lo, hi = math.radians(60), math.pi
        for _ in range(40):
            mid = (lo + hi) / 2
            if self._lug_min_x(self.r_free, mid) > gap / 2:
                lo = mid
            else:
                hi = mid
        return lo

    # -- ring -----------------------------------------------------------
    def outline(self, state: str) -> list[Face]:
        """Body and the two lugs in plan view (they share their root edges)."""
        lay = self.free if state == "free" else self.installed
        r, phi, b = lay.r_in, lay.phi, self.rd.b
        r_end = r + self.w_end
        edges = [
            Edge.make_three_point_arc(u(-phi) * r, u(0) * r, u(phi) * r),
            Edge.make_line(u(phi) * r, u(phi) * r_end),
            Edge.make_three_point_arc(u(phi) * r_end, u(0) * (r + b), u(-phi) * r_end),
            Edge.make_line(u(-phi) * r_end, u(-phi) * r),
        ]
        lug = self._place_lug(r, phi)
        return [Face(Wire(edges)), lug, mirror(lug, about=Plane.YZ).faces()[0]]

    def plan(self, state: str) -> Face:
        """Single plan-view face of the whole ring, normal +Z."""
        faces = [_facing_up(f) for f in self.outline(state)]
        ring = faces[0].fuse(*faces[1:]).clean().faces()
        if len(ring) != 1:
            raise RuntimeError(f"ring outline failed for DIN 471 - {self.rd.size}")
        return ring[0]

    def solid(self, state: str) -> Part:
        """Ring with its flat faces at z = 0 and z = s, axis along Z."""
        ring = extrude(self.plan(state), amount=self.rd.s)
        if not ring.is_valid or len(ring.solids()) != 1:
            raise RuntimeError(f"ring solid failed for DIN 471 - {self.rd.size}")
        return ring


class DIN471(Standard):
    id = "din471"
    title = "DIN 471"
    summary = "Retaining rings (circlips) for shafts, regular series, 3 to 300 mm"
    category = "Retaining rings"
    source = "Values in mm, from DIN 471 (regular series)."

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="size",
                label="Shaft diameter d1",
                kind="select",
                default="20",
                options=[Option(k, f"{k} mm  (s = {_fmt(r.s)})") for k, r in SIZES.items()],
            ),
            Parameter(
                name="state",
                label="State",
                kind="select",
                default="installed",
                options=[Option(k, v) for k, v in STATES.items()],
                help="Installed: the ring opened onto the groove diameter d2, "
                "centred on the shaft axis. Free: the ring as manufactured.",
            ),
        ]

    def validate(self, raw: dict[str, Any]) -> dict[str, Any]:
        size = str(raw.get("size", "20"))
        if size.endswith(".0"):
            size = size[:-2]
        if size not in SIZES:
            raise ParameterError(
                f"unknown shaft diameter {size!r}; choose one of {', '.join(SIZES)}"
            )
        state = str(raw.get("state", "installed"))
        if state not in STATES:
            raise ParameterError(f"state must be one of {', '.join(STATES)}")
        return {"size": size, "state": state}

    def designation(self, p: dict[str, Any]) -> str:
        rd = SIZES[p["size"]]
        return f"DIN 471 - {rd.size} x {_fmt(rd.s)}"

    def file_stem(self, p: dict[str, Any]) -> str:
        rd = SIZES[p["size"]]
        return f"DIN471_{rd.size}x{_fmt(rd.s)}_{p['state']}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        rd = SIZES[p["size"]]
        clip = _circlip(p["size"])
        return [
            Dimension("d1", "Shaft diameter", rd.d1),
            Dimension("s", "Ring thickness", rd.s),
            Dimension("d3", "Inner dia. (free)", rd.d3),
            Dimension("a max", "Lug height", rd.a_max),
            Dimension("b ≈", "Section width", rd.b),
            Dimension("d5 min", "Plier hole", rd.d5_min),
            Dimension("d2", "Groove diameter", rd.d2),
            Dimension("m H13", "Groove width", rd.m),
            Dimension("t", "Groove depth", rd.t),
            Dimension("n min", "Groove to shaft end", rd.n_min),
            Dimension("d4", "Clearance dia. (installed)", rd.d4),
            Dimension("gap free", "Lug gap, free (model)", round(clip.free.gap, 2)),
            Dimension("gap inst.", "Lug gap, installed (model)", round(clip.installed.gap, 2)),
            Dimension("mass", "Approx. mass (table)", rd.weight, unit="g"),
        ]

    def notes(self, p: dict[str, Any]) -> list[str]:
        rd = SIZES[p["size"]]
        out = []
        if p["state"] == "installed":
            out.append(
                f"Installed: inner edge on the groove diameter d2 = {_fmt(rd.d2)} mm, "
                "ring centred on the origin with the shaft axis along Z."
            )
        else:
            out.append(f"Free: inner diameter d3 = {_fmt(rd.d3)} mm, as supplied.")
        out.append(f"Flat faces at z = 0 and z = s = {_fmt(rd.s)} mm; opening towards +Y.")
        out.append(
            "DIN 471 fixes d3, s, a, b and d5; the lug outline, the section taper "
            "and the free gap are modeled to typical proportions."
        )
        return out

    def build(self, p: dict[str, Any]) -> Part:
        part = _circlip(p["size"]).solid(p["state"])
        part.label = self.designation(p) + f" ({p['state']})"
        return part


_CACHE: dict[str, Circlip] = {}


def _circlip(size: str) -> Circlip:
    if size not in _CACHE:
        _CACHE[size] = Circlip(SIZES[size])
    return _CACHE[size]

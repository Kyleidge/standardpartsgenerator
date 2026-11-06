"""DIN 472 retaining rings (circlips) for bores, regular series."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from build123d import Edge, Face, Part, Plane, Pos, Rot, Vector, Wire, extrude, mirror

from .base import Dimension, Option, Parameter, ParameterError, Standard
from .din471 import _disk, _facing_up, _fan, u
from .din472_data import SIZES, RingData

STATES = {
    "free": "Free (as supplied, outer dia. d3)",
    "installed": "Installed (in the groove, outer dia. d2)",
}

# Proportions the standard leaves to the manufacturer.
END_WIDTH = 0.6        # radial width at the lug root, as a fraction of b
HOLE_SPACING = 1.1     # angular offset of the lug centre, in lug half-angles
END_TRIM = 0.85        # how far the lug runs past its centre, in half-angles
BORE_GAP = 0.5         # lug gap left when squeezed to d1, in plier hole diameters


def _fmt(x: float) -> str:
    return f"{x:g}"


@dataclass(frozen=True)
class RingLayout:
    """Angles and radii of one state of the ring."""

    r_out: float     # outer radius of the body
    phi: float       # body runs over polar angles -phi..phi
    gap: float       # smallest distance between the two lugs


class Circlip:
    """Plan-view geometry of a DIN 472 ring.

    The body is a band whose outer edge is a circle (d3 free, d2 installed)
    and whose inner edge tapers from b at the back to END_WIDTH * b at the
    lugs. The lugs point inwards. A lug is drawn once, in the installed state
    with its root on the polar line psi = 0 (outer radius d2 / 2), and moved
    as a rigid body onto the end of the body for any state. The body's middle
    fibre keeps its length when the ring is squeezed, so the lug gap closes
    from free to installed, and closes further when the ring is squeezed to
    d1 to pass through the bore. The free shape is chosen so that the gap at
    d1 is still BORE_GAP * d5; the gaps of both modeled states follow.
    """

    def __init__(self, rd: RingData):
        self.rd = rd
        b = rd.b
        self.w_end = END_WIDTH * b
        self.w_mid = (b + self.w_end) / 4   # half the mean radial width
        self.r_inst = rd.d2 / 2
        self.r_free = rd.d3 / 2
        self.r_bore = rd.d1 / 2
        self.lug = self._lug_at_root()
        self.bore_gap = BORE_GAP * rd.d5_min
        phi_bore = self._solve_phi(self.r_bore, self.bore_gap)
        self.fibre = phi_bore * (self.r_bore - self.w_mid)  # half length / 1 rad
        self.free = self._layout(self.r_free)
        self.installed = self._layout(self.r_inst)

    def _layout(self, r_out: float) -> RingLayout:
        phi = self.fibre / (r_out - self.w_mid)
        return RingLayout(r_out, phi, 2 * self._lug_min_x(r_out, phi))

    # -- lug ------------------------------------------------------------
    def _lug_at_root(self) -> Face:
        rd = self.rd
        R, a = self.r_inst, rd.a_max
        rc = R - a / 2
        half = math.asin((a / 2) / rc)        # half-angle the lug disk spans
        psi_c = HOLE_SPACING * half
        psi_end = psi_c + END_TRIM * half
        center = u(psi_c) * rc
        big = 2 * R
        origin = Vector()

        pieces = [
            # the body's end band, continued past the lug centre
            (_disk(origin, R) - _disk(origin, R - self.w_end)) & _fan(0, psi_end, big),
            # square outer corner past the lug centre
            (_disk(origin, R) - _disk(origin, rc)) & _fan(psi_c, psi_end, big),
            _disk(center, a / 2),
        ]
        # Ramp from the body's inner edge down to the round lug, tangent to it.
        p_in = u(0) * (R - self.w_end)
        to_p = p_in - center
        dist = to_p.length
        if dist > 1.02 * a / 2:
            gamma = math.acos((a / 2) / dist)
            base = math.atan2(to_p.Y, to_p.X)
            cands = [
                center + Vector(math.cos(base + s * gamma), math.sin(base + s * gamma)) * (a / 2)
                for s in (1, -1)
            ]
            tangent = min(cands, key=lambda p: p.length)
            if math.atan2(tangent.X, -tangent.Y) > 1e-6:  # polar angle > 0
                r_far = 1.05 * R / math.cos(psi_c / 2)   # outside R, clipped below
                pieces.append(Face(Wire.make_polygon(
                    [p_in, tangent, center, u(psi_c) * r_far, u(0) * r_far], close=True
                )))

        pieces = [_facing_up(f) for f in pieces]
        lug = pieces[0]
        for piece in pieces[1:]:
            lug = lug + piece
        lug = lug & (_disk(origin, R) & _fan(0, psi_end, big))
        lug = lug - _disk(center, rd.d5_min / 2)
        faces = lug.faces()
        if len(faces) != 1:
            raise RuntimeError(f"lug construction failed for DIN 472 - {rd.size}")
        return faces[0]

    def _place_lug(self, r_out: float, phi: float) -> Face:
        """Move the root lug onto the body end at angle phi, outer radius r_out."""
        shift = u(phi) * (r_out - self.r_inst)
        return Pos(shift) * (Rot(0, 0, math.degrees(phi)) * self.lug)

    def _lug_min_x(self, r_out: float, phi: float) -> float:
        return self._place_lug(r_out, phi).bounding_box(optimal=True).min.X

    def _solve_phi(self, r_out: float, gap: float) -> float:
        """Body angle at outer radius r_out that leaves `gap` between the lugs."""
        lo, hi = math.radians(60), math.pi
        for _ in range(40):
            mid = (lo + hi) / 2
            if self._lug_min_x(r_out, mid) > gap / 2:
                lo = mid
            else:
                hi = mid
        return lo

    # -- ring -----------------------------------------------------------
    def outline(self, state: str) -> list[Face]:
        """Body and the two lugs in plan view (they share their root edges)."""
        lay = self.free if state == "free" else self.installed
        R, phi, b = lay.r_out, lay.phi, self.rd.b
        r_end = R - self.w_end
        edges = [
            Edge.make_three_point_arc(u(-phi) * R, u(0) * R, u(phi) * R),
            Edge.make_line(u(phi) * R, u(phi) * r_end),
            Edge.make_three_point_arc(u(phi) * r_end, u(0) * (R - b), u(-phi) * r_end),
            Edge.make_line(u(-phi) * r_end, u(-phi) * R),
        ]
        lug = self._place_lug(R, phi)
        return [Face(Wire(edges)), lug, mirror(lug, about=Plane.YZ).faces()[0]]

    def plan(self, state: str) -> Face:
        """Single plan-view face of the whole ring, normal +Z."""
        faces = [_facing_up(f) for f in self.outline(state)]
        ring = faces[0].fuse(*faces[1:]).clean().faces()
        if len(ring) != 1:
            raise RuntimeError(f"ring outline failed for DIN 472 - {self.rd.size}")
        return ring[0]

    def solid(self, state: str) -> Part:
        """Ring with its flat faces at z = 0 and z = s, axis along Z."""
        ring = extrude(self.plan(state), amount=self.rd.s)
        if not ring.is_valid or len(ring.solids()) != 1:
            raise RuntimeError(f"ring solid failed for DIN 472 - {self.rd.size}")
        return ring


class DIN472(Standard):
    id = "din472"
    title = "DIN 472"
    summary = "Retaining rings (circlips) for bores, regular series, 8 to 300 mm"
    category = "Retaining rings"
    source = "Values in mm, from DIN 472 (regular series)."

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="size",
                label="Bore diameter d1",
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
                help="Installed: the ring squeezed into the groove diameter d2, "
                "centred on the bore axis. Free: the ring as manufactured.",
            ),
        ]

    def validate(self, raw: dict[str, Any]) -> dict[str, Any]:
        size = str(raw.get("size", "20"))
        if size.endswith(".0"):
            size = size[:-2]
        if size not in SIZES:
            raise ParameterError(
                f"unknown bore diameter {size!r}; choose one of {', '.join(SIZES)}"
            )
        state = str(raw.get("state", "installed"))
        if state not in STATES:
            raise ParameterError(f"state must be one of {', '.join(STATES)}")
        return {"size": size, "state": state}

    def designation(self, p: dict[str, Any]) -> str:
        rd = SIZES[p["size"]]
        return f"DIN 472 - {rd.size} x {_fmt(rd.s)}"

    def file_stem(self, p: dict[str, Any]) -> str:
        rd = SIZES[p["size"]]
        return f"DIN472_{rd.size}x{_fmt(rd.s)}_{p['state']}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        rd = SIZES[p["size"]]
        clip = _circlip(p["size"])
        return [
            Dimension("d1", "Bore diameter", rd.d1),
            Dimension("s", "Ring thickness", rd.s),
            Dimension("d3", "Outer dia. (free)", rd.d3),
            Dimension("a max", "Lug height", rd.a_max),
            Dimension("b ≈", "Section width", rd.b),
            Dimension("d5 min", "Plier hole", rd.d5_min),
            Dimension("d2", "Groove diameter", rd.d2),
            Dimension("m H13", "Groove width", rd.m),
            Dimension("t", "Groove depth", rd.t),
            Dimension("n min", "Groove to bore end", rd.n_min),
            Dimension("d4", "Clearance dia. (installed)", rd.d4),
            Dimension("gap free", "Lug gap, free (model)", round(clip.free.gap, 2)),
            Dimension("gap inst.", "Lug gap, installed (model)", round(clip.installed.gap, 2)),
            Dimension("gap at d1", "Lug gap, squeezed to d1 (model)", round(clip.bore_gap, 2)),
            Dimension("mass", "Approx. mass (table)", rd.weight, unit="g"),
        ]

    def notes(self, p: dict[str, Any]) -> list[str]:
        rd = SIZES[p["size"]]
        out = []
        if p["state"] == "installed":
            out.append(
                f"Installed: outer edge on the groove diameter d2 = {_fmt(rd.d2)} mm, "
                "ring centred on the origin with the bore axis along Z."
            )
        else:
            out.append(f"Free: outer diameter d3 = {_fmt(rd.d3)} mm, as supplied.")
        out.append(f"Flat faces at z = 0 and z = s = {_fmt(rd.s)} mm; opening towards +Y.")
        out.append(
            "DIN 472 fixes d3, s, a, b and d5; the lug outline, the section taper "
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

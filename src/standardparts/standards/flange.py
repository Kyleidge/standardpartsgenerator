"""Shared geometry for hexagon parts with a plain (non-serrated) flange:
ISO 4162 flange bolts and ISO 4161 flange nuts.

The flange is revolved, the hexagon is a prism fused on top of it.

Flange profile, in (radius, z) with the bearing face at z = 0:

* The bearing face is flat out to where the rim round starts.
* The top of the flange is a cone falling outwards at `angle` degrees to the
  bearing plane (ISO 4161 / ISO 4162: 15 deg to 25 deg). It passes through
  thickness c at diameter dw, as the standards measure c "at dw min".
* The rim is a round tangent to both the bearing plane and the cone, whose
  outermost point is at dc / 2. Where that round would start inside dw (thick
  flanges with little rim, e.g. ISO 4162 M16), the rim is instead a quarter
  round of radius (dc - dw) / 2 at the bearing face, a short cylinder at dc
  and a sharp edge to the cone. ISO 4161 and ISO 4162 leave the edge contour
  to the manufacturer; the drawings show it rounded.
* Inside the hexagon the profile carries on as a round core of radius
  r_core up to z_core, so that the hexagon prism, whose bottom face is
  buried in the flange, overlaps the revolved part without any coincident
  faces (coincident faces make OCCT fuses fail silently).

`fuse_hex` checks the fuse against an analytic volume: the hexagon's overlap
with the revolved part is integrated exactly over the hexagon in polar
coordinates, so a dropped solid or a wrong boolean is caught.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from build123d import Part

from ..geometry import SQRT3, ProfileItem


@dataclass(frozen=True)
class Flange:
    dc: float            # outer flange diameter (dc max)
    dw: float            # diameter at which the flange is c thick (dw min)
    c: float             # flange thickness at dw (c min)
    angle: float = 20.0  # top cone angle to the bearing plane, degrees

    @property
    def tan(self) -> float:
        return math.tan(math.radians(self.angle))

    def height(self, r: float) -> float:
        """Height of the top cone at radius r."""
        return self.c + (self.dw / 2 - r) * self.tan

    @property
    def edge_height(self) -> float:
        """Height of the (extended) cone at dc / 2."""
        return self.height(self.dc / 2)

    @property
    def tangent_rim_radius(self) -> float:
        """Radius of the round tangent to the bearing plane and the cone with
        its outermost point at dc / 2."""
        a = math.radians(self.angle)
        return self.edge_height * math.cos(a) / (1 + math.cos(a) - math.sin(a))

    @property
    def rim_tangent(self) -> bool:
        """True if the tangent rim round fits outside dw. Otherwise the rim is
        a quarter round of radius (dc - dw) / 2 at the bearing face, a short
        cylinder at dc and a sharp edge to the cone."""
        return self.dc - 2 * self.tangent_rim_radius >= self.dw

    @property
    def rim_radius(self) -> float:
        if self.rim_tangent:
            return self.tangent_rim_radius
        return (self.dc - self.dw) / 2

    @property
    def bearing_dia(self) -> float:
        """Diameter where the flat bearing face ends and the rim round starts."""
        return self.dc - 2 * self.rim_radius

    @property
    def rim_top(self) -> tuple[float, float]:
        """Point where the rim runs into the top cone."""
        if not self.rim_tangent:
            return (self.dc / 2, self.edge_height)
        a = math.radians(self.angle)
        rho = self.rim_radius
        return (self.dc / 2 - rho + rho * math.sin(a), rho + rho * math.cos(a))

    def check(self) -> None:
        if self.edge_height <= 0 or self.dc <= self.dw:
            raise ValueError("flange cone reaches the bearing face inside dc")

    def rim(self) -> list[ProfileItem]:
        """Rim profile from the outer end of the bearing face to rim_top."""
        rho = self.rim_radius
        r_out = self.dc / 2
        if self.rim_tangent:
            return [(r_out - rho, 0.0), ("arc", (r_out, rho), self.rim_top)]
        q = rho / math.sqrt(2)
        return [
            (r_out - rho, 0.0),
            ("arc", (r_out - rho + q, rho - q), (r_out, rho)),
            self.rim_top,
        ]

    def profile(self, r_core: float, z_core: float) -> list[ProfileItem]:
        """Profile from the outer end of the flat bearing face around the rim,
        up the cone to r_core, up the core to z_core and back to the axis."""
        if not 0 < r_core < self.rim_top[0]:
            raise ValueError("core radius outside the flange cone")
        if z_core <= self.height(r_core):
            raise ValueError("core top below the flange cone")
        return [
            *self.rim(),
            (r_core, self.height(r_core)),
            (r_core, z_core),
            (0.0, z_core),
        ]


def hex_overlap_volume(s: float, z_hex: float, flange: Flange, r_core: float,
                       z_core: float, steps: int = 64) -> float:
    """Volume shared by a hexagon prism (width s across flats, bottom face at
    z_hex, top above z_core) and the revolved flange-and-core solid.

    Above the hexagon's cross section the revolved part reaches z_core for
    r < r_core and the cone height for r >= r_core; both must be above
    z_hex over the whole hexagon. The hexagon is split into 12 right
    triangles; the radial integral is exact, the angular one Simpson's rule
    (smooth integrand).
    """
    a = s / 2
    e2 = s / SQRT3
    if flange.height(e2) <= z_hex or r_core >= a:
        raise ValueError("hexagon bottom is not buried in the flange")
    t = flange.tan
    a0 = flange.c + flange.dw / 2 * flange.tan - z_hex  # cone height - z_hex at r = 0

    def g(r: float) -> float:  # integral of (cone height - z_hex) * r dr from 0
        return a0 * r * r / 2 - t * r**3 / 3

    inner = (z_core - z_hex) * r_core**2 / 2 - g(r_core)

    def f(theta: float) -> float:
        return inner + g(a / math.cos(theta))

    n = steps + steps % 2
    h = (math.pi / 6) / n
    total = f(0.0) + f(math.pi / 6)
    for i in range(1, n):
        total += (4 if i % 2 else 2) * f(i * h)
    return 12 * total * h / 3


def fuse_hex(body: Part, hexagon: Part, overlap: float, what: str) -> Part | None:
    """Fuse the hexagon onto the revolved body; return None if the result is
    not one valid solid of the expected volume."""
    try:
        fused = body + hexagon
    except Exception:  # noqa: BLE001 - any kernel failure means "retry"
        return None
    expected = body.volume + hexagon.volume - overlap
    if (
        fused is not None
        and len(fused.solids()) == 1
        and abs(fused.volume - expected) < 1e-4 * hexagon.volume
        and fused.is_valid
    ):
        return fused
    return None

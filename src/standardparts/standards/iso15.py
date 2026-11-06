"""ISO 15 radial deep groove ball bearings, series 60, 62 and 63."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from build123d import Part, Pos, Sphere

from ..geometry import ProfileItem, revolve_profile
from .base import Dimension, Option, Parameter, ParameterError, Standard
from .iso15_data import BEARINGS, BearingData

DETAILS = {
    "envelope": "Envelope (one solid: d, D, B and the r_s rounds)",
    "faces": "Faces (one solid with the ring and shield faces of a 2Z bearing)",
    "rings": "Rings and balls (assembly: 2 rings, 2 shields, balls)",
}

SQ2 = 1 / math.sqrt(2)


def _fmt(x: float) -> str:
    return f"{x:g}"


def _round(corner: tuple[float, float], r: float, dr: int, dz: int):
    """Arc rounding a 90 degree corner of the (radius, z) profile.

    (dr, dz) points from the corner into the material, e.g. (+1, +1) for the
    corner at the bore on the bottom face. Returns (on_face, mid, on_cyl):
    the arc's end point on the end face (z = const), its midpoint, and its
    end point on the cylinder (r = const).
    """
    rc, zc = corner[0] + dr * r, corner[1] + dz * r
    mid = (rc - dr * r * SQ2, zc - dz * r * SQ2)
    on_face = (rc, corner[1])       # on the end face (z = const)
    on_cyl = (corner[0], zc)        # on the cylinder (r = const)
    return on_face, mid, on_cyl


@dataclass(frozen=True)
class Internals:
    """Proportions of the simplified internal design.

    Only d, D, B and r_s are ISO 15 values; z and Dw are NSK's. The rest
    follows typical deep groove ball bearing proportions, scaled with the
    ball diameter, and is not standardised.
    """

    r_pitch: float     # ball centre radius, (d + D) / 4
    r_ball: float
    ri_sh: float       # inner ring shoulder (land) radius
    ro_sh: float       # outer ring shoulder (land) radius
    ro_rec: float      # outer ring shield recess radius
    ri_bot: float      # inner raceway bottom radius
    ro_bot: float      # outer raceway bottom radius
    zi: float          # half width of the inner raceway groove at the land
    zo: float          # half width of the outer raceway groove at the land
    t_shield: float    # shield thickness
    e_shield: float    # shield outer face below the ring faces
    k_step: float      # depth of the shield seat step in the outer ring
    rs_in: float       # shield inner radius
    rs_out: float      # shield outer radius

    @classmethod
    def of(cls, bd: BearingData) -> Internals:
        Dw = bd.Dw
        r_pitch = bd.dm / 2
        play = 0.005 * Dw                  # radial internal clearance
        rg = 0.52 * Dw                     # raceway groove radius
        ri_sh = r_pitch - 0.3 * Dw
        ro_sh = r_pitch + 0.3 * Dw
        ri_bot = r_pitch - Dw / 2 - play / 2
        ro_bot = r_pitch + Dw / 2 + play / 2
        ci, co = ri_bot + rg, ro_bot - rg  # groove arc centres
        zi = math.sqrt(rg**2 - (ci - ri_sh) ** 2)
        zo = math.sqrt(rg**2 - (ro_sh - co) ** 2)
        t_shield = max(0.2, 0.02 * bd.B)
        e_shield = max(0.1, 0.01 * bd.B)
        gap = 0.1 * t_shield
        ro_rec = ro_sh + 0.15 * Dw
        return cls(
            r_pitch=r_pitch,
            r_ball=Dw / 2,
            ri_sh=ri_sh,
            ro_sh=ro_sh,
            ro_rec=ro_rec,
            ri_bot=ri_bot,
            ro_bot=ro_bot,
            zi=zi,
            zo=zo,
            t_shield=t_shield,
            e_shield=e_shield,
            k_step=e_shield + t_shield + gap,
            rs_in=ri_sh + 0.04 * Dw,
            rs_out=ro_rec - 0.02 * Dw,
        )


def _bore_side(bd: BearingData, r_land: float) -> tuple[list[ProfileItem], list[ProfileItem]]:
    """Bottom and top halves of a profile's bore edge with the r_s rounds.

    Returns (start, close): `start` begins on the bottom face next to the
    bore and runs out to r_land; `close` runs from (r_land, B/2) back
    across the top face, down the bore and ends at the start point.
    """
    hb, rs, ri = bd.B / 2, bd.rs_min, bd.d / 2
    bot_face, bot_mid, bot_cyl = _round((ri, -hb), rs, +1, +1)
    top_face, top_mid, top_cyl = _round((ri, hb), rs, +1, -1)
    start: list[ProfileItem] = [bot_face, (r_land, -hb)]
    close: list[ProfileItem] = [
        (r_land, hb),
        top_face,
        ("arc", top_mid, top_cyl),
        bot_cyl,
        ("arc", bot_mid, bot_face),
    ]
    return start, close


def _od_side(bd: BearingData, r_land: float) -> list[ProfileItem]:
    """From (r_land, -B/2) out along the bottom face, up the outside
    diameter with both r_s rounds, and back in along the top face to r_land."""
    hb, rs, ro = bd.B / 2, bd.rs_min, bd.D / 2
    bot_face, bot_mid, bot_cyl = _round((ro, -hb), rs, -1, +1)
    top_face, top_mid, top_cyl = _round((ro, hb), rs, -1, -1)
    return [
        (r_land, -hb),
        bot_face,
        ("arc", bot_mid, bot_cyl),
        top_cyl,
        ("arc", top_mid, top_face),
        (r_land, hb),
    ]


def envelope(bd: BearingData) -> Part:
    """Annulus d..D, width B, with the four r_s edge rounds."""
    rs = bd.rs_min
    start, close = _bore_side(bd, bd.d / 2 + rs)
    od = _od_side(bd, bd.D / 2 - rs)
    # Land radii sit on the round ends, so the extra points coincide with
    # their neighbours and revolve_profile drops the zero-length segments.
    return revolve_profile([*start, *od, *close])


def faces_solid(bd: BearingData, it: Internals) -> Part:
    """One solid with the visible faces of a shielded (2Z) bearing: inner
    ring face, a narrow gap, the recessed shield, then the outer ring face."""
    hb = bd.B / 2
    z_sh = hb - it.e_shield                   # shield outer face
    z_gap = hb - it.e_shield - it.t_shield    # bottom of the gap at the inner ring
    start, close = _bore_side(bd, it.ri_sh)
    od = _od_side(bd, it.ro_rec)
    bottom = [
        (it.ri_sh, -z_gap),
        (it.rs_in, -z_gap),
        (it.rs_in, -z_sh),
        (it.ro_rec, -z_sh),
    ]
    top = [(r, -z) for r, z in reversed(bottom)]
    return revolve_profile([*start, *bottom, *od, *top, *close])


def inner_ring(bd: BearingData, it: Internals) -> Part:
    start, close = _bore_side(bd, it.ri_sh)
    groove = [(it.ri_sh, -it.zi), ("arc", (it.ri_bot, 0.0), (it.ri_sh, it.zi))]
    return revolve_profile([*start, *groove, *close])


def outer_ring(bd: BearingData, it: Internals) -> Part:
    hb = bd.B / 2
    zs = hb - it.k_step
    inside = [
        (it.ro_rec, zs),
        (it.ro_sh, zs),
        (it.ro_sh, it.zo),
        ("arc", (it.ro_bot, 0.0), (it.ro_sh, -it.zo)),
        (it.ro_sh, -zs),
        (it.ro_rec, -zs),
    ]
    return revolve_profile([*_od_side(bd, it.ro_rec), *inside])


def shield(bd: BearingData, it: Internals, side: int) -> Part:
    z_out = side * (bd.B / 2 - it.e_shield)
    z_in = side * (bd.B / 2 - it.e_shield - it.t_shield)
    lo, hi = sorted((z_in, z_out))
    return revolve_profile([(it.rs_in, lo), (it.rs_out, lo), (it.rs_out, hi), (it.rs_in, hi)])


def balls(bd: BearingData, it: Internals) -> list[Part]:
    proto = Sphere(it.r_ball)
    out = []
    for i in range(bd.z):
        a = 2 * math.pi * i / bd.z
        ball = Pos(it.r_pitch * math.cos(a), it.r_pitch * math.sin(a), 0) * proto
        ball.label = f"ball {i + 1}"
        out.append(ball)
    return out


def assembly(bd: BearingData, it: Internals) -> Part:
    ir, ors = inner_ring(bd, it), outer_ring(bd, it)
    ir.label, ors.label = "inner ring", "outer ring"
    top, bottom = shield(bd, it, +1), shield(bd, it, -1)
    top.label, bottom.label = "shield +Z", "shield -Z"
    return Part(children=[ir, ors, top, bottom, *balls(bd, it)])


def build_bearing(bd: BearingData, detail: str) -> Part:
    """Build the bearing.

    Coordinate system: the bearing axis is Z, the bearing is centred on the
    origin and its faces lie at z = -B/2 and z = +B/2.
    """
    if detail not in DETAILS:
        raise ParameterError(f"unknown detail {detail!r}")
    if detail == "envelope":
        part = envelope(bd)
    else:
        it = Internals.of(bd)
        part = faces_solid(bd, it) if detail == "faces" else assembly(bd, it)
    want = bd.z + 4 if detail == "rings" else 1
    if not part.is_valid or len(part.solids()) != want:
        raise RuntimeError(f"bearing model failed for {bd.designation} ({detail})")
    return part


def envelope_volume(bd: BearingData) -> float:
    """Exact volume of the envelope model (used by the tests)."""
    r = bd.rs_min
    spandrel = (1 - math.pi / 4) * r**2
    e = r * (10 - 3 * math.pi) / (3 * (4 - math.pi))  # spandrel centroid offset
    radii = 2 * (bd.D / 2 - e) + 2 * (bd.d / 2 + e)
    return math.pi / 4 * (bd.D**2 - bd.d**2) * bd.B - 2 * math.pi * spandrel * radii


class ISO15(Standard):
    id = "iso15"
    title = "ISO 15"
    summary = "Deep groove ball bearings, series 60, 62 and 63, bore 10 to 110 mm"
    category = "Bearings"
    source = "Values in mm, boundary dimensions from ISO 15 (chamfers ISO 582)."

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="size",
                label="Bearing",
                kind="select",
                default="6205",
                options=[
                    Option(k, f"{k} ({_fmt(bd.d)} × {_fmt(bd.D)} × {_fmt(bd.B)})")
                    for k, bd in BEARINGS.items()
                ],
            ),
            Parameter(
                name="detail",
                label="Detail",
                kind="select",
                default="envelope",
                options=[Option(k, v) for k, v in DETAILS.items()],
                help="Envelope and Faces are single solids. Rings and balls is "
                "an assembly of separate solids (no cage).",
            ),
        ]

    def validate(self, raw: dict[str, Any]) -> dict[str, Any]:
        size = str(raw.get("size", "6205")).strip()
        if size not in BEARINGS:
            raise ParameterError(f"unknown bearing {size!r}; choose one of {', '.join(BEARINGS)}")
        detail = str(raw.get("detail", "envelope")).strip().lower()
        if detail not in DETAILS:
            raise ParameterError(f"detail must be one of {', '.join(DETAILS)}")
        return {"size": size, "detail": detail}

    def designation(self, p: dict[str, Any]) -> str:
        return p["size"]

    def file_stem(self, p: dict[str, Any]) -> str:
        return f"ISO15_{p['size']}_{p['detail']}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        bd = BEARINGS[p["size"]]
        out = [
            Dimension("d", "Bore diameter", bd.d),
            Dimension("D", "Outside diameter", bd.D),
            Dimension("B", "Width", bd.B),
            Dimension("r_s min", "Chamfer dimension (ISO 582)", bd.rs_min),
            Dimension("series", "ISO 15 dimension series", bd.dimension_series, unit=""),
            Dimension("da min", "Shaft shoulder dia., min (NSK)", bd.da_min),
            Dimension("da max", "Shaft shoulder dia., max (NSK)", bd.da_max),
            Dimension("Da max", "Housing shoulder dia., max (NSK)", bd.Da_max),
            Dimension("ra max", "Shaft / housing fillet radius, max (NSK)", bd.ra_max),
            Dimension("mass", "Approx. mass, open bearing (NSK)", bd.mass, unit="kg"),
        ]
        if p["detail"] == "rings":
            out += [
                Dimension("z", "Number of balls (NSK, model)", bd.z, unit=""),
                Dimension("Dw", "Ball diameter (NSK, model)", bd.Dw),
                Dimension("dm", "Ball pitch diameter (model)", bd.dm),
            ]
        return out

    def notes(self, p: dict[str, Any]) -> list[str]:
        bd = BEARINGS[p["size"]]
        out = [
            f"Bearing axis along Z, centred on the origin, faces at z = ±{_fmt(bd.B / 2)} mm.",
            f"All four outer edges rounded with r = r_s min = {_fmt(bd.rs_min)} mm.",
        ]
        if p["detail"] == "envelope":
            out.append("Envelope: one solid with the boundary dimensions only.")
        elif p["detail"] == "faces":
            out.append(
                "Faces: one solid. The inner ring, the shield recess and the outer "
                "ring are drawn on both faces like a shielded (2Z) bearing; their "
                "radii are typical proportions, not standardised."
            )
        else:
            out.append(
                f"Assembly of {bd.z + 4} solids: inner ring, outer ring, two shields "
                f"and {bd.z} balls of {_fmt(bd.Dw)} mm (NSK's internal design). No "
                "cage. Raceways, lands and shields are typical proportions, not "
                "standardised."
            )
        return out

    def build(self, p: dict[str, Any]) -> Part:
        part = build_bearing(BEARINGS[p["size"]], p["detail"])
        part.label = f"{self.designation(p)} ({p['detail']})"
        return part

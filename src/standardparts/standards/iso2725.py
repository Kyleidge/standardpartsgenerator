"""ISO 2725-1 hand-operated square drive sockets (hex and bi-hex)."""

from __future__ import annotations

import math
from typing import Any

from build123d import Align, Cylinder, Part, Pos, RegularPolygon, Rot, extrude

from ..geometry import SQRT3, revolve_profile
from .base import Dimension, Option, Parameter, ParameterError, Standard
from .driving_squares import female_square_cutter
from .iso1174_data import SQUARES
from .iso2725_data import ALL_SIZES, COUNTERSINK_ANGLE, SOCKETS, SocketData

# Model choices (the figures of ISO 2725-1 are "only examples"):
OUTER_CHAMFER = 0.5      # 45 deg chamfer on both outer end edges
STEP_ANGLE = 45.0        # cone between d1 and d2, to the axis
STEP_CLEARANCE = 1.0     # the d2 section starts this far below the square
COUNTERSINK_DIA = 1.08   # x e: mouth countersink diameter (clears the corners)
COUNTERSINK_WALL = 2.0   # ... but at least this much below d1 on the diameter
SQUARE_EXTRA_DEPTH = 0.3  # square pocket depth beyond l2 min (see clearance_hole)

FORMS = {"hex": "Hex socket", "bi-hex": "Bi-hex socket"}
TYPES = {"A": "A (normal)", "B": "B (long)"}


def _fmt(x: float) -> str:
    return f"{x:g}"


def corner_dia(s: float) -> float:
    """Across corners of the sharp hexagon (and of the 12-point opening)."""
    return 2 * s / SQRT3


def countersink_dia(sd: SocketData) -> float:
    return min(COUNTERSINK_DIA * corner_dia(sd.s), sd.d1 - COUNTERSINK_WALL)


def step_z(sd: SocketData, length: float) -> tuple[float, float]:
    """(z where the cone from d1 starts, z where it reaches d2)."""
    sq = SQUARES[sd.drive]
    z_top = length - sq.l2 - STEP_CLEARANCE
    dz = (sd.d2 - sd.d1) / 2 / math.tan(math.radians(STEP_ANGLE))
    return z_top - dz, z_top


def outer_body(sd: SocketData, length: float) -> Part:
    c = OUTER_CHAMFER
    r1, r2 = sd.d1 / 2, sd.d2 / 2
    pts = [(0.0, 0.0), (r1 - c, 0.0), (r1, c)]
    if sd.d2 > sd.d1 + 1e-9:
        z0, z1 = step_z(sd, length)
        pts += [(r1, z0), (r2, z1)]
    pts += [(r2, length - c), (r2 - c, length), (0.0, length)]
    return revolve_profile(pts)


def opening_cutter(sd: SocketData, form: str) -> Part:
    """Hexagon or double hexagon of nominal s, t deep from z = 0, with the
    mouth countersink and the bolt clearance hole d3 behind it."""
    prism = Pos(0, 0, -0.1) * extrude(
        RegularPolygon(radius=sd.s / 2, side_count=6, major_radius=False), amount=sd.t + 0.1
    )
    cut = prism
    if form == "bi-hex":
        cut = cut + Rot(0, 0, 30) * prism
    r_cs = countersink_dia(sd) / 2
    half = math.radians(COUNTERSINK_ANGLE / 2)
    eps = 0.1
    cut = cut + revolve_profile([
        (0.0, -eps),
        (r_cs + eps * math.tan(half), -eps),
        (0.0, r_cs / math.tan(half)),
    ])
    return cut


def clearance_hole(sd: SocketData, length: float) -> Part:
    """Bolt clearance hole d3 from the bottom of the opening up to l2 below
    the drive face. The square pocket goes SQUARE_EXTRA_DEPTH deeper, so the
    two cutters overlap without coplanar faces; where d3 is wider than the
    square (6.3 drive from s = 10 up) the square's walls keep their full
    depth l2."""
    z_top = length - SQUARES[sd.drive].l2
    return Pos(0, 0, sd.t - 0.1) * Cylinder(
        sd.d3 / 2, z_top - sd.t + 0.1, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )


def build_socket(sd: SocketData, form: str, socket_type: str, retainer: str) -> Part:
    """Build the socket.

    Coordinate system: Z is the socket axis. The opening faces -Z with its
    mouth at z = 0 (put it on a nut whose top is at z = 0); the drive face
    with the female square is at z = l. Flats of the opening face +-Y; the
    square's flats face +-X and +-Y, the type D hole goes through the +X
    wall.
    """
    length = sd.length(socket_type)
    sq = SQUARES[sd.drive]
    body = outer_body(sd, length)
    cutters = [
        opening_cutter(sd, form),
        clearance_hole(sd, length),
        female_square_cutter(sq, retainer, length, wall=sd.d2, extra_depth=SQUARE_EXTRA_DEPTH),
    ]
    for c in cutters:
        body = body - c
    if len(body.solids()) != 1 or not body.is_valid:
        raise RuntimeError(f"ISO 2725-1 socket {sd.drive} x {sd.size} failed")
    return body


class ISO2725(Standard):
    id = "iso2725-1"
    title = "ISO 2725-1"
    summary = "Square drive sockets, hex and bi-hex, 6.3 / 10 / 12.5 drive, s = 3.2 to 34"
    category = "Tools"
    source = (
        "Values in mm, from ISO 2725-1:2017 Tables 1 to 3 and ISO 1174-1:2011 "
        "Tables 1 and 2 (driving square)."
    )

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="drive",
                label="Square drive",
                kind="select",
                default="12.5",
                options=[
                    Option("6.3", "6.3 mm (1/4 in), s = 3.2 to 17"),
                    Option("10", "10 mm (3/8 in), s = 6 to 25"),
                    Option("12.5", "12.5 mm (1/2 in), s = 8 to 34"),
                ],
            ),
            Parameter(
                name="size",
                label="Width across flats s",
                kind="select",
                default="13",
                options=[Option(s, f"{s} mm") for s in ALL_SIZES],
            ),
            Parameter(
                name="form",
                label="Opening",
                kind="select",
                default="hex",
                options=[Option("hex", "Hexagon (6-point)"), Option("bi-hex", "Double hexagon (12-point)")],
            ),
            Parameter(
                name="type",
                label="Length",
                kind="select",
                default="A",
                options=[Option(k, v) for k, v in TYPES.items()],
            ),
            Parameter(
                name="retainer",
                label="Square retaining feature (ISO 1174-1)",
                kind="select",
                default="C",
                options=[
                    Option("C", "Type C: ball recesses"),
                    Option("D", "Type D: plunger hole"),
                ],
            ),
        ]

    def validate(self, raw: dict[str, Any]) -> dict[str, Any]:
        drive = str(raw.get("drive", "12.5"))
        if drive not in SOCKETS:
            raise ParameterError(f"unknown square drive {drive!r}; choose one of {', '.join(SOCKETS)}")
        size = str(raw.get("size", "13"))
        table = SOCKETS[drive]
        if size not in table:
            raise ParameterError(
                f"ISO 2725-1 has no {drive} drive socket for s = {size}; "
                f"sizes: {', '.join(table)}"
            )
        form = str(raw.get("form", "hex"))
        if form not in FORMS:
            raise ParameterError(f"unknown opening {form!r}; choose hex or bi-hex")
        socket_type = str(raw.get("type", "A"))
        if socket_type not in TYPES:
            raise ParameterError(f"unknown type {socket_type!r}; choose A or B")
        retainer = str(raw.get("retainer", "C"))
        if retainer not in ("C", "D"):
            raise ParameterError(f"unknown retaining feature {retainer!r}; choose C or D")
        if retainer not in SQUARES[drive].types:
            raise ParameterError(f"ISO 1174-1 has no type {retainer} female square of size {drive}")
        return {"drive": drive, "size": size, "form": form, "type": socket_type, "retainer": retainer}

    def designation(self, p: dict[str, Any]) -> str:
        drive = SQUARES[p["drive"]].name
        return f"{FORMS[p['form']]} ISO 2725-1 - {drive} x {p['size']} - {p['type']}"

    def file_stem(self, p: dict[str, Any]) -> str:
        form = "BiHex" if p["form"] == "bi-hex" else "Hex"
        return f"ISO2725-1_{form}_{p['drive']}x{p['size']}_{p['type']}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        sd = SOCKETS[p["drive"]][p["size"]]
        sq = SQUARES[p["drive"]]
        length = sd.length(p["type"])
        l_label = "Length, type A, max." if p["type"] == "A" else "Length, type B, min."
        dims = [
            Dimension("s", "Width across flats, nominal (tolerance ISO 691)", sd.s),
            Dimension("Dmax", "Largest thread served", sd.D_max),
            Dimension("t", "Depth of the opening, min.", sd.t),
            Dimension("d1", "Outside diameter, opening end, max.", sd.d1),
            Dimension("d2", "Outside diameter, drive end, max.", sd.d2),
            Dimension("d3", "Bolt clearance hole, min.", sd.d3),
            Dimension("l", l_label, length),
            Dimension("s2", "Female square (min / max)", f"{sq.s2_min:.2f} / {sq.s2_max:.2f}"),
            Dimension("e2", "Square across corners, min.", sq.e2),
            Dimension("l2", "Square depth, min.", sq.l2),
            Dimension("l3", "Face to retaining feature", f"{_fmt(sq.l3)} ± {_fmt(sq.l3_tol)}", ""),
        ]
        if p["retainer"] == "D":
            dims.append(Dimension("d3 sq", "Retaining hole, min.", sq.d3))
        dims.append(Dimension("α", "Countersink (model; 115 to 150°)", f"{_fmt(COUNTERSINK_ANGLE)}°", ""))
        return dims

    def notes(self, p: dict[str, Any]) -> list[str]:
        sd = SOCKETS[p["drive"]][p["size"]]
        sq = SQUARES[p["drive"]]
        out = []
        if not sd.in_iso272:
            out.append(f"s = {sd.size} is not a width across flats of ISO 272.")
        if p["retainer"] not in sq.preferred:
            out.append(f"Type {p['retainer']} is non-preferred for the {p['drive']} square (ISO 1174-1 Table 2).")
        out.append(
            "ISO 2725-1 gives limits only (the figures are examples). The model "
            "uses d1, d2 and l at the table values, t min and d3 min, and the "
            "opening at nominal s with sharp corners; real openings are larger "
            "by the ISO 691 tolerance."
        )
        out.append(
            f"Model choices: {_fmt(COUNTERSINK_ANGLE)}° countersink at the mouth, "
            f"{_fmt(STEP_ANGLE)}° step from d1 to d2 just below the square, "
            f"{_fmt(OUTER_CHAMFER)} mm outer chamfers."
        )
        square = (
            f"Female square type {p['retainer']}: s2 = {sq.s2:g} (mean), corners at "
            f"e2 min, {_fmt(sq.l2 + SQUARE_EXTRA_DEPTH)} deep "
            f"(l2 min + {_fmt(SQUARE_EXTRA_DEPTH)})"
        )
        if p["retainer"] == "C":
            square += (f", ball recesses ⌀{_fmt(sq.ball)} sunk {_fmt(sq.l4)} mm into "
                       "the ±X faces at l3.")
        else:
            square += f", ⌀{_fmt(sq.d3)} retaining hole through the +X wall at l3."
            if sq.size in ("12.5", "20", "25"):
                square += " The lead-in groove (r2, t1) is not modeled."
        out.append(square)
        out.append("Opening at z = 0 facing −Z; drive face at z = l.")
        return out

    def build(self, p: dict[str, Any]) -> Part:
        sd = SOCKETS[p["drive"]][p["size"]]
        part = build_socket(sd, p["form"], p["type"], p["retainer"])
        part.label = self.designation(p)
        return part

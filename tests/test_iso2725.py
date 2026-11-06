import math
import tempfile
from pathlib import Path

import pytest
from build123d import Vector, export_step, import_step

from standardparts.standards import ParameterError
from standardparts.standards.iso1174_data import SQUARES
from standardparts.standards.iso2725 import (
    ISO2725,
    corner_dia,
    countersink_dia,
    outer_body,
    step_z,
)
from standardparts.standards.iso2725_data import ALL_SIZES, SOCKETS

SOCKET = ISO2725()
ROWS = [(drive, size) for drive, table in SOCKETS.items() for size in table]


def test_tables():
    assert [len(t) for t in SOCKETS.values()] == [16, 20, 22]
    assert ALL_SIZES[0] == "3.2" and ALL_SIZES[-1] == "34"
    for table in SOCKETS.values():
        prev = None
        for size, sd in table.items():
            assert sd.size == size
            # t min and d1 max grow with s; d2 >= d1 (Figures 1 and 2 only).
            if prev is not None:
                assert sd.s > prev.s and sd.t >= prev.t and sd.d1 > prev.d1
            assert sd.d1 <= sd.d2
            assert sd.l_A < sd.l_B
            # d3 min = 1.05 Dmax (footnote b), except Dmax 18, printed 18.3
            # in both Tables 2 and 3.
            if sd.D_max != 18:
                assert sd.d3 == pytest.approx(math.floor(1.05 * sd.D_max * 10 + 0.5) / 10, abs=1e-9)
            else:
                assert sd.d3 == 18.3
            assert sd.d3 < sd.s
            prev = sd


def test_squares():
    for size, sq in SQUARES.items():
        assert sq.s2_min < sq.s2 < sq.s2_max
        # The female square clears the male square of Table 1 at the corners.
        assert sq.e2 > sq.s2_max
        assert sq.preferred and set(sq.preferred) <= set(sq.types)
        # Every type C square has a ball; 25 has no type A male square.
        assert sq.ball is not None or "C" not in sq.types
        assert (sq.ball is None) == (size == "25")
        # l4 min = s2 max - s1 min + 0.5 (Table 1, footnote b), rounded.
        assert sq.l3 < sq.l2


@pytest.mark.parametrize("drive,size", ROWS, ids=[f"{d}x{s}" for d, s in ROWS])
def test_clearances(drive, size):
    sd = SOCKETS[drive][size]
    sq = SQUARES[drive]
    for socket_type in ("A", "B"):
        l = sd.length(socket_type)
        z0, _ = step_z(sd, l)
        # The step from d1 to d2 lies between the opening and the square.
        if sd.d2 > sd.d1:
            assert z0 > sd.t + 2
        assert l - sq.l2 > sd.t + 2
    # Walls: opening corners inside d1, square corners inside d2.
    assert (sd.d1 - corner_dia(sd.s)) / 2 >= 1.0
    assert (sd.d2 - sq.e2) / 2 >= 1.9
    # The countersink clears the opening's corners and leaves a face ring.
    assert corner_dia(sd.s) < countersink_dia(sd) <= sd.d1 - 2.0
    # Type D hole and type C recesses stay inside the wall.
    assert sq.s2 / 2 + sq.l4 < sd.d2 / 2 - 1


def probe(part, sd, form, socket_type, retainer):
    sq = SQUARES[sd.drive]
    l = sd.length(socket_type)
    s, t = sd.s, sd.t
    z = t / 2
    # Opening: a corner points along +X.
    r_corner = corner_dia(s) / 2
    assert not part.is_inside(Vector(r_corner - 0.1, 0, z))
    assert part.is_inside(Vector(r_corner + 0.1, 0, z))
    if form == "hex":
        # Flats face +-Y.
        assert not part.is_inside(Vector(0, s / 2 - 0.05, z))
        assert part.is_inside(Vector(0, s / 2 + 0.05, z))
    else:
        # The second hexagon puts corners along +-Y; the 12 inner corners
        # lie at 15 deg, at (s / 2) / cos 15 deg.
        assert not part.is_inside(Vector(0, r_corner - 0.1, z))
        r_in = s / 2 / math.cos(math.radians(15))
        u = Vector(math.cos(math.radians(15)), math.sin(math.radians(15)), 0)
        assert not part.is_inside(u * (r_in - 0.05) + Vector(0, 0, z))
        assert part.is_inside(u * (r_in + 0.05) + Vector(0, 0, z))
    # Outside diameters.
    assert part.is_inside(Vector(sd.d1 / 2 - 0.05, 0, t))
    assert not part.is_inside(Vector(sd.d1 / 2 + 0.05, 0, t))
    assert part.is_inside(Vector(0, sd.d2 / 2 - 0.05, l - 1))
    assert not part.is_inside(Vector(0, sd.d2 / 2 + 0.05, l - 1))
    # Clearance hole between opening and square, stopping below the square.
    z_bore = (t + l - sq.l2) / 2
    assert not part.is_inside(Vector(sd.d3 / 2 - 0.05, 0, z_bore))
    assert part.is_inside(Vector(sd.d3 / 2 + 0.05, 0, z_bore))
    if sd.d3 / 2 > sq.s2 / 2:
        assert part.is_inside(Vector(0, sq.s2 / 2 + 0.05, l - sq.l2 + 0.05))
    # Square: flats face +-X and +-Y.
    z_sq = l - sq.l2 + 0.5
    assert not part.is_inside(Vector(0, sq.s2 / 2 - 0.05, z_sq))
    assert part.is_inside(Vector(0, sq.s2 / 2 + 0.05, z_sq))
    # Corners turned to e2 (in the 45 deg direction).
    c = 1 / math.sqrt(2)
    assert not part.is_inside(Vector(c, c, 0) * (sq.e2 / 2 - 0.05) + Vector(0, 0, z_sq))
    assert part.is_inside(Vector(c, c, 0) * (sq.e2 / 2 + 0.05) + Vector(0, 0, z_sq))
    # Bottom of the square, 0.3 below l2 (where the clearance hole is narrower).
    if sd.d3 / 2 < sq.s2 / 2 - 0.5:
        assert not part.is_inside(Vector(0, sq.s2 / 2 - 0.05, l - sq.l2 - 0.25))
        assert part.is_inside(Vector(0, sq.s2 / 2 - 0.05, l - sq.l2 - 0.35))
    # Mouth chamfer r1 at 45 deg on the drive face.
    assert not part.is_inside(Vector(0, sq.s2 / 2 + 0.5 * sq.r1, l - 0.25 * sq.r1))
    assert part.is_inside(Vector(0, sq.s2 / 2 + 0.5 * sq.r1, l - 0.75 * sq.r1))
    z_ret = l - sq.l3
    if retainer == "C":
        for sign in (1, -1):
            assert not part.is_inside(Vector(sign * (sq.s2 / 2 + sq.l4 / 2), 0, z_ret))
        assert part.is_inside(Vector(0, sq.s2 / 2 + sq.l4 / 2, z_ret))
    else:
        assert not part.is_inside(Vector(sd.d2 / 2 - 0.1, 0, z_ret))
        assert part.is_inside(Vector(-(sd.d2 / 2 - 0.1), 0, z_ret))


SAMPLE = (
    [(d, s, "hex", "A", SQUARES[d].preferred[0]) for d, s in ROWS]
    + [(d, s, "bi-hex", "B", SQUARES[d].types[-1]) for d, s in ROWS]
)


@pytest.mark.parametrize("drive,size,form,socket_type,retainer", SAMPLE,
                         ids=[f"{d}x{s}-{f}-{t}-{r}" for d, s, f, t, r in SAMPLE])
def test_sockets_build(drive, size, form, socket_type, retainer):
    sd = SOCKETS[drive][size]
    p = SOCKET.validate({"drive": drive, "size": size, "form": form, "type": socket_type,
                         "retainer": retainer})
    part = SOCKET.build(p)
    assert part.label == SOCKET.designation(p)
    assert part.is_valid and len(part.solids()) == 1
    bb = part.bounding_box()
    l = sd.length(socket_type)
    assert bb.min.Z == pytest.approx(0, abs=1e-6)
    assert bb.max.Z == pytest.approx(l, abs=1e-6)
    assert bb.size.X == pytest.approx(sd.d2, abs=1e-3)
    assert part.volume < outer_body(sd, l).volume
    probe(part, sd, form, socket_type, retainer)


def test_step_roundtrip():
    p = SOCKET.validate({"drive": "10", "size": "13", "form": "bi-hex"})
    part = SOCKET.build(p)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "socket.stp"
        export_step(part, path)
        assert b"Bi-hex socket ISO 2725-1 - 10 x 13 - A" in path.read_bytes()
        imported = import_step(path)
    assert imported.is_valid
    assert imported.volume == pytest.approx(part.volume, rel=1e-6)


def test_api_surface():
    assert SOCKET.category == "Tools"
    params = {p.name: p for p in SOCKET.parameters()}
    assert set(params) == {"drive", "size", "form", "type", "retainer"}
    assert [o.value for o in params["size"].options] == ALL_SIZES
    p = SOCKET.validate({})
    assert p == {"drive": "12.5", "size": "13", "form": "hex", "type": "A", "retainer": "C"}
    assert SOCKET.designation(p) == "Hex socket ISO 2725-1 - 12,5 x 13 - A"
    assert SOCKET.file_stem(p) == "ISO2725-1_Hex_12.5x13_A"
    # Example of the designation clause.
    p = SOCKET.validate({"drive": "12.5", "size": "10", "form": "bi-hex"})
    assert SOCKET.designation(p) == "Bi-hex socket ISO 2725-1 - 12,5 x 10 - A"
    dims = {d.symbol: d.value for d in SOCKET.dimensions(p)}
    assert dims["t"] == 5.3 and dims["d1"] == 15.5 and dims["l"] == 40
    p = SOCKET.validate({"drive": "10", "size": "9", "retainer": "D"})
    notes = SOCKET.notes(p)
    assert any("not a width across flats of ISO 272" in n for n in notes)
    assert any("non-preferred" in n for n in notes)


@pytest.mark.parametrize("raw", [
    {"drive": "20", "size": "24"},
    {"drive": "6.3", "size": "19"},
    {"drive": "12.5", "size": "6"},
    {"drive": "12.5", "size": "13", "form": "square"},
    {"drive": "12.5", "size": "13", "type": "C"},
    {"drive": "12.5", "size": "13", "retainer": "B"},
])
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        SOCKET.validate(raw)

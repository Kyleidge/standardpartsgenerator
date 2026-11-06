import math
import tempfile
from pathlib import Path

import pytest
from build123d import Unit, Vector, export_step, import_step

from standardparts.geometry import chamfered_hex
from standardparts.standards import ParameterError
from standardparts.standards.iso4032_data import SIZES as ISO4032_SIZES
from standardparts.standards.iso4035_data import SIZES as ISO4035_SIZES
from standardparts.standards.nyloc import INSERT_COLOR, ISO7040, ISO10511
from standardparts.standards.nyloc_data import (
    CHAMFER_ANGLE,
    COUNTERSINK_ANGLE,
    ISO7040_SIZES,
    ISO10511_SIZES,
)

N7040 = ISO7040()
N10511 = ISO10511()
STDS = {"7040": N7040, "10511": N10511}
BASE = {"7040": ISO4032_SIZES, "10511": ISO4035_SIZES}
SQRT3 = math.sqrt(3)
TAN60 = math.tan(math.radians(COUNTERSINK_ANGLE / 2))
TANB = math.tan(math.radians(CHAMFER_ANGLE))
COARSE = {3: 0.5, 4: 0.7, 5: 0.8, 6: 1, 8: 1.25, 10: 1.5, 12: 1.75, 14: 2, 16: 2,
          20: 2.5, 24: 3, 30: 3.5, 36: 4}
SIZE_LIST = ["M3", "M4", "M5", "M6", "M8", "M10", "M12", "M14", "M16", "M20", "M24",
             "M30", "M36"]
ALL = [(n, s) for n in STDS for s in SIZE_LIST]

# Modeled threads sampled in the suite; every size in both modes was swept
# separately.
MODELED_SAMPLE = [("7040", "M3"), ("7040", "M10"), ("7040", "M36"),
                  ("10511", "M4"), ("10511", "M16")]


def d1(nd):
    return nd.D - 1.25 * SQRT3 / 2 * nd.P


def build(number, size, thread="simplified"):
    std = STDS[number]
    return std.build(std.validate({"size": size, "thread": thread}))


def test_size_lists():
    assert list(ISO7040_SIZES) == SIZE_LIST
    assert list(ISO10511_SIZES) == SIZE_LIST


@pytest.mark.parametrize("number,size", ALL)
def test_rows_are_consistent(number, size):
    nd = STDS[number].sizes[size]
    base = BASE[number][size]
    assert nd.P == COARSE[nd.D] == base.P
    assert nd.preferred == (size != "M14")
    assert nd.s_min < nd.s_max and nd.s_max == base.s_max and nd.s_min == base.s_min
    assert nd.h_min < nd.h_max
    # The metal part is the plain nut: same m min, mw min = 0.8 m min.
    assert nd.m_min == base.m_min
    assert nd.mw_min == pytest.approx(0.8 * nd.m_min, abs=0.006)
    assert nd.m_hex == base.m_max
    assert nd.m_min < nd.m_hex < nd.h_min
    assert nd.e_min == pytest.approx(1.13 * nd.s_min, abs=0.01)
    assert nd.D < nd.da_max <= 1.16 * nd.D
    # Model proportions: insert inside the collar, collar inside dw <= s,
    # lip opening clears the screw, insert bore under D1.
    assert nd.da_max < nd.di < nd.dc < nd.dw_min < nd.s_min
    assert nd.D < nd.dl < nd.di
    assert 0.95 * d1(nd) < nd.d_insert < d1(nd)
    assert nd.wall > 0.25 and nd.insert_height > 1.5
    # Hex corners at least e min wide over mw min.
    assert nd.m_hex - 2 * (nd.e_min - nd.dw_min) / 2 * TANB >= nd.mw_min


def test_angles_in_standard_ranges():
    assert 15 <= CHAMFER_ANGLE <= 30
    assert 90 <= COUNTERSINK_ANGLE <= 120


def collar_volume(nd, z0):
    ri, rc, rl, t, h = nd.di / 2, nd.dc / 2, nd.dl / 2, nd.wall, nd.h
    ring = math.pi * (rc**2 - ri**2) * (h - t - z0)
    rounded = math.pi * t * t / 4 * 2 * math.pi * (ri + 4 * t / (3 * math.pi))
    lip = math.pi * (ri**2 - rl**2) * t
    return ring + rounded + lip


def check_nyloc(number, size, thread):
    std = STDS[number]
    nd = std.sizes[size]
    part = build(number, size, thread)
    assert part.is_valid
    assert part.label == f"ISO {number} - {size}"
    assert len(part.solids()) == 2
    body, insert = part.children
    assert (body.label, insert.label) == ("body", "insert")
    assert insert.color is not None and tuple(insert.color) == pytest.approx(tuple(INSERT_COLOR))
    for child in (body, insert):
        assert child.is_valid and len(child.solids()) == 1
    tol = 1e-3 * nd.D
    bb = part.bounding_box()
    assert bb.size.X == pytest.approx(nd.e_nom, abs=tol)
    assert bb.size.Y == pytest.approx(nd.s_nom, abs=tol)
    assert bb.min.Z == pytest.approx(0, abs=tol)
    assert bb.max.Z == pytest.approx(nd.h_max, abs=tol)
    # Insert sits inside the collar: within the collar bore, between the top
    # of the hex and the lip.
    ib = insert.bounding_box()
    assert ib.size.X == pytest.approx(nd.di, abs=tol)
    assert ib.min.Z == pytest.approx(nd.m_hex, abs=tol)
    assert ib.max.Z == pytest.approx(nd.h - nd.wall, abs=tol)
    assert ib.max.X < nd.dc / 2
    m, h, t = nd.m_hex, nd.h, nd.wall
    ri, rc, rl, rb = nd.di / 2, nd.dc / 2, nd.dl / 2, nd.d_insert / 2
    z_ins = (m + h - t) / 2
    # Bore empty; hex wall, collar wall and lip are steel.
    assert not body.is_inside(Vector(0, 0, m / 2))
    assert not body.is_inside(Vector(0.95 * d1(nd) / 2, 0, m / 2))
    assert body.is_inside(Vector((nd.D / 2 + nd.s_nom / 2) / 2, 0, m / 2))
    assert body.is_inside(Vector(0, (ri + rc) / 2, z_ins))
    assert body.is_inside(Vector((rl + ri) / 2, 0, h - t / 2))
    assert not body.is_inside(Vector(0, (rc + nd.s_nom / 2) / 2, z_ins))
    assert not body.is_inside(Vector((rb + rl) / 2, 0, h - t / 2))
    # Insert fills the collar bore and is not part of the body.
    for r in (0.5 * (rb + ri), rb + 0.05 * (ri - rb), ri - 0.05 * (ri - rb)):
        p = Vector(r, 0, z_ins)
        assert insert.is_inside(p) and not body.is_inside(p)
    assert not insert.is_inside(Vector(0.97 * rb, 0, z_ins))
    # The bolt cuts its thread in the insert: the insert bore is under D1.
    assert insert.is_inside(Vector(0, 1.005 * rb, z_ins))
    # Bearing face flat to dw, chamfered corners, full corners mid-height.
    eps = 0.01 * m
    assert body.is_inside(Vector(0, 0.97 * nd.dw_min / 2, eps))
    for z in (eps, m - eps):
        assert not body.is_inside(Vector(0.99 * nd.e_nom / 2, 0, z))
    for z in (m / 2 - 0.45 * nd.mw_min, m / 2 + 0.45 * nd.mw_min):
        assert body.is_inside(Vector(0.99 * nd.e_nom / 2, 0, z))
    # Countersink on the bearing face.
    r = (nd.D + nd.da_max) / 4
    depth = (nd.da_max / 2 - r) / TAN60
    assert not body.is_inside(Vector(0, r, 0.3 * depth))
    assert body.is_inside(Vector(0, r, depth + 0.05 * m))
    # Solids do not overlap.
    common = body & insert
    assert common.volume < 1e-6 * insert.volume
    return part


@pytest.mark.parametrize("number,size", ALL)
def test_simplified_nyloc(number, size):
    part = check_nyloc(number, size, "simplified")
    nd = STDS[number].sizes[size]
    body, insert = part.children
    m = nd.m_hex
    hex_body = chamfered_hex(nd.s_nom, 0, m, nd.dw_min, nd.dw_min, CHAMFER_ANGLE)
    r, ra = d1(nd) / 2, nd.da_max / 2
    ts = (ra - r) / TAN60
    countersink = math.pi * ts / 3 * (ra * ra + ra * r + r * r) - math.pi * r * r * ts
    nut = hex_body.volume - math.pi * r * r * m - 2 * countersink
    assert body.volume == pytest.approx(nut + collar_volume(nd, m), rel=1e-6)
    ri, rb = nd.di / 2, nd.d_insert / 2
    assert insert.volume == pytest.approx(
        math.pi * (ri**2 - rb**2) * (nd.h - nd.wall - m), rel=1e-6
    )


@pytest.mark.parametrize("number,size", MODELED_SAMPLE)
def test_modeled_nyloc(number, size):
    part = check_nyloc(number, size, "modeled")
    nd = STDS[number].sizes[size]
    body = part.children[0]
    P = nd.P
    H = SQRT3 / 2 * P
    m = nd.m_hex
    assert body.is_inside(Vector(nd.D / 2 + 0.2 * P, 0, m / 2))
    # Ridge fills 9/16 of the axial length halfway up the flank.
    r_mid = (d1(nd) + nd.D) / 4
    n = 48
    hits = sum(
        body.is_inside(Vector(r_mid, 0, m / 2 - P / 2 + P * (i + 0.5) / n)) for i in range(n)
    )
    assert hits / n == pytest.approx(9 / 16, abs=0.04)
    # Groove volume relative to the plain bore, as for ISO 4032.
    plain = build(number, size).children[0]
    r_g = d1(nd) / 2 + 0.381 * 5 / 8 * H
    length = m - 2 * (nd.da_max / 2 - r_g) / TAN60
    expected = 35 / 128 * P * H * 2 * math.pi * r_g * length / P
    assert plain.volume - body.volume == pytest.approx(expected, rel=0.03)
    # Insert identical in both modes.
    assert part.children[1].volume == pytest.approx(
        build(number, size).children[1].volume, rel=1e-9
    )


def test_step_roundtrip():
    part = build("7040", "M8", "modeled")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "nut.stp"
        export_step(part, str(path), unit=Unit.MM)
        data = path.read_bytes()
        imported = import_step(path)
    assert data.startswith(b"ISO-10303-21;")
    assert b"ISO 7040 - M8" in data and b"insert" in data and b"body" in data
    assert len(imported.solids()) == 2
    assert imported.is_valid
    assert imported.volume == pytest.approx(part.volume, rel=1e-4)


@pytest.mark.parametrize(
    "std,raw",
    [
        (N7040, {"size": "M2"}),
        (N7040, {"size": "M39"}),
        (N7040, {"size": "8"}),
        (N10511, {"size": "M1.6"}),
        (N10511, {"size": "M8", "thread": "fancy"}),
    ],
)
def test_validation_rejects(std, raw):
    with pytest.raises(ParameterError):
        std.validate(raw)


def test_designation_and_files():
    p = N7040.validate({"size": "M8"})
    assert p == {"size": "M8", "thread": "simplified"}
    assert N7040.designation(p) == "ISO 7040 - M8"
    assert N7040.file_stem(p) == "ISO7040_M8"
    assert N7040.file_stem(N7040.validate({"size": "M8", "thread": "modeled"})) == "ISO7040_M8_threaded"
    q = N10511.validate({"size": "M36", "thread": "modeled"})
    assert N10511.designation(q) == "ISO 10511 - M36"
    assert N10511.file_stem(q) == "ISO10511_M36_threaded"
    for std in (N7040, N10511):
        assert std.category == "Nuts"
        assert {par.kind for par in std.parameters()} <= {"select", "length"}
        assert [o.value for o in std.parameters()[0].options] == list(std.sizes)
        assert std.parameters()[0].default in std.sizes
        assert [o.value for o in std.parameters()[1].options] == ["simplified", "modeled"]


def test_notes_and_dimensions():
    notes = " ".join(N7040.notes(N7040.validate({"size": "M14"})))
    assert "avoided" in notes and "insert" in notes and "ISO 4032" in notes
    notes = " ".join(N10511.notes(N10511.validate({"size": "M8", "thread": "modeled"})))
    assert "avoided" not in notes and "ISO 68-1" in notes and "ISO 4035" in notes
    dims = {d.symbol: d for d in N7040.dimensions({"size": "M8", "thread": "simplified"})}
    assert dims["h max"].value == 9.5 and dims["m min"].value == 6.44
    assert dims["mw min"].value == 5.15 and dims["dw min"].value == 11.63
    assert dims["m"].value == 6.8
    assert dims["d insert"].value == pytest.approx(6.647 - 0.125, abs=1e-3)
    assert dims["β"].unit == "°"
    dims = {d.symbol: d.value for d in N10511.dimensions({"size": "M8", "thread": "simplified"})}
    assert dims["h max"] == 6.76 and dims["m"] == 4.0 and dims["s"] == 13

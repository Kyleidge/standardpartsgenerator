import math
import tempfile
from pathlib import Path

import pytest
from build123d import Unit, Vector, export_step, import_step

from standardparts.geometry import SQRT3, chamfered_hex
from standardparts.nuts import NUT_THREAD_MODES, Countersink, bore_volume
from standardparts.standards.base import ParameterError
from standardparts.standards.flange import hex_overlap_volume
from standardparts.standards.iso4161 import (
    CORE_RADIUS,
    HEX_BOTTOM_FRACTIONS,
    ISO4161,
    flange,
    model_mw,
)
from standardparts.standards.iso4161_data import (
    COUNTERSINK_ANGLE,
    SIZES,
    TOP_CHAMFER_ANGLE,
    TOP_CHAMFER_DIA,
)
from test_iso4162 import revolved_volume

STD = ISO4161()
TAN60 = math.tan(math.radians(COUNTERSINK_ANGLE / 2))
COARSE = {5: 0.8, 6: 1, 8: 1.25, 10: 1.5, 12: 1.75, 14: 2, 16: 2, 20: 2.5}

# Modeled sizes sampled here (the sweep script builds all of them).
MODELED_SAMPLE = ["M5", "M10", "M20"]


def d1(sd):
    return sd.D - 1.25 * SQRT3 / 2 * sd.P


def build(size, thread="simplified"):
    return STD.build(STD.validate({"size": size, "thread": thread}))


@pytest.mark.parametrize("sd", SIZES.values(), ids=list(SIZES))
def test_size_rows_are_consistent(sd):
    assert sd.P == COARSE[sd.D]
    assert sd.preferred == (sd.size != "M14")
    assert sd.s_min < sd.s_max
    assert sd.m_min < sd.m_max == sd.D
    assert sd.mw_min < sd.m_min
    assert sd.D < sd.da_max <= 1.15 * sd.D
    # e min = 1.13 s min (ISO 4759-1), below the exact corners of s nom.
    assert sd.e_min == pytest.approx(1.13 * sd.s_min, abs=0.006)
    assert sd.e_min < sd.e_nom < sd.dw_min < sd.dc_max
    assert sd.product_grade == ("A" if sd.D <= 16 else "B")


@pytest.mark.parametrize("sd", SIZES.values(), ids=list(SIZES))
def test_model_geometry_within_standard(sd):
    fl = flange(sd)
    fl.check()
    assert fl.bearing_dia >= sd.dw_min - 1e-9
    assert sd.e_nom / 2 < fl.rim_top[0] <= sd.dc_max / 2 + 1e-9
    assert model_mw(sd) >= sd.mw_min
    # Countersinks fit inside the top chamfer circle and the flange.
    assert sd.da_max < TOP_CHAMFER_DIA * sd.s_nom


def check_nut(size, thread):
    sd = SIZES[size]
    part = build(size, thread)
    assert part.is_valid
    assert len(part.solids()) == 1
    assert part.label == f"ISO 4161 - {size}"
    bb = part.bounding_box()
    tol = 1e-3 * sd.D
    assert bb.size.X == pytest.approx(sd.dc_max, abs=tol)
    assert bb.size.Y == pytest.approx(sd.dc_max, abs=tol)
    assert bb.min.Z == pytest.approx(0, abs=tol)
    assert bb.max.Z == pytest.approx(sd.m_max, abs=tol)
    m, s, e2 = sd.m_max, sd.s_nom, sd.e_nom / 2
    fl = flange(sd)
    z_mid = (fl.height(e2) + m) / 2
    # Bore empty below the minor diameter, wall solid.
    assert not part.is_inside(Vector(0, 0, m / 2))
    assert not part.is_inside(Vector(0.95 * d1(sd) / 2, 0, m / 2))
    assert part.is_inside(Vector((sd.D / 2 + s / 2) / 2, 0, z_mid))
    # Hexagon: corners on X, flats parallel to X, chamfered top corner.
    assert part.is_inside(Vector(0.97 * e2, 0, z_mid))
    assert part.is_inside(Vector(0, 0.97 * s / 2, z_mid))
    assert not part.is_inside(Vector(0, 1.03 * s / 2, z_mid))
    assert not part.is_inside(Vector(0.99 * e2, 0, m - 0.01 * s))
    # Countersinks on both faces.
    r = (sd.D + sd.da_max) / 4
    depth = (sd.da_max / 2 - r) / TAN60
    for z in (0.3 * depth, m - 0.3 * depth):
        assert not part.is_inside(Vector(0, r, z))
    # Flange: solid at dw near the bearing face and just under c, empty
    # above the cone.
    rw = sd.dw_min / 2
    assert part.is_inside(Vector(0, rw, 0.02 * sd.c_min))
    assert part.is_inside(Vector(rw, 0, 0.95 * sd.c_min))
    assert not part.is_inside(Vector(rw, 0, 1.05 * sd.c_min))
    assert not part.is_inside(Vector(0.998 * sd.dc_max / 2, 0, fl.edge_height + 0.05))
    return part


def analytic_body_volume(sd):
    fl = flange(sd)
    s, m = sd.s_nom, sd.m_max
    r_core = CORE_RADIUS * s
    z_core = (fl.height(r_core) + m) / 2
    rev = revolved_volume([(0.0, 0.0), *fl.profile(r_core, z_core)])
    z_hex = HEX_BOTTOM_FRACTIONS[0] * fl.height(s / SQRT3)
    hexagon = chamfered_hex(s, z_hex, m, TOP_CHAMFER_DIA * s, None, TOP_CHAMFER_ANGLE)
    return rev + hexagon.volume - hex_overlap_volume(s, z_hex, fl, r_core, z_core)


@pytest.mark.parametrize("size", list(SIZES))
def test_simplified_nut(size):
    sd = SIZES[size]
    part = check_nut(size, "simplified")
    cs = Countersink(sd.da_max, COUNTERSINK_ANGLE)
    expected = analytic_body_volume(sd) - bore_volume(d1(sd) / 2, sd.m_max, cs, cs)
    assert part.volume == pytest.approx(expected, rel=1e-5)


@pytest.mark.parametrize("size", MODELED_SAMPLE)
def test_modeled_nut(size):
    part = check_nut(size, "modeled")
    sd = SIZES[size]
    P = sd.P
    H = SQRT3 / 2 * P
    m = sd.m_max
    assert part.is_inside(Vector(sd.D / 2 + 0.2 * P, 0, m / 2))
    # Volume removed relative to the plain bore at D1: the ISO 68-1 groove
    # (35/128 P H per pitch, centroid 0.381 of the way from D1 to D) over the
    # length between the countersinks at that radius.
    plain = build(size)
    r_g = d1(sd) / 2 + 0.381 * 5 / 8 * H
    length = m - 2 * (sd.da_max / 2 - r_g) / TAN60
    expected = 35 / 128 * P * H * 2 * math.pi * r_g * length / P
    assert plain.volume - part.volume == pytest.approx(expected, rel=0.03)


def test_step_roundtrip():
    part = build("M8", "modeled")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "nut.stp"
        export_step(part, str(path), unit=Unit.MM)
        data = path.read_bytes()
        imported = import_step(path)
    assert b"ISO 4161 - M8" in data
    assert imported.is_valid
    assert imported.volume == pytest.approx(part.volume, rel=1e-4)


@pytest.mark.parametrize("raw", [{"size": "M4"}, {"size": "M24"}, {"size": "8"},
                                 {"size": "M8", "thread": "fancy"}])
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        STD.validate(raw)


def test_designation_files_and_schema():
    p = STD.validate({})
    assert p == {"size": "M8", "thread": "simplified"}
    assert STD.designation(p) == "ISO 4161 - M8"
    assert STD.file_stem(p) == "ISO4161_M8"
    assert STD.file_stem(STD.validate({"size": "M8", "thread": "modeled"})) == "ISO4161_M8_threaded"
    params = STD.parameters()
    assert {par.kind for par in params} <= {"select", "length"}
    assert {o.value for o in params[0].options} == set(SIZES)
    assert [o.value for o in params[1].options] == list(NUT_THREAD_MODES)
    STD.describe_json()


def test_notes_and_dimensions():
    notes = " ".join(STD.notes(STD.validate({"size": "M14"})))
    assert "non-preferred" in notes and "grade A" in notes
    notes = " ".join(STD.notes(STD.validate({"size": "M20", "thread": "modeled"})))
    assert "grade B" in notes and "ISO 68-1" in notes
    dims = {d.symbol: d for d in STD.dimensions(STD.validate({"size": "M8"}))}
    assert dims["s"].value == 13 and dims["m max"].value == 8 and dims["dc max"].value == 17.9
    assert dims["δ"].unit == "°" and dims["grade"].unit == ""
    assert dims["D1"].value == pytest.approx(6.647, abs=1e-3)

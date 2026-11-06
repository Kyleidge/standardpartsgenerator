import math
import tempfile
from io import BytesIO
from pathlib import Path

import pytest
from build123d import Unit, Vector, export_step, export_stl, import_step

from standardparts.standards.base import ParameterError
from standardparts.standards.iso15 import (
    DETAILS,
    ISO15,
    Internals,
    assembly,
    envelope_volume,
)
from standardparts.standards.iso15_data import BEARINGS

ISO = ISO15()
STEEL = 7.85e-6  # kg / mm^3
ISO582_RS_MIN = {0.3, 0.6, 1, 1.1, 1.5, 2, 2.1, 3}
BORE_CODE = {"00": 10, "01": 12, "02": 15, "03": 17}


@pytest.mark.parametrize("bd", BEARINGS.values(), ids=list(BEARINGS))
def test_data_rows_are_consistent(bd):
    code = bd.bore_code
    assert bd.d == BORE_CODE.get(code, 5 * int(code))
    assert bd.d < bd.da_min < bd.da_max < bd.Da_max < bd.D
    assert bd.rs_min in ISO582_RS_MIN
    assert bd.ra_max <= bd.rs_min
    # Balls fit between the rings and side by side on the pitch circle.
    assert bd.Dw < (bd.D - bd.d) / 2
    assert 2 * (bd.dm / 2) * math.sin(math.pi / bd.z) > bd.Dw


def test_series_cover_bore_codes_00_to_22():
    for series in ("60", "62", "63"):
        codes = [b.bore_code for b in BEARINGS.values() if b.series == series]
        assert codes == [f"{i:02d}" for i in range(23)]


@pytest.mark.parametrize("code", [f"{i:02d}" for i in range(23)])
def test_series_grow_for_each_bore(code):
    b60, b62, b63 = (BEARINGS[s + code] for s in ("60", "62", "63"))
    assert b60.d == b62.d == b63.d
    assert b60.D < b62.D < b63.D
    assert b60.B < b62.B < b63.B
    assert b60.rs_min <= b62.rs_min <= b63.rs_min


@pytest.mark.parametrize("bd", BEARINGS.values(), ids=list(BEARINGS))
def test_internal_design_clearances(bd):
    it = Internals.of(bd)
    hb = bd.B / 2
    # Raceway grooves and the shield seat stay inside the width.
    assert it.zi < hb - it.k_step and it.zo < hb - it.k_step
    # Balls clear the lands at the groove edges and the shields.
    assert math.hypot(it.r_pitch - it.ri_sh, it.zi) > it.r_ball
    assert math.hypot(it.ro_sh - it.r_pitch, it.zo) > it.r_ball
    assert hb - it.e_shield - it.t_shield > it.r_ball
    # Shields sit between the rings.
    assert it.ri_sh < it.rs_in < it.rs_out < it.ro_rec
    # A shaft shoulder up to da max and a housing shoulder down to Da max
    # bear on the ring faces only, not on the shields.
    assert it.ri_sh > bd.da_max / 2
    assert it.ro_rec < bd.Da_max / 2


def build(size, detail):
    params = ISO.validate({"size": size, "detail": detail})
    part = ISO.build(params)
    assert part.is_valid
    assert part.label == f"{size} ({detail})"
    bd = BEARINGS[size]
    bb = part.bounding_box()
    tol = 1e-6 * bd.D
    assert (bb.min.Z, bb.max.Z) == pytest.approx((-bd.B / 2, bd.B / 2), abs=tol)
    for lo, hi in ((bb.min.X, bb.max.X), (bb.min.Y, bb.max.Y)):
        assert (lo, hi) == pytest.approx((-bd.D / 2, bd.D / 2), abs=tol)
    return part


def ring_section_checks(part, bd):
    """Points that every detail mode has in common."""
    rs, hb = bd.rs_min, bd.B / 2
    # Bore is empty, material just outside the bore and inside the OD.
    assert not part.is_inside(Vector(bd.d / 2 - 0.01 * bd.d, 0, 0))
    assert part.is_inside(Vector(0, bd.d / 2 + 0.3 * rs, 0))
    assert part.is_inside(Vector(-(bd.D / 2 - 0.3 * rs), 0, 0))
    # The four edges are rounded: the corner points are outside.
    for r in (bd.d / 2 + 0.1 * rs, bd.D / 2 - 0.1 * rs):
        for z in (hb - 0.1 * rs, -hb + 0.1 * rs):
            assert not part.is_inside(Vector(r, 0, z))


@pytest.mark.parametrize("size", list(BEARINGS))
def test_envelope(size):
    bd = BEARINGS[size]
    part = build(size, "envelope")
    assert len(part.solids()) == 1
    assert part.volume == pytest.approx(envelope_volume(bd), rel=1e-6)
    ring_section_checks(part, bd)
    assert part.is_inside(Vector(bd.dm / 2, 0, bd.B / 2 - 0.01 * bd.B))


@pytest.mark.parametrize("size", list(BEARINGS))
def test_faces(size):
    bd = BEARINGS[size]
    it = Internals.of(bd)
    part = build(size, "faces")
    assert len(part.solids()) == 1
    ring_section_checks(part, bd)
    # Shield recess and the gap at the inner ring are cut into both faces.
    hb = bd.B / 2
    recess = 2 * math.pi * ((it.ro_rec**2 - it.ri_sh**2) * it.e_shield
                            + (it.rs_in**2 - it.ri_sh**2) * it.t_shield)
    assert part.volume == pytest.approx(envelope_volume(bd) - recess, rel=1e-6)
    for side in (1, -1):
        assert not part.is_inside(Vector(bd.dm / 2, 0, side * (hb - 0.5 * it.e_shield)))
        assert part.is_inside(Vector(bd.dm / 2, 0, side * (hb - 1.5 * it.e_shield - it.t_shield)))
        gap_r = (it.ri_sh + it.rs_in) / 2
        assert not part.is_inside(Vector(gap_r, 0, side * (hb - it.e_shield - 0.5 * it.t_shield)))


@pytest.mark.parametrize("size", list(BEARINGS))
def test_rings(size):
    bd = BEARINGS[size]
    it = Internals.of(bd)
    part = build(size, "rings")
    assert len(part.solids()) == bd.z + 4
    assert all(s.is_valid for s in part.solids())
    labels = [c.label for c in part.children]
    assert labels[:4] == ["inner ring", "outer ring", "shield +Z", "shield -Z"]
    assert labels[4:] == [f"ball {i + 1}" for i in range(bd.z)]
    ring_section_checks(part, bd)
    # The model (no cage, with shields) weighs about what NSK lists for the
    # open bearing.
    assert part.volume * STEEL == pytest.approx(bd.mass, rel=0.08)
    balls = part.children[4:]
    assert sum(b.volume for b in balls) == pytest.approx(
        bd.z * math.pi / 6 * bd.Dw**3, rel=1e-6
    )
    for b in balls:
        c = b.center()
        assert math.hypot(c.X, c.Y) == pytest.approx(bd.dm / 2, abs=1e-6)
        assert c.Z == pytest.approx(0, abs=1e-6)
    # Free space between the inner ring land and the outer ring land.
    assert not part.is_inside(Vector((it.ri_sh + it.ro_sh) / 2, 0, it.r_ball * 1.05))


@pytest.mark.parametrize("size", ["6000", "6022", "6201", "6222", "6300", "6322"])
def test_rings_parts_do_not_overlap(size):
    bd = BEARINGS[size]
    parts = assembly(bd, Internals.of(bd)).children
    inner, outer, top, bottom, *balls = parts
    tol = 1e-6 * bd.D**3
    for a, b in [(inner, outer), (inner, top), (inner, bottom), (outer, top),
                 (outer, bottom), *((r, x) for r in (inner, outer, top, bottom) for x in balls[:2])]:
        common = a & b
        assert common.volume < tol, (a.label, b.label)


@pytest.mark.parametrize(
    "raw",
    [
        {"size": "6023"},
        {"size": "6400"},
        {"size": "abc"},
        {"size": "6205", "detail": "cage"},
    ],
)
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        ISO.validate(raw)


def test_designation_and_file_stem():
    p = ISO.validate({})
    assert p == {"size": "6205", "detail": "envelope"}
    assert ISO.designation(p) == "6205"
    assert ISO.file_stem(p) == "ISO15_6205_envelope"
    assert ISO.file_stem(ISO.validate({"size": "6322", "detail": "RINGS"})) == "ISO15_6322_rings"


def test_dimension_table():
    p = ISO.validate({"size": "6205", "detail": "rings"})
    dims = {d.symbol: d.value for d in ISO.dimensions(p)}
    assert (dims["d"], dims["D"], dims["B"], dims["r_s min"]) == (25, 52, 15, 1)
    assert dims["series"] == "02"
    assert dims["z"] == 9
    assert "z" not in {d.symbol for d in ISO.dimensions(ISO.validate({"size": "6205"}))}


def test_parameter_schema():
    params = {p.name: p for p in ISO.parameters()}
    assert params["size"].default in BEARINGS
    labels = {o.value: o.label for o in params["size"].options}
    assert labels["6205"] == "6205 (25 × 52 × 15)"
    assert [o.value for o in params["detail"].options] == list(DETAILS)
    ISO.describe_json()


@pytest.mark.parametrize("detail", list(DETAILS))
def test_step_and_stl_export(detail):
    p = ISO.validate({"size": "6205", "detail": detail})
    part = ISO.build(p)
    buf = BytesIO()
    export_step(part, buf, unit=Unit.MM)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bearing.stp"
        path.write_bytes(buf.getvalue())
        imported = import_step(path)
        stl = Path(tmp) / "bearing.stl"
        export_stl(part, stl, tolerance=52 * 5e-4, angular_tolerance=0.3)
        assert stl.stat().st_size > 1000
    assert len(imported.solids()) == len(part.solids())
    assert imported.volume == pytest.approx(part.volume, rel=1e-6)

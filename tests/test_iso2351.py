import math
import tempfile
from pathlib import Path

import pytest
from build123d import Vector, export_step, import_step

from standardparts.standards import ParameterError
from standardparts.standards.drive_ends import drive_end_shank, shank_radius
from standardparts.standards.iso1173_data import DRIVE_ENDS, END_CHAMFER_LENGTH
from standardparts.standards.iso2351 import ISO2351, layout
from standardparts.standards.iso2351_data import (
    BIT_LENGTH,
    COMBINATIONS,
    PROOF_TORQUE,
    TIP_LENGTH,
)
from standardparts.standards.iso2936_data import SIZES as KEY_SIZES

BIT = ISO2351()
ALL = [(s, d) for s, drives in COMBINATIONS.items() for d in drives]


def test_tables():
    assert set(BIT_LENGTH) == set(DRIVE_ENDS)
    assert list(COMBINATIONS) == list(TIP_LENGTH) == list(PROOF_TORQUE)
    assert len(ALL) == 61  # crosses in Table 1
    for s, drives in COMBINATIONS.items():
        assert s in KEY_SIZES
        assert set(drives) <= set(BIT_LENGTH)
    # Every drive end is used by some tip.
    assert {d for _, d in ALL} == set(BIT_LENGTH)
    # The minimum tip length grows with s.
    assert list(TIP_LENGTH.values()) == sorted(TIP_LENGTH.values())


@pytest.mark.parametrize("de", DRIVE_ENDS.values(), ids=list(DRIVE_ENDS))
def test_drive_end_rows(de):
    if de.hexagon:
        assert de.s1_min < de.s1_max < de.e1_min < de.e1_max
        # Corners turned below the sharp hexagon (about 1.13 s).
        assert de.e1_max < 2 * de.s1_max / math.sqrt(3)
        assert de.e1_min == pytest.approx(1.13 * de.s1_min, abs=0.02)
    if de.form == "A":
        # Turned hexagon inside the collar; the groove cuts the collar.
        assert de.e1_max < de.d1 and de.d3 < de.d1
        assert de.l5 < de.l3 - de.r < de.l3 + de.r < de.l1 - 0.6
    if de.form == "C" and de.d3 is not None:
        # The V groove only notches the corners.
        assert de.s1_max < de.d3 < de.e1_min
    if de.form == "E":
        assert de.d3 < de.s1_min
    if de.form == "G":
        assert de.d3 < de.d1 and de.e1_max < de.d1
        assert de.l5 < de.l3 < de.l1
    assert de.l3 < de.l1


@pytest.mark.parametrize("de", DRIVE_ENDS.values(), ids=list(DRIVE_ENDS))
def test_drive_end_features(de):
    L = 40.0
    part = drive_end_shank(de, 0.0, L)
    assert part.is_valid and len(part.solids()) == 1
    assert part.bounding_box().max.Z == pytest.approx(L, abs=1e-6)
    zg = L - de.l3
    if de.form == "A":
        r1 = de.d1 / 2
        assert part.is_inside(Vector(r1 - 0.05, 0, zg - de.r - 0.3))
        assert not part.is_inside(Vector(de.d3 / 2 + 0.05, 0, zg))
        assert part.is_inside(Vector(de.d3 / 2 - 0.05, 0, zg))
        # Shoulder at l1, hexagon at the end (corner on +X).
        assert part.is_inside(Vector(shank_radius(de) - 0.05, 0, L - de.l1 - 0.1))
        assert not part.is_inside(Vector(r1 + 0.05, 0, L - de.l1 + 1))
        assert not part.is_inside(Vector(de.e1_max / 2 + 0.02, 0, L - 3))
        assert part.is_inside(Vector(de.e1_max / 2 - 0.05, 0, L - 3))
    if de.form == "C":
        if de.d3 is None:
            assert not part.is_inside(Vector(0, 0, zg))            # cross hole
            assert part.is_inside(Vector(0, 0, zg - 1.5))
        else:
            # Corner (on +X) notched to d3, flats untouched.
            assert not part.is_inside(Vector(de.d3 / 2 + 0.05, 0, zg))
            assert part.is_inside(Vector(de.d3 / 2 - 0.05, 0, zg))
            assert part.is_inside(Vector(0, de.s1_max / 2 - 0.02, zg))
            assert part.is_inside(Vector(de.e1_max / 2 - 0.05, 0, zg - 2))
    if de.form == "E":
        zf = zg - de.l7 / 2  # middle of the flat groove bottom
        assert not part.is_inside(Vector(0, de.d3 / 2 + 0.05, zf))
        assert part.is_inside(Vector(0, de.d3 / 2 - 0.05, zf))
        assert part.is_inside(Vector(0, de.s1_max / 2 - 0.05, zg - de.l7 - de.r - 0.2))
    if de.form == "G":
        assert not part.is_inside(Vector(0, de.d3 / 2 + 0.05, zg))
        assert part.is_inside(Vector(0, de.d3 / 2 - 0.05, zg))
        # Flats facing +-X near the end, full cylinder below them.
        half = (de.e1_max + de.e1_min) / 4
        z_flat = L - (de.l3 - de.l5) / 2
        assert not part.is_inside(Vector(half + 0.05, 0, z_flat))
        assert part.is_inside(Vector(half - 0.05, 0, z_flat))
        assert part.is_inside(Vector(0, de.d1 / 2 - 0.05, z_flat))
        assert part.is_inside(Vector(de.d1 / 2 - 0.05, 0, L - (de.l3 - de.l5) - 1))
    if de.hexagon:
        # End chamfer: the corner is cut back on the end face only.
        r = de.e1_max / 2
        assert not part.is_inside(Vector(r - 0.1, 0, L - 0.05))
        assert part.is_inside(Vector(r - 0.05, 0, L - END_CHAMFER_LENGTH - 0.1))


@pytest.mark.parametrize("s,drive", ALL, ids=[f"{d}-{s}" for s, d in ALL])
def test_every_bit_builds(s, drive):
    p = BIT.validate({"drive": drive, "size": s})
    part = BIT.build(p)
    de, kd = DRIVE_ENDS[drive], KEY_SIZES[s]
    lay = layout(s, drive)
    assert part.label == BIT.designation(p)
    assert part.is_valid and len(part.solids()) == 1
    bb = part.bounding_box()
    assert bb.min.Z == pytest.approx(0, abs=1e-6)
    assert bb.max.Z == pytest.approx(BIT_LENGTH[drive], abs=1e-6)
    # The taper ends before the ISO 1173 drive end starts.
    assert lay.taper_end <= lay.length - de.l1
    # Tip: hexagon s with flats facing +-Y over l2 min.
    z = lay.tip_length / 2
    assert part.is_inside(Vector(0, kd.s / 2 - 0.02, z))
    assert not part.is_inside(Vector(0, kd.s / 2 + 0.02, z))
    assert not part.is_inside(Vector(kd.e_max / 2 + 0.02, 0, z))
    # Drive end at full section just below its end chamfer.
    z_d = lay.length - 2.5
    if de.hexagon:
        assert part.is_inside(Vector(0, de.s1_max / 2 - 0.02, z_d))
        assert not part.is_inside(Vector(0, de.s1_max / 2 + 0.02, z_d))
    else:
        assert part.is_inside(Vector(0, de.d1 / 2 - 0.02, z_d))
    # The shank is never thinner than the tip.
    if lay.tip_in_shank:
        z_mid = (lay.taper_end + lay.length - de.l1) / 2
        assert part.is_inside(Vector(0, min(kd.s, de.s1_max or kd.s) / 2 - 0.02, z_mid))


def test_step_roundtrip():
    p = BIT.validate({"drive": "E6.3", "size": "4"})
    part = BIT.build(p)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bit.stp"
        export_step(part, path)
        assert b"Bit ISO 2351-3 E 6,3 - 4" in path.read_bytes()
        imported = import_step(path)
    assert imported.is_valid
    assert imported.volume == pytest.approx(part.volume, rel=1e-6)


def test_api_surface():
    assert BIT.category == "Tools"
    params = {p.name: p for p in BIT.parameters()}
    assert set(params) == {"drive", "size"}
    assert [o.value for o in params["drive"].options] == list(BIT_LENGTH)
    assert [o.value for o in params["size"].options] == list(TIP_LENGTH)
    p = BIT.validate({})
    assert p == {"drive": "C6.3", "size": "5"}
    assert BIT.designation(p) == "Bit ISO 2351-3 C 6,3 - 5"
    assert BIT.file_stem(p) == "ISO2351-3_C6.3-5"
    # Example of ISO 2351-3 clause 6.
    p = BIT.validate({"drive": "E11.2", "size": "6"})
    assert BIT.designation(p) == "Bit ISO 2351-3 E 11,2 - 6"
    dims = {d.symbol: d.value for d in BIT.dimensions(p)}
    assert dims["l1"] == 55 and dims["l2"] == 9 and dims["Md"] == 61
    assert BIT.notes(p)
    p = BIT.validate({"drive": "E8", "size": "8"})
    assert any("not recommended" in n for n in BIT.notes(p))
    assert any("wider than the drive end" in n for n in BIT.notes(p))


@pytest.mark.parametrize("raw", [
    {"drive": "C6.3", "size": "0.7"},   # not a combination of Table 1
    {"drive": "A3", "size": "4"},
    {"drive": "C12.5", "size": "11"},   # no such tip size
    {"drive": "F6.3", "size": "4"},     # F is a female drive end
])
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        BIT.validate(raw)

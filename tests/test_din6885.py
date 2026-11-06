import tempfile
from io import BytesIO
from pathlib import Path

import pytest
from build123d import Unit, Vector, export_step, import_step

from standardparts.standards.base import ParameterError
from standardparts.standards.din6885 import DIN6885, FORMS, edge_radius, key_volume
from standardparts.standards.din6885_data import LENGTH_SERIES, SIZES

DIN = DIN6885()
STEEL = 7.85e-3  # g / mm^3

# Form B masses in kg per 1000 pieces from fasten.it's DIN 6885-1 table
# (steel, 7.85 kg/dm3): (size, length) -> mass. Its masses for 56 x 32 to
# 70 x 36 sit 3 to 8 % below b h l rho, so none of those rows is used.
TABLE_MASS = {
    ("2x2", 20): 0.628,
    ("5x5", 32): 6.28,
    ("8x7", 40): 17.6,
    ("12x8", 32): 24.1,
    ("22x14", 250): 604,
    ("36x20", 400): 2260,
    ("100x50", 400): 15700,
}


@pytest.mark.parametrize("kd", SIZES.values(), ids=list(SIZES))
def test_data_rows_are_consistent(kd):
    assert kd.t1 < kd.h
    # Back clearance in the hub keyway, interference with the tight depth.
    assert 0.1 <= kd.t1 + kd.t2 - kd.h <= 0.6
    assert kd.t1 + kd.t2_tight < kd.h
    assert kd.t2_tight < kd.t2
    assert kd.s_min < kd.s_max
    assert 2 * kd.s_max < kd.h
    assert kd.l_min in LENGTH_SERIES and kd.l_max in LENGTH_SERIES
    assert kd.l_min > kd.b  # form A needs straight sides
    assert kd.d_over < kd.d_to
    assert kd.standard_lengths()[0] == kd.l_min
    assert kd.standard_lengths()[-1] == kd.l_max
    for tol in (kd.t1_tol, kd.t2_tol, kd.t2_tight_tol):
        assert tol == (0.1 if kd.b <= 6 else 0.2 if kd.b <= 32 else 0.3)


def test_shaft_ranges_are_contiguous():
    rows = list(SIZES.values())
    assert rows[0].d_over == 6 and rows[-1].d_to == 500
    for a, b in zip(rows, rows[1:]):
        assert a.d_to == b.d_over
        assert a.b < b.b and a.h <= b.h
        assert a.l_min <= b.l_min and a.l_max <= b.l_max


def cases():
    for size, kd in SIZES.items():
        lengths = kd.standard_lengths()
        for l in sorted({lengths[0], lengths[len(lengths) // 2], lengths[-1]}):
            for form in FORMS:
                yield size, l, form


@pytest.mark.parametrize("size,l,form", list(cases()))
def test_key_solid(size, l, form):
    kd = SIZES[size]
    params = DIN.validate({"size": size, "length": l, "form": form})
    part = DIN.build(params)
    assert part.is_valid
    assert len(part.solids()) == 1
    assert part.label == DIN.designation(params)
    bb = part.bounding_box()
    tol = 1e-6 * l
    assert (bb.min.X, bb.max.X) == pytest.approx((-l / 2, l / 2), abs=tol)
    assert (bb.min.Y, bb.max.Y) == pytest.approx((-kd.b / 2, kd.b / 2), abs=tol)
    assert (bb.min.Z, bb.max.Z) == pytest.approx((0, kd.h), abs=tol)
    assert part.volume == pytest.approx(key_volume(kd, l, form), rel=1e-6)

    r = edge_radius(kd)
    z = kd.h / 2
    assert part.is_inside(Vector(0, 0, z))
    # Ends: a round end leaves the corner region empty, a square end fills
    # it up to the edge rounding.
    # Form AB: round end at -X, square end at +X.
    for x_sign, square in ((1, form in ("B", "AB")), (-1, form == "B")):
        corner = Vector(x_sign * (l / 2 - 0.1 * r), kd.b / 2 - 0.1 * r, z)
        assert not part.is_inside(corner)
        inner = Vector(x_sign * (l / 2 - 1.5 * r), kd.b / 2 - 1.5 * r, z)
        assert part.is_inside(inner) == square
    # Round ends reach the full length on the centre line.
    assert part.is_inside(Vector(l / 2 - 0.5 * r, 0, z))
    assert part.is_inside(Vector(-l / 2 + 0.5 * r, 0, z))


@pytest.mark.parametrize("size,l", list(TABLE_MASS))
def test_mass_matches_table(size, l):
    model = key_volume(SIZES[size], l, "B") * STEEL
    assert model == pytest.approx(TABLE_MASS[size, l], rel=0.03)


@pytest.mark.parametrize(
    "raw",
    [
        {"size": "7x7", "length": 20},
        {"size": "8x7", "length": 17},
        {"size": "8x7", "length": 91},
        {"size": "8x7", "length": "abc"},
        {"size": "8x7", "length": "nan"},
        {"size": "8x7", "length": 40, "form": "C"},
    ],
)
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        DIN.validate(raw)


def test_validation_normalises():
    assert DIN.validate({}) == {"size": "8x7", "length": 40.0, "form": "A"}
    p = DIN.validate({"size": "8 × 7", "length": "40", "form": "ab"})
    assert p == {"size": "8x7", "length": 40.0, "form": "AB"}
    assert DIN.validate({"size": "8.0x7"})["size"] == "8x7"


def test_designation_and_file_stem():
    p = DIN.validate({"size": "8x7", "length": 40, "form": "A"})
    assert DIN.designation(p) == "DIN 6885 A 8 x 7 x 40"
    assert DIN.file_stem(p) == "DIN6885_A_8x7x40"
    p = DIN.validate({"size": "100x50", "length": 312.5, "form": "AB"})
    assert DIN.file_stem(p) == "DIN6885_AB_100x50x312.5"


def test_custom_length_is_flagged():
    p = DIN.validate({"size": "8x7", "length": 41})
    assert any("not a standard length" in n for n in DIN.notes(p))
    part = DIN.build(p)
    assert part.is_valid and part.bounding_box().size.X == pytest.approx(41)


def test_dimension_table_has_keyway():
    p = DIN.validate({"size": "8x7", "length": 40})
    dims = {d.symbol: d.value for d in DIN.dimensions(p)}
    assert dims["t1"] == "4 +0.2"
    assert dims["t2"] == "3.3 +0.2"
    assert dims["d1"] == "22 … 30"
    assert dims["lt"] == 32


def test_parameter_schema():
    params = {p.name: p for p in DIN.parameters()}
    assert params["size"].default in SIZES
    length = params["length"]
    assert length.kind == "length" and length.depends_on == "size"
    assert set(length.preferred) == set(SIZES) == set(length.limits)
    assert length.default in length.preferred[params["size"].default]
    assert [o.value for o in params["form"].options] == list(FORMS)
    DIN.describe_json()


def test_step_roundtrip():
    p = DIN.validate({"size": "8x7", "length": 40, "form": "A"})
    part = DIN.build(p)
    buf = BytesIO()
    export_step(part, buf, unit=Unit.MM)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "key.stp"
        path.write_bytes(buf.getvalue())
        imported = import_step(path)
    assert imported.is_valid
    assert imported.volume == pytest.approx(part.volume, rel=1e-6)

import math
import tempfile
from pathlib import Path

import pytest
from build123d import Vector, export_step, import_step

from standardparts.standards import ParameterError
from standardparts.standards.iso3601 import ISO3601, torus_volume
from standardparts.standards.iso3601_data import (
    CROSS_SECTIONS,
    SIZES,
    UNVERIFIED_CODES,
    class_b_tolerance,
    find,
    metric_code,
)

ORING = ISO3601()

# Class B tolerances printed in the ISO 3601-1:2012 preview (Tables 1 to 3).
PREVIEW_CLASS_B = {
    0.74: .12, 1.07: .12, 1.42: .12,
    2.57: .13, 3.68: .14, 6.07: .16, 7.65: .17, 9.25: .18, 10.82: .20, 12.42: .21,
    14.0: .22, 15.6: .23, 17.17: .24, 18.77: .26, 20.35: .27, 21.95: .28, 23.52: .29,
    25.12: .30, 26.7: .31, 28.3: .33, 29.87: .34, 31.47: .35, 33.05: .36, 34.65: .37,
    37.82: .39, 41.0: .42, 44.17: .44, 47.35: .46, 50.52: .48, 53.7: .51, 56.87: .53,
    60.05: .55, 63.22: .57, 66.4: .59, 69.57: .62, 72.75: .64, 75.92: .66, 82.27: .70,
    88.62: .75, 94.97: .79, 101.32: .83, 107.67: .88, 114.02: .92, 120.37: .96,
    126.72: 1.01, 133.07: 1.05,
    1.24: .12, 2.06: .13, 3.63: .14, 6.02: .16, 7.59: .17, 9.19: .18, 10.77: .20,
    12.37: .21, 13.94: .22, 15.54: .23, 17.12: .24, 18.72: .26, 20.29: .27, 21.89: .28,
    23.47: .29, 25.07: .30, 26.64: .31, 28.24: .33, 29.82: .34, 31.42: .35, 32.99: .36,
    34.59: .37, 36.17: .38, 37.77: .39, 39.34: .40, 40.94: .42, 42.52: .43, 44.12: .44,
    45.69: .45, 47.29: .46,
}

# Inch series: code ranges per cross-section (AS568 dash numbers).
INCH_CODES = {"1.02": ("001", "001"), "1.27": ("002", "002"), "1.52": ("003", "003"),
              "1.78": ("004", "050"), "2.62": ("102", "178"), "3.53": ("201", "284"),
              "5.33": ("309", "395"), "6.99": ("425", "475")}


def test_class_b_formula():
    for d1, tol in PREVIEW_CLASS_B.items():
        assert class_b_tolerance(d1) == tol, d1


def test_tables():
    assert set(SIZES) == set(CROSS_SECTIONS)
    total = 0
    for key, rows in SIZES.items():
        cs = CROSS_SECTIONS[key]
        assert float(key) == cs.d2
        d1s = [r.d1 for r in rows]
        assert d1s == sorted(d1s) and len(set(d1s)) == len(d1s)
        tols = [r.tol for r in rows]
        assert tols == sorted(tols), key            # tolerance grows with d1
        assert len({r.code for r in rows}) == len(rows)
        if cs.family == "metric":
            for r in rows:
                assert r.code == metric_code(cs.letter, r.d1)
                # Close to the ISO 3601-1:2002 series A formula (0.13 floor).
                formula = max(0.13, 0.007 * r.d1 ** 0.96 + 0.09)
                assert r.tol == pytest.approx(formula, abs=0.011), r.code
        else:
            first, last = INCH_CODES[key]
            assert (rows[0].code, rows[-1].code) == (first, last)
            assert all(len(r.code) == 3 and r.code.isdigit() for r in rows)
            codes = [int(r.code) for r in rows]
            assert codes == sorted(codes)
            for r in rows:
                # Class B is the wider class except at the smallest sizes (e.g. 102:
                # A 0.13, B 0.12).
                assert class_b_tolerance(r.d1) >= r.tol - 0.011
        total += len(rows)
    assert len(SIZES["1.78"]) == 47 and len(SIZES["2.62"]) == 77
    assert len(SIZES["3.53"]) == 84 and len(SIZES["5.33"]) == 87
    assert len(SIZES["6.99"]) == 51
    # Metric tolerances depend on d1 only: the same in every series.
    by_d1 = {}
    for key, rows in SIZES.items():
        if CROSS_SECTIONS[key].family == "metric":
            for r in rows:
                assert by_d1.setdefault(r.d1, r.tol) == r.tol, r.code
    assert total == 349 + 378
    assert UNVERIFIED_CODES <= {r.code for r in SIZES["7"]}


def test_known_rows():
    # Designation examples of the standard and spot checks.
    assert find("1.78", 7.65).code == "011"
    assert find("2.62", 32.99).code == "125"
    assert find("3.55", 54.5).code == "C0545"
    assert find("5.3", 125).code == "D1250"
    assert find("3.55", 63).code == "C0630"       # Machinery's Handbook example
    assert find("6.99", 253.37).code == "449"     # Prepol misprint corrected
    assert find("3.53", 63.09).code == "230"
    assert find("2.65", 20).tol == 0.21
    assert find("1.8", 12.5).code == "A0125"
    assert find("1.8", 2.24).code == "A0022"
    assert find("2.65", 20.5) is None


@pytest.mark.parametrize("key", list(SIZES))
def test_every_oring_builds(key):
    cs = CROSS_SECTIONS[key]
    for row in SIZES[key]:
        p = ORING.validate({"d2": key, "d1": row.d1})
        part = ORING.build(p)
        assert part.label == ORING.designation(p)
        assert row.code in part.label
        assert part.is_valid
        assert len(part.solids()) == 1
        bb = part.bounding_box()
        D = row.d1 + 2 * cs.d2
        assert bb.size.X == pytest.approx(D, abs=1e-6)
        assert bb.size.Y == pytest.approx(D, abs=1e-6)
        assert bb.min.Z == pytest.approx(-cs.d2 / 2, abs=1e-6)
        assert bb.max.Z == pytest.approx(cs.d2 / 2, abs=1e-6)
        assert part.volume == pytest.approx(torus_volume(row.d1, cs.d2), rel=1e-6)


def test_shape():
    part = ORING.build(ORING.validate({"d2": "2.65", "d1": 20}))
    R = (20 + 2.65) / 2
    assert part.is_inside(Vector(R, 0, 0))
    assert part.is_inside(Vector(0, -R, 0))
    assert not part.is_inside(Vector(0, 0, 0))
    assert not part.is_inside(Vector(10 - 0.01, 0, 0))   # inside diameter is clear
    assert part.is_inside(Vector(10 + 0.01, 0, 0))
    assert not part.is_inside(Vector(R, 0, 1.33))
    assert torus_volume(20, 2.65) == pytest.approx(2 * math.pi ** 2 * R * 1.325 ** 2)


def test_custom_d1_builds_and_is_flagged():
    p = ORING.validate({"d2": "2.65", "d1": 20.5})
    part = ORING.build(p)
    assert part.is_valid and len(part.solids()) == 1
    assert ORING.designation(p) == "O-ring 20.5 x 2.65 (non-standard d1)"
    assert any("not a standard size" in n for n in ORING.notes(p))
    dims = {d.symbol: d.value for d in ORING.dimensions(p)}
    assert dims["d1 tol. ±"] == class_b_tolerance(20.5)


def test_unverified_sizes_are_flagged():
    p = ORING.validate({"d2": "7", "d1": 670})
    assert any("one secondary source" in n for n in ORING.notes(p))
    p = ORING.validate({"d2": "7", "d1": 400})
    assert not any("one secondary source" in n for n in ORING.notes(p))


def test_step_roundtrip():
    part = ORING.build(ORING.validate({"d2": "2.65", "d1": 20}))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "oring.stp"
        export_step(part, path)
        assert b"O-ring ISO 3601-1A - B0200 - 20 x 2.65" in path.read_bytes()
        imported = import_step(path)
    assert imported.is_valid
    assert imported.volume == pytest.approx(part.volume, rel=1e-6)


def test_api_surface():
    assert ORING.category == "Seals"
    params = {p.name: p for p in ORING.parameters()}
    assert set(params) == {"d2", "d1"}
    assert params["d2"].kind == "select" and params["d1"].kind == "length"
    assert params["d1"].depends_on == "d2"
    assert [o.value for o in params["d2"].options] == list(CROSS_SECTIONS)
    for k, rows in SIZES.items():
        assert params["d1"].preferred[k] == [r.d1 for r in rows]
        assert params["d1"].limits[k] == [rows[0].d1, rows[-1].d1]
    p = ORING.validate({})
    assert p == {"d2": "2.65", "d1": 20}
    assert ORING.designation(p) == "O-ring ISO 3601-1A - B0200 - 20 x 2.65"
    assert ORING.file_stem(p) == "ISO3601-1_20x2.65"
    p = ORING.validate({"d2": "3.53", "d1": "24.99"})
    assert ORING.designation(p) == "O-ring ISO 3601-1 - 214 - 24.99 x 3.53"
    assert ORING.file_stem(p) == "ISO3601-1_24.99x3.53"
    dims = {d.symbol: d.value for d in ORING.dimensions(p)}
    assert dims["AS568"] == "-214"
    assert dims["d1 tol. A ±"] == 0.25 and dims["d1 tol. B ±"] == 0.30
    dims = {d.symbol: d.value for d in ORING.dimensions(ORING.validate({"d2": "2.62", "d1": 32.99}))}
    assert dims["d2 tol. A ±"] == 0.08 and dims["d2 tol. B ±"] == 0.09
    # d2 given as a number is accepted.
    assert ORING.validate({"d2": 7.0, "d1": 200})["d2"] == "7"
    assert ORING.validate({"d2": "1.80", "d1": 20})["d2"] == "1.8"
    assert ORING.file_stem(ORING.validate({"d2": "7", "d1": 200})) == "ISO3601-1_200x7"
    assert ORING.notes(p)
    assert ORING.describe_json()["parameters"]


@pytest.mark.parametrize(
    "raw",
    [
        {"d2": "2.5", "d1": 20},
        {"d2": "x", "d1": 20},
        {"d2": "2.65", "d1": 4.4},
        {"d2": "2.65", "d1": 251},
        {"d2": "2.65", "d1": "x"},
        {"d2": "2.65", "d1": "nan"},
        {"d2": "1.02", "d1": 1},
    ],
)
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        ORING.validate(raw)

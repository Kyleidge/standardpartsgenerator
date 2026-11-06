import math

import pytest
from build123d import Vector

from standardparts.standards import ParameterError
from standardparts.standards.iso7089_data import ISO7089_SIZES
from standardparts.standards.iso7092 import ISO7092, ISO7093
from standardparts.standards.iso7092_data import ISO7092_SIZES, ISO7093_SIZES

W92 = ISO7092()
W93 = ISO7093()
NON_PREFERRED = {"3.5", "14", "18", "22", "27", "33"}
ISO7092_LIST = ["1.6", "2", "2.5", "3", "3.5", "4", "5", "6", "8", "10", "12", "14", "16",
                "18", "20", "22", "24", "27", "30", "33", "36"]
ISO7093_LIST = ["3", "3.5", "4", "5", "6", "8", "10", "12", "14", "16", "18", "20", "22",
                "24", "27", "30", "33", "36"]

# ISO 4759-3 product grade A tolerances, as the tables apply them:
# d1 is +IT13 or +IT14, d2 is -IT14 or -IT15 (ISO 286 values).
IT13 = [(3, 0.14), (6, 0.18), (10, 0.22), (18, 0.27), (30, 0.33), (50, 0.39)]
IT14 = [(3, 0.25), (6, 0.30), (10, 0.36), (18, 0.43), (30, 0.52), (50, 0.62), (80, 0.74), (120, 0.87)]
IT15 = [(80, 1.2), (120, 1.4)]


def it(table, x):
    for limit, tol in table:
        if x <= limit:
            return tol
    raise AssertionError(x)


def test_size_lists():
    assert list(ISO7092_SIZES) == ISO7092_LIST
    assert list(ISO7093_SIZES) == ISO7093_LIST


@pytest.mark.parametrize("std", [W92, W93], ids=["7092", "7093-1"])
def test_rows_are_consistent(std):
    for size, wd in std.sizes.items():
        assert wd.preferred == (size not in NON_PREFERRED)
        assert wd.d < wd.d1_min < wd.d1_max < wd.d2_min < wd.d2_max
        assert wd.h_min < wd.h_nom < wd.h_max
        assert wd.h_max - wd.h_nom == pytest.approx(wd.h_nom - wd.h_min)
        # d1 tolerance is IT13 or IT14 of d1 (ISO 4759-3).
        tol1 = wd.d1_max - wd.d1_min
        assert tol1 == pytest.approx(it(IT13, wd.d1_min), abs=1e-9) or tol1 == pytest.approx(
            it(IT14, wd.d1_min), abs=1e-9
        )
        tol2 = wd.d2_max - wd.d2_min
        assert tol2 == pytest.approx(it(IT14, wd.d2_max), abs=1e-9) or tol2 == pytest.approx(
            it(IT15, wd.d2_max), abs=1e-9
        )
        # Small series < normal series (ISO 7089) < large series.
        if size in ISO7089_SIZES:
            normal = ISO7089_SIZES[size]
            if std is W92:
                assert wd.d2 < normal.d2 and wd.h <= normal.h and wd.d1 == normal.d1
            else:
                assert wd.d2 > normal.d2 and wd.h >= normal.h and wd.d1 >= normal.d1


def check_washer(std, size):
    wd = std.sizes[size]
    part = std.build(std.validate({"size": size}))
    assert part.is_valid
    assert len(part.solids()) == 1
    assert part.label == f"ISO {std.number} - {size}"
    bb = part.bounding_box()
    tol = 1e-6 * wd.d2
    assert bb.size.X == pytest.approx(wd.d2, abs=tol)
    assert bb.size.Y == pytest.approx(wd.d2, abs=tol)
    assert bb.min.Z == pytest.approx(0, abs=tol)
    assert bb.max.Z == pytest.approx(wd.h, abs=tol)
    r1, r2, h = wd.d1 / 2, wd.d2 / 2, wd.h
    assert not part.is_inside(Vector(0, 0, h / 2))
    assert not part.is_inside(Vector(0.98 * r1, 0, h / 2))
    assert part.is_inside(Vector(1.02 * r1, 0, h / 2))
    assert part.is_inside(Vector(0, (r1 + r2) / 2, h / 2))
    assert part.is_inside(Vector(0.995 * r2, 0, 0.99 * h))
    assert not part.is_inside(Vector(1.01 * r2, 0, h / 2))
    expected = math.pi * (r2**2 - r1**2) * h
    assert part.volume == pytest.approx(expected, rel=1e-6)


@pytest.mark.parametrize("size", ISO7092_LIST)
def test_iso7092_washer(size):
    check_washer(W92, size)


@pytest.mark.parametrize("size", ISO7093_LIST)
def test_iso7093_washer(size):
    check_washer(W93, size)


def test_table_spot_values():
    assert (lambda w: (w.d1, w.d2, w.h))(ISO7092_SIZES["8"]) == (8.4, 15, 1.6)
    assert (lambda w: (w.d1, w.d2, w.h))(ISO7092_SIZES["18"]) == (19, 30, 3)
    assert (lambda w: (w.d1, w.d2, w.h))(ISO7093_SIZES["8"]) == (8.4, 24, 2)
    assert (lambda w: (w.d1, w.d2, w.h))(ISO7093_SIZES["30"]) == (33, 92, 6)
    assert (lambda w: (w.d1, w.d2, w.h))(ISO7093_SIZES["36"]) == (39, 110, 8)


@pytest.mark.parametrize(
    "std,raw",
    [
        (W92, {"size": "1"}),
        (W92, {"size": "39"}),
        (W93, {"size": "2.5"}),
        (W93, {"size": "1.6"}),
        (W93, {"size": "42"}),
        (W93, {"size": "abc"}),
    ],
)
def test_validation_rejects(std, raw):
    with pytest.raises(ParameterError):
        std.validate(raw)


def test_designation_and_files():
    p = W92.validate({"size": "8"})
    assert p == {"size": "8"}
    assert W92.designation(p) == "ISO 7092 - 8"
    assert W92.file_stem(p) == "ISO7092_8"
    assert W92.validate({"size": "M8"}) == p
    q = W93.validate({"size": "M8"})
    assert W93.designation(q) == "ISO 7093-1 - 8"
    assert W93.file_stem(q) == "ISO7093-1_8"
    assert W92.file_stem(W92.validate({"size": "1.6"})) == "ISO7092_1.6"
    for std in (W92, W93):
        assert std.category == "Washers"
        assert {par.kind for par in std.parameters()} <= {"select", "length"}
        assert [o.value for o in std.parameters()[0].options] == list(std.sizes)
        assert std.parameters()[0].default in std.sizes


def test_notes_and_dimensions():
    notes = " ".join(W93.notes({"size": "14"}))
    assert "non-preferred" in notes and "200 HV" in notes and "ISO 7093-1" in notes
    assert "chamfer" not in " ".join(W92.notes({"size": "8"}))
    dims = {d.symbol: d.value for d in W93.dimensions({"size": "8"})}
    assert (dims["d1"], dims["d2"], dims["h"]) == (8.4, 24, 2)
    assert (dims["d1 max"], dims["d2 min"], dims["h max"], dims["h min"]) == (8.62, 23.48, 2.2, 1.8)

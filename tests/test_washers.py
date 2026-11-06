import math

import pytest
from build123d import Vector

from standardparts.standards import ParameterError
from standardparts.standards.iso7089 import ISO7089, ISO7090, chamfer_size
from standardparts.standards.iso7089_data import (
    CHAMFER_ANGLE,
    CHAMFER_HEIGHT,
    ISO7089_SIZES,
    ISO7090_SIZES,
)

W89 = ISO7089()
W90 = ISO7090()
NON_PREFERRED = {"3.5", "14", "18", "22", "27", "33", "39", "45", "52", "60"}

# ISO 887:2000 Table 3, normal series, product grade A: (d1, d2, h).
ISO887_NORMAL = {
    "1.6": (1.7, 4, 0.3), "2": (2.2, 5, 0.3), "2.5": (2.7, 6, 0.5), "3": (3.2, 7, 0.5),
    "3.5": (3.7, 8, 0.5), "4": (4.3, 9, 0.8), "5": (5.3, 10, 1), "6": (6.4, 12, 1.6),
    "8": (8.4, 16, 1.6), "10": (10.5, 20, 2), "12": (13, 24, 2.5), "14": (15, 28, 2.5),
    "16": (17, 30, 3), "18": (19, 34, 3), "20": (21, 37, 3), "22": (23, 39, 3),
    "24": (25, 44, 4), "27": (28, 50, 4), "30": (31, 56, 4), "33": (34, 60, 5),
    "36": (37, 66, 5), "39": (42, 72, 6), "42": (45, 78, 8), "45": (48, 85, 8),
    "48": (52, 92, 8), "52": (56, 98, 8), "56": (62, 105, 10), "60": (66, 110, 10),
    "64": (70, 115, 10),
}


@pytest.mark.parametrize("wd", ISO7089_SIZES.values(), ids=list(ISO7089_SIZES))
def test_rows_are_consistent(wd):
    assert (wd.d1, wd.d2, wd.h) == ISO887_NORMAL[wd.size]
    assert wd.preferred == (wd.size not in NON_PREFERRED)
    assert wd.d < wd.d1_min < wd.d1_max < wd.d2_min < wd.d2_max
    assert wd.h_min < wd.h_nom < wd.h_max
    assert wd.h_max - wd.h_nom == pytest.approx(wd.h_nom - wd.h_min)


def test_iso7090_sizes():
    assert list(ISO7090_SIZES) == [s for s in ISO7089_SIZES if float(s) >= 5]
    assert list(ISO7090_SIZES)[0] == "5" and list(ISO7090_SIZES)[-1] == "64"
    assert list(ISO7089_SIZES)[0] == "1.6" and list(ISO7089_SIZES)[-1] == "64"


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
    assert part.is_inside(Vector(0.99 * r2, 0, 0.1 * h))
    assert not part.is_inside(Vector(1.01 * r2, 0, h / 2))
    return part


@pytest.mark.parametrize("size", list(ISO7089_SIZES))
def test_iso7089_washer(size):
    part = check_washer(W89, size)
    wd = ISO7089_SIZES[size]
    expected = math.pi * ((wd.d2 / 2) ** 2 - (wd.d1 / 2) ** 2) * wd.h
    assert part.volume == pytest.approx(expected, rel=1e-6)
    # Sharp outer edge on both faces.
    assert part.is_inside(Vector(0.995 * wd.d2 / 2, 0, 0.99 * wd.h))


@pytest.mark.parametrize("size", list(ISO7090_SIZES))
def test_iso7090_washer(size):
    part = check_washer(W90, size)
    wd = ISO7090_SIZES[size]
    r2, h = wd.d2 / 2, wd.h
    dr, dz = chamfer_size(wd)
    assert dz == pytest.approx(CHAMFER_HEIGHT * h)
    assert dr / dz == pytest.approx(math.tan(math.radians(CHAMFER_ANGLE)))
    # Inside the standard's ranges: 30 to 45 deg, 0.25 h to 0.5 h.
    assert 30 <= CHAMFER_ANGLE <= 45 and 0.25 <= CHAMFER_HEIGHT <= 0.5
    ring = math.pi * (r2**2 - (wd.d1 / 2) ** 2) * h
    chamfer = 2 * math.pi * (r2 - dr / 3) * dr * dz / 2
    assert part.volume == pytest.approx(ring - chamfer, rel=1e-6)
    # Chamfer on the outer edge of the top face only.
    assert not part.is_inside(Vector(r2 - dr / 3, 0, h - dz / 3))
    assert part.is_inside(Vector(r2 - dr / 3, 0, dz / 3))
    assert part.is_inside(Vector(r2 - 1.2 * dr, 0, 0.99 * h))


@pytest.mark.parametrize(
    "std,raw",
    [
        (W89, {"size": "7"}),
        (W89, {"size": "1"}),
        (W90, {"size": "4"}),
        (W90, {"size": "1.6"}),
        (W90, {"size": "abc"}),
    ],
)
def test_validation_rejects(std, raw):
    with pytest.raises(ParameterError):
        std.validate(raw)


def test_designation_and_files():
    p = W89.validate({"size": "8"})
    assert p == {"size": "8"}
    assert W89.designation(p) == "ISO 7089 - 8"
    assert W89.file_stem(p) == "ISO7089_8"
    assert W89.validate({"size": "M8"}) == p
    assert W90.file_stem(W90.validate({"size": "64"})) == "ISO7090_64"
    assert W89.file_stem(W89.validate({"size": "1.6"})) == "ISO7089_1.6"
    assert W90.designation({"size": "10"}) == "ISO 7090 - 10"
    for std in (W89, W90):
        assert std.category == "Washers"
        assert {par.kind for par in std.parameters()} <= {"select", "length"}
        assert [o.value for o in std.parameters()[0].options] == list(std.sizes)
        assert std.parameters()[0].default in std.sizes


def test_notes_and_dimensions():
    notes = " ".join(W90.notes({"size": "14"}))
    assert "non-preferred" in notes and "chamfer" in notes and "200 HV" in notes
    assert "chamfer" not in " ".join(W89.notes({"size": "8"}))
    dims = {d.symbol: d.value for d in W89.dimensions({"size": "8"})}
    assert (dims["d1"], dims["d2"], dims["h"]) == (8.4, 16, 1.6)
    assert (dims["d1 max"], dims["d2 min"], dims["h max"], dims["h min"]) == (8.62, 15.57, 1.8, 1.4)
    dims90 = {d.symbol for d in W90.dimensions({"size": "8"})}
    assert {"chamfer", "chamfer h", "chamfer w"} <= dims90

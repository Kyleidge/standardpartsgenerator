import math
import tempfile
from pathlib import Path

import pytest
from build123d import Vector, export_step, import_step

from standardparts.standards import STANDARDS, ParameterError
from standardparts.standards.iso2936 import (
    ISO2936,
    build_key,
    centreline_length,
    end_chamfer,
)
from standardparts.standards.iso2936_data import SERIES, SIZES
from standardparts.tooling import hex_section

KEY = ISO2936()

# Sizes with long (M) and extra-long (L) keys in Table 1.
LONG_SIZES = {"1.3", "1.5", "2", "2.5", "3", "3.5", "4", "4.5", "5", "6", "7", "8", "9",
              "10", "11", "12", "13", "14", "15", "16", "17", "18"}
# Limit-deviation groups of Table 1 (lower deviation; the upper is 0).
L1_DEV = {**{s: -2 for s in ("0.7", "0.9", "1.3", "1.5", "2")},
          **{s: -4 for s in ("2.5", "3", "3.5", "4", "4.5", "5", "6")},
          **{s: -6 for s in ("7", "8", "9", "10", "11", "12")},
          **{s: -7 for s in ("13", "14", "15", "16", "17", "18", "19")},
          **{s: -12 for s in ("21", "22", "23", "24", "27", "29", "30", "32", "36")}}


def test_table():
    assert len(SIZES) == 34
    assert {s for s, kd in SIZES.items() if len(kd.l1) == 3} == LONG_SIZES
    assert all(set(kd.l1) in ({"standard"}, set(SERIES)) for kd in SIZES.values())
    assert {s: kd.l1_dev for s, kd in SIZES.items()} == L1_DEV
    prev = None
    for s, kd in SIZES.items():
        # s max is the nominal size from 1.5 up (0.71, 0.89, 1.27 below).
        if kd.s_max >= 1.5:
            assert float(s) == kd.s_max
        else:
            assert abs(float(s) - kd.s_max) < 0.035
        assert kd.s_min < kd.s_max and kd.e_min < kd.e_max
        # e max = 1.14 s max - 0.03 (footnote a, 1.5 <= s <= 36).
        if kd.s >= 1.5:
            assert kd.e_max == pytest.approx(1.14 * kd.s_max - 0.03, abs=0.006)
        # e min = 1.13 s min (footnote a, 8 <= s <= 36).
        if kd.s >= 8:
            assert kd.e_min == pytest.approx(1.13 * kd.s_min, abs=0.006)
        # Corners are always below the sharp hexagon.
        assert kd.e_max < 2 * kd.s / math.sqrt(3)
        assert kd.l2_dev == (-2 if kd.s <= 12 else -3 if kd.s <= 19 else -5)
        # Lengths grow with the size; the series are in order.
        lengths = [kd.l1[x] for x in SERIES if x in kd.l1]
        assert lengths == sorted(lengths)
        if prev is not None:
            assert kd.l1["standard"] >= prev.l1["standard"] and kd.l2 > prev.l2
        prev = kd
        # Both arms have a straight part after the bend.
        assert kd.l2 - kd.s - kd.bend_radius > 2
        assert kd.bend_radius == max(kd.s, 1.5)


def section_area(kd):
    return hex_section(kd.s, kd.e_max).area


@pytest.mark.parametrize("size", list(SIZES))
def test_every_key_builds(size):
    kd = SIZES[size]
    for series, l1 in kd.l1.items():
        p = KEY.validate({"size": size, "series": series})
        part = KEY.build(p)
        assert part.label == KEY.designation(p)
        assert part.is_valid and len(part.solids()) == 1
        bb = part.bounding_box()
        assert bb.min.Z == pytest.approx(0, abs=1e-6)
        assert bb.max.Z == pytest.approx(kd.l2, abs=1e-6)
        assert bb.min.X == pytest.approx(-kd.s / 2, abs=1e-6)
        assert bb.max.X == pytest.approx(l1 - kd.s / 2, abs=1e-6)
        # Corners point out of the plane of the bend.
        assert bb.size.Y == pytest.approx(kd.e_max, abs=1e-6)
        # Without the end chamfers the key is the section swept along the
        # centreline (Pappus: exact for the bend too).
        plain = build_key(kd, l1, chamfer=False)
        assert plain.volume == pytest.approx(section_area(kd) * centreline_length(kd, l1), rel=1e-9)
        removed = plain.volume - part.volume
        f = end_chamfer(kd)
        r_c = kd.e_max / 2
        # Each chamfer removes less than the ring of width f and length f.
        assert 0 < removed < 2 * math.pi * r_c * f * f


def test_shape():
    kd = SIZES["10"]
    part = build_key(kd, kd.l1["standard"])
    s, e, r = kd.s, kd.e_max, kd.bend_radius
    z = 10.0  # on the short arm
    # Two flats face +-X (across the bend), corners point along +-Y.
    assert part.is_inside(Vector(s / 2 - 0.05, 0, z))
    assert not part.is_inside(Vector(s / 2 + 0.05, 0, z))
    assert part.is_inside(Vector(0, e / 2 - 0.05, z))
    assert not part.is_inside(Vector(0, e / 2 + 0.05, z))
    # Long arm: flats face +-Z, its outside at z = l2.
    x = 80.0
    assert part.is_inside(Vector(x, 0, kd.l2 - 0.05))
    assert not part.is_inside(Vector(x, 0, kd.l2 + 0.05))
    assert part.is_inside(Vector(x, 0, kd.l2 - s + 0.05))
    assert not part.is_inside(Vector(x, 0, kd.l2 - s - 0.05))
    # Inner bend radius r around the bend centre.
    cx, cz = s / 2 + r, kd.l2 - s - r
    for a in (20, 45, 70):
        ux, uz = -math.cos(math.radians(a)), math.sin(math.radians(a))
        assert not part.is_inside(Vector(cx + (r - 0.05) * ux, 0, cz + (r - 0.05) * uz))
        assert part.is_inside(Vector(cx + (r + 0.05) * ux, 0, cz + (r + 0.05) * uz))
    # End chamfer at the short arm: the corner on the end face is gone, the
    # flat a little further in is not.
    f = end_chamfer(kd)
    assert not part.is_inside(Vector(0, e / 2 - 0.3 * f, 0.3 * f))
    assert part.is_inside(Vector(0, e / 2 - 0.05, 1.5 * f))


def test_step_roundtrip():
    p = KEY.validate({"size": "4", "series": "long"})
    part = KEY.build(p)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "key.stp"
        export_step(part, path)
        assert b"Socket screw key ISO 2936 - 4 M" in path.read_bytes()
        imported = import_step(path)
    assert imported.is_valid
    assert imported.volume == pytest.approx(part.volume, rel=1e-6)


def test_api_surface():
    assert STANDARDS["iso2936"] is not None
    assert KEY.category == "Tools"
    params = {p.name: p for p in KEY.parameters()}
    assert set(params) == {"size", "series"}
    assert [o.value for o in params["size"].options] == list(SIZES)
    p = KEY.validate({})
    assert p == {"size": "5", "series": "standard"}
    assert KEY.designation(p) == "Socket screw key ISO 2936 - 5"
    assert KEY.file_stem(p) == "ISO2936_5"
    p = KEY.validate({"size": "2.5", "series": "extra-long"})
    assert KEY.designation(p) == "Socket screw key ISO 2936 - 2.5 L"
    assert KEY.file_stem(p) == "ISO2936_2.5L"
    dims = {d.symbol: d.value for d in KEY.dimensions(p)}
    assert dims["l1"] == 114.5 and dims["l2"] == 20.5 and dims["r"] == 2.5
    assert KEY.notes(p)
    assert KEY.describe_json()["parameters"]


@pytest.mark.parametrize("raw", [
    {"size": "20"},
    {"size": "5", "series": "huge"},
    {"size": "0.7", "series": "long"},
    {"size": "36", "series": "extra-long"},
])
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        KEY.validate(raw)

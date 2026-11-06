import math
import tempfile
from pathlib import Path

import pytest
from build123d import Vector, export_step, import_step

from standardparts.standards import ParameterError
from standardparts.standards.iso2338 import ISO2338, chamfer_depth, expected_volume, length_tolerance
from standardparts.standards.iso2338_data import (
    CHAMFER_ANGLE,
    LENGTH_SERIES,
    SIZES,
    deviations_um,
)

PIN = ISO2338()

# ISO 2338:1997 Table 1: d -> (c, l_min, l_max), read from the rendered table.
TABLE = {
    "0.6": (0.12, 2, 6), "0.8": (0.16, 2, 8), "1": (0.2, 4, 10), "1.2": (0.25, 4, 12),
    "1.5": (0.3, 4, 16), "2": (0.35, 6, 20), "2.5": (0.4, 6, 24), "3": (0.5, 8, 30),
    "4": (0.63, 8, 40), "5": (0.8, 10, 50), "6": (1.2, 12, 60), "8": (1.6, 14, 80),
    "10": (2, 18, 95), "12": (2.5, 22, 140), "16": (3, 26, 180), "20": (3.5, 35, 200),
    "25": (4, 50, 200), "30": (5, 60, 200), "40": (6.3, 80, 200), "50": (8, 95, 200),
}


def test_table():
    assert {s: (p.c, p.l_min, p.l_max) for s, p in SIZES.items()} == TABLE
    prev_min = prev_max = 0
    for pd in SIZES.values():
        assert float(pd.size) == pd.d
        assert pd.l_min in LENGTH_SERIES and pd.l_max in LENGTH_SERIES
        # The chamfers at both ends never meet.
        assert 2 * pd.c < pd.l_min
        # The stepped range lines only move down the table.
        assert pd.l_min >= prev_min and pd.l_max >= prev_max
        prev_min, prev_max = pd.l_min, pd.l_max


def test_iso286_deviations():
    assert deviations_um(0.6, "m6") == (2, 8)
    assert deviations_um(3, "h8") == (-14, 0)
    assert deviations_um(4, "m6") == (4, 12)
    assert deviations_um(6, "m6") == (4, 12)
    assert deviations_um(8, "h8") == (-22, 0)
    assert deviations_um(50, "m6") == (9, 25)
    assert length_tolerance(10) == 0.25
    assert length_tolerance(12) == 0.5
    assert length_tolerance(55) == 0.75


def _lengths(pd):
    """Min, max and a sample in the middle of the preferred series."""
    std = pd.standard_lengths()
    return sorted({std[0], std[len(std) // 2], std[-1]})


@pytest.mark.parametrize("size", list(SIZES))
def test_every_size_builds(size):
    pd = SIZES[size]
    for l in _lengths(pd):
        p = PIN.validate({"size": size, "length": l})
        part = PIN.build(p)
        assert part.label == PIN.designation(p)
        assert part.is_valid
        assert len(part.solids()) == 1
        bb = part.bounding_box()
        assert bb.min.Z == pytest.approx(-l, abs=1e-6)
        assert bb.max.Z == pytest.approx(0, abs=1e-6)
        assert bb.size.X == pytest.approx(pd.d, abs=1e-6)
        assert bb.size.Y == pytest.approx(pd.d, abs=1e-6)
        assert part.volume == pytest.approx(expected_volume(pd, l), rel=1e-6)
        # Sanity: close to a plain cylinder.
        assert part.volume == pytest.approx(math.pi * pd.d ** 2 / 4 * l, rel=0.05)


def test_custom_length_builds_and_is_flagged():
    p = PIN.validate({"size": "6", "length": 31})
    part = PIN.build(p)
    assert part.is_valid and len(part.solids()) == 1
    assert any("not a preferred length" in n for n in PIN.notes(p))


def test_chamfer_shape():
    pd = SIZES["6"]
    part = PIN.build(PIN.validate({"size": "6", "length": 30}))
    R, c = pd.d / 2, pd.c
    depth = c * math.tan(math.radians(CHAMFER_ANGLE))
    for z_end, sign in ((0.0, -1), (-30.0, 1)):
        z = z_end + sign * c / 2
        assert part.is_inside(Vector(R - 0.6 * depth, 0, z))
        assert not part.is_inside(Vector(R - 0.4 * depth, 0, z))
        assert part.is_inside(Vector(R - 0.01, 0, z_end + sign * 1.1 * c))
    assert chamfer_depth(pd) == pytest.approx(depth)


def test_step_roundtrip():
    part = PIN.build(PIN.validate({"size": "6", "length": 30}))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "pin.stp"
        export_step(part, path)
        assert b"ISO 2338 - 6 m6 x 30" in path.read_bytes()
        imported = import_step(path)
    assert imported.is_valid
    assert imported.volume == pytest.approx(part.volume, rel=1e-6)


def test_api_surface():
    assert PIN.category == "Pins"
    params = {p.name: p for p in PIN.parameters()}
    assert set(params) == {"size", "length", "tolerance"}
    assert {p.kind for p in params.values()} <= {"select", "length"}
    for s, pd in SIZES.items():
        assert params["length"].preferred[s] == pd.standard_lengths()
        assert params["length"].limits[s] == [pd.l_min, pd.l_max]
    # Every default is valid.
    p = PIN.validate({})
    assert p == {"size": "6", "length": 30, "tolerance": "m6"}
    assert PIN.designation(p) == "ISO 2338 - 6 m6 x 30"
    assert PIN.file_stem(p) == "ISO2338_6x30"
    p = PIN.validate({"size": "0.6", "length": "2", "tolerance": "h8"})
    assert PIN.designation(p) == "ISO 2338 - 0.6 h8 x 2"
    assert PIN.file_stem(p) == "ISO2338_0.6x2_h8"
    dims = {d.symbol: d for d in PIN.dimensions(p)}
    assert dims["c ≈"].value == 0.12
    assert dims["d max"].value == 0.6 and dims["d min"].value == 0.586
    assert dims["α ≈"].unit == "°"
    assert PIN.notes(p)
    assert PIN.describe_json()["parameters"]
    # The tolerance class does not change the geometry.
    a = PIN.build(PIN.validate({"size": "8", "length": 40, "tolerance": "m6"}))
    b = PIN.build(PIN.validate({"size": "8", "length": 40, "tolerance": "h8"}))
    assert a.volume == pytest.approx(b.volume, rel=1e-12)
    assert b.label == "ISO 2338 - 8 h8 x 40"


@pytest.mark.parametrize(
    "raw",
    [
        {"size": "7", "length": 20},
        {"size": "6", "length": 11},
        {"size": "6", "length": 61},
        {"size": "6", "length": "x"},
        {"size": "6", "length": "nan"},
        {"size": "6", "length": 30, "tolerance": "h7"},
    ],
)
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        PIN.validate(raw)

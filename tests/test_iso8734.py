import math
import tempfile
from pathlib import Path

import pytest
from build123d import Vector, export_step, import_step

from standardparts.standards import ParameterError
from standardparts.standards.iso8734 import ISO8734, chamfer_depth
from standardparts.standards.iso8734_data import CHAMFER_ANGLE, LENGTH_SERIES, SIZES

PIN = ISO8734()

# Commercial length ranges of ISO 8734:1997 Table 1 (bold stepped lines).
RANGES = {"1": (3, 10), "1.5": (4, 16), "2": (5, 20), "2.5": (6, 24), "3": (8, 30),
          "4": (10, 40), "5": (12, 50), "6": (14, 60), "8": (18, 80),
          "10": (22, 100), "12": (26, 100), "16": (40, 100), "20": (50, 100)}
C = {"1": 0.2, "1.5": 0.3, "2": 0.35, "2.5": 0.4, "3": 0.5, "4": 0.63, "5": 0.8,
     "6": 1.2, "8": 1.6, "10": 2, "12": 2.5, "16": 3, "20": 3.5}


def test_table():
    assert {s: (p.l_min, p.l_max) for s, p in SIZES.items()} == RANGES
    assert {s: p.c for s, p in SIZES.items()} == C
    for pd in SIZES.values():
        assert float(pd.size) == pd.d
        assert pd.l_min in LENGTH_SERIES and pd.l_max in LENGTH_SERIES
        # The chamfers at both ends never meet.
        assert 2 * pd.c < pd.l_min


def expected_volume(pd, l):
    R = pd.d / 2
    r = R - chamfer_depth(pd)
    c = pd.c
    return math.pi * R * R * (l - 2 * c) + 2 * math.pi * c / 3 * (R * R + R * r + r * r)


@pytest.mark.parametrize("size", list(SIZES))
def test_every_length_builds(size):
    pd = SIZES[size]
    for l in pd.standard_lengths():
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


def test_chamfer_shape():
    pd = SIZES["6"]
    part = PIN.build(PIN.validate({"size": "6", "length": 20}))
    R, c = pd.d / 2, pd.c
    depth = c * math.tan(math.radians(CHAMFER_ANGLE))
    for z_end, sign in ((0.0, -1), (-20.0, 1)):
        # Halfway along the chamfer the surface is depth / 2 inside d.
        z = z_end + sign * c / 2
        assert part.is_inside(Vector(R - 0.6 * depth, 0, z))
        assert not part.is_inside(Vector(R - 0.4 * depth, 0, z))
        # Past the chamfer the full diameter is solid.
        assert part.is_inside(Vector(R - 0.01, 0, z_end + sign * 1.1 * c))


def test_step_roundtrip():
    part = PIN.build(PIN.validate({"size": "6", "length": 20}))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "pin.stp"
        export_step(part, path)
        assert b"ISO 8734 - 6 x 20" in path.read_bytes()
        imported = import_step(path)
    assert imported.is_valid
    assert imported.volume == pytest.approx(part.volume, rel=1e-6)


def test_api_surface():
    assert PIN.category == "Pins"
    params = {p.name: p for p in PIN.parameters()}
    assert set(params) == {"size", "length"}
    assert {p.kind for p in params.values()} <= {"select", "length"}
    for s, pd in SIZES.items():
        assert params["length"].preferred[s] == pd.standard_lengths()
        assert params["length"].limits[s] == [pd.l_min, pd.l_max]
    p = PIN.validate({})
    assert p == {"size": "6", "length": 20}
    assert PIN.designation(p) == "ISO 8734 - 6 x 20"
    assert PIN.file_stem(p) == "ISO8734_6x20"
    p = PIN.validate({"size": "1.5", "length": "4"})
    assert PIN.file_stem(p) == "ISO8734_1.5x4"
    dims = {d.symbol: d.value for d in PIN.dimensions(p)}
    assert dims["c ≈"] == 0.3
    assert PIN.notes(p)
    assert PIN.describe_json()["parameters"]


@pytest.mark.parametrize(
    "raw",
    [
        {"size": "7", "length": 20},
        {"size": "6", "length": 13},
        {"size": "6", "length": 61},
        {"size": "6", "length": "x"},
        {"size": "6", "length": "nan"},
    ],
)
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        PIN.validate(raw)


def test_custom_length_is_flagged():
    p = PIN.validate({"size": "6", "length": 21})
    assert any("not a preferred length" in n for n in PIN.notes(p))

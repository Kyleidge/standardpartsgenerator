import tempfile
from pathlib import Path

import pytest
from build123d import Vector, export_step, import_step

from standardparts.standards import ParameterError
from standardparts.standards.iso1234 import ISO1234, SLIT, layout
from standardparts.standards.iso1234_data import LENGTH_SERIES, SIZES

PIN = ISO1234()

# ISO 1234:1997 Table 2 commercial length ranges (bold stepped lines).
RANGES = {"0.6": (4, 12), "0.8": (5, 16), "1": (6, 20), "1.2": (8, 25), "1.6": (8, 32),
          "2": (10, 40), "2.5": (12, 50), "3.2": (14, 63), "4": (18, 80), "5": (22, 100),
          "6.3": (32, 125), "8": (40, 160), "10": (45, 200), "13": (71, 250),
          "16": (112, 280), "20": (160, 280)}


def test_table():
    assert {s: (p.l_min, p.l_max) for s, p in SIZES.items()} == RANGES
    prev = None
    for sd in SIZES.values():
        assert sd.d_max > sd.d_min
        assert sd.d_max < sd.hole
        assert sd.c_max > sd.c_min
        assert sd.a_max == pytest.approx(2 * sd.a_min)
        assert sd.l_min in LENGTH_SERIES and sd.l_max in LENGTH_SERIES
        if prev is not None:
            assert sd.hole > prev.hole and sd.d_max > prev.d_max and sd.b >= prev.b
            assert sd.l_min >= prev.l_min and sd.l_max >= prev.l_max
            # Bolt ranges chain on from one size to the next.
            assert sd.bolt[0] == prev.bolt[1] and sd.clevis[0] == prev.clevis[1]
        prev = sd


def _lengths(sd):
    std = sd.standard_lengths()
    return sorted({std[0], std[len(std) // 2], std[-1]})


@pytest.mark.parametrize("size", list(SIZES))
def test_every_size_builds(size):
    sd = SIZES[size]
    for l in _lengths(sd):
        p = PIN.validate({"size": size, "length": l})
        part = PIN.build(p)
        assert part.label == PIN.designation(p)
        assert part.is_valid
        assert len(part.solids()) == 1
        lay = layout(sd, l)
        assert part.volume == pytest.approx(lay.volume(), rel=1e-6)
        bb = part.bounding_box()
        assert bb.max.Z == pytest.approx(sd.b, abs=1e-6)              # top of the eye
        assert bb.min.Z == pytest.approx(-(l + sd.a_max), abs=1e-6)   # longer leg
        assert bb.size.X == pytest.approx(sd.c_max, abs=1e-6)         # eye width c
        assert bb.size.Y == pytest.approx(sd.d_max, rel=1e-3)         # wire width d
        # Volume is close to a round rod of diameter d along the wire.
        wire_len = 2 * l + sd.a_max + lay.eye_angle * (lay.r_in + sd.d_max / 4)
        assert part.volume < 3.1416 * sd.d_max ** 2 / 4 * (wire_len + 4 * sd.b)
        assert part.volume > 3.1416 * sd.d_max ** 2 / 4 * (2 * l + sd.a_max) / 2


@pytest.mark.parametrize("size", ["0.6", "4", "20"])
def test_shape(size):
    sd = SIZES[size]
    l = sd.standard_lengths()[0]
    part = PIN.build(PIN.validate({"size": size, "length": l}))
    lay = layout(sd, l)
    d, a = sd.d_max, sd.a_max
    # Both legs at mid length, the slit between them is empty.
    assert part.is_inside(Vector(d / 4, 0, -l / 2))
    assert part.is_inside(Vector(-d / 4, 0, -l / 2))
    assert not part.is_inside(Vector(0, 0, -l / 2))
    # Only the +X leg carries the extended prong.
    assert part.is_inside(Vector(d / 4, 0, -l - a / 2))
    assert not part.is_inside(Vector(-d / 4, 0, -l - a / 2))
    # The eye: empty hole in the middle, solid wire around it.
    assert not part.is_inside(Vector(0, 0, lay.zc))
    assert part.is_inside(Vector(0, 0, sd.b - lay.thickness / 2))
    assert part.is_inside(Vector(sd.c_max / 2 - lay.thickness / 2, 0, lay.zc))
    assert part.is_inside(Vector(-sd.c_max / 2 + lay.thickness / 2, 0, lay.zc))
    assert not part.is_inside(Vector(0, 0, sd.b + 0.01))
    assert lay.slit == pytest.approx(SLIT * d)


def test_custom_length_builds_and_is_flagged():
    p = PIN.validate({"size": "4", "length": 33})
    part = PIN.build(p)
    assert part.is_valid and len(part.solids()) == 1
    assert any("not a preferred length" in n for n in PIN.notes(p))


def test_step_roundtrip():
    part = PIN.build(PIN.validate({"size": "4", "length": 32}))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "pin.stp"
        export_step(part, path)
        assert b"ISO 1234 - 4 x 32" in path.read_bytes()
        imported = import_step(path)
    assert imported.is_valid
    assert imported.volume == pytest.approx(part.volume, rel=1e-6)


def test_api_surface():
    assert PIN.category == "Pins"
    params = {p.name: p for p in PIN.parameters()}
    assert set(params) == {"size", "length"}
    assert {p.kind for p in params.values()} <= {"select", "length"}
    for s, sd in SIZES.items():
        assert params["length"].preferred[s] == sd.standard_lengths()
        assert params["length"].limits[s] == [sd.l_min, sd.l_max]
    p = PIN.validate({})
    assert p == {"size": "4", "length": 32}
    assert PIN.designation(p) == "ISO 1234 - 4 x 32"
    assert PIN.file_stem(p) == "ISO1234_4x32"
    p = PIN.validate({"size": "6.3", "length": "40"})
    assert PIN.file_stem(p) == "ISO1234_6.3x40"
    dims = {d.symbol: d.value for d in PIN.dimensions(p)}
    assert dims["d max"] == 5.9 and dims["c max"] == 11.8 and dims["b ≈"] == 12.6
    assert dims["bolt"] == "over 27 to 39"
    assert dims["hole"] == "H14"
    assert {d.symbol: d.value for d in PIN.dimensions(PIN.validate({"size": "0.6", "length": 4}))}[
        "bolt"] == "up to 2.5"
    assert PIN.notes(p)
    assert PIN.describe_json()["parameters"]


@pytest.mark.parametrize(
    "raw",
    [
        {"size": "7", "length": 20},
        {"size": "4", "length": 17},
        {"size": "4", "length": 81},
        {"size": "4", "length": "x"},
        {"size": "4", "length": "inf"},
    ],
)
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        PIN.validate(raw)

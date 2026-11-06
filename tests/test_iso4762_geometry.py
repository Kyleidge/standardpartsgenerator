import math
import tempfile
from pathlib import Path

import pytest
from build123d import Vector, import_step

from standardparts.export import build_part, step_bytes
from standardparts.standards import STANDARDS, ParameterError
from standardparts.standards.iso4762_data import SIZES

ISO = STANDARDS["iso4762"]


def cases():
    for size, sd in SIZES.items():
        lengths = sd.standard_lengths()
        partial = [l for l in lengths if not sd.is_fully_threaded(l)]
        picks = {lengths[0], lengths[-1], *(partial[:1])}
        for l in sorted(picks):
            yield size, l


def check_solid(size, l, thread):
    sd = SIZES[size]
    params = ISO.validate({"size": size, "length": l, "thread": thread})
    part = build_part("iso4762", params)
    assert part.is_valid
    assert len(part.solids()) == 1
    bb = part.bounding_box()
    tol = 1e-3 * sd.d
    assert bb.min.Z == pytest.approx(-l, abs=tol)
    assert bb.max.Z == pytest.approx(sd.k_max, abs=tol)
    assert bb.size.X == pytest.approx(sd.dk_max, abs=tol)
    assert bb.size.Y == pytest.approx(sd.dk_max, abs=tol)
    # Socket is empty, shank and head wall are solid.
    assert not part.is_inside(Vector(0, 0, sd.k_max - sd.t_min / 2))
    assert part.is_inside(Vector(0, 0, sd.w_min / 2))
    assert part.is_inside(Vector(0, 0, -l / 2))
    return part


@pytest.mark.parametrize("size,l", list(cases()))
def test_simplified_solid(size, l):
    part = check_solid(size, l, "simplified")
    sd = SIZES[size]
    # Volume sits between the bare cylinders of shank and head.
    shank = math.pi * (sd.d / 2) ** 2 * l
    head = math.pi * (sd.dk_max / 2) ** 2 * sd.k_max
    assert 0.85 * (shank + head) < part.volume < shank + head


@pytest.mark.parametrize("size,l", list(cases()))
def test_modeled_thread_solid(size, l):
    part = check_solid(size, l, "modeled")
    plain = build_part("iso4762", ISO.validate({"size": size, "length": l}))
    sd = SIZES[size]
    # The ISO 68-1 basic profile removes 0.3045 P^2 per pitch of cross
    # section compared with a plain cylinder at d (computed at mean radius).
    threaded = l if sd.is_fully_threaded(l) else sd.b
    r_mean = sd.d / 2 - 0.2706 * sd.P
    expected = 0.3045 * sd.P**2 * 2 * math.pi * r_mean * threaded / sd.P
    assert plain.volume - part.volume == pytest.approx(expected, rel=0.15)


def test_step_roundtrip():
    params = ISO.validate({"size": "M6", "length": 20, "thread": "modeled"})
    data = step_bytes("iso4762", params)
    assert data.startswith(b"ISO-10303-21;")
    assert b"ISO 4762 - M6 x 20" in data
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "part.stp"
        path.write_bytes(data)
        imported = import_step(path)
    assert imported.is_valid
    assert imported.volume == pytest.approx(build_part("iso4762", params).volume, rel=1e-4)


@pytest.mark.parametrize(
    "raw",
    [
        {"size": "M7", "length": 20},
        {"size": "M6", "length": 5},
        {"size": "M6", "length": 61},
        {"size": "M6", "length": "abc"},
        {"size": "M6", "length": "nan"},
        {"size": "M6", "length": 20, "thread": "fancy"},
    ],
)
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        ISO.validate(raw)


def test_custom_length_is_flagged():
    params = ISO.validate({"size": "M6", "length": "22.5"})
    assert params["length"] == 22.5
    assert any("not a preferred length" in n for n in ISO.notes(params))

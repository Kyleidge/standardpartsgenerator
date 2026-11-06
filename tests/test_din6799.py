from io import BytesIO

import pytest
from build123d import Cylinder, Vector, export_step, import_step

from standardparts.standards.base import ParameterError
from standardparts.standards.din471 import u
from standardparts.standards.din6799 import DIN6799, STEEL, _clip
from standardparts.standards.din6799_data import SIZES

DIN = DIN6799()


@pytest.mark.parametrize("cd", SIZES.values(), ids=list(SIZES))
def test_data_rows_are_consistent(cd):
    # Groove below the smallest shaft, washer beyond the largest one.
    assert cd.a < cd.d2 < cd.d1_min < cd.d1_max < cd.d3
    # Groove width clears the thickness, including its tolerance.
    assert cd.s + cd.s_tol < cd.m
    assert cd.m - cd.s == pytest.approx(0.04 if cd.d2 <= 7 else 0.05)
    # Catalogue free diameter lies inside the seated maximum.
    assert cd.od_free < cd.d3
    assert cd.g < cd.n_min
    assert cd.weight == pytest.approx(
        _clip(cd.size).plan().area * cd.s * STEEL, rel=0.2
    )


def test_sizes_ascend_and_shaft_ranges_overlap_or_touch():
    rows = list(SIZES.values())
    for prev, nxt in zip(rows, rows[1:]):
        assert nxt.d2 > prev.d2
        assert nxt.d1_min <= prev.d1_max


def washer(size):
    return DIN.build(DIN.validate({"size": size}))


@pytest.mark.parametrize("size", list(SIZES))
def test_washer_solid(size):
    cd, clip = SIZES[size], _clip(size)
    part = washer(size)
    assert part.is_valid
    assert len(part.solids()) == 1
    bb = part.bounding_box()
    assert bb.min.Z == pytest.approx(0, abs=1e-6)
    assert bb.max.Z == pytest.approx(cd.s, abs=1e-6)
    # Outer contour on d3, centred on the axis, opening towards +Y.
    assert bb.size.X == pytest.approx(cd.d3, abs=1e-4)
    assert bb.min.X == pytest.approx(-cd.d3 / 2, abs=1e-4)
    assert bb.min.Y == pytest.approx(-cd.d3 / 2, abs=1e-4)
    assert bb.max.Y == pytest.approx(clip.y_end, abs=1e-4)
    assert 0 < bb.max.Y < cd.d3 / 2


@pytest.mark.parametrize("size", list(SIZES))
def test_contact_lobes_on_groove_diameter(size):
    cd, clip = SIZES[size], _clip(size)
    part = washer(size)
    z, eps, r2 = cd.s / 2, 0.01 * cd.d2, cd.d2 / 2
    # Back lobe tip on d2.
    assert part.is_inside(Vector(0, -(r2 + eps), z))
    assert not part.is_inside(Vector(0, -(r2 - eps), z))
    # Each jaw contact face on d2, between its back edge and the tip.
    psi = (clip.psi_tip + clip.psi_jaw) / 2
    for side in (1, -1):
        assert part.is_inside(u(side * psi) * (r2 + eps) + Vector(0, 0, z))
        assert not part.is_inside(u(side * psi) * (r2 - eps) + Vector(0, 0, z))
    # Relief cut-outs between the lobes stay clear of the groove.
    for side in (1, -1):
        mid = u(side * psi / 2)
        assert not part.is_inside(mid * (r2 + eps) + Vector(0, 0, z))
        assert not part.is_inside(mid * (clip.r_relief - eps) + Vector(0, 0, z))
        assert part.is_inside(mid * (clip.r_relief + eps) + Vector(0, 0, z))


@pytest.mark.parametrize("size", list(SIZES))
def test_opening_width_is_a(size):
    cd, clip = SIZES[size], _clip(size)
    part = washer(size)
    z, eps = cd.s / 2, 0.01 * cd.d2
    assert clip.y_tip > 0  # the jaws reach past the shaft's equator
    for y in (clip.y_tip + 0.25 * (clip.y_end - clip.y_tip),
              clip.y_tip + 0.5 * (clip.y_end - clip.y_tip)):
        for side in (1, -1):
            assert part.is_inside(Vector(side * (cd.a / 2 + eps), y, z))
            assert not part.is_inside(Vector(side * (cd.a / 2 - eps), y, z))


@pytest.mark.parametrize("size", list(SIZES))
def test_washer_between_groove_and_d3(size):
    cd = SIZES[size]
    part = washer(size)
    outside = part - Cylinder(cd.d3 / 2, 3 * cd.s)
    inside = part & Cylinder(cd.d2 / 2, 3 * cd.s)
    assert outside.volume < 1e-6 * part.volume
    assert inside.volume < 1e-6 * part.volume


@pytest.mark.parametrize(
    "raw",
    [{"size": "6.5"}, {"size": "31"}, {"size": "M6"}, {"size": ""}],
)
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        DIN.validate(raw)


@pytest.mark.parametrize("raw,size", [("6.0", "6"), ("1,2", "1.2"), ("0.80", "0.8"), (3.2, "3.2")])
def test_size_accepts_float_text(raw, size):
    assert DIN.validate({"size": raw})["size"] == size


def test_default_and_labels():
    assert DIN.validate({}) == {"size": "6"}
    (size,) = DIN.parameters()
    labels = {o.value: o.label for o in size.options}
    assert labels["6"] == "6 mm  (shaft 7–9, s = 0.7)"
    assert set(labels) == set(SIZES)


def test_dimensions_and_designation():
    p = DIN.validate({"size": "6"})
    assert DIN.designation(p) == "DIN 6799 - 6"
    assert DIN.file_stem(p) == "DIN6799_6"
    dims = {d.symbol: d.value for d in DIN.dimensions(p)}
    assert dims["d1"] == "7 – 9"
    assert dims["d3 max"] == 12.3
    assert dims["m"] == 0.74
    assert dims["n min"] == 1.2
    assert DIN.notes(p)


def test_step_round_trip(tmp_path):
    p = DIN.validate({"size": "1.2"})
    part = washer("1.2")
    path = tmp_path / "e.step"
    export_step(part, str(path))
    data = path.read_bytes()
    assert data.startswith(b"ISO-10303-21;")
    assert b"DIN 6799 - 1.2" in data
    back = import_step(str(path))
    assert back.volume == pytest.approx(part.volume, rel=1e-6)
    assert DIN.file_stem(p) == "DIN6799_1.2"
    buf = BytesIO()
    export_step(part, buf)
    assert buf.getvalue().startswith(b"ISO-10303-21;")

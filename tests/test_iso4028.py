import math
import tempfile
from pathlib import Path

import pytest
from build123d import Vector, export_step, import_step

from standardparts.geometry import SQRT3, MetricThread
from standardparts.standards import ParameterError
from standardparts.standards.set_screws import (
    ISO4026,
    ISO4028,
    drill_point_height,
    socket_depth,
)
from standardparts.standards.set_screws_data import (
    DP,
    LENGTH_RANGE_4028,
    LENGTH_SERIES,
    SHORT_LENGTHS,
    SOCKET,
    Z_LONG,
    Z_SHORT,
    is_short,
    standard_lengths,
)

STD = ISO4028()


# ---------------------------------------------------------------- helpers


def _frustums(profile):
    """Volume of the solid of revolution under a (r, z) polyline."""
    v = 0.0
    for (r1, z1), (r2, z2) in zip(profile, profile[1:]):
        v += math.pi * abs(z2 - z1) / 3 * (r1 * r1 + r1 * r2 + r2 * r2)
    return v


def expected_simplified_volume(size, l):
    """Exact volume of the simplified model: revolved body minus socket."""
    sd = SOCKET[size]
    short = STD.is_short(size, l)
    R = sd.d / 2
    dp, z = STD.dog(sd, short)
    r_dog = dp / 2
    r_top = MetricThread(sd.d, sd.P).d3 / 2
    top = STD.top(short)
    z_sh = -l + z
    z2 = -(R - r_top) / math.tan(math.radians(top.half_angle))
    body = _frustums([(r_dog, -l), (r_dog, z_sh), (R, z_sh + R - r_dog), (R, z2), (r_top, 0.0)])
    s, t = sd.s_nom, socket_depth(sd, short)
    h = drill_point_height(s)
    r_cone = 0.96 * s / 2 * h / (h + 1e-3 * s)  # hex_socket cone radius at z = -t
    socket = SQRT3 / 2 * s * s * t + math.pi * r_cone**2 * h / 3
    return body - socket


def check_part(size, l, mode):
    """Build one dog point set screw and check it; returns the part. Used by
    the tests and by the full sweep script."""
    sd = SOCKET[size]
    params = STD.validate({"size": size, "length": l, "thread": mode})
    part = STD.build(params)
    assert part.label == STD.designation(params)
    assert part.is_valid
    assert len(part.solids()) == 1

    d, R = sd.d, sd.d / 2
    short = STD.is_short(size, l)
    thread = MetricThread(sd.d, sd.P)
    bb = part.bounding_box()
    tol = 1e-3 * d
    assert bb.min.Z == pytest.approx(-l, abs=tol)
    assert bb.max.Z == pytest.approx(0.0, abs=tol)
    size_tol = tol if mode == "simplified" else 0.02 * d
    assert bb.size.X == pytest.approx(d, abs=size_tol)
    assert bb.size.Y == pytest.approx(d, abs=size_tol)

    t = socket_depth(sd, short)
    s = sd.s_nom
    inside = lambda r, z: part.is_inside(Vector(r, 0, z))  # noqa: E731
    # Socket is empty, its rim is solid.
    assert not inside(0, -t / 2)
    assert not inside(0.45 * s, -t / 2)
    assert inside((s / SQRT3 + thread.d3 / 2) / 2, -t / 2)
    # The dog: solid inside dp, empty between dp and the thread, both along
    # its length; solid on the axis between the socket and the tip.
    dp, z = STD.dog(sd, short)
    r_dog = dp / 2
    for f in (0.1, 0.5, 0.9):
        zz = -l + f * z
        assert inside(0.9 * r_dog, zz)
        assert not inside((r_dog + R) / 2, zz)
    z_socket = -t - drill_point_height(s)
    assert z_socket + l > 0.05 * d
    assert inside(0, (z_socket - l) / 2)
    assert inside(0, -l + 0.002 * d)
    # Above the 45 deg shoulder cone the full section is there.
    z_full = -l + z + (R - r_dog) + 0.1 * sd.P
    if mode == "simplified" and z_full < -(R - thread.d3 / 2) - 0.1 * sd.P:
        assert inside(R - 0.01 * d, z_full)
    return part


def cases():
    """Sample: shortest, last short, first long and longest lengths of each size."""
    for size in SOCKET:
        lengths = standard_lengths("iso4028", size)
        shorts = [x for x in lengths if is_short("iso4028", size, x)]
        longs = [x for x in lengths if not is_short("iso4028", size, x)]
        for l in sorted({lengths[0], shorts[-1], *longs[:1], lengths[-1]}):
            yield size, l


# ------------------------------------------------------------------ data


def test_dog_table():
    for size, sd in SOCKET.items():
        (zs_max, zs_min), (zl_max, zl_min) = Z_SHORT[size], Z_LONG[size]
        assert zs_min < zs_max < zl_max and zl_min < zl_max
        assert zs_min < zl_min
        # The dog fits inside the thread core.
        assert DP[size][0] < MetricThread(sd.d, sd.P).d1
        # z short ~ 0.25 d, z long ~ 0.5 d (ISO 4028 rows).
        assert zs_min == pytest.approx(0.25 * sd.d, rel=0.27)
        assert zl_min == pytest.approx(0.5 * sd.d, rel=0.27)


def test_commercial_lengths():
    expected = {"M1.6": (2, 8), "M2": (2.5, 10), "M2.5": (3, 12), "M3": (4, 16),
                "M4": (5, 20), "M5": (6, 25), "M6": (8, 30), "M8": (8, 40),
                "M10": (10, 50), "M12": (12, 60), "M16": (16, 60),
                "M20": (20, 60), "M24": (25, 60)}
    assert LENGTH_RANGE_4028 == expected
    for size, (lo, hi) in expected.items():
        assert lo in LENGTH_SERIES and hi in LENGTH_SERIES
        assert STD.standard_lengths(size) == [x for x in LENGTH_SERIES if lo <= x <= hi]
    # The other set screws keep their own ranges.
    assert ISO4026().length_range("M2") == (2, 10)
    assert ISO4026().standard_lengths("M6") == SOCKET["M6"].standard_lengths()


def test_short_lengths():
    shaded = SHORT_LENGTHS["iso4028"]
    assert shaded["M5"] == (6,) and shaded["M6"] == (8,) and shaded["M24"] == (25, 30)
    for size in SOCKET:
        lengths = standard_lengths("iso4028", size)
        assert list(shaded[size]) == lengths[: len(shaded[size])]
        for l in lengths:
            assert is_short("iso4028", size, l) == (l in shaded[size])
    # ISO 4028 shades different cells than ISO 4026.
    assert is_short("iso4028", "M8", 10) and not is_short("iso4026", "M8", 10)
    assert is_short("iso4028", "M8", 11.5)
    assert not is_short("iso4028", "M8", 12)


def test_walls_around_socket():
    # The dog eats into the point wall more than the other points do.
    # Everything keeps the 0.25 d of test_set_screws except M1.6 x 3, the
    # first long length: long socket t = 1.5 plus long dog z max = 1.05
    # leave about 0.2 d (0.32 mm) between the drill point and the shoulder.
    for size, sd in SOCKET.items():
        for l in STD.standard_lengths(size):
            side, point = STD.walls(size, l)
            assert side > 0.08 * sd.d, (size, l, side)
            limit = 0.19 if (size, l) == ("M1.6", 3) else 0.25
            assert point > limit * sd.d, (size, l, point)


# -------------------------------------------------------------- geometry


@pytest.mark.parametrize("size,l", list(cases()))
def test_simplified(size, l):
    part = check_part(size, l, "simplified")
    assert part.volume == pytest.approx(expected_simplified_volume(size, l), rel=1e-3)


MODELED = [("M1.6", 2), ("M2", 3), ("M3", 4), ("M5", 8), ("M6", 30), ("M8", 8),
           ("M12", 12), ("M24", 25), ("M24", 60)]


@pytest.mark.parametrize("size,l", MODELED)
def test_modeled(size, l):
    part = check_part(size, l, "modeled")
    sd = SOCKET[size]
    plain = expected_simplified_volume(size, l)
    # As in test_set_screws: about 0.3045 P^2 per pitch of cross section is
    # removed compared with a plain cylinder, over the threaded length.
    short = STD.is_short(size, l)
    _, z = STD.dog(sd, short)
    r_mean = sd.d / 2 - 0.2706 * sd.P
    full = 0.3045 * sd.P * 2 * math.pi * r_mean * (l - z)
    assert 0.5 * full < plain - part.volume < 1.1 * full


def test_step_roundtrip():
    params = STD.validate({"size": "M6", "length": 12, "thread": "modeled"})
    part = STD.build(params)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "part.stp"
        export_step(part, path)
        assert b"ISO 4028 - M6 x 12" in path.read_bytes()
        imported = import_step(path)
    assert imported.is_valid
    assert imported.volume == pytest.approx(part.volume, rel=1e-4)


# ---------------------------------------------------------- API surface


def test_schema_and_designation():
    assert STD.id == "iso4028" and STD.category == "Set screws"
    params = {p.name: p for p in STD.parameters()}
    assert set(params) == {"size", "length", "thread"}
    for size in SOCKET:
        assert params["length"].preferred[size] == STD.standard_lengths(size)
        assert params["length"].limits[size] == list(LENGTH_RANGE_4028[size])
    assert STD.describe_json()["parameters"]
    p = STD.validate({})
    assert p == {"size": "M6", "length": 10, "thread": "simplified"}
    assert STD.designation(p) == "ISO 4028 - M6 x 10"
    assert STD.file_stem(p) == "ISO4028_M6x10"
    p = STD.validate({"size": "M1.6", "length": 2.5, "thread": "modeled"})
    assert STD.file_stem(p) == "ISO4028_M1.6x2.5_threaded"


def test_dimensions_and_notes():
    p = STD.validate({"size": "M8", "length": 10})
    dims = {d.symbol: d.value for d in STD.dimensions(p)}
    assert dims["t min"] == 3 and dims["∠ df"] == "120°"
    assert dims["dp max"] == 5.5 and dims["z max"] == 2.25 and dims["z min"] == 2.0
    notes = STD.notes(p)
    assert any("Short length" in n for n in notes)
    assert any("short dog" in n for n in notes)
    p = STD.validate({"size": "M8", "length": 12})
    dims = {d.symbol: d.value for d in STD.dimensions(p)}
    assert dims["t min"] == 5 and dims["∠ df"] == "90°"
    assert dims["z max"] == 4.3 and dims["z min"] == 4.0
    assert any("long dog" in n for n in STD.notes(p))


@pytest.mark.parametrize(
    "raw",
    [
        {"size": "M7", "length": 10},
        {"size": "M30", "length": 40},
        {"size": "M6", "length": 6},     # valid for ISO 4026, not for ISO 4028
        {"size": "M2", "length": 2},
        {"size": "M6", "length": 31},
        {"size": "M6", "length": "abc"},
        {"size": "M6", "length": "nan"},
        {"size": "M6", "length": 10, "thread": "fancy"},
    ],
)
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        STD.validate(raw)


def test_custom_length_is_flagged():
    params = STD.validate({"size": "M6", "length": "9"})
    assert params["length"] == 9
    assert any("not a preferred length" in n for n in STD.notes(params))
    assert ISO4026().validate({"size": "M6", "length": 6})["length"] == 6

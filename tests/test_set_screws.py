import math
import tempfile
from pathlib import Path

import pytest
from build123d import Vector, export_step, import_step

from standardparts.geometry import SQRT3, MetricThread
from standardparts.standards import ParameterError
from standardparts.standards.set_screws import (
    CUP_ANGLE,
    ISO4026,
    ISO4027,
    ISO4029,
    drill_point_height,
    socket_depth,
)
from standardparts.standards.set_screws_data import (
    DP,
    DT_MAX,
    DZ,
    LENGTH_SERIES,
    SHORT_LENGTHS,
    SOCKET,
    is_short,
)

STANDARDS = {s.id: s for s in (ISO4026(), ISO4027(), ISO4029())}


# ---------------------------------------------------------------- helpers


def _frustums(profile):
    """Volume of the solid of revolution under a (r, z) polyline."""
    v = 0.0
    for (r1, z1), (r2, z2) in zip(profile, profile[1:]):
        v += math.pi * abs(z2 - z1) / 3 * (r1 * r1 + r1 * r2 + r2 * r2)
    return v


def expected_simplified_volume(std, size, l):
    """Exact volume of the simplified model: revolved body minus socket and cup."""
    sd = SOCKET[size]
    short = std.is_short(size, l)
    R = sd.d / 2
    top, pt = std.top(short), std.point(sd, short)
    r_top = MetricThread(sd.d, sd.P).d3 / 2
    r_tip = pt.r_tip
    z1 = -l + (R - r_tip) / math.tan(math.radians(pt.half_angle))
    z2 = -(R - r_top) / math.tan(math.radians(top.half_angle))
    body = _frustums([(r_tip, -l), (R, z1), (R, z2), (r_top, 0.0)])
    s, t = sd.s_nom, socket_depth(sd, short)
    h = drill_point_height(s)
    r_cone = 0.96 * s / 2 * h / (h + 1e-3 * s)  # hex_socket cone radius at z = -t
    socket = SQRT3 / 2 * s * s * t + math.pi * r_cone**2 * h / 3
    cup = 0.0
    if std.id == "iso4029":
        r_c = DZ[size][1] / 2
        cup = math.pi * r_c**2 * (r_c / math.tan(math.radians(CUP_ANGLE / 2))) / 3
    return body - socket - cup


def check_part(std_id, size, l, mode):
    """Build one set screw and check it; returns the part. Used by the tests
    and by the full sweep script."""
    std = STANDARDS[std_id]
    sd = SOCKET[size]
    params = std.validate({"size": size, "length": l, "thread": mode})
    part = std.build(params)
    assert part.label == std.designation(params)
    assert part.is_valid
    assert len(part.solids()) == 1

    d, R = sd.d, sd.d / 2
    short = std.is_short(size, l)
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
    # Socket is empty (on the axis and near the flats).
    assert not inside(0, -t / 2)
    assert not inside(0.45 * s, -t / 2)
    # Rim around the socket is solid.
    assert inside((s / SQRT3 + thread.d3 / 2) / 2, -t / 2)
    # Material between the socket bottom and the point, on the axis.
    z_socket = -t - drill_point_height(s)
    z_point = -l
    pt = std.point(sd, short)
    if std_id == "iso4029":
        r_c = DZ[size][1] / 2
        cup_depth = r_c / math.tan(math.radians(CUP_ANGLE / 2))
        z_point = -l + cup_depth
        assert not inside(0, -l + cup_depth / 2)          # cup is empty
        assert inside((DZ[size][0] + DZ[size][1]) / 4, -l + 0.002 * d)  # land
    else:
        assert inside(0, -l + 0.002 * d)                  # tip face
    assert z_socket - z_point > 0.05 * d
    assert inside(0, (z_socket + z_point) / 2)
    # The point chamfer / cone is there: just above the tip, outside it is empty.
    delta = 0.05 * (R - pt.r_tip)
    assert not inside((pt.r_tip + R) / 2, -l + delta)
    return part


def cases(std_id):
    """Sample: shortest, last short, first long and longest lengths of each size."""
    for size, sd in SOCKET.items():
        lengths = sd.standard_lengths()
        shorts = [x for x in lengths if is_short(std_id, size, x)]
        longs = [x for x in lengths if not is_short(std_id, size, x)]
        for l in sorted({lengths[0], shorts[-1], *longs[:1], lengths[-1]}):
            yield size, l


# ------------------------------------------------------------------ data


def test_socket_table_is_consistent():
    for sd in SOCKET.values():
        # e min = 1.14 s min (Table 1 footnote b), rounded as printed.
        assert sd.e_min == pytest.approx(1.14 * sd.s_min, abs=0.006), sd.size
        # s nom is the key size; for M1.6 to M2.5 it lies just below s min.
        assert sd.s_min < sd.s_max and abs(sd.s_nom - sd.s_min) < 0.02 * sd.s_nom + 0.011
        assert sd.t_min_short < sd.t_min_long
        assert sd.l_min in LENGTH_SERIES and sd.l_max in LENGTH_SERIES
        assert DP[sd.size][1] < DP[sd.size][0] < MetricThread(sd.d, sd.P).d3
        assert DZ[sd.size][1] < DZ[sd.size][0] < MetricThread(sd.d, sd.P).d3
        assert DT_MAX[sd.size] < DZ[sd.size][0]


def test_commercial_lengths():
    expected = {"M1.6": (2, 8), "M2": (2, 10), "M2.5": (2.5, 12), "M3": (3, 16),
                "M4": (4, 20), "M5": (5, 25), "M6": (6, 30), "M8": (8, 40),
                "M10": (10, 50), "M12": (12, 60), "M16": (16, 60),
                "M20": (20, 60), "M24": (25, 60)}
    assert {s: (sd.l_min, sd.l_max) for s, sd in SOCKET.items()} == expected


@pytest.mark.parametrize("std_id", list(STANDARDS))
def test_short_lengths(std_id):
    for size, sd in SOCKET.items():
        shaded = SHORT_LENGTHS[std_id][size]
        lengths = sd.standard_lengths()
        # The shaded cells are the first few commercial lengths.
        assert list(shaded) == lengths[: len(shaded)]
        for l in lengths:
            assert is_short(std_id, size, l) == (l in shaded)
    # A custom length below the first long length still gets the short socket.
    assert is_short(std_id, "M8", 9.5)
    assert not is_short(std_id, "M8", 10)


@pytest.mark.parametrize("std_id", list(STANDARDS))
def test_walls_around_socket(std_id):
    std = STANDARDS[std_id]
    for size, sd in SOCKET.items():
        for l in sd.standard_lengths():
            side, point = std.walls(size, l)
            assert side > 0.08 * sd.d, (size, l, side)
            assert point > 0.25 * sd.d, (size, l, point)


# -------------------------------------------------------------- geometry


@pytest.mark.parametrize(
    "std_id,size,l", [(std_id, *c) for std_id in STANDARDS for c in cases(std_id)]
)
def test_simplified(std_id, size, l):
    part = check_part(std_id, size, l, "simplified")
    expected = expected_simplified_volume(STANDARDS[std_id], size, l)
    assert part.volume == pytest.approx(expected, rel=1e-3)


MODELED = [("M1.6", 2), ("M2", 3), ("M3", 4), ("M5", 6), ("M6", 30), ("M8", 8),
           ("M12", 12), ("M24", 25), ("M24", 60)]


@pytest.mark.parametrize("std_id", list(STANDARDS))
@pytest.mark.parametrize("size,l", MODELED)
def test_modeled(std_id, size, l):
    part = check_part(std_id, size, l, "modeled")
    sd = SOCKET[size]
    plain = expected_simplified_volume(STANDARDS[std_id], size, l)
    # The ISO 68-1 basic profile removes about 0.3045 P^2 per pitch of cross
    # section compared with a plain cylinder at d (see the ISO 4762 test); the
    # chamfered ends lose less, so allow a generous band.
    r_mean = sd.d / 2 - 0.2706 * sd.P
    full = 0.3045 * sd.P * 2 * math.pi * r_mean * l
    assert 0.5 * full < plain - part.volume < 1.05 * full


def test_step_roundtrip():
    std = STANDARDS["iso4029"]
    params = std.validate({"size": "M6", "length": 10, "thread": "modeled"})
    part = std.build(params)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "part.stp"
        export_step(part, path)
        assert b"ISO 4029 - M6 x 10" in path.read_bytes()
        imported = import_step(path)
    assert imported.is_valid
    assert imported.volume == pytest.approx(part.volume, rel=1e-4)


# ---------------------------------------------------------- API surface


def test_designation_and_file_stem():
    std = STANDARDS["iso4029"]
    p = std.validate({"size": "M8", "length": "10"})
    assert std.designation(p) == "ISO 4029 - M8 x 10"
    assert std.file_stem(p) == "ISO4029_M8x10"
    p = std.validate({"size": "M1.6", "length": 2.5, "thread": "modeled"})
    assert std.file_stem(p) == "ISO4029_M1.6x2.5_threaded"
    assert STANDARDS["iso4026"].designation(p) == "ISO 4026 - M1.6 x 2.5"


@pytest.mark.parametrize("std_id", list(STANDARDS))
def test_schema(std_id):
    std = STANDARDS[std_id]
    assert std.category == "Set screws"
    params = {p.name: p for p in std.parameters()}
    assert set(params) == {"size", "length", "thread"}
    assert {p.kind for p in params.values()} <= {"select", "length"}
    length = params["length"]
    for size, sd in SOCKET.items():
        assert length.preferred[size] == sd.standard_lengths()
        assert length.limits[size] == [sd.l_min, sd.l_max]
    assert std.describe_json()["parameters"]
    p = std.validate({})
    assert p == {"size": "M6", "length": 10, "thread": "simplified"}
    dims = {d.symbol: d.value for d in std.dimensions(p)}
    assert dims["s"] == 3 and dims["t min"] == 3.5
    assert std.notes(p)


def test_short_length_dimensions_and_notes():
    std = STANDARDS["iso4027"]
    p = std.validate({"size": "M5", "length": 6})
    dims = {d.symbol: d.value for d in std.dimensions(p)}
    assert dims["t min"] == 2 and dims["γ"] == "120°" and dims["∠ df"] == "120°"
    assert any("Short length" in n for n in std.notes(p))
    p = std.validate({"size": "M5", "length": 8})
    dims = {d.symbol: d.value for d in std.dimensions(p)}
    assert dims["t min"] == 3 and dims["γ"] == "90°" and dims["∠ df"] == "90°"


@pytest.mark.parametrize(
    "raw",
    [
        {"size": "M7", "length": 10},
        {"size": "M30", "length": 40},
        {"size": "M6", "length": 5},
        {"size": "M6", "length": 31},
        {"size": "M6", "length": "abc"},
        {"size": "M6", "length": "inf"},
        {"size": "M6", "length": 10, "thread": "fancy"},
    ],
)
def test_validation_rejects(raw):
    for std in STANDARDS.values():
        with pytest.raises(ParameterError):
            std.validate(raw)


def test_custom_length_is_flagged():
    std = STANDARDS["iso4026"]
    params = std.validate({"size": "M6", "length": "7.5"})
    assert params["length"] == 7.5
    assert any("not a preferred length" in n for n in std.notes(params))

import math

import pytest
from build123d import GeomType, Vector

from standardparts.drives import HEXALOBULAR, hexalobular_depth_total, min_wall
from standardparts.geometry import MetricThread
from standardparts.standards.base import ParameterError
from standardparts.standards.iso14581 import ISO14581, build_body, recess_tool
from standardparts.standards.iso14581_data import LENGTH_SERIES, SIZES

ISO = ISO14581()

# ISO 14581:2013 Table 1: commercial length range (bold stepped lines).
RANGES = {
    "M2": (3, 20), "M2.5": (3, 25), "M3": (4, 30), "M3.5": (5, 35), "M4": (5, 40),
    "M5": (6, 50), "M6": (8, 60), "M8": (10, 60), "M10": (12, 60),
}


def flat_top(f):
    return f.geom_type == GeomType.PLANE and abs(f.center().Z) < 1e-6


def test_length_ranges_and_threading():
    assert list(SIZES) == list(RANGES)
    for size, (lo, hi) in RANGES.items():
        sd = SIZES[size]
        assert (sd.l_min, sd.l_max) == (lo, hi)
        assert lo in LENGTH_SERIES and hi in LENGTH_SERIES
        # Dashed line: threaded to the head up to 30 / 45 mm.
        assert sd.l_full_max == (30 if sd.d <= 3 else 45)


@pytest.mark.parametrize("sd", SIZES.values(), ids=list(SIZES))
def test_size_rows_are_consistent(sd):
    assert sd.k_max == pytest.approx((sd.dk_theo - sd.d) / 2, abs=1e-9)
    assert sd.d < sd.dk_min < sd.dk_max < sd.dk_theo
    h = HEXALOBULAR[sd.socket]
    assert h.A == pytest.approx(sd.A_ref, abs=0.025)
    assert sd.t_min < sd.t_max < sd.k_max
    assert h.A < sd.dk_min / 2 + sd.d / 2


def check_solid(size, l, thread):
    sd = SIZES[size]
    part = ISO.build(ISO.validate({"size": size, "length": l, "thread": thread}))
    assert part.label == f"ISO 14581 - {size} x {l:g}"
    assert part.is_valid
    assert len(part.solids()) == 1
    bb = part.bounding_box()
    tol = 1e-3 * sd.d
    assert bb.min.Z == pytest.approx(-l, abs=tol)
    assert bb.max.Z == pytest.approx(0, abs=tol)
    assert bb.size.X == pytest.approx(sd.dk_max, abs=tol)
    h = HEXALOBULAR[sd.socket]
    z = -sd.t_min / 2
    # Socket empty at the lobes, solid just outside them and around.
    for k in range(6):
        a = math.radians(60 * k)
        ai = a + math.pi / 6
        assert not part.is_inside(Vector((h.A / 2 - 0.02) * math.cos(a), (h.A / 2 - 0.02) * math.sin(a), z))
        assert part.is_inside(Vector((h.A / 2 + 0.02) * math.cos(a), (h.A / 2 + 0.02) * math.sin(a), z))
        assert part.is_inside(Vector((h.B / 2 + 0.02) * math.cos(ai), (h.B / 2 + 0.02) * math.sin(ai), z))
    assert not part.is_inside(Vector(0, 0, -hexalobular_depth_total(sd.socket, sd.t_min) + 0.02))
    assert part.is_inside(Vector(0, 0, -hexalobular_depth_total(sd.socket, sd.t_min) - 0.02))
    rc = sd.d / 2 + sd.k_max / 2
    assert part.is_inside(Vector(rc - 0.03, 0, -sd.k_max / 2))
    assert not part.is_inside(Vector(rc + 0.03, 0, -sd.k_max / 2))
    return part


def cases():
    for size, sd in SIZES.items():
        yield size, sd.l_min
        yield size, sd.l_max


@pytest.mark.parametrize("size,l", list(cases()))
def test_simplified_solid(size, l):
    part = check_solid(size, l, "simplified")
    sd = SIZES[size]
    R, Rk = sd.d / 2, sd.dk_theo / 2
    shank = math.pi * R**2 * (l - sd.k_max)
    cone = math.pi * sd.k_max / 3 * (R**2 + R * Rk + Rk**2)
    assert 0.8 * (shank + cone) < part.volume < shank + cone
    body = build_body(sd, l, "simplified")
    tool = recess_tool(sd)
    removed = body.volume - part.volume
    assert removed == pytest.approx((tool & body).volume, rel=1e-3)
    h = HEXALOBULAR[sd.socket]
    # At least the contour prism down to t min (area between the B and A circles).
    assert removed > math.pi * (h.B / 2) ** 2 * sd.t_min


@pytest.mark.parametrize("size,l", [("M2", 20), ("M2.5", 3), ("M4", 5), ("M5", 50), ("M10", 60)])
def test_modeled_thread_solid(size, l):
    part = check_solid(size, l, "modeled")
    sd = SIZES[size]
    plain = ISO.build(ISO.validate({"size": size, "length": l}))
    threaded = l - sd.k_max if sd.is_fully_threaded(l) else sd.b_min
    r_mean = sd.d / 2 - 0.2706 * sd.P
    expected = 0.3045 * sd.P**2 * 2 * math.pi * r_mean * threaded / sd.P
    assert plain.volume - part.volume == pytest.approx(expected, rel=0.2)


@pytest.mark.parametrize("size", list(SIZES))
def test_socket_does_not_break_through(size):
    sd = SIZES[size]
    body = build_body(sd, sd.l_min, "simplified")
    dr = (sd.d - MetricThread(sd.d, sd.P).d1) / 2
    wall = min_wall(recess_tool(sd), body, flat_top)
    assert wall - dr >= 0.1 * sd.d, wall


@pytest.mark.parametrize(
    "raw",
    [
        {"size": "M1.6", "length": 10},
        {"size": "M2", "length": 2},
        {"size": "M2", "length": 21},
        {"size": "M5", "length": "x"},
        {"size": "M5", "length": 12, "thread": "full"},
    ],
)
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        ISO.validate(raw)


def test_parameters_and_names():
    params = {p.name: p for p in ISO.parameters()}
    assert list(params) == ["size", "length", "thread"]
    assert params["length"].limits["M10"] == [12, 60]
    p = ISO.validate({"size": "M5", "length": 12})
    assert "drive" not in p
    assert ISO.designation(p) == "ISO 14581 - M5 x 12"
    assert ISO.file_stem(p) == "ISO14581_M5x12"
    assert ISO.file_stem({**p, "thread": "modeled"}) == "ISO14581_M5x12_threaded"
    dims = {d.symbol: d.value for d in ISO.dimensions(p)}
    assert dims["Socket"] == "T25" and dims["A"] == 4.5 and dims["t min"] == 1.12


def test_notes():
    notes = ISO.notes(ISO.validate({"size": "M3.5", "length": 50 - 15}))
    assert any("M3.5 is in parentheses" in n for n in notes)
    assert any("T15" in n for n in notes)
    assert any("2022" in n for n in notes)

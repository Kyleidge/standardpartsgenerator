import math

import pytest
from build123d import GeomType, Vector

from standardparts.drives import min_wall
from standardparts.geometry import MetricThread
from standardparts.standards.base import ParameterError
from standardparts.standards.iso7046 import ISO7046, build_body, recess_tool
from standardparts.standards.iso7046_data import LENGTH_SERIES, SIZES
from standardparts.standards.iso14581_data import SIZES as ISO14581_SIZES

ISO = ISO7046()
DENSITY = 7.85e-3

# ISO 7046-1:2011 Table 1: length range and mass (kg / 1000 pieces) at the
# shortest and longest length.
TABLE_1 = {
    "M1.6": (3, 0.058, 16, 0.208), "M2": (3, 0.101, 20, 0.417),
    "M2.5": (3, 0.176, 25, 0.838), "M3": (4, 0.291, 30, 1.44),
    "M3.5": (5, 0.573, 35, 2.37), "M4": (5, 0.825, 40, 3.56),
    "M5": (6, 1.24, 50, 6.52), "M6": (8, 2.38, 60, 11.5),
    "M8": (10, 5.68, 60, 21.7), "M10": (12, 9.54, 60, 33.8),
}


def flat_top(f):
    return f.geom_type == GeomType.PLANE and abs(f.center().Z) < 1e-6


# --- data -----------------------------------------------------------------------

def test_length_ranges_and_threading():
    assert list(SIZES) == list(TABLE_1)
    for size, (lo, _, hi, _) in TABLE_1.items():
        sd = SIZES[size]
        assert (sd.l_min, sd.l_max) == (lo, hi)
        assert lo in LENGTH_SERIES and hi in LENGTH_SERIES
        assert sd.l_full_max == (30 if sd.d <= 3 else 45)
    assert [l for l in SIZES["M5"].standard_lengths() if not SIZES["M5"].is_fully_threaded(l)] == [50]
    assert not any(not SIZES["M4"].is_fully_threaded(l) for l in SIZES["M4"].standard_lengths())


@pytest.mark.parametrize("sd", SIZES.values(), ids=list(SIZES))
def test_size_rows_are_consistent(sd):
    # The 90 deg cone meets d at z = -k.
    assert sd.k_max == pytest.approx((sd.dk_theo - sd.d) / 2, abs=1e-9)
    assert sd.d < sd.dk_min < sd.dk_max < sd.dk_theo
    assert 0 < sd.land_height < sd.k_max / 3
    assert sd.a_max == pytest.approx(2 * sd.P)
    for kind in "HZ":
        m, p_min, p_max = sd.recess(kind)
        assert p_min < p_max and m < sd.dk_min


def test_common_head_style_matches_iso14581():
    for size, other in ISO14581_SIZES.items():
        sd = SIZES[size]
        assert (sd.dk_theo, sd.dk_max, sd.dk_min, sd.k_max, sd.r_max, sd.x_max, sd.b_min) == (
            other.dk_theo, other.dk_max, other.dk_min, other.k_max, other.r_max, other.x_max,
            other.b_min,
        )


# --- geometry ---------------------------------------------------------------------

def check_solid(size, l, thread, drive):
    sd = SIZES[size]
    part = ISO.build(ISO.validate({"size": size, "length": l, "thread": thread, "drive": drive}))
    assert part.label == f"ISO 7046-1 - {size} x {l:g} - {drive}"
    assert part.is_valid
    assert len(part.solids()) == 1
    bb = part.bounding_box()
    tol = 1e-3 * sd.d
    assert bb.min.Z == pytest.approx(-l, abs=tol)
    assert bb.max.Z == pytest.approx(0, abs=tol)
    assert bb.size.X == pytest.approx(sd.dk_max, abs=tol)
    m, p_min, _ = sd.recess(drive)
    # Recess empty (centre, wings along X / Y), head solid around it.
    assert not part.is_inside(Vector(0, 0, -p_min / 2))
    assert not part.is_inside(Vector(0.3 * m, 0, -0.2 * p_min))
    assert not part.is_inside(Vector(0, 0.3 * m, -0.2 * p_min))
    r = (m / 2 + sd.dk_max / 2) / 2
    assert part.is_inside(Vector(r, 0, -0.02))
    assert part.is_inside(Vector(0, -r, -0.02))
    # The 90 deg cone passes through (d/2 + k/2, -k/2).
    rc = sd.d / 2 + sd.k_max / 2
    assert part.is_inside(Vector(rc - 0.03, 0, -sd.k_max / 2))
    assert not part.is_inside(Vector(rc + 0.03, 0, -sd.k_max / 2))
    assert part.is_inside(Vector(sd.dk_max / 2 - 0.02, 0, -sd.land_height / 2))
    assert part.is_inside(Vector(0, 0, -(l + sd.k_max) / 2))
    return part


def cases():
    for i, (size, sd) in enumerate(SIZES.items()):
        drives = "HZ" if i % 2 == 0 else "ZH"
        yield size, sd.l_min, drives[0]
        yield size, sd.l_max, drives[1]


@pytest.mark.parametrize("size,l,drive", list(cases()))
def test_simplified_solid(size, l, drive):
    part = check_solid(size, l, "simplified", drive)
    sd = SIZES[size]
    lo, m_lo, _, _ = TABLE_1[size]
    if l == lo:
        assert part.volume * DENSITY == pytest.approx(m_lo, rel=0.15)
    R, Rk = sd.d / 2, sd.dk_theo / 2
    shank = math.pi * R**2 * (l - sd.k_max)
    cone = math.pi * sd.k_max / 3 * (R**2 + R * Rk + Rk**2)
    assert 0.7 * (shank + cone) < part.volume < shank + cone
    body = build_body(sd, l, "simplified")
    tool = recess_tool(sd, drive)
    assert body.volume - part.volume == pytest.approx((tool & body).volume, rel=1e-3)


# M2.5 x 3 / M4 x 5: too short for the 2P runout of screws.threaded_screw.
MODELED = [("M2", 20, "Z"), ("M2.5", 3, "H"), ("M3", 4, "H"), ("M4", 5, "Z"), ("M5", 50, "H"),
           ("M8", 60, "Z")]


@pytest.mark.parametrize("size,l,drive", MODELED)
def test_modeled_thread_solid(size, l, drive):
    part = check_solid(size, l, "modeled", drive)
    sd = SIZES[size]
    _, _, hi, m_hi = TABLE_1[size]
    if l == hi:
        rel = 0.04 if sd.is_fully_threaded(l) else 0.09
        assert part.volume * DENSITY == pytest.approx(m_hi, rel=rel)
    plain = ISO.build(ISO.validate({"size": size, "length": l, "drive": drive}))
    threaded = l - sd.k_max if sd.is_fully_threaded(l) else sd.b_min
    r_mean = sd.d / 2 - 0.2706 * sd.P
    expected = 0.3045 * sd.P**2 * 2 * math.pi * r_mean * threaded / sd.P
    assert plain.volume - part.volume == pytest.approx(expected, rel=0.2)


@pytest.mark.parametrize("size", list(SIZES))
def test_recess_does_not_break_through(size):
    """The countersunk head is thin and the recess reaches below the cone
    into the shank. Its distance to every face except the top, less the
    thread depth, must stay above 8 % of d (our criterion; ISO 7046-1
    specifies no wall)."""
    sd = SIZES[size]
    body = build_body(sd, sd.l_min, "simplified")
    dr = (sd.d - MetricThread(sd.d, sd.P).d1) / 2
    for drive in "HZ":
        wall = min_wall(recess_tool(sd, drive), body, flat_top)
        assert wall - dr >= 0.08 * sd.d, (drive, wall)


# --- parameters -------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw",
    [
        {"size": "M12", "length": 20},
        {"size": "M5", "length": 5},
        {"size": "M5", "length": 51},
        {"size": "M5", "length": "nan"},
        {"size": "M5", "length": 10, "drive": "h"},
    ],
)
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        ISO.validate(raw)


def test_parameters_and_names():
    params = {p.name: p for p in ISO.parameters()}
    assert [p.kind for p in params.values()] == ["select", "length", "select", "select"]
    assert params["length"].preferred["M5"][-1] == 50
    assert params["length"].limits["M1.6"] == [3, 16]
    p = ISO.validate({"size": "M5", "length": 20, "drive": "Z", "thread": "modeled"})
    assert ISO.designation(p) == "ISO 7046-1 - M5 x 20 - Z"
    assert ISO.file_stem(p) == "ISO7046-1_M5x20_Z_threaded"
    assert ISO.file_stem({**p, "thread": "simplified"}) == "ISO7046-1_M5x20_Z"
    dims = {d.symbol: d for d in ISO.dimensions(p)}
    assert dims["m"].value == 4.9 and dims["p min"].value == 2.6
    assert dims["α"].value == 90 and dims["α"].unit == "°"
    assert dims["dk max"].value == 9.3


def test_notes():
    notes = ISO.notes(ISO.validate({"size": "M4", "length": 5, "thread": "modeled"}))
    assert any("runout is shortened to 1.4P" in n for n in notes)
    assert not any("shortened" in n for n in ISO.notes(ISO.validate({"size": "M4", "length": 6, "thread": "modeled"})))
    notes = ISO.notes(ISO.validate({"size": "M6", "length": 55}))
    assert any("55 mm is in parentheses" in n for n in notes)
    assert any("Partially threaded" in n for n in notes)
    assert any("includes the head" in n for n in notes)

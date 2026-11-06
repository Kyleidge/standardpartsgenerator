import math
import tempfile
from pathlib import Path

import pytest
from build123d import GeomType, Vector, export_step, import_step

from standardparts.geometry import SQRT3, hex_socket
from standardparts.standards.base import ParameterError
from standardparts.standards.iso10642 import ISO10642, build_body
from standardparts.standards.iso10642_data import LENGTH_SERIES, SIZES

ISO = ISO10642()

# ls min / lg max values printed in ISO 10642:2004 Table 1. Every length of a
# size below its first entry is threaded to the head (grey cells).
TABLE_1 = {
    "M3": {30: (9.5, 12)},
    "M4": {30: (6.5, 10), 35: (11.5, 15), 40: (16.5, 20)},
    "M5": {35: (9, 13), 40: (14, 18), 45: (19, 23), 50: (24, 28)},
    "M6": {40: (11, 16), 45: (16, 21), 50: (21, 26), 55: (26, 31), 60: (31, 36)},
    "M8": {50: (15.75, 22), 55: (20.75, 27), 60: (25.75, 32), 65: (30.75, 37),
           70: (35.75, 42), 80: (45.75, 52)},
    "M10": {55: (15.5, 23), 60: (20.5, 28), 65: (25.5, 33), 70: (30.5, 38),
            80: (40.5, 48), 90: (50.5, 58), 100: (60.5, 68)},
    "M12": {65: (20.25, 29), 70: (25.25, 34), 80: (35.25, 44), 90: (45.25, 54),
            100: (55.25, 64)},
    "M14": {70: (20, 30), 80: (30, 40), 90: (40, 50), 100: (50, 60)},
    "M16": {80: (26, 36), 90: (36, 46), 100: (46, 56)},
    "M20": {100: (35.5, 48)},
}
# Commercial length range per size (stepped lines of Table 1).
RANGES = {
    "M3": (8, 30), "M4": (8, 40), "M5": (8, 50), "M6": (8, 60), "M8": (10, 80),
    "M10": (12, 100), "M12": (20, 100), "M14": (25, 100), "M16": (30, 100),
    "M20": (35, 100),
}


# --- data -------------------------------------------------------------------

@pytest.mark.parametrize("size", list(SIZES))
def test_thread_geometry_matches_table_1(size):
    sd = SIZES[size]
    for l in sd.standard_lengths():
        assert sd.thread_geometry(l) == TABLE_1[size].get(l, (None, None)), (size, l)


def test_length_ranges():
    assert list(SIZES) == list(RANGES)
    for size, (lo, hi) in RANGES.items():
        sd = SIZES[size]
        assert (sd.l_min, sd.l_max) == (lo, hi)
        assert max(TABLE_1[size]) == hi
        assert lo in LENGTH_SERIES and hi in LENGTH_SERIES


def test_custom_lengths_follow_table_boundary():
    sd = SIZES["M8"]
    assert sd.is_fully_threaded(48)
    assert sd.thread_geometry(52) == (17.75, 24)


@pytest.mark.parametrize("sd", SIZES.values(), ids=list(SIZES))
def test_size_rows_are_consistent(sd):
    # k is the height of the theoretical sharp 90 deg cone from d to dk.
    assert sd.k_max == pytest.approx((sd.dk_theo_max - sd.d) / 2, abs=1e-9)
    assert sd.d < sd.dk_min < sd.dk_theo_max
    assert 0 < sd.land_height < sd.k_max / 3
    assert sd.ds_min < sd.d < sd.da_max
    # The fillet joins the cone inside da max.
    assert sd.d + 2 * (1 - math.sqrt(0.5)) * sd.r_min <= sd.da_max
    assert sd.e_min == pytest.approx(1.14 * sd.s_min, abs=1e-3)   # footnote c
    assert sd.s_nom <= sd.s_min < sd.s_max
    assert sd.l_min < sd.l_partial <= sd.l_max


# --- geometry -----------------------------------------------------------------

def cases():
    for size, sd in SIZES.items():
        picks = {sd.l_min, sd.l_max, sd.l_partial}
        for l in sorted(picks):
            yield size, l


def modeled_cases():
    # One partially threaded length per size, plus a few threaded-to-head ones.
    for size, sd in SIZES.items():
        yield size, sd.l_partial
    for size in ("M3", "M8", "M20"):
        yield size, SIZES[size].l_min


def check_solid(size, l, thread):
    sd = SIZES[size]
    params = ISO.validate({"size": size, "length": l, "thread": thread})
    part = ISO.build(params)
    assert part.label == "ISO 10642 - " + f"{size} x {l:g}"
    assert part.is_valid
    assert len(part.solids()) == 1
    bb = part.bounding_box()
    tol = 1e-3 * sd.d
    assert bb.min.Z == pytest.approx(-l, abs=tol)
    assert bb.max.Z == pytest.approx(0, abs=tol)
    assert bb.size.X == pytest.approx(sd.dk_min, abs=tol)
    assert bb.size.Y == pytest.approx(sd.dk_min, abs=tol)
    # Socket is empty, head wall and shank are solid.
    assert not part.is_inside(Vector(0, 0, -sd.t_min / 2))
    r_wall = (sd.dk_min / 2 + sd.s_nom / SQRT3) / 2
    assert part.is_inside(Vector(r_wall, 0, -sd.t_min / 2))
    assert part.is_inside(Vector(0, 0, -(l + sd.k_max) / 2))
    # The 90 deg cone passes through (d/2 + k/2, -k/2).
    rc = sd.d / 2 + sd.k_max / 2
    assert part.is_inside(Vector(rc - 0.05, 0, -sd.k_max / 2))
    assert not part.is_inside(Vector(rc + 0.05, 0, -sd.k_max / 2))
    # Cylindrical head edge at dk min.
    assert part.is_inside(Vector(sd.dk_min / 2 - 0.02, 0, -sd.land_height / 2))
    return part


@pytest.mark.parametrize("size,l", list(cases()))
def test_simplified_solid(size, l):
    part = check_solid(size, l, "simplified")
    sd = SIZES[size]
    R = sd.d / 2
    Rk = sd.dk_theo_max / 2
    shank = math.pi * R**2 * (l - sd.k_max)
    cone = math.pi * sd.k_max / 3 * (R**2 + R * Rk + Rk**2)
    assert 0.85 * (shank + cone) < part.volume < shank + cone
    # The socket removed exactly the hex prism plus its drill point.
    body = build_body(sd, l, "simplified")
    r_d = 0.96 * sd.s_nom / 2
    socket = SQRT3 / 2 * sd.s_nom**2 * sd.t_min + math.pi * r_d**3 / math.tan(math.radians(59)) / 3
    assert body.volume - part.volume == pytest.approx(socket, rel=0.01)


@pytest.mark.parametrize("size,l", list(modeled_cases()))
def test_modeled_thread_solid(size, l):
    part = check_solid(size, l, "modeled")
    plain = ISO.build(ISO.validate({"size": size, "length": l}))
    sd = SIZES[size]
    # ISO 68-1 basic profile removes 0.3045 P^2 per pitch of cross section.
    threaded = l - sd.k_max if sd.is_fully_threaded(l) else sd.b
    r_mean = sd.d / 2 - 0.2706 * sd.P
    expected = 0.3045 * sd.P**2 * 2 * math.pi * r_mean * threaded / sd.P
    assert plain.volume - part.volume == pytest.approx(expected, rel=0.15)


@pytest.mark.parametrize("sd", SIZES.values(), ids=list(SIZES))
def test_socket_does_not_break_through_the_cone(sd):
    body = build_body(sd, sd.l_min, "simplified")
    tool = hex_socket(sd.s_nom, sd.t_min, 0.0)
    walls = [
        tool.distance_to(f)
        for f in body.faces()
        if not (f.geom_type == GeomType.PLANE and abs(f.center().Z) < 1e-6)
    ]
    assert min(walls) >= sd.w_min


def test_step_roundtrip():
    params = ISO.validate({"size": "M6", "length": 20, "thread": "modeled"})
    part = ISO.build(params)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "part.stp"
        assert export_step(part, path)
        imported = import_step(path)
    assert imported.is_valid
    assert imported.volume == pytest.approx(part.volume, rel=1e-4)


# --- parameters ---------------------------------------------------------------

@pytest.mark.parametrize(
    "raw",
    [
        {"size": "M7", "length": 20},
        {"size": "M6", "length": 6},
        {"size": "M6", "length": 61},
        {"size": "M20", "length": 30},
        {"size": "M6", "length": "abc"},
        {"size": "M6", "length": "nan"},
        {"size": "M6", "length": 20, "thread": "fancy"},
    ],
)
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        ISO.validate(raw)


def test_parameters_and_names():
    params = {p.name: p for p in ISO.parameters()}
    assert params["size"].kind == "select" and params["length"].kind == "length"
    assert params["length"].preferred["M8"] == [10, 12, 16, 20, 25, 30, 35, 40, 45,
                                                50, 55, 60, 65, 70, 80]
    assert params["length"].limits["M20"] == [35, 100]
    p = ISO.validate({"size": "M8", "length": "30", "thread": "modeled"})
    assert ISO.designation(p) == "ISO 10642 - M8 x 30"
    assert ISO.file_stem(p) == "ISO10642_M8x30_threaded"
    assert ISO.file_stem({**p, "thread": "simplified"}) == "ISO10642_M8x30"
    dims = {d.symbol: d.value for d in ISO.dimensions(p)}
    assert dims["b"] == "to head" and dims["dk min"] == 15.24
    assert ISO.dimensions({**p, "length": 60})[3].value == 28


def test_notes():
    notes = ISO.notes(ISO.validate({"size": "M14", "length": "27.5"}))
    assert any("parentheses" in n for n in notes)
    assert any("not a preferred length" in n for n in notes)
    assert any("Threaded up to the head" in n for n in notes)
    notes = ISO.notes(ISO.validate({"size": "M10", "length": 80}))
    assert any("Partially threaded" in n for n in notes)

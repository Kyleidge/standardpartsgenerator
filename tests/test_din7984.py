import math
import tempfile
from pathlib import Path

import pytest
from build123d import Vector, export_step, import_step

from standardparts.geometry import SQRT3
from standardparts.standards import iso4762_data
from standardparts.standards.base import ParameterError
from standardparts.standards.din7984 import (
    DIN7984,
    SOCKET_DRILL_ANGLE,
    build_body,
    socket_point_height,
)
from standardparts.standards.din7984_data import LENGTH_SERIES, SIZES

DIN = DIN7984()

# ls min / lg max printed in DIN 7984:2009-06 Table 1. Every standard length
# below a size's first entry is threaded to the head.
TABLE_1 = {
    "M3": {20: (5.5, 8)},
    "M4": {25: (7.5, 11)},
    "M5": {30: (10, 14)},
    "M6": {30: (7, 12), 35: (12, 17), 40: (17, 22)},
    "M8": {35: (6.75, 13), 40: (11.75, 18), 45: (16.75, 23), 50: (21.75, 28),
           55: (26.75, 33), 60: (31.75, 38), 70: (41.75, 48), 80: (51.75, 58)},
    "M10": {40: (6.5, 14), 45: (11.5, 19), 50: (16.5, 24), 55: (21.5, 29), 60: (26.5, 34),
            70: (36.5, 44), 80: (46.5, 54), 90: (56.5, 64), 100: (66.5, 74)},
    "M12": {50: (11.25, 20), 55: (16.25, 25), 60: (21.25, 30), 70: (31.25, 40),
            80: (41.25, 50)},
    "M14": {55: (11, 21), 60: (16, 26), 70: (26, 36), 80: (36, 46)},
    "M16": {60: (12, 22), 70: (22, 32), 80: (32, 42)},
    "M18": {70: (15.5, 28), 80: (25.5, 38), 90: (35.5, 48), 100: (45.5, 58)},
    "M20": {70: (11.5, 24), 80: (21.5, 34), 90: (31.5, 44), 100: (41.5, 54)},
    "M22": {80: (17.5, 30), 90: (27.5, 40), 100: (37.5, 50)},
    "M24": {90: (21, 36), 100: (31, 46)},
}
# Standard length range of each size in Table 1.
LENGTH_RANGES = {
    "M3": (5, 20), "M4": (6, 25), "M5": (8, 30), "M6": (10, 40), "M8": (12, 80),
    "M10": (16, 100), "M12": (20, 80), "M14": (30, 80), "M16": (30, 80),
    "M18": (30, 100), "M20": (30, 100), "M22": (40, 100), "M24": (40, 100),
}
# lg max printed for the screws threaded to the head (footnote c: ~ 3P).
LG_FULL = {
    "M3": 1.5, "M4": 2.1, "M5": 2.4, "M6": 3, "M8": 3.75, "M10": 4.5, "M12": 5.25,
    "M14": 6, "M16": 6, "M18": 7.5, "M20": 7.5, "M22": 7.5, "M24": 9,
}


# --- data -------------------------------------------------------------------

def test_length_ranges():
    assert list(SIZES) == list(LENGTH_RANGES)
    for size, (lo, hi) in LENGTH_RANGES.items():
        sd = SIZES[size]
        assert (sd.l_min, sd.l_max) == (lo, hi)
        assert lo in LENGTH_SERIES and hi in LENGTH_SERIES


@pytest.mark.parametrize("size", list(TABLE_1))
def test_thread_geometry_matches_table_1(size):
    sd = SIZES[size]
    expected = TABLE_1[size]
    assert sd.l_partial == min(expected)
    assert max(expected) == sd.l_max
    for l in sd.standard_lengths():
        assert sd.thread_geometry(l) == expected.get(l, (None, None)), (size, l)
        assert sd.is_fully_threaded(l) == (l not in expected)


@pytest.mark.parametrize("size", list(LG_FULL))
def test_full_thread_lg_is_3p(size):
    sd = SIZES[size]
    assert 3 * sd.P == pytest.approx(LG_FULL[size])
    p = DIN.validate({"size": size, "length": sd.l_min})
    dims = {d.symbol: d.value for d in DIN.dimensions(p)}
    assert dims["b"] == "to head" and dims["lg max"] == pytest.approx(LG_FULL[size])


def test_thread_length_bands():
    sd = SIZES["M16"]
    assert [sd.thread_length(l) for l in (100, 125, 126, 200, 201)] == [38, 38, 44, 44, 57]
    assert SIZES["M8"].thread_length(150) == 28


@pytest.mark.parametrize("sd", SIZES.values(), ids=list(SIZES))
def test_size_rows_are_consistent(sd):
    assert sd.e_min == pytest.approx(1.14 * sd.s_min, abs=0.005)
    assert sd.v_max == pytest.approx(0.1 * sd.d)
    assert sd.dk_min < sd.dk_max and sd.k_min < sd.k_max
    assert sd.ds_min < sd.d < sd.da_max
    assert sd.d + 2 * sd.r_min <= sd.da_max
    assert sd.dw_min < sd.dk_min
    assert sd.s_nom <= sd.s_min < sd.s_max and sd.t_min < sd.t_nom < sd.t_max
    # lf max = 1.7 r max with r max = (da max - ds max) / 2. Table 1 prints
    # 1.87 for M12 to M16, above the formula's 1.45; never below it.
    assert sd.lf_max >= 1.7 * (sd.da_max - sd.d) / 2 - 0.01
    # Low head and reduced socket compared with ISO 4762 (no M18 / M22
    # there), same head diameter.
    iso = iso4762_data.SIZES.get(sd.size)
    if iso is not None:
        assert sd.dk_max == iso.dk_max
        assert sd.k_max < iso.k_max and sd.s_nom < iso.s_nom
    # The socket's drill point stays inside the head.
    assert socket_point_height(sd) > 0.15


# --- geometry -----------------------------------------------------------------

def check_solid(size, l, thread):
    sd = SIZES[size]
    params = DIN.validate({"size": size, "length": l, "thread": thread})
    part = DIN.build(params)
    assert part.label == f"DIN 7984 - {size} x {l:g}"
    assert part.is_valid
    assert len(part.solids()) == 1
    bb = part.bounding_box()
    tol = 1e-3 * sd.d
    k = sd.k_max
    assert bb.min.Z == pytest.approx(-l, abs=tol)
    assert bb.max.Z == pytest.approx(k, abs=tol)
    assert bb.size.X == pytest.approx(sd.dk_max, abs=tol)
    assert bb.size.Y == pytest.approx(sd.dk_max, abs=tol)
    # Socket empty, head under the drill point and shank solid.
    assert not part.is_inside(Vector(0, 0, k - sd.t_min / 2))
    assert part.is_inside(Vector(0, 0, socket_point_height(sd) / 2))
    assert part.is_inside(Vector(0, 0, -l / 2))
    # Bearing face reaches dw; nothing outside d under the head.
    assert part.is_inside(Vector(sd.dw_min / 2 - 0.01, 0, 0.02))
    assert not part.is_inside(Vector(0.8 * sd.d, 0, -0.05))
    return part


@pytest.mark.parametrize(
    "size,l", [(s, l) for s, sd in SIZES.items() for l in sd.standard_lengths()]
)
def test_simplified_solid(size, l):
    part = check_solid(size, l, "simplified")
    sd = SIZES[size]
    shank = math.pi * (sd.d / 2) ** 2 * l
    head = math.pi * (sd.dk_max / 2) ** 2 * sd.k_max
    assert 0.8 * (shank + head) < part.volume < shank + head


@pytest.mark.parametrize("sd", SIZES.values(), ids=list(SIZES))
def test_socket_volume(sd):
    body = build_body(sd, sd.l_min, "simplified")
    part = DIN.build(DIN.validate({"size": sd.size, "length": sd.l_min}))
    r_d = 0.96 * sd.s_nom / 2
    h = r_d / math.tan(math.radians(SOCKET_DRILL_ANGLE / 2))
    socket = SQRT3 / 2 * sd.s_nom**2 * sd.t_min + math.pi * r_d**2 * h / 3
    assert body.volume - part.volume == pytest.approx(socket, rel=0.01)


def modeled_cases():
    for size, sd in SIZES.items():
        yield size, sd.l_partial
    yield from [("M3", 5), ("M10", 35), ("M24", 40), ("M10", 100)]


@pytest.mark.parametrize("size,l", list(modeled_cases()))
def test_modeled_thread_solid(size, l):
    part = check_solid(size, l, "modeled")
    plain = DIN.build(DIN.validate({"size": size, "length": l}))
    sd = SIZES[size]
    threaded = l if sd.is_fully_threaded(l) else sd.thread_length(l)
    r_mean = sd.d / 2 - 0.2706 * sd.P
    expected = 0.3045 * sd.P**2 * 2 * math.pi * r_mean * threaded / sd.P
    assert plain.volume - part.volume == pytest.approx(expected, rel=0.15)


def test_step_roundtrip():
    params = DIN.validate({"size": "M6", "length": 20, "thread": "modeled"})
    part = DIN.build(params)
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
        {"size": "M30", "length": 60},
        {"size": "M6", "length": 8},
        {"size": "M6", "length": 41},
        {"size": "M12", "length": 90},
        {"size": "M6", "length": "abc"},
        {"size": "M6", "length": "nan"},
        {"size": "M6", "length": 20, "thread": "fancy"},
    ],
)
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        DIN.validate(raw)


def test_parameters_and_names():
    params = {p.name: p for p in DIN.parameters()}
    assert params["size"].kind == "select" and params["length"].kind == "length"
    assert params["length"].preferred["M3"] == [5, 6, 8, 10, 12, 14, 16, 18, 20]
    assert params["length"].limits["M24"] == [40, 100]
    assert params["length"].default in params["length"].preferred[params["size"].default]
    p = DIN.validate({"size": "M8", "length": "40", "thread": "modeled"})
    assert DIN.designation(p) == "DIN 7984 - M8 x 40"
    assert DIN.file_stem(p) == "DIN7984_M8x40_threaded"
    assert DIN.file_stem({**p, "thread": "simplified"}) == "DIN7984_M8x40"
    dims = {d.symbol: d.value for d in DIN.dimensions(p)}
    assert dims["b"] == 22 and dims["lg max"] == 18 and dims["ls min"] == 11.75
    assert dims["k max"] == 5 and dims["s"] == 5


def test_notes():
    notes = DIN.notes(DIN.validate({"size": "M8", "length": "22.5"}))
    assert any("not a preferred length" in n for n in notes)
    assert any("Threaded up to the head" in n for n in notes)
    notes = DIN.notes(DIN.validate({"size": "M10", "length": 60}))
    assert any("Partially threaded" in n for n in notes)
    notes = DIN.notes(DIN.validate({"size": "M14", "length": 40}))
    assert any("brackets" in n for n in notes)
    # Custom lengths follow the table's step: M10 is partial from 40 mm.
    assert DIN.validate({"size": "M10", "length": 39.5}) and SIZES["M10"].is_fully_threaded(39.5)
    assert not SIZES["M10"].is_fully_threaded(40)

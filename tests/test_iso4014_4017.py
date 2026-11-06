import math
import tempfile
from pathlib import Path

import pytest
from build123d import Unit, Vector, export_step, import_step

from standardparts.geometry import SQRT3, MetricThread
from standardparts.screws import THREAD_MODES
from standardparts.standards.base import ParameterError
from standardparts.standards.hexscrew import TOP_CHAMFER_DIA, ISO4014, ISO4017
from standardparts.standards.hexscrew_data import LENGTH_SERIES, SIZES

B4014 = ISO4014()
S4017 = ISO4017()

# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------

# ls min / lg max as printed in ISO 4014:2022 Tables 1 to 4 (M1.6 to M27):
# the first and last length of every size and the rows around the b bands.
TABLE_2022 = {
    "M1.6": {12: (1.25, 3), 16: (5.25, 7)},
    "M2": {16: (4, 6), 20: (8, 10)},
    "M2.5": {16: (2.75, 5), 25: (11.75, 14)},
    "M3": {20: (5.5, 8), 30: (15.5, 18)},
    "M3.5": {20: (4, 7), 35: (19, 22)},
    "M4": {25: (7.5, 11), 40: (22.5, 26)},
    "M5": {25: (5, 9), 50: (30, 34)},
    "M6": {30: (7, 12), 60: (37, 42)},
    "M7": {35: (10, 15), 70: (45, 50)},
    "M8": {40: (11.75, 18), 80: (51.75, 58)},
    "M10": {45: (11.5, 19), 100: (66.5, 74)},
    "M12": {50: (11.25, 20), 120: (81.25, 90)},
    "M14": {55: (11, 21), 120: (76, 86), 130: (80, 90), 140: (90, 100)},
    "M16": {65: (17, 27), 120: (72, 82), 130: (76, 86), 150: (96, 106), 160: (106, 116)},
    "M18": {70: (15.5, 28), 120: (65.5, 78), 130: (69.5, 82), 160: (99.5, 112),
            180: (119.5, 132)},
    "M20": {80: (21.5, 34), 120: (61.5, 74), 130: (65.5, 78), 200: (135.5, 148)},
    "M22": {90: (27.5, 40), 130: (61.5, 74), 200: (131.5, 144), 220: (138.5, 151)},
    "M24": {90: (21, 36), 120: (51, 66), 130: (55, 70), 200: (125, 140), 220: (132, 147),
            240: (152, 167)},
    "M27": {100: (25, 40), 120: (45, 60), 130: (49, 64), 200: (119, 134), 220: (126, 141),
            260: (166, 181)},
}

# ISO 4014:2011 Table 1 (preferred sizes M30 to M64), rows inside the
# ISO 4014:2022 length ranges. The 2011 table prints M36 x 340 as
# ls min = 233, a misprint for 223 (lg max = 243 and lg - 5P = 223), so
# that row is left out.
TABLE_2011 = {
    "M30": {110: (26.5, 44), 120: (36.5, 54), 130: (40.5, 58), 200: (110.5, 128),
            220: (117.5, 135), 300: (197.5, 215)},
    "M36": {140: (36, 56), 200: (96, 116), 220: (103, 123), 360: (243, 263)},
    "M42": {160: (41.5, 64), 200: (81.5, 104), 220: (88.5, 111), 420: (288.5, 311)},
    "M48": {180: (47, 72), 200: (67, 92), 220: (74, 99), 480: (334, 359)},
    "M56": {220: (55.5, 83), 500: (335.5, 363)},
    "M64": {260: (77, 107), 500: (317, 347)},
}


@pytest.mark.parametrize("table", [TABLE_2022, TABLE_2011], ids=["2022", "2011"])
def test_iso4014_thread_geometry_matches_tables(table):
    for size, rows in table.items():
        sd = SIZES[size]
        for l, expected in rows.items():
            assert l in sd.lengths_4014(), (size, l)
            assert sd.thread_geometry_4014(l) == expected, (size, l)


def test_iso4014_2022_ranges_match_table():
    for size, rows in TABLE_2022.items():
        lengths = SIZES[size].lengths_4014()
        assert (lengths[0], lengths[-1]) == (min(rows), max(rows)), size


def _nearest_standard(x):
    # Nearest standard length, ties rounded up (as ISO 4017:2022 does for
    # M3.5 and M7).
    return min(LENGTH_SERIES, key=lambda l: (abs(l - x), -l))


def _greatest_standard(x):
    return max(l for l in LENGTH_SERIES if l <= x + 1e-9)


def test_iso4017_ranges_follow_2022_rules():
    # ISO 4017:2022 Figure 1: shortest 2d rounded to the nearest standard
    # length (120 for M64), greatest 10d or 200, whichever is shorter. The
    # data were read from the table, this checks them against the rule.
    for size, sd in SIZES.items():
        lo = 120 if size == "M64" else _nearest_standard(2 * sd.d)
        hi = _greatest_standard(min(10 * sd.d, 200))
        assert sd.l4017 == (lo, hi), size


def test_iso4014_ranges_follow_2022_rules():
    # ISO 4014:2022 Figure 1: shortest 5d (M5 to M8), 4.5d (M10), 4d (M12
    # to M22), 3.75d (M24 to M60), 220 for M64; greatest 10d or 500.
    # M1.6 to M4 have no rule; their ranges are taken from Table 1.
    for size, sd in SIZES.items():
        d = sd.d
        hi = _greatest_standard(min(10 * d, 500))
        if d < 5:
            assert sd.l4014[1] == hi, size
            continue
        f = 5 if d <= 8 else 4.5 if d == 10 else 4 if d <= 22 else 3.75
        lo = 220 if size == "M64" else _nearest_standard(f * d)
        assert sd.l4014 == (lo, hi), size


@pytest.mark.parametrize("sd", SIZES.values(), ids=list(SIZES))
def test_iso4014_b_follows_iso888(sd):
    for band, add in zip(sd.b, (6, 12, 25)):
        if band is not None:
            assert band == math.floor(2 * sd.d + add + 1e-9)
    for l in sd.lengths_4014():
        ls_min, lg_max = sd.thread_geometry_4014(l)
        assert ls_min > 0
        # Room for the fillet and the 45 deg step from the thread core.
        assert lg_max > sd.r_min + (sd.d - MetricThread(sd.d, sd.P).d1) / 2


@pytest.mark.parametrize("sd", SIZES.values(), ids=list(SIZES))
def test_size_rows_are_consistent(sd):
    assert sd.c_min < sd.c_max
    assert sd.d + 2 * sd.r_min <= sd.da_max
    lengths = sorted(set(sd.lengths_4014()) | set(sd.lengths_4017()))
    assert sd.l4014[0] in LENGTH_SERIES and sd.l4014[1] in LENGTH_SERIES
    assert sd.l4017[0] in LENGTH_SERIES and sd.l4017[1] in LENGTH_SERIES
    for g in {sd.grade_dims(l) for l in lengths}:
        assert g.s_min < sd.s_nom
        assert g.k_min < sd.k_nom < g.k_max
        assert g.kw_min == pytest.approx(0.7 * g.k_min, abs=0.006)
        # e min = 1.13 s min (ISO 4759-1), below the exact corners at s nom.
        assert g.e_min == pytest.approx(1.13 * g.s_min, abs=0.011)
        assert g.e_min < sd.e_nom
        # Washer face fits under the hexagon and inside the top chamfer
        # circle, and the underhead fillet fits on the washer face.
        assert g.dw_min < g.s_min
        assert g.dw_min < TOP_CHAMFER_DIA * sd.s_nom
        assert sd.d + 2 * sd.r_min < g.dw_min
        # The hexagon is taller than the washer face by at least kw.
        assert sd.k_nom - sd.c_max >= g.kw_min


def test_product_grades():
    assert SIZES["M24"].product_grade(150) == "A"
    assert SIZES["M16"].product_grade(160) == "B"
    assert SIZES["M12"].product_grade(120) == "A"
    assert SIZES["M27"].product_grade(55) == "B"
    for sd in SIZES.values():
        for l in set(sd.lengths_4014()) | set(sd.lengths_4017()):
            sd.grade_dims(l)  # data exist for every grade that is used


@pytest.mark.parametrize("sd", SIZES.values(), ids=list(SIZES))
def test_iso4017_thread_runout_within_a(sd):
    # Model: full thread ends 2P below z_thread_end = -(r + (d - d1) / 2).
    # That distance to the bearing face must be within a = 1P to 3P.
    t = MetricThread(sd.d, sd.P)
    a_model = sd.r_min + (sd.d - t.d1) / 2 + 2 * sd.P
    assert sd.a_min_4017 <= a_model <= sd.a_max_4017


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------


def cases(std):
    for size, sd in SIZES.items():
        lengths = std._lengths(sd)
        for l in sorted({lengths[0], lengths[-1]}):
            yield size, l


def modeled_cases(std):
    # Shortest length of every size, longest of a few (the sweep script
    # builds every standard length).
    for size, sd in SIZES.items():
        lengths = std._lengths(sd)
        picks = {lengths[0], lengths[-1]} if size in ("M3", "M10", "M24", "M64") else {lengths[0]}
        for l in sorted(picks):
            yield size, l


def check_solid(std, size, l, thread, head_probes=True):
    sd = SIZES[size]
    params = std.validate({"size": size, "length": l, "thread": thread})
    part = std.build(params)
    assert part.label == std.designation(params)
    assert part.is_valid
    assert len(part.solids()) == 1
    bb = part.bounding_box()
    tol = 1e-3 * sd.d
    assert bb.min.Z == pytest.approx(-l, abs=tol)
    assert bb.max.Z == pytest.approx(sd.k_nom, abs=tol)
    assert bb.size.X == pytest.approx(sd.e_nom, abs=tol)  # corners on X
    assert bb.size.Y == pytest.approx(sd.s_nom, abs=tol)  # flats parallel to X
    g = sd.grade_dims(l)
    k, c, s, R = sd.k_nom, sd.c_max, sd.s_nom, sd.d / 2
    # Point classification is slow on helical faces; the head is the same
    # in both thread modes, so modeled parts only probe the shank.
    if head_probes:
        # Head: solid core and corners, chamfered top corner.
        assert part.is_inside(Vector(0, 0, (c + k) / 2))
        assert part.is_inside(Vector(0.95 * sd.e_nom / 2, 0, c + 0.3 * (k - c)))
        assert not part.is_inside(Vector(0.99 * sd.e_nom / 2, 0, k - 0.01 * s))
        # Washer face: solid inside dw, empty between dw and the hexagon.
        assert part.is_inside(Vector(0, 0.9 * g.dw_min / 2, c / 2))
        assert not part.is_inside(Vector(0, (g.dw_min / 2 + s / 2) / 2, c / 2))
    # Shank.
    assert part.is_inside(Vector(0, 0, -l / 2))
    assert not part.is_inside(Vector(1.05 * R, 0, -l / 2))
    return part


def simplified_volume_bounds(sd, l):
    g = sd.grade_dims(l)
    R = sd.d / 2
    upper = (
        math.pi * R**2 * l
        + SQRT3 / 2 * sd.s_nom**2 * (sd.k_nom - sd.c_max)
        + math.pi * (g.dw_min / 2) ** 2 * sd.c_max
        + 2 * math.pi * (R + sd.r_min) * sd.r_min**2 * (1 - math.pi / 4)  # fillet
    )
    return 0.9 * upper, upper


@pytest.mark.parametrize("size,l", list(cases(B4014)))
def test_iso4014_simplified_solid(size, l):
    sd = SIZES[size]
    part = check_solid(B4014, size, l, "simplified")
    lo, hi = simplified_volume_bounds(sd, l)
    assert lo < part.volume < hi
    # Plain shank above the thread.
    _, lg_max = sd.thread_geometry_4014(l)
    assert part.is_inside(Vector(0.97 * sd.d / 2, 0, -(lg_max + sd.r_min) / 2))


@pytest.mark.parametrize("size,l", list(cases(S4017)))
def test_iso4017_simplified_solid(size, l):
    sd = SIZES[size]
    part = check_solid(S4017, size, l, "simplified")
    lo, hi = simplified_volume_bounds(sd, l)
    assert lo < part.volume < hi


def check_thread_volume(std, part, size, l, threaded):
    sd = SIZES[size]
    plain = std.build(std.validate({"size": size, "length": l}))
    # The ISO 68-1 basic profile removes 0.3045 P^2 per pitch of cross
    # section compared with a plain cylinder at d (computed at mean radius).
    r_mean = sd.d / 2 - 0.2706 * sd.P
    expected = 0.3045 * sd.P**2 * 2 * math.pi * r_mean * threaded / sd.P
    assert plain.volume - part.volume == pytest.approx(expected, rel=0.15)


@pytest.mark.parametrize("size,l", list(modeled_cases(B4014)))
def test_iso4014_modeled_solid(size, l):
    sd = SIZES[size]
    part = check_solid(B4014, size, l, "modeled", head_probes=False)
    check_thread_volume(B4014, part, size, l, sd.b_4014(l))
    _, lg_max = sd.thread_geometry_4014(l)
    assert part.is_inside(Vector(0.97 * sd.d / 2, 0, -(lg_max + sd.r_min) / 2))


@pytest.mark.parametrize("size,l", list(modeled_cases(S4017)))
def test_iso4017_modeled_solid(size, l):
    part = check_solid(S4017, size, l, "modeled", head_probes=False)
    check_thread_volume(S4017, part, size, l, l)


def test_step_roundtrip():
    params = S4017.validate({"size": "M6", "length": 20, "thread": "modeled"})
    part = S4017.build(params)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "part.stp"
        export_step(part, path, unit=Unit.MM)
        assert b"ISO 4017 - M6 x 20" in path.read_bytes()
        imported = import_step(path)
    assert imported.is_valid
    assert imported.volume == pytest.approx(part.volume, rel=1e-4)


# --------------------------------------------------------------------------
# Parameters
# --------------------------------------------------------------------------


@pytest.mark.parametrize("std", [B4014, S4017], ids=["iso4014", "iso4017"])
def test_parameter_schema(std):
    params = {p.name: p for p in std.parameters()}
    assert set(params) == {"size", "length", "thread"}
    assert {p.kind for p in params.values()} <= {"select", "length"}
    length = params["length"]
    assert set(length.preferred) == set(SIZES) == set(length.limits)
    for size, pref in length.preferred.items():
        lo, hi = length.limits[size]
        assert pref and pref[0] == lo and pref[-1] == hi
    assert length.default in length.preferred[params["size"].default]
    assert [o.value for o in params["thread"].options] == list(THREAD_MODES)
    std.describe_json()
    # Defaults validate.
    std.validate({})


def test_designation_and_file_stem():
    p = S4017.validate({"size": "M8", "length": "40", "thread": "modeled"})
    assert S4017.designation(p) == "ISO 4017 - M8 x 40"
    assert S4017.file_stem(p) == "ISO4017_M8x40_threaded"
    p = B4014.validate({"size": "M10", "length": 60})
    assert B4014.designation(p) == "ISO 4014 - M10 x 60"
    assert B4014.file_stem(p) == "ISO4014_M10x60"


@pytest.mark.parametrize("std", [B4014, S4017], ids=["iso4014", "iso4017"])
def test_info_tables(std):
    for size in ["M1.6", "M24", "M64"]:
        sd = SIZES[size]
        lengths = std._lengths(sd)
        for l in lengths[:: max(1, len(lengths) // 4)]:
            p = std.validate({"size": size, "length": l})
            dims = {d.symbol: d.value for d in std.dimensions(p)}
            assert dims["s"] == sd.s_nom and dims["k"] == sd.k_nom
            assert dims["grade"] == sd.product_grade(l)
            assert std.notes(p)


@pytest.mark.parametrize(
    "std,raw",
    [
        (B4014, {"size": "M7.5", "length": 40}),
        (B4014, {"size": "M8", "length": 35}),
        (B4014, {"size": "M8", "length": 81}),
        (B4014, {"size": "M8", "length": "abc"}),
        (B4014, {"size": "M8", "length": "inf"}),
        (B4014, {"size": "M8", "length": 40, "thread": "fancy"}),
        (S4017, {"size": "M8", "length": 12}),
        (S4017, {"size": "M64", "length": 220}),
        (S4017, {"size": "M8", "length": "nan"}),
    ],
)
def test_validation_rejects(std, raw):
    with pytest.raises(ParameterError):
        std.validate(raw)


def test_custom_length_is_flagged():
    p = S4017.validate({"size": "M8", "length": "22.5"})
    assert p["length"] == 22.5
    assert any("not a standard length" in n for n in S4017.notes(p))
    p = B4014.validate({"size": "M16", "length": "155"})
    assert any("grade B" in n for n in B4014.notes(p))
    assert B4014.build(p).is_valid

import math
import tempfile
from pathlib import Path

import pytest
from build123d import Unit, Vector, export_step, import_step

from standardparts.geometry import SQRT3, MetricThread
from standardparts.screws import THREAD_MODES
from standardparts.standards.base import ParameterError
from standardparts.standards.hexscrew_data import LENGTH_SERIES
from standardparts.standards.hexscrew_data import SIZES as COARSE
from standardparts.standards.hexscrew_fine import ISO8676, ISO8765
from standardparts.standards.hexscrew_fine_data import FINE_PITCHES, SIZES

B8765 = ISO8765()
S8676 = ISO8676()

# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------

# ISO 261 fine pitches of the diameters in ISO 8765 / ISO 8676.
ISO261_FINE = {8: {1, 0.75}, 10: {1.25, 1, 0.75}, 12: {1.5, 1.25, 1}, 14: {1.5, 1.25, 1},
               16: {1.5, 1}, 18: {2, 1.5, 1}, 20: {2, 1.5, 1}, 22: {2, 1.5, 1},
               24: {2, 1.5, 1}, 27: {2, 1.5, 1}, 30: {3, 2, 1.5, 1}, 33: {3, 2, 1.5},
               36: {3, 2, 1.5}, 39: {3, 2, 1.5}, 42: {4, 3, 2, 1.5}, 45: {4, 3, 2, 1.5},
               48: {4, 3, 2, 1.5}, 52: {4, 3, 2, 1.5}, 56: {4, 3, 2, 1.5},
               60: {4, 3, 2, 1.5}, 64: {4, 3, 2, 1.5}}

# Preferred (bold) entries of ISO 8765:2022 / ISO 8676:2022 Tables 1 to 4,
# and of ISO 8765:2011 Table 1 for M45 to M64.
PREFERRED = {"M8x1", "M10x1.25", "M12x1.5", "M16x1.5", "M20x2", "M24x2", "M30x2",
             "M36x3", "M42x3", "M48x3", "M56x4", "M64x4"}

# ls min / lg max printed in ISO 8765:2022 Tables 1 to 4: first and last
# length of every size and rows around the b bands and the grade change.
TABLE_8765_2022 = {
    "M8x1": {40: (11.75, 18), 80: (51.75, 58)},
    "M10x1.25": {45: (11.5, 19), 100: (66.5, 74)},
    "M10x1": {45: (11.5, 19), 100: (66.5, 74)},
    "M12x1.5": {50: (11.25, 20), 120: (81.25, 90)},
    "M12x1.25": {50: (11.25, 20), 120: (81.25, 90)},
    "M14x1.5": {55: (11, 21), 120: (76, 86), 130: (80, 90), 140: (90, 100)},
    "M16x1.5": {65: (17, 27), 150: (96, 106), 160: (106, 116)},
    "M18x2": {70: (15.5, 28), 150: (89.5, 102), 160: (99.5, 112), 180: (119.5, 132)},
    "M18x1.5": {70: (15.5, 28), 180: (119.5, 132)},
    "M20x2": {80: (21.5, 34), 150: (85.5, 98), 200: (135.5, 148)},
    "M20x1.5": {80: (21.5, 34), 200: (135.5, 148)},
    "M22x2": {90: (27.5, 40), 150: (81.5, 94), 220: (138.5, 151)},
    "M22x1.5": {90: (27.5, 40), 220: (138.5, 151)},
    "M24x2": {90: (21, 36), 150: (75, 90), 160: (85, 100), 240: (152, 167)},
    "M27x2": {100: (25, 40), 260: (166, 181)},
    "M30x2": {110: (26.5, 44), 120: (36.5, 54), 130: (40.5, 58), 300: (197.5, 215)},
    "M33x2": {120: (30.5, 48), 320: (211.5, 229)},
    "M36x3": {140: (36, 56), 200: (96, 116), 220: (103, 123), 360: (243, 263)},
    "M39x3": {150: (40, 60), 380: (257, 277)},
    "M42x3": {160: (41.5, 64), 420: (288.5, 311)},
}

# Shortest / greatest standard length, ISO 8676:2022 Tables 1 to 4.
RANGES_8676_2022 = {
    "M8": (16, 80), "M10": (20, 100), "M12": (25, 120), "M14": (30, 140),
    "M16": (30, 160), "M18": (35, 180), "M20": (40, 200), "M22": (45, 200),
    "M24": (50, 200), "M27": (55, 200), "M30": (60, 200), "M33": (65, 200),
    "M36": (70, 200), "M39": (80, 200), "M42": (80, 200),
}


def test_size_pitch_combinations():
    assert len(SIZES) == len(FINE_PITCHES) == 26
    assert {ts.sd.size for ts in SIZES.values()} == {
        s for s, sd in COARSE.items() if sd.d >= 8
    }
    for key, ts in SIZES.items():
        assert key == f"{ts.sd.size}x{ts.P:g}"
        assert ts.fine
        assert ts.P in ISO261_FINE[ts.sd.d] and ts.P < ts.sd.P
        assert ts.preferred == (key in PREFERRED)
        # Preferred sizes are the preferred coarse diameters.
        assert not ts.preferred or ts.sd.preferred
    two = {k for k, ts in SIZES.items()
           if sum(t.sd is ts.sd for t in SIZES.values()) == 2}
    assert two == {"M10x1.25", "M10x1", "M12x1.5", "M12x1.25", "M18x2", "M18x1.5",
                   "M20x2", "M20x1.5", "M22x2", "M22x1.5"}


def test_iso8765_thread_geometry_matches_2022_table():
    # lg max = l - b, ls min = lg max - 5P with the coarse pitch.
    for key, rows in TABLE_8765_2022.items():
        sd = SIZES[key].sd
        lengths = B8765._lengths(sd)
        assert (lengths[0], lengths[-1]) == (min(rows), max(rows)), key
        for l, expected in rows.items():
            assert l in lengths
            assert sd.thread_geometry_4014(l) == expected, (key, l)


def test_iso8676_ranges_match_2022_table():
    for key, ts in SIZES.items():
        lengths = S8676._lengths(ts.sd)
        if ts.sd.size in RANGES_8676_2022:
            assert (lengths[0], lengths[-1]) == RANGES_8676_2022[ts.sd.size], key
        else:
            # Table 5 (M45 to M64) is not in the preview: 2022 rules.
            assert lengths[-1] == 200
            # Shortest: 2d to the nearest standard length, ties up.
            lo = 120 if ts.sd.size == "M64" else min(
                LENGTH_SERIES, key=lambda l: (abs(l - 2 * ts.sd.d), -l))
            assert lengths[0] == lo, key


def test_head_values_match_2022_tables():
    # Spot checks against ISO 8676:2022 / ISO 8765:2022 Tables 1 to 4.
    m14 = SIZES["M14x1.5"].sd
    assert (m14.A.dw_min, m14.A.e_min, m14.k_nom, m14.r_min, m14.s_nom) == (
        19.64, 23.36, 8.8, 0.6, 21)
    m18 = SIZES["M18x2"].sd
    assert (m18.A.dw_min, m18.B.dw_min, m18.da_max, m18.b[:2]) == (25.34, 24.85, 20.2, (42, 48))
    m42 = SIZES["M42x3"].sd
    assert (m42.B.dw_min, m42.da_max, m42.r_min, m42.k_nom, m42.B.kw_min) == (
        59.95, 45.6, 1.2, 26, 17.91)
    assert SIZES["M22x1.5"].sd.b == (50, 56, 69)
    assert SIZES["M24x2"].sd.b == (54, 60, 73)


def test_product_grades():
    assert SIZES["M24x2"].sd.product_grade(150) == "A"
    assert SIZES["M24x2"].sd.product_grade(160) == "B"
    assert SIZES["M16x1.5"].sd.product_grade(160) == "B"
    assert SIZES["M27x2"].sd.product_grade(100) == "B"
    for ts in SIZES.values():
        for l in set(B8765._lengths(ts.sd)) | set(S8676._lengths(ts.sd)):
            ts.sd.grade_dims(l)


def a_model(ts):
    """First full thread of the modeled ISO 8676 screw below the bearing face."""
    t = MetricThread(ts.sd.d, ts.P)
    return ts.sd.r_min + (ts.sd.d - t.d1) / 2 + 2 * ts.P


# Sizes whose fillet r min, 45 deg core step and 2P runout add up to a bit
# more than a max = 3P (the 2P runout is fixed in screws.threaded_screw).
A_OVER = {"M12x1.25", "M20x1.5", "M22x1.5", "M27x2", "M30x2", "M33x2", "M48x3",
          "M56x4", "M60x4", "M64x4"}


@pytest.mark.parametrize("key", list(SIZES))
def test_iso8676_thread_runout_near_a(key):
    ts = SIZES[key]
    a = a_model(ts)
    assert ts.P <= a
    if key in A_OVER:
        assert 3 * ts.P < a <= 3 * ts.P + 0.23
    else:
        assert a <= 3 * ts.P


@pytest.mark.parametrize("key", list(SIZES))
def test_iso8765_thread_fits(key):
    ts = SIZES[key]
    t = MetricThread(ts.sd.d, ts.P)
    for l in B8765._lengths(ts.sd):
        ls_min, lg_max = ts.sd.thread_geometry_4014(l)
        assert ls_min > 0
        assert lg_max > ts.sd.r_min + (ts.sd.d - t.d1) / 2


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------


def cases(std):
    for key, ts in SIZES.items():
        lengths = std._lengths(ts.sd)
        for l in sorted({lengths[0], lengths[-1]}):
            yield key, l


MODELED_LONG = ("M8x1", "M20x1.5", "M64x4")


def modeled_cases(std):
    # Shortest length of every size, longest of a few (the sweep script
    # builds every standard length).
    for key, ts in SIZES.items():
        lengths = std._lengths(ts.sd)
        picks = {lengths[0], lengths[-1]} if key in MODELED_LONG else {lengths[0]}
        for l in sorted(picks):
            yield key, l


def check_solid(std, key, l, thread, head_probes=True):
    sd = SIZES[key].sd
    params = std.validate({"size": key, "length": l, "thread": thread})
    part = std.build(params)
    assert part.label == std.designation(params)
    assert part.is_valid
    assert len(part.solids()) == 1
    bb = part.bounding_box()
    tol = 1e-3 * sd.d
    assert bb.min.Z == pytest.approx(-l, abs=tol)
    assert bb.max.Z == pytest.approx(sd.k_nom, abs=tol)
    assert bb.size.X == pytest.approx(sd.e_nom, abs=tol)
    assert bb.size.Y == pytest.approx(sd.s_nom, abs=tol)
    g = sd.grade_dims(l)
    k, c, s, R = sd.k_nom, sd.c_max, sd.s_nom, sd.d / 2
    if head_probes:
        assert part.is_inside(Vector(0, 0, (c + k) / 2))
        assert part.is_inside(Vector(0.95 * sd.e_nom / 2, 0, c + 0.3 * (k - c)))
        assert not part.is_inside(Vector(0.99 * sd.e_nom / 2, 0, k - 0.01 * s))
        assert part.is_inside(Vector(0, 0.9 * g.dw_min / 2, c / 2))
        assert not part.is_inside(Vector(0, (g.dw_min / 2 + s / 2) / 2, c / 2))
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
        + 2 * math.pi * (R + sd.r_min) * sd.r_min**2 * (1 - math.pi / 4)
    )
    return 0.9 * upper, upper


@pytest.mark.parametrize("key,l", list(cases(B8765)))
def test_iso8765_simplified_solid(key, l):
    sd = SIZES[key].sd
    part = check_solid(B8765, key, l, "simplified")
    lo, hi = simplified_volume_bounds(sd, l)
    assert lo < part.volume < hi
    _, lg_max = sd.thread_geometry_4014(l)
    assert part.is_inside(Vector(0.97 * sd.d / 2, 0, -(lg_max + sd.r_min) / 2))


@pytest.mark.parametrize("key,l", list(cases(S8676)))
def test_iso8676_simplified_solid(key, l):
    sd = SIZES[key].sd
    part = check_solid(S8676, key, l, "simplified")
    lo, hi = simplified_volume_bounds(sd, l)
    assert lo < part.volume < hi


def check_thread_volume(std, part, key, l, threaded):
    ts = SIZES[key]
    P = ts.P
    plain = std.build(std.validate({"size": key, "length": l}))
    # ISO 68-1 basic profile: 0.3045 P^2 per pitch less than a cylinder at d.
    # With the coarse pitch it would be 17% to 67% more.
    r_mean = ts.sd.d / 2 - 0.2706 * P
    expected = 0.3045 * P**2 * 2 * math.pi * r_mean * threaded / P
    assert plain.volume - part.volume == pytest.approx(expected, rel=0.1)


@pytest.mark.parametrize("key,l", list(modeled_cases(B8765)))
def test_iso8765_modeled_solid(key, l):
    sd = SIZES[key].sd
    part = check_solid(B8765, key, l, "modeled", head_probes=False)
    check_thread_volume(B8765, part, key, l, sd.b_4014(l))
    _, lg_max = sd.thread_geometry_4014(l)
    assert part.is_inside(Vector(0.97 * sd.d / 2, 0, -(lg_max + sd.r_min) / 2))


@pytest.mark.parametrize("key,l", list(modeled_cases(S8676)))
def test_iso8676_modeled_solid(key, l):
    part = check_solid(S8676, key, l, "modeled", head_probes=False)
    check_thread_volume(S8676, part, key, l, l)


def test_modeled_pitch():
    # Sample a line at the pitch diameter over three fine pitches. With the
    # ridge at the fine pitch the solid samples lie in phase with it: the
    # mean of exp(2 pi i z / P) over them has length about 2 / pi (0.64) for
    # a half-filled period. A ridge at the coarse 1.5 mm would average out.
    key = "M10x1"
    ts = SIZES[key]
    t = MetricThread(ts.sd.d, ts.P)
    l = S8676._lengths(ts.sd)[0]
    part = S8676.build(S8676.validate({"size": key, "length": l, "thread": "modeled"}))
    n, steps = 3, 16
    zs = [-l / 2 + (i + 0.5) * ts.P / steps for i in range(n * steps)]
    hits = [z for z in zs if part.is_inside(Vector(t.d2 / 2, 0, z))]
    assert len(hits) / len(zs) == pytest.approx(0.5, abs=0.07)
    c = sum(math.cos(2 * math.pi * z / ts.P) for z in hits) / len(hits)
    s = sum(math.sin(2 * math.pi * z / ts.P) for z in hits) / len(hits)
    assert math.hypot(c, s) > 0.5


def test_step_roundtrip():
    params = B8765.validate({"size": "M12x1.5", "length": 50, "thread": "modeled"})
    part = B8765.build(params)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "part.stp"
        export_step(part, path, unit=Unit.MM)
        assert b"ISO 8765 - M12 x 1.5 x 50" in path.read_bytes()
        imported = import_step(path)
    assert imported.is_valid
    assert imported.volume == pytest.approx(part.volume, rel=1e-4)


# --------------------------------------------------------------------------
# Parameters
# --------------------------------------------------------------------------


@pytest.mark.parametrize("std", [B8765, S8676], ids=["iso8765", "iso8676"])
def test_parameter_schema(std):
    params = {p.name: p for p in std.parameters()}
    assert set(params) == {"size", "length", "thread"}
    size = params["size"]
    assert [o.value for o in size.options] == list(SIZES)
    labels = {o.value: o.label for o in size.options}
    assert labels["M10x1.25"] == "M10 x 1.25"
    assert labels["M10x1"] == "M10 x 1 (non-preferred)"
    length = params["length"]
    assert set(length.preferred) == set(SIZES) == set(length.limits)
    for key, pref in length.preferred.items():
        lo, hi = length.limits[key]
        assert pref and pref[0] == lo and pref[-1] == hi
    assert length.default in length.preferred[size.default]
    assert [o.value for o in params["thread"].options] == list(THREAD_MODES)
    std.describe_json()
    std.validate({})


def test_ids_and_titles():
    assert (B8765.id, B8765.title, S8676.id, S8676.title) == (
        "iso8765", "ISO 8765", "iso8676", "ISO 8676")


def test_designation_and_file_stem():
    p = B8765.validate({"size": "M12x1.5", "length": "50"})
    assert B8765.designation(p) == "ISO 8765 - M12 x 1.5 x 50"
    assert B8765.file_stem(p) == "ISO8765_M12x1.5x50"
    p = S8676.validate({"size": "M10x1.25", "length": 40, "thread": "modeled"})
    assert S8676.designation(p) == "ISO 8676 - M10 x 1.25 x 40"
    assert S8676.file_stem(p) == "ISO8676_M10x1.25x40_threaded"


@pytest.mark.parametrize("std", [B8765, S8676], ids=["iso8765", "iso8676"])
def test_info_tables(std):
    for key in ["M8x1", "M20x1.5", "M64x4"]:
        ts = SIZES[key]
        lengths = std._lengths(ts.sd)
        for l in lengths[:: max(1, len(lengths) // 4)]:
            p = std.validate({"size": key, "length": l})
            dims = {d.symbol: d.value for d in std.dimensions(p)}
            assert dims["P"] == ts.P
            assert dims["s"] == ts.sd.s_nom and dims["k"] == ts.sd.k_nom
            assert dims["d3"] == pytest.approx(ts.sd.d - 1.226869 * ts.P, abs=1e-3)
            assert dims["grade"] == ts.sd.product_grade(l)
            notes = " ".join(std.notes(p))
            assert "Fine pitch thread " + ts.name in notes
    p = S8676.validate({"size": "M20x1.5", "length": 40})
    dims = {d.symbol: d.value for d in S8676.dimensions(p)}
    assert (dims["a max"], dims["a min"]) == (4.5, 1.5)
    assert any("non-preferred" in n for n in S8676.notes(p))


@pytest.mark.parametrize(
    "std,raw",
    [
        (B8765, {"size": "M10", "length": 50}),       # coarse key
        (B8765, {"size": "M10x1.5", "length": 50}),   # coarse pitch
        (B8765, {"size": "M8x1", "length": 35}),
        (B8765, {"size": "M8x1", "length": 85}),
        (B8765, {"size": "M8x1", "length": "abc"}),
        (B8765, {"size": "M8x1", "length": 40, "thread": "fancy"}),
        (S8676, {"size": "M6x0.75", "length": 20}),
        (S8676, {"size": "M8x1", "length": 12}),
        (S8676, {"size": "M64x4", "length": 220}),
        (S8676, {"size": "M8x1", "length": "nan"}),
    ],
)
def test_validation_rejects(std, raw):
    with pytest.raises(ParameterError):
        std.validate(raw)


def test_custom_length_is_flagged():
    p = S8676.validate({"size": "M10x1", "length": "22.5"})
    assert p["length"] == 22.5
    assert any("not a standard length for M10 x 1" in n for n in S8676.notes(p))
    p = B8765.validate({"size": "M16x1.5", "length": "155"})
    assert any("grade B" in n for n in B8765.notes(p))
    assert B8765.build(p).is_valid

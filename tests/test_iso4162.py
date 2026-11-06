import math
import tempfile
from pathlib import Path

import pytest
from build123d import Unit, Vector, export_step, import_step

from standardparts.geometry import SQRT3, MetricThread, chamfered_hex
from standardparts.screws import THREAD_MODES
from standardparts.standards.base import ParameterError
from standardparts.standards.flange import Flange, hex_overlap_volume
from standardparts.standards.iso4162 import (
    CORE_RADIUS,
    HEX_BOTTOM_FRACTIONS,
    ISO4162,
    flange,
    model_kw,
    z_thread_end,
)
from standardparts.standards.iso4162_data import (
    LENGTH_SERIES,
    SIZES,
    TOP_CHAMFER_ANGLE,
    TOP_CHAMFER_DIA,
)

STD = ISO4162()

# ISO 261 coarse pitches.
COARSE = {5: 0.8, 6: 1, 8: 1.25, 10: 1.5, 12: 1.75, 14: 2, 16: 2}

# ls min / lg max as printed in ISO 4162:1990 Table 1: the first partially
# threaded length of every size, the last length, rows around the b bands
# and a few in between.
TABLE = {
    "M5": {25: (5, 9), 35: (15, 19), 50: (30, 34)},
    "M6": {30: (7, 12), 45: (22, 27), 60: (37, 42)},
    "M8": {35: (6.75, 13), 60: (31.75, 38), 80: (51.75, 58)},
    "M10": {40: (6.5, 14), 80: (46.5, 54), 100: (66.5, 74)},
    "M12": {45: (6.25, 15), 80: (41.25, 50), 120: (81.25, 90)},
    "M14": {50: (6, 16), 110: (66, 76), 120: (76, 86), 130: (80, 90), 140: (90, 100)},
    "M16": {55: (7, 17), 80: (32, 42), 120: (72, 82), 130: (76, 86), 150: (96, 106),
            160: (106, 116)},
}
# Standard length range and longest length threaded to the head (the
# continuous stepped line), ISO 4162:1990 Table 1.
RANGES = {
    "M5": (10, 50, 20), "M6": (12, 60, 25), "M8": (16, 80, 30), "M10": (20, 100, 35),
    "M12": (25, 120, 40), "M14": (30, 140, 45), "M16": (35, 160, 50),
}

# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------


def test_thread_geometry_matches_table():
    for size, rows in TABLE.items():
        sd = SIZES[size]
        for l, expected in rows.items():
            assert l in sd.standard_lengths(), (size, l)
            assert not sd.threaded_to_head(l)
            assert sd.thread_geometry(l) == expected, (size, l)


def test_length_ranges_match_table():
    assert set(RANGES) == set(SIZES)
    for size, (lo, hi, to_head) in RANGES.items():
        sd = SIZES[size]
        lengths = sd.standard_lengths()
        assert (lengths[0], lengths[-1]) == (lo, hi), size
        assert sd.l_to_head == to_head
        heads = [l for l in lengths if sd.threaded_to_head(l)]
        assert heads and heads[-1] == to_head
        first = lengths[len(heads)]
        assert sd.thread_geometry(first)[0] > 0


@pytest.mark.parametrize("sd", SIZES.values(), ids=list(SIZES))
def test_size_rows_are_consistent(sd):
    assert sd.P == COARSE[sd.d]
    assert sd.preferred == (sd.size != "M14")
    assert sd.b1 == 2 * sd.d + 6
    assert sd.b2 is None or sd.b2 == 2 * sd.d + 12
    # The table lists b for 125 < l <= 200 from M8 up, needed from M14 up.
    assert sd.b2 is not None or sd.lengths[1] <= 125
    assert sd.ds_min < sd.d
    assert sd.s_min < sd.s_max
    # Driving feature of product grade B: e min = 1.12 s min (ISO 4759-1).
    assert sd.e_min == pytest.approx(1.12 * sd.s_min, abs=0.006)
    assert sd.e_min < sd.e_nom
    assert sd.d + 2 * sd.r1_min <= sd.da_max < sd.dw_min < sd.dc_max
    assert sd.e_nom < sd.dw_min
    assert sd.r1_min < sd.lf_max
    assert sd.lengths[0] in LENGTH_SERIES and sd.lengths[1] in LENGTH_SERIES
    for l in sd.standard_lengths():
        if not sd.threaded_to_head(l):
            ls_min, lg_max = sd.thread_geometry(l)
            assert ls_min > 0
            # Room for the fillet and the 45 deg step from the thread core.
            assert lg_max > sd.r1_min + (sd.d - MetricThread(sd.d, sd.P).d1) / 2


@pytest.mark.parametrize("sd", SIZES.values(), ids=list(SIZES))
def test_model_geometry_within_standard(sd):
    fl = flange(sd)
    fl.check()
    # Bearing face reaches at least dw min; the rim stays inside dc.
    assert fl.bearing_dia >= sd.dw_min - 1e-9
    assert fl.rim_top[0] <= sd.dc_max / 2 + 1e-9
    # Hexagon corners sit on the flange cone, inside the rim.
    assert sd.e_nom / 2 < fl.rim_top[0]
    # Wrenching height of the model is above kw min, and the top chamfer
    # circle is at least s max - 15 % (Figure 1).
    assert model_kw(sd) >= sd.kw_min
    assert TOP_CHAMFER_DIA >= 0.85
    # Thread runout when threaded to the head stays within 3P.
    t = MetricThread(sd.d, sd.P)
    a_model = sd.r1_min + (sd.d - t.d1) / 2 + 2 * sd.P
    assert a_model <= 3 * sd.P


def test_hex_overlap_matches_occt():
    # The analytic overlap used to check the fuse, against an OCCT
    # intersection for one size.
    from standardparts.geometry import revolve_profile

    sd = SIZES["M10"]
    fl = flange(sd)
    s, k = sd.s_nom, sd.k_max
    r_core = CORE_RADIUS * s
    z_core = (fl.height(r_core) + k) / 2
    body = revolve_profile([(0.0, 0.0), *fl.profile(r_core, z_core)])
    z_hex = HEX_BOTTOM_FRACTIONS[0] * fl.height(s / SQRT3)
    hexagon = chamfered_hex(s, z_hex, k, TOP_CHAMFER_DIA * s, None, TOP_CHAMFER_ANGLE)
    common = (body & hexagon).volume
    assert hex_overlap_volume(s, z_hex, fl, r_core, z_core) == pytest.approx(common, rel=1e-6)


def test_flange_rim_fallback():
    # Thick flange with little rim: the tangent round would start inside dw.
    fl = flange(SIZES["M16"])
    assert not fl.rim_tangent
    assert fl.bearing_dia == pytest.approx(fl.dw)
    assert flange(SIZES["M8"]).rim_tangent
    with pytest.raises(ValueError):
        Flange(10, 9, 0.1, 25).check()


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------


def _arc_points(p0, mid, p1, n=400):
    (x1, y1), (x2, y2), (x3, y3) = p0, mid, p1
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    ux = ((x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1) + (x3**2 + y3**2) * (y1 - y2)) / d
    uy = ((x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3) + (x3**2 + y3**2) * (x2 - x1)) / d
    rad = math.hypot(x1 - ux, y1 - uy)
    a0, am, a1 = (math.atan2(p[1] - uy, p[0] - ux) for p in (p0, mid, p1))
    span = (a1 - a0) % (2 * math.pi)
    if (am - a0) % (2 * math.pi) > span:  # mid not on the ccw arc: go cw
        span -= 2 * math.pi
    return [(ux + rad * math.cos(a0 + span * i / n), uy + rad * math.sin(a0 + span * i / n))
            for i in range(1, n + 1)]


def revolved_volume(items):
    """Volume of a revolved (radius, z) profile, arcs finely discretized."""
    pts = [items[0]]
    for it in items[1:]:
        if isinstance(it[0], str):
            pts += _arc_points(pts[-1], it[1], it[2])
        else:
            pts.append(it)
    v = 0.0
    for (r0, z0), (r1, z1) in zip(pts, pts[1:] + pts[:1]):
        v += (z1 - z0) * (r0 * r0 + r0 * r1 + r1 * r1)
    return abs(v) * math.pi / 3


def analytic_simplified_volume(sd, l):
    """Independent volume of the simplified bolt: revolved profile (Pappus
    on a fine polygon) plus the hexagon minus their overlap."""
    t = MetricThread(sd.d, sd.P)
    R, r, r_tip = sd.d / 2, sd.r1_min, t.d3 / 2
    fl = flange(sd)
    s, k = sd.s_nom, sd.k_max
    r_core = CORE_RADIUS * s
    z_core = (fl.height(r_core) + k) / 2
    rev = revolved_volume([
        (0.0, -l), (r_tip, -l), (R, -l + (R - r_tip)), (R, -r),
        ("arc", (R + r - r / math.sqrt(2), -r + r / math.sqrt(2)), (R + r, 0.0)),
        *fl.profile(r_core, z_core),
    ])
    z_hex = HEX_BOTTOM_FRACTIONS[0] * fl.height(s / SQRT3)
    hexagon = chamfered_hex(s, z_hex, k, TOP_CHAMFER_DIA * s, None, TOP_CHAMFER_ANGLE)
    return rev + hexagon.volume - hex_overlap_volume(s, z_hex, fl, r_core, z_core)


def cases():
    for size, sd in SIZES.items():
        lengths = sd.standard_lengths()
        first_partial = next(l for l in lengths if not sd.threaded_to_head(l))
        for l in sorted({lengths[0], sd.l_to_head, first_partial, lengths[-1]}):
            yield size, l


def modeled_cases():
    # Shortest length of every size, plus the first partially threaded and
    # the longest of two sizes (the sweep script builds every length).
    for size, sd in SIZES.items():
        lengths = sd.standard_lengths()
        picks = {lengths[0]}
        if size in ("M5", "M16"):
            picks |= {lengths[-1], next(l for l in lengths if not sd.threaded_to_head(l))}
        for l in sorted(picks):
            yield size, l


def check_solid(size, l, thread, head_probes=True):
    sd = SIZES[size]
    params = STD.validate({"size": size, "length": l, "thread": thread})
    part = STD.build(params)
    assert part.label == STD.designation(params)
    assert part.is_valid
    assert len(part.solids()) == 1
    bb = part.bounding_box()
    tol = 1e-3 * sd.d
    assert bb.min.Z == pytest.approx(-l, abs=tol)
    assert bb.max.Z == pytest.approx(sd.k_max, abs=tol)
    # The flange is the widest part.
    assert bb.size.X == pytest.approx(sd.dc_max, abs=tol)
    assert bb.size.Y == pytest.approx(sd.dc_max, abs=tol)
    R = sd.d / 2
    if head_probes:
        fl = flange(sd)
        s, k, e2 = sd.s_nom, sd.k_max, sd.e_nom / 2
        z_mid = (fl.height(e2) + k) / 2
        # Hexagon: corners on X, flats parallel to X, chamfered top corner.
        assert part.is_inside(Vector(0.97 * e2, 0, z_mid))
        assert not part.is_inside(Vector(0, 1.03 * s / 2, z_mid))
        assert part.is_inside(Vector(0, 0.97 * s / 2, z_mid))
        assert not part.is_inside(Vector(0.99 * e2, 0, k - 0.01 * s))
        assert part.is_inside(Vector(0, 0, k - 0.01 * s))
        # Flange: solid at dw just above the bearing face and just below c,
        # empty above the cone, nothing below the bearing face.
        rw = sd.dw_min / 2
        assert part.is_inside(Vector(0, rw, 0.02 * sd.c_min))
        assert part.is_inside(Vector(rw, 0, 0.95 * sd.c_min))
        assert not part.is_inside(Vector(rw, 0, 1.05 * sd.c_min))
        assert part.is_inside(Vector(0, 0.99 * fl.bearing_dia / 2, 0.02 * sd.c_min))
        assert not part.is_inside(Vector(0, 1.2 * R, -0.02 * sd.c_min))
        assert not part.is_inside(Vector(0.998 * sd.dc_max / 2, 0, fl.edge_height + 0.05))
    # Shank.
    assert part.is_inside(Vector(0, 0, -l / 2))
    assert not part.is_inside(Vector(1.05 * R, 0, -l / 2))
    if not sd.threaded_to_head(l):
        # Plain shank at d above the thread.
        lg_max = sd.thread_geometry(l)[1]
        assert part.is_inside(Vector(0.97 * R, 0, -(lg_max + sd.r1_min) / 2))
    return part


@pytest.mark.parametrize("size,l", list(cases()))
def test_simplified_solid(size, l):
    part = check_solid(size, l, "simplified")
    assert part.volume == pytest.approx(analytic_simplified_volume(SIZES[size], l), rel=1e-5)


@pytest.mark.parametrize("size,l", list(modeled_cases()))
def test_modeled_solid(size, l):
    sd = SIZES[size]
    part = check_solid(size, l, "modeled", head_probes=False)
    plain = STD.build(STD.validate({"size": size, "length": l}))
    # The ISO 68-1 basic profile removes 0.3045 P^2 per pitch of cross
    # section compared with a plain cylinder at d (at the mean radius).
    threaded = l + z_thread_end(sd, l)
    r_mean = sd.d / 2 - 0.2706 * sd.P
    expected = 0.3045 * sd.P**2 * 2 * math.pi * r_mean * threaded / sd.P
    assert plain.volume - part.volume == pytest.approx(expected, rel=0.15)


def test_step_roundtrip():
    params = STD.validate({"size": "M8", "length": 30, "thread": "modeled"})
    part = STD.build(params)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "part.stp"
        export_step(part, path, unit=Unit.MM)
        assert b"ISO 4162 - M8 x 30" in path.read_bytes()
        imported = import_step(path)
    assert imported.is_valid
    assert imported.volume == pytest.approx(part.volume, rel=1e-4)


# --------------------------------------------------------------------------
# Parameters
# --------------------------------------------------------------------------


def test_parameter_schema():
    params = {p.name: p for p in STD.parameters()}
    assert set(params) == {"size", "length", "thread"}
    assert {p.kind for p in params.values()} <= {"select", "length"}
    length = params["length"]
    assert set(length.preferred) == set(SIZES) == set(length.limits)
    for size, pref in length.preferred.items():
        lo, hi = length.limits[size]
        assert pref and pref[0] == lo and pref[-1] == hi
    assert length.default in length.preferred[params["size"].default]
    assert [o.value for o in params["thread"].options] == list(THREAD_MODES)
    STD.describe_json()
    STD.validate({})


def test_designation_and_file_stem():
    p = STD.validate({"size": "M8", "length": "30"})
    assert STD.designation(p) == "ISO 4162 - M8 x 30"
    assert STD.file_stem(p) == "ISO4162_M8x30"
    p = STD.validate({"size": "M8", "length": 30, "thread": "modeled"})
    assert STD.file_stem(p) == "ISO4162_M8x30_threaded"


def test_info_tables():
    for size, sd in SIZES.items():
        for l in sd.standard_lengths():
            p = STD.validate({"size": size, "length": l})
            dims = {d.symbol: d for d in STD.dimensions(p)}
            assert dims["s"].value == sd.s_nom and dims["dc max"].value == sd.dc_max
            assert dims["δ"].unit == "°"
            notes = " ".join(STD.notes(p))
            if sd.threaded_to_head(l):
                assert dims["b"].value == "to head" and "Threaded up to the head" in notes
            else:
                assert dims["lg max"].value == sd.thread_geometry(l)[1]
                assert "Partially threaded" in notes
    assert "non-preferred" in " ".join(STD.notes(STD.validate({"size": "M14", "length": 50})))


@pytest.mark.parametrize(
    "raw",
    [
        {"size": "M4", "length": 20},
        {"size": "M20", "length": 50},
        {"size": "M8", "length": 12},
        {"size": "M8", "length": 81},
        {"size": "M8", "length": "abc"},
        {"size": "M8", "length": "inf"},
        {"size": "M8", "length": "nan"},
        {"size": "M8", "length": 40, "thread": "fancy"},
    ],
)
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        STD.validate(raw)


def test_custom_length_is_flagged():
    p = STD.validate({"size": "M8", "length": "32.5"})
    assert p["length"] == 32.5
    assert any("not a standard length" in n for n in STD.notes(p))
    part = STD.build(p)
    assert part.is_valid and len(part.solids()) == 1

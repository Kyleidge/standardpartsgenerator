import math
import tempfile
from pathlib import Path

import pytest
from build123d import Unit, Vector, export_step, import_step

from standardparts.geometry import MetricThread, chamfered_hex
from standardparts.nuts import Countersink, internal_thread_volume
from standardparts.standards import ParameterError
from standardparts.standards.din1587 import (
    DIN1587,
    ThreadEnd,
    blind_thread_volume,
    crown_thickness,
    dome_volume,
    drill_floor,
    is_flattened,
    point_crown,
)
from standardparts.standards.din1587_data import (
    COUNTERSINK_ANGLE,
    DRILL_POINT_ANGLE,
    SIZES,
)

DIN = DIN1587()
SQRT3 = math.sqrt(3)
TAN60 = math.tan(math.radians(COUNTERSINK_ANGLE / 2))

# ISO 261 coarse pitches.
COARSE = {4: 0.7, 5: 0.8, 6: 1, 8: 1.25, 10: 1.5, 12: 1.75, 14: 2, 16: 2, 18: 2.5,
          20: 2.5, 22: 2.5, 24: 3}
# ISO widths across flats (DIN 1587:2000 dropped 17, 19, 22 and 32).
ISO_S = {4: 7, 5: 8, 6: 10, 8: 13, 10: 16, 12: 18, 14: 21, 16: 24, 18: 27, 20: 30,
         22: 34, 24: 36}

# Modeled sizes sampled in the test suite: type A (run-out) smallest and
# largest, type B (undercut) smallest and largest (multi-segment ridge).
# The full sweep of every size in both modes was run separately.
MODELED_SAMPLE = ["M4", "M10", "M12", "M24"]
# DIN 1587:2000 gives x (type A) up to M10 and g (type B) from M12.
TYPE_A = {"M4", "M5", "M6", "M8", "M10"}


def d1(sd):
    return sd.D - 1.25 * SQRT3 / 2 * sd.P


def drill_height(sd):
    return d1(sd) / 2 / math.tan(math.radians(DRILL_POINT_ANGLE / 2))


def z_tip(sd):
    """Deepest point of the bore: the drill point tip, or the floor that
    keeps w min."""
    return min(sd.t_nom + drill_height(sd), sd.h - sd.w_min)


def tip_volume(sd):
    r = d1(sd) / 2
    hc = drill_height(sd)
    if sd.t_nom + hc <= sd.h - sd.w_min:
        return math.pi * r * r * hc / 3
    a = sd.h - sd.w_min - sd.t_nom
    rf = r * (1 - a / hc)
    return math.pi * a / 3 * (r * r + r * rf + rf * rf)


def build(size, thread="simplified"):
    return DIN.build(DIN.validate({"size": size, "thread": thread}))


@pytest.mark.parametrize("sd", SIZES.values(), ids=list(SIZES))
def test_size_rows_are_consistent(sd):
    assert sd.P == COARSE[sd.D]
    assert sd.s == ISO_S[sd.D]
    # The dome radius is dk / 2; the dome fits inside the flats.
    assert 2 * sd.r == pytest.approx(sd.dk_max, abs=0.021)
    assert sd.dk_max < sd.s
    # A cylindrical part of the dome is left between hexagon and sphere.
    assert sd.h - sd.r - sd.m_max > 1
    assert sd.e_min < sd.e_nom
    assert sd.t_min < sd.t_nom < sd.t_max
    assert sd.t_max - sd.t_min == pytest.approx(0.7, abs=0.31)
    # Thread run-out x = 2P.
    assert sd.x_max == pytest.approx(2 * sd.P)
    assert sd.D < sd.da_max < sd.dw_min < sd.s
    assert sd.end_type == ("A" if sd.size in TYPE_A else "B")
    # Undercut (type B): 3.5 P to 3.75 P wide.
    if sd.end_type == "B":
        assert 3.5 * sd.P < sd.g_max < 3.75 * sd.P
    # The bore keeps w min on the axis; where a full 120 deg point would
    # not, it is cut flat with a real flat face left.
    assert crown_thickness(sd) >= sd.w_min
    assert is_flattened(sd) == (point_crown(sd) < sd.w_min)
    if is_flattened(sd):
        assert drill_floor(sd) > sd.t_max
        assert sd.t_nom + drill_height(sd) - drill_floor(sd) < 0.9 * drill_height(sd)
    # M8 and M12 keep w min with a full drill point almost exactly.
    if sd.size in ("M8", "M12"):
        assert point_crown(sd) == pytest.approx(sd.w_min, abs=0.04)
    # The bearing and top chamfers leave a full-height corner.
    r_c = sd.e_nom / 2
    t30 = math.tan(math.radians(30))
    assert (r_c - sd.dw_min / 2) * t30 + (r_c - sd.r) * t30 < 0.5 * sd.m_max


def check_nut(size, thread):
    sd = SIZES[size]
    part = build(size, thread)
    assert part.is_valid
    assert len(part.solids()) == 1
    assert part.label == f"DIN 1587 - {size}"
    bb = part.bounding_box()
    tol = 1e-3 * sd.D
    # Flats parallel to X: s across Y, corners e on the X axis.
    assert bb.size.X == pytest.approx(sd.e_nom, abs=tol)
    assert bb.size.Y == pytest.approx(sd.s, abs=tol)
    assert bb.min.Z == pytest.approx(0, abs=tol)
    assert bb.max.Z == pytest.approx(sd.h, abs=tol)
    m, h, r, t = sd.m_max, sd.h, sd.r, sd.t_nom
    # Blind bore: empty on the axis up to the drill point, solid beyond it.
    for z in (0.1 * t, 0.5 * t, 0.95 * t, (t + z_tip(sd)) / 2, z_tip(sd) - 0.01):
        assert not part.is_inside(Vector(0, 0, z))
    assert part.is_inside(Vector(0, 0, z_tip(sd) + 0.01))
    assert part.is_inside(Vector(0, 0, z_tip(sd) + 0.5 * crown_thickness(sd)))
    assert part.is_inside(Vector(0, 0, h - 0.01 * h))
    assert not part.is_inside(Vector(0.95 * d1(sd) / 2, 0, m / 2))
    # Hexagon wall solid; dome a cylinder of radius r, then a sphere.
    assert part.is_inside(Vector((sd.D / 2 + sd.s / 2) / 2, 0, m / 2))
    assert part.is_inside(Vector(0.99 * sd.e_nom / 2, 0, m / 2))
    z_cyl = (m + h - r) / 2
    assert part.is_inside(Vector(0.98 * r, 0, z_cyl))
    assert not part.is_inside(Vector(1.02 * r, 0, z_cyl))
    for deg in (30, 60):
        a = math.radians(deg)
        pt = (r * math.cos(a), h - r + r * math.sin(a))
        assert part.is_inside(Vector(0.98 * pt[0], 0, h - r + 0.98 * r * math.sin(a)))
        assert not part.is_inside(Vector(1.02 * pt[0], 0, h - r + 1.02 * r * math.sin(a)))
    # Countersink on the bearing face: empty just inside da at the face.
    rc = (sd.D + sd.da_max) / 4
    depth = (sd.da_max / 2 - rc) / TAN60
    assert not part.is_inside(Vector(0, rc, 0.3 * depth))
    assert part.is_inside(Vector(0, rc, depth + 0.05 * m))
    # Hexagon chamfered at both ends: corners cut away at the faces.
    eps = 0.01 * m
    assert part.is_inside(Vector(0, 0.97 * sd.dw_min / 2, eps))
    assert not part.is_inside(Vector(0.99 * sd.e_nom / 2, 0, eps))
    assert not part.is_inside(Vector(0.99 * sd.e_nom / 2, 0, m - eps))
    return part


def body_volume(sd):
    return chamfered_hex(sd.s, 0, sd.m_max, sd.dw_min, 2 * sd.r).volume + dome_volume(sd)


@pytest.mark.parametrize("size", list(SIZES))
def test_simplified_nut(size):
    part = check_nut(size, "simplified")
    sd = SIZES[size]
    # Bore at D1 to t, drill point, 120 deg countersink from da max, and for
    # type B the undercut groove entered by a 45 deg step from D1.
    r, ra = d1(sd) / 2, sd.da_max / 2
    tc = (ra - r) / TAN60
    countersink = math.pi * tc / 3 * (ra * ra + ra * r + r * r) - math.pi * r * r * tc
    removed = math.pi * r * r * sd.t_nom + tip_volume(sd) + countersink
    if sd.end_type == "B":
        rg = sd.dg / 2
        step = rg - r
        ring = math.pi * step / 3 * (r * r + r * rg + rg * rg) - math.pi * r * r * step
        removed += ring + (math.pi * rg * rg - math.pi * r * r) * (sd.g_max - step)
        assert not part.is_inside(Vector(0, (r + rg) / 2, sd.t_nom - sd.g_max / 2))
        assert part.is_inside(Vector(0, (r + rg) / 2, sd.t_nom - sd.g_max - 0.1 * sd.P))
    assert part.volume == pytest.approx(body_volume(sd) - removed, rel=1e-6)
    # Table mass (kg per 1000) where given, steel; the plain bore at D1
    # leaves a little more material than the real thread.
    masses = {"M6": 4.66, "M8": 11, "M10": 20.1, "M16": 54.3, "M18": 95, "M20": 104,
              "M24": 216}
    if size in masses:
        assert part.volume * 7.85e-3 == pytest.approx(masses[size], rel=0.15)


def thread_phase(part, sd, r, angle):
    """Axial position of the ridge at radius r and the given angle, as a
    phase in radians of the pitch (circular mean of the solid samples)."""
    P = sd.P
    n = 48
    z0 = (sd.t_nom - sd.x_max) / 2 - P / 2
    c = s = 0.0
    hits = 0
    for i in range(n):
        z = z0 + P * (i + 0.5) / n
        a = math.radians(angle)
        if part.is_inside(Vector(r * math.cos(a), r * math.sin(a), z)):
            c += math.cos(2 * math.pi * z / P)
            s += math.sin(2 * math.pi * z / P)
            hits += 1
    return math.atan2(s, c), hits / n


@pytest.mark.parametrize("size", MODELED_SAMPLE)
def test_modeled_nut(size):
    part = check_nut(size, "modeled")
    sd = SIZES[size]
    P = sd.P
    H = SQRT3 / 2 * P
    R = sd.D / 2
    t = sd.t_nom
    x = sd.x_max if sd.end_type == "A" else sd.g_max
    z_te = t - x
    # Solid just outside D over the full thread (root of the internal thread).
    for z in (0.3 * z_te, 0.7 * z_te):
        assert part.is_inside(Vector(R + 0.2 * P, 0, z))
    # Halfway up the flank the ridge fills 9/16 of the axial length.
    r_mid = (d1(sd) + sd.D) / 4
    ph0, fill = thread_phase(part, sd, r_mid, 0)
    assert fill == pytest.approx(9 / 16, abs=0.04)
    # Right-hand thread: a quarter turn on, the ridge is P/4 higher.
    ph90, _ = thread_phase(part, sd, r_mid, 90)
    shift = (ph90 - ph0) % (2 * math.pi)
    assert shift == pytest.approx(math.pi / 2, abs=0.1)
    if sd.end_type == "A":
        # Run-out: near the bottom of the bore the groove has gone, the nut
        # is solid all round at a radius the full thread leaves empty.
        r_test = R - 0.1 * P
        for deg in range(0, 360, 15):
            a = math.radians(deg)
            assert part.is_inside(Vector(r_test * math.cos(a), r_test * math.sin(a),
                                         t - 0.3 * x))
    else:
        # Undercut: empty all round beyond D in the middle of the groove.
        r_u = (R + sd.dg / 2) / 2
        for deg in range(0, 360, 15):
            a = math.radians(deg)
            assert not part.is_inside(Vector(r_u * math.cos(a), r_u * math.sin(a), t - x / 2))
    # Volume removed relative to the plain bore at D1: the ISO 68-1 groove
    # (35/128 P H per pitch, centroid 0.381 of the way from D1 to D) over the
    # thread between the countersink and its end 0.1 P before t - x (t - g),
    # then the empty ring between D1 and D over those 0.1 P, and the part of
    # the thread end the bore at D adds: the run-out cone (type A) or the
    # ring at the undercut's 45 deg step, which starts at D instead of D1
    # (type B).
    plain = build(size)
    r_g = d1(sd) / 2 + 0.381 * 5 / 8 * H
    r1 = d1(sd) / 2
    length = z_te - 0.1 * P - (sd.da_max / 2 - r_g) / TAN60
    if sd.end_type == "A":
        area = (R - r1) * (0.1 * P + x / 2)
    else:
        step = sd.dg / 2 - R
        area = (R - r1) * (0.1 * P + step) + (R - r1) ** 2 / 2
    extra = 2 * math.pi * (R + r1) / 2 * area
    expected = 35 / 128 * P * H * 2 * math.pi * r_g * length / P + extra
    assert plain.volume - part.volume == pytest.approx(expected, rel=0.03)


def test_blind_thread_volume():
    # The ridge ends 0.1 P before the thread end, so the thread adds what a
    # through thread of that height with one countersink adds.
    th = MetricThread(10, 1.5)
    cs = Countersink(10.8)
    for end in (ThreadEnd("A", 3.0), ThreadEnd("B", 5.6, 10.75)):
        z_hi = 20.0 - end.length - 0.15
        assert blind_thread_volume(th, 20.0, end, cs) == pytest.approx(
            internal_thread_volume(th, z_hi, cs, None))


def test_step_roundtrip():
    part = build("M8", "modeled")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "nut.stp"
        export_step(part, str(path), unit=Unit.MM)
        data = path.read_bytes()
        imported = import_step(path)
    assert data.startswith(b"ISO-10303-21;")
    assert b"DIN 1587 - M8" in data
    assert imported.is_valid
    assert imported.volume == pytest.approx(part.volume, rel=1e-4)


@pytest.mark.parametrize(
    "raw",
    [
        {"size": "M3"},
        {"size": "M27"},
        {"size": "8"},
        {"size": "M8", "thread": "fancy"},
    ],
)
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        DIN.validate(raw)


def test_designation_and_files():
    p = DIN.validate({})
    assert p == {"size": "M8", "thread": "simplified"}
    assert DIN.designation(p) == "DIN 1587 - M8"
    assert DIN.file_stem(p) == "DIN1587_M8"
    q = DIN.validate({"size": "M24", "thread": "modeled"})
    assert DIN.file_stem(q) == "DIN1587_M24_threaded"
    kinds = {par.kind for par in DIN.parameters()}
    assert kinds <= {"select", "length"}
    assert {o.value for o in DIN.parameters()[0].options} == set(SIZES)


def test_notes_and_dimensions():
    notes = " ".join(DIN.notes(DIN.validate({"size": "M8"})))
    assert "One-piece" in notes and "D1" in notes
    notes = " ".join(DIN.notes(DIN.validate({"size": "M8", "thread": "modeled"})))
    assert "ISO 68-1" in notes and "run-out" in notes and "Type A" in notes
    notes = " ".join(DIN.notes(DIN.validate({"size": "M20"})))
    assert "Type B" in notes and "undercut" in notes
    # M4's drill point is cut flat to keep w min, and the notes say so;
    # M8's is not.
    assert "w min" in " ".join(DIN.notes(DIN.validate({"size": "M4"})))
    assert "w min" not in " ".join(DIN.notes(DIN.validate({"size": "M8"})))
    dims = {d.symbol: d.value for d in DIN.dimensions(DIN.validate({"size": "M8"}))}
    assert dims["s"] == 13 and dims["m max"] == 6.5 and dims["h"] == 15
    assert dims["dk max"] == 12.5 and dims["t"] == 11.05 and dims["x max"] == 2.5
    assert dims["type"] == "A, run-out" and "g max" not in dims
    assert dims["e"] == pytest.approx(15.011, abs=1e-3)
    assert dims["D1"] == pytest.approx(6.647, abs=1e-3)
    dims = {d.symbol: d.value for d in DIN.dimensions(DIN.validate({"size": "M20"}))}
    assert dims["type"] == "B, undercut" and dims["g max"] == 9.3
    assert dims["dg"] == 21.25 and "x max" not in dims

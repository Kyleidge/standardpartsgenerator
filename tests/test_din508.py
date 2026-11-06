import math
import tempfile
from pathlib import Path

import pytest
from build123d import Unit, Vector, export_step, import_step

from standardparts.nuts import Countersink, bore_volume
from standardparts.standards import ParameterError
from standardparts.standards.din508 import DIN508, body_volume
from standardparts.standards.din508_data import COUNTERSINK_ANGLE, SIZES

DIN = DIN508()
SQRT3 = math.sqrt(3)
TAN60 = math.tan(math.radians(COUNTERSINK_ANGLE / 2))

# ISO 261 coarse pitches.
COARSE = {4: 0.7, 5: 0.8, 6: 1, 8: 1.25, 10: 1.5, 12: 1.75, 16: 2, 20: 2.5, 24: 3,
          30: 3.5, 36: 4, 42: 4.5, 48: 5}
# DIN 508:2002 slot width -> thread.
PAIRS = {"5": "M4", "6": "M5", "8": "M6", "10": "M8", "12": "M10", "14": "M12",
         "18": "M16", "22": "M20", "28": "M24", "36": "M30", "42": "M36",
         "48": "M42", "54": "M48"}

# Modeled sizes sampled in the test suite: the smallest (thinnest tenon
# wall), M16 (0.85 mm wall), a large one and the largest. The full sweep of
# every size in both modes was run separately.
MODELED_SAMPLE = ["5", "18", "36", "54"]


def d1(sd):
    return sd.D - 1.25 * SQRT3 / 2 * sd.P


def build(size, thread="simplified"):
    return DIN.build(DIN.validate({"size": size, "thread": thread}))


def test_table_pairs():
    assert {k: sd.d for k, sd in SIZES.items()} == PAIRS


@pytest.mark.parametrize("sd", SIZES.values(), ids=list(SIZES))
def test_size_rows_are_consistent(sd):
    assert sd.P == COARSE[sd.D]
    assert sd.a_nom == float(sd.slot)
    # a -0.3 / -0.5 up to 28, wider limits above.
    assert sd.a_max == pytest.approx(sd.a_nom - (0.3 if sd.a_nom <= 28 else 0.4))
    assert sd.a_min < sd.a_max
    assert sd.e_min < sd.e_max and sd.k_min < sd.k_max < sd.h
    assert sd.D < sd.a_min < sd.e_min
    assert 0 < sd.f < sd.k_min
    # The model countersink fits between the thread and the tenon walls.
    assert sd.D / 2 + 0.05 * sd.P < sd.da / 2 < sd.a_max / 2
    # The table mass is within 10% of the modeled nut (bore at D1, steel),
    # except two table values that also disagree with Halder's weights
    # (10 x M8: 12 to 14 g, 36 x M30: 585 g), which match the model.
    r = d1(sd) / 2
    mass = (body_volume(sd) - math.pi * r * r * sd.h) * 7.85e-3
    if sd.slot in ("10", "36"):
        assert mass < 0.85 * sd.mass
    else:
        assert mass == pytest.approx(sd.mass, rel=0.1)


def check_nut(size, thread):
    sd = SIZES[size]
    part = build(size, thread)
    assert part.is_valid
    assert len(part.solids()) == 1
    assert part.label == f"DIN 508 - {sd.d} x {size}"
    bb = part.bounding_box()
    tol = 1e-3 * sd.D
    e, a, k, h, f = sd.e_max, sd.a_max, sd.k_max, sd.h, sd.f
    assert bb.size.X == pytest.approx(e, abs=tol)
    assert bb.size.Y == pytest.approx(e, abs=tol)
    assert bb.min.Z == pytest.approx(0, abs=tol)
    assert bb.max.Z == pytest.approx(h, abs=tol)
    # Bore empty below the minor diameter, in the base and in the tenon.
    for z in (k / 2, (k + h) / 2):
        assert not part.is_inside(Vector(0, 0, z))
        assert not part.is_inside(Vector(0, 0.95 * d1(sd) / 2, z))
    # Tenon: solid between the thread and its side walls (across Y), and
    # solid all along X; empty beside it above the shoulders.
    zt = (k + h) / 2
    assert part.is_inside(Vector(0, (sd.D / 2 + a / 2) / 2, zt))
    assert part.is_inside(Vector(0.45 * e, 0, zt))
    assert not part.is_inside(Vector(0, (a / 2 + e / 2) / 2, zt))
    # Base: solid out to the edge, chamfered on the two edges along X only.
    assert part.is_inside(Vector(0, (a / 2 + e / 2) / 2, k / 2))
    assert not part.is_inside(Vector(0, e / 2 - 0.3 * f, 0.3 * f))
    assert part.is_inside(Vector(0, e / 2 - 0.3 * f, 0.9 * f))
    assert part.is_inside(Vector(e / 2 - 0.3 * f, 0, 0.3 * f))
    # Countersinks on both faces: empty just inside da at the face.
    r = (sd.D + sd.da) / 4
    depth = (sd.da / 2 - r) / TAN60
    for z in (0.3 * depth, h - 0.3 * depth):
        assert not part.is_inside(Vector(r, 0, z))
    for z in (depth + 0.05 * h, h - depth - 0.05 * h):
        assert part.is_inside(Vector(r, 0, z))
    return part


@pytest.mark.parametrize("size", list(SIZES))
def test_simplified_nut(size):
    part = check_nut(size, "simplified")
    sd = SIZES[size]
    cs = Countersink(sd.da, COUNTERSINK_ANGLE)
    expected = body_volume(sd) - bore_volume(d1(sd) / 2, sd.h, cs, cs)
    assert part.volume == pytest.approx(expected, rel=1e-6)


def test_body_volume_formula():
    sd = SIZES["14"]
    # 22 x 22 x 8 base minus two 2.5 x 2.5 / 2 chamfers, 13.7 x 22 x 8 tenon.
    assert body_volume(sd) == pytest.approx(22 * 22 * 8 - 2.5**2 * 22 + 13.7 * 22 * 8)


def thread_phase(part, sd, r, angle):
    """Axial position of the ridge at radius r and the given angle, as a
    phase in radians of the pitch (circular mean of the solid samples)."""
    P = sd.P
    n = 48
    z0 = sd.h / 2 - P / 2
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
    h = sd.h
    # Solid just outside D everywhere (root of the internal thread), also in
    # the narrow tenon.
    for z in (sd.k_max / 2, (sd.k_max + h) / 2):
        assert part.is_inside(Vector(0, sd.D / 2 + 0.2 * P, z))
    # Halfway up the flank the ridge fills 9/16 of the axial length.
    r_mid = (d1(sd) + sd.D) / 4
    ph0, fill = thread_phase(part, sd, r_mid, 0)
    assert fill == pytest.approx(9 / 16, abs=0.04)
    # Right-hand thread: a quarter turn on, the ridge is P/4 higher.
    ph90, _ = thread_phase(part, sd, r_mid, 90)
    shift = (ph90 - ph0) % (2 * math.pi)
    assert shift == pytest.approx(math.pi / 2, abs=0.1)
    # Volume removed relative to the plain bore at D1: the ISO 68-1 groove
    # (35/128 P H per pitch, centroid 0.381 of the way from D1 to D) over the
    # length between the countersinks at that radius.
    plain = build(size)
    r_g = d1(sd) / 2 + 0.381 * 5 / 8 * H
    length = h - 2 * (sd.da / 2 - r_g) / TAN60
    expected = 35 / 128 * P * H * 2 * math.pi * r_g * length / P
    assert plain.volume - part.volume == pytest.approx(expected, rel=0.03)


def test_step_roundtrip():
    part = build("14", "modeled")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "nut.stp"
        export_step(part, str(path), unit=Unit.MM)
        data = path.read_bytes()
        imported = import_step(path)
    assert data.startswith(b"ISO-10303-21;")
    assert b"DIN 508 - M12 x 14" in data
    assert imported.is_valid
    assert imported.volume == pytest.approx(part.volume, rel=1e-4)


@pytest.mark.parametrize(
    "raw",
    [
        {"size": "16"},
        {"size": "M12"},
        {"size": "14.0"},
        {"size": "14", "thread": "fancy"},
    ],
)
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        DIN.validate(raw)


def test_designation_and_files():
    p = DIN.validate({})
    assert p == {"size": "14", "thread": "simplified"}
    assert DIN.designation(p) == "DIN 508 - M12 x 14"
    assert DIN.file_stem(p) == "DIN508_M12x14"
    q = DIN.validate({"size": "5", "thread": "modeled"})
    assert DIN.designation(q) == "DIN 508 - M4 x 5"
    assert DIN.file_stem(q) == "DIN508_M4x5_threaded"
    kinds = {par.kind for par in DIN.parameters()}
    assert kinds <= {"select", "length"}
    assert {o.value for o in DIN.parameters()[0].options} == set(SIZES)


def test_notes_and_dimensions():
    notes = " ".join(DIN.notes(DIN.validate({"size": "14"})))
    assert "D1" in notes and "countersink" in notes
    notes = " ".join(DIN.notes(DIN.validate({"size": "14", "thread": "modeled"})))
    assert "ISO 68-1" in notes
    dims = {d.symbol: d.value for d in DIN.dimensions(DIN.validate({"size": "14"}))}
    assert dims["d"] == "M12" and dims["a nom"] == 14 and dims["a max"] == 13.7
    assert dims["e max"] == 22 and dims["h"] == 16 and dims["k max"] == 8
    assert dims["f"] == 2.5 and dims["mass"] == 35
    assert dims["D1"] == pytest.approx(10.106, abs=1e-3)

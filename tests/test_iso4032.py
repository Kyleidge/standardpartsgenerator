import math
import tempfile
from pathlib import Path

import pytest
from build123d import Unit, Vector, export_step, import_step

from standardparts.geometry import chamfered_hex
from standardparts.standards import ParameterError
from standardparts.standards.iso4032 import ISO4032
from standardparts.standards.iso4032_data import COUNTERSINK_ANGLE, SIZES

ISO = ISO4032()
SQRT3 = math.sqrt(3)
TAN60 = math.tan(math.radians(COUNTERSINK_ANGLE / 2))

# ISO 261 coarse pitches.
COARSE = {1.6: 0.35, 2: 0.4, 2.5: 0.45, 3: 0.5, 3.5: 0.6, 4: 0.7, 5: 0.8, 6: 1, 7: 1,
          8: 1.25, 10: 1.5, 12: 1.75, 14: 2, 16: 2, 18: 2.5, 20: 2.5, 22: 2.5, 24: 3,
          27: 3, 30: 3.5, 33: 3.5, 36: 4, 39: 4, 42: 4.5, 45: 4.5, 48: 5, 52: 5,
          56: 5.5, 60: 5.5, 64: 6}
NON_PREFERRED = {"M3.5", "M7", "M14", "M18", "M22", "M27", "M33", "M39", "M45", "M52", "M60"}

# Modeled sizes sampled in the test suite: smallest, two that need a retry
# at another start angle, a mid size and the largest (multi-segment ridge).
# The full sweep of every size in both modes was run separately.
MODELED_SAMPLE = ["M1.6", "M4", "M10", "M24", "M64"]


def d1(sd):
    return sd.D - 1.25 * SQRT3 / 2 * sd.P


def build(size, thread="simplified"):
    return ISO.build(ISO.validate({"size": size, "thread": thread}))


@pytest.mark.parametrize("sd", SIZES.values(), ids=list(SIZES))
def test_size_rows_are_consistent(sd):
    assert sd.P == COARSE[sd.D]
    assert sd.preferred == (sd.size not in NON_PREFERRED)
    assert sd.s_min < sd.s_max
    assert sd.m_min < sd.m_max
    assert sd.mw_min < sd.m_min
    assert sd.D < sd.da_max <= 1.16 * sd.D
    assert sd.da_max < sd.dw_min < sd.s_min
    # e min = 1.13 s min (ISO 4759-1), below the exact corners of s nom.
    assert sd.e_min == pytest.approx(1.13 * sd.s_min, abs=0.006)
    assert sd.e_min < sd.e_nom
    # The 30 deg corner chamfers on both faces leave a full-height corner.
    assert 2 * (sd.e_nom - sd.dw_min) / 2 * math.tan(math.radians(30)) < sd.m_max
    assert sd.edition == ("2023" if 5 <= sd.D <= 39 else "1999")


def check_nut(size, thread):
    sd = SIZES[size]
    part = build(size, thread)
    assert part.is_valid
    assert len(part.solids()) == 1
    assert part.label == f"ISO 4032 - {size}"
    bb = part.bounding_box()
    tol = 1e-3 * sd.D
    # Flats parallel to X: s across Y, corners e on the X axis.
    assert bb.size.X == pytest.approx(sd.e_nom, abs=tol)
    assert bb.size.Y == pytest.approx(sd.s_nom, abs=tol)
    assert bb.min.Z == pytest.approx(0, abs=tol)
    assert bb.max.Z == pytest.approx(sd.m_max, abs=tol)
    m = sd.m_max
    # Bore is empty below the minor diameter, the hex wall is solid.
    assert not part.is_inside(Vector(0, 0, m / 2))
    assert not part.is_inside(Vector(0.95 * d1(sd) / 2, 0, m / 2))
    assert part.is_inside(Vector((sd.D / 2 + sd.s_nom / 2) / 2, 0, m / 2))
    # Countersinks on both faces: empty just inside da at the face.
    r = (sd.D + sd.da_max) / 4
    depth = (sd.da_max / 2 - r) / TAN60
    for z in (0.3 * depth, m - 0.3 * depth):
        assert not part.is_inside(Vector(0, r, z))
    for z in (depth + 0.05 * m, m - depth - 0.05 * m):
        assert part.is_inside(Vector(0, r, z))
    # Bearing faces: flat out to dw, corners chamfered away at the faces.
    eps = 0.01 * m
    for z in (eps, m - eps):
        assert part.is_inside(Vector(0, 0.97 * sd.dw_min / 2, z))
        assert not part.is_inside(Vector(0.99 * sd.e_nom / 2, 0, z))
    assert part.is_inside(Vector(0.99 * sd.e_nom / 2, 0, m / 2))
    return part


@pytest.mark.parametrize("size", list(SIZES))
def test_simplified_nut(size):
    part = check_nut(size, "simplified")
    sd = SIZES[size]
    m = sd.m_max
    body = chamfered_hex(sd.s_nom, 0, m, sd.dw_min, sd.dw_min)
    # Bore at D1 plus two 120 deg countersink frustums from da max down to D1.
    r, ra = d1(sd) / 2, sd.da_max / 2
    t = (ra - r) / TAN60
    countersink = math.pi * t / 3 * (ra * ra + ra * r + r * r) - math.pi * r * r * t
    removed = math.pi * r * r * m + 2 * countersink
    assert part.volume == pytest.approx(body.volume - removed, rel=1e-6)


def thread_phase(part, sd, r, angle):
    """Axial position of the ridge at radius r and the given angle, as a
    phase in radians of the pitch (circular mean of the solid samples)."""
    P = sd.P
    n = 48
    z0 = sd.m_max / 2 - P / 2
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
    m = sd.m_max
    # Solid just outside D everywhere (root of the internal thread).
    assert part.is_inside(Vector(sd.D / 2 + 0.2 * P, 0, m / 2))
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
    h = 5 / 8 * H
    r_g = d1(sd) / 2 + 0.381 * h
    length = m - 2 * (sd.da_max / 2 - r_g) / TAN60
    expected = 35 / 128 * P * H * 2 * math.pi * r_g * length / P
    assert plain.volume - part.volume == pytest.approx(expected, rel=0.03)


def test_step_roundtrip():
    part = build("M8", "modeled")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "nut.stp"
        export_step(part, str(path), unit=Unit.MM)
        data = path.read_bytes()
        imported = import_step(path)
    assert data.startswith(b"ISO-10303-21;")
    assert b"ISO 4032 - M8" in data
    assert imported.is_valid
    assert imported.volume == pytest.approx(part.volume, rel=1e-4)


@pytest.mark.parametrize(
    "raw",
    [
        {"size": "M9"},
        {"size": "8"},
        {"size": "M8", "thread": "fancy"},
    ],
)
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        ISO.validate(raw)


def test_designation_and_files():
    p = ISO.validate({"size": "M8"})
    assert p == {"size": "M8", "thread": "simplified"}
    assert ISO.designation(p) == "ISO 4032 - M8"
    assert ISO.file_stem(p) == "ISO4032_M8"
    q = ISO.validate({"size": "M1.6", "thread": "modeled"})
    assert ISO.file_stem(q) == "ISO4032_M1.6_threaded"
    kinds = {par.kind for par in ISO.parameters()}
    assert kinds <= {"select", "length"}
    assert {o.value for o in ISO.parameters()[0].options} == set(SIZES)


def test_notes_and_dimensions():
    notes = " ".join(ISO.notes(ISO.validate({"size": "M3.5"})))
    assert "non-preferred" in notes and "Annex A" in notes
    notes = " ".join(ISO.notes(ISO.validate({"size": "M8", "thread": "modeled"})))
    assert "Annex A" not in notes and "non-preferred" not in notes
    assert "ISO 68-1" in notes
    dims = {d.symbol: d.value for d in ISO.dimensions(ISO.validate({"size": "M8"}))}
    assert dims["s"] == 13 and dims["m max"] == 6.8 and dims["dw min"] == 11.63
    assert dims["e"] == pytest.approx(15.011, abs=1e-3)
    assert dims["D1"] == pytest.approx(6.647, abs=1e-3)

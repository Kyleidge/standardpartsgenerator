import math
import tempfile
from pathlib import Path

import pytest
from build123d import Unit, Vector, export_step, import_step

from standardparts.geometry import chamfered_hex
from standardparts.standards import ParameterError
from standardparts.standards.iso4032_data import SIZES as ISO4032_SIZES
from standardparts.standards.iso8673 import ISO8673
from standardparts.standards.iso8673_data import COUNTERSINK_ANGLE, SIZES, product_grade

ISO = ISO8673()
SQRT3 = math.sqrt(3)
TAN60 = math.tan(math.radians(COUNTERSINK_ANGLE / 2))

# Every size/pitch of ISO 8673:2023 Tables 1 and 2 plus the 2012 sizes
# above M39 (Annex A of the 2023 edition).
KEYS = ["M8x1", "M10x1.25", "M10x1", "M12x1.5", "M12x1.25", "M14x1.5", "M16x1.5",
        "M18x2", "M18x1.5", "M20x2", "M20x1.5", "M22x2", "M22x1.5", "M24x2",
        "M27x2", "M30x2", "M33x2", "M36x3", "M39x3", "M42x3", "M45x3", "M48x3",
        "M52x4", "M56x4", "M60x4", "M64x4"]
PREFERRED = {"M8x1", "M10x1.25", "M12x1.5", "M16x1.5", "M20x2", "M24x2", "M30x2",
             "M36x3", "M42x3", "M48x3", "M56x4", "M64x4"}

# Modeled sizes sampled in the test suite: smallest, both pitches of a
# two-pitch diameter, a 2012 size and the largest. The sweep script builds
# every size in both modes.
MODELED_SAMPLE = ["M8x1", "M12x1.5", "M12x1.25", "M42x3", "M64x4"]


def d1(sd):
    return sd.D - 1.25 * SQRT3 / 2 * sd.P


def build(size, thread="simplified"):
    return ISO.build(ISO.validate({"size": size, "thread": thread}))


def test_size_list():
    assert list(SIZES) == KEYS
    for key, sd in SIZES.items():
        assert key == f"M{sd.D:g}x{sd.P:g}" == sd.size
        assert sd.fine
        assert sd.preferred == (key in PREFERRED)
        assert sd.edition == ("2023" if sd.D <= 39 else "2012")
        assert sd.in_annex == (sd.D > 39)


@pytest.mark.parametrize("sd", SIZES.values(), ids=list(SIZES))
def test_size_rows_are_consistent(sd):
    coarse = ISO4032_SIZES[f"M{sd.D:g}"]
    assert sd.P < coarse.P
    assert sd.s_min < sd.s_max
    assert sd.m_min < sd.m_max
    assert sd.mw_min == pytest.approx(0.8 * sd.m_min, abs=0.006)
    assert sd.D < sd.da_max <= 1.16 * sd.D
    assert sd.da_max < sd.dw_min < sd.s_min
    assert sd.e_min == pytest.approx(1.13 * sd.s_min, abs=0.006)
    assert sd.e_min < sd.e_nom
    assert 2 * (sd.e_nom - sd.dw_min) / 2 * math.tan(math.radians(30)) < sd.m_max
    # Same nut as ISO 4032 for the diameter: identical to the 2023 coarse
    # rows; the 2012 rows above M39 add decimals to the ISO 4032:1999 ones.
    fields = ("da_max", "dw_min", "e_min", "m_max", "m_min", "mw_min", "s_max", "s_min")
    for f in fields:
        if sd.edition == "2023":
            assert getattr(sd, f) == getattr(coarse, f), f
        else:
            assert getattr(sd, f) == pytest.approx(getattr(coarse, f), abs=0.06), f


def test_2012_values_for_annex_sizes():
    # ISO 8673:2012 Tables 1 and 2.
    m42, m64 = SIZES["M42x3"], SIZES["M64x4"]
    assert (m42.da_max, m42.dw_min, m42.m_max, m42.mw_min) == (45.4, 59.95, 34.0, 25.92)
    assert (m64.da_max, m64.dw_min, m64.m_min, m64.mw_min) == (69.1, 88.16, 49.1, 39.28)


def test_product_grade():
    assert product_grade(16) == "A" and product_grade(18) == "B"


def check_nut(size, thread):
    sd = SIZES[size]
    part = build(size, thread)
    assert part.is_valid
    assert len(part.solids()) == 1
    assert part.label == f"ISO 8673 - {sd.name}"
    bb = part.bounding_box()
    tol = 1e-3 * sd.D
    assert bb.size.X == pytest.approx(sd.e_nom, abs=tol)
    assert bb.size.Y == pytest.approx(sd.s_nom, abs=tol)
    assert bb.min.Z == pytest.approx(0, abs=tol)
    assert bb.max.Z == pytest.approx(sd.m_max, abs=tol)
    m = sd.m_max
    assert not part.is_inside(Vector(0, 0, m / 2))
    assert not part.is_inside(Vector(0.95 * d1(sd) / 2, 0, m / 2))
    assert part.is_inside(Vector((sd.D / 2 + sd.s_nom / 2) / 2, 0, m / 2))
    r = (sd.D + sd.da_max) / 4
    depth = (sd.da_max / 2 - r) / TAN60
    for z in (0.3 * depth, m - 0.3 * depth):
        assert not part.is_inside(Vector(0, r, z))
    for z in (depth + 0.05 * m, m - depth - 0.05 * m):
        assert part.is_inside(Vector(0, r, z))
    eps = 0.01 * m
    for z in (eps, m - eps):
        assert part.is_inside(Vector(0, 0.97 * sd.dw_min / 2, z))
        assert not part.is_inside(Vector(0.99 * sd.e_nom / 2, 0, z))
    assert part.is_inside(Vector(0.99 * sd.e_nom / 2, 0, m / 2))
    return part


@pytest.mark.parametrize("size", KEYS)
def test_simplified_nut(size):
    part = check_nut(size, "simplified")
    sd = SIZES[size]
    m = sd.m_max
    body = chamfered_hex(sd.s_nom, 0, m, sd.dw_min, sd.dw_min)
    r, ra = d1(sd) / 2, sd.da_max / 2
    t = (ra - r) / TAN60
    countersink = math.pi * t / 3 * (ra * ra + ra * r + r * r) - math.pi * r * r * t
    removed = math.pi * r * r * m + 2 * countersink
    assert part.volume == pytest.approx(body.volume - removed, rel=1e-6)


def thread_phase(part, sd, r, angle):
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
    assert part.is_inside(Vector(sd.D / 2 + 0.2 * P, 0, m / 2))
    # Halfway up the flank the ridge fills 9/16 of every fine pitch, and a
    # quarter turn on it is P/4 higher (right hand). Both are measured over
    # one fine pitch, so a coarse ridge would fail them.
    r_mid = (d1(sd) + sd.D) / 4
    ph0, fill = thread_phase(part, sd, r_mid, 0)
    assert fill == pytest.approx(9 / 16, abs=0.04)
    ph90, _ = thread_phase(part, sd, r_mid, 90)
    shift = (ph90 - ph0) % (2 * math.pi)
    assert shift == pytest.approx(math.pi / 2, abs=0.1)
    plain = build(size)
    h = 5 / 8 * H
    r_g = d1(sd) / 2 + 0.381 * h
    length = m - 2 * (sd.da_max / 2 - r_g) / TAN60
    expected = 35 / 128 * P * H * 2 * math.pi * r_g * length / P
    assert plain.volume - part.volume == pytest.approx(expected, rel=0.03)


def test_step_roundtrip():
    part = build("M10x1.25", "modeled")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "nut.stp"
        export_step(part, str(path), unit=Unit.MM)
        data = path.read_bytes()
        imported = import_step(path)
    assert data.startswith(b"ISO-10303-21;")
    assert b"ISO 8673 - M10 x 1.25" in data
    assert imported.is_valid
    assert imported.volume == pytest.approx(part.volume, rel=1e-4)


@pytest.mark.parametrize(
    "raw",
    [
        {"size": "M8"},           # coarse key
        {"size": "M8x1.25"},      # coarse pitch
        {"size": "M10x1.5"},
        {"size": "M6x0.75"},
        {"size": "M8x1", "thread": "fancy"},
    ],
)
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        ISO.validate(raw)


def test_designation_and_files():
    assert (ISO.id, ISO.title, ISO.category) == ("iso8673", "ISO 8673", "Nuts")
    p = ISO.validate({})
    assert p == {"size": "M8x1", "thread": "simplified"}
    assert ISO.designation(p) == "ISO 8673 - M8 x 1"
    assert ISO.file_stem(p) == "ISO8673_M8x1"
    q = ISO.validate({"size": "M12x1.25", "thread": "modeled"})
    assert ISO.designation(q) == "ISO 8673 - M12 x 1.25"
    assert ISO.file_stem(q) == "ISO8673_M12x1.25_threaded"
    params = ISO.parameters()
    assert {par.kind for par in params} <= {"select", "length"}
    options = {o.value: o.label for o in params[0].options}
    assert list(options) == KEYS
    assert options["M12x1.5"] == "M12 x 1.5"
    assert options["M12x1.25"] == "M12 x 1.25 (non-preferred)"
    ISO.describe_json()


def test_notes_and_dimensions():
    notes = " ".join(ISO.notes(ISO.validate({"size": "M45x3"})))
    assert "M45 x 3 is a non-preferred size" in notes
    assert "ISO 8673:2023" in notes and "Annex A" in notes and "ISO 8673:2012" in notes
    notes = " ".join(ISO.notes(ISO.validate({"size": "M8x1", "thread": "modeled"})))
    assert "Annex A" not in notes and "non-preferred" not in notes
    assert "ISO 68-1" in notes and "ISO 8674" in notes
    dims = {d.symbol: d.value for d in ISO.dimensions(ISO.validate({"size": "M8x1"}))}
    assert dims["P"] == 1.0 and dims["grade"] == "A"
    assert dims["s"] == 13 and dims["m max"] == 6.8 and dims["dw min"] == 11.63
    assert dims["D1"] == pytest.approx(8 - 1.082532, abs=1e-3)
    dims = {d.symbol: d.value for d in ISO.dimensions(ISO.validate({"size": "M20x1.5"}))}
    assert dims["grade"] == "B" and dims["m max"] == 18

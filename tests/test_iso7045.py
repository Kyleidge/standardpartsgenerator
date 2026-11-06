import math
import tempfile
from pathlib import Path

import pytest
from build123d import GeomType, Vector, export_step, import_step

from standardparts.drives import cross_geometry, min_wall
from standardparts.geometry import MetricThread
from standardparts.standards.base import ParameterError
from standardparts.standards.iso7045 import (
    ISO7045,
    build_body,
    dome_height,
    head_outline,
    recess_reference_z,
    recess_tool,
)
from standardparts.standards.iso7045_data import LENGTH_SERIES, SIZES

ISO = ISO7045()
DENSITY = 7.85e-3  # g / mm^3, as in ISO 7045 Table 1

# ISO 7045:2011 Table 1: commercial length range and approximate mass in
# kg per 1000 pieces at the shortest and longest length.
TABLE_1 = {
    "M1.6": (3, 0.099, 16, 0.245), "M2": (3, 0.178, 20, 0.492),
    "M2.5": (3, 0.336, 25, 0.996), "M3": (4, 0.544, 30, 1.69),
    "M3.5": (5, 0.891, 35, 2.68), "M4": (5, 1.3, 40, 4.01),
    "M5": (6, 2.32, 45, 7.14), "M6": (8, 4.37, 60, 13.5),
    "M8": (10, 9.96, 60, 26), "M10": (12, 19.8, 60, 43.9),
}


# --- data -----------------------------------------------------------------------

def test_length_ranges_and_threading():
    assert list(SIZES) == list(TABLE_1)
    for size, (lo, _, hi, _) in TABLE_1.items():
        sd = SIZES[size]
        assert (sd.l_min, sd.l_max) == (lo, hi)
        assert lo in LENGTH_SERIES and hi in LENGTH_SERIES
        # Dashed line of Table 1: threaded to the head up to 25 / 40 mm.
        assert sd.l_full_max == (25 if sd.d <= 3 else 40)
        assert sd.b_min == (25 if sd.d <= 3 else 38)
    partial = {s: [l for l in sd.standard_lengths() if not sd.is_fully_threaded(l)]
               for s, sd in SIZES.items()}
    assert partial["M3"] == [30] and partial["M5"] == [45] and partial["M4"] == []
    assert partial["M10"] == [45, 50, 55, 60]


@pytest.mark.parametrize("sd", SIZES.values(), ids=list(SIZES))
def test_size_rows_are_consistent(sd):
    assert sd.dk_min < sd.dk_max and sd.k_min < sd.k_max
    assert sd.d < sd.da_max < sd.dk_min
    assert sd.d + 2 * sd.r_min <= sd.da_max
    assert sd.a_max == pytest.approx(2 * sd.P)
    assert sd.pH_min < sd.pH_max and sd.pZ_min < sd.pZ_max
    o = head_outline(sd)
    assert 0 < o["z_side"] < sd.k_max / 2
    for kind in "HZ":
        m, _, p_max = sd.recess(kind)
        # The recess opens on the dome, inside the rounded edge.
        assert m / 2 < o["tangent"][0]
        assert m < sd.dk_min


# --- geometry ---------------------------------------------------------------------

def check_solid(size, l, thread, drive):
    sd = SIZES[size]
    part = ISO.build(ISO.validate({"size": size, "length": l, "thread": thread, "drive": drive}))
    assert part.label == f"ISO 7045 - {size} x {l:g} - {drive}"
    assert part.is_valid
    assert len(part.solids()) == 1
    bb = part.bounding_box()
    tol = 1e-3 * sd.d
    assert bb.min.Z == pytest.approx(-l, abs=tol)
    assert bb.size.X == pytest.approx(sd.dk_max, abs=tol)
    assert bb.size.Y == pytest.approx(sd.dk_max, abs=tol)
    m, p_min, _ = sd.recess(drive)
    z_ref = recess_reference_z(sd, drive)
    # The crown is cut away by the recess; the head reaches the dome height
    # just outside m.
    assert dome_height(sd, m / 2 + 0.05 * m) - tol <= bb.max.Z <= sd.k_max
    # Recess empty (centre and wings along X / Y), head solid around it.
    assert not part.is_inside(Vector(0, 0, z_ref - p_min / 2))
    assert not part.is_inside(Vector(0.3 * m, 0, z_ref - 0.2 * p_min))
    assert not part.is_inside(Vector(0, -0.3 * m, z_ref - 0.2 * p_min))
    r_head = (m / 2 + sd.dk_max / 2) / 2
    assert part.is_inside(Vector(r_head, 0, sd.k_max / 3))
    assert part.is_inside(Vector(r_head, 0, dome_height(sd, r_head) - 0.02))
    assert not part.is_inside(Vector(r_head, 0, dome_height(sd, r_head) + 0.02))
    assert part.is_inside(Vector(sd.dk_max / 2 - 0.02, 0, 0.02))
    assert not part.is_inside(Vector(sd.dk_max / 2 - 0.02, 0, -0.02))
    assert part.is_inside(Vector(0, 0, -l / 2))
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
        # Head-dominated: close to the table mass (shank modeled at d).
        assert part.volume * DENSITY == pytest.approx(m_lo, rel=0.08)
    # The recess cut removed the tool's volume inside the plain body.
    body = build_body(sd, l, "simplified")
    tool = recess_tool(sd, drive)
    assert body.volume - part.volume == pytest.approx((tool & body).volume, rel=1e-3)
    cg = cross_geometry(sd.recess(drive)[0], sum(sd.recess(drive)[1:]) / 2)
    assert body.volume - part.volume > 0.3 * math.pi / 3 * (sd.recess(drive)[0] / 2) ** 2 * cg.depth


# M2 x 8: small recess on a threaded body, needs precise volume integration
# in the recess cut check.
MODELED = [("M1.6", 16, "H"), ("M2", 8, "H"), ("M3", 30, "Z"), ("M5", 45, "H"), ("M10", 60, "Z")]


@pytest.mark.parametrize("size,l,drive", MODELED)
def test_modeled_thread_solid(size, l, drive):
    part = check_solid(size, l, "modeled", drive)
    sd = SIZES[size]
    _, _, hi, m_hi = TABLE_1[size]
    if l == hi:
        # Table masses include the thread; partially threaded screws are a
        # little heavier here because the plain shank is modeled at d.
        rel = 0.04 if sd.is_fully_threaded(l) else 0.06
        assert part.volume * DENSITY == pytest.approx(m_hi, rel=rel)
    plain = ISO.build(ISO.validate({"size": size, "length": l, "drive": drive}))
    t = MetricThread(sd.d, sd.P)
    threaded = l if sd.is_fully_threaded(l) else sd.b_min
    r_mean = sd.d / 2 - 0.2706 * sd.P
    expected = 0.3045 * sd.P**2 * 2 * math.pi * r_mean * threaded / sd.P
    assert plain.volume - part.volume == pytest.approx(expected, rel=0.15)
    assert t.d1 < sd.d


@pytest.mark.parametrize("size", list(SIZES))
def test_recess_leaves_a_wall(size):
    """The recess opens only into the dome. Its smallest distance to every
    other face of the head and shank, less the thread depth, must stay
    above 8 % of d (no wall is specified by ISO 7045; our criterion)."""
    sd = SIZES[size]
    body = build_body(sd, sd.l_min, "simplified")
    dr = (sd.d - MetricThread(sd.d, sd.P).d1) / 2
    for drive in "HZ":
        wall = min_wall(recess_tool(sd, drive), body, lambda f: f.geom_type == GeomType.SPHERE)
        assert wall - dr >= 0.08 * sd.d, (drive, wall)


def test_step_roundtrip():
    part = ISO.build(ISO.validate({"size": "M4", "length": 10, "thread": "modeled", "drive": "Z"}))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "part.stp"
        assert export_step(part, path)
        imported = import_step(path)
    assert imported.is_valid
    assert imported.volume == pytest.approx(part.volume, rel=1e-4)


# --- parameters -------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw",
    [
        {"size": "M7", "length": 10},
        {"size": "M4", "length": 4},
        {"size": "M4", "length": 41},
        {"size": "M4", "length": "abc"},
        {"size": "M4", "length": "inf"},
        {"size": "M4", "length": 10, "thread": "fancy"},
        {"size": "M4", "length": 10, "drive": "T"},
    ],
)
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        ISO.validate(raw)


def test_parameters_and_names():
    params = {p.name: p for p in ISO.parameters()}
    assert [p.kind for p in params.values()] == ["select", "length", "select", "select"]
    assert [o.value for o in params["drive"].options] == ["H", "Z"]
    assert params["length"].preferred["M4"] == [5, 6, 8, 10, 12, 14, 16, 20, 25, 30, 35, 40]
    assert params["length"].limits["M10"] == [12, 60]
    assert params["size"].options[4].label == "(M3.5) x 0.6"
    p = ISO.validate({"size": "M4", "length": "10"})
    assert p == {"size": "M4", "length": 10, "thread": "simplified", "drive": "H"}
    assert ISO.designation(p) == "ISO 7045 - M4 x 10 - H"
    assert ISO.file_stem(p) == "ISO7045_M4x10_H"
    assert ISO.file_stem({**p, "thread": "modeled", "drive": "Z"}) == "ISO7045_M4x10_Z_threaded"
    dims = {d.symbol: d for d in ISO.dimensions(p)}
    assert dims["m"].value == 4.4 and dims["p max"].value == 2.4
    assert dims["Recess"].value == "H2" and dims["flank"].unit == "°"
    assert {d.symbol: d.value for d in ISO.dimensions({**p, "drive": "Z"})}["m"] == 4.3
    assert dims["b"].value == "to head"
    assert {d.symbol: d.value for d in ISO.dimensions({**p, "size": "M6", "length": 50})}["b"] == "38 min"


def test_notes():
    notes = ISO.notes(ISO.validate({"size": "M3.5", "length": "14"}))
    assert any("M3.5 is in parentheses" in n for n in notes)
    assert any("14 mm is in parentheses" in n for n in notes)
    assert any("Threaded up to the head" in n for n in notes)
    notes = ISO.notes(ISO.validate({"size": "M8", "length": 47.5, "drive": "Z"}))
    assert any("not a standard length" in n for n in notes)
    assert any("Partially threaded" in n for n in notes)
    assert any("ISO 4757" in n for n in notes)

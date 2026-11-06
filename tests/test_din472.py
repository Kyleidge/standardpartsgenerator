import math
from functools import cache

import pytest
from build123d import Cylinder, GeomType, Vector

from standardparts.standards.base import ParameterError
from standardparts.standards.din472 import DIN472, _circlip
from standardparts.standards.din472_data import SIZES

DIN = DIN472()
STEEL = 7.85e-3  # g / mm^3
GROOVE_WIDTH = {0.8: 0.9, 1: 1.1, 1.2: 1.3, 1.5: 1.6, 1.75: 1.85, 2: 2.15,
                2.5: 2.65, 3: 3.15, 4: 4.15, 5: 5.15}


def test_size_range():
    assert len(SIZES) == 88
    assert list(SIZES)[0] == "8" and list(SIZES)[-1] == "300"


@pytest.mark.parametrize("rd", SIZES.values(), ids=list(SIZES))
def test_data_rows_are_consistent(rd):
    assert rd.t == pytest.approx((rd.d2 - rd.d1) / 2, abs=0.011)
    assert rd.d4 < rd.d1 < rd.d2 < rd.d3
    assert rd.b <= rd.a_max
    assert rd.d5_min < rd.a_max
    # Groove width m follows the ring thickness s.
    assert rd.m == GROOVE_WIDTH[rd.s]
    # Edge distance n is 3 t, rounded up to 0.1 mm.
    assert rd.n_min == pytest.approx(math.ceil(round(30 * rd.t, 6)) / 10)


def test_corrected_rows():
    assert SIZES["72"].d3 == 76.5
    assert SIZES["82"].s == 2.5
    assert SIZES["90"].d3 == 95.5


@cache
def ring(size, state):
    return DIN.build(DIN.validate({"size": size, "state": state}))


@pytest.mark.parametrize("size", list(SIZES))
@pytest.mark.parametrize("state", ["free", "installed"])
def test_ring_solid(size, state):
    rd = SIZES[size]
    part = ring(size, state)
    assert part.is_valid
    assert len(part.solids()) == 1
    assert part.label == f"DIN 472 - {size} x {rd.s:g} ({state})"
    bb = part.bounding_box()
    assert bb.min.Z == pytest.approx(0, abs=1e-6)
    assert bb.max.Z == pytest.approx(rd.s, abs=1e-6)

    # Outer edge at the back of the ring sits on d3 (free) or d2 (installed);
    # the section there is b wide.
    r_out = rd.d3 / 2 if state == "free" else rd.d2 / 2
    eps = 0.02 * rd.b
    z = rd.s / 2
    assert not part.is_inside(Vector(0, -(r_out + eps), z))
    assert part.is_inside(Vector(0, -(r_out - eps), z))
    assert part.is_inside(Vector(0, -(r_out - rd.b + eps), z))
    assert not part.is_inside(Vector(0, -(r_out - rd.b - eps), z))
    # Nothing reaches beyond the outer circle anywhere.
    assert (part - Cylinder(r_out + 1e-3, 3 * rd.s)).volume < 1e-6 * part.volume

    # Opening towards +Y, with a gap between the lugs.
    assert not part.is_inside(Vector(0, r_out - rd.b / 2, z))
    clip = _circlip(size)
    lay = clip.free if state == "free" else clip.installed
    assert lay.gap > 0


@pytest.mark.parametrize("size", list(SIZES))
def test_installed_ring_clear_of_d4(size):
    rd = SIZES[size]
    part = ring(size, "installed")
    inside = part & Cylinder(rd.d4 / 2, 3 * rd.s)
    assert inside.volume < 1e-6 * part.volume


@pytest.mark.parametrize("size", list(SIZES))
def test_squeezing_closes_the_ring(size):
    clip = _circlip(size)
    # The gap closes from free to installed and further at d1 (passing the
    # bore), but never shuts.
    assert clip.free.gap > clip.installed.gap > clip.bore_gap > 0
    assert clip.installed.phi > clip.free.phi
    # Middle fibre keeps its length (lugs are rigid).
    w = clip.w_mid
    assert clip.free.phi * (clip.r_free - w) == pytest.approx(
        clip.installed.phi * (clip.r_inst - w)
    )
    assert clip.free.phi * (clip.r_free - w) == pytest.approx(clip.fibre)


@pytest.mark.parametrize("size", [k for k in SIZES if k != "10"])
def test_mass_close_to_table(size):
    # The lug outline and section taper are not standardised, and the table
    # weights are not self-consistent (their implied fill factor varies by a
    # third across sizes), so the band is wide: the model lands between 0.93
    # and 1.37 times the table mass, within 15 % for 55 of 88 sizes (most of
    # d1 <= 48 and d1 >= 170) and 16 to 37 % heavy for most of 50 to 165.
    # d1 = 10 is excluded: its table weight (0.18 g, between 0.15 at 9 and
    # 0.31 at 11) is 1.7 x below the model; Maedler lists 0.26 g.
    rd = SIZES[size]
    ratio = ring(size, "free").volume * STEEL / rd.weight
    assert 0.9 < ratio < 1.4


@pytest.mark.parametrize("state", ["free", "installed"])
def test_plier_holes(state):
    rd = SIZES["50"]
    circles = ring("50", state).edges().filter_by(GeomType.CIRCLE)
    holes = [e for e in circles if e.radius == pytest.approx(rd.d5_min / 2)]
    assert len(holes) == 4  # two holes, top and bottom edge each


@pytest.mark.parametrize(
    "raw",
    [{"size": "23"}, {"size": "7"}, {"size": "301"}, {"size": "20", "state": "squashed"}],
)
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        DIN.validate(raw)


def test_size_accepts_float_text():
    assert DIN.validate({"size": "20.0"})["size"] == "20"


def test_names():
    p = DIN.validate({"size": "20", "state": "installed"})
    assert DIN.designation(p) == "DIN 472 - 20 x 1"
    assert DIN.file_stem(p) == "DIN472_20x1_installed"
    assert DIN.file_stem({"size": "47", "state": "free"}) == "DIN472_47x1.75_free"


def test_dimension_table_shows_groove_and_gaps():
    dims = {d.symbol: d.value for d in DIN.dimensions({"size": "20", "state": "free"})}
    for sym in ("d1", "s", "d3", "d2", "m H13", "t", "n min", "d4", "gap free", "gap inst."):
        assert sym in dims
    assert dims["d2"] == 21 and dims["m H13"] == 1.1 and dims["t"] == 0.5
    assert dims["gap free"] > dims["gap inst."] > 0


def test_schema_uses_supported_kinds():
    params = DIN.describe_json()["parameters"]
    assert [p["name"] for p in params] == ["size", "state"]
    assert all(p["kind"] == "select" for p in params)

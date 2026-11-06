import pytest
from build123d import Cylinder, GeomType, Vector

from standardparts.export import build_part, step_bytes
from standardparts.standards import STANDARDS, ParameterError
from standardparts.standards.din471 import _circlip, u
from standardparts.standards.din471_data import SIZES

DIN = STANDARDS["din471"]
STEEL = 7.85e-3  # g / mm^3
GROOVE_WIDTH = {0.4: 0.5, 0.6: 0.7, 0.7: 0.8, 0.8: 0.9, 1: 1.1, 1.2: 1.3, 1.5: 1.6,
                1.75: 1.85, 2: 2.15, 2.5: 2.65, 3: 3.15, 4: 4.15, 5: 5.15}


@pytest.mark.parametrize("rd", SIZES.values(), ids=list(SIZES))
def test_data_rows_are_consistent(rd):
    assert rd.t == pytest.approx((rd.d1 - rd.d2) / 2, abs=0.011)
    assert rd.d3 < rd.d2 < rd.d1 < rd.d4
    assert rd.b <= rd.a_max
    assert rd.d5_min < rd.a_max
    # Groove width m follows the ring thickness s.
    assert rd.m == GROOVE_WIDTH[rd.s]


def ring(size, state):
    return build_part("din471", DIN.validate({"size": size, "state": state}))


@pytest.mark.parametrize("size", list(SIZES))
@pytest.mark.parametrize("state", ["free", "installed"])
def test_ring_solid(size, state):
    rd = SIZES[size]
    part = ring(size, state)
    assert part.is_valid
    assert len(part.solids()) == 1
    bb = part.bounding_box()
    assert bb.min.Z == pytest.approx(0, abs=1e-6)
    assert bb.max.Z == pytest.approx(rd.s, abs=1e-6)

    # Inner edge at the back of the ring sits on d3 (free) or d2 (installed);
    # the section there is b wide.
    r_in = rd.d3 / 2 if state == "free" else rd.d2 / 2
    eps = 0.02 * rd.b
    z = rd.s / 2
    assert not part.is_inside(Vector(0, -(r_in - eps), z))
    assert part.is_inside(Vector(0, -(r_in + eps), z))
    assert part.is_inside(Vector(0, -(r_in + rd.b - eps), z))
    assert not part.is_inside(Vector(0, -(r_in + rd.b + eps), z))

    # Opening towards +Y, with a gap between the lugs.
    assert not part.is_inside(Vector(0, r_in + rd.b / 2, z))
    clip = _circlip(size)
    lay = clip.free if state == "free" else clip.installed
    assert lay.gap > 0


@pytest.mark.parametrize("size", list(SIZES))
def test_installed_ring_fits_clearance_diameter(size):
    rd = SIZES[size]
    part = ring(size, "installed")
    outside = part - Cylinder(rd.d4 / 2, 3 * rd.s)
    assert outside.volume < 1e-6 * part.volume


@pytest.mark.parametrize("size", list(SIZES))
def test_installing_opens_the_ring(size):
    clip = _circlip(size)
    assert clip.installed.gap > clip.free.gap
    assert clip.installed.phi < clip.free.phi
    # Middle fibre keeps its length (lugs are rigid).
    rd = SIZES[size]
    w = (rd.b + clip.w_end) / 4
    assert clip.free.phi * (clip.r_free + w) == pytest.approx(
        clip.installed.phi * (clip.r_inst + w)
    )


@pytest.mark.parametrize("size", [k for k, r in SIZES.items() if r.d1 >= 12])
def test_mass_close_to_table(size):
    # The lug outline is not standardised; above 12 mm the modeled shape
    # comes within 20 % of the table mass. Small rings are lug-dominated and
    # the model runs heavy there.
    rd = SIZES[size]
    assert ring(size, "free").volume * STEEL == pytest.approx(rd.weight, rel=0.2)


@pytest.mark.parametrize("state", ["free", "installed"])
def test_plier_holes(state):
    rd = SIZES["50"]
    circles = ring("50", state).edges().filter_by(GeomType.CIRCLE)
    holes = [e for e in circles if e.radius == pytest.approx(rd.d5_min / 2)]
    assert len(holes) == 4  # two holes, top and bottom edge each


@pytest.mark.parametrize(
    "raw",
    [{"size": "21.5"}, {"size": "301"}, {"size": "20", "state": "squashed"}],
)
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        DIN.validate(raw)


def test_size_accepts_float_text():
    assert DIN.validate({"size": "20.0"})["size"] == "20"


def test_step_has_name_and_state():
    data = step_bytes("din471", DIN.validate({"size": "20", "state": "free"}))
    assert data.startswith(b"ISO-10303-21;")
    assert b"DIN 471 - 20 x 1.2 (free)" in data
    assert DIN.file_stem({"size": "20", "state": "free"}) == "DIN471_20x1.2_free"

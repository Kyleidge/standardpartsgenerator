import dataclasses
import math
import tempfile
from pathlib import Path

import pytest
from build123d import GeomType, Vector, export_step, import_step

from standardparts.geometry import SQRT3, hex_socket
from standardparts.standards.base import ParameterError
from standardparts.standards.iso7380 import ISO7380, build_body, dome_arc
from standardparts.standards.iso7380_data import B_2011, LENGTH_SERIES, SIZES

ISO = ISO7380()

# ISO 7380-1:2011 length data as published for GB/T 70.2-2015: standard
# length range and the first partially threaded length of each size.
LENGTHS_2011 = {
    "M3": (6, 30, 25), "M4": (6, 40, 30), "M5": (8, 50, 30), "M6": (10, 60, 35),
    "M8": (12, 80, 40), "M10": (16, 90, 45), "M12": (20, 90, 55), "M16": (25, 90, 65),
}


# --- data -------------------------------------------------------------------

def test_length_ranges():
    assert list(SIZES) == list(LENGTHS_2011)
    for size, (lo, hi, _) in LENGTHS_2011.items():
        sd = SIZES[size]
        assert (sd.l_min, sd.l_max) == (lo, hi)
        assert lo in LENGTH_SERIES and hi in LENGTH_SERIES


@pytest.mark.parametrize("size", list(SIZES))
def test_thread_rule_reproduces_2011_data(size):
    sd = dataclasses.replace(SIZES[size], b=B_2011.get(size, SIZES[size].b))
    first = LENGTHS_2011[size][2]
    for l in sd.standard_lengths():
        assert sd.is_fully_threaded(l) == (l < first), (size, l)


def test_m16_uses_2022_thread_length():
    sd = SIZES["M16"]
    assert sd.b == 3 * sd.d
    assert sd.is_fully_threaded(65) and not sd.is_fully_threaded(70)
    assert sd.thread_geometry(80) == (22, 32)


@pytest.mark.parametrize("sd", SIZES.values(), ids=list(SIZES))
def test_size_rows_are_consistent(sd):
    # Rules printed with ISO 7380-1:2022 Table 1.
    assert sd.dw_min == pytest.approx(0.92 * sd.dk_min, abs=0.005)
    assert sd.t_max == pytest.approx(sd.k_min - sd.wb_min, abs=1e-9)
    assert sd.e_min == pytest.approx(1.14 * sd.s_min, abs=0.005)
    assert sd.dk_min < sd.dk_max and sd.k_min < sd.k_max and sd.rf_min < sd.rf_max
    assert sd.ds_min < sd.d < sd.da_max
    assert sd.rs_min < sd.rt_min
    assert sd.s_nom <= sd.s_min < sd.s_max and sd.t_min < sd.t_max
    # Socket fits inside the top flat; the fillet ends inside da max.
    assert sd.s_nom / SQRT3 < sd.dL_ref / 2 < sd.dk_max / 2
    for full in (True, False):
        assert sd.d + 2 * sd.underhead_radius(full) <= sd.da_max + 1e-9


@pytest.mark.parametrize("sd", SIZES.values(), ids=list(SIZES))
def test_dome_arc_is_well_formed(sd):
    (cr, cz), (mr, mz) = dome_arc(sd)
    # Centre below the bearing face and inside the top flat: the dome falls
    # monotonically from the flat to its widest point at the bearing edge.
    assert cz < 0 and cr < sd.dL_ref / 2
    assert math.hypot(sd.dk_max / 2 - cr, cz) == pytest.approx(sd.rf_max)
    assert math.hypot(sd.dL_ref / 2 - cr, sd.k_max - cz) == pytest.approx(sd.rf_max)
    assert sd.dL_ref / 2 < mr < sd.dk_max / 2 and 0 < mz < sd.k_max


# --- geometry -----------------------------------------------------------------

def first_partial(sd):
    return next(l for l in sd.standard_lengths() if not sd.is_fully_threaded(l))


def cases():
    for size, sd in SIZES.items():
        for l in sorted({sd.l_min, sd.l_max, first_partial(sd)}):
            yield size, l


def modeled_cases():
    for size, sd in SIZES.items():
        yield size, first_partial(sd)
    # Threaded to the head, including M8 x 25, which needs the thread-end
    # retry in iso7380._threaded_body.
    yield from [("M3", 6), ("M8", 25), ("M16", 30)]


def check_solid(size, l, thread):
    sd = SIZES[size]
    params = ISO.validate({"size": size, "length": l, "thread": thread})
    part = ISO.build(params)
    assert part.label == f"ISO 7380-1 - {size} x {l:g}"
    assert part.is_valid
    assert len(part.solids()) == 1
    bb = part.bounding_box()
    tol = 1e-3 * sd.d
    k = sd.k_max
    assert bb.min.Z == pytest.approx(-l, abs=tol)
    assert bb.max.Z == pytest.approx(k, abs=tol)
    assert bb.size.X == pytest.approx(sd.dk_max, abs=tol)
    assert bb.size.Y == pytest.approx(sd.dk_max, abs=tol)
    # Socket is empty, head and shank are solid.
    assert not part.is_inside(Vector(0, 0, k - sd.t_min / 2))
    r_wall = (sd.dL_ref / 2 + sd.s_nom / SQRT3) / 2
    assert part.is_inside(Vector(r_wall, 0, k - sd.t_min / 2))
    assert part.is_inside(Vector(0, 0, -l / 2))
    # Bearing face reaches dw min at the reference height 0.1 mm.
    assert part.is_inside(Vector(sd.dw_min / 2 - 0.01, 0, 0.1))
    assert not part.is_inside(Vector(sd.dk_max / 2 + 0.05, 0, 0.05))
    assert not part.is_inside(Vector(0.8 * sd.d, 0, -0.05))
    return part


@pytest.mark.parametrize("size,l", list(cases()))
def test_simplified_solid(size, l):
    part = check_solid(size, l, "simplified")
    sd = SIZES[size]
    shank = math.pi * (sd.d / 2) ** 2 * l
    head = math.pi * (sd.dk_max / 2) ** 2 * sd.k_max
    assert 0.7 * (shank + head) < part.volume < shank + head
    body = build_body(sd, l, "simplified")
    r_d = 0.96 * sd.s_nom / 2
    socket = SQRT3 / 2 * sd.s_nom**2 * sd.t_min + math.pi * r_d**3 / math.tan(math.radians(59)) / 3
    assert body.volume - part.volume == pytest.approx(socket, rel=0.01)


@pytest.mark.parametrize("size,l", list(modeled_cases()))
def test_modeled_thread_solid(size, l):
    part = check_solid(size, l, "modeled")
    plain = ISO.build(ISO.validate({"size": size, "length": l}))
    sd = SIZES[size]
    threaded = l if sd.is_fully_threaded(l) else sd.b
    r_mean = sd.d / 2 - 0.2706 * sd.P
    expected = 0.3045 * sd.P**2 * 2 * math.pi * r_mean * threaded / sd.P
    assert plain.volume - part.volume == pytest.approx(expected, rel=0.15)


@pytest.mark.parametrize("sd", SIZES.values(), ids=list(SIZES))
def test_socket_wall(sd):
    body = build_body(sd, sd.l_min, "simplified")
    tool = hex_socket(sd.s_nom, sd.t_min, sd.k_max)
    under, dome = [], []
    for f in body.faces():
        z = f.center().Z
        if f.geom_type == GeomType.PLANE and abs(z - sd.k_max) < 1e-6:
            continue                      # top flat, cut by the socket
        (under if z <= 1e-6 else dome).append(tool.distance_to(f))
    # Wall between the socket and the bearing face / underhead fillet.
    assert min(under) >= sd.wb_min
    # The dome is closest at the rim of the top flat: (dL - e) / 2.
    assert min(dome) == pytest.approx(sd.dL_ref / 2 - sd.s_nom / SQRT3, abs=1e-3)
    assert min(dome) > 0.1


def test_step_roundtrip():
    params = ISO.validate({"size": "M6", "length": 20, "thread": "modeled"})
    part = ISO.build(params)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "part.stp"
        assert export_step(part, path)
        imported = import_step(path)
    assert imported.is_valid
    assert imported.volume == pytest.approx(part.volume, rel=1e-4)


# --- parameters ---------------------------------------------------------------

@pytest.mark.parametrize(
    "raw",
    [
        {"size": "M7", "length": 20},
        {"size": "M20", "length": 40},
        {"size": "M6", "length": 8},
        {"size": "M6", "length": 61},
        {"size": "M6", "length": "abc"},
        {"size": "M6", "length": "inf"},
        {"size": "M6", "length": 20, "thread": "fancy"},
    ],
)
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        ISO.validate(raw)


def test_parameters_and_names():
    params = {p.name: p for p in ISO.parameters()}
    assert params["size"].kind == "select" and params["length"].kind == "length"
    assert params["length"].preferred["M3"] == [6, 8, 10, 12, 16, 20, 25, 30]
    assert params["length"].limits["M16"] == [25, 90]
    p = ISO.validate({"size": "M8", "length": "30", "thread": "modeled"})
    assert ISO.designation(p) == "ISO 7380-1 - M8 x 30"
    assert ISO.file_stem(p) == "ISO7380-1_M8x30_threaded"
    assert ISO.file_stem({**p, "thread": "simplified"}) == "ISO7380-1_M8x30"
    dims = {d.symbol: d.value for d in ISO.dimensions(p)}
    assert dims["b"] == "to head" and dims["rt min"] == 0.7 and dims["dk max"] == 14


def test_notes():
    notes = ISO.notes(ISO.validate({"size": "M8", "length": "22.5"}))
    assert any("not a preferred length" in n for n in notes)
    assert any("Threaded up to the head" in n for n in notes)
    assert any("limited to stay inside da max" in n for n in notes)
    notes = ISO.notes(ISO.validate({"size": "M10", "length": 60}))
    assert any("Partially threaded" in n for n in notes)

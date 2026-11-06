import math
import tempfile
from pathlib import Path

import pytest
from build123d import Vector, export_step, import_step

from standardparts.geometry import SQRT3, MetricThread
from standardparts.standards.base import ParameterError
from standardparts.standards.iso7379 import ISO7379, TAN_UC, build_body
from standardparts.standards.iso7379_data import LENGTH_SERIES, SIZES

ISO = ISO7379()

# Range of commercial lengths, ISO 7379:1983 table (same on fasten.it).
LENGTH_RANGES = {
    "6.5": (10, 40), "8": (12, 50), "10": (16, 120), "13": (16, 120),
    "16": (30, 120), "20": (40, 120), "25": (50, 120),
}
THREADS = {"6.5": "M5", "8": "M6", "10": "M8", "13": "M10", "16": "M12", "20": "M16", "25": "M20"}
# Nominal thread lengths as listed by suppliers (middle of b min / b max).
B_NOM = {"6.5": 9.5, "8": 11, "10": 13, "13": 16, "16": 18, "20": 22, "25": 27}


def f9(ds: float) -> tuple[float, float]:
    """ISO 286 f9 limits (upper, lower deviation) in mm for 6 < ds <= 30."""
    if ds <= 10:
        return -0.013, -0.049
    if ds <= 18:
        return -0.016, -0.059
    return -0.020, -0.072


# --- data -------------------------------------------------------------------

def test_sizes_and_length_ranges():
    assert {s: sd.thread for s, sd in SIZES.items()} == THREADS
    for size, (lo, hi) in LENGTH_RANGES.items():
        sd = SIZES[size]
        assert (sd.l_min, sd.l_max) == (lo, hi)
        assert lo in LENGTH_SERIES and hi in LENGTH_SERIES
        assert sd.b_nom == B_NOM[size]


@pytest.mark.parametrize("sd", SIZES.values(), ids=list(SIZES))
def test_size_rows_are_consistent(sd):
    es, ei = f9(sd.ds)
    assert sd.ds_max == pytest.approx(sd.ds + es, abs=1e-9)
    assert sd.ds_min == pytest.approx(sd.ds + ei, abs=1e-9)
    assert sd.d == float(sd.thread[1:])
    assert sd.dk_min < sd.dk_max < sd.dk_max_knurled
    assert sd.k_min < sd.k_max and sd.b_min < sd.b_max and sd.dg2_min < sd.dg2_max
    assert sd.e_min == pytest.approx(1.14 * sd.s_min, abs=0.005)
    assert sd.s_nom < sd.s_min < sd.s_max
    # Socket wall above the bearing face.
    assert sd.k_max - sd.t_min >= sd.w_min
    # Groove under the head, neck below the shoulder: both below the next
    # diameter, the neck below the thread root, the fillets inside their
    # transition diameters and widths.
    assert sd.dg1_min < sd.ds < sd.da1_max
    assert sd.da2_max == sd.d
    assert sd.dg2_max < MetricThread(sd.d, sd.P).d1
    assert sd.dg2_nom + 2 * sd.r2_min <= sd.da2_max
    assert sd.r1_min < sd.g1_max and sd.r2_min < sd.g2_max
    # The neck and the 30 deg cone fit inside the thread length.
    rise = (sd.d - sd.dg2_nom) / 2 / TAN_UC
    assert sd.g2_max + rise < 0.5 * sd.b_nom


# --- geometry -----------------------------------------------------------------

def check_solid(size, l, thread):
    sd = SIZES[size]
    params = ISO.validate({"size": size, "length": l, "thread": thread})
    part = ISO.build(params)
    assert part.label == f"ISO 7379 - {size} x {l:g}"
    assert part.is_valid
    assert len(part.solids()) == 1
    bb = part.bounding_box()
    tol = 1e-3 * sd.d
    k = sd.k_max
    b = sd.b_nom
    assert bb.min.Z == pytest.approx(-(l + b), abs=tol)
    assert bb.max.Z == pytest.approx(k, abs=tol)
    assert bb.size.X == pytest.approx(sd.dk_max, abs=tol)
    assert bb.size.Y == pytest.approx(sd.dk_max, abs=tol)
    # Socket empty, head wall and shoulder solid.
    assert not part.is_inside(Vector(0, 0, k - sd.t_min / 2))
    assert part.is_inside(Vector(0, 0, sd.w_min / 2))
    assert part.is_inside(Vector(sd.ds / 2 - 0.05, 0, -l / 2))
    assert not part.is_inside(Vector(sd.ds / 2 + 0.02, 0, -l / 2))
    # Groove under the head.
    r_groove = (sd.dg1_min + sd.ds) / 4
    assert not part.is_inside(Vector(r_groove, 0, -sd.g1_max / 2))
    assert part.is_inside(Vector(sd.dg1_min / 2 - 0.05, 0, -sd.g1_max / 2))
    # Neck between shoulder and thread.
    z_neck = -l - sd.g2_max / 2
    assert part.is_inside(Vector(sd.dg2_nom / 2 - 0.05, 0, z_neck))
    assert not part.is_inside(Vector(sd.dg2_nom / 2 + 0.05, 0, z_neck))
    assert not part.is_inside(Vector(sd.d / 2 - 0.05 * sd.P, 0, -l - sd.g2_max - 0.02))
    # Thread core.
    assert part.is_inside(Vector(0, 0, -l - 0.8 * b))
    return part


@pytest.mark.parametrize(
    "size,l", [(s, l) for s, sd in SIZES.items() for l in sd.standard_lengths()]
)
def test_simplified_solid(size, l):
    part = check_solid(size, l, "simplified")
    sd = SIZES[size]
    cylinders = math.pi / 4 * (sd.dk_max**2 * sd.k_max + sd.ds**2 * l + sd.d**2 * sd.b_nom)
    assert 0.85 * cylinders < part.volume < cylinders


@pytest.mark.parametrize("sd", SIZES.values(), ids=list(SIZES))
def test_socket_volume(sd):
    l = sd.l_min
    body = build_body(sd, l, "simplified")
    part = ISO.build(ISO.validate({"size": sd.size, "length": l}))
    r_d = 0.96 * sd.s_nom / 2
    socket = SQRT3 / 2 * sd.s_nom**2 * sd.t_min + math.pi * r_d**3 / math.tan(math.radians(59)) / 3
    assert body.volume - part.volume == pytest.approx(socket, rel=0.01)


def modeled_cases():
    for size, sd in SIZES.items():
        yield size, sd.l_min
    yield "10", 120


@pytest.mark.parametrize("size,l", list(modeled_cases()))
def test_modeled_thread_solid(size, l):
    part = check_solid(size, l, "modeled")
    plain = ISO.build(ISO.validate({"size": size, "length": l}))
    sd = SIZES[size]
    # Full thread from the tip up to where the 30 deg cone meets the root d1.
    t = MetricThread(sd.d, sd.P)
    threaded = sd.b_nom - sd.g2_max - (t.d1 - sd.dg2_nom) / 2 / TAN_UC
    r_mean = sd.d / 2 - 0.2706 * sd.P
    expected = 0.3045 * sd.P**2 * 2 * math.pi * r_mean * threaded / sd.P
    assert plain.volume - part.volume == pytest.approx(expected, rel=0.15)


def test_step_roundtrip():
    params = ISO.validate({"size": "10", "length": 40, "thread": "modeled"})
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
        {"size": "12", "length": 20},
        {"size": "M8", "length": 20},
        {"size": "10", "length": 12},
        {"size": "10", "length": 121},
        {"size": "6.5", "length": 50},
        {"size": "10", "length": "abc"},
        {"size": "10", "length": "inf"},
        {"size": "10", "length": 40, "thread": "fancy"},
    ],
)
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        ISO.validate(raw)


def test_parameters_and_names():
    params = {p.name: p for p in ISO.parameters()}
    assert params["size"].kind == "select" and params["length"].kind == "length"
    labels = {o.value: o.label for o in params["size"].options}
    assert labels["10"] == "10 (M8)" and labels["6.5"] == "6.5 (M5)"
    assert params["length"].preferred["6.5"] == [10, 12, 16, 20, 25, 30, 40]
    assert params["length"].limits["16"] == [30, 120]
    assert params["size"].default in SIZES
    assert params["length"].default in params["length"].preferred[params["size"].default]
    p = ISO.validate({"size": "10", "length": "40", "thread": "modeled"})
    assert ISO.designation(p) == "ISO 7379 - 10 x 40"
    assert ISO.file_stem(p) == "ISO7379_10x40_threaded"
    assert ISO.file_stem({**p, "thread": "simplified"}) == "ISO7379_10x40"
    dims = {d.symbol: d.value for d in ISO.dimensions(p)}
    assert dims["d"] == "M8" and dims["b"] == 13 and dims["l + b"] == 53
    assert dims["ds max"] == 9.987 and dims["k max"] == 7


def test_notes():
    notes = ISO.notes(ISO.validate({"size": "10", "length": "35"}))
    assert any("not a standard shoulder length" in n for n in notes)
    assert any("f9" in n for n in notes)
    notes = ISO.notes(ISO.validate({"size": "10", "length": 40, "thread": "modeled"}))
    assert not any("not a standard" in n for n in notes)
    assert any("undercut cone" in n for n in notes)

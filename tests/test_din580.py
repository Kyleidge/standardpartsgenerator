import math
import tempfile
from io import BytesIO
from pathlib import Path

import pytest
from build123d import Unit, Vector, export_step, import_step

from standardparts.geometry import MetricThread
from standardparts.standards.base import ParameterError
from standardparts.standards.din580 import DIN580, EyeGeometry, build_eye_bolt
from standardparts.standards.din580_data import SIZES

DIN = DIN580()
STEEL = 7.85e-3  # g / mm^3


@pytest.mark.parametrize("sd", SIZES.values(), ids=list(SIZES))
def test_data_rows_are_consistent(sd):
    g = EyeGeometry(sd)
    # The ring section is round at the top: k = (d3 - d4) / 2 in every row.
    assert sd.k == (sd.d3 - sd.d4) / 2
    assert sd.k < sd.m < sd.d2
    # The ring outline is concentric with the eye and its top is at h, so
    # its bottom (d3 below the top) lies within the collar height.
    assert abs(sd.h - sd.d3) < sd.e
    # The eye opening starts above the collar top.
    assert sd.e < g.z_eye_bottom <= sd.e + 0.1 * sd.d4
    # Undercut: 2P long, below the thread minor diameter.
    assert sd.f == pytest.approx(2 * sd.P)
    assert sd.dg < MetricThread(sd.d, sd.P).d3
    assert sd.r2 < sd.f
    assert sd.wll_side < sd.wll_45 < sd.wll_axial
    # The axial WLL loads the thread stress area with 37 to 63 N/mm^2
    # (3.8 to 6.4 kg/mm^2); this catches a slipped digit in the table.
    stress_area = math.pi / 4 * (sd.d - 0.9382 * sd.P) ** 2
    assert 3.5 < sd.wll_axial / stress_area < 6.6


def test_sizes_grow():
    rows = list(SIZES.values())
    assert [r.size for r in rows] == [
        "M8", "M10", "M12", "M16", "M20", "M24", "M30", "M36", "M42", "M48",
        "M56", "M64", "M72x6", "M80x6", "M100x6",
    ]
    for a, b in zip(rows, rows[1:]):
        assert a.d < b.d
        for field in ("d2", "d3", "d4", "e", "h", "k", "l", "m", "dg", "mass",
                      "wll_axial", "wll_45", "wll_side"):
            assert getattr(a, field) < getattr(b, field), field


def check_solid(size, thread):
    sd = SIZES[size]
    g = EyeGeometry(sd)
    part = DIN.build(DIN.validate({"size": size, "thread": thread}))
    assert part.is_valid
    assert len(part.solids()) == 1
    bb = part.bounding_box()
    tol = 1e-3 * sd.d
    assert bb.min.Z == pytest.approx(-sd.l, abs=tol)
    assert bb.max.Z == pytest.approx(sd.h, abs=tol)
    assert bb.size.X == pytest.approx(sd.d3, abs=tol)  # eye outer diameter
    # Collar: d2 at the bearing face, less the small edge break and draft.
    assert sd.d2 - 0.01 * sd.d2 < bb.size.Y <= sd.d2 + tol
    # The eye is open; the ring, collar and shank are solid.
    assert not part.is_inside(Vector(0, 0, g.zc))
    assert not part.is_inside(Vector(0, sd.d2, g.zc))
    assert part.is_inside(Vector(0, 0.9 * sd.d2 / 2, sd.e / 2))
    assert part.is_inside(Vector(0, 0, -sd.l / 2))
    # Thread undercut: dg just under the bearing face, d below it.
    z_g = -(sd.f + sd.r2) / 2
    assert part.is_inside(Vector(0.98 * sd.dg / 2, 0, z_g))
    assert not part.is_inside(Vector(1.02 * sd.dg / 2, 0, z_g))
    # Ring: d3 / d4 contour and the out-of-plane width (k at the top, m at
    # the bottom), checked between the loft sections too.
    eps = 0.01 * g.a
    for phi in (0, 7.5, 52.5, 90, 127.5):
        t = math.radians(phi)
        radial = Vector(math.sin(t), 0, math.cos(t))
        centre = Vector(0, 0, g.zc)
        for r in (sd.d3 / 2 - eps, sd.d4 / 2 + eps, g.Rm):
            assert part.is_inside(centre + radial * r), (phi, r)
        for r in (sd.d3 / 2 + eps, sd.d4 / 2 - eps):
            assert not part.is_inside(centre + radial * r), (phi, r)
        w = g.half_width(phi)
        mid = centre + radial * g.Rm
        assert part.is_inside(mid + Vector(0, w - eps, 0)), phi
        assert not part.is_inside(mid + Vector(0, w + eps, 0)), phi
    assert g.half_width(0) == sd.k / 2 and g.half_width(180) == sd.m / 2
    return part


@pytest.mark.parametrize("size", list(SIZES))
def test_simplified_solid(size):
    part = check_solid(size, "simplified")
    sd = SIZES[size]
    # Mass against the DIN 580 table (steel). The table's M24 mass (0.74 kg)
    # looks low: M24 scales M20 by 1.25 in every eye dimension, which
    # predicts about 0.88 kg; the model gives 0.885 kg.
    mass = part.volume * STEEL / 1000
    tol = 0.25 if size == "M24" else 0.12
    assert mass == pytest.approx(sd.mass, rel=tol)


@pytest.mark.parametrize("size", list(SIZES))
def test_modeled_thread_solid(size):
    part = check_solid(size, "modeled")
    plain = DIN.build(DIN.validate({"size": size}))
    sd = SIZES[size]
    # The ISO 68-1 basic profile removes 0.3045 P^2 per pitch of cross
    # section compared with a plain cylinder at d (computed at mean radius).
    r_mean = sd.d / 2 - 0.2706 * sd.P
    expected = 0.3045 * sd.P**2 * 2 * math.pi * r_mean * (sd.l - sd.f) / sd.P
    assert plain.volume - part.volume == pytest.approx(expected, rel=0.15)


def test_step_roundtrip():
    params = DIN.validate({"size": "M12", "thread": "modeled"})
    part = DIN.build(params)
    buf = BytesIO()
    export_step(part, buf, unit=Unit.MM)
    data = buf.getvalue()
    assert data.startswith(b"ISO-10303-21;")
    assert DIN.designation(params).encode() in data
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "part.stp"
        path.write_bytes(data)
        imported = import_step(path)
    assert imported.is_valid
    assert imported.volume == pytest.approx(part.volume, rel=1e-4)


@pytest.mark.parametrize(
    "raw",
    [
        {"size": "M14"},
        {"size": "M100"},
        {"size": "m12"},
        {"size": "M12", "thread": "fancy"},
    ],
)
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        DIN.validate(raw)


def test_length_is_fixed():
    # There is no length parameter; one passed anyway is ignored.
    assert DIN.validate({"size": "M16", "length": 99}) == {"size": "M16", "thread": "simplified"}
    assert [p.name for p in DIN.parameters()] == ["size", "thread"]


def test_unknown_thread_mode_in_builder():
    with pytest.raises(ParameterError):
        build_eye_bolt(SIZES["M8"], "fancy")


def test_info():
    params = DIN.validate({"size": "M20", "thread": "modeled"})
    dims = {d.symbol: d for d in DIN.dimensions(params)}
    sd = SIZES["M20"]
    assert dims["d3"].value == sd.d3 and dims["h"].value == sd.h
    assert dims["l"].value == sd.l
    table = {"WLL 0°": sd.wll_axial, "WLL 45°": sd.wll_45, "WLL side": sd.wll_side}
    for symbol, kg in table.items():
        wll = dims[symbol]
        assert wll.unit == ("t" if kg >= 1000 else "kg")
        assert wll.value * (1000 if wll.unit == "t" else 1) == kg
    assert (dims["WLL 0°"].value, dims["WLL 0°"].unit) == (1.2, "t")
    small = {d.symbol: d for d in DIN.dimensions(DIN.validate({"size": "M8"}))}
    assert (small["WLL 0°"].value, small["WLL 0°"].unit) == (140, "kg")
    assert DIN.file_stem(params) == "DIN580_M20_threaded"
    assert DIN.designation(params) == "Eye bolt DIN 580 - M20 - C15E"
    assert any("modeled" in n for n in DIN.notes(params))

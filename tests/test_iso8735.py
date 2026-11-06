import math
import tempfile
from pathlib import Path

import pytest
from build123d import Vector, export_step, import_step

from standardparts.geometry import MetricThread
from standardparts.standards import ParameterError
from standardparts.standards.iso8735 import (
    ISO8735,
    TAN_CH,
    bore_bottom_z,
    crown,
    drill_tip_z,
    expected_volume,
    vent_depth,
)
from standardparts.standards.iso8735_data import LENGTH_SERIES, SIZES

PIN = ISO8735()

# ISO 8735:1997 Table 1: d1: (a, c, thread, P, d3, t1, t2 min, t3).
TABLE = {
    "6": (0.8, 2.1, "M4", 0.7, 4.3, 6, 10, 1),
    "8": (1, 2.6, "M5", 0.8, 5.3, 8, 12, 1.2),
    "10": (1.2, 3, "M6", 1, 6.4, 10, 16, 1.2),
    "12": (1.6, 3.8, "M6", 1, 6.4, 12, 20, 1.2),
    "16": (2, 4.6, "M8", 1.25, 8.4, 16, 25, 1.5),
    "20": (2.5, 6, "M10", 1.5, 10.5, 18, 28, 1.5),
    "25": (3, 6, "M16", 2, 17, 24, 35, 2),
    "30": (4, 7, "M20", 2.5, 21, 30, 40, 2),
    "40": (5, 8, "M20", 2.5, 21, 30, 40, 2.5),
    "50": (6.3, 10, "M24", 3, 25, 36, 50, 2.5),
}
# Commercial length ranges (DIN EN ISO 8735 via fasten.it).
RANGES = {"6": (16, 60), "8": (18, 80), "10": (22, 100), "12": (26, 120),
          "16": (32, 160), "20": (40, 200), "25": (50, 200), "30": (60, 200),
          "40": (80, 200), "50": (100, 200)}


# ------------------------------------------------------------------ data


def test_table():
    for s, pd in SIZES.items():
        assert (pd.a, pd.c, pd.thread, pd.P, pd.d3, pd.t1, pd.t2, pd.t3) == TABLE[s]
        assert (pd.l_min, pd.l_max) == RANGES[s]
        assert float(pd.size) == pd.d1
        assert pd.thread == f"M{pd.D:g}"
        assert pd.l_min in LENGTH_SERIES and pd.l_max in LENGTH_SERIES


def test_table_is_consistent():
    for pd in SIZES.values():
        R = pd.d1 / 2
        thread = MetricThread(pd.D, pd.P)
        # The counterbore clears the thread and the thread's outer ridge
        # overlap (0.05 P), and stays inside the threaded-end chamfer.
        assert pd.D / 2 + 0.05 * pd.P < pd.d3 / 2 < R - pd.a * TAN_CH
        assert pd.t3 < pd.t1 < pd.t2
        # The modeled thread's bore at D ends above the drilled depth.
        z_b = bore_bottom_z(pd, thread)
        assert z_b - (pd.D - thread.d1) / 2 > -pd.t2
        # The shortest pin keeps material between the drill point and the
        # far-end chamfer.
        assert pd.l_min - pd.c + drill_tip_z(pd, thread.d1 / 2) > 0.02 * pd.d1
        # The venting flat stays clear of the counterbore.
        assert R - vent_depth(pd) > pd.d3 / 2 + 0.1 * pd.d1


def test_crown():
    for pd in SIZES.values():
        x, rho, h = crown(pd)
        assert x + h == pytest.approx(pd.c, abs=1e-9)
        assert rho == pytest.approx(pd.d1 / 2 - x * TAN_CH)
        # The crown base lies on the sphere of radius d1 through the apex.
        assert (pd.d1 - h) ** 2 + rho**2 == pytest.approx(pd.d1**2)
        # Both parts are real: the crown starts on the chamfer, inside d1.
        assert h > 0.05 * pd.c and x > 0.05 * pd.c and rho < pd.d1 / 2


# -------------------------------------------------------------- geometry


def independent_volume_b(pd, l):
    """Simplified type B, computed directly: cylinder with two chamfer
    frusta minus counterbore, countersink, bore at D1 and drill point."""
    R = pd.d1 / 2
    r1 = MetricThread(pd.D, pd.P).d1 / 2
    frustum = lambda h, a, b: math.pi * h / 3 * (a * a + a * b + b * b)  # noqa: E731
    outer = (math.pi * R * R * (l - pd.a - pd.c)
             + frustum(pd.a, R, R - pd.a * TAN_CH) + frustum(pd.c, R, R - pd.c * TAN_CH))
    r3 = pd.d3 / 2
    h_cs = (r3 - r1) / math.tan(math.radians(60))
    h_dr = r1 / math.tan(math.radians(60))
    hole = (math.pi * r3 * r3 * pd.t3 + frustum(h_cs, r3, r1)
            + math.pi * r1 * r1 * (pd.t2 - pd.t3 - h_cs) + frustum(h_dr, r1, 0))
    return outer - hole


def check_pin(size, l, pin_type, mode, vent="none"):
    """Build one pin and check it; returns the part. Used by the tests and
    by the full sweep script."""
    pd = SIZES[size]
    p = PIN.validate({"size": size, "length": l, "type": pin_type, "thread": mode,
                      "vent": vent})
    part = PIN.build(p)
    assert part.label == PIN.designation(p)
    assert part.is_valid
    assert len(part.solids()) == 1
    R = pd.d1 / 2
    bb = part.bounding_box()
    tol = 1e-4 * pd.d1
    assert bb.min.Z == pytest.approx(-l, abs=tol)
    assert bb.max.Z == pytest.approx(0, abs=tol)
    assert bb.size.Y == pytest.approx(pd.d1, abs=tol)
    x_max = R - vent_depth(pd) if vent == "flat" else R
    assert bb.max.X == pytest.approx(x_max, abs=tol)
    assert bb.min.X == pytest.approx(-R, abs=tol)
    expected = expected_volume(pd, l, pin_type, mode, vent)
    rel = 1e-6 if mode == "simplified" and vent == "none" else 1e-3
    assert part.volume == pytest.approx(expected, rel=rel)

    thread = MetricThread(pd.D, pd.P)
    r1 = thread.d1 / 2
    inside = lambda r, z, y=0.0: part.is_inside(Vector(r, y, z))  # noqa: E731
    # Counterbore empty, wall around it solid.
    assert not inside(0.98 * pd.d3 / 2, -pd.t3 / 2)
    assert inside(pd.d3 / 2 + 0.02 * pd.d1, -pd.t3 / 2, y=0.0)
    # Drilled hole empty down to t2, solid on the axis below the drill point.
    assert not inside(0, -(pd.t1 + pd.t2) / 2)
    assert not inside(0.9 * r1, -pd.t2 + 0.05 * pd.P)
    z_tip = drill_tip_z(pd, r1)
    assert inside(0, (z_tip - l + pd.c) / 2)
    if vent == "none":
        assert inside(0.95 * R, -l / 2)
    assert inside(-0.95 * R, -l / 2)
    # Thread region: between D1 and D at mid thread depth.
    zs = [-pd.t1 / 2 + k * pd.P / 8 for k in range(8)]
    r_mid = (r1 + pd.D / 2) / 2
    hits = [inside(-r_mid, z) for z in zs]
    if mode == "simplified":
        assert all(hits)
    else:
        assert any(hits) and not all(hits)
        # Below the runout the thread is gone: plain bore at D.
        assert not inside(-0.99 * pd.D / 2, bore_bottom_z(pd, thread) + 0.05 * pd.P)
    # Far end: crown apex (type A) or flat face (type B).
    if pin_type == "A":
        assert inside(0, -l + 0.001 * pd.d1)
        _, rho, h = crown(pd)
        assert not inside(-0.99 * rho, -l + 0.2 * h)
    else:
        r_end = R - pd.c * TAN_CH
        assert inside(-0.98 * r_end, -l + 0.001 * pd.d1)
        assert not inside(-(r_end + R) / 2, -l + 0.1 * pd.c)
    if vent == "flat":
        assert not inside(R - 0.5 * vent_depth(pd), -l / 2)
        assert inside(R - 1.5 * vent_depth(pd), -l / 2)
    return part


@pytest.mark.parametrize("size", list(SIZES))
def test_every_length_simplified(size):
    pd = SIZES[size]
    lengths = pd.standard_lengths()
    for l in lengths:
        check_pin(size, l, "A", "simplified")
    for l in (lengths[0], lengths[-1]):
        part = check_pin(size, l, "B", "simplified")
        assert part.volume == pytest.approx(independent_volume_b(pd, l), rel=1e-6)
    check_pin(size, lengths[0], "B", "simplified", "flat")


# One modeled pin per size, alternating type and vent.
MODELED = [("6", 16, "A", "none"), ("8", 18, "B", "flat"), ("10", 40, "A", "flat"),
           ("12", 26, "B", "none"), ("16", 32, "A", "none"), ("20", 200, "B", "none"),
           ("25", 50, "A", "flat"), ("30", 60, "B", "none"), ("40", 80, "A", "none"),
           ("50", 100, "B", "flat")]


@pytest.mark.parametrize("size,l,pin_type,vent", MODELED)
def test_modeled(size, l, pin_type, vent):
    part = check_pin(size, l, pin_type, "modeled", vent)
    pd = SIZES[size]
    # The ridge adds material inside the bore at D: the modeled pin is
    # lighter than the simplified one (bore at D1) but not by much.
    plain = expected_volume(pd, l, pin_type, "simplified", vent)
    assert part.volume < plain
    thread_len = pd.t1 - pd.t3
    ring = math.pi * ((pd.D / 2) ** 2 - (MetricThread(pd.D, pd.P).d1 / 2) ** 2)
    assert plain - part.volume < 0.75 * ring * (thread_len + 3 * pd.P)


def test_step_roundtrip():
    part = PIN.build(PIN.validate({"size": "8", "length": 30, "thread": "modeled"}))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "pin.stp"
        export_step(part, path)
        assert b"ISO 8735 - 8 x 30 - A" in path.read_bytes()
        imported = import_step(path)
    assert imported.is_valid
    assert imported.volume == pytest.approx(part.volume, rel=1e-4)


# ---------------------------------------------------------- API surface


def test_api_surface():
    assert PIN.id == "iso8735" and PIN.category == "Pins"
    params = {p.name: p for p in PIN.parameters()}
    assert set(params) == {"size", "length", "type", "thread", "vent"}
    assert {p.kind for p in params.values()} <= {"select", "length"}
    for s, pd in SIZES.items():
        assert params["length"].preferred[s] == pd.standard_lengths()
        assert params["length"].limits[s] == [pd.l_min, pd.l_max]
    assert [o.value for o in params["type"].options] == ["A", "B"]
    assert [o.value for o in params["thread"].options] == ["simplified", "modeled"]
    assert [o.value for o in params["vent"].options] == ["none", "flat"]
    assert PIN.describe_json()["parameters"]
    p = PIN.validate({})
    assert p == {"size": "10", "length": 40, "type": "A", "thread": "simplified",
                 "vent": "none"}
    assert PIN.designation(p) == "ISO 8735 - 10 x 40 - A"
    assert PIN.file_stem(p) == "ISO8735_10x40_A"
    p = PIN.validate({"size": "6", "length": "16", "type": "b", "thread": "modeled",
                      "vent": "flat"})
    assert PIN.designation(p) == "ISO 8735 - 6 x 16 - B"
    assert PIN.file_stem(p) == "ISO8735_6x16_B_threaded_vent"
    dims = {d.symbol: d.value for d in PIN.dimensions(p)}
    assert dims["d2"] == "M4" and dims["t1"] == 6 and dims["t2 min"] == 10
    assert dims["d3"] == 4.3 and dims["t3"] == 1 and dims["f"] == vent_depth(SIZES["6"])
    assert "r" not in dims
    dims = {d.symbol: d.value for d in PIN.dimensions(PIN.validate({}))}
    assert dims["r"] == 10 and "f" not in dims
    notes = PIN.notes(p)
    assert any("Type B" in n for n in notes) and any("Venting flat" in n for n in notes)
    assert any("modeled" in n for n in notes)


@pytest.mark.parametrize(
    "raw",
    [
        {"size": "7", "length": 20},
        {"size": "6", "length": 15},
        {"size": "6", "length": 61},
        {"size": "6", "length": "x"},
        {"size": "6", "length": "inf"},
        {"size": "6", "length": 20, "type": "C"},
        {"size": "6", "length": 20, "thread": "fancy"},
        {"size": "6", "length": 20, "vent": "groove"},
    ],
)
def test_validation_rejects(raw):
    with pytest.raises(ParameterError):
        PIN.validate(raw)


def test_custom_length_is_flagged():
    p = PIN.validate({"size": "6", "length": 21})
    assert any("not a preferred length" in n for n in PIN.notes(p))

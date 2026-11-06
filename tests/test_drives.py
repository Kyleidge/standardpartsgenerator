import math

import pytest
from build123d import Box, Pos, Vector

from standardparts.drives import (
    FLANK_ANGLE,
    H_RECESSES,
    HEXALOBULAR,
    RIB_RADIUS,
    Z_RECESSES,
    checked_cut,
    cross_geometry,
    cross_recess,
    hexalobular_depth_total,
    hexalobular_face,
    hexalobular_recess,
    hexalobular_ri,
)
from standardparts.standards.iso7045_data import SIZES as PAN
from standardparts.standards.iso7046_data import SIZES as CSK

TAN_FLANK = math.tan(math.radians(FLANK_ANGLE))

# ISO 10664:2005 Table 3, GO gauge limits (A, B, Ri, Re as (min, max)).
GO_GAUGE = {
    6: ((1.695, 1.709), (1.210, 1.224), (0.371, 0.396), (0.130, 0.134)),
    10: ((2.761, 2.776), (1.979, 1.993), (0.585, 0.609), (0.227, 0.231)),
    20: ((3.879, 3.893), (2.764, 2.778), (0.846, 0.871), (0.303, 0.307)),
    30: ((5.543, 5.557), (3.958, 3.972), (1.182, 1.206), (0.448, 0.454)),
    50: ((8.857, 8.872), (6.366, 6.380), (1.804, 1.828), (0.773, 0.777)),
}


def mean(rng):
    return sum(rng) / 2


def cross_cases():
    """(standard, size, kind, recess No., m, mean penetration, p min, p max)."""
    for name, table in (("7045", PAN), ("7046", CSK)):
        for size, sd in table.items():
            for kind in "HZ":
                m, p_min, p_max = sd.recess(kind)
                yield name, size, kind, sd.recess_no, m, (p_min + p_max) / 2, p_min, p_max


CROSS = list(cross_cases())
CROSS_IDS = [f"{c[0]}-{c[1]}-{c[2]}" for c in CROSS]


# --- hexalobular -----------------------------------------------------------------

@pytest.mark.parametrize("no", list(GO_GAUGE))
def test_hexalobular_tangency_reproduces_go_gauge(no):
    A, B, Ri, Re = (mean(r) for r in GO_GAUGE[no])
    assert hexalobular_ri(A, B, Re) == pytest.approx(Ri, abs=0.003)


@pytest.mark.parametrize("no", list(HEXALOBULAR))
def test_hexalobular_data(no):
    h = HEXALOBULAR[no]
    assert h.B < h.A
    assert 0 < h.Re < h.Ri < h.B / 2
    if no in GO_GAUGE:
        # The socket is a little larger than the GO gauge.
        assert h.A >= GO_GAUGE[no][0][1] and h.B >= GO_GAUGE[no][1][1]
        assert GO_GAUGE[no][3][0] <= h.Re <= GO_GAUGE[no][3][1]


@pytest.mark.parametrize("no", list(HEXALOBULAR))
def test_hexalobular_tool(no):
    h = HEXALOBULAR[no]
    depth = 0.3 * h.A
    face = hexalobular_face(h)
    assert face.is_valid
    tool = hexalobular_recess(no, depth, z_ref=1.0)
    assert tool.is_valid and len(tool.solids()) == 1
    bb = tool.bounding_box()
    assert bb.size.X == pytest.approx(h.A, abs=1e-3)
    assert bb.min.Z == pytest.approx(1.0 - hexalobular_depth_total(no, depth), abs=1e-3)
    z = 1.0 - depth / 2
    for k in range(6):
        a = math.radians(60 * k)
        ai = a + math.pi / 6
        assert tool.is_inside(Vector((h.A / 2 - 0.01) * math.cos(a), (h.A / 2 - 0.01) * math.sin(a), z))
        assert not tool.is_inside(Vector((h.A / 2 + 0.01) * math.cos(a), (h.A / 2 + 0.01) * math.sin(a), z))
        assert tool.is_inside(Vector((h.B / 2 - 0.01) * math.cos(ai), (h.B / 2 - 0.01) * math.sin(ai), z))
        assert not tool.is_inside(Vector((h.B / 2 + 0.01) * math.cos(ai), (h.B / 2 + 0.01) * math.sin(ai), z))
    # Prism of the contour plus the cone bottom.
    prism = face.area * (depth + 0.1 * h.A)
    assert prism < tool.volume < prism * 1.25


# --- cross recesses -----------------------------------------------------------------

@pytest.mark.parametrize("case", CROSS, ids=CROSS_IDS)
def test_cross_model_matches_recess_data(case):
    _, _, kind, no, m, p, p_min, p_max = case
    cg = cross_geometry(m, p)
    rec = H_RECESSES[no] if kind == "H" else Z_RECESSES[no]
    # With m and the penetration fixed, the diameter at the bottom of the
    # flanks stays close to the ISO 4757 gauge diameter g ...
    assert cg.g_eff == pytest.approx(rec.g, rel=0.16)
    # ... and the recess is deep enough for the gauge at p max.
    assert cg.t_total > p_max
    if kind == "H":
        assert rec.b < cg.g_eff
        assert rec.t1 == pytest.approx(rec.g / 2 * math.tan(math.radians(28)), abs=0.01)


def wing_half_width(tool, x, z, limit):
    if not tool.is_inside(Vector(x, 0, z)):
        return 0.0
    lo, hi = 0.0, limit
    for _ in range(25):
        mid = (lo + hi) / 2
        if tool.is_inside(Vector(x, mid, z)):
            lo = mid
        else:
            hi = mid
    return lo


# One case per recess number and type.
SAMPLE = [c for c in CROSS if c[0] == "7045" and c[1] in ("M2", "M3", "M4", "M6", "M10")]


@pytest.mark.parametrize("case", SAMPLE, ids=[f"{c[1]}-{c[2]}" for c in SAMPLE])
def test_cross_tool_geometry(case):
    _, _, kind, no, m, p, _, _ = case
    cg = cross_geometry(m, p)
    tool = cross_recess(kind, no, m, p, z_ref=2.0, h_up=0.5)
    assert tool.is_valid and len(tool.solids()) == 1
    bb = tool.bounding_box()
    assert bb.min.Z == pytest.approx(2.0 - cg.t_total, abs=1e-3)
    assert bb.max.Z == pytest.approx(2.5, abs=1e-6)
    # Wings along X and Y reach m / 2 at the reference plane.
    for a in (0, 90, 180, 270):
        c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
        r_in, r_out = m / 2 - 0.02 * m, m / 2 + 0.02 * m
        assert tool.is_inside(Vector(r_in * c, r_in * s, 2.0 - 0.01))
        assert not tool.is_inside(Vector(r_out * c, r_out * s, 2.0 - 0.01))
    # Flanks at 26.5 deg: at half the penetration the wing ends at
    # m / 2 - (p / 2) tan 26.5.
    z = 2.0 - p / 2
    r_fl = m / 2 - p / 2 * TAN_FLANK
    assert tool.is_inside(Vector(r_fl - 0.02 * m, 0, z))
    assert not tool.is_inside(Vector(r_fl + 0.02 * m, 0, z))
    if kind == "H":
        # Material between the wings on the diagonal, outside the core.
        d = 0.45 * m / math.sqrt(2)
        assert not tool.is_inside(Vector(d, d, 2.0 - 0.3 * p))
        rec = H_RECESSES[no]
        # Wing width near the bottom of the flanks is ISO 4757 f.
        z = 2.0 - 0.9 * p
        x = m / 2 - 0.9 * p * TAN_FLANK - 0.02 * m
        w = 2 * wing_half_width(tool, x, z, m)
        assert rec.f_min - 0.05 <= w <= rec.f_max + 0.05
        # Wings get wider towards the top (corner lean beta).
        w_top = 2 * wing_half_width(tool, m / 2 - 0.02 * m, 2.0 - 1e-3, m)
        assert w_top > w
        # Corners: material on the diagonal just outside the core b.
        assert not tool.is_inside(Vector(*(2 * [(rec.b / 2 + 0.25 * m) / math.sqrt(2)]), z))
    else:
        rec = Z_RECESSES[no]
        z = 2.0 - 0.3 * p
        x = 0.5 * (rec.g / 2 + m / 2 - 0.3 * p * TAN_FLANK)
        w = 2 * wing_half_width(tool, x, z, m)
        assert w == pytest.approx(rec.f, abs=2e-3)
        # Central cone of diameter g at the reference plane: between each
        # wing and rib there is an arc of it, with material just outside.
        r_in, r_out = rec.g / 2 * 0.97, rec.g / 2 * 1.05
        gap = [
            a for a in range(1, 45)
            if not tool.is_inside(Vector(r_out * math.cos(math.radians(a)),
                                         r_out * math.sin(math.radians(a)), 2.0 - 0.01))
        ]
        assert len(gap) >= 2
        for a in gap:
            a = math.radians(a)
            assert tool.is_inside(Vector(r_in * math.cos(a), r_in * math.sin(a), 2.0 - 0.01))
        # Ribs on the diagonals run out at RIB_RADIUS * m.
        a = math.radians(45)
        r = (m / 2 + RIB_RADIUS * m) / 2
        assert tool.is_inside(Vector(r * math.cos(a), r * math.sin(a), 2.0 - 0.005))
        r = RIB_RADIUS * m + 0.02 * m
        assert not tool.is_inside(Vector(r * math.cos(a), r * math.sin(a), 2.0 - 0.005))


def test_cross_tool_rejects_bad_input():
    with pytest.raises(ValueError):
        cross_recess("X", 2, 4.4, 2.15)
    with pytest.raises(ValueError):
        cross_recess("H", 2, 4.4, 5.0)   # deeper than the flanks allow


# --- checked cut ---------------------------------------------------------------------

def test_checked_cut_verifies_volume():
    body = Pos(0, 0, -5) * Box(10, 10, 10)
    tool = hexalobular_recess(20, 1.5)
    cut = checked_cut(body, tool, body, "box")
    assert body.volume - cut.volume == pytest.approx((tool & body).volume, rel=1e-6)
    # A reference that disagrees with the body is caught.
    taller = Pos(0, 0, -4) * Box(10, 10, 10)
    with pytest.raises(RuntimeError):
        checked_cut(body, tool, taller, "box")
    # A tool that misses the part is caught.
    with pytest.raises(RuntimeError):
        checked_cut(body, Pos(0, 0, 20) * tool, body, "box")

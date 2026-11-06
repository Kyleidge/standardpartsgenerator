"""Dimension table for ISO 4035, hexagon thin nuts (style 0, chamfered).

Sources:

* M5 to M39 (including the non-preferred M7, added in the 2023 edition):
  ISO 4035:2023 Tables 1 and 2. These give da max, dw min and mw min to
  two decimals.
* M1.6 to M4 (with M3.5) and M42 to M64: ISO 4035:2023 moved these sizes
  to its normative Annex A, whose values are not included here. Their
  values come from ISO 4035:2012 Tables 1 and 2, which agree with ISO
  4035:1999 Tables 1 and 2 on every value. For M5 to M39 the 2023 edition
  raised dw min (e.g. M5: 6.9 to 7.20) and lowered mw min slightly (M5:
  2.0 to 1.96), so the Annex A values for M1.6 to M4 may differ a little
  from the 2012 values here. dw only places the bearing-face chamfer and
  mw is only checked, not modeled.
* Cross-check: m max and s for M1.6 to M52 match the ISO 4035 columns of
  bd_warehouse's hex_nut_parameters.csv. fasten.it's DIN EN ISO 4035 page
  agrees on e min, m and s for the sizes it lists, except e min of M48
  (83.91 there; 82.6 in ISO 4035:1999 and 2012, which is 1.13 s min as
  ISO 4759-1 requires, so the ISO value is kept).

e is not stored as a model value: the model uses the exact hexagon across
corners e = s / cos 30 deg. e min from the standard is kept for the
dimension table.

All values are in millimetres. The field names say which limit a value is
(``m_max``, ``dw_min``, ...). da min is always D.
"""

from __future__ import annotations

from dataclasses import dataclass

# Countersink at both bore ends: ISO 4035:2023 Figure 1 allows 110 to
# 120 deg (90 to 120 deg in the 2012 edition).
COUNTERSINK_ANGLE = 120.0
# Corner chamfer on both faces: ISO 4035 Figure 1 allows 15 to 30 deg.
# 15 deg is used so the full-width corners keep at least mw min of height
# on every size (at 30 deg, a thin nut's corners drop below mw min).
CHAMFER_ANGLE = 15.0


@dataclass(frozen=True)
class SizeData:
    size: str          # designation, e.g. "M8"
    D: float           # nominal thread diameter
    P: float           # coarse thread pitch
    da_max: float      # countersink diameter on the faces
    dw_min: float      # bearing face diameter
    e_min: float       # width across corners
    m_max: float       # nut height
    m_min: float
    mw_min: float      # wrenching height
    s_max: float       # width across flats (s nom = s max)
    s_min: float
    preferred: bool    # False for the sizes the standard puts in brackets
    edition: str       # edition the row is taken from

    @property
    def da_min(self) -> float:
        return self.D

    @property
    def s_nom(self) -> float:
        return self.s_max

    @property
    def e_nom(self) -> float:
        """Across corners of the exact hexagon of width s nom."""
        return self.s_nom * 2 / 3**0.5

    @property
    def in_annex(self) -> bool:
        """Sizes ISO 4035:2023 lists only in its Annex A."""
        return not 5 <= self.D <= 39


def _row(size, P, da_max, dw_min, e_min, m_max, m_min, mw_min, s_max, s_min,
         preferred=True, edition="2023"):
    return SizeData(size, float(size[1:]), P, da_max, dw_min, e_min, m_max, m_min,
                    mw_min, s_max, s_min, preferred, edition)


_ROWS = [
    #     size    P     da max  dw min  e min   m max  m min  mw min  s max  s min
    _row("M1.6", 0.35, 1.84,   2.40,   3.41,   1.00,  0.75,  0.60,   3.20,  3.02, edition="2012"),
    _row("M2",   0.4,  2.30,   3.10,   4.32,   1.20,  0.95,  0.80,   4.00,  3.82, edition="2012"),
    _row("M2.5", 0.45, 2.90,   4.10,   5.45,   1.60,  1.35,  1.10,   5.00,  4.82, edition="2012"),
    _row("M3",   0.5,  3.45,   4.60,   6.01,   1.80,  1.55,  1.20,   5.50,  5.32, edition="2012"),
    _row("M3.5", 0.6,  4.00,   5.10,   6.58,   2.00,  1.75,  1.40,   6.00,  5.82, False, "2012"),
    _row("M4",   0.7,  4.60,   5.90,   7.66,   2.20,  1.95,  1.60,   7.00,  6.78, edition="2012"),
    _row("M5",   0.8,  5.75,   7.20,   8.79,   2.70,  2.45,  1.96,   8.00,  7.78),
    _row("M6",   1.0,  6.75,   8.88,   11.05,  3.20,  2.90,  2.32,   10.00, 9.78),
    _row("M7",   1.0,  7.75,   9.63,   12.12,  3.70,  3.40,  2.72,   11.00, 10.73, False),
    _row("M8",   1.25, 8.75,   11.63,  14.38,  4.00,  3.70,  2.96,   13.00, 12.73),
    _row("M10",  1.5,  10.80,  14.63,  17.77,  5.00,  4.70,  3.76,   16.00, 15.73),
    _row("M12",  1.75, 12.96,  16.63,  20.03,  6.00,  5.70,  4.56,   18.00, 17.73),
    _row("M14",  2.0,  15.12,  19.64,  23.36,  7.00,  6.42,  5.14,   21.00, 20.67, False),
    _row("M16",  2.0,  17.28,  22.49,  26.75,  8.00,  7.42,  5.94,   24.00, 23.67),
    _row("M18",  2.5,  19.44,  24.85,  29.56,  9.00,  8.42,  6.74,   27.00, 26.16, False),
    _row("M20",  2.5,  21.60,  27.70,  32.95,  10.00, 9.10,  7.28,   30.00, 29.16),
    _row("M22",  2.5,  23.76,  31.35,  37.29,  11.00, 9.90,  7.92,   34.00, 33.00, False),
    _row("M24",  3.0,  25.92,  33.25,  39.55,  12.00, 10.90, 8.72,   36.00, 35.00),
    _row("M27",  3.0,  29.16,  38.00,  45.20,  13.50, 12.40, 9.92,   41.00, 40.00, False),
    _row("M30",  3.5,  32.40,  42.75,  50.85,  15.00, 13.90, 11.12,  46.00, 45.00),
    _row("M33",  3.5,  35.64,  46.55,  55.37,  16.50, 15.40, 12.32,  50.00, 49.00, False),
    _row("M36",  4.0,  38.88,  51.11,  60.79,  18.00, 16.90, 13.52,  55.00, 53.80),
    _row("M39",  4.0,  42.12,  55.86,  66.44,  19.50, 18.20, 14.56,  60.00, 58.80, False),
    _row("M42",  4.5,  45.40,  60.00,  71.30,  21.00, 19.70, 15.80,  65.00, 63.10, edition="2012"),
    _row("M45",  4.5,  48.60,  64.70,  76.95,  22.50, 21.20, 17.00,  70.00, 68.10, False, "2012"),
    _row("M48",  5.0,  51.80,  69.50,  82.60,  24.00, 22.70, 18.20,  75.00, 73.10, edition="2012"),
    _row("M52",  5.0,  56.20,  74.20,  88.25,  26.00, 24.70, 19.80,  80.00, 78.10, False, "2012"),
    _row("M56",  5.5,  60.50,  78.70,  93.56,  28.00, 26.70, 21.40,  85.00, 82.80, edition="2012"),
    _row("M60",  5.5,  64.80,  83.40,  99.21,  30.00, 28.70, 23.00,  90.00, 87.80, False, "2012"),
    _row("M64",  6.0,  69.10,  88.20,  104.86, 32.00, 30.40, 24.30,  95.00, 92.80, edition="2012"),
]

SIZES: dict[str, SizeData] = {r.size: r for r in _ROWS}

"""Dimension table for ISO 8673, hexagon regular nuts (style 1) with metric
fine pitch thread, product grades A (D <= 16) and B (D > 16).

Sources:

* M8x1 to M39x3: ISO 8673:2023 Tables 1 and 2. These give da max, dw min
  and mw min to two decimals, and add M18x2 and M22x2. The 2023 edition
  also changed which pitch is preferred: M10x1.25, M12x1.5 and M20x2 are
  now preferred and M10x1, M12x1.25 and M20x1.5 non-preferred
  (ISO 8673:2012 had it the other way round).
* M42x3 to M64x4: ISO 8673:2023 moved D > 39 to the informative Annex A
  ("historical nuts", m min < 0.8 D, heights from the withdrawn DIN 934),
  whose values are not included here. Their values come from ISO
  8673:2012 Tables 1 and 2, which give them to two decimals already.
  Preferred status for these is that of the 2012 edition.
* Cross-checks: ISO 8673:2012 Tables 1 and 2 for every size. The 2012
  edition gives the same m, m min, s, s min, e min and dw min for M8 to
  M39; only some da max differ in the second decimal (e.g. M12 13.00 vs
  12.96, M16 17.30 vs 17.28, M24 25.90 vs 25.92); the 2023 values are
  1.08 D for D >= 10. fasten.it (DIN EN ISO 8673 04-2013)
  agrees on s, e min and m max for every size.

The heights m are not reduced for fine threads: for every diameter the
2023 rows (M8 to M39) are identical to the ISO 4032:2023 coarse rows, and
the 2012 rows for M42 to M64 match ISO 4032:1999 except for the extra
decimals (dw min 59.95 vs 60.0 for M42, mw min 25.92 vs 25.9, ...). This
is checked in the tests.

e is not a model value: the model uses the exact hexagon across corners
e = s / cos 30 deg. e min is kept for the dimension table.

All values are in millimetres.
"""

from __future__ import annotations

from .iso4032_data import CHAMFER_ANGLE, COUNTERSINK_ANGLE, SizeData

__all__ = ["CHAMFER_ANGLE", "COUNTERSINK_ANGLE", "SIZES", "SizeData", "product_grade"]


def product_grade(D: float) -> str:
    """ISO 8673: grade A for D <= 16 mm, grade B above."""
    return "A" if D <= 16 else "B"


def _row(D, P, da_max, dw_min, e_min, m_max, m_min, mw_min, s_max, s_min,
         preferred, edition="2023") -> SizeData:
    size = f"M{D:g}x{P:g}"
    return SizeData(size, float(D), P, da_max, dw_min, e_min, m_max, m_min, mw_min,
                    s_max, s_min, preferred, edition, fine=True)


# Order as in ISO 8673:2023 Tables 1 and 2 (preferred pitch first).
# fmt: off
_ROWS = [
    #    D   P     da max  dw min  e min   m max  m min  mw min  s max  s min  preferred
    _row(8,  1.0,  8.75,   11.63,  14.38,  6.80,  6.44,  5.15,   13.00, 12.73, True),
    _row(10, 1.25, 10.80,  14.63,  17.77,  8.40,  8.04,  6.43,   16.00, 15.73, True),
    _row(10, 1.0,  10.80,  14.63,  17.77,  8.40,  8.04,  6.43,   16.00, 15.73, False),
    _row(12, 1.5,  12.96,  16.63,  20.03,  10.80, 10.37, 8.30,   18.00, 17.73, True),
    _row(12, 1.25, 12.96,  16.63,  20.03,  10.80, 10.37, 8.30,   18.00, 17.73, False),
    _row(14, 1.5,  15.12,  19.64,  23.36,  12.80, 12.10, 9.68,   21.00, 20.67, False),
    _row(16, 1.5,  17.28,  22.49,  26.75,  14.80, 14.10, 11.28,  24.00, 23.67, True),
    _row(18, 2.0,  19.44,  24.85,  29.56,  15.80, 15.10, 12.08,  27.00, 26.16, False),
    _row(18, 1.5,  19.44,  24.85,  29.56,  15.80, 15.10, 12.08,  27.00, 26.16, False),
    _row(20, 2.0,  21.60,  27.70,  32.95,  18.00, 16.90, 13.52,  30.00, 29.16, True),
    _row(20, 1.5,  21.60,  27.70,  32.95,  18.00, 16.90, 13.52,  30.00, 29.16, False),
    _row(22, 2.0,  23.76,  31.35,  37.29,  19.40, 18.10, 14.48,  34.00, 33.00, False),
    _row(22, 1.5,  23.76,  31.35,  37.29,  19.40, 18.10, 14.48,  34.00, 33.00, False),
    _row(24, 2.0,  25.92,  33.25,  39.55,  21.50, 20.20, 16.16,  36.00, 35.00, True),
    _row(27, 2.0,  29.16,  38.00,  45.20,  23.80, 22.50, 18.00,  41.00, 40.00, False),
    _row(30, 2.0,  32.40,  42.75,  50.85,  25.60, 24.30, 19.44,  46.00, 45.00, True),
    _row(33, 2.0,  35.64,  46.55,  55.37,  28.70, 27.40, 21.92,  50.00, 49.00, False),
    _row(36, 3.0,  38.88,  51.11,  60.79,  31.00, 29.40, 23.52,  55.00, 53.80, True),
    _row(39, 3.0,  42.12,  55.86,  66.44,  33.40, 31.80, 25.44,  60.00, 58.80, False),
    # ISO 8673:2012 (Annex A of the 2023 edition)
    _row(42, 3.0,  45.40,  59.95,  71.30,  34.00, 32.40, 25.92,  65.00, 63.10, True,  "2012"),
    _row(45, 3.0,  48.60,  64.70,  76.95,  36.00, 34.40, 27.52,  70.00, 68.10, False, "2012"),
    _row(48, 3.0,  51.80,  69.45,  82.60,  38.00, 36.40, 29.12,  75.00, 73.10, True,  "2012"),
    _row(52, 4.0,  56.20,  74.20,  88.25,  42.00, 40.40, 32.32,  80.00, 78.10, False, "2012"),
    _row(56, 4.0,  60.50,  78.66,  93.56,  45.00, 43.40, 34.72,  85.00, 82.80, True,  "2012"),
    _row(60, 4.0,  64.80,  83.41,  99.21,  48.00, 46.40, 37.12,  90.00, 87.80, False, "2012"),
    _row(64, 4.0,  69.10,  88.16,  104.86, 51.00, 49.10, 39.28,  95.00, 92.80, True,  "2012"),
]
# fmt: on

SIZES: dict[str, SizeData] = {r.size: r for r in _ROWS}

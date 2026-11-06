"""Dimension table for DIN 6885-1, parallel keys, deep (high) pattern.

All values in mm.

Sources:

* b, h, shaft-diameter range d1, shaft keyway depth t1 and hub keyway depth
  t2 (hub with back clearance): fasten.it, "DIN 6885-1 Standard Dimensions
  for Parallel keys" (DIN 6885-1:1968-08), cross-checked against
  globalfastener.com, DIN 6885 (A) - 1968 and DIN 6885-1 (A) - 2021. The
  two agree on every row. bd_warehouse's shaft_key_parameters.csv (DIN 6885,
  shafts up to 50 mm) agrees as well.
* The t1 and t2 tolerances (upper deviation, lower deviation 0) and the hub
  depth for an interference fit (``t2_tight``) come from globalfastener.com
  only. They are listed in the dimension table but not used in the model.
* Edge chamfer or rounding s (min, max) comes from ISO 773 / GB/T 1096-2003
  as published by globalfastener.com. DIN 6885-1 uses the same key
  cross-sections, but these values have not been checked against the DIN
  text.
* Length range per size (l_min, l_max): the DIN 6885-1 form B table on
  fasten.it (lengths at which the standard lists a mass). This range was
  not cross-checked against a second online source. It matches the
  commonly reprinted DIN 6885-1 tables.
* Length series: globalfastener.com's DIN 6885 length list (ends 280, 320,
  360, 400). fasten.it prints 315 and 355 in its mass table, but its masses
  for those rows were worked out for 320 and 360 (28 x 16 x 320 x 7.85e-3
  = 1125 g, listed as 1130 g), so 320 and 360 are used here.
"""

from __future__ import annotations

from dataclasses import dataclass

# Nominal lengths l (DIN 6885-1 length series).
LENGTH_SERIES: tuple[float, ...] = (
    6, 8, 10, 12, 14, 16, 18, 20, 22, 25, 28, 32, 36, 40, 45, 50, 56, 63, 70,
    80, 90, 100, 110, 125, 140, 160, 180, 200, 220, 250, 280, 320, 360, 400,
)


@dataclass(frozen=True)
class KeyData:
    b: float          # key width (h9) = keyway width
    h: float          # key height (h11, h9 for square keys)
    d_over: float     # suits shaft diameters d1 over ...
    d_to: float       # ... up to and including
    t1: float         # shaft keyway depth
    t1_tol: float     # upper deviation of t1
    t2: float         # hub keyway depth, hub with back clearance
    t2_tol: float     # upper deviation of t2
    t2_tight: float   # hub keyway depth, interference fit
    t2_tight_tol: float
    s_min: float      # key edge chamfer or rounding
    s_max: float
    l_min: float      # shortest nominal length
    l_max: float      # longest nominal length

    @property
    def size(self) -> str:
        return f"{self.b:g}x{self.h:g}"

    def standard_lengths(self) -> list[float]:
        return [l for l in LENGTH_SERIES if self.l_min <= l <= self.l_max]


# b, h, d over, d to, t1, t1 tol, t2, t2 tol, t2 tight, tol, s min, s max, l min, l max
_ROWS = [
    (2, 2, 6, 8, 1.2, 0.1, 1.0, 0.1, 0.5, 0.1, 0.16, 0.25, 6, 20),
    (3, 3, 8, 10, 1.8, 0.1, 1.4, 0.1, 0.9, 0.1, 0.16, 0.25, 6, 36),
    (4, 4, 10, 12, 2.5, 0.1, 1.8, 0.1, 1.2, 0.1, 0.16, 0.25, 8, 45),
    (5, 5, 12, 17, 3.0, 0.1, 2.3, 0.1, 1.7, 0.1, 0.25, 0.40, 10, 56),
    (6, 6, 17, 22, 3.5, 0.1, 2.8, 0.1, 2.2, 0.1, 0.25, 0.40, 14, 70),
    (8, 7, 22, 30, 4.0, 0.2, 3.3, 0.2, 2.4, 0.2, 0.25, 0.40, 18, 90),
    (10, 8, 30, 38, 5.0, 0.2, 3.3, 0.2, 2.4, 0.2, 0.40, 0.60, 22, 110),
    (12, 8, 38, 44, 5.0, 0.2, 3.3, 0.2, 2.4, 0.2, 0.40, 0.60, 28, 140),
    (14, 9, 44, 50, 5.5, 0.2, 3.8, 0.2, 2.9, 0.2, 0.40, 0.60, 36, 160),
    (16, 10, 50, 58, 6.0, 0.2, 4.3, 0.2, 3.4, 0.2, 0.40, 0.60, 45, 180),
    (18, 11, 58, 65, 7.0, 0.2, 4.4, 0.2, 3.4, 0.2, 0.40, 0.60, 50, 200),
    (20, 12, 65, 75, 7.5, 0.2, 4.9, 0.2, 3.9, 0.2, 0.60, 0.80, 56, 220),
    (22, 14, 75, 85, 9.0, 0.2, 5.4, 0.2, 4.4, 0.2, 0.60, 0.80, 63, 250),
    (25, 14, 85, 95, 9.0, 0.2, 5.4, 0.2, 4.4, 0.2, 0.60, 0.80, 70, 280),
    (28, 16, 95, 110, 10.0, 0.2, 6.4, 0.2, 5.4, 0.2, 0.60, 0.80, 80, 320),
    (32, 18, 110, 130, 11.0, 0.2, 7.4, 0.2, 6.4, 0.2, 0.60, 0.80, 90, 360),
    (36, 20, 130, 150, 12.0, 0.3, 8.4, 0.3, 7.1, 0.3, 1.00, 1.20, 100, 400),
    (40, 22, 150, 170, 13.0, 0.3, 9.4, 0.3, 8.1, 0.3, 1.00, 1.20, 110, 400),
    (45, 25, 170, 200, 15.0, 0.3, 10.4, 0.3, 9.1, 0.3, 1.00, 1.20, 125, 400),
    (50, 28, 200, 230, 17.0, 0.3, 11.4, 0.3, 10.1, 0.3, 1.00, 1.20, 140, 400),
    (56, 32, 230, 260, 20.0, 0.3, 12.4, 0.3, 11.1, 0.3, 1.60, 2.00, 160, 400),
    (63, 32, 260, 290, 20.0, 0.3, 12.4, 0.3, 11.1, 0.3, 1.60, 2.00, 180, 400),
    (70, 36, 290, 330, 22.0, 0.3, 14.4, 0.3, 13.1, 0.3, 1.60, 2.00, 200, 400),
    (80, 40, 330, 380, 25.0, 0.3, 15.4, 0.3, 14.1, 0.3, 2.50, 3.00, 220, 400),
    (90, 45, 380, 440, 28.0, 0.3, 17.4, 0.3, 16.1, 0.3, 2.50, 3.00, 250, 400),
    (100, 50, 440, 500, 31.0, 0.3, 19.5, 0.3, 18.1, 0.3, 2.50, 3.00, 280, 400),
]

SIZES: dict[str, KeyData] = {}
for _row in _ROWS:
    _k = KeyData(*(float(x) for x in _row))
    SIZES[_k.size] = _k

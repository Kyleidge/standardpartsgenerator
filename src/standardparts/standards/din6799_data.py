"""Dimension table for DIN 6799, retaining washers (E-clips) for shafts.

Dimensions in mm, weight in g per washer (the standard lists kg per 1000
pieces, which is the same number). Symbols follow DIN 6799:

* d2  groove diameter, the nominal size ("DIN 6799 - 6" fits a 6 mm groove)
* d1  shaft diameter range the washer is meant for (from - to)
* s   washer thickness
* a   opening width of the unstressed washer (between the jaw tips)
* d3  maximum external diameter when seated in a groove of nominal d2
* m   groove width (minimum; upper deviation in `m_tol`)
* n   minimum edge margin, groove to shaft end
* g   largest corner chamfer / radius allowed on the abutting part
  ("corner distance", DIN 6799 Table 2)

Sources:

* fasten.it's DIN 6799 tables for the 1981-09, 2011-04 and 2017-06
  editions (a nominal and a min, s, d3, m, n, weight).
* Westfield Fasteners' DIN 6799 product specification (Table 1 with shaft
  ranges and all tolerances, Table 2 with d3 and g, and Figure 1).
* Rotor Clip DE (DIN 6799) datasheet: all of the above plus the free outer
  diameter G (a supplier reference value, not in DIN 6799).

The three agree on every row. The 2023 edition was not checked; the
2017 edition shows the same values as 2011 and 1981 for every column
listed here. Transcription differences resolved:

* d2 = 1.5: a = 1.28 (1981, 2011, Westfield, Rotor Clip). fasten.it's 2017
  table shows 1.25, but its a min of 1.24 = 1.28 - 0.04.
* d2 = 1.2: a = 1.01. fasten.it's 1981 table shows 1.1, but its a min of
  0.97 = 1.01 - 0.04.
* d2 = 9: d3 = 18.8 (Westfield, Rotor Clip, fasten.it 2017). fasten.it's
  1981 and 2011 tables show 18.30 in one column and 18.8 in the other.
* d2 = 7: fasten.it's 2017 table shows d3 "143", a typo for 14.3.
* d2 = 1.9: shaft range 2.5 - 3 (Westfield, Rotor Clip). fasten.it's 2011
  table shows "2.5 < d1 < 5", which would overlap the next two sizes.
* d2 = 9: g = 1.6 (Rotor Clip's matching "max. corner radius/chamfer"
  column); Westfield shows 1.61, which breaks the one-decimal pattern.

Tolerances (Westfield and Rotor Clip agree): s ±0.02 up to d2 = 7 and
±0.03 from 8; a ±0.04 up to 3.2, ±0.048 for 4 to 7, ±0.058 for 8 to 10,
±0.07 for 12 to 19, ±0.084 for 24 and 30; groove d2 upper deviation 0;
groove width m lower deviation 0.

The free outer diameter `od_free` is Rotor Clip's reference value. DIN 6799
gives only the seated maximum d3, which the model uses for its outline.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClipData:
    d2: float       # groove diameter, nominal size
    d1_min: float   # shaft diameter range, from
    d1_max: float   # shaft diameter range, to
    s: float        # thickness
    s_tol: float    # ± tolerance on s
    a: float        # opening width, unstressed
    a_tol: float    # ± tolerance on a
    d3: float       # max external diameter seated in the groove
    d2_tol: float   # lower deviation of the groove diameter (upper is 0)
    m: float        # groove width, min
    m_tol: float    # upper deviation of m (lower is 0)
    n_min: float    # edge margin
    g: float        # max corner chamfer / radius on the abutting part
    weight: float   # g per washer
    od_free: float  # free outer diameter, Rotor Clip reference (not DIN)

    @property
    def size(self) -> str:
        return f"{self.d2:g}"


def _row(d2, d1a, d1b, s, a, d3, m, n, g, W, G):
    s_tol = 0.02 if d2 <= 7 else 0.03
    a_tol = (0.04 if d2 <= 3.2 else 0.048 if d2 <= 7 else 0.058 if d2 <= 10
             else 0.07 if d2 <= 19 else 0.084)
    d2_tol = (0.04 if d2 <= 0.8 else 0.06 if d2 <= 2.3 else 0.075 if d2 <= 6
              else 0.09 if d2 <= 10 else 0.11 if d2 <= 15 else 0.13)
    m_tol = 0.04 if d2 <= 1.5 else 0.05 if d2 <= 7 else 0.08
    return ClipData(d2, d1a, d1b, s, s_tol, a, a_tol, d3, d2_tol, m, m_tol, n, g, W, G)


# fmt: off
#       d2  d1 from  to      s       a      d3      m     n     g      W       G
SIZES: dict[str, ClipData] = {r.size: r for r in [
    _row(0.8,   1,   1.4,  0.2,   0.58,  2.25,  0.24,  0.4,  0.3,  0.003,  1.95),
    _row(1.2,   1.4, 2,    0.3,   1.01,  3.25,  0.34,  0.6,  0.4,  0.009,  2.90),
    _row(1.5,   2,   2.5,  0.4,   1.28,  4.25,  0.44,  0.8,  0.6,  0.021,  3.90),
    _row(1.9,   2.5, 3,    0.5,   1.61,  4.8,   0.54,  1,    0.7,  0.040,  4.40),
    _row(2.3,   3,   4,    0.6,   1.94,  6.3,   0.64,  1,    0.9,  0.069,  5.90),
    _row(3.2,   4,   5,    0.6,   2.70,  7.3,   0.64,  1,    0.9,  0.088,  6.90),
    _row(4,     5,   7,    0.7,   3.34,  9.3,   0.74,  1.2,  1.0,  0.158,  8.85),
    _row(5,     6,   8,    0.7,   4.11,  11.3,  0.74,  1.2,  1.0,  0.236,  10.85),
    _row(6,     7,   9,    0.7,   5.26,  12.3,  0.74,  1.2,  1.1,  0.255,  11.80),
    _row(7,     8,   11,   0.9,   5.84,  14.3,  0.94,  1.5,  1.3,  0.474,  13.80),
    _row(8,     9,   12,   1.0,   6.52,  16.3,  1.05,  1.8,  1.5,  0.660,  15.75),
    _row(9,     10,  14,   1.1,   7.63,  18.8,  1.15,  2,    1.6,  1.09,   18.20),
    _row(10,    11,  15,   1.2,   8.32,  20.4,  1.25,  2,    1.8,  1.25,   19.70),
    _row(12,    13,  18,   1.3,   10.45, 23.4,  1.35,  2.5,  1.9,  1.63,   22.70),
    _row(15,    16,  24,   1.5,   12.61, 29.4,  1.55,  3,    2.2,  3.37,   28.70),
    _row(19,    20,  31,   1.75,  15.92, 37.6,  1.80,  3.5,  2.5,  6.42,   36.50),
    _row(24,    25,  38,   2.0,   21.88, 44.6,  2.05,  4,    3.0,  8.55,   43.50),
    _row(30,    32,  42,   2.5,   25.80, 52.6,  2.55,  4.5,  3.5,  13.5,   51.30),
]}
# fmt: on

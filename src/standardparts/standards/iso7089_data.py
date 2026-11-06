"""Dimension tables for ISO 7089:2000 and ISO 7090:2000, plain washers,
normal series, product grade A (ISO 7090: chamfered).

Sources:

* Nominal d1, d2 and h: ISO 887:2000 Table 3, "Normal" series, product
  grade A, which marks the sizes ISO 7089 (1.6 to 64) and ISO 7090 (5 to
  64) specify. d1 nom = d1 min and d2 nom = d2 max.
* Tolerance limits (d1 max, d2 min, h max, h min): the ISO 7089 and ISO 7090
  tables published by Westfield Fasteners, which agree with ISO 887 on every
  nominal value. The ISO 7089/7090 texts themselves were not available.
  These limits are only shown in the dimension table; the model uses the
  nominal values. bd_warehouse's washer tables agree with d1 nom, d2 nom and
  h max.
  Westfield's ISO 7090 page has two typos that ISO 887 and their own ISO
  7089 page contradict (size 10: d2 21; size 36: d2 64.8); the ISO 887
  values (20, 66) are used.
* ISO 7090 chamfer: the ISO 7090 figure (as shown by fasten.it) shows a
  chamfer on the outer edge of one face, at 30 to 45 deg to the axis and
  0.25 h to 0.5 h high. The standard gives a range, not a single value; the
  model uses the middle of both ranges (CHAMFER_ANGLE, CHAMFER_HEIGHT).

All values are in millimetres.
"""

from __future__ import annotations

from dataclasses import dataclass

# ISO 7090 outer chamfer, measured from the axis direction (the outer
# cylinder), and its axial height as a fraction of h. Middle of the ranges
# 30 to 45 deg and 0.25 h to 0.5 h.
CHAMFER_ANGLE = 37.5
CHAMFER_HEIGHT = 0.375


@dataclass(frozen=True)
class WasherData:
    size: str          # nominal size = thread size, e.g. "8"
    d1_min: float      # hole diameter (d1 nom = d1 min)
    d1_max: float
    d2_max: float      # outside diameter (d2 nom = d2 max)
    d2_min: float
    h_nom: float       # thickness
    h_max: float
    h_min: float
    preferred: bool    # False for the sizes the standard puts in brackets

    @property
    def d1(self) -> float:
        return self.d1_min

    @property
    def d2(self) -> float:
        return self.d2_max

    @property
    def h(self) -> float:
        return self.h_nom

    @property
    def d(self) -> float:
        return float(self.size)


def _row(size, d1_min, d1_max, d2_max, d2_min, h, h_max, h_min, preferred=True):
    return WasherData(size, d1_min, d1_max, d2_max, d2_min, h, h_max, h_min, preferred)


_ROWS = [
    #     size   d1 min d1 max  d2 max  d2 min  h nom h max h min
    _row("1.6",  1.7,   1.84,   4.0,    3.7,    0.3,  0.35, 0.25),
    _row("2",    2.2,   2.34,   5.0,    4.7,    0.3,  0.35, 0.25),
    _row("2.5",  2.7,   2.84,   6.0,    5.7,    0.5,  0.55, 0.45),
    _row("3",    3.2,   3.38,   7.0,    6.64,   0.5,  0.55, 0.45),
    _row("3.5",  3.7,   3.88,   8.0,    7.64,   0.5,  0.55, 0.45, False),
    _row("4",    4.3,   4.48,   9.0,    8.64,   0.8,  0.9,  0.7),
    _row("5",    5.3,   5.48,   10.0,   9.64,   1.0,  1.1,  0.9),
    _row("6",    6.4,   6.62,   12.0,   11.57,  1.6,  1.8,  1.4),
    _row("8",    8.4,   8.62,   16.0,   15.57,  1.6,  1.8,  1.4),
    _row("10",   10.5,  10.77,  20.0,   19.48,  2.0,  2.2,  1.8),
    _row("12",   13.0,  13.27,  24.0,   23.48,  2.5,  2.7,  2.3),
    _row("14",   15.0,  15.27,  28.0,   27.48,  2.5,  2.7,  2.3,  False),
    _row("16",   17.0,  17.27,  30.0,   29.48,  3.0,  3.3,  2.7),
    _row("18",   19.0,  19.33,  34.0,   33.38,  3.0,  3.3,  2.7,  False),
    _row("20",   21.0,  21.33,  37.0,   36.38,  3.0,  3.3,  2.7),
    _row("22",   23.0,  23.33,  39.0,   38.38,  3.0,  3.3,  2.7,  False),
    _row("24",   25.0,  25.33,  44.0,   43.38,  4.0,  4.3,  3.7),
    _row("27",   28.0,  28.33,  50.0,   49.38,  4.0,  4.3,  3.7,  False),
    _row("30",   31.0,  31.39,  56.0,   55.26,  4.0,  4.3,  3.7),
    _row("33",   34.0,  34.62,  60.0,   58.8,   5.0,  5.6,  4.4,  False),
    _row("36",   37.0,  37.62,  66.0,   64.8,   5.0,  5.6,  4.4),
    _row("39",   42.0,  42.62,  72.0,   70.8,   6.0,  6.6,  5.4,  False),
    _row("42",   45.0,  45.62,  78.0,   76.8,   8.0,  9.0,  7.0),
    _row("45",   48.0,  48.62,  85.0,   83.6,   8.0,  9.0,  7.0,  False),
    _row("48",   52.0,  52.74,  92.0,   90.6,   8.0,  9.0,  7.0),
    _row("52",   56.0,  56.74,  98.0,   96.6,   8.0,  9.0,  7.0,  False),
    _row("56",   62.0,  62.74,  105.0,  103.6,  10.0, 11.0, 9.0),
    _row("60",   66.0,  66.74,  110.0,  108.6,  10.0, 11.0, 9.0,  False),
    _row("64",   70.0,  70.74,  115.0,  113.6,  10.0, 11.0, 9.0),
]

# ISO 7089: 1.6 to 64. ISO 7090: 5 to 64 (same dimensions, chamfered).
ISO7089_SIZES: dict[str, WasherData] = {r.size: r for r in _ROWS}
ISO7090_SIZES: dict[str, WasherData] = {r.size: r for r in _ROWS if r.d >= 5}

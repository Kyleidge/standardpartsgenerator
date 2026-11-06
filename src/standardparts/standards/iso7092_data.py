"""Dimension tables for ISO 7092:2000 (plain washers, small series, product
grade A) and ISO 7093-1:2000 (plain washers, large series, product grade A).

Sources:

* ISO 7092: ISO 7092:2000 Tables 1 (preferred) and 2 (non-preferred):
  every value (d1 nom = min, d1 max, d2 nom = max, d2 min, h nom, h max,
  h min). Sizes 1.6 to 36.
* ISO 7093-1: ISO 7093-1:2000 (corrected 2001-02-01) Tables 1 and 2: every
  value. Sizes 3 to 36.
* Cross-check: fasten.it's DIN EN ISO 7092 and DIN EN ISO 7093-1 pages
  agree on d1, d2 and h nom for every size (and on h min and d2 min for
  ISO 7093-1), except ISO 7092 size 18, where fasten.it gives h = 2.5. The
  ISO table gives 3, and fasten.it's own weight for that size (9.97 kg per
  1000) matches h = 3, so the ISO value is used.

Note that the large series does not just scale the normal series: ISO
7093-1 sizes 27, 30, 33 and 36 have larger holes (30, 33, 36, 39) than ISO
7089 (28, 31, 34, 37).

All values are in millimetres. Rows use iso7089_data.WasherData.
"""

from __future__ import annotations

from .iso7089_data import WasherData


def _row(size, d1_min, d1_max, d2_max, d2_min, h, h_max, h_min, preferred=True):
    return WasherData(size, d1_min, d1_max, d2_max, d2_min, h, h_max, h_min, preferred)


_ISO7092_ROWS = [
    #     size   d1 min d1 max  d2 max  d2 min  h nom h max h min
    _row("1.6",  1.70,  1.84,   3.5,    3.2,    0.3,  0.35, 0.25),
    _row("2",    2.20,  2.34,   4.5,    4.2,    0.3,  0.35, 0.25),
    _row("2.5",  2.70,  2.84,   5.0,    4.7,    0.5,  0.55, 0.45),
    _row("3",    3.20,  3.38,   6.0,    5.7,    0.5,  0.55, 0.45),
    _row("3.5",  3.70,  3.88,   7.0,    6.64,   0.5,  0.55, 0.45, False),
    _row("4",    4.30,  4.48,   8.0,    7.64,   0.5,  0.55, 0.45),
    _row("5",    5.30,  5.48,   9.0,    8.64,   1.0,  1.1,  0.9),
    _row("6",    6.40,  6.62,   11.0,   10.57,  1.6,  1.8,  1.4),
    _row("8",    8.40,  8.62,   15.0,   14.57,  1.6,  1.8,  1.4),
    _row("10",   10.50, 10.77,  18.0,   17.57,  1.6,  1.8,  1.4),
    _row("12",   13.00, 13.27,  20.0,   19.48,  2.0,  2.2,  1.8),
    _row("14",   15.00, 15.27,  24.0,   23.48,  2.5,  2.7,  2.3,  False),
    _row("16",   17.00, 17.27,  28.0,   27.48,  2.5,  2.7,  2.3),
    _row("18",   19.00, 19.33,  30.0,   29.48,  3.0,  3.3,  2.7,  False),
    _row("20",   21.00, 21.33,  34.0,   33.38,  3.0,  3.3,  2.7),
    _row("22",   23.00, 23.33,  37.0,   36.38,  3.0,  3.3,  2.7,  False),
    _row("24",   25.00, 25.33,  39.0,   38.38,  4.0,  4.3,  3.7),
    _row("27",   28.00, 28.33,  44.0,   43.38,  4.0,  4.3,  3.7,  False),
    _row("30",   31.00, 31.39,  50.0,   49.38,  4.0,  4.3,  3.7),
    _row("33",   34.00, 34.62,  56.0,   54.8,   5.0,  5.6,  4.4,  False),
    _row("36",   37.00, 37.62,  60.0,   58.8,   5.0,  5.6,  4.4),
]

_ISO7093_ROWS = [
    #     size   d1 min d1 max  d2 max  d2 min  h nom h max h min
    _row("3",    3.20,  3.38,   9.0,    8.64,   0.8,  0.9,  0.7),
    _row("3.5",  3.70,  3.88,   11.0,   10.57,  0.8,  0.9,  0.7,  False),
    _row("4",    4.30,  4.48,   12.0,   11.57,  1.0,  1.1,  0.9),
    _row("5",    5.30,  5.48,   15.0,   14.57,  1.0,  1.1,  0.9),
    _row("6",    6.40,  6.62,   18.0,   17.57,  1.6,  1.8,  1.4),
    _row("8",    8.40,  8.62,   24.0,   23.48,  2.0,  2.2,  1.8),
    _row("10",   10.50, 10.77,  30.0,   29.48,  2.5,  2.7,  2.3),
    _row("12",   13.00, 13.27,  37.0,   36.38,  3.0,  3.3,  2.7),
    _row("14",   15.00, 15.27,  44.0,   43.38,  3.0,  3.3,  2.7,  False),
    _row("16",   17.00, 17.27,  50.0,   49.38,  3.0,  3.3,  2.7),
    _row("18",   19.00, 19.33,  56.0,   55.26,  4.0,  4.3,  3.7,  False),
    _row("20",   21.00, 21.33,  60.0,   59.26,  4.0,  4.3,  3.7),
    _row("22",   23.00, 23.52,  66.0,   64.8,   5.0,  5.6,  4.4,  False),
    _row("24",   25.00, 25.52,  72.0,   70.8,   5.0,  5.6,  4.4),
    _row("27",   30.00, 30.52,  85.0,   83.6,   6.0,  6.6,  5.4,  False),
    _row("30",   33.00, 33.62,  92.0,   90.6,   6.0,  6.6,  5.4),
    _row("33",   36.00, 36.62,  105.0,  103.6,  6.0,  6.6,  5.4,  False),
    _row("36",   39.00, 39.62,  110.0,  108.6,  8.0,  9.0,  7.0),
]

ISO7092_SIZES: dict[str, WasherData] = {r.size: r for r in _ISO7092_ROWS}
ISO7093_SIZES: dict[str, WasherData] = {r.size: r for r in _ISO7093_ROWS}

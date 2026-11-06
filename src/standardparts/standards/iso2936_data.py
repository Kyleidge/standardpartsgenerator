"""Dimension table for ISO 2936:2014, hexagon socket screw keys (L-shaped
hex keys, "Allen keys").

Sources:

* ISO 2936:2014 Table 1 and Figure 1. Every value below is from Table 1.
* Cross-checks (tested): e max = 1.14 s max - 0.03 for 1.5 <= s <= 36 and
  e min = 1.13 s min for 8 <= s <= 36 (Table 1, footnote a), and the l1 / l2
  limit-deviation groups.

Figure 1 fixes the shape:

* The lengths l1 (long arm) and l2 (short arm) are measured to the outside
  of the other arm. Their limit deviations are 0 / -x, so the tabulated
  values are maximum lengths; the model uses them.
* The cross-section is a hexagon s whose corners may be sharp, rounded or
  chamfered within e. Two flats lie in the plane of the bend (the bend is
  "flat on the inside").
* The inner bend radius r is at least s and at least 1.5 mm. The arms are at
  90 deg (+2 / -1 deg; +3 / -1 deg above s = 17).
* Each end is square to its arm within 1 deg. Its edge may be sharp, rounded
  or chamfered by at most f max = (e max - s min) / 2.

Designation: "Socket screw key ISO 2936 - 10" (ISO 2936:1995 clause 5; not
checked against the 2014 edition). The suffixes M (long) and L (extra-long)
are from a third-party summary of the 2014 edition and were not checked
against the standard's text.

All values are in millimetres.
"""

from __future__ import annotations

from dataclasses import dataclass

SERIES = ("standard", "long", "extra-long")
# Designation suffix of each series (ISO 2936: M = long, L = extra-long).
SERIES_SUFFIX = {"standard": "", "long": "M", "extra-long": "L"}

MIN_BEND_RADIUS = 1.5  # r >= s, and never below 1.5 mm (Figure 1, footnote b)


@dataclass(frozen=True)
class KeyData:
    size: str              # designation of s, e.g. "10" or "2.5"
    s_max: float           # width across flats (= nominal from 1.5 up)
    s_min: float
    e_max: float           # width across corners
    e_min: float
    l1: dict[str, float]   # long arm per available series (maximum lengths)
    l1_dev: float          # lower limit deviation of l1 (upper is 0)
    l2: float              # short arm (maximum length)
    l2_dev: float          # lower limit deviation of l2 (upper is 0)

    @property
    def s(self) -> float:
        return self.s_max

    @property
    def bend_radius(self) -> float:
        """Inner bend radius used by the model: the smallest allowed."""
        return max(self.s_max, MIN_BEND_RADIUS)

    @property
    def f_max(self) -> float:
        """Largest end chamfer or radius allowed (Figure 1, footnote a)."""
        return (self.e_max - self.s_min) / 2


def _row(size: str, s_max: float, s_min: float, e_max: float, e_min: float,
         standard: float, long: float | None, extra: float | None, l1_dev: float,
         l2: float, l2_dev: float) -> KeyData:
    l1 = {"standard": standard}
    if long is not None:
        l1["long"] = long
    if extra is not None:
        l1["extra-long"] = extra
    return KeyData(size, s_max, s_min, e_max, e_min, l1, l1_dev, l2, l2_dev)


# fmt: off
SIZES: dict[str, KeyData] = {k.size: k for k in [
    #     s      max    min    e max  e min  l1 std long   extra  dev  l2    dev
    _row("0.7", 0.71,  0.70,  0.79,  0.76,  33,    None,  None,  -2, 7,    -2),
    _row("0.9", 0.89,  0.88,  0.99,  0.96,  33,    None,  None,  -2, 11,   -2),
    _row("1.3", 1.27,  1.24,  1.42,  1.37,  41,    63.5,  81,    -2, 13,   -2),
    _row("1.5", 1.50,  1.48,  1.68,  1.63,  46.5,  63.5,  91.5,  -2, 15.5, -2),
    _row("2",   2.00,  1.96,  2.25,  2.18,  52,    77,    102,   -2, 18,   -2),
    _row("2.5", 2.50,  2.46,  2.82,  2.75,  58.5,  87.5,  114.5, -4, 20.5, -2),
    _row("3",   3.00,  2.96,  3.39,  3.31,  66,    93,    129,   -4, 23,   -2),
    _row("3.5", 3.50,  3.45,  3.96,  3.91,  69.5,  98.5,  140,   -4, 25.5, -2),
    _row("4",   4.00,  3.95,  4.53,  4.43,  74,    104,   144,   -4, 29,   -2),
    _row("4.5", 4.50,  4.45,  5.10,  5.04,  80,    114.5, 156,   -4, 30.5, -2),
    _row("5",   5.00,  4.95,  5.67,  5.57,  85,    120,   165,   -4, 33,   -2),
    _row("6",   6.00,  5.95,  6.81,  6.70,  96,    141,   186,   -4, 38,   -2),
    _row("7",   7.00,  6.94,  7.95,  7.85,  102,   147,   197,   -6, 41,   -2),
    _row("8",   8.00,  7.94,  9.09,  8.97,  108,   158,   208,   -6, 44,   -2),
    _row("9",   9.00,  8.94,  10.23, 10.10, 114,   169,   219,   -6, 47,   -2),
    _row("10",  10.00, 9.94,  11.37, 11.23, 122,   180,   234,   -6, 50,   -2),
    _row("11",  11.00, 10.89, 12.51, 12.31, 129,   191,   247,   -6, 53,   -2),
    _row("12",  12.00, 11.89, 13.65, 13.44, 137,   202,   262,   -6, 57,   -2),
    _row("13",  13.00, 12.89, 14.79, 14.57, 145,   213,   277,   -7, 63,   -3),
    _row("14",  14.00, 13.89, 15.93, 15.70, 154,   229,   294,   -7, 70,   -3),
    _row("15",  15.00, 14.89, 17.07, 16.83, 161,   240,   307,   -7, 73,   -3),
    _row("16",  16.00, 15.89, 18.21, 17.96, 168,   240,   307,   -7, 76,   -3),
    _row("17",  17.00, 16.89, 19.35, 19.09, 177,   262,   337,   -7, 80,   -3),
    _row("18",  18.00, 17.89, 20.49, 20.22, 188,   262,   358,   -7, 84,   -3),
    _row("19",  19.00, 18.87, 21.63, 21.32, 199,   None,  None,  -7, 89,   -3),
    _row("21",  21.00, 20.87, 23.91, 23.58, 211,   None,  None,  -12, 96,  -5),
    _row("22",  22.00, 21.87, 25.05, 24.71, 222,   None,  None,  -12, 102, -5),
    _row("23",  23.00, 22.87, 26.19, 25.84, 233,   None,  None,  -12, 108, -5),
    _row("24",  24.00, 23.87, 27.33, 26.97, 248,   None,  None,  -12, 114, -5),
    _row("27",  27.00, 26.87, 30.75, 30.36, 277,   None,  None,  -12, 127, -5),
    _row("29",  29.00, 28.87, 33.03, 32.62, 311,   None,  None,  -12, 141, -5),
    _row("30",  30.00, 29.87, 34.17, 33.75, 315,   None,  None,  -12, 142, -5),
    _row("32",  32.00, 31.84, 36.45, 35.98, 347,   None,  None,  -12, 157, -5),
    _row("36",  36.00, 35.84, 41.01, 40.50, 391,   None,  None,  -12, 176, -5),
]}
# fmt: on

"""Dimension tables for ISO 1234:1997, split pins (cotter pins).

Sources:

* ISO 1234:1997 Table 1 (d, a, b, c, corresponding bolt and clevis pin
  diameters), Table 2 (nominal lengths and the commercial length range of
  every size, the area between the bold stepped lines) and Figure 1, as
  published in SIST EN ISO 1234:2001 (identical text).
* Figure 1: b is the eye length, from the top of the eye to where the legs
  start; l is measured from there to the end of the shorter leg; the
  longer leg extends a further a; c is the outer width of the eye in the
  plane of the bend; d is the diameter of the pin (the two half-round
  legs together). "Shape of ends optional".
* Nominal size = diameter of the split pin hole (H13 for nominal size
  <= 1.2, H14 above).
* Footnote 2 of Table 1: for railway applications, or where split pins in
  clevis pins see alternating transverse forces, use the next larger size.
* Not cross-checked against a second source (fasten.it gives its ISO
  1234 table only as an image). Every value here is from the standard's
  own tables, and the tests check the table's internal consistency
  (d max > d min, c max > c min, a max = 2 a min, ranges monotonic).

Table 2 has a misprint (l = 45: max 46,6 instead of 46,5); only the
nominal lengths are used here.

All values are in millimetres.
"""

from __future__ import annotations

from dataclasses import dataclass

# Nominal lengths l of Table 2.
LENGTH_SERIES: tuple[float, ...] = (
    4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 25, 28, 32, 36, 40, 45, 50, 56,
    63, 71, 80, 90, 100, 112, 125, 140, 160, 180, 200, 224, 250, 280,
)


@dataclass(frozen=True)
class SplitPinData:
    size: str                       # nominal size = pin hole diameter
    d_max: float                    # pin diameter (both legs together)
    d_min: float
    a_max: float                    # extended prong (longer leg)
    a_min: float
    b: float                        # eye length, approximate
    c_max: float                    # eye outer width
    c_min: float
    bolt: tuple[float | None, float | None]    # corresponding bolt dia., over / to
    clevis: tuple[float | None, float | None]  # corresponding clevis pin dia., over / to
    l_min: float                    # commercial length range
    l_max: float

    @property
    def hole(self) -> float:
        return float(self.size)

    def standard_lengths(self) -> list[float]:
        return [l for l in LENGTH_SERIES if self.l_min <= l <= self.l_max]


# fmt: off
SIZES: dict[str, SplitPinData] = {r.size: r for r in [
    #            size   d max d min a max a min b     c max c min bolt          clevis        l range
    SplitPinData("0.6", 0.5,  0.4,  1.6,  0.8,  2,    1.0,  0.9,  (None, 2.5),  (None, 2),    4,   12),
    SplitPinData("0.8", 0.7,  0.6,  1.6,  0.8,  2.4,  1.4,  1.2,  (2.5, 3.5),   (2, 3),       5,   16),
    SplitPinData("1",   0.9,  0.8,  1.6,  0.8,  3,    1.8,  1.6,  (3.5, 4.5),   (3, 4),       6,   20),
    SplitPinData("1.2", 1.0,  0.9,  2.5,  1.25, 3,    2.0,  1.7,  (4.5, 5.5),   (4, 5),       8,   25),
    SplitPinData("1.6", 1.4,  1.3,  2.5,  1.25, 3.2,  2.8,  2.4,  (5.5, 7),     (5, 6),       8,   32),
    SplitPinData("2",   1.8,  1.7,  2.5,  1.25, 4,    3.6,  3.2,  (7, 9),       (6, 8),       10,  40),
    SplitPinData("2.5", 2.3,  2.1,  2.5,  1.25, 5,    4.6,  4.0,  (9, 11),      (8, 9),       12,  50),
    SplitPinData("3.2", 2.9,  2.7,  3.2,  1.6,  6.4,  5.8,  5.1,  (11, 14),     (9, 12),      14,  63),
    SplitPinData("4",   3.7,  3.5,  4,    2,    8,    7.4,  6.5,  (14, 20),     (12, 17),     18,  80),
    SplitPinData("5",   4.6,  4.4,  4,    2,    10,   9.2,  8.0,  (20, 27),     (17, 23),     22,  100),
    SplitPinData("6.3", 5.9,  5.7,  4,    2,    12.6, 11.8, 10.3, (27, 39),     (23, 29),     32,  125),
    SplitPinData("8",   7.5,  7.3,  4,    2,    16,   15.0, 13.1, (39, 56),     (29, 44),     40,  160),
    SplitPinData("10",  9.5,  9.3,  6.3,  3.15, 20,   19.0, 16.6, (56, 80),     (44, 69),     45,  200),
    SplitPinData("13",  12.4, 12.1, 6.3,  3.15, 26,   24.8, 21.7, (80, 120),    (69, 110),    71,  250),
    SplitPinData("16",  15.4, 15.1, 6.3,  3.15, 32,   30.8, 27.0, (120, 170),   (110, 160),   112, 280),
    SplitPinData("20",  19.3, 19.0, 6.3,  3.15, 40,   38.5, 33.8, (170, None),  (160, None),  160, 280),
]}
# fmt: on

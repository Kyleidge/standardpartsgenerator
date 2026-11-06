"""Dimension table for ISO 7045:2011, pan head screws with type H or type Z
cross recess, product grade A.

Source: ISO 7045:2011 Table 1, M1.6 to M10, including the length range and
the threaded-to-head line. Cross-checked against
the ISO 7045 table of the FreeCAD Fasteners workbench (FsData/
iso7045def.csv: P, a, b, dk, da, k, r, rf, x, recess No., m H / Z and the
length ranges all agree) and against fasten.it's DIN EN ISO 7045 page
(recess numbers, m and the per-length masses agree; fasten.it lists
dk / k for M2.5, M3, M3.5 and M5 that differ from ISO 7045:2011, e.g. M5
dk 10, k 3.8 instead of 9.5, 3.7; the ISO values are used).

* Commercial lengths per size are the cells with a printed mass, which lie
  between the bold stepped lines (l_min / l_max).
* Lengths above the bold dashed line are threaded up to the head
  (b = l - a): up to 25 mm for M1.6 to M3, up to 40 mm for M3.5 to M10
  (``l_full_max``). Longer screws have b min (25 or 38 mm) of thread.
* l is measured from the bearing face to the tip.
* The head outline is not fully drawn in the standard (dk, k, rf ≈ and a
  rounded edge). The corner radius between the dome and the cylindrical side
  is not specified; the model uses k / 3 (see iso7045.py). Derived.
* m and the penetration depths are per screw size, for recess types H and
  Z; the recess geometry itself is ISO 4757 (see drives.py).

M3.5 is printed in parentheses (to be avoided if possible). Lengths 14 and
55 are printed in parentheses as well.

All values in millimetres.
"""

from __future__ import annotations

from dataclasses import dataclass

# Nominal lengths l of Table 1 (14 and 55 printed in parentheses).
LENGTH_SERIES: tuple[float, ...] = (
    3, 4, 5, 6, 8, 10, 12, 14, 16, 20, 25, 30, 35, 40, 45, 50, 55, 60,
)
NON_PREFERRED_LENGTHS = (14, 55)


@dataclass(frozen=True)
class SizeData:
    size: str           # designation, e.g. "M4"
    d: float            # nominal thread diameter
    P: float            # coarse pitch
    a_max: float        # distance of the last full thread to the head
    b_min: float        # thread length of partially threaded screws
    da_max: float       # transition diameter of the underhead fillet
    dk_max: float       # head diameter (nom = max)
    dk_min: float
    k_max: float        # head height (nom = max)
    k_min: float
    r_min: float        # underhead fillet radius
    rf: float           # dome radius (approximate value)
    x_max: float        # thread runout of partially threaded screws
    recess_no: int      # cross recess No. (ISO 4757)
    mH: float           # type H: recess diameter m (ref)
    pH_min: float       # type H: penetration depth
    pH_max: float
    mZ: float           # type Z: recess diameter m (ref)
    pZ_min: float       # type Z: penetration depth
    pZ_max: float
    l_min: float        # shortest commercial length
    l_max: float        # longest commercial length
    l_full_max: float   # longest length threaded up to the head
    preferred: bool = True

    def standard_lengths(self) -> list[float]:
        return [l for l in LENGTH_SERIES if self.l_min <= l <= self.l_max]

    def is_fully_threaded(self, l: float) -> bool:
        return l <= self.l_full_max

    def recess(self, kind: str) -> tuple[float, float, float]:
        """(m, penetration min, penetration max) for recess type H or Z."""
        if kind == "H":
            return self.mH, self.pH_min, self.pH_max
        if kind == "Z":
            return self.mZ, self.pZ_min, self.pZ_max
        raise KeyError(kind)


# fmt: off
#            size    d    P     a    b   da    dk_max dk_min k_max k_min r     rf   x     No mH    pH_min pH_max mZ   pZ_min pZ_max l_min l_max l_full
_ROWS = [
    SizeData("M1.6", 1.6, 0.35, 0.7, 25, 2.0,  3.2,  2.9,  1.30, 1.16, 0.1,  2.5, 0.9,  0, 1.7,  0.70, 0.95,  1.6, 0.65, 0.90,  3,  16, 25),
    SizeData("M2",   2,   0.4,  0.8, 25, 2.6,  4.0,  3.7,  1.60, 1.46, 0.1,  3.2, 1.0,  0, 1.9,  0.9,  1.2,   2.1, 1.17, 1.42,  3,  20, 25),
    SizeData("M2.5", 2.5, 0.45, 0.9, 25, 3.1,  5.0,  4.7,  2.10, 1.96, 0.1,  4,   1.1,  1, 2.7,  1.15, 1.55,  2.6, 1.25, 1.50,  3,  25, 25),
    SizeData("M3",   3,   0.5,  1.0, 25, 3.6,  5.6,  5.3,  2.40, 2.26, 0.1,  5,   1.25, 1, 3.0,  1.4,  1.8,   2.8, 1.50, 1.75,  4,  30, 25),
    SizeData("M3.5", 3.5, 0.6,  1.2, 38, 4.1,  7.00, 6.64, 2.60, 2.46, 0.1,  6,   1.5,  2, 3.9,  1.4,  1.9,   3.9, 1.48, 1.93,  5,  35, 40, False),
    SizeData("M4",   4,   0.7,  1.4, 38, 4.7,  8.00, 7.64, 3.10, 2.92, 0.2,  6.5, 1.75, 2, 4.4,  1.9,  2.4,   4.3, 1.89, 2.34,  5,  40, 40),
    SizeData("M5",   5,   0.8,  1.6, 38, 5.7,  9.50, 9.14, 3.70, 3.52, 0.2,  8,   2.0,  2, 4.9,  2.4,  2.9,   4.7, 2.29, 2.74,  6,  45, 40),
    SizeData("M6",   6,   1.0,  2.0, 38, 6.8,  12.00, 11.57, 4.6, 4.3, 0.25, 10,  2.5,  3, 6.9,  3.1,  3.6,   6.7, 3.03, 3.46,  8,  60, 40),
    SizeData("M8",   8,   1.25, 2.5, 38, 9.2,  16.00, 15.57, 6.0, 5.7, 0.4,  13,  3.2,  4, 9.0,  4.0,  4.6,   8.8, 4.05, 4.50,  10, 60, 40),
    SizeData("M10",  10,  1.5,  3.0, 38, 11.2, 20.00, 19.48, 7.50, 7.14, 0.4, 16,  3.8,  4, 10.1, 5.2,  5.8,   9.9, 5.24, 5.69,  12, 60, 40),
]
# fmt: on

SIZES: dict[str, SizeData] = {r.size: r for r in _ROWS}

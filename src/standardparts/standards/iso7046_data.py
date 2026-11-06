"""Dimension table for ISO 7046-1:2011, countersunk flat head screws
(common head style) with type H or type Z cross recess, product grade A,
property class 4.8.

Source: ISO 7046-1:2011 Table 1, M1.6 to M10, including the length range
and the threaded-to-head line. Cross recess: series 1 (deep), as printed.

Cross-checks:

* Head dimensions (dk theoretical / actual, k, r, x) for M2 to M10 are the
  same as in ISO 14581:2013 Table 1 (the same "common head style").
* Recess numbers and m for H and Z agree with the FreeCAD Fasteners
  workbench (FsData/iso7046def.csv), except that FreeCAD lists m = 4.0 for
  M5 type Z where ISO 7046-1 prints 4.9 (a FreeCAD typo; 4.9 is used).
  FreeCAD's length ranges for ISO 7046 agree.
* k max equals (dk theoretical - d) / 2 for every size: the 90° cone meets d
  at z = -k. This is a property of the table, checked in the tests.

Notes:

* Commercial lengths are the cells with a printed mass, between the bold
  continuous lines (l_min / l_max).
* l includes the head. Lengths above the bold dashed line are threaded up
  to the head, b = l - (k + a): up to 30 mm for M1.6 to M3 and 45 mm for
  M3.5 to M10 (``l_full_max``). Longer screws have b min of thread.
* The underhead radius has only a maximum; the model uses r max / 2
  (derived).

M3.5 and the lengths 14 and 55 are printed in parentheses.

All values in millimetres.
"""

from __future__ import annotations

from dataclasses import dataclass

LENGTH_SERIES: tuple[float, ...] = (
    3, 4, 5, 6, 8, 10, 12, 14, 16, 20, 25, 30, 35, 40, 45, 50, 55, 60,
)
NON_PREFERRED_LENGTHS = (14, 55)

# Countersink angle, ISO 7721.
HEAD_ANGLE = 90.0


@dataclass(frozen=True)
class SizeData:
    size: str
    d: float
    P: float
    a_max: float
    b_min: float
    dk_theo: float      # theoretical (sharp) head diameter, max
    dk_max: float       # actual head diameter, nom = max
    dk_min: float
    k_max: float        # head height, nom = max
    r_max: float        # underhead radius
    x_max: float
    recess_no: int
    mH: float
    pH_min: float
    pH_max: float
    mZ: float
    pZ_min: float
    pZ_max: float
    l_min: float
    l_max: float
    l_full_max: float
    preferred: bool = True

    @property
    def land_height(self) -> float:
        """Height of the cylindrical head edge at dk max when the cone sits
        at its theoretical (flush) position (derived)."""
        return (self.dk_theo - self.dk_max) / 2

    @property
    def r_model(self) -> float:
        return self.r_max / 2

    def standard_lengths(self) -> list[float]:
        return [l for l in LENGTH_SERIES if self.l_min <= l <= self.l_max]

    def is_fully_threaded(self, l: float) -> bool:
        return l <= self.l_full_max

    def recess(self, kind: str) -> tuple[float, float, float]:
        if kind == "H":
            return self.mH, self.pH_min, self.pH_max
        if kind == "Z":
            return self.mZ, self.pZ_min, self.pZ_max
        raise KeyError(kind)


# fmt: off
#            size    d    P     a    b   dk_th dk_max dk_min k     r    x     No mH    pH_min pH_max mZ   pZ_min pZ_max l_min l_max l_full
_ROWS = [
    SizeData("M1.6", 1.6, 0.35, 0.7, 25, 3.6,  3.0,   2.7,   1.0,  0.4, 0.9,  0, 1.6,  0.6, 0.9,   1.6, 0.70, 0.95,  3,  16, 30),
    SizeData("M2",   2,   0.4,  0.8, 25, 4.4,  3.8,   3.5,   1.2,  0.5, 1.0,  0, 1.9,  0.9, 1.2,   1.9, 0.95, 1.20,  3,  20, 30),
    SizeData("M2.5", 2.5, 0.45, 0.9, 25, 5.5,  4.7,   4.4,   1.5,  0.6, 1.1,  1, 2.9,  1.4, 1.8,   2.8, 1.48, 1.73,  3,  25, 30),
    SizeData("M3",   3,   0.5,  1.0, 25, 6.3,  5.5,   5.2,   1.65, 0.8, 1.25, 1, 3.2,  1.7, 2.1,   3.0, 1.76, 2.01,  4,  30, 30),
    SizeData("M3.5", 3.5, 0.6,  1.2, 38, 8.2,  7.30,  6.94,  2.35, 0.9, 1.5,  2, 4.4,  1.9, 2.4,   4.1, 1.75, 2.20,  5,  35, 45, False),
    SizeData("M4",   4,   0.7,  1.4, 38, 9.4,  8.40,  8.04,  2.7,  1.0, 1.75, 2, 4.6,  2.1, 2.6,   4.4, 2.06, 2.51,  5,  40, 45),
    SizeData("M5",   5,   0.8,  1.6, 38, 10.4, 9.30,  8.94,  2.7,  1.3, 2.0,  2, 5.2,  2.7, 3.2,   4.9, 2.60, 3.05,  6,  50, 45),
    SizeData("M6",   6,   1.0,  2.0, 38, 12.6, 11.30, 10.87, 3.3,  1.5, 2.5,  3, 6.8,  3.0, 3.5,   6.6, 3.00, 3.45,  8,  60, 45),
    SizeData("M8",   8,   1.25, 2.5, 38, 17.3, 15.80, 15.37, 4.65, 2.0, 3.2,  4, 8.9,  4.0, 4.6,   8.8, 4.15, 4.60,  10, 60, 45),
    SizeData("M10",  10,  1.5,  3.0, 38, 20.0, 18.30, 17.78, 5.0,  2.5, 3.8,  4, 10.0, 5.1, 5.7,   9.8, 5.19, 5.64,  12, 60, 45),
]
# fmt: on

SIZES: dict[str, SizeData] = {r.size: r for r in _ROWS}

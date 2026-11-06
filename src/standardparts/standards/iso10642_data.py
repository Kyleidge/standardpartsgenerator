"""Dimension table for ISO 10642:2004, hexagon socket countersunk head screws.

Source: ISO 10642:2004 Table 1 ("Dimensions"), M3 to M20, French edition
(ISO 10642:2004(F)). Every value below is from that table; nothing is
derived except where a docstring says so.

* The length rows (8 to 100 mm) and the two stepped lines that bound the
  commercial range of each size are taken from the table: the range
  starts at the first grey or white cell inside the bold border and ends at
  the last row with values (``l_min`` / ``l_max``).
* Grey cells are screws threaded up to the head ("à une distance de moins de
  3 P" of the head). Lengths with printed values are partially threaded with
  lg max = l - b and ls min = lg max - 5 P (Table 1 footnote f). The first
  partially threaded length of each size is ``l_partial``; the tests check
  that the formulas reproduce every printed ls / lg pair.
* l, ls and lg are measured from the top of the head: the head is part of
  the nominal length (Figure 1).
* k max equals (dk theoretical max - d) / 2: the height of the theoretical
  sharp 90 degree cone from d to dk. This is a property of the table, checked
  in the tests, not an assumption.
* dk actual has only a minimum in the table. The model uses it as the head
  diameter (see iso10642.py).

Later editions exist (ISO 10642:2019 and 2026, M2 to M20, "with reduced
loadability"). Their tables were not available and have not been checked
against these values; M2 is therefore not offered.

M14 is printed in parentheses in the standard (to be avoided if possible).

All values in millimetres.
"""

from __future__ import annotations

from dataclasses import dataclass

# Nominal lengths l printed in Table 1.
LENGTH_SERIES: tuple[float, ...] = (
    8, 10, 12, 16, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 80, 90, 100,
)

# Countersink angle: 90 deg nominal (90 to 92 deg allowed, Figure 1 note d).
HEAD_ANGLE = 90.0


@dataclass(frozen=True)
class SizeData:
    size: str           # designation, e.g. "M8"
    d: float            # nominal thread diameter (= ds max)
    P: float            # coarse thread pitch
    b: float            # thread length (reference) for partially threaded screws
    da_max: float       # transition diameter of the underhead fillet
    dk_theo_max: float  # theoretical sharp head diameter (flush gauge D)
    dk_min: float       # actual head diameter, minimum
    ds_min: float       # shank diameter (ds max = d)
    e_min: float        # socket width across corners
    k_max: float        # head height
    F_max: float        # flushness tolerance (head top below gauge surface)
    r_min: float        # underhead fillet radius
    s_nom: float        # socket width across flats
    s_max: float
    s_min: float
    t_min: float        # socket depth (key engagement)
    w_min: float        # wall thickness under the socket
    l_min: float        # shortest nominal length in the commercial range
    l_max: float        # longest nominal length in the commercial range
    l_partial: float    # first length of Table 1 with ls / lg values
    preferred: bool = True  # False for sizes printed in parentheses

    @property
    def ds_max(self) -> float:
        return self.d

    @property
    def land_height(self) -> float:
        """Height of the cylindrical head edge at dk_min, if the cone sits at
        its theoretical (flush) position: the cone loses (dk_theo - dk) / 2 of
        height at 45 deg. Derived, not a table value."""
        return (self.dk_theo_max - self.dk_min) / 2

    def standard_lengths(self) -> list[float]:
        return [l for l in LENGTH_SERIES if self.l_min <= l <= self.l_max]

    def thread_geometry(self, l: float) -> tuple[float | None, float | None]:
        """Return (ls_min, lg_max) for nominal length l, both from the top of
        the head. Both are None when the screw is threaded up to the head.

        Table 1 prints ls / lg from ``l_partial`` up; shorter lengths are
        threaded to the head. Custom (non-table) lengths follow the same
        boundary: partially threaded from l_partial on.
        """
        if l < self.l_partial:
            return None, None
        lg_max = l - self.b
        return round(lg_max - 5 * self.P, 3), round(lg_max, 3)

    def is_fully_threaded(self, l: float) -> bool:
        return self.thread_geometry(l)[0] is None


# fmt: off
#            size   d   P     b   da     dk_theo dk_min ds_min e_min   k     F     r     s_nom s_max   s_min   t    w     l_min l_max l_partial
_ROWS = [
    SizeData("M3",  3,  0.5,  18, 3.3,   6.72,  5.54,  2.86,  2.303,  1.86, 0.25, 0.1,  2,    2.08,   2.02,   1.1, 0.25, 8,  30,  30),
    SizeData("M4",  4,  0.7,  20, 4.4,   8.96,  7.53,  3.82,  2.873,  2.48, 0.25, 0.2,  2.5,  2.58,   2.52,   1.5, 0.45, 8,  40,  30),
    SizeData("M5",  5,  0.8,  22, 5.5,   11.20, 9.43,  4.82,  3.443,  3.1,  0.3,  0.2,  3,    3.08,   3.02,   1.9, 0.66, 8,  50,  35),
    SizeData("M6",  6,  1.0,  24, 6.6,   13.44, 11.34, 5.82,  4.583,  3.72, 0.35, 0.25, 4,    4.095,  4.020,  2.2, 0.7,  8,  60,  40),
    SizeData("M8",  8,  1.25, 28, 8.54,  17.92, 15.24, 7.78,  5.723,  4.96, 0.4,  0.4,  5,    5.14,   5.02,   3.0, 1.16, 10, 80,  50),
    SizeData("M10", 10, 1.5,  32, 10.62, 22.40, 19.22, 9.78,  6.863,  6.2,  0.4,  0.4,  6,    6.140,  6.020,  3.6, 1.62, 12, 100, 55),
    SizeData("M12", 12, 1.75, 36, 13.5,  26.88, 23.12, 11.73, 9.149,  7.44, 0.45, 0.6,  8,    8.175,  8.025,  4.3, 1.8,  20, 100, 65),
    SizeData("M14", 14, 2.0,  40, 15.5,  30.8,  26.52, 13.73, 11.429, 8.4,  0.5,  0.6,  10,   10.175, 10.025, 4.5, 1.62, 25, 100, 70, False),
    SizeData("M16", 16, 2.0,  44, 17.5,  33.60, 29.01, 15.73, 11.429, 8.8,  0.6,  0.6,  10,   10.175, 10.025, 4.8, 2.2,  30, 100, 80),
    SizeData("M20", 20, 2.5,  52, 22.0,  40.32, 36.05, 19.67, 13.716, 10.16, 0.75, 0.8, 12,   12.212, 12.032, 5.6, 2.2,  35, 100, 100),
]
# fmt: on

SIZES: dict[str, SizeData] = {r.size: r for r in _ROWS}

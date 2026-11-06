"""Dimension table for ISO 4162, hexagon bolts with flange, small series,
product grade A with driving feature of product grade B, M5 to M16.

Sources:

* ISO 4162:1990 Table 1, both parts: every value below, including the
  stepped lines of the length table (standard lengths per size,
  threaded-to-head lengths) and the ls min / lg max columns.
* ISO 4162:2012 (current, second edition) describes itself as "a minor
  revision" of the 1990 edition. Its scope (M5 to M16) and Figures 1 to 3
  (head, flange and underhead shapes, beta = 15 to 30 deg, top chamfer
  circle at least 0.85 s max, c measured at dw min, flange top 15 to
  25 deg, Type F flat bearing face) are cited here; its Table 1 was not
  available, so the numbers are not checked against the 2012 table. The
  2012 figure calls the wrenching height kw (k' in 1990).
* Cross-checks: fasten.it (its ISO 4162 1990 table: P, b, c, dc, e, k, s
  for every size), globalfastener.com (ISO 4162: P, b, c, dc, ds, e, k, s)
  and aftfasteners.com (ISO 4162: s, e, dc, ds, k). All agree with the
  1990 table. da, dw, kw (k'), lf, r1, r2 and the length table come from
  the 1990 table only.
* e min = 1.12 s min for every size (ISO 4759-1 grade B, i.e. the driving
  feature of grade B); tested.

The rule for ls / lg reproduces the table exactly (tested): lg max = l - b,
ls min = lg max - 5P, with b by ISO 888 band (l <= 125, 125 < l <= 200).
Lengths up to `l_to_head` are threaded to the head (above the continuous
stepped line of the table).

ISO 15071:2011 (the same bolt in product grade A throughout) is not
included: its table was not available, and the only secondary
table found (fasten.it, 1999 edition) differs from ISO 4162 in e min, k max
and has a misaligned M16 row.

All values are in millimetres; field names say which limit a value is.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Nominal lengths of the ISO 4162 length table.
LENGTH_SERIES: tuple[float, ...] = (
    10, 12, 16, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 80, 90, 100,
    110, 120, 130, 140, 150, 160,
)

# Flange top cone angle (ISO 4162 Figure 3: 15 to 25 deg) and hexagon top
# chamfer (Figure 1: beta = 15 to 30 deg, chamfer circle >= 0.85 s max).
FLANGE_ANGLE = 20.0
TOP_CHAMFER_DIA = 0.95   # fraction of s
TOP_CHAMFER_ANGLE = 30.0


@dataclass(frozen=True)
class SizeData:
    size: str          # designation, e.g. "M8"
    d: float           # nominal thread diameter (= ds max)
    P: float           # coarse pitch
    b1: float          # thread length b for l <= 125
    b2: float | None   # thread length b for 125 < l <= 200
    c_min: float       # flange thickness, measured at dw min
    da_max: float      # transition dia. of the underhead fillet (Type F)
    dc_max: float      # flange diameter
    ds_min: float
    dw_min: float      # bearing face diameter
    e_min: float       # width across corners
    k_max: float       # head height (flange included)
    kw_min: float      # wrenching height (k' in the 1990 edition)
    lf_max: float      # length of the underhead transition
    r1_min: float      # underhead fillet radius
    r2_max: float      # radius at the hexagon-to-flange junction
    s_max: float       # width across flats (s nom = s max)
    s_min: float
    lengths: tuple[float, float]   # [shortest, greatest] standard length
    l_to_head: float   # standard lengths up to this are threaded to the head
    preferred: bool = True

    @property
    def s_nom(self) -> float:
        return self.s_max

    @property
    def e_nom(self) -> float:
        """Across corners of the exact hexagon modeled at s nom."""
        return 2 * self.s_nom / math.sqrt(3)

    def standard_lengths(self) -> list[float]:
        lo, hi = self.lengths
        return [l for l in LENGTH_SERIES if lo <= l <= hi]

    def threaded_to_head(self, l: float) -> bool:
        return l <= self.l_to_head

    def b(self, l: float) -> float:
        """Thread length b for nominal length l (ISO 888 bands)."""
        b = self.b1 if l <= 125 else self.b2
        if b is None or l > 200:
            raise ValueError(f"no thread length b for {self.size} x {l:g}")
        return b

    def thread_geometry(self, l: float) -> tuple[float, float]:
        """(ls_min, lg_max) for a partially threaded bolt."""
        lg_max = l - self.b(l)
        return round(lg_max - 5 * self.P, 3), round(lg_max, 3)


# fmt: off
#           size   d   P     b1  b2    c    da    dc    ds    dw    e      k     kw   lf   r1    r2   s max s min  lengths    to head
SIZES: dict[str, SizeData] = {r.size: r for r in [
    SizeData("M5",  5,  0.8,  16, None, 1.0, 5.7,  11.4, 4.82,  9.4,  7.44,  5.6,  2.3, 1.4, 0.2,  0.3, 7,  6.64,  (10, 50),  20),
    SizeData("M6",  6,  1.0,  18, None, 1.1, 6.8,  13.6, 5.82,  11.6, 8.56,  6.8,  2.9, 1.6, 0.25, 0.4, 8,  7.64,  (12, 60),  25),
    SizeData("M8",  8,  1.25, 22, 28,   1.2, 9.2,  17.0, 7.78,  14.9, 10.80, 8.5,  3.8, 2.1, 0.4,  0.5, 10, 9.64,  (16, 80),  30),
    SizeData("M10", 10, 1.5,  26, 32,   1.5, 11.2, 20.8, 9.78,  18.7, 14.08, 9.7,  4.3, 2.1, 0.4,  0.6, 13, 12.57, (20, 100), 35),
    SizeData("M12", 12, 1.75, 30, 36,   1.8, 13.7, 24.7, 11.73, 22.5, 16.32, 11.9, 5.4, 2.1, 0.6,  0.7, 15, 14.57, (25, 120), 40),
    SizeData("M14", 14, 2.0,  34, 40,   2.1, 15.7, 28.6, 13.73, 26.4, 19.68, 12.9, 5.6, 2.1, 0.6,  0.9, 18, 17.57, (30, 140), 45, preferred=False),
    SizeData("M16", 16, 2.0,  38, 44,   2.4, 17.7, 32.8, 15.73, 30.6, 22.58, 15.1, 6.7, 3.2, 0.6,  1.0, 21, 20.16, (35, 160), 50),
]}
# fmt: on

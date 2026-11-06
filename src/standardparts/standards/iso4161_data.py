"""Dimension table for ISO 4161, hexagon nuts with flange, style 2, coarse
thread, M5 to M20.

Sources:

* ISO 4161:2012 Table 1: every value below. Figure 1 of the same
  standard gives the shapes: countersink theta = 90 to 120 deg at both
  bore ends, top corner chamfer beta = 15 to 30 deg, flange top cone
  delta = 15 to 25 deg, c measured at dw min, flat bearing face
  (0.75 +- 0.75 deg dished), edge contour at the manufacturer's
  discretion.
* Cross-check: fasten.it's DIN EN 1661 table (P, m, dc, c, s, e min for
  M5 to M20) agrees with ISO 4161:2012 except for M10, where EN 1661 has
  s = 16 / e = 17.77 and ISO 4161 has s = 15 / e = 16.64 (fasten.it notes
  the different M10 key size). da, dw and mw come from ISO 4161:2012 only.
* e min = 1.13 s min for every size (ISO 4759-1); tested.

Product grade A up to M16, B for M20 (ISO 4161:2012 clause 1).

All values are in millimetres; field names say which limit a value is.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Countersink at both bore ends (Figure 1: 90 to 120 deg), top corner
# chamfer (beta = 15 to 30 deg) and flange top cone (delta = 15 to 25 deg).
COUNTERSINK_ANGLE = 120.0
TOP_CHAMFER_ANGLE = 30.0
FLANGE_ANGLE = 20.0
# The top corner chamfer starts on a circle of this fraction of s. ISO 4161
# gives no value; this is the same as for the ISO 4162 bolt head.
TOP_CHAMFER_DIA = 0.95


@dataclass(frozen=True)
class SizeData:
    size: str          # designation, e.g. "M8"
    D: float           # nominal thread diameter
    P: float           # coarse pitch
    c_min: float       # flange thickness, measured at dw min
    da_max: float      # countersink diameter
    dc_max: float      # flange diameter
    dw_min: float      # bearing face diameter
    e_min: float       # width across corners
    m_max: float       # nut height (flange included)
    m_min: float
    mw_min: float      # wrenching height
    s_max: float       # width across flats (s nom = s max)
    s_min: float
    r_max: float       # radius at the hexagon-to-flange junction
    preferred: bool = True

    @property
    def da_min(self) -> float:
        return self.D

    @property
    def s_nom(self) -> float:
        return self.s_max

    @property
    def e_nom(self) -> float:
        """Across corners of the exact hexagon modeled at s nom."""
        return 2 * self.s_nom / math.sqrt(3)

    @property
    def product_grade(self) -> str:
        return "A" if self.D <= 16 else "B"


# fmt: off
#           size   D   P     c    da max dc    dw    e      m max m min  mw    s max s min  r
SIZES: dict[str, SizeData] = {r.size: r for r in [
    SizeData("M5",  5,  0.8,  1.0, 5.75,  11.8, 9.8,  8.79,  5.0,  4.70,  2.5,  8,  7.78,  0.3),
    SizeData("M6",  6,  1.0,  1.1, 6.75,  14.2, 12.2, 11.05, 6.0,  5.70,  3.1,  10, 9.78,  0.4),
    SizeData("M8",  8,  1.25, 1.2, 8.75,  17.9, 15.8, 14.38, 8.0,  7.64,  4.6,  13, 12.73, 0.5),
    SizeData("M10", 10, 1.5,  1.5, 10.80, 21.8, 19.6, 16.64, 10.0, 9.64,  5.6,  15, 14.73, 0.6),
    SizeData("M12", 12, 1.75, 1.8, 13.00, 26.0, 23.8, 20.03, 12.0, 11.57, 6.8,  18, 17.73, 0.7),
    SizeData("M14", 14, 2.0,  2.1, 15.10, 29.9, 27.6, 23.36, 14.0, 13.30, 7.7,  21, 20.67, 0.9, preferred=False),
    SizeData("M16", 16, 2.0,  2.4, 17.30, 34.5, 31.9, 26.75, 16.0, 15.30, 8.9,  24, 23.67, 1.0),
    SizeData("M20", 20, 2.5,  3.0, 21.60, 42.8, 39.9, 32.95, 20.0, 18.70, 10.7, 30, 29.16, 1.2),
]}
# fmt: on

"""Dimension table for DIN 508, nuts for T-slots (T-slot nuts).

Sources:

* DIN 508:2002-06 dimension table as published by globalfastener.com
  ("DIN 508 - 2002 Nuts for T-slots"): d, P, a nom / max / min, the base
  width (s max / min there, e in the other sources), the base chamfer f,
  h, k max / min and the mass per 1000 pieces, for M4 x 5 to M48 x 54.
  The drawing there shows the square base (e x e), the tenon of width a
  running over the full length e, and the 45 deg chamfer f on the two
  bottom edges of the base that run along the slot.
* Cross-checks: Halder EH 23010 datasheet (d, a, e, h, k for every row
  here; Halder marks exactly these 13 slot / thread pairs as DIN 508 and
  flags its other pairs, e.g. 14 x M10 or 16 x M14, as "not included in
  DIN"), Elesa-Ganter DIN 508 catalogue (a -0.3/-0.5, e -0.5, h, k with
  tolerances for 5 to 28), Sorotec and McMaster-Carr (M36 x 42 and
  M42 x 48: base 65 / 75, base height 26 / 30, overall 52 / 60), and
  fasten.it's DIN 508 page (06/2002), which uses the symbols a, e, h, k.

Symbols follow fasten.it, Halder and Elesa: a tenon width (fits the slot
width a nom), e width and length of the square base, h overall height, k
base height, f base chamfer. globalfastener's redrawing calls the base
width s.

Not taken over:

* fasten.it's table also lists 16 x M14, 20 x M18 and 24 x M22 (and omits
  5, 42, 48, 54). Halder and globalfastener do not list those as DIN 508
  and give no f or k min for them, so they are not offered. Neither source
  lists a second thread for any slot width: DIN 508 pairs each slot width
  with one thread.

Derived / model values:

* DIN 508 gives no countersink. The model has a 120 deg countersink of
  diameter da = min(1.08 d, (d + a max) / 2) at both bore ends (the 1.08 d
  of ISO 4032 da max, kept inside the narrow tenon).
* The masses are the table's approximate values. Two disagree with the
  geometry: 10 x M8 (18 g; the dimensions give about 14 g, Halder lists
  12 to 14 g) and 36 x M30 (770 g; about 635 g, Halder 585 g). The others
  agree with the model within 10%.
* The plan view in globalfastener's drawing shows slightly rounded
  vertical corners on the base; they have no dimension and are not modeled.

All values are in millimetres.
"""

from __future__ import annotations

from dataclasses import dataclass

COUNTERSINK_ANGLE = 120.0
CHAMFER_ANGLE = 45.0  # base chamfer f x 45 deg


@dataclass(frozen=True)
class SizeData:
    slot: str          # slot width a nom as text, the size key, e.g. "14"
    a_nom: float       # nominal tenon width = T-slot width (DIN 650)
    d: str             # thread, e.g. "M12"
    D: float           # nominal thread diameter
    P: float           # coarse pitch
    a_max: float       # tenon width
    a_min: float
    e_max: float       # base width and length
    e_min: float
    f: float           # base chamfer, 45 deg
    h: float           # overall height
    k_max: float       # base height
    k_min: float
    mass: float        # g per piece (= kg per 1000), approx., steel

    @property
    def designation(self) -> str:
        return f"{self.d} x {self.slot}"

    @property
    def da(self) -> float:
        """Model countersink diameter at both bore ends (not in DIN 508)."""
        return round(min(1.08 * self.D, (self.D + self.a_max) / 2), 3)


def _row(a, d, P, a_max, a_min, e_max, e_min, f, h, k_max, k_min, mass):
    return SizeData(f"{a:g}", float(a), d, float(d[1:]), P, a_max, a_min, e_max,
                    e_min, f, h, k_max, k_min, mass)


_ROWS = [
    #    a   d      P     a max  a min  e max  e min  f    h     k max  k min  kg/1000
    _row(5,  "M4",  0.7,  4.7,   4.5,   9,     8.5,   1.0, 6.5,  3,     2.7,   2.5),
    _row(6,  "M5",  0.8,  5.7,   5.5,   10,    9.5,   1.6, 8,    4,     3.5,   4),
    _row(8,  "M6",  1.0,  7.7,   7.5,   13,    12.5,  1.6, 10,   6,     5.5,   10),
    _row(10, "M8",  1.25, 9.7,   9.5,   15,    14.5,  1.6, 12,   6,     5.5,   18),
    _row(12, "M10", 1.5,  11.7,  11.4,  18,    17.5,  2.5, 14,   7,     6.5,   24),
    _row(14, "M12", 1.75, 13.7,  13.4,  22,    21.5,  2.5, 16,   8,     7.5,   35),
    _row(18, "M16", 2.0,  17.7,  17.4,  28,    27.5,  2.5, 20,   10,    9.5,   75),
    _row(22, "M20", 2.5,  21.7,  21.4,  35,    34.5,  2.5, 28,   14,    13.5,  165),
    _row(28, "M24", 3.0,  27.7,  27.4,  44,    43,    4.0, 36,   18,    17,    345),
    _row(36, "M30", 3.5,  35.6,  35.3,  54,    53,    6.0, 44,   22,    21,    770),
    _row(42, "M36", 4.0,  41.6,  41.3,  65,    64,    6.0, 52,   26,    25,    1030),
    _row(48, "M42", 4.5,  47.6,  47.3,  75,    74,    6.0, 60,   30,    29,    1550),
    _row(54, "M48", 5.0,  53.6,  53.2,  85,    84,    6.0, 70,   34,    33,    2300),
]

SIZES: dict[str, SizeData] = {r.slot: r for r in _ROWS}

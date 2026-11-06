"""Dimension table for DIN 580:2010-09, lifting eye bolts (Ringschrauben),
forged steel C15E, M8 to M100 x 6.

Symbols follow DIN 580 Bild 1:

* d1: thread (coarse pitch; the three largest sizes are fine pitch x 6),
* d2: collar (bearing face) diameter, the collar flank drafted 1:20,
* d3: eye outer diameter, d4: eye inner diameter,
* e: collar height, from the bearing face to the collar's top edge,
* h: overall height, from the bearing face to the top of the eye,
* k: thickness of the ring at the top of the eye (its section is round
  there, and k = (d3 - d4) / 2 in every row),
* m: out-of-plane width of the ring at its lower section, at the collar,
* l: thread length below the bearing face,
* f: thread undercut length, max (2P in every row), dg: undercut diameter
  (h13, DIN 76-1), r2: undercut-to-bearing-face radius, r3:
  undercut-to-thread radius, r1: radius where the outer contour of the
  ring runs into the bearing face.

Sources:

* d2, d3, d4, e, k, l, m, the mass per piece and the three working load
  limits for every size: fasten.it's DIN 580 table for the 09/2010 edition
  (https://www.fasten.it/en/norms/norm/din_580), identical to its 04/2018
  table and to DIN 580:2018-04 Tables 1, 3 and 4.
* h, f, dg, r1, r2 and r3: DIN 580:2018-04 and fasteners.eu
  (https://www.fasteners.eu/standards/DIN/580/). fasten.it's 2010 table
  has no h or undercut columns. h is also confirmed by the Elesa+Ganter
  DIN 580 datasheet (M8 to M36, checked) and the Greenpin eye bolt
  datasheet (M8 to M72 x 6). fasteners.eu lists f = 6 for M42, a typo for
  9 (= 2P, as in DIN 580:2018-04).
* Edition: DIN Media's change notes say the 2018 edition only added
  intermediate sizes (M6, M14, ..., M60) and load directions, and the 2010
  edition (which superseded 2003-08) added tolerances and a 90 deg
  breaking load but no dimensional changes. So the 2018 nominal values of
  the 15 sizes listed here are taken as the 2010 table; that is an
  inference, since the 2010 text itself was not checked. The 2003 and
  older (1972) tables were not checked; supplier data for "1972" bolts shows
  the same main dimensions.
* Pitches are the ISO 261 coarse pitches (not printed in the table); the
  undercut diameters match d - 1.6P ... d - 1.39P as in DIN 76-1.

Working load limits are in kg per eye bolt: ``wll_axial`` for a pull
along the bolt axis, ``wll_45`` for two or more legs inclined up to 45 deg
in the ring plane, ``wll_side`` for up to 45 deg with the bolts fitted at
the sides of the load (DIN 580:2010 table; the 2018 edition lists the same
values for 60 deg and 90 deg). Pulling across the ring plane is not
permitted.

All values are nominal, in millimetres.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SizeData:
    size: str          # designation, e.g. "M12" or "M72x6"
    d: float           # nominal thread diameter d1
    P: float           # pitch
    d2: float          # collar diameter
    d3: float          # eye outer diameter
    d4: float          # eye inner diameter
    e: float           # collar height
    h: float           # overall height
    k: float           # ring thickness at the top
    l: float           # thread length
    m: float           # ring width at the collar
    f: float           # undercut length, max
    dg: float          # undercut diameter
    r1: float          # ring contour to bearing face (not modeled)
    r2: float          # undercut to bearing face
    r3: float          # undercut to thread (not modeled)
    mass: float        # kg per piece (table)
    wll_axial: float   # kg
    wll_45: float      # kg, per bolt
    wll_side: float    # kg, per bolt

    @property
    def designation_thread(self) -> str:
        if "x" in self.size:
            d, p = self.size[1:].split("x")
            return f"M{d} x {p}"
        return self.size

    @property
    def label(self) -> str:
        return f"{self.designation_thread} (P {self.P:g})"


_COARSE = {
    8: 1.25, 10: 1.5, 12: 1.75, 16: 2.0, 20: 2.5, 24: 3.0, 30: 3.5, 36: 4.0,
    42: 4.5, 48: 5.0, 56: 5.5, 64: 6.0,
}

# size, d2, d3, d4, e, h, k, l, m, f, dg, r1, r2, r3, mass, WLL 0 / 45 / side
_ROWS = [
    ("M8", 20, 36, 20, 6, 36, 8, 13, 10, 2.5, 6, 4, 1, 1, 0.06, 140, 100, 70),
    ("M10", 25, 45, 25, 8, 45, 10, 17, 12, 3, 7.7, 4, 1, 1, 0.11, 230, 170, 115),
    ("M12", 30, 54, 30, 10, 53, 12, 20.5, 14, 3.5, 9.4, 6, 2, 1.2, 0.18, 340, 240, 170),
    ("M16", 35, 63, 35, 12, 62, 14, 27, 16, 4, 13, 6, 2, 1.2, 0.28, 700, 500, 350),
    ("M20", 40, 72, 40, 14, 71, 16, 30, 19, 5, 16.4, 8, 2, 1.6, 0.45, 1200, 860, 600),
    ("M24", 50, 90, 50, 18, 90, 20, 36, 24, 6, 19.6, 12, 2, 2, 0.74, 1800, 1290, 900),
    ("M30", 65, 108, 60, 22, 109, 24, 45, 28, 7, 25, 15, 3, 2, 1.66, 3200, 2300, 1600),
    ("M36", 75, 126, 70, 26, 128, 28, 54, 32, 8, 30.3, 18, 3, 2, 2.65, 4600, 3300, 2300),
    ("M42", 85, 144, 80, 30, 147, 32, 63, 38, 9, 35.6, 20, 3, 2.5, 4.03, 6300, 4500, 3150),
    ("M48", 100, 166, 90, 35, 168, 38, 68, 46, 10, 41, 22, 4, 2.5, 6.38, 8600, 6100, 4300),
    ("M56", 110, 184, 100, 38, 187, 42, 78, 50, 11, 48.3, 25, 4, 3, 8.8, 11500, 8200, 5750),
    ("M64", 120, 206, 110, 42, 208, 48, 90, 58, 12, 55.7, 25, 4, 3, 12.4, 16000, 11000, 8000),
    ("M72x6", 150, 260, 140, 50, 260, 60, 100, 72, 12, 63.7, 35, 4, 3, 23.3, 20000, 14000, 10000),
    ("M80x6", 170, 296, 160, 55, 298, 68, 112, 80, 12, 71.7, 35, 4, 3, 34.2, 28000, 20000, 14000),
    ("M100x6", 190, 330, 180, 60, 330, 75, 130, 88, 12, 91.7, 40, 4, 3, 49.1, 40000, 29000, 20000),
]


def _size(row: tuple) -> SizeData:
    size = row[0]
    if "x" in size:
        d_str, p_str = size[1:].split("x")
        d, P = float(d_str), float(p_str)
    else:
        d = float(size[1:])
        P = _COARSE[int(d)]
    return SizeData(size, d, P, *row[1:])


SIZES: dict[str, SizeData] = {row[0]: _size(row) for row in _ROWS}

"""Dimension table for ISO 7379:1983, hexagon socket head shoulder screws.

Sources:

* Every dimension and the length ranges: ISO 7379:1983 section 3 (figure
  and table): ds max/min, d, P, b max/min, dk max (plain and knurled), dk
  min, dg1 min, dg2 max/min, da1 max, da2 max, e min, k max/min, g1 max,
  g2 max, r1 min, r2 min, s nom/max/min, t min, w min.
* Cross-checked against fasten.it's ISO 7379 page (same values, including
  k = 9 for ds = 13), and its "range of commercial items", which matches
  the stepped length range of the standard.

Symbols follow the 1983 standard. Supplier catalogues often use other
letters for the same features: shoulder diameter ds = d1, thread d = d3,
thread length b = l2, shoulder length l = l1.

Tolerances: ds is f9 in ISO 7379:1983 (e.g. 10: -0.013 / -0.049; a test
checks every row against the ISO 286 f9 limits). Many suppliers sell the
same screw with an h8 shoulder; the model uses the nominal ds either way.

Derived values, used by the model but not printed in the standard:

* b_nom = (b max + b min) / 2. These are the round values suppliers list as
  the nominal thread length (9.5, 11, 13, 16, 18, 22, 27).
* dg2_nom = (dg2 max + dg2 min) / 2, the neck (thread undercut) diameter.
* The neck runs at dg2 for g2 max below the shoulder face, then rises to d
  on a 30 deg cone (the figure's "30 deg min", measured from the axis).
* The groove under the head is modeled at dg1 min for a width g1 max (from
  the bearing face to the start of its 45 deg flank).
* The standard leaves the shoulder edge "rounded or chamfered, 0.15 mm for
  ds < 10 mm and 0.2 mm for ds > 10 mm"; ds = 10 is not covered and the
  model uses 0.2 mm for it.
* The head top edge may be rounded or chamfered with no size given; the
  model uses a 45 deg chamfer v = 0.1 k (ISO 4762 uses v = 0.1 d = 0.1 k).

All values in millimetres. Where the standard gives a range, the field name
says which limit it is (``dk_max``, ``t_min``, ...).
"""

from __future__ import annotations

from dataclasses import dataclass

# Nominal shoulder lengths l printed in ISO 7379:1983 (tolerance +0.25 / 0).
# Intermediate lengths according to ISO 888 are permitted.
LENGTH_SERIES: tuple[float, ...] = (10, 12, 16, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100, 120)


@dataclass(frozen=True)
class SizeData:
    size: str            # shoulder diameter key, e.g. "10"
    ds: float            # nominal shoulder diameter
    ds_max: float
    ds_min: float
    thread: str          # thread designation, e.g. "M8"
    d: float             # thread diameter
    P: float             # coarse thread pitch
    b_max: float         # thread length, from the shoulder face to the tip
    b_min: float
    dk_max: float        # head diameter, plain head
    dk_max_knurled: float
    dk_min: float
    dg1_min: float       # groove diameter under the head
    dg2_max: float       # neck (undercut) diameter between shoulder and thread
    dg2_min: float
    da1_max: float       # underhead transition diameter (form without groove)
    da2_max: float       # transition diameter on the shoulder face
    e_min: float         # socket width across corners
    k_max: float         # head height
    k_min: float
    g1_max: float        # groove width under the head
    g2_max: float        # neck length below the shoulder face
    r1_min: float        # fillet head / groove
    r2_min: float        # fillet shoulder face / neck
    s_nom: float         # socket width across flats
    s_max: float
    s_min: float
    t_min: float         # socket depth
    w_min: float         # wall between socket bottom and bearing face
    l_min: float         # shortest standard shoulder length
    l_max: float         # longest standard shoulder length

    @property
    def label(self) -> str:
        return f"{self.size} ({self.thread})"

    @property
    def b_nom(self) -> float:
        """Nominal thread length, the middle of the tolerance (derived)."""
        return round((self.b_max + self.b_min) / 2, 3)

    @property
    def dg2_nom(self) -> float:
        """Neck diameter used by the model, the middle of the tolerance (derived)."""
        return round((self.dg2_max + self.dg2_min) / 2, 3)

    @property
    def shoulder_chamfer(self) -> float:
        """Shoulder edge chamfer: 0.15 for ds < 10, else 0.2 (see module notes)."""
        return 0.15 if self.ds < 10 else 0.2

    @property
    def v(self) -> float:
        """Head top-edge chamfer used by the model, 0.1 k (derived)."""
        return round(0.1 * self.k_max, 3)

    def standard_lengths(self) -> list[float]:
        return [l for l in LENGTH_SERIES if self.l_min <= l <= self.l_max]


# fmt: off
_COLUMNS = (
    "size ds ds_max ds_min thread d P b_max b_min dk_max dk_max_knurled dk_min "
    "dg1_min dg2_max dg2_min da1_max da2_max e_min k_max k_min g1_max g2_max "
    "r1_min r2_min s_nom s_max s_min t_min w_min l_min l_max"
).split()

_ROWS = [
    # size  ds    ds_max  ds_min  thr    d   P     b max  b min  dk    dk_kn  dk_min dg1   dg2max dg2min da1  da2 e_min  k   k_min g1   g2   r1    r2    s   s_max   s_min   t    w     l_min l_max
    ("6.5", 6.5,  6.487,  6.451,  "M5",  5,  0.8,  9.75,  9.25,  10,  10.22, 9.78,  5.92,  3.86,  3.68,  7.5,  5,  3.44,  4.5, 4.32, 2.5, 2,   0.25, 0.5,  3,  3.08,   3.02,   2.4, 1,    10,   40),
    ("8",   8,    7.987,  7.951,  "M6",  6,  1,    11.25, 10.75, 13,  13.27, 12.73, 7.42,  4.58,  4.40,  9.2,  6,  4.58,  5.5, 5.32, 2.5, 2.5, 0.4,  0.53, 4,  4.095,  4.02,   3.3, 1.15, 12,   50),
    ("10",  10,   9.987,  9.951,  "M8",  8,  1.25, 13.25, 12.75, 16,  16.27, 15.73, 9.42,  6.25,  6.03,  11.2, 8,  5.72,  7,   6.78, 2.5, 3.1, 0.6,  0.64, 5,  5.095,  5.02,   4.2, 1.6,  16,   120),
    ("13",  13,   12.984, 12.941, "M10", 10, 1.5,  16.40, 15.60, 18,  18.27, 17.73, 12.42, 7.91,  7.69,  15.2, 10, 6.86,  9,   8.78, 2.5, 3.7, 0.6,  0.77, 6,  6.095,  6.02,   4.9, 1.8,  16,   120),
    ("16",  16,   15.984, 15.941, "M12", 12, 1.75, 18.40, 17.60, 24,  24.33, 23.67, 15.42, 9.57,  9.35,  18.2, 12, 9.15,  11,  10.73, 2.5, 4.4, 0.6, 0.87, 8,  8.115,  8.025,  6.6, 2,    30,   120),
    ("20",  20,   19.980, 19.928, "M16", 16, 2,    22.40, 21.60, 30,  30.33, 29.67, 19.42, 13.33, 12.96, 22.4, 16, 11.43, 14,  13.73, 2.5, 5,   0.8, 1.14, 10, 10.115, 10.025, 8.8, 3.2,  40,   120),
    ("25",  25,   24.980, 24.928, "M20", 20, 2.5,  27.40, 26.60, 36,  36.39, 35.61, 24.42, 16.57, 16.30, 27.4, 20, 13.72, 16,  15.73, 3,   6.3, 0.8, 1.38, 12, 12.142, 12.032, 10,  3.25, 50,   120),
]
# fmt: on

SIZES: dict[str, SizeData] = {
    row[0]: SizeData(**dict(zip(_COLUMNS, row, strict=True))) for row in _ROWS
}

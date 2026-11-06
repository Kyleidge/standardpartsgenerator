"""Dimension table for DIN 7984:2009-06, hexagon socket head cap screws with
low head.

Sources:

* DIN 7984:2009-06 Table 1: P, b (l <= 125, 125 < l <= 200, l > 200),
  da max, dk max/min, ds max/min, dw min, e min, lf max, k max/min,
  r min, s nom/min/max, t nom/min/max, v max, the length ranges and the
  ls / lg entries of every listed nominal length.
* Cross-checked against fasten.it's DIN 7984 tables (same head, socket and
  b values in the 2009-06, 10/2021 and 03/2022 editions), the Ferrobend
  DIN 7984 table (M3 to M8) and fasteners.eu's DIN 7984 ls / lg tables
  (edition not stated). fasteners.eu agrees on every ls / lg value it
  lists and on the threaded-to-head boundary of all 13 sizes, and on the
  length ranges of M3 to M16. Its ranges for M18 and M20 start at 40 (here
  30) and for M22 and M24 at 50 (here 40), and its M8 / M10 rows were only
  checked up to 70 mm; those lengths are not confirmed by a second source.

Thread length rule (Table 1 footnote c): for lengths below the stepped line
lg max = l - b and ls min = lg max - 5P; above it the screw is threaded to
the head, with the last full thread within lg max ~ 3P of the bearing face.
The step does not follow a single ls or lg threshold (e.g. M3 x 18 is
threaded to the head with ls = 3.5, while M10 x 40 is partial with
ls = 6.5), so the table's first partially threaded length is stored per
size (``l_partial``) and applied to custom lengths too. The tests check the
printed ls / lg values against the rule.

Table 1 prints lf max = 1.87 for M12, M14 and M16, above the figure's rule
lf max = 1.7 (da max - ds max) / 2 = 1.45; kept as printed (lf is not used
by the model).

DIN 7984 lists nominal lengths up to 100 mm. Lengths in brackets, (14),
(18) and (55), and the sizes (M14), (M18) and (M22) "should be avoided if
possible" but are standard and included here. The 10/2021 edition extended
the commercial length range (to 160 mm for M10 to M20); those lengths are
not included.

Model choices (derived, not in the standard): socket s nom to depth t min
like ISO 4762, but finished with a 140 deg drill point instead of the
shared 118 deg one, because DIN 7984's reduced socket depth leaves the
118 deg point at or below the bearing face for most sizes (k - t min is
less than the 118 deg cone height). The 140 deg point stays inside the head
on every size (at least 0.18 mm above the bearing face, M4).

All values in millimetres. Where the standard gives a range, the field name
says which limit it is (``dk_max``, ``t_min``, ...).
"""

from __future__ import annotations

from dataclasses import dataclass

# Nominal lengths l of DIN 7984:2009-06 Table 1 (14, 18 and 55 in brackets).
LENGTH_SERIES: tuple[float, ...] = (
    5, 6, 8, 10, 12, 14, 16, 18, 20, 25, 30, 35, 40, 45, 50, 55, 60, 70, 80, 90, 100,
)


@dataclass(frozen=True)
class SizeData:
    size: str            # designation, e.g. "M6"
    d: float             # nominal thread diameter (= ds max)
    P: float             # coarse thread pitch
    b: float             # thread length for l <= 125
    b_200: float | None  # thread length for 125 < l <= 200
    b_long: float | None # thread length for l > 200
    da_max: float        # transition diameter of the underhead fillet
    dk_max: float        # head diameter
    dk_min: float
    ds_min: float        # shank diameter
    dw_min: float        # bearing face diameter
    e_min: float         # socket width across corners (1.14 s min)
    lf_max: float        # underhead fillet length
    k_max: float         # head height
    k_min: float
    r_min: float         # underhead fillet radius
    s_nom: float         # socket width across flats
    s_min: float
    s_max: float
    t_nom: float         # socket depth
    t_min: float
    t_max: float
    v_max: float         # head top-edge chamfer
    l_min: float         # shortest standard nominal length
    l_max: float         # longest standard nominal length
    l_partial: float     # first standard length that is partially threaded

    @property
    def ds_max(self) -> float:
        return self.d

    def standard_lengths(self) -> list[float]:
        return [l for l in LENGTH_SERIES if self.l_min <= l <= self.l_max]

    def thread_length(self, l: float) -> float:
        """b for nominal length l (DIN 7984 Table 1)."""
        if l <= 125:
            return self.b
        if l <= 200 and self.b_200 is not None:
            return self.b_200
        if self.b_long is not None:
            return self.b_long
        return self.b_200 if self.b_200 is not None else self.b

    def is_fully_threaded(self, l: float) -> bool:
        return l < self.l_partial

    def thread_geometry(self, l: float) -> tuple[float | None, float | None]:
        """(ls_min, lg_max) for nominal length l, both None when the screw is
        threaded to the head."""
        if self.is_fully_threaded(l):
            return None, None
        lg_max = l - self.thread_length(l)
        return round(lg_max - 5 * self.P, 3), round(lg_max, 3)


# fmt: off
_COLUMNS = (
    "size d P b b_200 b_long da_max dk_max dk_min ds_min dw_min e_min lf_max "
    "k_max k_min r_min s_nom s_min s_max t_nom t_min t_max v_max l_min l_max l_partial"
).split()

_ROWS = [
    # size   d   P     b   b200  blong da    dk  dk_min ds_min dw_min e_min  lf    k    k_min  r     s   s_min   s_max   t    t_min t_max v    l_min l_max l_part
    ("M3",   3,  0.5,  12, None, None, 3.6,  5.5, 5.32,  2.86,  4.84,  2.3,   0.51, 2,   1.86,  0.1,  2,  2.02,   2.10,   1.5, 1.38, 1.62, 0.3, 5,   20,   20),
    ("M4",   4,  0.7,  14, None, None, 4.7,  7,   6.78,  3.82,  6.2,   2.87,  0.6,  2.8, 2.66,  0.2,  2.5, 2.52,  2.60,   2.3, 2.18, 2.42, 0.4, 6,   25,   25),
    ("M5",   5,  0.8,  16, None, None, 5.7,  8.5, 8.28,  4.82,  7.7,   3.44,  0.6,  3.5, 3.32,  0.2,  3,  3.02,   3.10,   2.7, 2.58, 2.82, 0.5, 8,   30,   30),
    ("M6",   6,  1,    18, None, None, 6.8,  10,  9.78,  5.82,  9.2,   4.58,  0.68, 4,   3.82,  0.25, 4,  4.02,   4.12,   3,   2.88, 3.12, 0.6, 10,  40,   30),
    ("M8",   8,  1.25, 22, 28,   None, 9.2,  13,  12.73, 7.78,  12.03, 5.72,  1.02, 5,   4.82,  0.4,  5,  5.02,   5.14,   3.8, 3.65, 3.95, 0.8, 12,  80,   35),
    ("M10",  10, 1.5,  26, 32,   None, 11.2, 16,  15.73, 9.78,  15.03, 8.01,  1.02, 6,   5.82,  0.4,  7,  7.025,  7.175,  4.5, 4.35, 4.65, 1,   16,  100,  40),
    ("M12",  12, 1.75, 30, 36,   None, 13.7, 18,  17.73, 11.73, 17.03, 9.15,  1.87, 7,   6.78,  0.6,  8,  8.025,  8.175,  5,   4.85, 5.15, 1.2, 20,  80,   50),
    ("M14",  14, 2,    34, 40,   None, 15.7, 21,  20.67, 13.73, 19.83, 11.43, 1.87, 8,   7.78,  0.6,  10, 10.025, 10.175, 5.3, 5.15, 5.45, 1.4, 30,  80,   55),
    ("M16",  16, 2,    38, 44,   57,   17.7, 24,  23.67, 15.73, 22.83, 13.72, 1.87, 9,   8.78,  0.6,  12, 12.032, 12.212, 5.5, 5.35, 5.65, 1.6, 30,  80,   60),
    ("M18",  18, 2.5,  42, 48,   61,   20.2, 27,  26.67, 17.73, 25.83, 13.72, 1.87, 10,  9.78,  0.6,  12, 12.032, 12.212, 6.5, 6.32, 6.68, 1.8, 30,  100,  70),
    ("M20",  20, 2.5,  46, 52,   65,   22.4, 30,  29.67, 19.67, 28.83, 16,    2.04, 11,  10.73, 0.8,  14, 14.032, 14.212, 7.5, 7.32, 7.68, 2,   30,  100,  70),
    ("M22",  22, 2.5,  50, 56,   69,   24.4, 33,  32.61, 21.67, 31.61, 16,    2.04, 12,  11.73, 0.8,  14, 14.032, 14.212, 8,   7.82, 8.18, 2.2, 40,  100,  80),
    ("M24",  24, 3,    54, 60,   73,   26.4, 36,  35.61, 23.67, 34.61, 19.44, 2.04, 13,  12.73, 0.8,  17, 17.05,  17.23,  8,   7.82, 8.18, 2.4, 40,  100,  90),
]
# fmt: on

SIZES: dict[str, SizeData] = {
    row[0]: SizeData(**dict(zip(_COLUMNS, row, strict=True))) for row in _ROWS
}

"""Dimension tables for ISO 4014:2022 (hexagon head bolts, partially
threaded) and ISO 4017:2022 (hexagon head screws, threaded to the head),
product grades A and B, M1.6 to M64 coarse thread.

Both standards use the same head, so the head dimensions are one table.

Sources:

* Head dimensions (c, da, dw, e, k, kw, r, s) for every size, preferred and
  non-preferred: ISO 4017:2022 Tables 1 to 4. Grade A columns cover M1.6
  to M24, grade B columns M16 to M64. The grade B values for M1.6 to M14
  (Annex A) are not included; they are not needed because every standard
  length of those sizes is grade A (see `product_grade`).
* Cross-checks of the head table: ISO 4014:2022 Tables 1 to 4 (grade A
  M1.6 to M24, grade B M16 to M27, all values identical), ISO 4014:2011
  Table 1 (grade B M30 to M64, identical) and fasten.it (DIN EN ISO 4014
  06-2011 and DIN EN ISO 4017 10-2014: s, e, k and b for all sizes).
* ISO 4014 thread lengths b: ISO 4014:2022 Tables 1 to 4 for M1.6 to M27,
  ISO 4014:2011 Table 1 and fasten.it for M30 to M64. All follow the
  ISO 888 rule b = 2d + 6 (l <= 125), 2d + 12 (125 < l <= 200) and
  2d + 25 (l > 200), rounded down for M1.6. One value is derived: M33
  b = 72 for l <= 125 (2d + 6). The tables list no b there because the
  older edition started M33 at 130 mm; the 2022 length rule starts it at
  120 mm.
* ISO 4017 length ranges: from the stepped lines of ISO 4017:2022
  Tables 1 to 4 (every size). They follow the rules printed in the
  standard: shortest length 2d rounded to the nearest standard length
  (ties round up, e.g. M3.5 -> 8, M7 -> 16), 120 mm for M64; greatest
  length 10d or 200 mm, whichever is shorter.
* ISO 4014 length ranges: M1.6 to M27 from the stepped lines of ISO
  4014:2022 Tables 1 to 4. M30 to M64 (Tables 5 and 6) are not taken from
  the 2022 tables; they are derived from the rules printed in Figure 1 of
  ISO 4014:2022: shortest length 3.75d rounded to the nearest standard
  length (ties rounded up as in ISO 4017:2022; this affects M36 -> 140 and
  M56 -> 220, which also match the 2011 edition), 220 mm for M64; greatest
  length 10d or 500 mm, whichever is shorter. These derived ranges differ
  from ISO 4014:2011 for M33 (120 vs 130), M42 (max 420 vs 440), M45 (160
  vs 180), M52 (max 500 vs 480), M60 (220 vs 240) and M64 (220 vs 260),
  which is what the 2022 foreword announces ("rules for the shortest and
  greatest standard lengths have been added, and they have been amended
  accordingly"), but they are not checked against the 2022 table itself.

All values are in millimetres. Where the standard gives a range, the field
name says which limit it is.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Standard nominal lengths (ISO 4014:2022 / ISO 4017:2022 length columns).
LENGTH_SERIES: tuple[float, ...] = (
    3, 4, 5, 6, 8, 10, 12, 16, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70,
    80, 90, 100, 110, 120, 130, 140, 150, 160, 180, 200, 220, 240, 260, 280,
    300, 320, 340, 360, 380, 400, 420, 440, 460, 480, 500,
)


@dataclass(frozen=True)
class GradeDims:
    """Head dimensions that depend on the product grade."""

    dw_min: float      # bearing face diameter
    e_min: float       # width across corners
    k_max: float
    k_min: float
    kw_min: float      # wrenching height
    s_min: float


@dataclass(frozen=True)
class SizeData:
    size: str          # designation, e.g. "M8"
    d: float           # nominal thread diameter (= ds max)
    P: float           # coarse pitch
    c_max: float       # washer face height
    c_min: float
    da_max: float      # transition diameter of the underhead fillet
    k_nom: float       # head height, nominal
    r_min: float       # underhead fillet radius
    s_nom: float       # width across flats (nom = max)
    A: GradeDims | None
    B: GradeDims | None
    b: tuple[float | None, float | None, float | None]  # ISO 4014: l<=125, <=200, >200
    l4014: tuple[float, float]   # ISO 4014 [shortest, greatest] standard length
    l4017: tuple[float, float]   # ISO 4017 [shortest, greatest] standard length

    @property
    def preferred(self) -> bool:
        return self.size not in NON_PREFERRED

    @property
    def e_nom(self) -> float:
        """Across corners of the exact hexagon modeled at s nom."""
        return 2 * self.s_nom / math.sqrt(3)

    def product_grade(self, l: float) -> str:
        """Grade A for d <= 24 and l <= 10d or 150 mm (whichever is shorter),
        grade B otherwise (scope of ISO 4014 / ISO 4017)."""
        return "A" if self.d <= 24 and l <= min(10 * self.d, 150) else "B"

    def grade_dims(self, l: float) -> GradeDims:
        dims = self.A if self.product_grade(l) == "A" else self.B
        assert dims is not None, (self.size, l)
        return dims

    # ISO 4014 -------------------------------------------------------------

    def lengths_4014(self) -> list[float]:
        lo, hi = self.l4014
        return [l for l in LENGTH_SERIES if lo <= l <= hi]

    def b_4014(self, l: float) -> float:
        """Thread length b for nominal length l (ISO 888 bands)."""
        b = self.b[0] if l <= 125 else self.b[1] if l <= 200 else self.b[2]
        if b is None:
            raise ValueError(f"no thread length b for {self.size} x {l:g}")
        return b

    def thread_geometry_4014(self, l: float) -> tuple[float, float]:
        """(ls_min, lg_max): lg_max = l - b and ls_min = lg_max - 5P."""
        lg_max = l - self.b_4014(l)
        return round(lg_max - 5 * self.P, 3), round(lg_max, 3)

    # ISO 4017 -------------------------------------------------------------

    def lengths_4017(self) -> list[float]:
        lo, hi = self.l4017
        return [l for l in LENGTH_SERIES if lo <= l <= hi]

    @property
    def a_max_4017(self) -> float:
        """Distance from the bearing face to the first full thread, max 3P."""
        return 3 * self.P

    @property
    def a_min_4017(self) -> float:
        return self.P


NON_PREFERRED = {"M3.5", "M7", "M14", "M18", "M22", "M27", "M33", "M39", "M45", "M52", "M60"}


def _g(dw, e, kmax, kmin, kw, smin) -> GradeDims:
    return GradeDims(dw_min=dw, e_min=e, k_max=kmax, k_min=kmin, kw_min=kw, s_min=smin)


# Grade A head columns, ISO 4017:2022 Tables 1 and 2 (= ISO 4014:2022 Tables 1 to 3).
# fmt: off
#               dw     e       k max   k min   kw     s min
_A = {
    "M1.6": _g(2.54,  3.41,  1.225,  0.975,  0.68,  3.02),
    "M2":   _g(3.34,  4.32,  1.525,  1.275,  0.89,  3.82),
    "M2.5": _g(4.34,  5.45,  1.825,  1.575,  1.10,  4.82),
    "M3":   _g(4.84,  6.01,  2.125,  1.875,  1.31,  5.32),
    "M3.5": _g(5.34,  6.58,  2.525,  2.275,  1.59,  5.82),
    "M4":   _g(6.20,  7.66,  2.925,  2.675,  1.87,  6.78),
    "M5":   _g(7.20,  8.79,  3.65,   3.35,   2.35,  7.78),
    "M6":   _g(8.88,  11.05, 4.15,   3.85,   2.70,  9.78),
    "M7":   _g(9.63,  12.12, 4.95,   4.65,   3.26,  10.73),
    "M8":   _g(11.63, 14.38, 5.45,   5.15,   3.61,  12.73),
    "M10":  _g(14.63, 17.77, 6.58,   6.22,   4.35,  15.73),
    "M12":  _g(16.63, 20.03, 7.68,   7.32,   5.12,  17.73),
    "M14":  _g(19.64, 23.36, 8.98,   8.62,   6.03,  20.67),
    "M16":  _g(22.49, 26.75, 10.18,  9.82,   6.87,  23.67),
    "M18":  _g(25.34, 30.14, 11.715, 11.285, 7.90,  26.67),
    "M20":  _g(28.19, 33.53, 12.715, 12.285, 8.60,  29.67),
    "M22":  _g(31.71, 37.72, 14.215, 13.785, 9.65,  33.38),
    "M24":  _g(33.61, 39.98, 15.215, 14.785, 10.35, 35.38),
}

# Grade B head columns, ISO 4017:2022 Tables 3 and 4 (= ISO 4014:2022 Table 4
# for M16 to M27 and ISO 4014:2011 Table 1 for M30 to M64).
#               dw     e       k max   k min   kw     s min
_B = {
    "M16":  _g(22.00, 26.17,  10.29, 9.71,  6.80,  23.16),
    "M18":  _g(24.85, 29.56,  11.85, 11.15, 7.81,  26.16),
    "M20":  _g(27.70, 32.95,  12.85, 12.15, 8.51,  29.16),
    "M22":  _g(31.35, 37.29,  14.35, 13.65, 9.56,  33.00),
    "M24":  _g(33.25, 39.55,  15.35, 14.65, 10.26, 35.00),
    "M27":  _g(38.00, 45.20,  17.35, 16.65, 11.66, 40.00),
    "M30":  _g(42.75, 50.85,  19.12, 18.28, 12.80, 45.00),
    "M33":  _g(46.55, 55.37,  21.42, 20.58, 14.41, 49.00),
    "M36":  _g(51.11, 60.79,  22.92, 22.08, 15.46, 53.80),
    "M39":  _g(55.86, 66.44,  25.42, 24.58, 17.21, 58.80),
    "M42":  _g(59.95, 71.30,  26.42, 25.58, 17.91, 63.10),
    "M45":  _g(64.70, 76.95,  28.42, 27.58, 19.31, 68.10),
    "M48":  _g(69.45, 82.60,  30.42, 29.58, 20.71, 73.10),
    "M52":  _g(74.20, 88.25,  33.50, 32.50, 22.75, 78.10),
    "M56":  _g(78.66, 93.56,  35.50, 34.50, 24.15, 82.80),
    "M60":  _g(83.41, 99.21,  38.50, 37.50, 26.25, 87.80),
    "M64":  _g(88.16, 104.86, 40.50, 39.50, 27.65, 92.80),
}


def _row(size, d, P, c_max, c_min, da_max, k_nom, r_min, s_nom, b1, b2, b3,
         l4014, l4017):
    return SizeData(
        size=size, d=d, P=P, c_max=c_max, c_min=c_min, da_max=da_max,
        k_nom=k_nom, r_min=r_min, s_nom=s_nom, A=_A.get(size), B=_B.get(size),
        b=(b1, b2, b3), l4014=l4014, l4017=l4017,
    )


# b: None where no ISO 4014:2022 standard length falls in that band.
# The M33 b1 = 72 is derived (2d + 6), see the module docstring.
# l4014 for M30 to M64 is derived from the ISO 4014:2022 rules.
#      size    d    P     c max c min da    k nom r min s     b1   b2    b3     ISO 4014    ISO 4017
SIZES: dict[str, SizeData] = {r.size: r for r in [
    _row("M1.6", 1.6, 0.35, 0.25, 0.10, 2.0,  1.1,  0.10, 3.2,  9,   None, None, (12, 16),   (3, 16)),
    _row("M2",   2,   0.4,  0.25, 0.10, 2.6,  1.4,  0.10, 4,    10,  None, None, (16, 20),   (4, 20)),
    _row("M2.5", 2.5, 0.45, 0.25, 0.10, 3.1,  1.7,  0.10, 5,    11,  None, None, (16, 25),   (5, 25)),
    _row("M3",   3,   0.5,  0.40, 0.15, 3.6,  2,    0.10, 5.5,  12,  None, None, (20, 30),   (6, 30)),
    _row("M3.5", 3.5, 0.6,  0.40, 0.15, 4.1,  2.4,  0.10, 6,    13,  None, None, (20, 35),   (8, 35)),
    _row("M4",   4,   0.7,  0.40, 0.15, 4.7,  2.8,  0.20, 7,    14,  None, None, (25, 40),   (8, 40)),
    _row("M5",   5,   0.8,  0.50, 0.15, 5.7,  3.5,  0.20, 8,    16,  None, None, (25, 50),   (10, 50)),
    _row("M6",   6,   1.0,  0.50, 0.15, 6.8,  4,    0.25, 10,   18,  None, None, (30, 60),   (12, 60)),
    _row("M7",   7,   1.0,  0.60, 0.15, 7.8,  4.8,  0.25, 11,   20,  None, None, (35, 70),   (16, 70)),
    _row("M8",   8,   1.25, 0.60, 0.15, 9.2,  5.3,  0.40, 13,   22,  None, None, (40, 80),   (16, 80)),
    _row("M10",  10,  1.5,  0.60, 0.15, 11.2, 6.4,  0.40, 16,   26,  None, None, (45, 100),  (20, 100)),
    _row("M12",  12,  1.75, 0.60, 0.15, 13.7, 7.5,  0.60, 18,   30,  None, None, (50, 120),  (25, 120)),
    _row("M14",  14,  2.0,  0.60, 0.15, 15.7, 8.8,  0.60, 21,   34,  40,   None, (55, 140),  (30, 140)),
    _row("M16",  16,  2.0,  0.80, 0.20, 17.7, 10,   0.60, 24,   38,  44,   None, (65, 160),  (30, 160)),
    _row("M18",  18,  2.5,  0.80, 0.20, 20.2, 11.5, 0.60, 27,   42,  48,   None, (70, 180),  (35, 180)),
    _row("M20",  20,  2.5,  0.80, 0.20, 22.4, 12.5, 0.80, 30,   46,  52,   None, (80, 200),  (40, 200)),
    _row("M22",  22,  2.5,  0.80, 0.20, 24.4, 14,   0.80, 34,   50,  56,   69,   (90, 220),  (45, 200)),
    _row("M24",  24,  3.0,  0.80, 0.20, 26.4, 15,   0.80, 36,   54,  60,   73,   (90, 240),  (50, 200)),
    _row("M27",  27,  3.0,  0.80, 0.20, 30.4, 17,   1.0,  41,   60,  66,   79,   (100, 260), (55, 200)),
    _row("M30",  30,  3.5,  0.80, 0.20, 33.4, 18.7, 1.0,  46,   66,  72,   85,   (110, 300), (60, 200)),
    _row("M33",  33,  3.5,  0.80, 0.20, 36.4, 21,   1.0,  50,   72,  78,   91,   (120, 320), (65, 200)),
    _row("M36",  36,  4.0,  0.80, 0.20, 39.4, 22.5, 1.0,  55,   None, 84,  97,   (140, 360), (70, 200)),
    _row("M39",  39,  4.0,  1.0,  0.30, 42.4, 25,   1.0,  60,   None, 90,  103,  (150, 380), (80, 200)),
    _row("M42",  42,  4.5,  1.0,  0.30, 45.6, 26,   1.2,  65,   None, 96,  109,  (160, 420), (80, 200)),
    _row("M45",  45,  4.5,  1.0,  0.30, 48.6, 28,   1.2,  70,   None, 102, 115,  (160, 440), (90, 200)),
    _row("M48",  48,  5.0,  1.0,  0.30, 52.6, 30,   1.6,  75,   None, 108, 121,  (180, 480), (100, 200)),
    _row("M52",  52,  5.0,  1.0,  0.30, 56.6, 33,   1.6,  80,   None, 116, 129,  (200, 500), (100, 200)),
    _row("M56",  56,  5.5,  1.0,  0.30, 63.0, 35,   2.0,  85,   None, None, 137, (220, 500), (110, 200)),
    _row("M60",  60,  5.5,  1.0,  0.30, 67.0, 38,   2.0,  90,   None, None, 145, (220, 500), (120, 200)),
    _row("M64",  64,  6.0,  1.0,  0.30, 71.0, 40,   2.0,  95,   None, None, 153, (220, 500), (120, 200)),
]}
# fmt: on


@dataclass(frozen=True)
class ThreadSize:
    """One entry of a standard's size select: the head and length row of
    the nominal diameter plus the thread pitch actually cut.

    The coarse standards (ISO 4014 / 4017) have one entry per row of
    SIZES. The fine pitch standards (ISO 8765 / 8676) use the same rows
    with one entry per listed pitch (hexscrew_fine_data.py).
    """

    key: str           # select value: "M8" (coarse) or "M10x1.25" (fine)
    sd: SizeData       # head, b and length data of the nominal diameter
    P: float           # pitch of the thread
    preferred: bool
    fine: bool = False

    @property
    def name(self) -> str:
        """Size as written in designations: "M8", or "M10 x 1.25" for fine."""
        return f"{self.sd.size} x {self.P:g}" if self.fine else self.key

    @property
    def label(self) -> str:
        """Option label of the size select."""
        return f"{self.sd.size} x {self.P:g}" + ("" if self.preferred else " (non-preferred)")


# Coarse thread entries, one per row.
THREAD_SIZES: dict[str, ThreadSize] = {
    s: ThreadSize(s, sd, sd.P, sd.preferred) for s, sd in SIZES.items()
}

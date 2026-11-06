"""Dimension table for ISO 4032, hexagon regular nuts (style 1).

Sources:

* M5 to M39 (including the non-preferred M7, added in the 2023 edition):
  ISO 4032:2023 Tables 1 and 2. These give da max, dw min and mw min to
  two decimals.
* M1.6 to M4 and M42 to M64: ISO 4032:2023 moved these sizes to the
  informative Annex A, whose values are not included here. Their values
  come from ISO 4032:1999 Tables 1 and 2. The 2023 edition says that it
  changed dw min for D <= M5 from s min - IT16 to s min - IT15, so the
  dw min of M1.6 to M4 here (1999 values) may be a little smaller than in
  the 2023 Annex A. dw only places the bearing-face chamfer.
* Cross-check: m max and s for every size match the ISO 4032 columns of
  bd_warehouse's hex_nut_parameters.csv. For M5 to M39 the 1999 and 2023
  tables agree except for the extra decimals.

e is not stored as a model value: the model uses the exact hexagon across
corners e = s / cos 30 deg. e min from the standard is kept for the
dimension table.

All values are in millimetres. The field names say which limit a value is
(``m_max``, ``dw_min``, ...). da min is always D.
"""

from __future__ import annotations

from dataclasses import dataclass

# Countersink at both bore ends: ISO 4032 Figure 1 allows q = 90 to 120 deg.
COUNTERSINK_ANGLE = 120.0
# Corner chamfer on both faces: ISO 4032 Figure 1 allows beta = 15 to 30 deg.
CHAMFER_ANGLE = 30.0


@dataclass(frozen=True)
class SizeData:
    size: str          # designation, e.g. "M8"
    D: float           # nominal thread diameter
    P: float           # coarse thread pitch
    da_max: float      # countersink diameter on the faces
    dw_min: float      # bearing face diameter
    e_min: float       # width across corners
    m_max: float       # nut height
    m_min: float
    mw_min: float      # wrenching height
    s_max: float       # width across flats (s nom = s max)
    s_min: float
    preferred: bool    # False for the sizes the standard puts in brackets
    edition: str       # edition the row is taken from
    fine: bool = False  # fine pitch row (ISO 8673); `size` is then e.g. "M10x1.25"

    @property
    def name(self) -> str:
        """Size as written in designations: "M8", or "M10 x 1.25" for fine."""
        return f"M{self.D:g} x {self.P:g}" if self.fine else self.size

    @property
    def label(self) -> str:
        """Option label of the size select."""
        return f"M{self.D:g} x {self.P:g}" + ("" if self.preferred else " (non-preferred)")

    @property
    def da_min(self) -> float:
        return self.D

    @property
    def s_nom(self) -> float:
        return self.s_max

    @property
    def e_nom(self) -> float:
        """Across corners of the exact hexagon of width s nom."""
        return self.s_nom * 2 / 3**0.5

    @property
    def in_annex(self) -> bool:
        """Sizes ISO 4032:2023 (and ISO 8673:2023) list only in their
        informative Annex A."""
        return not 5 <= self.D <= 39


def _row(size, P, da_max, dw_min, e_min, m_max, m_min, mw_min, s_max, s_min,
         preferred=True, edition="2023"):
    return SizeData(size, float(size[1:]), P, da_max, dw_min, e_min, m_max, m_min,
                    mw_min, s_max, s_min, preferred, edition)


_ROWS = [
    #     size    P     da max  dw min  e min   m max  m min  mw min  s max  s min
    _row("M1.6", 0.35, 1.84,   2.4,    3.41,   1.30,  1.05,  0.8,    3.20,  3.02, edition="1999"),
    _row("M2",   0.4,  2.3,    3.1,    4.32,   1.60,  1.35,  1.1,    4.00,  3.82, edition="1999"),
    _row("M2.5", 0.45, 2.9,    4.1,    5.45,   2.00,  1.75,  1.4,    5.00,  4.82, edition="1999"),
    _row("M3",   0.5,  3.45,   4.6,    6.01,   2.40,  2.15,  1.7,    5.50,  5.32, edition="1999"),
    _row("M3.5", 0.6,  4.0,    5.0,    6.58,   2.80,  2.55,  2.0,    6.00,  5.82, False, "1999"),
    _row("M4",   0.7,  4.6,    5.9,    7.66,   3.20,  2.90,  2.3,    7.00,  6.78, edition="1999"),
    _row("M5",   0.8,  5.75,   7.20,   8.79,   4.70,  4.40,  3.52,   8.00,  7.78),
    _row("M6",   1.0,  6.75,   8.88,   11.05,  5.20,  4.90,  3.92,   10.00, 9.78),
    _row("M7",   1.0,  7.75,   9.63,   12.12,  6.50,  6.14,  4.91,   11.00, 10.73, False),
    _row("M8",   1.25, 8.75,   11.63,  14.38,  6.80,  6.44,  5.15,   13.00, 12.73),
    _row("M10",  1.5,  10.80,  14.63,  17.77,  8.40,  8.04,  6.43,   16.00, 15.73),
    _row("M12",  1.75, 12.96,  16.63,  20.03,  10.80, 10.37, 8.30,   18.00, 17.73),
    _row("M14",  2.0,  15.12,  19.64,  23.36,  12.80, 12.10, 9.68,   21.00, 20.67, False),
    _row("M16",  2.0,  17.28,  22.49,  26.75,  14.80, 14.10, 11.28,  24.00, 23.67),
    _row("M18",  2.5,  19.44,  24.85,  29.56,  15.80, 15.10, 12.08,  27.00, 26.16, False),
    _row("M20",  2.5,  21.60,  27.70,  32.95,  18.00, 16.90, 13.52,  30.00, 29.16),
    _row("M22",  2.5,  23.76,  31.35,  37.29,  19.40, 18.10, 14.48,  34.00, 33.00, False),
    _row("M24",  3.0,  25.92,  33.25,  39.55,  21.50, 20.20, 16.16,  36.00, 35.00),
    _row("M27",  3.0,  29.16,  38.00,  45.20,  23.80, 22.50, 18.00,  41.00, 40.00, False),
    _row("M30",  3.5,  32.40,  42.75,  50.85,  25.60, 24.30, 19.44,  46.00, 45.00),
    _row("M33",  3.5,  35.64,  46.55,  55.37,  28.70, 27.40, 21.92,  50.00, 49.00, False),
    _row("M36",  4.0,  38.88,  51.11,  60.79,  31.00, 29.40, 23.52,  55.00, 53.80),
    _row("M39",  4.0,  42.12,  55.86,  66.44,  33.40, 31.80, 25.44,  60.00, 58.80, False),
    _row("M42",  4.5,  45.4,   60.0,   71.3,   34.0,  32.4,  25.9,   65.0,  63.1, edition="1999"),
    _row("M45",  4.5,  48.6,   64.7,   76.95,  36.0,  34.4,  27.5,   70.0,  68.1, False, "1999"),
    _row("M48",  5.0,  51.8,   69.5,   82.6,   38.0,  36.4,  29.1,   75.0,  73.1, edition="1999"),
    _row("M52",  5.0,  56.2,   74.2,   88.25,  42.0,  40.4,  32.3,   80.0,  78.1, False, "1999"),
    _row("M56",  5.5,  60.5,   78.7,   93.56,  45.0,  43.4,  34.7,   85.0,  82.8, edition="1999"),
    _row("M60",  5.5,  64.8,   83.4,   99.21,  48.0,  46.4,  37.1,   90.0,  87.8, False, "1999"),
    _row("M64",  6.0,  69.1,   88.2,   104.86, 51.0,  49.1,  39.3,   95.0,  92.8, edition="1999"),
]

SIZES: dict[str, SizeData] = {r.size: r for r in _ROWS}

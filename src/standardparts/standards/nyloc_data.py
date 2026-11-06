"""Dimension tables for ISO 7040 and ISO 10511, prevailing torque hexagon
nuts with non-metallic insert ("nyloc"): ISO 7040 regular height (body of
ISO 4032), ISO 10511 thin (body of ISO 4035).

Sources:

* ISO 7040: ISO 7040:2012 Table 1, M3 to M36 with the non-preferred M14.
  Cross-checked against ISO/DIS 7040:2016 Table 1 (identical for every
  preferred size) and fasten.it's DIN EN ISO 7040 page (P, s, h, m min
  and e min agree; fasten.it has a typo e min 6.1 for M3).
* ISO 10511: ISO 10511:2012 Table 1, corrected version (French edition),
  M3 to M36 with M14. Cross-checked against fasten.it's DIN EN
  ISO 10511 page (e min, s, m min, h max and h min agree; fasten.it has a
  typo P 1.75 for M10).
* The 2025 editions of both standards (M3 to M39) were not available and
  were not used. ISO/DIS 7040:2016 added non-preferred sizes
  (M3.5, M7, M18, M22, M27, M33, M39); they are not included because the
  final values could not be checked.
* da, dw and mw for both standards come from the 2012 ISO tables only.

The standards fix s, e, h, m min, mw min, dw and da. The prevailing torque
element is "shape at the discretion of the manufacturer" (Figure 1 a), so
these model values are derived, not standardised:

* Hex height: m max of the plain nut the standard is based on (ISO 4032
  for ISO 7040, ISO 4035 for ISO 10511). Both tables give only m min,
  which equals the plain nut's m min.
* Collar (crimped top holding the insert): outer diameter
  dc = da + COLLAR_OD (dw - da), so it stays inside dw <= s as in Figure 1.
  Insert / collar bore di = da + INSERT_OD (dw - da). Collar wall and
  crimped lip thickness t = (dc - di) / 2, with the top outer edge rounded
  at radius t. Lip opening dl = (D + di) / 2, so the screw passes freely.
* Insert: polyamide ring from the top of the hex up to the lip, bore
  D1 - INSERT_BORE_SHRINK P (a little under the basic minor diameter D1,
  so the screw forms its thread in the insert).

All values are in millimetres.
"""

from __future__ import annotations

from dataclasses import dataclass

from .iso4032_data import SIZES as ISO4032_SIZES
from .iso4035_data import SIZES as ISO4035_SIZES

# Bearing-face and top hex corner chamfer: Figure 1 allows beta = 15 to 30 deg.
CHAMFER_ANGLE = 15.0
# Countersinks: Figure 1 allows theta = 90 to 120 deg.
COUNTERSINK_ANGLE = 120.0
# Model proportions of the prevailing torque element (see the docstring).
COLLAR_OD = 0.85
INSERT_OD = 0.3
INSERT_BORE_SHRINK = 0.1


@dataclass(frozen=True)
class NylocData:
    size: str          # designation, e.g. "M8"
    D: float           # nominal thread diameter
    P: float           # coarse thread pitch
    da_max: float      # countersink diameter on the bearing face
    dw_min: float      # bearing face diameter
    e_min: float       # width across corners
    h_max: float       # overall nut height, including the collar
    h_min: float
    m_min: float       # height of the metal thread
    mw_min: float      # wrenching height
    s_max: float       # width across flats (s nom = s max)
    s_min: float
    m_hex: float       # model hex height: m max of the plain nut
    preferred: bool = True

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
    def h(self) -> float:
        """Modeled overall height."""
        return self.h_max

    @property
    def dc(self) -> float:
        """Model collar outside diameter."""
        return self.da_max + COLLAR_OD * (self.dw_min - self.da_max)

    @property
    def di(self) -> float:
        """Model insert outside diameter = collar bore."""
        return self.da_max + INSERT_OD * (self.dw_min - self.da_max)

    @property
    def wall(self) -> float:
        """Model collar wall and lip thickness."""
        return (self.dc - self.di) / 2

    @property
    def dl(self) -> float:
        """Model lip opening diameter."""
        return (self.D + self.di) / 2

    @property
    def d_insert(self) -> float:
        """Model insert bore, a little under the basic minor diameter D1."""
        D1 = self.D - 1.25 * 3**0.5 / 2 * self.P
        return D1 - INSERT_BORE_SHRINK * self.P

    @property
    def insert_height(self) -> float:
        return self.h - self.wall - self.m_hex


def _rows(base, rows):
    out = {}
    for (size, P, da_max, dw_min, e_min, h_max, h_min, m_min, mw_min, s_max, s_min) in rows:
        out[size] = NylocData(
            size, float(size[1:]), P, da_max, dw_min, e_min, h_max, h_min, m_min,
            mw_min, s_max, s_min, base[size].m_max, size != "M14",
        )
    return out


ISO7040_SIZES: dict[str, NylocData] = _rows(ISO4032_SIZES, [
    # size    P     da max dw min e min  h max  h min  m min  mw min s max  s min
    ("M3",   0.5,  3.45,  4.57,  6.01,  4.50,  4.02,  2.15,  1.72,  5.50,  5.32),
    ("M4",   0.7,  4.60,  5.88,  7.66,  6.00,  5.52,  2.90,  2.32,  7.00,  6.78),
    ("M5",   0.8,  5.75,  6.88,  8.79,  6.80,  6.22,  4.40,  3.52,  8.00,  7.78),
    ("M6",   1.0,  6.75,  8.88,  11.05, 8.00,  7.42,  4.90,  3.92,  10.00, 9.78),
    ("M8",   1.25, 8.75,  11.63, 14.38, 9.50,  8.92,  6.44,  5.15,  13.00, 12.73),
    ("M10",  1.5,  10.80, 14.63, 17.77, 11.90, 11.20, 8.04,  6.43,  16.00, 15.73),
    ("M12",  1.75, 13.00, 16.63, 20.03, 14.90, 14.20, 10.37, 8.30,  18.00, 17.73),
    ("M14",  2.0,  15.10, 19.64, 23.36, 17.00, 15.90, 12.10, 9.68,  21.00, 20.67),
    ("M16",  2.0,  17.30, 22.49, 26.75, 19.10, 17.80, 14.10, 11.28, 24.00, 23.67),
    ("M20",  2.5,  21.60, 27.70, 32.95, 22.80, 20.70, 16.90, 13.52, 30.00, 29.16),
    ("M24",  3.0,  25.90, 33.25, 39.55, 27.10, 25.00, 20.20, 16.16, 36.00, 35.00),
    ("M30",  3.5,  32.40, 42.75, 50.85, 32.60, 30.10, 24.30, 19.44, 46.00, 45.00),
    ("M36",  4.0,  38.90, 51.11, 60.79, 38.90, 36.40, 29.40, 23.52, 55.00, 53.80),
])

ISO10511_SIZES: dict[str, NylocData] = _rows(ISO4035_SIZES, [
    # size    P     da max dw min e min  h max  h min  m min  mw min s max  s min
    ("M3",   0.5,  3.45,  4.56,  6.01,  3.90,  3.42,  1.55,  1.24,  5.50,  5.32),
    ("M4",   0.7,  4.60,  5.90,  7.66,  5.00,  4.52,  1.95,  1.56,  7.00,  6.78),
    ("M5",   0.8,  5.75,  6.90,  8.79,  5.00,  4.52,  2.45,  1.96,  8.00,  7.78),
    ("M6",   1.0,  6.75,  8.90,  11.05, 6.00,  5.52,  2.90,  2.32,  10.00, 9.78),
    ("M8",   1.25, 8.75,  11.60, 14.38, 6.76,  6.18,  3.70,  2.96,  13.00, 12.73),
    ("M10",  1.5,  10.80, 14.60, 17.77, 8.56,  7.98,  4.70,  3.76,  16.00, 15.73),
    ("M12",  1.75, 13.00, 16.60, 20.03, 10.23, 9.53,  5.70,  4.56,  18.00, 17.73),
    ("M14",  2.0,  15.10, 19.60, 23.35, 11.32, 10.22, 6.42,  5.14,  21.00, 20.67),
    ("M16",  2.0,  17.30, 22.50, 26.75, 12.42, 11.32, 7.42,  5.94,  24.00, 23.67),
    ("M20",  2.5,  21.60, 27.70, 32.95, 14.90, 13.10, 9.10,  7.28,  30.00, 29.16),
    ("M24",  3.0,  25.90, 33.20, 39.55, 17.80, 16.00, 10.90, 8.72,  36.00, 35.00),
    ("M30",  3.5,  32.40, 42.80, 50.85, 22.20, 20.10, 13.90, 11.12, 46.00, 45.00),
    ("M36",  4.0,  38.90, 51.10, 60.79, 25.50, 23.40, 16.90, 13.52, 55.00, 53.80),
])

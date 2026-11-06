"""Dimension table for ISO 2338:1997, parallel pins of unhardened steel and
austenitic stainless steel.

Sources:

* ISO 2338:1997 Table 1 and Figure 1, as published in SIST EN ISO
  2338:2001 (identical text): d, c and the commercial length range of
  every diameter (the area between the bold stepped lines).
* Figure 1: both ends have the same chamfer of axial length c at
  approximately 15 deg to the pin surface. "Radius and dimpled pin end
  permissible" as an optional end shape at the manufacturer's discretion.
* Scope: d from 0.6 to 50 mm inclusive. Diameter tolerance m6 or h8
  ("other tolerances as agreed"). For nominal lengths above 200 mm the
  standard steps in 20 mm, but no diameter's commercial range goes past
  200 mm, so the table here ends at 200.
* d and c cross-checked against the ISO 2338 table on boltport.com
  (ferrobend): all 20 rows agree. The per-diameter length ranges come from
  the standard's own table only (no second source that assigns ranges to
  diameters was found; fasten.it gives its tables only as images). They
  follow the usual pattern (each range starts about 2d to 3d and the lower
  bound never cuts into the two chamfers, 2c < l_min), which a test checks.

ISO 286-2 limit deviations for m6 and h8 (used only for the dimension
table, not for the geometry): the 3 to 50 mm rows were cross-checked
against the ISO 286-2 shaft table on cadforum.cz. The "up to 3 mm" row
(m6 +2/+8 um, h8 0/-14 um, i.e. IT6 = 6 um and IT8 = 14 um) is from
ISO 286-1/-2 and was not cross-checked against a second source here.

All values are in millimetres unless noted.
"""

from __future__ import annotations

from dataclasses import dataclass

# Nominal lengths l of Table 1 (up to 200 mm).
LENGTH_SERIES: tuple[float, ...] = (
    2, 3, 4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 35, 40,
    45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 120, 140, 160, 180, 200,
)

CHAMFER_ANGLE = 15.0  # deg, ~15 deg to the pin surface (Figure 1)

TOLERANCES = ("m6", "h8")

# ISO 286-2 limit deviations in micrometres for shafts, as
# (upper nominal size of the band, {class: (lower dev., upper dev.)}).
# A band covers "over the previous upper size, up to and including this one".
ISO286_BANDS: tuple[tuple[float, dict[str, tuple[int, int]]], ...] = (
    (3,  {"m6": (2, 8),  "h8": (-14, 0)}),
    (6,  {"m6": (4, 12), "h8": (-18, 0)}),
    (10, {"m6": (6, 15), "h8": (-22, 0)}),
    (18, {"m6": (7, 18), "h8": (-27, 0)}),
    (30, {"m6": (8, 21), "h8": (-33, 0)}),
    (50, {"m6": (9, 25), "h8": (-39, 0)}),
)


def deviations_um(d: float, tolerance: str) -> tuple[int, int]:
    """(lower, upper) limit deviation of d in micrometres (ISO 286-2)."""
    for upper, devs in ISO286_BANDS:
        if d <= upper:
            return devs[tolerance]
    raise ValueError(f"no ISO 286 band for d = {d}")


@dataclass(frozen=True)
class PinData:
    size: str      # designation of d, e.g. "6" or "0.6"
    d: float       # nominal diameter (tolerance m6 or h8)
    c: float       # end chamfer, axial length (approximate)
    l_min: float   # commercial length range
    l_max: float

    def standard_lengths(self) -> list[float]:
        return [l for l in LENGTH_SERIES if self.l_min <= l <= self.l_max]


# fmt: off
SIZES: dict[str, PinData] = {r.size: r for r in [
    PinData("0.6", 0.6, 0.12, 2,  6),
    PinData("0.8", 0.8, 0.16, 2,  8),
    PinData("1",   1,   0.2,  4,  10),
    PinData("1.2", 1.2, 0.25, 4,  12),
    PinData("1.5", 1.5, 0.3,  4,  16),
    PinData("2",   2,   0.35, 6,  20),
    PinData("2.5", 2.5, 0.4,  6,  24),
    PinData("3",   3,   0.5,  8,  30),
    PinData("4",   4,   0.63, 8,  40),
    PinData("5",   5,   0.8,  10, 50),
    PinData("6",   6,   1.2,  12, 60),
    PinData("8",   8,   1.6,  14, 80),
    PinData("10",  10,  2,    18, 95),
    PinData("12",  12,  2.5,  22, 140),
    PinData("16",  16,  3,    26, 180),
    PinData("20",  20,  3.5,  35, 200),
    PinData("25",  25,  4,    50, 200),
    PinData("30",  30,  5,    60, 200),
    PinData("40",  40,  6.3,  80, 200),
    PinData("50",  50,  8,    95, 200),
]}
# fmt: on

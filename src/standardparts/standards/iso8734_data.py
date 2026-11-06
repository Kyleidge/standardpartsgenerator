"""Dimension table for ISO 8734:1997, parallel pins of hardened steel and
martensitic stainless steel (dowel pins).

Sources:

* ISO 8734:1997 Table 1 (French edition). d, c and the nominal lengths
  are printed; each diameter's commercial length range is the area
  between the bold stepped lines of the table.
* Figure 1, as given in SIST EN ISO 8734:2001 (identical text): both
  ends have the same chamfer of axial length c at approximately 15 deg to
  the pin surface. A radius or dimpled end is permitted as an optional end
  shape at the manufacturer's discretion.
* Cross-checked against fasten.it (DIN EN ISO 8734, 1998): d, c and every
  commercial length range agree.

Type A (through hardened) and type B (case hardened) differ only in
material and heat treatment, not in shape. d has tolerance m6; the model
uses nominal d. Table 1 ends at l = 100 mm (longer lengths would step in
20 mm), and every diameter's commercial range ends at or below 100 mm.

All values are in millimetres.
"""

from __future__ import annotations

from dataclasses import dataclass

# Nominal lengths l of Table 1.
LENGTH_SERIES: tuple[float, ...] = (
    3, 4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 35, 40,
    45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100,
)

CHAMFER_ANGLE = 15.0  # deg, ~15 deg to the pin surface (Figure 1)


@dataclass(frozen=True)
class PinData:
    size: str      # designation of d, e.g. "6" or "1.5"
    d: float       # nominal diameter (tolerance m6)
    c: float       # end chamfer, axial length (approximate)
    l_min: float   # commercial length range
    l_max: float

    def standard_lengths(self) -> list[float]:
        return [l for l in LENGTH_SERIES if self.l_min <= l <= self.l_max]


# fmt: off
SIZES: dict[str, PinData] = {r.size: r for r in [
    PinData("1",   1,   0.2,  3,  10),
    PinData("1.5", 1.5, 0.3,  4,  16),
    PinData("2",   2,   0.35, 5,  20),
    PinData("2.5", 2.5, 0.4,  6,  24),
    PinData("3",   3,   0.5,  8,  30),
    PinData("4",   4,   0.63, 10, 40),
    PinData("5",   5,   0.8,  12, 50),
    PinData("6",   6,   1.2,  14, 60),
    PinData("8",   8,   1.6,  18, 80),
    PinData("10",  10,  2,    22, 100),
    PinData("12",  12,  2.5,  26, 100),
    PinData("16",  16,  3,    40, 100),
    PinData("20",  20,  3.5,  50, 100),
]}
# fmt: on

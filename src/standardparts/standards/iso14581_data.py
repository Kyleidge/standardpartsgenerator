"""Dimension table for ISO 14581, hexalobular socket countersunk flat head
screws (common head style) with reduced loadability, product grade A.

Source: ISO 14581:2013 Table 1, M2 to M10, including the length range and
the threaded-to-head line. For M2 and M2.5 the shortest length is taken as
3 mm (not confirmed).

Cross-checks: fasten.it's DIN EN ISO 14581 page (P, b, dk, k, t min / max
and the socket numbers agree), and the head dimensions are identical to
ISO 7046-1:2011 Table 1 (same common head style).

ISO 14581:2022 (second edition) is current. Its Table 1 was not available;
its foreword says the head dimensions were kept but that ds, k min and
r min were added, the underhead reinforcement of M5 to M10 became a cone,
partially threaded M2 to M4 were added and **the shortest standard lengths
were increased**. The 2013 lengths used here are therefore NOT verified
against the current edition (FreeCAD's table, of unstated origin, lists
e.g. M2 6 to 30 and M10 12 to 100). The underhead reinforcement is not
modeled (shank at d, like ISO 7046-1).

* The socket is ISO 10664; A ref in Table 1 is the socket's nominal A
  (Table 1 prints 7.95 for T45 where ISO 10664 has 7.93; the model uses
  ISO 10664). Penetration t min / max per size.
* l includes the head. Lengths above the dashed line are threaded to the
  head, b = l - (k + a): up to 30 mm for M2 to M3, 45 mm for M3.5 to M10.
  Longer screws have b min of thread.
* a max is not in Table 1; the figure notes give a max <= 2P (M2 to M4) and
  <= 2.5P (M5 to M10). The model threads to the head like ISO 7046-1.
* The underhead radius has only a maximum; the model uses r max / 2.

M3.5 and the lengths 14 and 55 are printed in parentheses.

All values in millimetres.
"""

from __future__ import annotations

from dataclasses import dataclass

LENGTH_SERIES: tuple[float, ...] = (
    3, 4, 5, 6, 8, 10, 12, 14, 16, 20, 25, 30, 35, 40, 45, 50, 55, 60,
)
NON_PREFERRED_LENGTHS = (14, 55)

HEAD_ANGLE = 90.0


@dataclass(frozen=True)
class SizeData:
    size: str
    d: float
    P: float
    b_min: float
    dk_theo: float
    dk_max: float
    dk_min: float
    k_max: float
    r_max: float
    x_max: float
    socket: int         # hexalobular socket No. (T6 ...)
    A_ref: float        # as printed in ISO 14581 Table 1
    t_max: float        # penetration depth
    t_min: float
    l_min: float
    l_max: float
    l_full_max: float
    preferred: bool = True

    @property
    def land_height(self) -> float:
        return (self.dk_theo - self.dk_max) / 2

    @property
    def r_model(self) -> float:
        return self.r_max / 2

    def standard_lengths(self) -> list[float]:
        return [l for l in LENGTH_SERIES if self.l_min <= l <= self.l_max]

    def is_fully_threaded(self, l: float) -> bool:
        return l <= self.l_full_max


# fmt: off
#            size    d    P     b   dk_th dk_max dk_min k     r    x     T   A     t_max t_min l_min l_max l_full
_ROWS = [
    SizeData("M2",   2,   0.4,  25, 4.4,  3.80,  3.50,  1.20, 0.5, 1.00, 6,  1.75, 0.64, 0.51, 3,  20, 30),
    SizeData("M2.5", 2.5, 0.45, 25, 5.5,  4.70,  4.40,  1.50, 0.6, 1.10, 8,  2.40, 0.79, 0.66, 3,  25, 30),
    SizeData("M3",   3,   0.5,  25, 6.3,  5.50,  5.20,  1.65, 0.8, 1.25, 10, 2.80, 0.83, 0.70, 4,  30, 30),
    SizeData("M3.5", 3.5, 0.6,  38, 8.2,  7.30,  6.94,  2.35, 0.9, 1.50, 15, 3.35, 1.32, 1.16, 5,  35, 45, False),
    SizeData("M4",   4,   0.7,  38, 9.4,  8.40,  8.04,  2.70, 1.0, 1.75, 20, 3.95, 1.53, 1.14, 5,  40, 45),
    SizeData("M5",   5,   0.8,  38, 10.4, 9.30,  8.94,  2.70, 1.3, 2.00, 25, 4.50, 1.51, 1.12, 6,  50, 45),
    SizeData("M6",   6,   1.0,  38, 12.6, 11.30, 10.87, 3.30, 1.5, 2.50, 30, 5.60, 1.78, 1.39, 8,  60, 45),
    SizeData("M8",   8,   1.25, 38, 17.3, 15.80, 15.37, 4.65, 2.0, 3.20, 45, 7.95, 2.54, 2.15, 10, 60, 45),
    SizeData("M10",  10,  1.5,  38, 20.0, 18.30, 17.78, 5.00, 2.5, 3.80, 50, 8.95, 2.80, 2.41, 12, 60, 45),
]
# fmt: on

SIZES: dict[str, SizeData] = {r.size: r for r in _ROWS}

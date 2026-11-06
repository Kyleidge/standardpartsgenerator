"""Dimension tables for hexagon socket set screws: ISO 4026 (flat point),
ISO 4027 (cone point), ISO 4028 (dog point) and ISO 4029 (cup point).

Sources:

* ISO 4026:2003, ISO 4027:2003 and ISO 4029:2003, Figure 1 and Table 1:
  every value below.
* Cross-checked against fasten.it (DIN EN ISO 4026 / 4027 / 4029,
  05-2004): P, dp max, dt max, dz max, s nom, e min, both t min values and
  the commercial-length ranges (their mass tables) all agree.

The three standards share the thread, socket (s, e, t) and length columns;
only the point differs. M1.6 to M24 is the range of the 2003 editions. The
2026 editions add M30 for steel; their tables were not available, so M30
is not offered.

Short lengths. Table 1 shades the shortest lengths of each size. For those
the socket-end chamfer is 120 deg instead of 90 deg, the socket depth is
the smaller t min, and (ISO 4027 only) the cone point is 120 deg instead
of 90 deg. The shaded cells below follow the tables' grey cell background
and were checked by eye only; the three standards shade slightly different
cells.

Figure 1 (all three): the socket end is chamfered down to df, which is
"approximately the minor thread diameter", at 90 deg (120 deg for short
lengths). The point end is a ~45 deg chamfer (flat and cup point) down to
dp / dz, or the cone at angle gamma down to dt (cone point). The cup is a
conical recess of approximately 120 deg.

ISO 4028 (dog point):

* ISO 4028:2003 Figure 1 and Table 1 (English and French editions):
  every value below, including the shaded cells and the bold stepped
  lines.
* Cross-checked against fasten.it (DIN EN ISO 4028, 05-2004, replaces
  DIN 915): P, dp, s, e, both t min values, z short / long dog and the
  commercial lengths (their mass table) all agree.
* The thread, s, e and t columns are identical to ISO 4026 (SOCKET below).
  dp is the same as the ISO 4026 flat point diameter (DP below).
* What differs: the commercial lengths start one step longer for M2 to
  M6 (LENGTH_RANGE_4028), the shaded cells are different (mostly the
  first two lengths of each size), and the dog length z depends on them:
  the short dog for shaded lengths (footnote d) and the long dog for the
  lengths below the shaded area (footnote e). The socket depth t follows
  the same shaded / unshaded rule as the other points, so ISO 4028 uses
  the short t on different lengths than ISO 4026.
* Figure 1: the dog is a cylinder of diameter dp and length z at the
  point end, joined to the thread by a ~45 deg cone, which applies only
  below the minor thread diameter (footnote b). The dog edges carry a
  "small radius" (footnote d); it is not dimensioned, and the model
  leaves those edges sharp. The model uses dp max and z max.

All values are in millimetres.
"""

from __future__ import annotations

from dataclasses import dataclass

# Nominal lengths l of Table 1 (identical in ISO 4026, 4027 and 4029).
LENGTH_SERIES: tuple[float, ...] = (
    2, 2.5, 3, 4, 5, 6, 8, 10, 12, 16, 20, 25, 30, 35, 40, 45, 50, 55, 60,
)


@dataclass(frozen=True)
class SocketData:
    """Thread, socket and length data shared by ISO 4026, 4027 and 4029."""

    size: str
    d: float
    P: float
    e_min: float
    s_nom: float
    s_max: float
    s_min: float
    t_min_short: float   # socket depth for the shaded (short) lengths
    t_min_long: float    # socket depth for all longer lengths
    l_min: float         # commercial length range (bold stepped lines)
    l_max: float

    def standard_lengths(self) -> list[float]:
        return [l for l in LENGTH_SERIES if self.l_min <= l <= self.l_max]


# fmt: off
#                       size    d    P     e_min   s nom  s max   s min   t short t long l_min l_max
SOCKET: dict[str, SocketData] = {r.size: r for r in [
    SocketData("M1.6", 1.6, 0.35, 0.809,  0.7, 0.724,  0.710,  0.7, 1.5,  2,   8),
    SocketData("M2",   2,   0.4,  1.011,  0.9, 0.913,  0.887,  0.8, 1.7,  2,   10),
    SocketData("M2.5", 2.5, 0.45, 1.454,  1.3, 1.300,  1.275,  1.2, 2,    2.5, 12),
    SocketData("M3",   3,   0.5,  1.733,  1.5, 1.58,   1.52,   1.2, 2,    3,   16),
    SocketData("M4",   4,   0.7,  2.303,  2,   2.08,   2.02,   1.5, 2.5,  4,   20),
    SocketData("M5",   5,   0.8,  2.873,  2.5, 2.58,   2.52,   2,   3,    5,   25),
    SocketData("M6",   6,   1.0,  3.443,  3,   3.08,   3.02,   2,   3.5,  6,   30),
    SocketData("M8",   8,   1.25, 4.583,  4,   4.095,  4.020,  3,   5,    8,   40),
    SocketData("M10",  10,  1.5,  5.723,  5,   5.14,   5.02,   4,   6,    10,  50),
    SocketData("M12",  12,  1.75, 6.863,  6,   6.14,   6.02,   4.8, 8,    12,  60),
    SocketData("M16",  16,  2.0,  9.149,  8,   8.175,  8.025,  6.4, 10,   16,  60),
    SocketData("M20",  20,  2.5,  11.429, 10,  10.175, 10.025, 8,   12,   20,  60),
    SocketData("M24",  24,  3.0,  13.716, 12,  12.212, 12.032, 10,  15,   25,  60),
]}

# Flat point diameter dp (ISO 4026 Table 1): (max, min).
DP: dict[str, tuple[float, float]] = {
    "M1.6": (0.80, 0.55), "M2": (1.00, 0.75), "M2.5": (1.50, 1.25),
    "M3": (2.00, 1.75), "M4": (2.50, 2.25), "M5": (3.5, 3.2), "M6": (4.0, 3.7),
    "M8": (5.5, 5.2), "M10": (7.00, 6.64), "M12": (8.50, 8.14),
    "M16": (12.00, 11.57), "M20": (15.00, 14.57), "M24": (18.00, 17.57),
}

# Cone point tip diameter dt max (ISO 4027 Table 1).
DT_MAX: dict[str, float] = {
    "M1.6": 0.4, "M2": 0.5, "M2.5": 0.65, "M3": 0.75, "M4": 1, "M5": 1.25,
    "M6": 1.5, "M8": 2, "M10": 2.5, "M12": 3, "M16": 4, "M20": 5, "M24": 6,
}

# Cup point diameter dz (ISO 4029 Table 1): (max, min).
DZ: dict[str, tuple[float, float]] = {
    "M1.6": (0.80, 0.55), "M2": (1.00, 0.75), "M2.5": (1.20, 0.95),
    "M3": (1.40, 1.15), "M4": (2.00, 1.75), "M5": (2.50, 2.25),
    "M6": (3.00, 2.75), "M8": (5.0, 4.7), "M10": (6.0, 5.7),
    "M12": (8.00, 7.64), "M16": (10.00, 9.64), "M20": (14.00, 13.57),
    "M24": (16.00, 15.57),
}

# ISO 4028 dog length z: (max, min), short dog (shaded lengths) and long dog.
Z_SHORT: dict[str, tuple[float, float]] = {
    "M1.6": (0.65, 0.40), "M2": (0.75, 0.50), "M2.5": (0.88, 0.63),
    "M3": (1.00, 0.75), "M4": (1.25, 1.00), "M5": (1.50, 1.25),
    "M6": (1.75, 1.50), "M8": (2.25, 2.00), "M10": (2.75, 2.50),
    "M12": (3.25, 3.00), "M16": (4.3, 4.0), "M20": (5.3, 5.0),
    "M24": (6.3, 6.0),
}
Z_LONG: dict[str, tuple[float, float]] = {
    "M1.6": (1.05, 0.80), "M2": (1.25, 1.00), "M2.5": (1.50, 1.25),
    "M3": (1.75, 1.50), "M4": (2.25, 2.00), "M5": (2.75, 2.50),
    "M6": (3.25, 3.00), "M8": (4.3, 4.0), "M10": (5.3, 5.0),
    "M12": (6.3, 6.0), "M16": (8.36, 8.00), "M20": (10.36, 10.00),
    "M24": (12.43, 12.00),
}

# Commercial length range of ISO 4028 (bold stepped lines). The other three
# standards use SocketData.l_min / l_max.
LENGTH_RANGE_4028: dict[str, tuple[float, float]] = {
    "M1.6": (2, 8), "M2": (2.5, 10), "M2.5": (3, 12), "M3": (4, 16),
    "M4": (5, 20), "M5": (6, 25), "M6": (8, 30), "M8": (8, 40),
    "M10": (10, 50), "M12": (12, 60), "M16": (16, 60), "M20": (20, 60),
    "M24": (25, 60),
}

# Shaded (short-length) cells of Table 1, per standard and size. From M6
# up all three standards shade only the shortest commercial length.
_SHADED_LARGE = {"M6": (6,), "M8": (8,), "M10": (10,), "M12": (12,),
                 "M16": (16,), "M20": (20,), "M24": (25,)}
SHORT_LENGTHS: dict[str, dict[str, tuple[float, ...]]] = {
    "iso4026": {"M1.6": (2,), "M2": (2, 2.5, 3), "M2.5": (2.5, 3), "M3": (3,),
                "M4": (4,), "M5": (5,), **_SHADED_LARGE},
    "iso4027": {"M1.6": (2, 2.5), "M2": (2, 2.5, 3), "M2.5": (2.5, 3),
                "M3": (3, 4), "M4": (4, 5), "M5": (5, 6), **_SHADED_LARGE},
    "iso4029": {"M1.6": (2,), "M2": (2, 2.5), "M2.5": (2.5, 3), "M3": (3, 4),
                "M4": (4, 5), "M5": (5,), **_SHADED_LARGE},
    "iso4028": {"M1.6": (2, 2.5), "M2": (2.5, 3), "M2.5": (3, 4), "M3": (4, 5),
                "M4": (5, 6), "M5": (6,), "M6": (8,), "M8": (8, 10),
                "M10": (10, 12), "M12": (12, 16), "M16": (16, 20),
                "M20": (20, 25), "M24": (25, 30)},
}
# fmt: on


def length_range(standard_id: str, size: str) -> tuple[float, float]:
    """Commercial (l_min, l_max) of a size in the given standard."""
    if standard_id == "iso4028":
        return LENGTH_RANGE_4028[size]
    sd = SOCKET[size]
    return sd.l_min, sd.l_max


def standard_lengths(standard_id: str, size: str) -> list[float]:
    """Preferred lengths of a size in the given standard."""
    lo, hi = length_range(standard_id, size)
    return [l for l in LENGTH_SERIES if lo <= l <= hi]


def is_short(standard_id: str, size: str, l: float) -> bool:
    """True if length l falls in the shaded (short) area of Table 1.

    The table only shades preferred lengths. A custom length counts as short
    when it lies below the first preferred length that is not shaded, so the
    shallower socket is used whenever the screw is shorter than the shortest
    screw the long socket depth was specified for.
    """
    shaded = SHORT_LENGTHS[standard_id][size]
    longer = [x for x in standard_lengths(standard_id, size) if x > max(shaded)]
    return not longer or l < longer[0]

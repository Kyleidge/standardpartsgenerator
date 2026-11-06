"""Dimension table for ISO 8735:1997, parallel pins with internal thread of
hardened steel and martensitic stainless steel (extractable dowel pins).

Sources:

* ISO 8735:1997 Figure 1 and Table 1 (English edition): d1, a, c, d2, P,
  d3, t1, t2 min and t3 are from Table 1. The length rows of Table 1
  beyond l = 22 mm were not available.
* Commercial length ranges: fasten.it (DIN EN ISO 8735, 03-1998, the
  identical European adoption), whose commercial-items matrix gives the
  range of every d1. The nominal lengths are the same series as ISO 8734
  from 16 mm, continued in 20 mm steps from 100 to 200 mm.
* fasten.it also lists a, c, the thread, P, t1 and t2 ("c1", "c3", "c4"):
  all agree with ISO 8735 except c for d1 = 16, which fasten.it gives as
  4.7. The ISO value 4.6 is used.

Symbols follow the standard, which differ from ISO 8734: d1 is the pin
diameter (tolerance m6), d2 the internal thread (6H), d3 the diameter of
the counterbore at the hole mouth, t3 its depth, t1 the thread depth and
t2 min the depth of the drilled hole, all measured from the threaded end
face.

Figure 1, as modeled:

* Threaded end: edge chamfer of axial length a at ~15 deg to the pin
  surface (~75 deg to the end face). The hole mouth is a counterbore of
  diameter d3 and depth t3 followed by a 120 deg countersink down to the
  thread.
* Other end, type A (through hardened steel, martensitic stainless C1):
  "pin with crown", a chamfer at ~15 deg followed by a spherical crown of
  radius r = d1. Figure 1 dimensions c from the crown apex to the end of
  the chamfer, so c covers both; the model solves for the chamfer length
  that makes chamfer plus crown height equal c (derived).
* Other end, type B (case hardened steel): "flat pin", a plain ~15 deg
  chamfer of axial length c and a flat end face.
* The drill point angle is not given (the figure shows a conical drill
  point); 120 deg is used. The drilled hole is modeled at the basic minor
  diameter D1 of the thread, to depth t2 min.
* Footnote 1: "slight flat or small groove at the manufacturer's
  discretion" on the pin surface, for venting the blind hole. It is not
  dimensioned and is not what types A and B distinguish. The model offers
  it as an option: a flat over the full length at depth VENT_DEPTH * d1
  (an assumption, no standard or supplier dimension found).

All values are in millimetres.
"""

from __future__ import annotations

from dataclasses import dataclass

# Nominal lengths l (Table 1 from 16 mm; fasten.it for the full series).
LENGTH_SERIES: tuple[float, ...] = (
    16, 18, 20, 22, 24, 26, 28, 30, 32, 35, 40, 45, 50, 55, 60, 65, 70, 75,
    80, 85, 90, 95, 100, 120, 140, 160, 180, 200,
)

CHAMFER_ANGLE = 15.0       # deg to the pin surface, both ends (Figure 1)
COUNTERSINK_ANGLE = 120.0  # included angle below the counterbore (Figure 1)
DRILL_ANGLE = 120.0        # drill point of the blind hole (assumed)
VENT_DEPTH = 0.03          # venting flat depth as a fraction of d1 (assumed)


@dataclass(frozen=True)
class PinData:
    size: str      # designation of d1, e.g. "6"
    d1: float      # nominal pin diameter (tolerance m6)
    a: float       # threaded-end chamfer, axial length (approximate)
    c: float       # far-end chamfer (type A: chamfer + crown), axial length
    thread: str    # d2, e.g. "M4"
    D: float       # thread major diameter
    P: float       # pitch
    d3: float      # counterbore diameter at the hole mouth
    t1: float      # thread depth
    t2: float      # drilled hole depth, min.
    t3: float      # counterbore depth
    l_min: float   # commercial length range
    l_max: float

    def standard_lengths(self) -> list[float]:
        return [l for l in LENGTH_SERIES if self.l_min <= l <= self.l_max]


# fmt: off
#                   size  d1  a    c    thread   D   P     d3    t1  t2  t3   l_min l_max
SIZES: dict[str, PinData] = {r.size: r for r in [
    PinData("6",   6,   0.8, 2.1, "M4",  4,  0.7,  4.3,  6,  10, 1,   16,  60),
    PinData("8",   8,   1,   2.6, "M5",  5,  0.8,  5.3,  8,  12, 1.2, 18,  80),
    PinData("10",  10,  1.2, 3,   "M6",  6,  1.0,  6.4,  10, 16, 1.2, 22,  100),
    PinData("12",  12,  1.6, 3.8, "M6",  6,  1.0,  6.4,  12, 20, 1.2, 26,  120),
    PinData("16",  16,  2,   4.6, "M8",  8,  1.25, 8.4,  16, 25, 1.5, 32,  160),
    PinData("20",  20,  2.5, 6,   "M10", 10, 1.5,  10.5, 18, 28, 1.5, 40,  200),
    PinData("25",  25,  3,   6,   "M16", 16, 2.0,  17,   24, 35, 2,   50,  200),
    PinData("30",  30,  4,   7,   "M20", 20, 2.5,  21,   30, 40, 2,   60,  200),
    PinData("40",  40,  5,   8,   "M20", 20, 2.5,  21,   30, 40, 2.5, 80,  200),
    PinData("50",  50,  6.3, 10,  "M24", 24, 3.0,  25,   36, 50, 2.5, 100, 200),
]}
# fmt: on

# Types of Figure 1 / Table 2. Both share every dimension except the end shape.
TYPES: dict[str, str] = {
    "A": "Type A: crowned end, through hardened steel or martensitic stainless steel",
    "B": "Type B: flat end, case hardened steel",
}

"""Dimension table for ISO 7380-1:2022, hexagon socket button head screws.

Sources:

* Head, socket and shank dimensions: ISO 7380-1:2022 Table 1, M3 to M16.
  The tests check the table's own rules: dw min = 0.92 dk min and
  t max = k min - wb min.
* Thread length b: M3 to M12 as published for ISO 7380-1:2011 by Westfield
  Fasteners, fasteners.eu and Fuller Fasteners (18, 20, 22, 24, 28, 32, 36,
  44). The 2022 foreword says b was raised to 3d for M16, so M16 uses
  b = 48. Secondary sources; Table 2 of the 2022 edition was not available.
* Nominal lengths and the threaded-to-head boundary: the 2022 values were
  not available. The range per size and which lengths are threaded to the
  head come from GB/T 70.2-2015 (a modified adoption of ISO 7380-1:2011), as
  listed per length by GlobalFastener. The smallest lengths agree with the
  bd_warehouse ISO 7380-1 table. The 2022 foreword says the smallest and
  greatest standard lengths were amended; those changes are NOT reflected
  here and have not been verified.
* The 2011 data is threaded to the head exactly where the ISO 4762 rule
  gives ls min < d / 2 (lg max = l - b, ls min = lg max - 5P, ISO 7380-1
  Figure 1 note d). With b = 44 the rule reproduces every size; the tests
  check this. The model applies the same rule with M16 b = 48, so M16 is
  partially threaded from 70 mm instead of 65 mm. This is derived.

All values in millimetres. Where the standard gives a range, the field name
says which limit it is (``dk_max``, ``t_min``, ...).
"""

from __future__ import annotations

from dataclasses import dataclass

# Nominal lengths l listed for GB/T 70.2-2015 / ISO 7380-1:2011.
LENGTH_SERIES: tuple[float, ...] = (
    6, 8, 10, 12, 16, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 80, 90,
)


@dataclass(frozen=True)
class SizeData:
    size: str          # designation, e.g. "M8"
    d: float           # nominal thread diameter (= ds max)
    P: float           # coarse thread pitch
    b: float           # thread length (reference) for partially threaded screws
    da_max: float      # transition diameter of the underhead fillet
    dk_max: float      # head diameter
    dk_min: float
    dL_ref: float      # diameter of the flat on top of the dome
    ds_min: float      # shank diameter
    dw_min: float      # bearing face diameter (0.1 mm above the bearing face)
    e_min: float       # socket width across corners
    k_max: float       # head height
    k_min: float
    rf_max: float      # dome radius
    rf_min: float
    rs_min: float      # underhead radius, screws with a plain shank
    rt_min: float      # underhead radius, screws threaded to the head
    s_nom: float       # socket width across flats
    s_max: float
    s_min: float
    t_max: float       # socket depth
    t_min: float
    wb_min: float      # wall between socket bottom and bearing face
    l_min: float       # shortest standard length (see module docstring)
    l_max: float       # longest standard length (see module docstring)

    @property
    def ds_max(self) -> float:
        return self.d

    def standard_lengths(self) -> list[float]:
        return [l for l in LENGTH_SERIES if self.l_min <= l <= self.l_max]

    def thread_geometry(self, l: float) -> tuple[float | None, float | None]:
        """Return (ls_min, lg_max) for nominal length l.

        Both are None when the screw is threaded up to the head:
        lg max = l - b, ls min = lg max - 5P, and the screw is threaded to
        the head while ls min < d / 2 (see the module docstring).
        """
        lg_max = l - self.b
        ls_min = lg_max - 5 * self.P
        if ls_min < self.d / 2:
            return None, None
        return round(ls_min, 3), round(lg_max, 3)

    def is_fully_threaded(self, l: float) -> bool:
        return self.thread_geometry(l)[0] is None

    def underhead_radius(self, fully_threaded: bool) -> float:
        """Fillet radius used by the model.

        rs min for screws with a plain shank. For screws threaded to the head
        the standard asks for the larger rt min, but on a model whose shank
        is a cylinder at d that fillet would end outside da max for M4 to
        M16, so it is limited to (da max - d) / 2 (derived).
        """
        if not fully_threaded:
            return self.rs_min
        return round(min(self.rt_min, (self.da_max - self.d) / 2), 4)


# fmt: off
#            size   d   P     b   da    dk_max dk_min dL    ds_min dw_min e_min  k_max k_min rf_max rf_min rs    rt    s_nom s_max   s_min   t_max t_min wb    l_min l_max
_ROWS = [
    SizeData("M3",  3,  0.5,  18, 3.6,  5.70,  5.40,  2.6,  2.86,  4.97,  2.30,  1.65, 1.40, 3.70,  3.30,  0.10, 0.30, 2,    2.080,  2.020,  1.20, 1.04, 0.20, 6,  30),
    SizeData("M4",  4,  0.7,  20, 4.7,  7.60,  7.24,  3.8,  3.82,  6.66,  2.87,  2.20, 1.95, 4.60,  4.20,  0.20, 0.40, 2.5,  2.580,  2.520,  1.65, 1.30, 0.30, 6,  40),
    SizeData("M5",  5,  0.8,  22, 5.7,  9.50,  9.14,  5.0,  4.82,  8.41,  3.44,  2.75, 2.50, 5.75,  5.25,  0.20, 0.45, 3,    3.080,  3.020,  2.12, 1.56, 0.38, 8,  50),
    SizeData("M6",  6,  1.0,  24, 6.8,  10.50, 10.07, 6.0,  5.82,  9.26,  4.58,  3.30, 3.00, 6.15,  5.65,  0.25, 0.50, 4,    4.095,  4.020,  2.26, 2.08, 0.74, 10, 60),
    SizeData("M8",  8,  1.25, 28, 9.2,  14.00, 13.57, 7.7,  7.78,  12.48, 5.72,  4.40, 4.10, 7.95,  7.45,  0.40, 0.70, 5,    5.140,  5.020,  3.05, 2.60, 1.05, 12, 80),
    SizeData("M10", 10, 1.5,  32, 11.2, 17.50, 17.07, 10.0, 9.78,  15.70, 6.86,  5.50, 5.20, 9.80,  9.20,  0.40, 0.70, 6,    6.140,  6.020,  3.75, 3.12, 1.45, 16, 90),
    SizeData("M12", 12, 1.75, 36, 13.7, 21.00, 20.48, 12.0, 11.73, 18.84, 9.15,  6.60, 6.24, 11.20, 10.50, 0.60, 1.10, 8,    8.175,  8.025,  4.61, 4.16, 1.63, 20, 90),
    SizeData("M16", 16, 2.0,  48, 17.7, 28.00, 27.48, 16.0, 15.73, 25.28, 11.43, 8.80, 8.44, 15.30, 14.50, 0.60, 1.10, 10,   10.175, 10.025, 6.19, 5.20, 2.25, 25, 90),
]
# fmt: on

SIZES: dict[str, SizeData] = {r.size: r for r in _ROWS}

# b for M16 in ISO 7380-1:2011 (before the 2022 change to 3d); used by the
# tests to check the threaded-to-head rule against the 2011 length data.
B_2011 = {"M16": 44.0}

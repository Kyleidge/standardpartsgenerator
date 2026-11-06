"""Male drive ends of screwdriver bits, ISO 1173:2001 (forms A, C, E, G).

Source: ISO 1173:2001 Tables 1, 3, 5 and 7 and Figures 1, 3, 5 and 7
(French edition).

ISO 1173 specifies only the features that make drive ends interchangeable;
"details not given shall be chosen appropriately" (clause 2). What the
model takes from the figures, and what it chooses:

* All forms: d3 (tolerance h12) is the diameter at the bottom of the
  retaining groove, the groove's centre (forms A, C, G) or its flat bottom
  (form E) lies at l3 from the end face, and l1 min is the length of the
  drive end. The end of the hexagon forms is chamfered at about 30 deg to
  the axis over 1.5 mm (Figures 1, 3, 5).
* Form A (Figure 1): a hexagon s1 of length l5 at the end, then a collar d1
  with the round groove (radius r) at l3, ending at l1 in a shoulder with
  R 0.6 min. The R 0.4 min at the root of the hexagon is not modeled.
* Form C (Figure 3): a hexagon whose corners carry a V groove at l3,
  included angle beta 80 to 120 deg with a root radius r; d3 lies between
  s1 and e1, so the groove only notches the corners. The model uses beta =
  90 deg. Size 4 has a cross hole of 2 mm at l3 instead of the groove.
* Form E (Figure 5): a hexagon with a full round groove: flat bottom of
  length l7 at d3, flanks of radius r. l3 runs from the end face to the
  end-side edge of the flat (as drawn in the figure).
* Form G (Figure 7): a cylinder d1 (f8) with two flats e1 apart over
  l3 - l5 from the end and a round groove (radius r min) at l3. R 0.5 max at
  the end of the flats: modeled sharp.
* Corners of the hexagon forms: e1 max and min are below the sharp-corner
  width, so the corners are turned to e1.

Size (8) of form E is marked "not recommended".

All values are in millimetres.
"""

from __future__ import annotations

from dataclasses import dataclass

END_CHAMFER_LENGTH = 1.5   # axial length of the end chamfer (Figures 1, 3, 5)
END_CHAMFER_ANGLE = 30.0   # deg to the axis, "approx. 30 deg"
SHOULDER_RADIUS = 0.6      # R 0.6 min at the end of form A (Figure 1)
FORM_C_GROOVE_ANGLE = 90.0  # beta, 80 to 120 deg (Figure 3, detail X)
FORM_C4_CROSS_HOLE = 2.0   # diameter of the cross hole of form C size 4


@dataclass(frozen=True)
class DriveEnd:
    form: str            # "A", "C", "E" or "G"
    size: str            # nominal dimension, e.g. "6.3"
    l1: float            # length of the drive end, min.
    l3: float            # end face to the retaining groove (see module doc)
    d3: float | None     # groove bottom diameter (h12); None = no groove
    r: float | None      # groove radius (A, E, G) or root radius (C), min.
    s1_max: float | None = None   # hexagon forms: width across flats
    s1_min: float | None = None
    e1_max: float | None = None   # hexagon forms: across corners; G: flats
    e1_min: float | None = None
    d1: float | None = None       # form A collar (h9), form G cylinder (f8)
    l5: float | None = None       # form A hexagon length; form G groove to flats
    l7: float | None = None       # form E groove flat length (approx.)
    recommended: bool = True

    @property
    def name(self) -> str:
        """Form and size as written in designations, e.g. 'E 6,3'."""
        return f"{self.form} {self.size.replace('.', ',')}"

    @property
    def key(self) -> str:
        """Parameter value, e.g. 'E6.3'."""
        return f"{self.form}{self.size}"

    @property
    def hexagon(self) -> bool:
        return self.form in ("A", "C", "E")

    @property
    def outer_radius(self) -> float:
        """Radius of the smallest cylinder around the drive end's section."""
        return self.d1 / 2 if self.form in ("A", "G") else self.e1_max / 2


# fmt: off
DRIVE_ENDS: dict[str, DriveEnd] = {d.key: d for d in [
    # Table 1, form A: s1, d1 h9, d3 h12, e1, l1 min, l3 (0/-0.2), l5 (+0.4/0), r min
    DriveEnd("A", "3",   l1=19.5, l3=11.9, d3=3.0, r=1.0,  s1_max=3.00, s1_min=2.96,
             e1_max=3.39, e1_min=3.34, d1=3.6, l5=7.4),
    DriveEnd("A", "5.5", l1=24,   l3=16,   d3=5.7, r=1.25, s1_max=5.50, s1_min=5.45,
             e1_max=6.21, e1_min=6.16, d1=6.7, l5=10.9),
    # Table 3, form C: s1, d3 h12, e1, l1 min, l3 (0/-0.2), r min
    DriveEnd("C", "4",    l1=9,    l3=4,    d3=None, r=None, s1_max=3.96,  s1_min=3.91,
             e1_max=4.48,  e1_min=4.42),
    DriveEnd("C", "6.3",  l1=11,   l3=8.2,  d3=6.7,  r=0.3,  s1_max=6.35,  s1_min=6.29,
             e1_max=7.18,  e1_min=7.11),
    DriveEnd("C", "8",    l1=13.5, l3=10.2, d3=8.2,  r=0.3,  s1_max=7.93,  s1_min=7.87,
             e1_max=8.96,  e1_min=8.90),
    DriveEnd("C", "12.5", l1=15.9, l3=12.7, d3=13.5, r=0.3,  s1_max=12.70, s1_min=12.63,
             e1_max=14.35, e1_min=14.27),
    # Table 5, form E: s1, d3 h12, e1, l1 min, l3 (0/-0.1), l7 approx., r min
    DriveEnd("E", "6.3",  l1=25,   l3=9.5, d3=4.7, r=2.4, s1_max=6.35,  s1_min=6.29,
             e1_max=7.18,  e1_min=7.11,  l7=1.0),
    DriveEnd("E", "8",    l1=27,   l3=5.4, d3=6.3, r=2.4, s1_max=7.93,  s1_min=7.87,
             e1_max=8.96,  e1_min=8.90,  l7=1.2, recommended=False),
    DriveEnd("E", "11.2", l1=31.5, l3=6.7, d3=8.7, r=2.8, s1_max=11.11, s1_min=11.04,
             e1_max=12.56, e1_min=12.48, l7=1.2),
    # Table 7, form G: d1 f8, d3 h12, e1 (flats), l1 min, l3 +-0.2, l5 +-0.2, r min
    DriveEnd("G", "7", l1=26, l3=20, d3=5.8, r=1.5, e1_max=3.86, e1_min=3.74,
             d1=7.0, l5=14),
]}
# fmt: on

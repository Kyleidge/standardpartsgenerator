"""Female driving squares for hand socket tools, ISO 1174-1:2011 (types C
and D), with the male-square values the female side depends on.

Source: ISO 1174-1:2011 Tables 1 and 2 and Figures 1 to 4.

* Type C (Figure 3) has recesses for the ball of a type A male square,
  drawn on two opposite faces at l3 from the face of the tool.
* Type D (Figure 4) has a retaining hole of diameter d3 at l3 for the
  plunger of a type B male square. From 12.5 up, a lead-in groove (radius
  r2, depth t1, 30 deg) runs from the face to the hole; the model leaves it
  out.
* The mouth of the square is "chamfered or rounded in conformity with
  radius r1 of the male square" (r1 max of Table 1).
* Types in brackets in Table 2 are non-preferred: D for 10 and 12.5. Size 20
  and 25 are type D only.

What the model chooses (ISO 1174-1 gives limits only):

* s2 is the mean of s2 min and s2 max; the corners are turned to e2 min.
* The square is l2 min deep (sockets add 0.3 mm so the clearance hole
  behind it never meets the pocket bottom face on face).
* A type C recess is a sphere of the male ball diameter d1 (approx.), sunk
  l4 min into the face, so the ball of a male square sits in it.
* The retaining hole of type D goes through the wall on one face.

All values are in millimetres.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FemaleSquare:
    size: str               # nominal size of the square, e.g. "12.5"
    types: tuple[str, ...]  # types allowed for this size, preferred first
    preferred: tuple[str, ...]
    s2_max: float
    s2_min: float
    d3: float               # retaining hole diameter (type D), min.
    e2: float               # across corners, min.
    l2: float               # depth, min.
    l3: float               # face to the retaining recess or hole, nom.
    l3_tol: float
    # From Table 1 (male squares):
    ball: float | None      # ball diameter d1 (approx.) of type A
    l4: float               # protrusion of ball or plunger, min.
    r1: float               # male square edge radius, max.

    @property
    def s2(self) -> float:
        return round((self.s2_max + self.s2_min) / 2, 3)

    @property
    def name(self) -> str:
        return self.size.replace(".", ",")


# fmt: off
SQUARES: dict[str, FemaleSquare] = {q.size: q for q in [
    #             size   types        preferred  s2 max s2 min d3   e2    l2    l3   tol  ball l4   r1
    FemaleSquare("6.3",  ("C", "D"), ("C", "D"), 6.63,  6.41,  2.5, 8.5,  8,    4,   0.2, 3,   0.9, 0.5),
    FemaleSquare("10",   ("C", "D"), ("C",),     9.80,  9.58,  5,   12.9, 11.5, 5.5, 0.2, 5,   0.9, 0.6),
    FemaleSquare("12.5", ("C", "D"), ("C",),     13.03, 12.76, 6,   17.1, 16,   8,   0.3, 6,   1.0, 0.8),
    FemaleSquare("20",   ("D",),     ("D",),     19.44, 19.11, 6,   25.6, 24,   10.2, 0.3, 7,  1.0, 1.2),
    FemaleSquare("25",   ("D",),     ("D",),     25.79, 25.46, 6.5, 34.4, 29,   15,  0.3, None, 1.0, 1.6),
]}
# fmt: on

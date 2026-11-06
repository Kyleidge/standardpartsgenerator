"""Dimension table for DIN 1587, hexagon domed cap nuts, high type
(one-piece acorn nuts), coarse thread M4 to M24.

Sources:

* DIN 1587:2000-10 values as listed by fasten.it: d, P, dk max, h nom,
  x max (M4 to M10), g max (M12 to M24), s, e min and t min / max. The
  drawing there shows a hexagon of height m with the dome on top, drawn as
  one piece, the thread run-out x (or undercut g) at the bottom of the
  bore, and t from the bearing face to the end of the cylindrical bore,
  which is closed by a conical drill point.
* Westfield Fasteners' DIN 1587 specification: da, dw min, e, x max and
  g2 max for every size, h, m, the auxiliary dome radius r, s, t (these
  match the 2014 edition, whose t differ from the 2000 values by at most
  0.05) and w min. Its m row is labelled min / max the wrong way round;
  m max is 3.2, 4, 5, 6.5, ... 19.
* Cross-checks: Fabory (M8: dk max 12.5, h 15, m max 6.5, s 13, t min
  10.65; M12: m max 10) and PGB-Europe (M12: s 18, dk 17, m 10).

Form: the DIN 1587 drawing shows the hexagon and dome as one piece, and
that is what is modeled. Two-piece nuts with a welded or pressed-on cap
are sold as "similar to DIN 1587" (Fabory lists them as "DIN ≈1587, with
welded cap") and are not modeled.

Values that are not in the 2000 table or were resolved by choice:

* m max comes from Westfield and Fabory. fasten.it's 2000 and 2014 coarse
  tables print a column headed "m max" (4.1, 5.4, 6, 8.5, ...) that
  disagrees with every other source and with fasten.it's own fine-thread
  table (M8x1: 6.5), so it is not used.
* r (dome radius) is an auxiliary dimension from Westfield; it equals
  dk max / 2 except M8 (6.24 against 6.25). The model's dome is a sphere
  of radius r on a short cylinder of diameter 2 r above the hexagon.
* Thread end: the 2000 table gives x max (run-out, type A) for M4 to M10
  only and g max (undercut, type B) for M12 to M24 only, and the model
  follows that. The other values (x for M12 to M24, all 2 P; g for M4 to
  M10) are Westfield's and are listed for reference only. The undercut
  diameter is not in the sources; the model uses dg = D + 0.5 P (as for
  DIN 76-1 internal thread undercuts), entered by a 45 deg step.
* da max and dw min (bearing face countersink and chamfer) are from
  Westfield; the 2000 table on fasten.it does not list them.
* s: the 2000 edition uses the ISO widths across flats (M10 16, M12 18,
  M14 21, M22 34). fasten.it prints the withdrawn widths 17, 19, 22 in
  brackets; for M22 it prints "32(34)" while its e min (37.29) belongs to
  s = 34, which Westfield also gives. The model uses 34.
* w min (crown thickness) is from Westfield. The sources do not show how
  deep the drill point goes. Read as the material on the axis beyond a
  120 deg drill point at t nom, w min is met almost exactly at M8 (2.03)
  and M12 (3.03) and with margin at M6 and M10. For the other sizes such
  a point would leave less than w min, so the model cuts the point flat
  at h - w min (see din1587.drill_floor).
* M27 and M30 appear in fasten.it's table with h and s only; they are
  outside the scope (M4 to M24) and are not offered. The fine-pitch sizes
  are not offered either: the 2000 table on fasten.it has no fine-pitch
  rows (they appear in the 2014 edition).

All values are in millimetres.
"""

from __future__ import annotations

from dataclasses import dataclass

COUNTERSINK_ANGLE = 120.0
CHAMFER_ANGLE = 30.0       # hexagon corner chamfers
DRILL_POINT_ANGLE = 120.0  # cone closing the bore, as drawn


@dataclass(frozen=True)
class SizeData:
    size: str          # thread, e.g. "M8"
    D: float           # nominal thread diameter
    P: float           # coarse pitch
    dk_max: float      # dome diameter
    h: float           # overall height (nom = max)
    m_max: float       # height of the hexagon
    s: float           # width across flats (nom = max)
    e_min: float       # width across corners
    t_min: float       # depth of the bore from the bearing face
    t_max: float
    x_max: float       # thread run-out at the bottom of the bore (type A)
    g_max: float       # thread undercut width (type B), not modeled
    r: float           # dome radius (auxiliary)
    da_max: float      # countersink diameter on the bearing face
    dw_min: float      # bearing face diameter
    w_min: float       # crown thickness

    @property
    def end_type(self) -> str:
        """Thread end: "A" run-out (the 2000 table gives x max, M4 to M10),
        "B" undercut (it gives g max, M12 to M24)."""
        return "A" if self.D <= 10 else "B"

    @property
    def dg(self) -> float:
        """Undercut diameter for type B: D + 0.5 P (model value, after
        DIN 76-1 internal thread undercuts)."""
        return round(self.D + 0.5 * self.P, 3)

    @property
    def t_nom(self) -> float:
        return round((self.t_min + self.t_max) / 2, 3)

    @property
    def e_nom(self) -> float:
        """Across corners of the exact hexagon of width s."""
        return self.s * 2 / 3**0.5


def _row(size, P, dk, h, m, s, e_min, t_min, t_max, x, g, r, da, dw, w):
    return SizeData(size, float(size[1:]), P, dk, h, m, s, e_min, t_min, t_max, x, g,
                    r, da, dw, w)


_ROWS = [
    #    size   P     dk    h   m     s   e min  t min  t max  x    g     r      da     dw    w
    _row("M4",  0.7,  6.5,  8,  3.2,  7,  7.66,  5.26,  5.74,  1.4, 2.75, 3.25,  4.6,   5.9,  2),
    _row("M5",  0.8,  7.5,  10, 4.0,  8,  8.79,  7.21,  7.79,  1.6, 3.0,  3.75,  5.75,  6.9,  2),
    _row("M6",  1.0,  9.5,  12, 5.0,  10, 11.05, 7.71,  8.29,  2.0, 3.7,  4.75,  6.75,  8.9,  2),
    _row("M8",  1.25, 12.5, 15, 6.5,  13, 14.38, 10.7,  11.4,  2.5, 4.9,  6.24,  8.75,  11.6, 2),
    _row("M10", 1.5,  15,   18, 8.0,  16, 17.77, 12.7,  13.4,  3.0, 5.6,  7.5,   10.8,  14.6, 2),
    _row("M12", 1.75, 17,   22, 10.0, 18, 20.03, 15.7,  16.4,  3.5, 6.4,  8.5,   13.0,  16.6, 3),
    _row("M14", 2.0,  20,   25, 11.0, 21, 23.35, 17.7,  18.4,  4.0, 7.3,  10.0,  15.1,  19.6, 4),
    _row("M16", 2.0,  23,   28, 13.0, 24, 26.75, 20.6,  21.4,  4.0, 7.3,  11.5,  17.3,  22.5, 4),
    _row("M18", 2.5,  26,   32, 15.0, 27, 29.56, 24.6,  25.4,  5.0, 9.3,  13.0,  19.5,  24.9, 5),
    _row("M20", 2.5,  28,   34, 16.0, 30, 32.95, 25.6,  26.4,  5.0, 9.3,  14.0,  21.6,  27.7, 5),
    _row("M22", 2.5,  33,   39, 18.0, 34, 37.29, 28.6,  29.4,  5.0, 9.3,  16.5,  23.7,  31.4, 5),
    _row("M24", 3.0,  34,   42, 19.0, 36, 39.55, 30.5,  31.5,  6.0, 10.7, 17.0,  25.9,  33.3, 6),
]

SIZES: dict[str, SizeData] = {r.size: r for r in _ROWS}

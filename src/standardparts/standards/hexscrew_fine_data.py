"""Size table for ISO 8765:2022 (hexagon head bolts, fine pitch thread,
partially threaded) and ISO 8676:2022 (hexagon head screws, fine pitch
thread, threaded to the head), product grades A and B, M8x1 to M64x4.

The fine pitch standards use the heads, thread lengths b and length ranges
of their coarse counterparts ISO 4014 / ISO 4017 unchanged. Only the thread
pitch differs, and some diameters come with two pitches. So this module
lists the size/pitch combinations and reuses the coarse rows of
hexscrew_data.py for everything else.

Sources:

* ISO 8765:2022 Tables 1 to 4 (M8x1 to M42x3) and ISO 8676:2022 Tables 1
  to 4 (same sizes). Every value in these tables was compared with
  hexscrew_data.py: b (all three bands), c, da, ds, dw, e, k, kw, r and s
  for both product grades, and the length ranges between the stepped
  lines, are identical to the ISO 4014:2022 /
  ISO 4017:2022 data. This includes dw min = 19.64 for M14x1.5, which the
  2022 foreword lists as a correction of ISO 8765:2011.
* Plain shank: ISO 8765:2022 Figure 1 note c defines lg max = l - b and
  ls min = lg max - 5P "where P is the coarse pitch in accordance with
  ISO 262", so ls min and lg max are the ISO 4014 values. The ls/lg rows
  of ISO 8765:2022 Tables 1 to 4 confirm it (e.g. M8x1 x 40: ls 11.75 =
  18 - 5 x 1.25).
* ISO 8676:2022: a = 1P to 3P of the fine pitch (Tables 1 to 4).
* ISO 8765:2011 Table 1 (preferred sizes) as a cross-check of the
  head values and the M45 to M64 pitches.
* fasten.it (DIN EN ISO 8765 04-2013, DIN EN ISO 8676 10-2022): s, e and
  k per diameter. Its pitch and k columns have obvious errors (M48 x 4,
  k = 19 for M30), so it was only used for s and e.

Table 5 of both 2022 editions (M45x3 to M64x4) was not available. Those
rows are taken as one pitch each, M45x3, M48x3, M52x4, M56x4, M60x4 and
M64x4, as in ISO 8765:2011 and the 2022 scope ("M8x1 to M64x4"), and their
heads and lengths come from the coarse data (head values cross-checked
against ISO 8765:2011 Table 1; the length ranges are derived from the 2022
rules exactly as for ISO 4014 / ISO 4017, see hexscrew_data.py).

Changes against the 2011 editions, all following the 2022 tables:

* M10x1.25, M12x1.5 and M20x2 are now the preferred pitches; M10x1,
  M12x1.25 and M20x1.5 are non-preferred (2011 had it the other way round).
* M18x2 is new in ISO 8765 and ISO 8676; M22x2 is listed in both 2022
  editions.
* Length ranges follow the 2022 rules: e.g. ISO 8765 M24x2 starts at 90
  (2011: 100), M30x2 at 110 (2011: 120), ISO 8676 lengths stop at 200.

The modeled ISO 8676 thread runs out 2P (fine) below the step from the
thread core to the shank right under the fillet, so its first full thread
lies r + (d - d1) / 2 + 2P below the bearing face. For ten fine sizes
with a large fillet for their pitch (M12x1.25, M20x1.5, M22x1.5, M27x2,
M30x2, M33x2, M48x3, M56x4, M60x4, M64x4) that is 0.03 to 0.22 mm more
than a max = 3P, because the 2P runout is fixed in screws.threaded_screw;
see test_iso8676_thread_runout_near_a.

All values are in millimetres.
"""

from __future__ import annotations

from .hexscrew_data import SIZES as COARSE_SIZES
from .hexscrew_data import ThreadSize

# (size, fine pitch, preferred) in the order of ISO 8765:2022 / ISO 8676:2022
# Tables 1 to 5 (the preferred pitch first where a diameter has two).
# fmt: off
FINE_PITCHES: tuple[tuple[str, float, bool], ...] = (
    ("M8",  1.0,  True),
    ("M10", 1.25, True),
    ("M10", 1.0,  False),
    ("M12", 1.5,  True),
    ("M12", 1.25, False),
    ("M14", 1.5,  False),
    ("M16", 1.5,  True),
    ("M18", 2.0,  False),
    ("M18", 1.5,  False),
    ("M20", 2.0,  True),
    ("M20", 1.5,  False),
    ("M22", 2.0,  False),
    ("M22", 1.5,  False),
    ("M24", 2.0,  True),
    ("M27", 2.0,  False),
    ("M30", 2.0,  True),
    ("M33", 2.0,  False),
    ("M36", 3.0,  True),
    ("M39", 3.0,  False),
    ("M42", 3.0,  True),
    ("M45", 3.0,  False),
    ("M48", 3.0,  True),
    ("M52", 4.0,  False),
    ("M56", 4.0,  True),
    ("M60", 4.0,  False),
    ("M64", 4.0,  True),
)
# fmt: on


def _key(size: str, P: float) -> str:
    return f"{size}x{P:g}"


SIZES: dict[str, ThreadSize] = {
    _key(size, P): ThreadSize(_key(size, P), COARSE_SIZES[size], P, preferred, fine=True)
    for size, P, preferred in FINE_PITCHES
}

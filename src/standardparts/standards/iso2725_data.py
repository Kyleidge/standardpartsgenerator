"""Hand-operated square drive sockets, ISO 2725-1:2017.

Source: ISO 2725-1:2017 Tables 1 to 3 (square drives 6.3, 10 and 12.5) and
Figures 1 to 3. The tables give, per width across flats s:

* Dmax, the largest thread the socket is meant for, and t min = m max + 0.1
  (m max: nut height of ISO 4032), the depth of the opening;
* d1 max and d2 max, the outside diameters at the opening end and at the
  drive end;
* d3 min = 1.05 Dmax, the bolt clearance hole behind the opening;
* l max of type A (normal) and l min of type B (long).

Tables 4 and 5 (drives 20 and 25) of the 2017 edition were not available.
The 2007 edition derived t and d3 differently (from
ISO 4014 head heights and other clearance holes), so its values are not
mixed in: drives 20 and 25 are not offered.

Corrected misprint: Table 3 (drive 12.5) prints d3 = 5.8 for s = 9. The
footnote rule gives 1.05 x 6 = 6.3, as do Tables 1 and 2 for s = 9; 6.3 is
used (tested against the rule for every row).

Other requirements:

* Opening: hexagon ("Hex socket") or double hexagon ("Bi-hex socket"); s
  toleranced by ISO 691 (manufacturer's choice of series), not reproduced
  here; the model uses nominal s.
* The figures are "only examples" and "not intended to influence the
  manufacturer's design". The mouth of the opening is countersunk with
  115 deg <= alpha <= 150 deg.
* The drive end is a female square in accordance with ISO 1174-1
  (iso1174_data).

Designation (clause 6 of the 2007 edition; not checked against the 2017
edition): "Bi-hex socket ISO 2725-1 - 12,5 x 10 - A".

All values are in millimetres.
"""

from __future__ import annotations

from dataclasses import dataclass

COUNTERSINK_ANGLE = 120.0  # alpha, 115 to 150 deg


@dataclass(frozen=True)
class SocketData:
    drive: str          # square drive, "6.3", "10" or "12.5"
    s: float            # width across flats, nominal
    D_max: float        # largest thread diameter served
    t: float            # depth of the opening, min.
    d1: float           # outside diameter at the opening end, max.
    d2: float           # outside diameter at the drive end, max.
    d3: float           # bolt clearance hole, min.
    l_A: float          # length, type A (normal), max.
    l_B: float          # length, type B (long), min.
    in_iso272: bool     # False: "nominal dimension not covered by ISO 272"

    @property
    def size(self) -> str:
        return f"{self.s:g}"

    def length(self, socket_type: str) -> float:
        return self.l_A if socket_type == "A" else self.l_B


def _table(drive: str, rows: list[tuple]) -> dict[str, SocketData]:
    out = {}
    for s, D, t, d1, d2, d3, la, lb, iso272 in rows:
        sd = SocketData(drive, s, D, t, d1, d2, d3, la, lb, iso272)
        out[sd.size] = sd
    return out


# fmt: off
# s, Dmax, t min, d1 max, d2 max, d3 min, l max A, l min B, in ISO 272
TABLE_6_3 = _table("6.3", [
    (3.2, 1.6, 1.4, 5.9,  12.5, 1.7,  26, 45, True),
    (4,   2,   1.7, 6.9,  12.5, 2.1,  26, 45, True),
    (5,   2.5, 2.1, 8.2,  12.5, 2.6,  26, 45, True),
    (5.5, 3,   2.5, 8.8,  12.5, 3.2,  26, 45, True),
    (6,   3.5, 2.9, 9.4,  12.5, 3.7,  26, 45, False),
    (7,   5,   3.3, 11,   12.5, 5.3,  26, 45, True),
    (8,   6,   4.8, 12.2, 12.5, 6.3,  26, 45, True),
    (9,   6,   5.1, 13.5, 13.5, 6.3,  26, 45, False),
    (10,  8,   5.3, 14.7, 14.7, 8.4,  26, 45, True),
    (11,  8,   5.8, 16,   16,   8.4,  26, 45, True),
    (12,  8,   6.4, 17.2, 17.2, 8.4,  26, 45, False),
    (13,  10,  6.9, 18.5, 18.5, 10.5, 26, 45, True),
    (14,  10,  7.4, 19.7, 19.7, 10.5, 26, 45, False),
    (15,  12,  8.0, 21.5, 21.5, 12.6, 26, 45, False),
    (16,  12,  8.5, 22,   22,   12.6, 26, 45, True),
    (17,  12,  9.7, 22.5, 22.5, 12.6, 26, 45, False),
])
TABLE_10 = _table("10", [
    (6,   3.5, 2.9,  10.1, 20,   3.7,  32, 44, False),
    (7,   5,   3.3,  11,   20,   5.3,  32, 44, True),
    (8,   6,   4.8,  12.2, 20,   6.3,  32, 44, True),
    (9,   6,   5.1,  13.5, 20,   6.3,  32, 44, False),
    (10,  8,   5.3,  14.7, 20,   8.4,  32, 44, True),
    (11,  8,   5.8,  16,   20,   8.4,  32, 44, True),
    (12,  8,   6.4,  17.2, 20,   8.4,  32, 44, False),
    (13,  10,  6.9,  18.5, 20,   10.5, 32, 44, True),
    (14,  10,  7.4,  19.7, 24,   10.5, 32, 45, False),
    (15,  12,  8.0,  21.0, 24,   12.6, 32, 45, False),
    (16,  12,  8.5,  22.2, 24,   12.6, 35, 50, True),
    (17,  12,  9.7,  23.5, 24,   12.6, 35, 54, False),
    (18,  14,  10.9, 24.7, 24.7, 14.7, 35, 54, True),
    (19,  14,  11.9, 26,   26,   14.7, 35, 60, False),
    (20,  14,  12.4, 27.8, 27.8, 14.7, 35, 60, False),
    (21,  16,  12.9, 28.5, 28.8, 16.8, 38, 60, True),
    (22,  16,  13.9, 29.7, 29.7, 16.8, 38, 60, False),
    (23,  16,  14.4, 31.3, 31.3, 16.8, 38, 60, False),
    (24,  16,  14.9, 32.5, 32.5, 16.8, 38, 65, True),
    (25,  18,  14.9, 33,   33,   18.3, 38, 65, True),
])
TABLE_12_5 = _table("12.5", [
    (8,   6,   4.8,  14,   24,   6.3,  40, 75, True),
    (9,   6,   5.1,  14.1, 24,   6.3,  40, 75, False),  # printed 5.8, see above
    (10,  8,   5.3,  15.5, 24,   8.4,  40, 75, True),
    (11,  8,   5.8,  16.7, 24,   8.4,  40, 75, True),
    (12,  8,   6.4,  18,   24,   8.4,  40, 75, False),
    (13,  10,  6.9,  19.2, 24,   10.5, 40, 75, True),
    (14,  10,  7.4,  20.5, 24,   10.5, 40, 75, False),
    (15,  12,  8.0,  21.7, 24,   12.6, 40, 75, False),
    (16,  12,  8.5,  23,   25.5, 12.6, 40, 75, True),
    (17,  12,  9.7,  24.2, 25.5, 12.6, 40, 75, False),
    (18,  14,  10.9, 25.5, 25.5, 14.7, 42, 75, True),
    (19,  14,  11.9, 26.7, 26.7, 14.7, 42, 75, False),
    (20,  14,  12.4, 28,   28,   14.7, 42, 75, False),
    (21,  16,  12.9, 29.2, 29.2, 16.8, 44, 75, True),
    (22,  16,  13.9, 30.5, 30.5, 16.8, 44, 75, False),
    (23,  16,  14.4, 31.3, 31.3, 16.8, 46, 75, False),
    (24,  16,  14.9, 33,   33,   16.8, 46, 75, True),
    (25,  18,  14.9, 33.4, 33.4, 18.3, 46, 75, False),
    (27,  20,  15.9, 36.7, 36.7, 21.0, 48, 75, True),
    (30,  20,  18.1, 40.5, 40.5, 21.0, 50, 75, True),
    (32,  24,  18.8, 43,   43,   25.2, 50, 75, False),
    (34,  24,  19.5, 46.5, 46.5, 25.2, 52, 75, True),
])
# fmt: on

SOCKETS: dict[str, dict[str, SocketData]] = {
    "6.3": TABLE_6_3,
    "10": TABLE_10,
    "12.5": TABLE_12_5,
}

# Every width across flats offered by at least one drive, in order.
ALL_SIZES: list[str] = sorted(
    {s for table in SOCKETS.values() for s in table}, key=float
)

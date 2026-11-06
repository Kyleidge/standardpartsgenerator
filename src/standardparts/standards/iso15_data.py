"""Boundary dimensions for single-row deep groove ball bearings, series 60,
62 and 63 (ISO 15 dimension series 10, 02 and 03), bore codes 00 to 22.

All values in mm.

Sources:

* d, D, B and the chamfer r_s min (ISO 15 boundary dimensions, chamfer
  values per ISO 582) for all 69 bearings: NSK's online catalogue
  (oss.nsk.com, one page per bearing, e.g. "6205 Series").
* Cross-check of D, B and r_s min: the Nachi deep groove ball bearing
  catalogue (snap-ring tables, pp. 159-164) agrees on all 64 bearings it
  lists (6002 to 6022, 6200 to 6222, 6300 to 6319). 6000 and 6001 agree
  with SKF data (bd_warehouse) and the NRB industrial catalogue. 6320 and
  6321 agree with SKF and FAG distributor data sheets (d x D x B and r_s
  min = 3). 6322 (110 x 240 x 50) agrees with SKF, FAG and NSK listings for
  d x D x B; its r_s min = 3 is from NSK only.
* The bore follows the ISO bore code: 00 = 10, 01 = 12, 02 = 15, 03 = 17,
  and 5 x code from 04. A test checks every row against it.

Not boundary dimensions (NSK catalogue values, manufacturer specific):

* da min / da max (shaft shoulder), Da max (housing shoulder) and ra max
  (fillet radius): abutment dimensions, shown in the dimension table only.
* z (number of balls) and Dw (ball diameter): NSK's internal design. They
  are used only by the "rings" detail model.
* mass: NSK's approximate mass of the open bearing, in kg. The tests compare
  the "rings" model against it.
"""

from __future__ import annotations

from dataclasses import dataclass

# Bearing series -> ISO 15 dimension series (width series, diameter series).
DIMENSION_SERIES = {"60": "10", "62": "02", "63": "03"}


@dataclass(frozen=True)
class BearingData:
    designation: str  # e.g. "6205"
    d: float          # bore diameter
    D: float          # outside diameter
    B: float          # width
    rs_min: float     # smallest chamfer dimension (ISO 582)
    da_min: float     # shaft abutment diameter, min (NSK)
    da_max: float     # shaft abutment diameter, max (NSK)
    Da_max: float     # housing abutment diameter, max (NSK)
    ra_max: float     # shaft / housing fillet radius, max (NSK)
    z: int            # number of balls (NSK internal design)
    Dw: float         # ball diameter (NSK internal design)
    mass: float       # approx. mass in kg, open bearing (NSK)

    @property
    def series(self) -> str:
        return self.designation[:2]

    @property
    def bore_code(self) -> str:
        return self.designation[2:]

    @property
    def dimension_series(self) -> str:
        return DIMENSION_SERIES[self.series]

    @property
    def dm(self) -> float:
        """Mean diameter, used as the ball pitch diameter in the model."""
        return (self.d + self.D) / 2


_ROWS = [
    # series 60 (dimension series 10)
    ("6000", 10, 26, 8, 0.3, 12, 13, 24, 0.3, 7, 4.762, 0.018),
    ("6001", 12, 28, 8, 0.3, 14, 15.5, 26, 0.3, 8, 4.762, 0.022),
    ("6002", 15, 32, 9, 0.3, 17, 19, 30, 0.3, 9, 4.762, 0.031),
    ("6003", 17, 35, 10, 0.3, 19, 21.5, 33, 0.3, 10, 4.762, 0.041),
    ("6004", 20, 42, 12, 0.6, 24, 25.5, 38, 0.6, 9, 6.35, 0.068),
    ("6005", 25, 47, 12, 0.6, 29, 30, 43, 0.6, 10, 6.35, 0.079),
    ("6006", 30, 55, 13, 1, 35, 36.5, 50, 1, 11, 7.144, 0.116),
    ("6007", 35, 62, 14, 1, 40, 41.5, 57, 1, 11, 7.938, 0.151),
    ("6008", 40, 68, 15, 1, 45, 47.5, 63, 1, 12, 7.938, 0.19),
    ("6009", 45, 75, 16, 1, 50, 53.5, 70, 1, 13, 8.731, 0.241),
    ("6010", 50, 80, 16, 1, 55, 58.5, 75, 1, 14, 8.731, 0.261),
    ("6011", 55, 90, 18, 1.1, 61.5, 64, 83.5, 1, 13, 10.319, 0.381),
    ("6012", 60, 95, 18, 1.1, 66.5, 69, 88.5, 1, 14, 10.319, 0.412),
    ("6013", 65, 100, 18, 1.1, 71.5, 73, 93.5, 1, 15, 10.319, 0.439),
    ("6014", 70, 110, 20, 1.1, 76.5, 80.5, 103.5, 1, 14, 11.906, 0.608),
    ("6015", 75, 115, 20, 1.1, 81.5, 85.5, 108.5, 1, 15, 11.906, 0.649),
    ("6016", 80, 125, 22, 1.1, 86.5, 91, 118.5, 1, 14, 13.494, 0.872),
    ("6017", 85, 130, 22, 1.1, 91.5, 96, 123.5, 1, 15, 13.494, 0.918),
    ("6018", 90, 140, 24, 1.5, 98, 103, 132, 1.5, 14, 15.081, 1.19),
    ("6019", 95, 145, 24, 1.5, 103, 108.5, 137, 1.5, 15, 15.081, 1.23),
    ("6020", 100, 150, 24, 1.5, 108, 112.5, 142, 1.5, 15, 15.081, 1.29),
    ("6021", 105, 160, 26, 2, 114, 120, 151, 2, 15, 16.669, 1.58),
    ("6022", 110, 170, 28, 2, 119, 124.5, 161, 2, 13, 19.05, 1.94),
    # series 62 (dimension series 02)
    ("6200", 10, 30, 9, 0.6, 14, 16, 26, 0.6, 8, 4.762, 0.032),
    ("6201", 12, 32, 10, 0.6, 16, 17, 28, 0.6, 7, 5.953, 0.037),
    ("6202", 15, 35, 11, 0.6, 19, 20.5, 31, 0.6, 8, 5.953, 0.045),
    ("6203", 17, 40, 12, 0.6, 21, 23.5, 36, 0.6, 8, 6.747, 0.067),
    ("6204", 20, 47, 14, 1, 25, 26.5, 42, 1, 8, 7.938, 0.107),
    ("6205", 25, 52, 15, 1, 30, 32, 47, 1, 9, 7.938, 0.129),
    ("6206", 30, 62, 16, 1, 35, 38.5, 57, 1, 9, 9.525, 0.199),
    ("6207", 35, 72, 17, 1.1, 41.5, 44.5, 65.5, 1, 9, 11.112, 0.284),
    ("6208", 40, 80, 18, 1.1, 46.5, 50.5, 73.5, 1, 9, 11.906, 0.366),
    ("6209", 45, 85, 19, 1.1, 51.5, 55.5, 78.5, 1, 10, 11.906, 0.42),
    ("6210", 50, 90, 20, 1.1, 56.5, 60, 83.5, 1, 10, 12.7, 0.459),
    ("6211", 55, 100, 21, 1.5, 63, 66.5, 92, 1.5, 10, 14.288, 0.619),
    ("6212", 60, 110, 22, 1.5, 68, 74.5, 102, 1.5, 10, 15.875, 0.783),
    ("6213", 65, 120, 23, 1.5, 73, 80, 112, 1.5, 10, 16.669, 1),
    ("6214", 70, 125, 24, 1.5, 78, 84, 117, 1.5, 10, 17.462, 1.09),
    ("6215", 75, 130, 25, 1.5, 83, 90, 122, 1.5, 11, 17.462, 1.19),
    ("6216", 80, 140, 26, 2, 89, 95.5, 131, 2, 10, 19.05, 1.42),
    ("6217", 85, 150, 28, 2, 94, 102, 141, 2, 10, 20.638, 1.76),
    ("6218", 90, 160, 30, 2, 99, 107.5, 151, 2, 10, 22.225, 2.18),
    ("6219", 95, 170, 32, 2.1, 106, 114, 159, 2, 10, 23.812, 2.64),
    ("6220", 100, 180, 34, 2.1, 111, 121.5, 169, 2, 10, 25.4, 3.17),
    ("6221", 105, 190, 36, 2.1, 116, 127.5, 179, 2, 10, 26.988, 3.79),
    ("6222", 110, 200, 38, 2.1, 121, 134, 189, 2, 10, 28.575, 4.45),
    # series 63 (dimension series 03)
    ("6300", 10, 35, 11, 0.6, 14, 16.5, 31, 0.6, 6, 7.144, 0.052),
    ("6301", 12, 37, 12, 1, 17, 18, 32, 1, 6, 7.938, 0.06),
    ("6302", 15, 42, 13, 1, 20, 22.5, 37, 1, 7, 7.938, 0.083),
    ("6303", 17, 47, 14, 1, 22, 25.5, 42, 1, 7, 8.731, 0.113),
    ("6304", 20, 52, 15, 1.1, 26.5, 28, 45.5, 1, 7, 9.525, 0.145),
    ("6305", 25, 62, 17, 1.1, 31.5, 36, 55.5, 1, 8, 10.319, 0.235),
    ("6306", 30, 72, 19, 1.1, 36.5, 42.5, 65.5, 1, 8, 11.906, 0.345),
    ("6307", 35, 80, 21, 1.5, 43, 47, 72, 1.5, 8, 13.494, 0.464),
    ("6308", 40, 90, 23, 1.5, 48, 53, 82, 1.5, 8, 15.081, 0.636),
    ("6309", 45, 100, 25, 1.5, 53, 61.5, 92, 1.5, 8, 17.462, 0.829),
    ("6310", 50, 110, 27, 2, 59, 68, 101, 2, 8, 19.05, 1.06),
    ("6311", 55, 120, 29, 2, 64, 72.5, 111, 2, 8, 20.638, 1.37),
    ("6312", 60, 130, 31, 2.1, 71, 79, 119, 2, 8, 22.225, 1.72),
    ("6313", 65, 140, 33, 2.1, 76, 85.5, 129, 2, 8, 23.812, 2.11),
    ("6314", 70, 150, 35, 2.1, 81, 92, 139, 2, 8, 25.4, 2.57),
    ("6315", 75, 160, 37, 2.1, 86, 98.5, 149, 2, 8, 26.988, 3.08),
    ("6316", 80, 170, 39, 2.1, 91, 104.5, 159, 2, 8, 28.575, 3.67),
    ("6317", 85, 180, 41, 3, 98, 110.5, 167, 2.5, 8, 30.162, 4.28),
    ("6318", 90, 190, 43, 3, 103, 117, 177, 2.5, 8, 31.75, 4.98),
    ("6319", 95, 200, 45, 3, 108, 123.5, 187, 2.5, 8, 33.338, 5.76),
    ("6320", 100, 215, 47, 3, 113, 133, 202, 2.5, 8, 36.512, 7.04),
    ("6321", 105, 225, 49, 3, 118, 138, 212, 2.5, 8, 38.1, 8.09),
    ("6322", 110, 240, 50, 3, 123, 147, 227, 2.5, 8, 41.275, 9.51),
]

BEARINGS: dict[str, BearingData] = {
    row[0]: BearingData(
        row[0], *(float(x) for x in row[1:9]), int(row[9]), float(row[10]), float(row[11])
    )
    for row in _ROWS
}

"""Machine-operated screwdriver bits for hexagon socket screws, ISO 2351-3.

Sources:

* ISO 2351-3:2002 Table 1 (recommended combinations of tip and drive end,
  with the bit length l1 for each drive end and the minimum tip length l2
  for each width across flats) and Figure 1.
* ISO 2351-3:2014 (current edition) keeps Figure 1 and the clause "the
  shape of the liaison between the tip and the driver end is at the
  discretion of the manufacturer". Its foreword lists changes to the proof
  torques of Table 2 only, so Table 1 is taken as unchanged. Table 1 of the
  2014 edition was not available, so this was not checked.
* The tip is a hexagon in accordance with ISO 2936 (s, e of
  iso2936_data); the drive end is in accordance with ISO 1173
  (iso1173_data).

Designation (2002 clause 6): "Bit ISO 2351-3 E 11,2 - 6".

All values are in millimetres.
"""

from __future__ import annotations

# Bit length l1 (+-2) per drive end (Table 1, header row).
BIT_LENGTH: dict[str, float] = {
    "A3": 45, "A5.5": 50, "C4": 28, "C6.3": 25, "C8": 30, "C12.5": 50,
    "E6.3": 50, "E8": 50, "E11.2": 55, "G7": 63,
}

# Minimum tip length l2 per width across flats s (Table 1).
TIP_LENGTH: dict[str, float] = {
    "0.7": 1.7, "0.9": 1.9, "1.3": 2.3, "1.5": 2.3, "2": 3, "2.5": 3.8,
    "3": 4.5, "4": 6, "5": 7.5, "6": 9, "7": 10.5, "8": 12, "10": 16, "12": 18,
}

# The crosses of Table 1: drive ends recommended for each tip size.
# fmt: off
COMBINATIONS: dict[str, tuple[str, ...]] = {
    "0.7": ("A3", "C4"),
    "0.9": ("A3", "C4"),
    "1.3": ("A3", "C4"),
    "1.5": ("A3", "C4", "C6.3", "E6.3"),
    "2":   ("A3", "C4", "C6.3", "E6.3", "G7"),
    "2.5": ("A3", "A5.5", "C4", "C6.3", "E6.3", "G7"),
    "3":   ("A3", "A5.5", "C4", "C6.3", "C8", "C12.5", "E6.3", "E8", "G7"),
    "4":   ("A5.5", "C6.3", "C8", "C12.5", "E6.3", "E8", "G7"),
    "5":   ("A5.5", "C6.3", "C8", "C12.5", "E6.3", "E8", "E11.2"),
    "6":   ("C6.3", "C8", "C12.5", "E6.3", "E8", "E11.2"),
    "7":   ("C8", "C12.5", "E8", "E11.2"),
    "8":   ("C8", "C12.5", "E8", "E11.2"),
    "10":  ("C12.5", "E11.2"),
    "12":  ("C12.5",),
}
# fmt: on

# Minimum proof torque Md (N m) per tip size, ISO 2351-3:2002 Table 2
# (about 1.16 x the ISO 2936 test torque); shown for information only.
PROOF_TORQUE: dict[str, float] = {
    "0.7": 0.09, "0.9": 0.2, "1.3": 0.6, "1.5": 0.95, "2": 2.3, "2.5": 4.4,
    "3": 7.6, "4": 18, "5": 35, "6": 61, "7": 97, "8": 140, "10": 255, "12": 480,
}

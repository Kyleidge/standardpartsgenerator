"""ISO 2351-3 machine-operated screwdriver bits for hexagon socket screws."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from build123d import Part, Pos, extrude

from ..tooling import cone_trim, corner_radius, hex_section
from .base import Dimension, Option, Parameter, ParameterError, Standard
from .drive_ends import drive_end_shank, shank_is_hexagon, shank_radius
from .iso1173_data import DRIVE_ENDS, DriveEnd
from .iso2351_data import BIT_LENGTH, COMBINATIONS, PROOF_TORQUE, TIP_LENGTH
from .iso2936_data import SIZES as KEY_SIZES

# The "liaison" between tip and drive end is the manufacturer's choice. The
# model tapers the shank down to the tip at this angle to the axis, starting
# just inside the tip's flats.
TAPER_ANGLE = 30.0
TAPER_START = 0.9  # x s / 2: radius where the taper meets the tip
# The tip's end edge: 45 deg chamfer of this fraction of ISO 2936's f max.
TIP_CHAMFER_FRACTION = 0.5


def _fmt(x: float) -> str:
    return f"{x:g}"


@dataclass(frozen=True)
class BitLayout:
    """Where the parts of a bit lie along Z (tip end face at z = 0)."""

    length: float        # l1, overall
    tip_length: float    # l2 min: full tip section from z = 0
    taper_end: float     # z where the taper reaches the shank's full size
    tip_in_shank: bool   # tip section lies inside the shank section


def tip_inside_shank(s: str, de: DriveEnd) -> bool:
    kd = KEY_SIZES[s]
    if shank_is_hexagon(de):
        return kd.s <= de.s1_max and kd.e_max <= de.e1_max
    return corner_radius(kd.s, kd.e_max) < shank_radius(de)


def layout(s: str, drive: str) -> BitLayout:
    de = DRIVE_ENDS[drive]
    kd = KEY_SIZES[s]
    length = BIT_LENGTH[drive]
    l2 = TIP_LENGTH[s]
    inside = tip_inside_shank(s, de)
    if inside:
        r0 = TAPER_START * kd.s / 2
        taper_end = l2 + (shank_radius(de) - r0) / math.tan(math.radians(TAPER_ANGLE))
    else:
        taper_end = l2
    return BitLayout(length, l2, taper_end, inside)


def build_bit(s: str, drive: str) -> Part:
    """Build the bit.

    Coordinate system: Z is the bit axis, the tip's end face lies at z = 0
    and the drive end's face at z = l1. Flats of tip and drive end are
    parallel (two of them face +-Y).
    """
    de = DRIVE_ENDS[drive]
    kd = KEY_SIZES[s]
    lay = layout(s, drive)
    if lay.taper_end > lay.length - de.l1:
        raise RuntimeError(f"bit {drive} - {s}: taper runs into the drive end")
    r_tip = corner_radius(kd.s, kd.e_max)
    tan_t = math.tan(math.radians(TAPER_ANGLE))
    if lay.tip_in_shank:
        # Shank from the end of the tip, trimmed to the taper cone; the tip
        # reaches up into the taper until the cone has passed its corners.
        shank = drive_end_shank(de, lay.tip_length, lay.length)
        r0 = TAPER_START * kd.s / 2
        shank = shank - Pos(0, 0, lay.tip_length) * cone_trim(r0, shank_radius(de), tan_t)
        tip_top = lay.tip_length + (1.05 * r_tip - r0) / tan_t
    else:
        # The tip is the larger section (s = 8 on C 8 / E 8): the shank
        # starts a little inside the tip, which ends square.
        shank = drive_end_shank(de, lay.tip_length - 0.5, lay.length)
        tip_top = lay.tip_length
    tip = extrude(hex_section(kd.s, kd.e_max), amount=tip_top)
    f = TIP_CHAMFER_FRACTION * kd.f_max
    tip = tip - cone_trim(r_tip - f, r_tip, 1.0)
    bit = shank + tip
    if len(bit.solids()) != 1 or not bit.is_valid:
        raise RuntimeError(f"ISO 2351-3 bit {drive} - {s} failed")
    return bit


_DRIVE_ORDER = list(BIT_LENGTH)


class ISO2351(Standard):
    id = "iso2351-3"
    title = "ISO 2351-3"
    summary = "Screwdriver bits for hexagon socket screws, s = 0.7 to 12 mm"
    category = "Tools"
    source = (
        "Values in mm, from ISO 2351-3:2002 Table 1, ISO 1173:2001 Tables 1 to 7 "
        "(drive ends) and ISO 2936:2014 Table 1 (tips)."
    )

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="drive",
                label="Drive end (ISO 1173)",
                kind="select",
                default="C6.3",
                options=[
                    Option(d, _drive_label(DRIVE_ENDS[d])) for d in _DRIVE_ORDER
                ],
            ),
            Parameter(
                name="size",
                label="Tip width across flats s",
                kind="select",
                default="5",
                options=[Option(s, f"{s} mm") for s in TIP_LENGTH],
                help="Table 1 recommends only some drive ends for each tip size.",
            ),
        ]

    def validate(self, raw: dict[str, Any]) -> dict[str, Any]:
        drive = str(raw.get("drive", "C6.3"))
        if drive not in BIT_LENGTH:
            raise ParameterError(f"unknown drive end {drive!r}; choose one of {', '.join(_DRIVE_ORDER)}")
        size = str(raw.get("size", "5"))
        if size not in TIP_LENGTH:
            raise ParameterError(f"unknown tip size {size!r}; choose one of {', '.join(TIP_LENGTH)}")
        if drive not in COMBINATIONS[size]:
            ok = ", ".join(DRIVE_ENDS[d].name for d in COMBINATIONS[size])
            raise ParameterError(
                f"ISO 2351-3 has no bit {DRIVE_ENDS[drive].name} for s = {size}; "
                f"drive ends for s = {size}: {ok}"
            )
        return {"drive": drive, "size": size}

    def designation(self, p: dict[str, Any]) -> str:
        return f"Bit ISO 2351-3 {DRIVE_ENDS[p['drive']].name} - {p['size']}"

    def file_stem(self, p: dict[str, Any]) -> str:
        return f"ISO2351-3_{p['drive']}-{p['size']}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        de = DRIVE_ENDS[p["drive"]]
        kd = KEY_SIZES[p["size"]]
        lay = layout(p["size"], p["drive"])
        dims = [
            Dimension("l1", "Bit length (±2)", lay.length),
            Dimension("s", "Tip width across flats (ISO 2936, max / min)",
                      f"{kd.s_max:.2f} / {kd.s_min:.2f}"),
            Dimension("e", "Tip width across corners (max / min)",
                      f"{kd.e_max:.2f} / {kd.e_min:.2f}"),
            Dimension("l2", "Tip length, min.", lay.tip_length),
        ]
        dims += _drive_dimensions(de)
        dims.append(Dimension("Md", "Minimum proof torque", PROOF_TORQUE[p["size"]], "N·m"))
        return dims

    def notes(self, p: dict[str, Any]) -> list[str]:
        de = DRIVE_ENDS[p["drive"]]
        lay = layout(p["size"], p["drive"])
        out = []
        if not de.recommended:
            out.append(f"Drive end {de.name} is marked 'not recommended' in ISO 1173.")
        out.append(
            "Tip at s max (the nominal size from s = 1.5 up) with the corners "
            "turned to e max, l2 min long, its end edge chamfered at 45° (half of "
            "ISO 2936's f max)."
        )
        if lay.tip_in_shank:
            out.append(
                f"The shape between tip and drive end is the manufacturer's choice "
                f"(ISO 2351-3 clause 3); the model tapers the shank at "
                f"{_fmt(TAPER_ANGLE)}° to the axis down to the tip."
            )
        else:
            out.append(
                "The tip is wider than the drive end here, so the model steps "
                "down from the tip to the drive end; the shape between them is the "
                "manufacturer's choice (ISO 2351-3 clause 3)."
            )
        out.append(_drive_note(de))
        out.append("Tip end face at z = 0; the bit runs up the Z axis to the drive end at z = l1.")
        return out

    def build(self, p: dict[str, Any]) -> Part:
        part = build_bit(p["size"], p["drive"])
        part.label = self.designation(p)
        return part


def _drive_label(de: DriveEnd) -> str:
    kind = {
        "A": "hexagon with collar",
        "C": "hexagon",
        "E": "hexagon with ball groove",
        "G": "cylinder with flats",
    }[de.form]
    extra = ", not recommended" if not de.recommended else ""
    return f"{de.name} ({kind}, l1 = {_fmt(BIT_LENGTH[de.key])} mm{extra})"


def _drive_dimensions(de: DriveEnd) -> list[Dimension]:
    dims = []
    if de.hexagon:
        dims += [
            Dimension("s1", "Drive hexagon across flats (max / min)", f"{de.s1_max:.2f} / {de.s1_min:.2f}"),
            Dimension("e1", "Drive hexagon across corners (max / min)", f"{de.e1_max:.2f} / {de.e1_min:.2f}"),
        ]
    else:
        dims += [
            Dimension("d1", "Drive cylinder (f8)", de.d1),
            Dimension("e1", "Across the flats (max / min)", f"{de.e1_max:.2f} / {de.e1_min:.2f}"),
        ]
    if de.form == "A":
        dims.append(Dimension("d1", "Collar (h9)", de.d1))
    dims.append(Dimension("l1 d", "Drive end length, min.", de.l1))
    if de.d3 is not None:
        dims.append(Dimension("d3", "Groove bottom diameter (h12)", de.d3))
        dims.append(Dimension("l3", "End face to groove", de.l3))
    else:
        dims.append(Dimension("l3", "End face to cross hole", de.l3))
    return dims


def _drive_note(de: DriveEnd) -> str:
    base = "Drive end to ISO 1173 at s1 max / e1 max"
    if de.form == "A":
        return (f"{base}: hexagon l5 = {_fmt(de.l5)}, collar d1 with the round groove, "
                f"R 0.6 shoulder at l1; the shank behind it (d1 + 2 mm) is a model choice.")
    if de.form == "C":
        if de.d3 is None:
            return f"{base}: hexagon with a 2 mm cross hole at l3."
        return f"{base}: hexagon with a 90° V groove on the corners at l3 (β = 80 to 120°)."
    if de.form == "E":
        return f"{base}: hexagon with the round ball groove (flat l7 = {_fmt(de.l7)} at d3)."
    return ("Drive end to ISO 1173: cylinder d1 with two flats at the mean of e1 over "
            f"l3 − l5 = {_fmt(de.l3 - de.l5)} mm and the round groove at l3.")

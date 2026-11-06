"""ISO 8734 parallel pins of hardened steel (dowel pins)."""

from __future__ import annotations

import math
from typing import Any

from build123d import Part

from ..geometry import revolve_profile
from .base import Dimension, Option, Parameter, ParameterError, Standard
from .iso8734_data import CHAMFER_ANGLE, SIZES, PinData


def _fmt(x: float) -> str:
    return f"{x:g}"


def chamfer_depth(pd: PinData) -> float:
    """Radial depth of the end chamfer: axial length c at ~15 deg."""
    return pd.c * math.tan(math.radians(CHAMFER_ANGLE))


def build_pin(pd: PinData, l: float) -> Part:
    """Build the pin solid.

    Coordinate system: Z is the pin axis, one end face lies in the XY plane
    at z = 0 and the pin extends to z = -l, like the screws in this project.
    Both ends carry the ISO 8734 chamfer of axial length c at ~15 deg.
    Nominal d is used (the standard tolerance is m6).
    """
    R = pd.d / 2
    r_end = R - chamfer_depth(pd)
    c = pd.c
    return revolve_profile([
        (0.0, 0.0),
        (r_end, 0.0),
        (R, -c),
        (R, -l + c),
        (r_end, -l),
        (0.0, -l),
    ])


class ISO8734(Standard):
    id = "iso8734"
    title = "ISO 8734"
    summary = "Parallel pins (dowel pins), hardened steel, d = 1 to 20 mm"
    category = "Pins"
    source = "Values in mm, from ISO 8734:1997 Table 1."

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="size",
                label="Nominal diameter d",
                kind="select",
                default="6",
                options=[Option(s, f"{s} mm") for s in SIZES],
            ),
            Parameter(
                name="length",
                label="Nominal length l",
                kind="length",
                default=20,
                depends_on="size",
                preferred={s: pd.standard_lengths() for s, pd in SIZES.items()},
                limits={s: [pd.l_min, pd.l_max] for s, pd in SIZES.items()},
                unit="mm",
                help="Overall length, end face to end face.",
            ),
        ]

    def validate(self, raw: dict[str, Any]) -> dict[str, Any]:
        size = str(raw.get("size", "6"))
        if size not in SIZES:
            raise ParameterError(f"unknown diameter {size!r}; choose one of {', '.join(SIZES)}")
        pd = SIZES[size]
        try:
            length = float(raw.get("length", 20))
        except (TypeError, ValueError):
            raise ParameterError("length must be a number") from None
        if not math.isfinite(length):
            raise ParameterError("length must be a number")
        length = round(length, 2)
        if not pd.l_min <= length <= pd.l_max:
            raise ParameterError(
                f"length for d = {size} must be between {_fmt(pd.l_min)} and "
                f"{_fmt(pd.l_max)} mm"
            )
        return {"size": size, "length": length}

    def designation(self, p: dict[str, Any]) -> str:
        return f"ISO 8734 - {p['size']} x {_fmt(p['length'])}"

    def file_stem(self, p: dict[str, Any]) -> str:
        return f"ISO8734_{p['size']}x{_fmt(p['length'])}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        pd = SIZES[p["size"]]
        return [
            Dimension("d m6", "Nominal diameter", pd.d),
            Dimension("l", "Nominal length", p["length"]),
            Dimension("c ≈", "End chamfer length", pd.c),
            Dimension("α", "Chamfer angle to pin surface", "≈ 15°", ""),
            Dimension("de", "End face dia. (model, d − 2c·tan α)",
                      round(pd.d - 2 * chamfer_depth(pd), 3)),
        ]

    def notes(self, p: dict[str, Any]) -> list[str]:
        pd = SIZES[p["size"]]
        l = p["length"]
        out = []
        if l not in pd.standard_lengths():
            pref = ", ".join(_fmt(x) for x in pd.standard_lengths())
            out.append(
                f"{_fmt(l)} mm is not a preferred length for d = {pd.size} "
                f"(preferred: {pref})."
            )
        out.append(
            "Modeled at nominal d (tolerance m6) with the Figure 1 chamfer of "
            "length c at about 15° on both ends. A radius or dimpled end is also "
            "permitted, at the manufacturer's discretion."
        )
        out.append(
            "Type A (through hardened) and type B (case hardened) have the same "
            "shape; the full designation adds the type and material, e.g. "
            f"ISO 8734 - {pd.size} x {_fmt(l)} - A - St."
        )
        out.append("One end face at z = 0, the pin extends to z = -l.")
        return out

    def build(self, p: dict[str, Any]) -> Part:
        part = build_pin(SIZES[p["size"]], p["length"])
        part.label = self.designation(p)
        return part

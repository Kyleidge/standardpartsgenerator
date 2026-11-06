"""ISO 7089 and ISO 7090 plain washers, normal series, product grade A."""

from __future__ import annotations

import math
from typing import Any

from build123d import Part

from ..geometry import revolve_profile
from .base import Dimension, Option, Parameter, ParameterError, Standard
from .iso7089_data import (
    CHAMFER_ANGLE,
    CHAMFER_HEIGHT,
    ISO7089_SIZES,
    ISO7090_SIZES,
    WasherData,
)


def chamfer_size(wd: WasherData) -> tuple[float, float]:
    """(radial, axial) size of the ISO 7090 outer chamfer."""
    axial = CHAMFER_HEIGHT * wd.h
    return axial * math.tan(math.radians(CHAMFER_ANGLE)), axial


def build_washer(wd: WasherData, chamfered: bool) -> Part:
    """Build the washer solid.

    Coordinate system: Z is the washer axis, the faces lie at z = 0 and
    z = h. Nominal sizes: d1 nom (= d1 min), d2 nom (= d2 max), h nom. The
    ISO 7090 chamfer is on the outer edge of the face at z = h.
    """
    r1, r2, h = wd.d1 / 2, wd.d2 / 2, wd.h
    pts: list[tuple[float, float]] = [(r1, 0.0), (r2, 0.0)]
    if chamfered:
        dr, dz = chamfer_size(wd)
        pts += [(r2, h - dz), (r2 - dr, h)]
    else:
        pts.append((r2, h))
    pts.append((r1, h))
    part = revolve_profile(pts)
    if len(part.solids()) != 1 or not part.is_valid:
        raise RuntimeError(f"washer build failed for size {wd.size}")
    return part


class _PlainWasher(Standard):
    category = "Washers"
    number: str
    sizes: dict[str, WasherData]
    chamfered: bool
    default_size = "8"

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="size",
                label="Nominal size",
                kind="select",
                default=self.default_size,
                options=[
                    Option(s, f"{s} (for M{s})" + ("" if wd.preferred else ", non-preferred"))
                    for s, wd in self.sizes.items()
                ],
                help="The nominal size is the thread size of the matching screw.",
            ),
        ]

    def validate(self, raw: dict[str, Any]) -> dict[str, Any]:
        size = str(raw.get("size", self.default_size))
        if size.upper().startswith("M"):
            size = size[1:]
        if size not in self.sizes:
            raise ParameterError(
                f"unknown size {size!r}; choose one of {', '.join(self.sizes)}"
            )
        return {"size": size}

    def designation(self, p: dict[str, Any]) -> str:
        return f"ISO {self.number} - {p['size']}"

    def file_stem(self, p: dict[str, Any]) -> str:
        return f"ISO{self.number}_{p['size']}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        wd = self.sizes[p["size"]]
        dims = [
            Dimension("d", "Nominal size (thread)", wd.d),
            Dimension("d1", "Hole diameter (nom. = min.)", wd.d1_min),
            Dimension("d1 max", "Hole diameter, max.", wd.d1_max),
            Dimension("d2", "Outside diameter (nom. = max.)", wd.d2_max),
            Dimension("d2 min", "Outside diameter, min.", wd.d2_min),
            Dimension("h", "Thickness (nom.)", wd.h_nom),
            Dimension("h max", "Thickness, max.", wd.h_max),
            Dimension("h min", "Thickness, min.", wd.h_min),
        ]
        if self.chamfered:
            dr, dz = chamfer_size(wd)
            dims += [
                Dimension("chamfer", "Outer chamfer angle (to axis)", CHAMFER_ANGLE, "°"),
                Dimension("chamfer h", "Outer chamfer height", round(dz, 3)),
                Dimension("chamfer w", "Outer chamfer width", round(dr, 3)),
            ]
        return dims

    def notes(self, p: dict[str, Any]) -> list[str]:
        wd = self.sizes[p["size"]]
        out = []
        if not wd.preferred:
            out.append(f"Size {wd.size} is a non-preferred size.")
        out.append("Modeled at nominal sizes: d1 nom, d2 nom, h nom.")
        if self.chamfered:
            out.append(
                f"Outer edge chamfered on the face at z = h. ISO {self.number} allows "
                "30° to 45° and 0.25 h to 0.5 h; the model uses the middle of both "
                f"ranges ({CHAMFER_ANGLE:g}°, {CHAMFER_HEIGHT:g} h)."
            )
        out.append(
            f"The full designation adds the hardness class, e.g. "
            f"Washer ISO {self.number} - {wd.size} - 200 HV (or 300 HV)."
        )
        return out

    def build(self, p: dict[str, Any]) -> Part:
        part = build_washer(self.sizes[p["size"]], self.chamfered)
        part.label = self.designation(p)
        return part


class ISO7089(_PlainWasher):
    id = "iso7089"
    title = "ISO 7089"
    summary = "Plain washers, normal series, product grade A, sizes 1.6 to 64"
    source = "Values in mm, from ISO 887:2000 Table 3 (normal series, ISO 7089)."
    number = "7089"
    sizes = ISO7089_SIZES
    chamfered = False


class ISO7090(_PlainWasher):
    id = "iso7090"
    title = "ISO 7090"
    summary = "Plain washers, chamfered, normal series, product grade A, sizes 5 to 64"
    source = "Values in mm, from ISO 887:2000 Table 3 (normal series, ISO 7090)."
    number = "7090"
    sizes = ISO7090_SIZES
    chamfered = True

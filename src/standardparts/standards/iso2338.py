"""ISO 2338 parallel pins of unhardened steel and austenitic stainless steel."""

from __future__ import annotations

import math
from typing import Any

from build123d import Part

from ..geometry import revolve_profile
from .base import Dimension, Option, Parameter, ParameterError, Standard
from .iso2338_data import CHAMFER_ANGLE, SIZES, TOLERANCES, PinData, deviations_um


def _fmt(x: float) -> str:
    return f"{x:g}"


def chamfer_depth(pd: PinData) -> float:
    """Radial depth of the end chamfer: axial length c at ~15 deg."""
    return pd.c * math.tan(math.radians(CHAMFER_ANGLE))


def length_tolerance(l: float) -> float:
    """± tolerance on l from Table 1 (l min / l max columns)."""
    if l <= 10:
        return 0.25
    if l <= 50:
        return 0.5
    return 0.75


def expected_volume(pd: PinData, l: float) -> float:
    """Exact volume of the modeled pin: a cylinder with two conical frusta."""
    R = pd.d / 2
    r = R - chamfer_depth(pd)
    c = pd.c
    return math.pi * R * R * (l - 2 * c) + 2 * math.pi * c / 3 * (R * R + R * r + r * r)


def build_pin(pd: PinData, l: float) -> Part:
    """Build the pin solid.

    Coordinate system: Z is the pin axis, one end face lies in the XY plane
    at z = 0 and the pin extends to z = -l, like the screws in this project.
    Both ends carry the Figure 1 chamfer of axial length c at ~15 deg.
    Nominal d is used (the tolerance class m6 or h8 does not change it).
    """
    R = pd.d / 2
    r_end = R - chamfer_depth(pd)
    c = pd.c
    part = revolve_profile([
        (0.0, 0.0),
        (r_end, 0.0),
        (R, -c),
        (R, -l + c),
        (r_end, -l),
        (0.0, -l),
    ])
    expected = expected_volume(pd, l)
    if (
        not part.is_valid
        or len(part.solids()) != 1
        or abs(part.volume - expected) > 1e-6 * expected
    ):
        raise RuntimeError(f"pin construction failed for ISO 2338 - {pd.size} x {l:g}")
    return part


class ISO2338(Standard):
    id = "iso2338"
    title = "ISO 2338"
    summary = "Parallel pins, unhardened steel and austenitic stainless steel, d = 0.6 to 50 mm"
    category = "Pins"
    source = "Values in mm, from ISO 2338:1997 Table 1."

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
                default=30,
                depends_on="size",
                preferred={s: pd.standard_lengths() for s, pd in SIZES.items()},
                limits={s: [pd.l_min, pd.l_max] for s, pd in SIZES.items()},
                unit="mm",
                help="Overall length, end face to end face.",
            ),
            Parameter(
                name="tolerance",
                label="Diameter tolerance",
                kind="select",
                default="m6",
                options=[
                    Option("m6", "m6 (ground, Ra < 0.8 µm)"),
                    Option("h8", "h8 (Ra < 1.6 µm)"),
                ],
                help="Changes the designation and the limits of d only; the model "
                "is at nominal d either way.",
            ),
        ]

    def validate(self, raw: dict[str, Any]) -> dict[str, Any]:
        size = str(raw.get("size", "6"))
        if size.endswith(".0"):
            size = size[:-2]
        if size not in SIZES:
            raise ParameterError(f"unknown diameter {size!r}; choose one of {', '.join(SIZES)}")
        pd = SIZES[size]
        try:
            length = float(raw.get("length", 30))
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
        tolerance = str(raw.get("tolerance", "m6"))
        if tolerance not in TOLERANCES:
            raise ParameterError(f"tolerance must be one of {', '.join(TOLERANCES)}")
        return {"size": size, "length": length, "tolerance": tolerance}

    def designation(self, p: dict[str, Any]) -> str:
        return f"ISO 2338 - {p['size']} {p['tolerance']} x {_fmt(p['length'])}"

    def file_stem(self, p: dict[str, Any]) -> str:
        suffix = "" if p["tolerance"] == "m6" else f"_{p['tolerance']}"
        return f"ISO2338_{p['size']}x{_fmt(p['length'])}{suffix}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        pd = SIZES[p["size"]]
        tol = p["tolerance"]
        lo, hi = deviations_um(pd.d, tol)
        return [
            Dimension(f"d {tol}", "Nominal diameter", pd.d),
            Dimension("d max", f"Largest diameter ({tol}, ISO 286-2)", round(pd.d + hi / 1000, 3)),
            Dimension("d min", f"Smallest diameter ({tol}, ISO 286-2)", round(pd.d + lo / 1000, 3)),
            Dimension("l", "Nominal length", p["length"]),
            Dimension("Δl ±", "Length tolerance (Table 1)", length_tolerance(p["length"])),
            Dimension("c ≈", "End chamfer length", pd.c),
            Dimension("α ≈", "Chamfer angle to pin surface", CHAMFER_ANGLE, "°"),
            Dimension("de", "End face dia. (model, d − 2c·tan α)",
                      round(pd.d - 2 * chamfer_depth(pd), 3)),
            Dimension("Ra", "Surface roughness, max.", 0.8 if tol == "m6" else 1.6, "µm"),
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
            f"Modeled at nominal d (tolerance {p['tolerance']}) with the Figure 1 "
            "chamfer of length c at about 15° on both ends. A radius or dimpled "
            "end is also permitted, at the manufacturer's discretion."
        )
        out.append(
            "The full designation adds the material: St (unhardened steel, "
            "125 to 245 HV30) or A1 (austenitic stainless steel, 210 to 280 HV30), "
            f"e.g. Parallel pin ISO 2338 - {pd.size} {p['tolerance']} x {_fmt(l)} - St."
        )
        out.append("One end face at z = 0, the pin extends to z = -l.")
        return out

    def build(self, p: dict[str, Any]) -> Part:
        part = build_pin(SIZES[p["size"]], p["length"])
        part.label = self.designation(p)
        return part

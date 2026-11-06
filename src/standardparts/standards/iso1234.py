"""ISO 1234 split pins (cotter pins)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from build123d import Axis, Edge, Face, Part, Pos, Wire, extrude, revolve

from .base import Dimension, Option, Parameter, ParameterError, Standard
from .iso1234_data import SIZES, SplitPinData

# The two legs are modeled with a small slit between their flat faces
# instead of touching: faces of one solid that coincide make invalid
# topology. The slit is this fraction of d; the round outer faces stay on
# the diameter d, so the pin still measures d across the legs.
SLIT = 0.01


def _fmt(x: float) -> str:
    return f"{x:g}"


@dataclass(frozen=True)
class SplitPinLayout:
    """Path and section of the modeled pin (all in mm).

    The wire's section is a circular segment: the disc of diameter d cut by
    a chord at slit / 2 from its centre, so each leg is "half round" and
    both legs together fill the circle d. The path is the line of the flat
    face: up leg 1 (x = +slit/2), a reverse bend of radius rho to the
    right, the eye arc of radius r_in around (0, zc) over the top, the
    mirrored reverse bend, and down leg 2 (x = -slit/2). The flat face is
    on the inside of the eye and the outside of the reverse bends.
    """

    d: float
    c: float
    b: float
    a: float
    l: float
    slit: float
    r_in: float     # eye: radius of the flat face (half the hole width)
    zc: float       # eye centre height
    rho: float      # reverse-bend radius of the flat face
    theta: float    # reverse-bend angle (rad)

    @property
    def thickness(self) -> float:
        """Section depth from the flat face to the round back."""
        return self.d / 2 - self.slit / 2

    @property
    def half_width(self) -> float:
        """Half the width of the flat face (along Y)."""
        R, s = self.d / 2, self.slit / 2
        return math.sqrt(R * R - s * s)

    @property
    def section_area(self) -> float:
        R, s = self.d / 2, self.slit / 2
        return R * R * math.acos(s / R) - s * self.half_width

    @property
    def section_centroid(self) -> float:
        """Distance of the section centroid from the flat face."""
        centroid_from_centre = (2 / 3) * self.half_width ** 3 / self.section_area
        return centroid_from_centre - self.slit / 2

    @property
    def eye_angle(self) -> float:
        return math.pi + 2 * self.theta

    def volume(self) -> float:
        """Exact volume by Pappus: straight legs, two bends and the eye."""
        A, e = self.section_area, self.section_centroid
        legs = A * (2 * self.l + self.a)
        bends = 2 * A * self.theta * (self.rho - e)
        eye = A * self.eye_angle * (self.r_in + e)
        return legs + bends + eye


def layout(sd: SplitPinData, l: float) -> SplitPinLayout:
    """Fit the path to d max, c max, b and a max of Table 1."""
    d, c, b, a = sd.d_max, sd.c_max, sd.b, sd.a_max
    g = SLIT * d
    t = d / 2 - g / 2
    r_in = c / 2 - t                # outer eye width = 2 (r_in + t) = c
    zc = b - c / 2                  # top of the eye at z = zc + r_in + t = b
    # Reverse bend from (g/2, 0) tangent to the eye circle: its centre
    # (g/2 + rho, 0) is rho + r_in from the eye centre (0, zc).
    rho = (zc * zc + g * g / 4 - r_in * r_in) / (2 * r_in - g)
    theta = math.atan2(zc, g / 2 + rho)
    if not (r_in > 0 and zc > r_in and rho > 1.2 * t):
        raise RuntimeError(f"no eye layout for ISO 1234 - {sd.size}")
    return SplitPinLayout(d, c, b, a, l, g, r_in, zc, rho, theta)


def build_split_pin(sd: SplitPinData, l: float) -> Part:
    """Build the split pin solid.

    Coordinate system: Z is the pin axis. The legs start at z = 0 (the
    start of l, under the eye); the eye is above, up to z = b, and the
    shorter leg ends at z = -l, the longer one at z = -(l + a). The eye and
    the legs lie in the XZ plane (eye width c along X), the flat faces of
    the legs face each other across the YZ plane, the longer leg is on +X.
    """
    lay = layout(sd, l)
    R, s, hw = lay.d / 2, lay.slit / 2, lay.half_width
    deg = math.degrees

    # Section at the start of the path, in the XY plane, flat face at x = s.
    section = Face(Wire([
        Edge.make_line((s, -hw, 0), (s, hw, 0)),
        Edge.make_three_point_arc((s, hw, 0), (R, 0, 0), (s, -hw, 0)),
    ]))
    # Each piece starts on the previous one's end face, so neighbours share
    # identical faces and fuse cleanly.
    leg1 = extrude(Pos(0, 0, -(l + lay.a)) * section, amount=l + lay.a, dir=(0, 0, 1))
    bend1_axis = Axis((s + lay.rho, 0, 0), (0, 1, 0))
    bend1 = revolve(section, bend1_axis, deg(lay.theta))
    eye_start = section.rotate(bend1_axis, deg(lay.theta))
    eye_axis = Axis((0, 0, lay.zc), (0, -1, 0))
    eye = revolve(eye_start, eye_axis, deg(lay.eye_angle))
    eye_end = eye_start.rotate(eye_axis, deg(lay.eye_angle))
    bend2_axis = Axis((-(s + lay.rho), 0, 0), (0, 1, 0))
    bend2 = revolve(eye_end, bend2_axis, deg(lay.theta))
    leg2_top = eye_end.rotate(bend2_axis, deg(lay.theta))
    leg2 = extrude(leg2_top, amount=l, dir=(0, 0, -1))

    part = leg1.fuse(bend1, eye, bend2, leg2).clean()
    expected = lay.volume()
    bb = part.bounding_box()
    ok = (
        part.is_valid
        and len(part.solids()) == 1
        and abs(part.volume - expected) < 1e-6 * expected
        and abs(bb.max.Z - lay.b) < 1e-6
        and abs(bb.min.Z + l + lay.a) < 1e-6
        and abs(bb.size.X - lay.c) < 1e-6
    )
    if not ok:
        raise RuntimeError(f"split pin construction failed for ISO 1234 - {sd.size} x {l:g}")
    return part


class ISO1234(Standard):
    id = "iso1234"
    title = "ISO 1234"
    summary = "Split pins (cotter pins), nominal sizes 0.6 to 20 mm"
    category = "Pins"
    source = "Values in mm, from ISO 1234:1997 Tables 1 and 2."

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="size",
                label="Nominal size (pin hole dia.)",
                kind="select",
                default="4",
                options=[Option(s, f"{s} mm  (d max {_fmt(sd.d_max)})") for s, sd in SIZES.items()],
            ),
            Parameter(
                name="length",
                label="Nominal length l",
                kind="length",
                default=32,
                depends_on="size",
                preferred={s: sd.standard_lengths() for s, sd in SIZES.items()},
                limits={s: [sd.l_min, sd.l_max] for s, sd in SIZES.items()},
                unit="mm",
                help="From under the eye to the end of the shorter leg.",
            ),
        ]

    def validate(self, raw: dict[str, Any]) -> dict[str, Any]:
        size = str(raw.get("size", "4"))
        if size.endswith(".0"):
            size = size[:-2]
        if size not in SIZES:
            raise ParameterError(f"unknown size {size!r}; choose one of {', '.join(SIZES)}")
        sd = SIZES[size]
        try:
            length = float(raw.get("length", 32))
        except (TypeError, ValueError):
            raise ParameterError("length must be a number") from None
        if not math.isfinite(length):
            raise ParameterError("length must be a number")
        length = round(length, 2)
        if not sd.l_min <= length <= sd.l_max:
            raise ParameterError(
                f"length for size {size} must be between {_fmt(sd.l_min)} and "
                f"{_fmt(sd.l_max)} mm"
            )
        return {"size": size, "length": length}

    def designation(self, p: dict[str, Any]) -> str:
        return f"ISO 1234 - {p['size']} x {_fmt(p['length'])}"

    def file_stem(self, p: dict[str, Any]) -> str:
        return f"ISO1234_{p['size']}x{_fmt(p['length'])}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        sd = SIZES[p["size"]]
        lay = layout(sd, p["length"])

        def rng(r: tuple[float | None, float | None]) -> str:
            lo, hi = r
            if lo is None:
                return f"up to {_fmt(hi)}"
            if hi is None:
                return f"over {_fmt(lo)}"
            return f"over {_fmt(lo)} to {_fmt(hi)}"

        return [
            Dimension("size", "Nominal size = pin hole dia.", sd.hole),
            Dimension("hole", "Pin hole tolerance (recommended)",
                      "H13" if sd.hole <= 1.2 else "H14", ""),
            Dimension("l", "Nominal length (to the shorter leg)", p["length"]),
            Dimension("d max", "Pin diameter", sd.d_max),
            Dimension("d min", "Pin diameter", sd.d_min),
            Dimension("a max", "Extended prong", sd.a_max),
            Dimension("a min", "Extended prong", sd.a_min),
            Dimension("b ≈", "Eye length", sd.b),
            Dimension("c max", "Eye width", sd.c_max),
            Dimension("c min", "Eye width", sd.c_min),
            Dimension("bolt", "For bolt diameters", rng(sd.bolt), "mm"),
            Dimension("clevis", "For clevis pin diameters", rng(sd.clevis), "mm"),
            Dimension("eye hole", "Eye hole width (model)", round(2 * lay.r_in, 3)),
            Dimension("slit", "Gap between the legs (model)", round(lay.slit, 3)),
        ]

    def notes(self, p: dict[str, Any]) -> list[str]:
        sd = SIZES[p["size"]]
        l = p["length"]
        out = []
        if l not in sd.standard_lengths():
            pref = ", ".join(_fmt(x) for x in sd.standard_lengths())
            out.append(
                f"{_fmt(l)} mm is not a preferred length for size {sd.size} "
                f"(preferred: {pref})."
            )
        out.append(
            "Modeled with d max, c max, a max and b of Table 1: a half-round wire "
            "bent into a round eye with short reverse bends into the legs. The "
            "exact bend shape is not specified by the standard; square leg ends "
            "(the end shape is optional)."
        )
        out.append(
            f"The legs are {_fmt(round(SLIT * sd.d_max, 3))} mm apart (1 % of d) "
            "instead of touching, so the model is one valid solid; across the "
            "legs it still measures d."
        )
        out.append(
            "Legs start at z = 0, the eye goes up to z = b, the shorter leg ends at "
            "z = -l and the longer one (on +X) at z = -(l + a). Eye in the XZ plane."
        )
        out.append(
            "The full designation adds the material (St, CuZn, Cu, Al or A), "
            f"e.g. Split pin ISO 1234 - {sd.size} x {_fmt(l)} - St."
        )
        return out

    def build(self, p: dict[str, Any]) -> Part:
        part = build_split_pin(SIZES[p["size"]], p["length"])
        part.label = self.designation(p)
        return part

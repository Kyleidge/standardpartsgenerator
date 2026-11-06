"""Hexagon socket set screws: ISO 4026 (flat point), ISO 4027 (cone point),
ISO 4028 (dog point) and ISO 4029 (cup point).

Coordinate system (all four): Z is the screw axis, the socket end face
lies in the XY plane at z = 0 and the point is at z = -l.

Model, following Figure 1 of the standards at nominal sizes:

* Threaded over the whole length (screws.threaded_rod), both thread modes.
* Socket end chamfered down to df = minor thread diameter d3 at 90 deg
  included (120 deg for the short lengths shaded in Table 1).
* Hexagon socket s nom to depth t min (the short-length t min for shaded
  lengths) with a 118 deg drill point.
* ISO 4026: ~45 deg chamfer down to a flat point of diameter dp max.
* ISO 4027: cone point at gamma = 90 deg included (120 deg for shaded
  lengths) truncated at dt max.
* ISO 4029: ~45 deg chamfer down to dz max, then a 120 deg conical cup
  whose mouth is at dz min, which leaves a narrow land between the limits.
* ISO 4028: a dog of diameter dp max and length z max (short dog for the
  shaded lengths, long dog otherwise), joined to the thread by a 45 deg
  cone. The dog edges are left sharp (Figure 1 asks for an undimensioned
  "small radius").
"""

from __future__ import annotations

import math
from typing import Any

from build123d import Part

from ..geometry import MetricThread, helical_thread, revolve_profile
from ..screws import THREAD_MODES, Point, _fuse_ridge, cut_hex_socket, threaded_rod
from .base import Dimension, Option, Parameter, ParameterError, Standard
from .set_screws_data import (
    DP,
    DT_MAX,
    DZ,
    SOCKET,
    Z_LONG,
    Z_SHORT,
    SocketData,
    is_short,
    length_range,
    standard_lengths,
)

DRILL_ANGLE = 118.0   # socket drill point (geometry.hex_socket default)
CUP_ANGLE = 120.0     # included angle of the ISO 4029 cup


def _fmt(x: float) -> str:
    return f"{x:g}"


def socket_depth(sd: SocketData, short: bool) -> float:
    return sd.t_min_short if short else sd.t_min_long


def drill_point_height(s: float) -> float:
    """Axial height of the drill cone below the socket (see geometry.hex_socket)."""
    return 0.96 * s / 2 / math.tan(math.radians(DRILL_ANGLE / 2))


def cut_cup(body: Part, r_mouth: float, l: float, what: str) -> Part:
    """Cut a conical cup (CUP_ANGLE included) with mouth radius r_mouth into
    the tip face at z = -l, and check the cut removed the expected volume."""
    tan_a = math.tan(math.radians(CUP_ANGLE / 2))
    h = r_mouth / tan_a
    eps = 0.2 * h  # start the tool below the tip face: no coincident faces
    tool = revolve_profile([
        (0.0, -l - eps),
        (r_mouth + eps * tan_a, -l - eps),
        (0.0, -l + h),
    ])
    cut = body - tool
    expected = math.pi * r_mouth**2 * h / 3
    removed = body.volume - cut.volume
    if (
        len(cut.solids()) != 1
        or not cut.is_valid
        or abs(removed - expected) > 0.02 * expected
    ):
        raise RuntimeError(f"cup cut failed for {what}")
    return cut


def dog_point_rod(
    thread: MetricThread,
    length: float,
    r_dog: float,
    z_dog: float,
    mode: str,
    top: Point,
    what: str,
) -> Part:
    """Set screw body with a dog point, z from -length to 0.

    Like screws.threaded_rod, with the point replaced by a dog: a cylinder
    of radius r_dog from the tip face (z = -length) up to the shoulder at
    z = -length + z_dog, then a 45 deg cone out to the thread. The socket
    end is chamfered by `top`. In modeled mode the thread ridge is trimmed
    by an envelope whose shoulder cone runs parallel to the core's, 0.03 P
    higher (coincident faces make the OCCT fuse drop the ridge silently),
    and the fuse is volume-checked by screws._fuse_ridge.
    """
    P = thread.P
    R = thread.d / 2
    r_core = thread.d1 / 2
    l = length
    r_top = thread.d3 / 2 if top.r_tip is None else top.r_tip
    if not 0 < r_dog < r_core or not 0 < z_dog < l:
        raise ValueError(f"dog does not fit the thread for {what}")
    z_sh = -l + z_dog
    tan_top = math.tan(math.radians(top.half_angle))

    def upper(r_limit: float) -> list[tuple[float, float]]:
        """Socket-end chamfer up to r_limit, from the outside in."""
        if r_top >= r_limit:
            return [(r_top, 0.0)]
        return [(r_limit, -(r_limit - r_top) / tan_top), (r_top, 0.0)]

    if mode == "simplified":
        return revolve_profile([
            (0.0, -l),
            (r_dog, -l),
            (r_dog, z_sh),
            (R, z_sh + (R - r_dog)),
            *upper(R),
            (0.0, 0.0),
        ])
    if mode != "modeled":
        raise ValueError(f"unknown thread mode {mode!r}")

    core = revolve_profile([
        (0.0, -l),
        (r_dog, -l),
        (r_dog, z_sh),
        (r_core, z_sh + (r_core - r_dog)),
        *upper(r_core),
        (0.0, 0.0),
    ])
    r_out = R + 0.05 * P
    z_lo, z_hi = z_sh + 0.03 * P, -0.03 * P
    envelope = revolve_profile([
        (0.0, z_lo),
        (r_dog, z_lo),
        (r_out, z_lo + (r_out - r_dog)),
        (r_out, z_hi - (r_out - r_top) / tan_top),
        (r_top, z_hi),
        (0.0, z_hi),
    ])
    ridge = helical_thread(thread, z_sh - P, P)
    return _fuse_ridge(core, ridge, envelope, what)


class SetScrew(Standard):
    """Common parameters, validation and build for the three set screws."""

    id: str
    number: str        # "4026"
    point_name: str    # "flat point"
    category = "Set screws"

    # --- point geometry, per standard ---------------------------------
    def point(self, sd: SocketData, short: bool) -> Point:
        raise NotImplementedError

    def finish(self, body: Part, sd: SocketData, l: float, what: str) -> Part:
        """Features cut after the socket (the ISO 4029 cup)."""
        return body

    def point_dimensions(self, sd: SocketData, short: bool) -> list[Dimension]:
        raise NotImplementedError

    def point_notes(self, sd: SocketData, short: bool) -> list[str]:
        return []

    def body(self, sd: SocketData, l: float, mode: str, short: bool, what: str) -> Part:
        """Threaded body with both end chamfers, before the socket is cut."""
        return threaded_rod(
            MetricThread(sd.d, sd.P), l, mode,
            point=self.point(sd, short), top=self.top(short), what=what,
        )

    def point_polyline(self, sd: SocketData, l: float, short: bool,
                       r_core: float) -> list[tuple[float, float]]:
        """Half-section of the point end in (r, z), from the thread core
        (r_core) to the axis; used by walls()."""
        pt = self.point(sd, short)
        r_tip = MetricThread(sd.d, sd.P).d3 / 2 if pt.r_tip is None else pt.r_tip
        z_pt = -l + (r_core - r_tip) / math.tan(math.radians(pt.half_angle))
        return [(r_core, z_pt), (r_tip, -l), *self.cup_profile(sd, l)]

    # --- shared --------------------------------------------------------
    @property
    def source(self) -> str:  # type: ignore[override]
        return f"Values in mm, from ISO {self.number}:2003 Table 1."

    def is_short(self, size: str, l: float) -> bool:
        return is_short(self.id, size, l)

    def length_range(self, size: str) -> tuple[float, float]:
        return length_range(self.id, size)

    def standard_lengths(self, size: str) -> list[float]:
        return standard_lengths(self.id, size)

    def top(self, short: bool) -> Point:
        """Socket-end chamfer: to df ~ d3 at 90 deg, 120 deg if short."""
        return Point(None, 60.0 if short else 45.0)

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="size",
                label="Thread size",
                kind="select",
                default="M6",
                options=[Option(s, f"{s} x {_fmt(sd.P)}") for s, sd in SOCKET.items()],
            ),
            Parameter(
                name="length",
                label="Nominal length l",
                kind="length",
                default=10,
                depends_on="size",
                preferred={s: self.standard_lengths(s) for s in SOCKET},
                limits={s: list(self.length_range(s)) for s in SOCKET},
                unit="mm",
                help="Overall length, socket face to point.",
            ),
            Parameter(
                name="thread",
                label="Thread",
                kind="select",
                default="simplified",
                options=[Option(k, v) for k, v in THREAD_MODES.items()],
                help="Simplified is lighter and is what most CAD libraries ship; "
                "the outer cylinder is the threaded face for a cosmetic thread.",
            ),
        ]

    def validate(self, raw: dict[str, Any]) -> dict[str, Any]:
        size = str(raw.get("size", "M6"))
        if size not in SOCKET:
            raise ParameterError(f"unknown size {size!r}; choose one of {', '.join(SOCKET)}")
        l_min, l_max = self.length_range(size)
        try:
            length = float(raw.get("length", 10))
        except (TypeError, ValueError):
            raise ParameterError("length must be a number") from None
        if not math.isfinite(length):
            raise ParameterError("length must be a number")
        length = round(length, 2)
        if not l_min <= length <= l_max:
            raise ParameterError(
                f"length for {size} must be between {_fmt(l_min)} and "
                f"{_fmt(l_max)} mm"
            )
        thread = str(raw.get("thread", "simplified"))
        if thread not in THREAD_MODES:
            raise ParameterError(f"thread must be one of {', '.join(THREAD_MODES)}")
        return {"size": size, "length": length, "thread": thread}

    def designation(self, p: dict[str, Any]) -> str:
        return f"ISO {self.number} - {p['size']} x {_fmt(p['length'])}"

    def file_stem(self, p: dict[str, Any]) -> str:
        suffix = "_threaded" if p["thread"] == "modeled" else ""
        return f"ISO{self.number}_{p['size']}x{_fmt(p['length'])}{suffix}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        sd = SOCKET[p["size"]]
        short = self.is_short(sd.size, p["length"])
        t = MetricThread(sd.d, sd.P)
        return [
            Dimension("d", "Thread diameter", sd.d),
            Dimension("P", "Pitch", sd.P),
            Dimension("l", "Nominal length", p["length"]),
            Dimension("s", "Socket across flats", sd.s_nom),
            Dimension("e min", "Socket across corners", sd.e_min),
            Dimension("t min", "Socket depth", socket_depth(sd, short)),
            Dimension("df", "Socket-end chamfer dia. (~ minor dia.)", round(t.d3, 3)),
            Dimension("∠ df", "Socket-end chamfer angle", "120°" if short else "90°", ""),
            *self.point_dimensions(sd, short),
            Dimension("d2", "Pitch diameter", round(t.d2, 3)),
            Dimension("d3", "Minor diameter", round(t.d3, 3)),
        ]

    def notes(self, p: dict[str, Any]) -> list[str]:
        sd = SOCKET[p["size"]]
        l = p["length"]
        short = self.is_short(sd.size, l)
        out = []
        if l not in self.standard_lengths(sd.size):
            pref = ", ".join(_fmt(x) for x in self.standard_lengths(sd.size))
            out.append(
                f"{_fmt(l)} mm is not a preferred length for {sd.size} "
                f"(preferred: {pref})."
            )
        if short:
            out.append(
                "Short length (shaded in Table 1): 120° socket-end chamfer and "
                f"the shallower socket, t min = {_fmt(sd.t_min_short)} mm."
            )
        out += self.point_notes(sd, short)
        if p["thread"] == "simplified":
            out.append(
                "Thread not modeled: the body is a plain cylinder at d, ready for "
                "a cosmetic thread."
            )
        else:
            out.append(
                "Thread modeled with the ISO 68-1 basic profile (flat root at d1), "
                "right hand, over the whole length."
            )
        out.append(
            "Modeled at nominal sizes: d, socket s nom to depth t min with a 118° "
            "drill point, socket end chamfered to df = d3."
        )
        out.append(
            f"Dimensions from ISO {self.number}:2003 (M1.6 to M24). The 2026 "
            "edition adds M30 for steel."
        )
        return out

    def walls(self, size: str, l: float) -> tuple[float, float]:
        """(side wall, point wall) in mm around the socket.

        Measured in the axial half-section. The side wall is the smallest
        distance from the socket to the socket-end chamfer and the thread
        core; the point wall is the smallest distance from the socket to the
        point (point chamfer or cone, tip face and cup). The socket is taken
        as round at the hex corner radius s / sqrt(3) and the outside at the
        thread core d1 / 2, so both are lower bounds in either thread mode.
        """
        sd = SOCKET[size]
        short = self.is_short(size, l)
        thread = MetricThread(sd.d, sd.P)
        r_core = thread.d1 / 2
        top = self.top(short)
        r_top = thread.d3 / 2
        z_top = -(r_core - r_top) / math.tan(math.radians(top.half_angle))
        point = self.point_polyline(sd, l, short, r_core)
        side = [(r_top, 0.0), (r_core, z_top), point[0]]
        t = socket_depth(sd, short)
        h = drill_point_height(sd.s_nom)
        r_hex = sd.s_nom / math.sqrt(3)
        r_drill = 0.96 * sd.s_nom / 2
        socket = [(r_hex, 0.0), (r_hex, -t), (r_drill, -t), (0.0, -t - h)]
        return _polyline_distance(socket, side), _polyline_distance(socket, point)

    def cup_profile(self, sd: SocketData, l: float) -> list[tuple[float, float]]:
        return [(0.0, -l)]

    def build(self, p: dict[str, Any]) -> Part:
        sd = SOCKET[p["size"]]
        l = p["length"]
        mode = p["thread"]
        if mode not in THREAD_MODES:
            raise ParameterError(f"unknown thread mode {mode!r}")
        short = self.is_short(sd.size, l)
        what = f"ISO {self.number} {sd.size} x {_fmt(l)}"
        body = self.body(sd, l, mode, short, what)
        body = cut_hex_socket(body, sd.s_nom, socket_depth(sd, short), 0.0, what)
        part = self.finish(body, sd, l, what)
        part.label = self.designation(p)
        return part


def _polyline_distance(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> float:
    """Minimum distance between two polylines (sampled densely)."""
    def samples(pts, n=60):
        out = []
        for (r0, z0), (r1, z1) in zip(pts, pts[1:]):
            for i in range(n + 1):
                f = i / n
                out.append((r0 + f * (r1 - r0), z0 + f * (z1 - z0)))
        return out
    sa, sb = samples(a), samples(b)
    return min(math.dist(p, q) for p in sa for q in sb)


class ISO4026(SetScrew):
    id = "iso4026"
    number = "4026"
    point_name = "flat point"
    title = "ISO 4026"
    summary = "Hexagon socket set screws with flat point, M1.6 to M24"

    def point(self, sd: SocketData, short: bool) -> Point:
        return Point(DP[sd.size][0] / 2, 45.0)

    def point_dimensions(self, sd: SocketData, short: bool) -> list[Dimension]:
        dp_max, dp_min = DP[sd.size]
        return [
            Dimension("dp max", "Flat point diameter", dp_max),
            Dimension("dp min", "Flat point diameter", dp_min),
        ]


class ISO4027(SetScrew):
    id = "iso4027"
    number = "4027"
    point_name = "cone point"
    title = "ISO 4027"
    summary = "Hexagon socket set screws with cone point, M1.6 to M24"

    def gamma(self, short: bool) -> float:
        return 120.0 if short else 90.0

    def point(self, sd: SocketData, short: bool) -> Point:
        return Point(DT_MAX[sd.size] / 2, self.gamma(short) / 2)

    def point_dimensions(self, sd: SocketData, short: bool) -> list[Dimension]:
        return [
            Dimension("dt max", "Cone point tip diameter", DT_MAX[sd.size]),
            Dimension("γ", "Cone point angle", f"{self.gamma(short):g}°", ""),
        ]

    def point_notes(self, sd: SocketData, short: bool) -> list[str]:
        return [
            f"Cone point at γ = {self.gamma(short):g}° "
            f"({'120° for the shaded short lengths' if short else '90°; 120° only for the shaded short lengths'}), "
            f"truncated at dt max = {_fmt(DT_MAX[sd.size])} mm."
        ]


class ISO4029(SetScrew):
    id = "iso4029"
    number = "4029"
    point_name = "cup point"
    title = "ISO 4029"
    summary = "Hexagon socket set screws with cup point, M1.6 to M24"

    def point(self, sd: SocketData, short: bool) -> Point:
        return Point(DZ[sd.size][0] / 2, 45.0)

    def cup_depth(self, sd: SocketData) -> float:
        return DZ[sd.size][1] / 2 / math.tan(math.radians(CUP_ANGLE / 2))

    def cup_profile(self, sd: SocketData, l: float) -> list[tuple[float, float]]:
        r_mouth = DZ[sd.size][1] / 2
        return [(r_mouth, -l), (0.0, -l + self.cup_depth(sd))]

    def finish(self, body: Part, sd: SocketData, l: float, what: str) -> Part:
        return cut_cup(body, DZ[sd.size][1] / 2, l, what)

    def point_dimensions(self, sd: SocketData, short: bool) -> list[Dimension]:
        dz_max, dz_min = DZ[sd.size]
        return [
            Dimension("dz max", "Cup point diameter", dz_max),
            Dimension("dz min", "Cup point diameter", dz_min),
            Dimension("∠ dz", "Cup angle", f"≈ {CUP_ANGLE:g}°", ""),
            Dimension("tz", "Cup depth (model)", round(self.cup_depth(sd), 3)),
        ]

    def point_notes(self, sd: SocketData, short: bool) -> list[str]:
        return [
            "Cup modeled as the ≈120° cone of Figure 1 with its mouth at dz min; "
            "the point is chamfered at 45° to dz max, leaving a narrow flat land "
            "between the two limits."
        ]


class ISO4028(SetScrew):
    id = "iso4028"
    number = "4028"
    point_name = "dog point"
    title = "ISO 4028"
    summary = "Hexagon socket set screws with dog point, M1.6 to M24"

    def dog(self, sd: SocketData, short: bool) -> tuple[float, float]:
        """(dp max, z max) of the dog: the short dog for shaded lengths."""
        z = Z_SHORT[sd.size] if short else Z_LONG[sd.size]
        return DP[sd.size][0], z[0]

    def body(self, sd: SocketData, l: float, mode: str, short: bool, what: str) -> Part:
        dp, z = self.dog(sd, short)
        return dog_point_rod(MetricThread(sd.d, sd.P), l, dp / 2, z, mode,
                             self.top(short), what)

    def point_polyline(self, sd: SocketData, l: float, short: bool,
                       r_core: float) -> list[tuple[float, float]]:
        dp, z = self.dog(sd, short)
        r_dog = dp / 2
        z_sh = -l + z
        return [(r_core, z_sh + (r_core - r_dog)), (r_dog, z_sh), (r_dog, -l), (0.0, -l)]

    def point_dimensions(self, sd: SocketData, short: bool) -> list[Dimension]:
        dp_max, dp_min = DP[sd.size]
        (zs_max, zs_min), (zl_max, zl_min) = Z_SHORT[sd.size], Z_LONG[sd.size]
        z_max, z_min = (zs_max, zs_min) if short else (zl_max, zl_min)
        kind = "short dog" if short else "long dog"
        return [
            Dimension("dp max", "Dog point diameter", dp_max),
            Dimension("dp min", "Dog point diameter", dp_min),
            Dimension("z max", f"Dog length ({kind})", z_max),
            Dimension("z min", f"Dog length ({kind})", z_min),
        ]

    def point_notes(self, sd: SocketData, short: bool) -> list[str]:
        dp, z = self.dog(sd, short)
        which = (
            "short dog (shaded lengths of Table 1)" if short
            else "long dog (lengths below the shaded area of Table 1)"
        )
        return [(
            f"Dog point: {which}, modeled at dp max = {_fmt(dp)} mm and "
            f"z max = {_fmt(z)} mm, joined to the thread by a 45° cone. The "
            "small radii Figure 1 asks for on the dog edges are not dimensioned "
            "and are left sharp."
        )]

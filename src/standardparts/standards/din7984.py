"""DIN 7984 hexagon socket head cap screws with low head."""

from __future__ import annotations

import math
from typing import Any

from build123d import Part

from ..geometry import SQRT3, MetricThread, hex_socket
from ..screws import THREAD_MODES, threaded_screw
from .base import Dimension, Option, Parameter, ParameterError, Standard
from .din7984_data import SIZES, SizeData

# Drill point of the socket. Flatter than the shared 118 deg so the point
# stays inside the low head (see din7984_data).
SOCKET_DRILL_ANGLE = 140.0

# Thread-end shifts (in pitches, towards the tip) tried in turn when the
# shared helical fuse fails at one exact thread-end height (same pattern as
# iso7380._threaded_body).
_Z_END_SHIFTS = (0.0, -0.05, -0.1, -0.2)


def _fmt(x: float) -> str:
    return f"{x:g}"


def cut_socket(body: Part, s: float, depth: float, z_top: float, what: str) -> Part:
    """screws.cut_hex_socket with the DIN 7984 drill point angle: cut a
    hexagon socket from z_top down and check that it removed material."""
    cut = body - hex_socket(s, depth, z_top, drill_angle=SOCKET_DRILL_ANGLE)
    hex_area = SQRT3 / 2 * s**2
    if len(cut.solids()) != 1 or body.volume - cut.volume < 0.95 * hex_area * depth:
        raise RuntimeError(f"socket cut failed for {what}")
    if not cut.is_valid:
        raise RuntimeError(f"socket cut gave an invalid solid for {what}")
    return cut


def socket_point_height(sd: SizeData) -> float:
    """Height of the socket's drill point tip above the bearing face."""
    r_drill = 0.96 * sd.s_nom / 2
    return sd.k_max - sd.t_min - r_drill / math.tan(math.radians(SOCKET_DRILL_ANGLE / 2))


def build_body(sd: SizeData, l: float, thread_mode: str) -> Part:
    """Revolved screw body with thread, before the socket is cut.

    Coordinate system: Z is the screw axis, the head bearing face lies in
    the XY plane at z = 0, the head extends to z = +k and the shank to
    z = -l. Nominal sizes: dk max, k max, ds = d, underhead fillet r min,
    bearing-face chamfer to dw min, top-edge chamfer v max, ISO 4753 point.
    """
    if thread_mode not in THREAD_MODES:
        raise ParameterError(f"unknown thread mode {thread_mode!r}")
    thread = MetricThread(sd.d, sd.P)
    R = sd.d / 2
    r = sd.r_min
    k = sd.k_max
    dk = sd.dk_max
    v = sd.v_max
    dw = sd.dw_min
    dr = R - thread.d1 / 2

    _, lg_max = sd.thread_geometry(l)
    z_end = -(r + dr) if lg_max is None else -lg_max
    head = [
        ("arc", (R + r - r / math.sqrt(2), -r + r / math.sqrt(2)), (R + r, 0.0)),
        (dw / 2, 0.0),
        (dk / 2, (dk - dw) / 2),   # 45 deg bearing-face chamfer down to dw
        (dk / 2, k - v),
        (dk / 2 - v, k),           # top-edge chamfer v
        (0.0, k),
    ]
    what = f"DIN 7984 {sd.size} x {l:g}"
    last: Exception | None = None
    for shift in _Z_END_SHIFTS if thread_mode == "modeled" else (0.0,):
        try:
            return threaded_screw(
                thread, l, z_end + shift * sd.P, -r, head, thread_mode, what=what
            )
        except (AttributeError, RuntimeError) as exc:
            last = exc
    raise RuntimeError(f"thread fuse failed for {what}") from last


def build_screw(sd: SizeData, l: float, thread_mode: str) -> Part:
    """build_body plus the socket, s nom to depth t min below z = k."""
    body = build_body(sd, l, thread_mode)
    return cut_socket(body, sd.s_nom, sd.t_min, sd.k_max, f"DIN 7984 {sd.size} x {l:g}")


class DIN7984(Standard):
    id = "din7984"
    title = "DIN 7984"
    summary = "Hexagon socket head cap screws with low head, M3 to M24"
    category = "Screws"
    source = "Values in mm, from DIN 7984:2009-06 Table 1."

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="size",
                label="Thread size",
                kind="select",
                default="M6",
                options=[Option(s, f"{s} x {_fmt(sd.P)}") for s, sd in SIZES.items()],
            ),
            Parameter(
                name="length",
                label="Nominal length l",
                kind="length",
                default=20,
                depends_on="size",
                preferred={s: sd.standard_lengths() for s, sd in SIZES.items()},
                limits={s: [sd.l_min, sd.l_max] for s, sd in SIZES.items()},
                unit="mm",
                help="Measured from under the head to the tip.",
            ),
            Parameter(
                name="thread",
                label="Thread",
                kind="select",
                default="simplified",
                options=[Option(k, v) for k, v in THREAD_MODES.items()],
                help="Simplified is lighter and is what most CAD libraries ship; "
                "the threaded length is a separate face for cosmetic threads.",
            ),
        ]

    def validate(self, raw: dict[str, Any]) -> dict[str, Any]:
        size = str(raw.get("size", "M6"))
        if size not in SIZES:
            raise ParameterError(f"unknown size {size!r}; choose one of {', '.join(SIZES)}")
        sd = SIZES[size]
        try:
            length = float(raw.get("length", 20))
        except (TypeError, ValueError):
            raise ParameterError("length must be a number") from None
        if not math.isfinite(length):
            raise ParameterError("length must be a number")
        length = round(length, 2)
        if not sd.l_min <= length <= sd.l_max:
            raise ParameterError(
                f"length for {size} must be between {_fmt(sd.l_min)} and "
                f"{_fmt(sd.l_max)} mm"
            )
        thread = str(raw.get("thread", "simplified"))
        if thread not in THREAD_MODES:
            raise ParameterError(f"thread must be one of {', '.join(THREAD_MODES)}")
        return {"size": size, "length": length, "thread": thread}

    def designation(self, p: dict[str, Any]) -> str:
        return f"DIN 7984 - {p['size']} x {_fmt(p['length'])}"

    def file_stem(self, p: dict[str, Any]) -> str:
        suffix = "_threaded" if p["thread"] == "modeled" else ""
        return f"DIN7984_{p['size']}x{_fmt(p['length'])}{suffix}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        sd = SIZES[p["size"]]
        l = p["length"]
        ls_min, lg_max = sd.thread_geometry(l)
        t = MetricThread(sd.d, sd.P)
        full = lg_max is None
        return [
            Dimension("d", "Thread diameter", sd.d),
            Dimension("P", "Pitch", sd.P),
            Dimension("l", "Nominal length", l),
            Dimension("b", "Thread length", "to head" if full else sd.thread_length(l)),
            Dimension("lg max", "Grip length", round(3 * sd.P, 3) if full else lg_max),
            Dimension("ls min", "Plain shank length", None if full else ls_min),
            Dimension("dk max", "Head diameter", sd.dk_max),
            Dimension("k max", "Head height", sd.k_max),
            Dimension("s", "Socket across flats", sd.s_nom),
            Dimension("e min", "Socket across corners", sd.e_min),
            Dimension("t min", "Socket depth", sd.t_min),
            Dimension("da max", "Fillet transition dia.", sd.da_max),
            Dimension("r min", "Underhead fillet", sd.r_min),
            Dimension("dw min", "Bearing face dia.", sd.dw_min),
            Dimension("v max", "Top edge chamfer", sd.v_max),
            Dimension("d2", "Pitch diameter", round(t.d2, 3)),
            Dimension("d3", "Minor diameter", round(t.d3, 3)),
        ]

    def notes(self, p: dict[str, Any]) -> list[str]:
        sd = SIZES[p["size"]]
        l = p["length"]
        out = []
        if l not in sd.standard_lengths():
            pref = ", ".join(_fmt(x) for x in sd.standard_lengths())
            out.append(
                f"{_fmt(l)} mm is not a preferred length for {sd.size} "
                f"(preferred: {pref})."
            )
        if sd.is_fully_threaded(l):
            out.append(
                "Threaded up to the head at this length (DIN 7984: lg max ~ 3P; "
                "the model runs the thread out under the fillet, as for ISO 4762)."
            )
        else:
            out.append(
                f"Partially threaded: b = {_fmt(sd.thread_length(l))} mm of thread, "
                "plain shank above."
            )
        if p["thread"] == "simplified":
            out.append(
                "Thread not modeled: shank is a plain cylinder at d. The threaded "
                "length is its own face, ready for a cosmetic thread."
            )
        else:
            out.append(
                "Thread modeled with the ISO 68-1 basic profile (flat root at d1), "
                "right hand, with a 2P runout."
            )
        out.append(
            "Modeled at nominal sizes: dk max, k max, ds = d, socket s nom to depth "
            f"t min with a {SOCKET_DRILL_ANGLE:g} deg point (low head)."
        )
        if size_bracketed(sd.size) or l in (14, 18, 55):
            out.append("DIN 7984: sizes and lengths in brackets should be avoided if possible.")
        return out

    def build(self, p: dict[str, Any]) -> Part:
        part = build_screw(SIZES[p["size"]], p["length"], p["thread"])
        part.label = self.designation(p)
        return part


def size_bracketed(size: str) -> bool:
    """M14, M18 and M22 are bracketed (non-preferred) in DIN 7984."""
    return size in ("M14", "M18", "M22")

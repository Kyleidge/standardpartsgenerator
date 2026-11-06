"""ISO 10642 hexagon socket countersunk head screws."""

from __future__ import annotations

import math
from typing import Any

from build123d import Part

from ..geometry import MetricThread
from ..screws import THREAD_MODES, cut_hex_socket, threaded_screw
from .base import Dimension, Option, Parameter, ParameterError, Standard
from .iso10642_data import HEAD_ANGLE, SIZES, SizeData

# Underhead fillet between the shank (vertical) and the 45 deg cone: the
# profile turns by 45 deg, so the tangent points sit r * tan(22.5 deg) from
# the sharp corner.
_TAN_HALF = math.tan(math.radians(22.5))


def _fmt(x: float) -> str:
    return f"{x:g}"


# Thread-end shifts (in pitches, always towards the tip) tried in turn when
# the shared helical fuse fails. screws._fuse_ridge only retries other start
# angles, and it raises AttributeError instead of retrying when OCCT returns
# no solid for the ridge/envelope intersection; this happens for a few exact
# thread-end heights (e.g. ISO 7380-1 M8 x 25). A shift of 0.05 P moves the
# end of the full thread by a few hundredths of a millimetre.
_Z_END_SHIFTS = (0.0, -0.05, -0.1, -0.2)


def _threaded_body(thread, length, z_end, z_shank_top, head, mode, what):
    last: Exception | None = None
    for shift in _Z_END_SHIFTS if mode == "modeled" else (0.0,):
        try:
            return threaded_screw(
                thread, length, z_end + shift * thread.P, z_shank_top, head, mode, what=what
            )
        except (AttributeError, RuntimeError) as exc:
            last = exc
    raise RuntimeError(f"thread fuse failed for {what}") from last


def head_profile(sd: SizeData) -> tuple[float, list]:
    """Return (z_shank_top, head profile items) for threaded_screw.

    The 90 deg cone sits at its theoretical position: it meets d at z = -k
    and would reach dk theoretical at the top face z = 0. The actual head is
    cut at dk min, which leaves a short cylindrical edge at the top.
    """
    R = sd.d / 2
    r = sd.r_min
    k = sd.k_max
    dk = sd.dk_min
    z_c = -k - r * _TAN_HALF            # fillet centre height (= z_shank_top)
    c_r = R + r                         # fillet centre radius
    s2 = math.sqrt(0.5)
    a_mid = math.radians(157.5)         # half way between 180 and 135 deg
    mid = (c_r + r * math.cos(a_mid), z_c + r * math.sin(a_mid))
    on_cone = (c_r - r * s2, z_c + r * s2)
    head = [
        ("arc", mid, on_cone),
        (dk / 2, -sd.land_height),      # cone up to the actual head diameter
        (dk / 2, 0.0),                  # cylindrical head edge
        (0.0, 0.0),                     # top face, flush with the countersink
    ]
    return z_c, head


def build_body(sd: SizeData, l: float, thread_mode: str) -> Part:
    """Revolved screw body with thread, before the socket is cut.

    Coordinate system: Z is the screw axis. The top face of the head lies in
    the XY plane at z = 0 (flush with the countersunk surface), the tip is at
    z = -l, so the nominal length includes the head as in the standard. The
    cone meets the shank at z = -k. threaded_screw is called with length = l
    and a head profile that ends at z = 0, so no translation is needed.
    """
    if thread_mode not in THREAD_MODES:
        raise ParameterError(f"unknown thread mode {thread_mode!r}")
    thread = MetricThread(sd.d, sd.P)
    dr = sd.d / 2 - thread.d1 / 2
    z_shank_top, head = head_profile(sd)
    _, lg_max = sd.thread_geometry(l)
    # lg is measured from the top of the head, like l.
    z_end = z_shank_top - dr if lg_max is None else -lg_max
    what = f"ISO 10642 {sd.size} x {l:g}"
    return _threaded_body(thread, l, z_end, z_shank_top, head, thread_mode, what)


def build_screw(sd: SizeData, l: float, thread_mode: str) -> Part:
    """Build the screw solid: build_body plus the socket, s nom to depth t
    min below the top face z = 0."""
    body = build_body(sd, l, thread_mode)
    return cut_hex_socket(body, sd.s_nom, sd.t_min, 0.0, f"ISO 10642 {sd.size} x {l:g}")


class ISO10642(Standard):
    id = "iso10642"
    title = "ISO 10642"
    summary = "Hexagon socket countersunk head screws, M3 to M20"
    category = "Screws"
    source = "Values in mm, from ISO 10642:2004 Table 1."

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="size",
                label="Thread size",
                kind="select",
                default="M6",
                options=[
                    Option(s, f"{s} x {_fmt(sd.P)}" if sd.preferred else f"({s}) x {_fmt(sd.P)}")
                    for s, sd in SIZES.items()
                ],
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
                help="Overall length, from the top of the head to the tip.",
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
        return f"ISO 10642 - {p['size']} x {_fmt(p['length'])}"

    def file_stem(self, p: dict[str, Any]) -> str:
        suffix = "_threaded" if p["thread"] == "modeled" else ""
        return f"ISO10642_{p['size']}x{_fmt(p['length'])}{suffix}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        sd = SIZES[p["size"]]
        l = p["length"]
        ls_min, lg_max = sd.thread_geometry(l)
        t = MetricThread(sd.d, sd.P)
        full = lg_max is None
        return [
            Dimension("d", "Thread diameter", sd.d),
            Dimension("P", "Pitch", sd.P),
            Dimension("l", "Nominal length (incl. head)", l),
            Dimension("b", "Thread length", "to head" if full else sd.b),
            Dimension("lg max", "Grip length", None if full else lg_max),
            Dimension("ls min", "Plain shank length", None if full else ls_min),
            Dimension("dk theo. max", "Head diameter, theoretical", sd.dk_theo_max),
            Dimension("dk min", "Head diameter, actual", sd.dk_min),
            Dimension("k max", "Head height", sd.k_max),
            Dimension("α", "Head angle", f"{HEAD_ANGLE:g}°", unit=""),
            Dimension("F max", "Flushness tolerance", sd.F_max),
            Dimension("s", "Socket across flats", sd.s_nom),
            Dimension("e min", "Socket across corners", sd.e_min),
            Dimension("t min", "Socket depth", sd.t_min),
            Dimension("w min", "Wall thickness", sd.w_min),
            Dimension("da max", "Fillet transition dia.", sd.da_max),
            Dimension("r min", "Underhead fillet", sd.r_min),
            Dimension("d2", "Pitch diameter", round(t.d2, 3)),
            Dimension("d3", "Minor diameter", round(t.d3, 3)),
        ]

    def notes(self, p: dict[str, Any]) -> list[str]:
        sd = SIZES[p["size"]]
        l = p["length"]
        out = []
        if not sd.preferred:
            out.append(f"{sd.size} is in parentheses in the standard: avoid it if possible.")
        if l not in sd.standard_lengths():
            pref = ", ".join(_fmt(x) for x in sd.standard_lengths())
            out.append(
                f"{_fmt(l)} mm is not a preferred length for {sd.size} "
                f"(preferred: {pref})."
            )
        if sd.is_fully_threaded(l):
            out.append("Threaded up to the head at this length.")
        else:
            out.append(
                f"Partially threaded: b = {_fmt(sd.b)} mm of thread, plain shank above."
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
            "The length l includes the head. The top face is at z = 0, flush with "
            "the countersink; the tip is at z = -l."
        )
        out.append(
            f"Head: 90° cone at its theoretical (flush) position, cut at the actual "
            f"head diameter dk min = {_fmt(sd.dk_min)} mm, which leaves a "
            f"{sd.land_height:.2f} mm cylindrical edge. Socket s nom to depth t min, "
            "underhead fillet r min, ds = d."
        )
        return out

    def build(self, p: dict[str, Any]) -> Part:
        part = build_screw(SIZES[p["size"]], p["length"], p["thread"])
        part.label = self.designation(p)
        return part

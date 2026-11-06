"""ISO 7380-1 hexagon socket button head screws."""

from __future__ import annotations

import math
from typing import Any

from build123d import Part

from ..geometry import MetricThread
from ..screws import THREAD_MODES, cut_hex_socket, threaded_screw
from .base import Dimension, Option, Parameter, ParameterError, Standard
from .iso7380_data import SIZES, SizeData


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


def dome_arc(sd: SizeData) -> tuple[tuple[float, float], tuple[float, float]]:
    """Centre and mid point of the dome arc, radius rf max, from the bearing
    edge (dk/2, 0) up to the top flat (dL/2, k).

    The standard lets the centre sit off the axis (ISO 7380-1:2022 Figure 1),
    so the arc is simply the circle of radius rf through both points, on the
    side that bulges outwards.
    """
    a = (sd.dk_max / 2, 0.0)
    b = (sd.dL_ref / 2, sd.k_max)
    rf = sd.rf_max
    mx, mz = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    ux, uz = b[0] - a[0], b[1] - a[1]
    chord = math.hypot(ux, uz)
    h = math.sqrt(rf**2 - (chord / 2) ** 2)
    nx, nz = uz / chord, -ux / chord        # chord normal pointing outwards
    centre = (mx - nx * h, mz - nz * h)
    mid = (centre[0] + nx * rf, centre[1] + nz * rf)
    return centre, mid


def build_body(sd: SizeData, l: float, thread_mode: str) -> Part:
    """Revolved screw body with thread, before the socket is cut.

    Coordinate system: Z is the screw axis, the bearing face lies in the XY
    plane at z = 0, the dome rises to z = +k and the shank runs to z = -l.
    Nominal sizes: dk max, k max, dome radius rf max from the bearing edge
    to the top flat dL, ds = d, socket s nom to depth t min.
    """
    if thread_mode not in THREAD_MODES:
        raise ParameterError(f"unknown thread mode {thread_mode!r}")
    thread = MetricThread(sd.d, sd.P)
    R = sd.d / 2
    _, lg_max = sd.thread_geometry(l)
    full = lg_max is None
    r = sd.underhead_radius(full)
    dr = R - thread.d1 / 2
    z_end = -(r + dr) if full else -lg_max
    _, mid = dome_arc(sd)
    s2 = math.sqrt(0.5)
    head = [
        ("arc", (R + r - r * s2, -r + r * s2), (R + r, 0.0)),   # underhead fillet
        (sd.dk_max / 2, 0.0),                                   # bearing face
        ("arc", mid, (sd.dL_ref / 2, sd.k_max)),                # dome
        (0.0, sd.k_max),                                        # top flat
    ]
    what = f"ISO 7380-1 {sd.size} x {l:g}"
    return _threaded_body(thread, l, z_end, -r, head, thread_mode, what)


def build_screw(sd: SizeData, l: float, thread_mode: str) -> Part:
    """Build the screw solid: build_body plus the socket, s nom to depth t
    min below the top flat z = k."""
    body = build_body(sd, l, thread_mode)
    return cut_hex_socket(
        body, sd.s_nom, sd.t_min, sd.k_max, f"ISO 7380-1 {sd.size} x {l:g}"
    )


class ISO7380(Standard):
    id = "iso7380"
    title = "ISO 7380-1"
    summary = "Hexagon socket button head screws, M3 to M16"
    category = "Screws"
    source = (
        "Values in mm, from ISO 7380-1:2022 Table 1; lengths and thread lengths "
        "from ISO 7380-1:2011 data (see notes)."
    )

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
        return f"ISO 7380-1 - {p['size']} x {_fmt(p['length'])}"

    def file_stem(self, p: dict[str, Any]) -> str:
        suffix = "_threaded" if p["thread"] == "modeled" else ""
        return f"ISO7380-1_{p['size']}x{_fmt(p['length'])}{suffix}"

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
            Dimension("b", "Thread length", "to head" if full else sd.b),
            Dimension("lg max", "Grip length", None if full else lg_max),
            Dimension("ls min", "Plain shank length", None if full else ls_min),
            Dimension("dk max", "Head diameter", sd.dk_max),
            Dimension("k max", "Head height", sd.k_max),
            Dimension("rf max", "Dome radius", sd.rf_max),
            Dimension("dL ref", "Top flat diameter", sd.dL_ref),
            Dimension("dw min", "Bearing face dia.", sd.dw_min),
            Dimension("s", "Socket across flats", sd.s_nom),
            Dimension("e min", "Socket across corners", sd.e_min),
            Dimension("t min", "Socket depth", sd.t_min),
            Dimension("wb min", "Wall thickness", sd.wb_min),
            Dimension("da max", "Fillet transition dia.", sd.da_max),
            Dimension("rs min" if not full else "rt min", "Underhead radius",
                      sd.rs_min if not full else sd.rt_min),
            Dimension("d2", "Pitch diameter", round(t.d2, 3)),
            Dimension("d3", "Minor diameter", round(t.d3, 3)),
        ]

    def notes(self, p: dict[str, Any]) -> list[str]:
        sd = SIZES[p["size"]]
        l = p["length"]
        full = sd.is_fully_threaded(l)
        out = []
        if l not in sd.standard_lengths():
            pref = ", ".join(_fmt(x) for x in sd.standard_lengths())
            out.append(
                f"{_fmt(l)} mm is not a preferred length for {sd.size} "
                f"(preferred: {pref})."
            )
        if full:
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
        r = sd.underhead_radius(full)
        fillet = f"underhead fillet {_fmt(r)} mm"
        if full and r < sd.rt_min:
            fillet += f" (rt min {_fmt(sd.rt_min)} limited to stay inside da max)"
        out.append(
            "Modeled at nominal sizes: dk max, k max, dome radius rf max from the "
            f"bearing edge to the top flat dL, ds = d, socket s nom to depth t min, {fillet}."
        )
        out.append(
            "Standard lengths and thread lengths follow the ISO 7380-1:2011 data; "
            "the 2022 edition amended the length range, not verified here."
        )
        return out

    def build(self, p: dict[str, Any]) -> Part:
        part = build_screw(SIZES[p["size"]], p["length"], p["thread"])
        part.label = self.designation(p)
        return part

"""ISO 4762 hexagon socket head cap screws."""

from __future__ import annotations

import math
from typing import Any

from build123d import Part

from ..geometry import MetricThread
from ..screws import THREAD_MODES, cut_hex_socket, threaded_screw
from .base import Dimension, Option, Parameter, ParameterError, Standard
from .iso4762_data import SIZES, SizeData


def _fmt(x: float) -> str:
    return f"{x:g}"


def build_screw(sd: SizeData, l: float, thread_mode: str) -> Part:
    """Build the screw solid.

    Coordinate system: Z is the screw axis, the head bearing face lies in
    the XY plane at z = 0, the head extends to z = +k and the shank to z = -l.
    Nominal sizes are used throughout (dk max, k max, ds = d, socket s nom
    with depth t min).
    """
    if thread_mode not in THREAD_MODES:
        raise ParameterError(f"unknown thread mode {thread_mode!r}")
    thread = MetricThread(sd.d, sd.P)
    R = sd.d / 2                 # major / shank radius
    r = sd.r_min                 # underhead fillet radius
    k = sd.k_max
    dk = sd.dk_max
    v = sd.v_max
    dw = sd.dw_min
    dr = R - thread.d1 / 2

    _, lg_max = sd.thread_geometry(l)
    # Threaded to the head: run the thread out right under the fillet.
    z_end = -(r + dr) if lg_max is None else -lg_max

    head = [
        ("arc", (R + r - r / math.sqrt(2), -r + r / math.sqrt(2)), (R + r, 0.0)),
        (dw / 2, 0.0),
        (dk / 2, (dk - dw) / 2),   # 45 deg bearing-face chamfer down to dw
        (dk / 2, k - v),
        (dk / 2 - v, k),           # top-edge chamfer v
        (0.0, k),
    ]
    what = f"ISO 4762 {sd.size} x {l:g}"
    body = threaded_screw(thread, l, z_end, -r, head, thread_mode, what=what)
    return cut_hex_socket(body, sd.s_nom, sd.t_min, k, what)


class ISO4762(Standard):
    id = "iso4762"
    title = "ISO 4762"
    summary = "Hexagon socket head cap screws, coarse thread M1.6 to M64"
    category = "Screws"
    source = "Values in mm, from ISO 4762:2004 Table 1."

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
        return f"ISO 4762 - {p['size']} x {_fmt(p['length'])}"

    def file_stem(self, p: dict[str, Any]) -> str:
        suffix = "_threaded" if p["thread"] == "modeled" else ""
        return f"ISO4762_{p['size']}x{_fmt(p['length'])}{suffix}"

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
            Dimension("s", "Socket across flats", sd.s_nom),
            Dimension("e min", "Socket across corners", sd.e_min),
            Dimension("t min", "Socket depth", sd.t_min),
            Dimension("w min", "Wall thickness", sd.w_min),
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
            "Modeled at nominal sizes: dk max, k max, ds = d, socket s nom to depth t min."
        )
        return out

    def build(self, p: dict[str, Any]) -> Part:
        part = build_screw(SIZES[p["size"]], p["length"], p["thread"])
        part.label = self.designation(p)
        return part

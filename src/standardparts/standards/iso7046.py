"""ISO 7046-1 countersunk flat head screws with type H or type Z cross
recess, product grade A."""

from __future__ import annotations

import math
from typing import Any

from build123d import Part

from ..drives import CROSS_TYPES, cross_recess
from ..geometry import MetricThread, helical_thread, revolve_profile
from ..screws import THREAD_MODES, _fuse_ridge, _rise
from .base import Dimension, Option, Parameter, ParameterError, Standard
from .iso7045 import (
    CROSS_NOTE,
    cross_dimensions,
    cut_recess,
    length_notes,
    thread_mode_note,
    threaded_body,
    validate_common,
)
from .iso7046_data import HEAD_ANGLE, NON_PREFERRED_LENGTHS, SIZES, SizeData

# Underhead fillet between the shank and the 45 deg cone: the profile turns
# by 45 deg, so the tangent points sit r * tan(22.5 deg) from the corner.
_TAN_HALF = math.tan(math.radians(22.5))


def _fmt(x: float) -> str:
    return f"{x:g}"


def countersunk_head(sd) -> tuple[float, list]:
    """(z_shank_top, head profile items) of a 90 deg countersunk head whose
    top face is at z = 0.

    The cone sits at its theoretical (flush) position: it meets d at z = -k
    and would reach dk theoretical at z = 0. The head is cut at the actual
    dk max, which leaves a short cylindrical edge of land_height. Works for
    any size row with d, k_max, dk_max, land_height and r_model.
    """
    R = sd.d / 2
    r = sd.r_model
    z_c = -sd.k_max - r * _TAN_HALF       # fillet centre height (= z_shank_top)
    c_r = R + r
    s2 = math.sqrt(0.5)
    a_mid = math.radians(157.5)
    mid = (c_r + r * math.cos(a_mid), z_c + r * math.sin(a_mid))
    on_cone = (c_r - r * s2, z_c + r * s2)
    return z_c, [
        ("arc", mid, on_cone),
        (sd.dk_max / 2, -sd.land_height),
        (sd.dk_max / 2, 0.0),
        (0.0, 0.0),
    ]


def countersunk_body(sd, l: float, thread_mode: str, what: str) -> Part:
    """Threaded countersunk screw body without the recess. Top face at
    z = 0, tip at z = -l (l includes the head). Threaded to the head
    (b = l - (k + a)) up to l_full_max, otherwise b min of thread."""
    if thread_mode not in THREAD_MODES:
        raise ParameterError(f"unknown thread mode {thread_mode!r}")
    thread = MetricThread(sd.d, sd.P)
    dr = sd.d / 2 - thread.d1 / 2
    z_shank_top, head = countersunk_head(sd)
    z_end = z_shank_top - dr if sd.is_fully_threaded(l) else -(l - sd.b_min)
    k_run = runout_pitches(thread, l, z_end)
    if thread_mode == "modeled" and k_run < 2.0:
        return short_modeled_screw(thread, l, z_end, z_shank_top, head, k_run, what)
    return threaded_body(thread, l, z_end, z_shank_top, head, thread_mode, what)


def runout_pitches(thread: MetricThread, l: float, z_end: float) -> float:
    """Thread runout length, in pitches, that fits between the tip chamfer
    and the end of the full thread (at most the usual 2P).

    screws.threaded_screw trims the helix with an envelope whose 45 deg tip
    cone and 2P runout cone overlap when less than about 3P of thread is
    left (ISO 7046-1 / ISO 14581 M2.5 x 3 and M4 x 5); the envelope then
    self-intersects and every fuse fails. Derived from the envelope offsets
    used there, with 0.1P of clearance.
    """
    P = thread.P
    dr = thread.d / 2 - thread.d1 / 2
    tip_top = -l + 0.03 * P + (thread.d / 2 + 0.05 * P - thread.d3 / 2)
    room = (z_end - 0.1 * P) - (tip_top + 0.1 * P)
    per_pitch = (dr + 0.05 * P) * P / dr        # envelope rise per pitch of runout
    return min(2.0, room / per_pitch)


def short_modeled_screw(thread, l, z_end, z_shank_top, head, k_run, what):
    """Modeled thread for screws too short for the 2P runout: the same
    construction as screws.threaded_screw (modeled mode, ISO 4753 point)
    with a runout of k_run pitches. Ridge fuse checked by screws._fuse_ridge."""
    if k_run < 0.5:
        raise RuntimeError(f"thread too short to model for {what}")
    P = thread.P
    R, r_core = thread.d / 2, thread.d1 / 2
    dr = R - r_core
    r_tip = thread.d3 / 2
    core = revolve_profile([
        (0.0, -l), (r_tip, -l), (r_core, -l + _rise(r_core - r_tip, 45.0)),
        (r_core, z_end), (R, z_end + dr), (R, z_shank_top), *head,
    ])
    slope = k_run * P / dr
    r_out, r_in = R + 0.05 * P, r_core - 0.1 * P
    z_tip, z_run = -l + 0.03 * P, z_end - 0.1 * P
    envelope = revolve_profile([
        (0.0, z_tip),
        (r_tip, z_tip),
        (r_out, z_tip + _rise(r_out - r_tip, 45.0)),
        (r_out, z_run - (r_out - r_core) * slope),
        (r_in, z_run + (r_core - r_in) * slope),
        (0.0, z_run + (r_core - r_in) * slope),
    ])
    ridge = helical_thread(thread, -l - P, z_end + P)
    return _fuse_ridge(core, ridge, envelope, what)


def countersunk_reference(sd, l: float) -> Part:
    """Plain revolved countersunk screw (shank at d, no thread, no recess)."""
    z_shank_top, head = countersunk_head(sd)
    thread = MetricThread(sd.d, sd.P)
    R, r_tip = sd.d / 2, thread.d3 / 2
    return revolve_profile([
        (0.0, -l), (r_tip, -l), (R, -l + (R - r_tip)), (R, z_shank_top), *head,
    ])


def build_body(sd: SizeData, l: float, thread_mode: str) -> Part:
    return countersunk_body(sd, l, thread_mode, f"ISO 7046-1 {sd.size} x {l:g}")


def recess_tool(sd: SizeData, drive: str) -> Part:
    m, p_min, p_max = sd.recess(drive)
    return cross_recess(drive, sd.recess_no, m, (p_min + p_max) / 2, 0.0)


def build_screw(sd: SizeData, l: float, thread_mode: str, drive: str) -> Part:
    if drive not in CROSS_TYPES:
        raise ParameterError(f"unknown drive {drive!r}")
    body = build_body(sd, l, thread_mode)
    ref = body if thread_mode == "simplified" else countersunk_reference(sd, l)
    what = f"ISO 7046-1 {sd.size} x {l:g} {drive}"
    return cut_recess(body, recess_tool(sd, drive), ref, what)


def short_thread_note(sd, l: float, thread_mode: str) -> list[str]:
    if thread_mode != "modeled":
        return []
    thread = MetricThread(sd.d, sd.P)
    z_shank_top, _ = countersunk_head(sd)
    z_end = z_shank_top - (sd.d / 2 - thread.d1 / 2) if sd.is_fully_threaded(l) else -(l - sd.b_min)
    k = runout_pitches(thread, l, z_end)
    if k >= 2.0:
        return []
    return [f"Short screw: the modeled thread runout is shortened to {k:.1f}P (2P otherwise)."]


def countersunk_dimensions(sd) -> list[Dimension]:
    return [
        Dimension("dk theo. max", "Head diameter, theoretical", sd.dk_theo),
        Dimension("dk max", "Head diameter, actual", sd.dk_max),
        Dimension("dk min", "Head diameter, actual", sd.dk_min),
        Dimension("k max", "Head height", sd.k_max),
        Dimension("α", "Head angle", HEAD_ANGLE, unit="°"),
        Dimension("r max", "Underhead radius", sd.r_max),
        Dimension("x max", "Thread runout", sd.x_max),
    ]


def countersunk_notes(sd) -> str:
    return (
        "The length l includes the head. The top face is at z = 0, flush with the "
        "countersink; the tip is at z = -l. Head: 90° cone at its theoretical "
        f"position, cut at the actual head diameter dk max = {_fmt(sd.dk_max)} mm, "
        f"which leaves a {sd.land_height:.2f} mm cylindrical edge. Underhead radius "
        f"r max / 2 = {_fmt(sd.r_model)} mm, ds = d."
    )


class ISO7046(Standard):
    id = "iso7046"
    title = "ISO 7046-1"
    summary = "Countersunk flat head screws with type H or type Z cross recess, M1.6 to M10"
    category = "Screws"
    source = "Values in mm, from ISO 7046-1:2011 Table 1; cross recess ISO 4757:1983."

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="size",
                label="Thread size",
                kind="select",
                default="M4",
                options=[
                    Option(s, f"{s} x {_fmt(sd.P)}" if sd.preferred else f"({s}) x {_fmt(sd.P)}")
                    for s, sd in SIZES.items()
                ],
            ),
            Parameter(
                name="length",
                label="Nominal length l",
                kind="length",
                default=10,
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
            Parameter(
                name="drive",
                label="Cross recess",
                kind="select",
                default="H",
                options=[Option(k, v) for k, v in CROSS_TYPES.items()],
            ),
        ]

    def validate(self, raw: dict[str, Any]) -> dict[str, Any]:
        return validate_common(raw, SIZES, "M4", 10, CROSS_TYPES)

    def designation(self, p: dict[str, Any]) -> str:
        return f"ISO 7046-1 - {p['size']} x {_fmt(p['length'])} - {p['drive']}"

    def file_stem(self, p: dict[str, Any]) -> str:
        suffix = "_threaded" if p["thread"] == "modeled" else ""
        return f"ISO7046-1_{p['size']}x{_fmt(p['length'])}_{p['drive']}{suffix}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        sd = SIZES[p["size"]]
        l = p["length"]
        t = MetricThread(sd.d, sd.P)
        full = sd.is_fully_threaded(l)
        return [
            Dimension("d", "Thread diameter", sd.d),
            Dimension("P", "Pitch", sd.P),
            Dimension("l", "Nominal length (incl. head)", l),
            Dimension("b", "Thread length", "to head" if full else f"{_fmt(sd.b_min)} min"),
            Dimension("a max", "Thread to head", sd.a_max),
            *countersunk_dimensions(sd),
            *cross_dimensions(sd, p["drive"]),
            Dimension("d2", "Pitch diameter", round(t.d2, 3)),
            Dimension("d3", "Minor diameter", round(t.d3, 3)),
        ]

    def notes(self, p: dict[str, Any]) -> list[str]:
        sd = SIZES[p["size"]]
        l = p["length"]
        out = length_notes(sd, l, NON_PREFERRED_LENGTHS)
        if sd.is_fully_threaded(l):
            out.append("Threaded up to the head at this length (b = l - (k + a)).")
        else:
            out.append(
                f"Partially threaded: b = {_fmt(sd.b_min)} mm of thread, plain shank above."
            )
        out.append(thread_mode_note(p["thread"]))
        out += short_thread_note(sd, l, p["thread"])
        out.append(countersunk_notes(sd))
        out.append(CROSS_NOTE + " Penetration depths of the deep series (series 1).")
        return out

    def build(self, p: dict[str, Any]) -> Part:
        part = build_screw(SIZES[p["size"]], p["length"], p["thread"], p["drive"])
        part.label = self.designation(p)
        return part

"""ISO 7045 pan head screws with type H or type Z cross recess."""

from __future__ import annotations

import math
from typing import Any

from build123d import Part, Rot

from ..drives import CROSS_TYPES, H_RECESSES, Z_RECESSES, checked_cut, cross_geometry, cross_recess
from ..geometry import MetricThread, revolve_profile
from ..screws import THREAD_MODES, threaded_screw
from .base import Dimension, Option, Parameter, ParameterError, Standard
from .iso7045_data import NON_PREFERRED_LENGTHS, SIZES, SizeData


def _fmt(x: float) -> str:
    return f"{x:g}"


# Thread-end shifts (in pitches, towards the tip) tried in turn when the
# shared helical fuse fails; see iso10642.py for the reason.
_Z_END_SHIFTS = (0.0, -0.05, -0.1, -0.2)

# Recess tool rotations (degrees) tried when a recess cut fails its check.
_RETRY_ANGLES = (0.0, 7.5, 15.0, 22.5)


def threaded_body(thread, length, z_end, z_shank_top, head, mode, what):
    last: Exception | None = None
    for shift in _Z_END_SHIFTS if mode == "modeled" else (0.0,):
        try:
            return threaded_screw(
                thread, length, z_end + shift * thread.P, z_shank_top, head, mode, what=what
            )
        except (AttributeError, RuntimeError) as exc:
            last = exc
    raise RuntimeError(f"thread fuse failed for {what}") from last


def cut_recess(body: Part, tool: Part, reference: Part, what: str) -> Part:
    """checked_cut, retrying with the tool turned a little about the axis."""
    return checked_cut(
        body, tool, reference, what,
        retry=lambda i: Rot(0, 0, _RETRY_ANGLES[i]) * tool,
        attempts=len(_RETRY_ANGLES),
    )


def corner_radius(sd: SizeData) -> float:
    """Radius between the dome and the cylindrical side of the head. ISO 7045
    shows a rounded edge but gives no value; k / 3 is a modeling choice."""
    return sd.k_max / 3


def head_outline(sd: SizeData) -> dict[str, Any]:
    """Points of the pan head outline (radius, z), bearing face at z = 0.

    The dome is a sphere of radius rf through (0, k); a corner fillet of
    radius corner_radius() joins it tangentially to the cylinder at dk / 2.
    """
    R_k = sd.dk_max / 2
    rc = corner_radius(sd)
    zs = sd.k_max - sd.rf                       # dome centre
    cx = R_k - rc                               # corner fillet centre
    cz = zs + math.sqrt((sd.rf - rc) ** 2 - cx**2)
    s = sd.rf / (sd.rf - rc)
    ps = (cx * s, zs + (cz - zs) * s)           # fillet / dome tangent point
    th = math.atan2(ps[1] - cz, ps[0] - cx)
    corner_mid = (cx + rc * math.cos(th / 2), cz + rc * math.sin(th / 2))
    ph = math.atan2(ps[1] - zs, ps[0])
    pm = (ph + math.pi / 2) / 2
    dome_mid = (sd.rf * math.cos(pm), zs + sd.rf * math.sin(pm))
    return {
        "z_side": cz, "tangent": ps, "corner_mid": corner_mid,
        "dome_mid": dome_mid, "dome_centre_z": zs,
    }


def dome_height(sd: SizeData, r: float) -> float:
    """z of the dome at radius r (inside the corner fillet)."""
    return sd.k_max - sd.rf + math.sqrt(sd.rf**2 - r**2)


def head_profile(sd: SizeData) -> tuple[float, list]:
    """(z_shank_top, head profile items) for threaded_screw."""
    R = sd.d / 2
    r = sd.r_min
    o = head_outline(sd)
    s2 = math.sqrt(0.5)
    head = [
        ("arc", (R + r - r * s2, -r + r * s2), (R + r, 0.0)),   # underhead fillet
        (sd.dk_max / 2, 0.0),                                   # bearing face
        (sd.dk_max / 2, o["z_side"]),                           # cylindrical side
        ("arc", o["corner_mid"], o["tangent"]),                 # rounded edge
        ("arc", o["dome_mid"], (0.0, sd.k_max)),                # dome
    ]
    return -r, head


def reference_body(sd: SizeData, l: float) -> Part:
    """Plain revolved screw (shank at d, no thread, no recess)."""
    z_shank_top, head = head_profile(sd)
    thread = MetricThread(sd.d, sd.P)
    r_tip = thread.d3 / 2
    R = sd.d / 2
    return revolve_profile([
        (0.0, -l), (r_tip, -l), (R, -l + (R - r_tip)), (R, z_shank_top), *head,
    ])


def build_body(sd: SizeData, l: float, thread_mode: str) -> Part:
    """Screw body without the recess.

    Coordinate system: Z is the screw axis, the bearing face is at z = 0,
    the dome rises to z = k and the tip is at z = -l.
    """
    if thread_mode not in THREAD_MODES:
        raise ParameterError(f"unknown thread mode {thread_mode!r}")
    thread = MetricThread(sd.d, sd.P)
    dr = sd.d / 2 - thread.d1 / 2
    z_shank_top, head = head_profile(sd)
    if sd.is_fully_threaded(l):
        z_end = z_shank_top - dr        # thread out right under the fillet (b = l - a)
    else:
        z_end = -(l - sd.b_min)
    what = f"ISO 7045 {sd.size} x {l:g}"
    return threaded_body(thread, l, z_end, z_shank_top, head, thread_mode, what)


def recess_reference_z(sd: SizeData, drive: str) -> float:
    """Reference plane of the recess: where the dome has diameter m
    (ISO 4757 2.2: below the crown, at the wing / surface intersection)."""
    m, _, _ = sd.recess(drive)
    return dome_height(sd, m / 2)


def recess_tool(sd: SizeData, drive: str) -> Part:
    m, p_min, p_max = sd.recess(drive)
    z_ref = recess_reference_z(sd, drive)
    h_up = sd.k_max - z_ref + 0.1 * sd.k_max
    return cross_recess(drive, sd.recess_no, m, (p_min + p_max) / 2, z_ref, h_up)


def build_screw(sd: SizeData, l: float, thread_mode: str, drive: str) -> Part:
    if drive not in CROSS_TYPES:
        raise ParameterError(f"unknown drive {drive!r}")
    body = build_body(sd, l, thread_mode)
    what = f"ISO 7045 {sd.size} x {l:g} {drive}"
    ref = body if thread_mode == "simplified" else reference_body(sd, l)
    return cut_recess(body, recess_tool(sd, drive), ref, what)


def _option_label(s: str, sd: SizeData) -> str:
    label = f"{s} x {_fmt(sd.P)}"
    return label if sd.preferred else f"({s}) x {_fmt(sd.P)}"


def validate_common(raw: dict[str, Any], sizes: dict, default_size: str, default_length: float,
                    drives: dict[str, str] | None) -> dict[str, Any]:
    """Shared validation for the cross recess / hexalobular screws."""
    size = str(raw.get("size", default_size))
    if size not in sizes:
        raise ParameterError(f"unknown size {size!r}; choose one of {', '.join(sizes)}")
    sd = sizes[size]
    try:
        length = float(raw.get("length", default_length))
    except (TypeError, ValueError):
        raise ParameterError("length must be a number") from None
    if not math.isfinite(length):
        raise ParameterError("length must be a number")
    length = round(length, 2)
    if not sd.l_min <= length <= sd.l_max:
        raise ParameterError(
            f"length for {size} must be between {_fmt(sd.l_min)} and {_fmt(sd.l_max)} mm"
        )
    thread = str(raw.get("thread", "simplified"))
    if thread not in THREAD_MODES:
        raise ParameterError(f"thread must be one of {', '.join(THREAD_MODES)}")
    out = {"size": size, "length": length, "thread": thread}
    if drives is not None:
        drive = str(raw.get("drive", "H"))
        if drive not in drives:
            raise ParameterError(f"drive must be one of {', '.join(drives)}")
        out["drive"] = drive
    return out


def length_notes(sd, l: float, non_preferred_lengths) -> list[str]:
    out = []
    if not sd.preferred:
        out.append(f"{sd.size} is in parentheses in the standard: avoid it if possible.")
    if l not in sd.standard_lengths():
        pref = ", ".join(_fmt(x) for x in sd.standard_lengths())
        out.append(f"{_fmt(l)} mm is not a standard length for {sd.size} (standard: {pref}).")
    elif l in non_preferred_lengths:
        out.append(f"{_fmt(l)} mm is in parentheses in the standard: avoid it if possible.")
    return out


def thread_mode_note(mode: str) -> str:
    if mode == "simplified":
        return (
            "Thread not modeled: shank is a plain cylinder at d. The threaded "
            "length is its own face, ready for a cosmetic thread."
        )
    return (
        "Thread modeled with the ISO 68-1 basic profile (flat root at d1), "
        "right hand, with a 2P runout."
    )


def cross_dimensions(sd, drive: str) -> list[Dimension]:
    m, p_min, p_max = sd.recess(drive)
    cg = cross_geometry(m, (p_min + p_max) / 2)
    rec = H_RECESSES[sd.recess_no] if drive == "H" else Z_RECESSES[sd.recess_no]
    dims = [
        Dimension("Recess", "Cross recess", f"{drive}{sd.recess_no}", unit=""),
        Dimension("m", "Recess diameter (ref)", m),
        Dimension("p min", "Penetration depth", p_min),
        Dimension("p max", "Penetration depth", p_max),
        Dimension("p model", "Modeled flank depth", round(cg.depth, 3)),
        Dimension("t total", "Modeled recess depth", round(cg.t_total, 3)),
        Dimension("g", "Gauge diameter (ISO 4757)", rec.g),
        Dimension("f", "Wing width (ISO 4757)",
                  f"{_fmt(rec.f_min)}–{_fmt(rec.f_max)}" if drive == "H" else rec.f),
    ]
    if drive == "H":
        dims.append(Dimension("b recess", "Core width (ISO 4757)", rec.b))
    dims += [
        Dimension("flank", "Wing flank angle", 26.5, unit="°"),
        Dimension("bottom", "Bottom cone angle", 28.0, unit="°"),
    ]
    return dims


CROSS_NOTE = (
    "Cross recess per ISO 4757, modeled from m and the mean penetration depth "
    "of this standard: 26.5° wing flanks down to the penetration depth, a 28° "
    "bottom cone, wing / core widths from ISO 4757. Exact recess geometry is "
    "defined by gauges; the model is a dimensionally faithful approximation "
    "(no edge radii, wing tapers simplified)."
)


class ISO7045(Standard):
    id = "iso7045"
    title = "ISO 7045"
    summary = "Pan head screws with type H or type Z cross recess, M1.6 to M10"
    category = "Screws"
    source = "Values in mm, from ISO 7045:2011 Table 1; cross recess ISO 4757:1983."

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="size",
                label="Thread size",
                kind="select",
                default="M4",
                options=[Option(s, _option_label(s, sd)) for s, sd in SIZES.items()],
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
        return f"ISO 7045 - {p['size']} x {_fmt(p['length'])} - {p['drive']}"

    def file_stem(self, p: dict[str, Any]) -> str:
        suffix = "_threaded" if p["thread"] == "modeled" else ""
        return f"ISO7045_{p['size']}x{_fmt(p['length'])}_{p['drive']}{suffix}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        sd = SIZES[p["size"]]
        l = p["length"]
        t = MetricThread(sd.d, sd.P)
        full = sd.is_fully_threaded(l)
        return [
            Dimension("d", "Thread diameter", sd.d),
            Dimension("P", "Pitch", sd.P),
            Dimension("l", "Nominal length", l),
            Dimension("b", "Thread length", "to head" if full else f"{_fmt(sd.b_min)} min"),
            Dimension("a max", "Thread to head", sd.a_max),
            Dimension("dk max", "Head diameter", sd.dk_max),
            Dimension("k max", "Head height", sd.k_max),
            Dimension("rf ≈", "Dome radius", sd.rf),
            Dimension("da max", "Fillet transition dia.", sd.da_max),
            Dimension("r min", "Underhead fillet", sd.r_min),
            *cross_dimensions(sd, p["drive"]),
            Dimension("d2", "Pitch diameter", round(t.d2, 3)),
            Dimension("d3", "Minor diameter", round(t.d3, 3)),
        ]

    def notes(self, p: dict[str, Any]) -> list[str]:
        sd = SIZES[p["size"]]
        l = p["length"]
        out = length_notes(sd, l, NON_PREFERRED_LENGTHS)
        if sd.is_fully_threaded(l):
            out.append("Threaded up to the head at this length (b = l - a).")
        else:
            out.append(
                f"Partially threaded: b = {_fmt(sd.b_min)} mm of thread, plain shank above."
            )
        out.append(thread_mode_note(p["thread"]))
        out.append(
            "Modeled at nominal sizes: dk max, k max, dome radius rf, underhead "
            f"fillet r min, ds = d. The edge between dome and side is rounded with "
            f"{corner_radius(sd):.2f} mm (k / 3; not specified by the standard)."
        )
        out.append(CROSS_NOTE)
        out.append(
            "Bearing face at z = 0, head up to z = k, tip at z = -l. The recess "
            "reference plane is where the dome has diameter m."
        )
        return out

    def build(self, p: dict[str, Any]) -> Part:
        part = build_screw(SIZES[p["size"]], p["length"], p["thread"], p["drive"])
        part.label = self.designation(p)
        return part

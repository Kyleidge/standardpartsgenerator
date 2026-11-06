"""ISO 7379 hexagon socket head shoulder screws."""

from __future__ import annotations

import math
from typing import Any

from build123d import Part

from ..geometry import MetricThread, ProfileItem, helical_thread, revolve_profile
from ..screws import THREAD_MODES, _fuse_ridge, cut_hex_socket
from .base import Dimension, Option, Parameter, ParameterError, Standard
from .iso7379_data import SIZES, SizeData

_S2 = math.sqrt(0.5)
UNDERCUT_ANGLE = 30.0  # neck-to-thread cone, degrees from the axis
TAN_UC = math.tan(math.radians(UNDERCUT_ANGLE))

# Axial offsets (in pitches, towards the tip) of the envelope's undercut
# cone from the core's cone, tried in turn if the thread fuse fails. Any
# non-zero offset keeps the envelope off the core's faces and edges.
_ENVELOPE_SHIFTS = (0.05, 0.08, 0.12)


def _fmt(x: float) -> str:
    return f"{x:g}"


def _fillet(r_from: float, z_from: float, r: float, dr: float, dz: float) -> ProfileItem:
    """Quarter-circle concave fillet of radius r from (r_from, z_from),
    turning from the axial to the radial direction; dr/dz give the signs."""
    end = (r_from + dr * r, z_from + dz * r)
    mid = (r_from + dr * r * (1 - _S2), z_from + dz * r * _S2)
    return ("arc", mid, end)


def build_body(sd: SizeData, l: float, thread_mode: str) -> Part:
    """Revolved screw body (no socket).

    Coordinate system: Z is the screw axis, the head bearing face lies in
    the XY plane at z = 0, the head extends to z = +k, the shoulder to
    z = -l (its end face) and the thread to the tip at z = -(l + b).

    From the head down: fillet r1 into the groove dg1 (width g1, 45 deg
    flank up to ds), the shoulder ds with its edge chamfer, the shoulder
    face, fillet r2 into the neck dg2 (length g2), a 30 deg cone up to the
    thread and the ISO 4753 chamfered point (d3 / 2 at 45 deg).
    """
    if thread_mode not in THREAD_MODES:
        raise ParameterError(f"unknown thread mode {thread_mode!r}")
    thread = MetricThread(sd.d, sd.P)
    P = sd.P
    R = sd.d / 2
    r_core = thread.d1 / 2
    r_tip = thread.d3 / 2
    r_neck = sd.dg2_nom / 2
    r_sh = sd.ds / 2
    r_gr = sd.dg1_min / 2
    c = sd.shoulder_chamfer
    v = sd.v
    k = sd.k_max
    z_s = -l                     # shoulder end face
    z_n = z_s - sd.g2_max        # end of the neck, start of the undercut cone
    z_tip = z_s - sd.b_nom

    def cone_z(r: float, shift: float = 0.0) -> float:
        """z at which the undercut cone (moved `shift` towards the tip) has radius r."""
        return z_n - shift - (r - r_neck) / TAN_UC

    upper: list[ProfileItem] = [
        (r_neck, z_n),
        (r_neck, z_s - sd.r2_min),
        _fillet(r_neck, z_s - sd.r2_min, sd.r2_min, +1, +1),
        (r_sh - c, z_s),
        (r_sh, z_s + c),                         # shoulder edge chamfer
        (r_sh, -sd.g1_max - (r_sh - r_gr)),      # shoulder up to the groove flank
        (r_gr, -sd.g1_max),                      # 45 deg flank
        (r_gr, -sd.r1_min),
        _fillet(r_gr, -sd.r1_min, sd.r1_min, +1, +1),
        (sd.dk_max / 2, 0.0),                    # bearing face
        (sd.dk_max / 2, k - v),
        (sd.dk_max / 2 - v, k),                  # top-edge chamfer
        (0.0, k),
    ]

    if thread_mode == "simplified":
        return revolve_profile([
            (0.0, z_tip),
            (r_tip, z_tip),
            (R, z_tip + (R - r_tip)),
            (R, cone_z(R)),                      # threaded face
            *upper,
        ])

    # Modeled: the core runs at the thread root d1 up to where the undercut
    # cone meets it; the ridge is trimmed by an envelope whose undercut cone
    # is parallel to the core's but moved slightly towards the tip, so the
    # thread ends on the cone without coincident faces.
    core = revolve_profile([
        (0.0, z_tip),
        (r_tip, z_tip),
        (r_core, z_tip + (r_core - r_tip)),
        (r_core, cone_z(r_core)),
        *upper,
    ])
    r_out = R + 0.05 * P
    r_in = r_core - 0.1 * P
    if r_in <= r_neck:
        raise RuntimeError(f"neck dg2 too large for the thread core of {sd.size}")
    z_lo = z_tip + 0.03 * P
    what = f"ISO 7379 {sd.size} x {l:g}"
    for shift in _ENVELOPE_SHIFTS:
        envelope = revolve_profile([
            (0.0, z_lo),
            (r_tip, z_lo),
            (r_out, z_lo + (r_out - r_tip)),
            (r_out, cone_z(r_out, shift * P)),
            (r_in, cone_z(r_in, shift * P)),
            (0.0, cone_z(r_in, shift * P)),
        ])
        ridge = helical_thread(thread, z_tip - P, cone_z(r_in) + P)
        try:
            # Checks single solid, validity and the added ridge volume, and
            # retries other start angles before giving up.
            return _fuse_ridge(core, ridge, envelope, what)
        except RuntimeError:
            continue
    raise RuntimeError(f"thread fuse failed for {what}")


def build_screw(sd: SizeData, l: float, thread_mode: str) -> Part:
    """build_body plus the socket, s nom to depth t min below z = k."""
    body = build_body(sd, l, thread_mode)
    return cut_hex_socket(body, sd.s_nom, sd.t_min, sd.k_max, f"ISO 7379 {sd.size} x {l:g}")


class ISO7379(Standard):
    id = "iso7379"
    title = "ISO 7379"
    summary = "Hexagon socket head shoulder screws, shoulder 6.5 to 25 mm (M5 to M20)"
    category = "Screws"
    source = "Values in mm, from ISO 7379:1983 section 3."

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="size",
                label="Shoulder diameter ds",
                kind="select",
                default="10",
                options=[Option(s, sd.label) for s, sd in SIZES.items()],
                help="Shoulder diameter, with the thread size in brackets.",
            ),
            Parameter(
                name="length",
                label="Shoulder length l",
                kind="length",
                default=40,
                depends_on="size",
                preferred={s: sd.standard_lengths() for s, sd in SIZES.items()},
                limits={s: [sd.l_min, sd.l_max] for s, sd in SIZES.items()},
                unit="mm",
                help="Nominal length: from under the head to the shoulder face, "
                "without the thread.",
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
        size = str(raw.get("size", "10"))
        if size not in SIZES:
            raise ParameterError(f"unknown size {size!r}; choose one of {', '.join(SIZES)}")
        sd = SIZES[size]
        try:
            length = float(raw.get("length", 40))
        except (TypeError, ValueError):
            raise ParameterError("length must be a number") from None
        if not math.isfinite(length):
            raise ParameterError("length must be a number")
        length = round(length, 2)
        if not sd.l_min <= length <= sd.l_max:
            raise ParameterError(
                f"shoulder length for {size} must be between {_fmt(sd.l_min)} and "
                f"{_fmt(sd.l_max)} mm"
            )
        thread = str(raw.get("thread", "simplified"))
        if thread not in THREAD_MODES:
            raise ParameterError(f"thread must be one of {', '.join(THREAD_MODES)}")
        return {"size": size, "length": length, "thread": thread}

    def designation(self, p: dict[str, Any]) -> str:
        return f"ISO 7379 - {p['size']} x {_fmt(p['length'])}"

    def file_stem(self, p: dict[str, Any]) -> str:
        suffix = "_threaded" if p["thread"] == "modeled" else ""
        return f"ISO7379_{p['size']}x{_fmt(p['length'])}{suffix}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        sd = SIZES[p["size"]]
        l = p["length"]
        t = MetricThread(sd.d, sd.P)
        return [
            Dimension("ds", "Shoulder diameter (f9)", sd.ds),
            Dimension("ds max", "Shoulder diameter max.", sd.ds_max),
            Dimension("ds min", "Shoulder diameter min.", sd.ds_min),
            Dimension("l", "Shoulder length", l),
            Dimension("d", "Thread", sd.thread, unit=""),
            Dimension("P", "Pitch", sd.P),
            Dimension("b", "Thread length (modeled)", sd.b_nom),
            Dimension("b max", "Thread length max.", sd.b_max),
            Dimension("l + b", "Overall length under head", round(l + sd.b_nom, 3)),
            Dimension("dk max", "Head diameter", sd.dk_max),
            Dimension("k max", "Head height", sd.k_max),
            Dimension("s", "Socket across flats", sd.s_nom),
            Dimension("e min", "Socket across corners", sd.e_min),
            Dimension("t min", "Socket depth", sd.t_min),
            Dimension("w min", "Wall thickness", sd.w_min),
            Dimension("dg1 min", "Groove dia. under head", sd.dg1_min),
            Dimension("g1 max", "Groove width under head", sd.g1_max),
            Dimension("r1 min", "Underhead fillet", sd.r1_min),
            Dimension("dg2", "Neck diameter (modeled)", sd.dg2_nom),
            Dimension("g2 max", "Neck length", sd.g2_max),
            Dimension("r2 min", "Shoulder face fillet", sd.r2_min),
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
                f"{_fmt(l)} mm is not a standard shoulder length for {sd.size} "
                f"(standard: {pref}; ISO 888 intermediate lengths are permitted)."
            )
        out.append(
            f"Shoulder {_fmt(sd.ds)} f9 ({_fmt(sd.ds_max)} / {_fmt(sd.ds_min)}), modeled at "
            f"nominal; thread {sd.thread} x {_fmt(sd.b_nom)} below the shoulder face."
        )
        if p["thread"] == "simplified":
            out.append(
                "Thread not modeled: a plain cylinder at d. The threaded length is "
                "its own face, ready for a cosmetic thread."
            )
        else:
            out.append(
                "Thread modeled with the ISO 68-1 basic profile (flat root at d1), "
                "right hand, running out on the 30 deg undercut cone."
            )
        out.append(
            "Modeled at nominal sizes: dk max, k max, ds nom, b and dg2 at mid "
            "tolerance, groove dg1 min x g1 max, neck length g2 max, fillets r1 min "
            "and r2 min, socket s nom to depth t min."
        )
        out.append(
            "Head top-edge chamfer (v = 0.1 k) and the 30 deg undercut cone are "
            "model choices; the standard leaves them open or as a minimum."
        )
        return out

    def build(self, p: dict[str, Any]) -> Part:
        part = build_screw(SIZES[p["size"]], p["length"], p["thread"])
        part.label = self.designation(p)
        return part

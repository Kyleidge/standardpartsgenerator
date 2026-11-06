"""ISO 3601-1 O-rings."""

from __future__ import annotations

import math
from typing import Any

from build123d import Part, Torus

from .base import Dimension, Option, Parameter, ParameterError, Standard
from .iso3601_data import (
    CROSS_SECTIONS,
    SIZES,
    UNVERIFIED_CODES,
    CrossSection,
    ORingSize,
    class_b_tolerance,
    find,
)


def _fmt(x: float) -> str:
    return f"{x:g}"


def _iso(x: float) -> str:
    """Number in the standard's designation style (decimal comma)."""
    return _fmt(x).replace(".", ",")


def torus_volume(d1: float, d2: float) -> float:
    R = (d1 + d2) / 2
    r = d2 / 2
    return 2 * math.pi ** 2 * R * r * r


def build_oring(d1: float, d2: float) -> Part:
    """Torus with inside diameter d1 and tube diameter d2.

    Coordinate system: Z is the ring axis, the ring is centred on the origin
    and symmetric about the XY plane (z = -d2/2 to +d2/2).
    """
    part = Torus((d1 + d2) / 2, d2 / 2)
    expected = torus_volume(d1, d2)
    bb = part.bounding_box()
    ok = (
        part.is_valid
        and len(part.solids()) == 1
        and abs(part.volume - expected) < 1e-6 * expected
        and abs(bb.size.X - (d1 + 2 * d2)) < 1e-6
        and abs(bb.size.Z - d2) < 1e-6
    )
    if not ok:
        raise RuntimeError(f"O-ring construction failed for {d1:g} x {d2:g}")
    return part


def _option_label(cs: CrossSection) -> str:
    rows = SIZES[cs.key]
    if cs.family == "metric":
        return f"{_fmt(cs.d2)} mm  (metric, codes {cs.letter}…)"
    codes = rows[0].code if len(rows) == 1 else f"{rows[0].code}–{rows[-1].code}"
    return f"{_fmt(cs.d2)} mm  ({cs.d2 / 25.4:.3f} in, AS568 {codes})"


class ISO3601(Standard):
    id = "iso3601"
    title = "ISO 3601-1"
    summary = "O-rings: metric series (d2 = 1.8 to 7) and inch / AS568 series (d2 = 1.02 to 6.99)"
    category = "Seals"
    source = "Values in mm, from ISO 3601-1:2012 (+ Amd 1:2019)."

    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="d2",
                label="Cross-section d2",
                kind="select",
                default="2.65",
                options=[Option(k, _option_label(cs)) for k, cs in CROSS_SECTIONS.items()],
                help="Metric sizes (codes A to E) or the inch-based sizes whose codes are "
                "the AS568 dash numbers.",
            ),
            Parameter(
                name="d1",
                label="Inside diameter d1",
                kind="length",
                default=20,
                depends_on="d2",
                preferred={k: [r.d1 for r in rows] for k, rows in SIZES.items()},
                limits={k: [rows[0].d1, rows[-1].d1] for k, rows in SIZES.items()},
                unit="mm",
                help="Preferred values are the standard sizes for this cross-section.",
            ),
        ]

    def validate(self, raw: dict[str, Any]) -> dict[str, Any]:
        raw_d2 = raw.get("d2", "2.65")
        key = str(raw_d2)
        if key not in CROSS_SECTIONS:
            try:
                value = float(key)
            except (TypeError, ValueError):
                value = math.nan
            key = next((k for k, cs in CROSS_SECTIONS.items() if cs.d2 == value), "")
        if not key:
            raise ParameterError(
                f"unknown cross-section {raw_d2!r}; choose one of {', '.join(CROSS_SECTIONS)}"
            )
        rows = SIZES[key]
        try:
            d1 = float(raw.get("d1", 20))
        except (TypeError, ValueError):
            raise ParameterError("d1 must be a number") from None
        if not math.isfinite(d1):
            raise ParameterError("d1 must be a number")
        d1 = round(d1, 2)
        lo, hi = rows[0].d1, rows[-1].d1
        if not lo <= d1 <= hi:
            raise ParameterError(
                f"d1 for d2 = {key} must be between {_fmt(lo)} and {_fmt(hi)} mm"
            )
        return {"d2": key, "d1": d1}

    @staticmethod
    def _row(p: dict[str, Any]) -> ORingSize | None:
        return find(p["d2"], p["d1"])

    def designation(self, p: dict[str, Any]) -> str:
        cs = CROSS_SECTIONS[p["d2"]]
        row = self._row(p)
        size = f"{_fmt(p['d1'])} x {_fmt(cs.d2)}"
        if row is None:
            return f"O-ring {size} (non-standard d1)"
        part1 = "ISO 3601-1A" if cs.family == "metric" else "ISO 3601-1"
        return f"O-ring {part1} - {row.code} - {size}"

    def file_stem(self, p: dict[str, Any]) -> str:
        return f"ISO3601-1_{_fmt(p['d1'])}x{_fmt(CROSS_SECTIONS[p['d2']].d2)}"

    def dimensions(self, p: dict[str, Any]) -> list[Dimension]:
        cs = CROSS_SECTIONS[p["d2"]]
        row = self._row(p)
        d1, d2 = p["d1"], cs.d2
        out = [
            Dimension("code", "Size code", row.code if row else "none (non-standard)", ""),
        ]
        if row and cs.family == "inch":
            out.append(Dimension("AS568", "AS568 dash number", f"-{row.code}", ""))
        out.append(Dimension("table", "ISO 3601-1 table", cs.table, ""))
        out.append(Dimension("d1", "Inside diameter", d1))
        if row is None:
            out.append(Dimension("d1 tol. ±", "Inside dia. tolerance (Eq. A.1, class B)",
                                 class_b_tolerance(d1)))
        elif cs.family == "inch":
            out.append(Dimension("d1 tol. A ±", "Inside dia. tolerance, class A", row.tol))
            out.append(Dimension("d1 tol. B ±", "Inside dia. tolerance, class B",
                                 class_b_tolerance(d1)))
        else:
            out.append(Dimension("d1 tol. ±", "Inside dia. tolerance", row.tol))
        out.append(Dimension("d2", "Cross-section", d2))
        if cs.tol_b is not None and cs.tol_b != cs.tol_a:
            out.append(Dimension("d2 tol. A ±", "Cross-section tolerance, class A", cs.tol_a))
            out.append(Dimension("d2 tol. B ±", "Cross-section tolerance, class B", cs.tol_b))
        else:
            out.append(Dimension("d2 tol. ±", "Cross-section tolerance", cs.tol_a))
        out.append(Dimension("d3", "Outside diameter (d1 + 2·d2, ref.)", round(d1 + 2 * d2, 3)))
        out.append(Dimension("V", "Volume (ref.)", round(torus_volume(d1, d2) / 1000, 4), "cm³"))
        return out

    def notes(self, p: dict[str, Any]) -> list[str]:
        cs = CROSS_SECTIONS[p["d2"]]
        row = self._row(p)
        d1 = p["d1"]
        out = []
        if row is None:
            out.append(
                f"d1 = {_fmt(d1)} mm is not a standard size for d2 = {_fmt(cs.d2)} "
                "(see the preferred values). Tolerance shown is the class B "
                "formula for non-standard O-rings."
            )
        elif row.code in UNVERIFIED_CODES:
            out.append(
                f"Size {row.code} is listed by one secondary source only and its d1 "
                "tolerance is calculated (ISO 3601-1:2002 series A formula); check "
                "both against the standard before ordering."
            )
        if cs.family == "metric":
            out.append(
                "Metric series: in ISO 3601-1:2012 these sizes are listed for aerospace "
                "applications (Tables 7 to 11), designated e.g. "
                f"O-ring-ISO3601-1A-{row.code if row else 'C0630'}-"
                f"{_iso(d1) if row else '63'}×{_iso(cs.d2) if row else '3,55'}-N "
                "(grade N, S or CS)."
            )
        else:
            code = row.code if row else "214"
            out.append(
                "Inch-based series for general industrial applications; the size code "
                "is the AS568 dash number. Full designation adds the tolerance class "
                f"and grade, e.g. O-ring-ISO3601-1-{code}A-"
                f"{_iso(d1) if row else '24,99'}×{_iso(cs.d2) if row else '3,53'}-N."
            )
        out.append(
            "Modeled as a torus at nominal d1 and d2, axis Z, centred on the origin "
            "(z = ±d2/2)."
        )
        out.append(
            "Housing (groove) dimensions of ISO 3601-2 are not included: no reliable "
            "public source for its tables was found."
        )
        return out

    def build(self, p: dict[str, Any]) -> Part:
        part = build_oring(p["d1"], CROSS_SECTIONS[p["d2"]].d2)
        part.label = self.designation(p)
        return part

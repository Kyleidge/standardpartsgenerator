"""Dimension table for ISO 4762:2004, hexagon socket head cap screws.

Sources:

* M1.6 to M12: ISO 4762:2004 Table 1.
* M14 to M64: the same columns as listed by fasten.it (DIN EN ISO 4762,
  06-2004) and the omdl ISO 4762 fastener database (d, P, b, dk, da, e, k,
  s, t, w); not checked against ISO 4762:2004 Table 1 itself. v follows
  the rule visible in the smaller sizes (v = 0.1 d).
  r_min and dw_min for these sizes come from secondary tables and have not
  been checked against the standard text; they only shape the small
  underhead fillet and bearing-face chamfer.
* lf_max = 1.7 r_max and r_max = (da_max - ds_max) / 2 (ISO 4762 Figure 1).

All values are in millimetres. Where the standard gives a range, the field
name says which limit it is (``dk_max``, ``t_min``, ...).
"""

from __future__ import annotations

from dataclasses import dataclass

# Preferred nominal lengths l (ISO 4762:2004 Table 1, length column).
LENGTH_SERIES: tuple[float, ...] = (
    2.5, 3, 4, 5, 6, 8, 10, 12, 16, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65,
    70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 180, 200, 220, 240, 260,
    280, 300,
)


@dataclass(frozen=True)
class SizeData:
    size: str          # designation, e.g. "M6"
    d: float           # nominal thread diameter
    P: float           # coarse thread pitch
    b: float           # thread length (reference) for partially threaded screws
    dk_max: float      # head diameter, plain head
    dk_max_knurled: float
    dk_min: float
    da_max: float      # transition diameter of the underhead fillet
    ds_min: float      # shank diameter (ds_max = d)
    e_min: float       # socket width across corners
    k_max: float       # head height (= d)
    k_min: float
    r_min: float       # underhead fillet radius
    s_nom: float       # socket width across flats
    t_min: float       # socket depth (key engagement)
    v_max: float       # head top-edge chamfer
    dw_min: float      # bearing face diameter
    w_min: float       # wall thickness under the socket
    l_min: float       # shortest nominal length in the standard
    l_max: float       # longest nominal length in the standard

    @property
    def ds_max(self) -> float:
        return self.d

    @property
    def lf_max(self) -> float:
        """Maximum underhead fillet length, lf = 1.7 r_max."""
        return 1.7 * (self.da_max - self.ds_max) / 2

    def standard_lengths(self) -> list[float]:
        return [l for l in LENGTH_SERIES if self.l_min <= l <= self.l_max]

    def thread_geometry(self, l: float) -> tuple[float | None, float | None]:
        """Return (ls_min, lg_max) for nominal length l.

        Both are None when the screw is threaded up to the head. The standard
        gives lg_max = l - b and ls_min = lg_max - 5P, and lists these values
        only once the plain shank is at least about half a diameter long
        (ls_min >= d / 2). This rule reproduces the stepped line of Table 1
        exactly for M1.6 to M12 and is applied to the larger sizes too.
        """
        lg_max = l - self.b
        ls_min = lg_max - 5 * self.P
        if ls_min < self.d / 2:
            return None, None
        return round(ls_min, 3), round(lg_max, 3)

    def is_fully_threaded(self, l: float) -> bool:
        return self.thread_geometry(l)[0] is None


def _row(size, d, P, b, dk_max, dk_max_knurled, dk_min, da_max, ds_min, e_min,
         k_min, r_min, s_nom, t_min, v_max, dw_min, w_min, l_min, l_max):
    return SizeData(
        size=size, d=d, P=P, b=b, dk_max=dk_max, dk_max_knurled=dk_max_knurled,
        dk_min=dk_min, da_max=da_max, ds_min=ds_min, e_min=e_min, k_max=d,
        k_min=k_min, r_min=r_min, s_nom=s_nom, t_min=t_min, v_max=v_max,
        dw_min=dw_min, w_min=w_min, l_min=l_min, l_max=l_max,
    )


# fmt: off
#      size    d     P     b    dk    dk_kn  dk_min  da    ds_min  e_min   k_min  r_min s    t     v     dw     w     l_min l_max
SIZES: dict[str, SizeData] = {r.size: r for r in [
    _row("M1.6", 1.6, 0.35, 15,  3.00, 3.14,  2.86,  2.0,  1.46,  1.733,  1.46,  0.1,  1.5, 0.7,  0.16, 2.72,  0.55, 2.5, 16),
    _row("M2",   2,   0.4,  16,  3.80, 3.98,  3.62,  2.6,  1.86,  1.733,  1.86,  0.1,  1.5, 1.0,  0.2,  3.48,  0.55, 3,   20),
    _row("M2.5", 2.5, 0.45, 17,  4.50, 4.68,  4.32,  3.1,  2.36,  2.303,  2.36,  0.1,  2,   1.1,  0.25, 4.18,  0.85, 4,   25),
    _row("M3",   3,   0.5,  18,  5.50, 5.68,  5.32,  3.6,  2.86,  2.873,  2.86,  0.1,  2.5, 1.3,  0.3,  5.07,  1.15, 5,   30),
    _row("M4",   4,   0.7,  20,  7.00, 7.22,  6.78,  4.7,  3.82,  3.443,  3.82,  0.2,  3,   2.0,  0.4,  6.53,  1.4,  6,   40),
    _row("M5",   5,   0.8,  22,  8.50, 8.72,  8.28,  5.7,  4.82,  4.583,  4.82,  0.2,  4,   2.5,  0.5,  8.03,  1.9,  8,   50),
    _row("M6",   6,   1.0,  24, 10.00, 10.22, 9.78,  6.8,  5.82,  5.723,  5.7,   0.25, 5,   3.0,  0.6,  9.38,  2.3,  10,  60),
    _row("M8",   8,   1.25, 28, 13.00, 13.27, 12.73, 9.2,  7.78,  6.863,  7.64,  0.4,  6,   4.0,  0.8,  12.33, 3.3,  12,  80),
    _row("M10",  10,  1.5,  32, 16.00, 16.27, 15.73, 11.2, 9.78,  9.149,  9.64,  0.4,  8,   5.0,  1.0,  15.33, 4.0,  16,  100),
    _row("M12",  12,  1.75, 36, 18.00, 18.27, 17.73, 13.7, 11.73, 11.429, 11.57, 0.6,  10,  6.0,  1.2,  17.23, 4.8,  20,  120),
    _row("M14",  14,  2.0,  40, 21.00, 21.33, 20.67, 15.7, 13.73, 13.716, 13.57, 0.6,  12,  7.0,  1.4,  20.17, 5.8,  25,  140),
    _row("M16",  16,  2.0,  44, 24.00, 24.33, 23.67, 17.7, 15.73, 15.996, 15.57, 0.6,  14,  8.0,  1.6,  23.17, 6.8,  25,  160),
    _row("M20",  20,  2.5,  52, 30.00, 30.33, 29.67, 22.4, 19.67, 19.437, 19.48, 0.8,  17,  10.0, 2.0,  28.87, 8.6,  30,  200),
    _row("M24",  24,  3.0,  60, 36.00, 36.39, 35.61, 26.4, 23.67, 21.734, 23.48, 0.8,  19,  12.0, 2.4,  34.81, 10.4, 40,  200),
    _row("M30",  30,  3.5,  72, 45.00, 45.39, 44.61, 33.4, 29.67, 25.154, 29.48, 1.0,  22,  15.5, 3.0,  43.61, 13.1, 45,  200),
    _row("M36",  36,  4.0,  84, 54.00, 54.46, 53.54, 39.4, 35.61, 30.854, 35.38, 1.0,  27,  19.0, 3.6,  52.54, 15.3, 55,  200),
    _row("M42",  42,  4.5,  96, 63.00, 63.46, 62.54, 45.6, 41.61, 36.571, 41.38, 1.2,  32,  24.0, 4.2,  61.34, 16.3, 60,  300),
    _row("M48",  48,  5.0,  108, 72.00, 72.46, 71.54, 52.6, 47.61, 41.131, 47.38, 1.6, 36,  28.0, 4.8,  70.34, 17.5, 70,  300),
    _row("M56",  56,  5.5,  124, 84.00, 84.54, 83.46, 63.0, 55.54, 46.831, 55.26, 2.0, 41,  34.0, 5.6,  82.26, 19.0, 80,  300),
    _row("M64",  64,  6.0,  140, 96.00, 96.54, 95.46, 71.0, 63.54, 52.531, 63.26, 2.0, 46,  38.0, 6.4,  94.26, 22.0, 90,  300),
]}
# fmt: on

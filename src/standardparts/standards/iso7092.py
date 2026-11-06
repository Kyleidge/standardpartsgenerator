"""ISO 7092 (small series) and ISO 7093-1 (large series) plain washers,
product grade A.

Same model and parameters as ISO 7089 (iso7089._PlainWasher): a flat ring
with faces at z = 0 and z = h, at nominal d1, d2 and h.
"""

from __future__ import annotations

from .iso7089 import _PlainWasher
from .iso7092_data import ISO7092_SIZES, ISO7093_SIZES


class ISO7092(_PlainWasher):
    id = "iso7092"
    title = "ISO 7092"
    summary = "Plain washers, small series, product grade A, sizes 1.6 to 36"
    source = "Values in mm, from ISO 7092:2000 Tables 1 and 2."
    number = "7092"
    sizes = ISO7092_SIZES
    chamfered = False


class ISO7093(_PlainWasher):
    id = "iso7093"
    title = "ISO 7093-1"
    summary = "Plain washers, large series, product grade A, sizes 3 to 36"
    source = "Values in mm, from ISO 7093-1:2000 Tables 1 and 2."
    number = "7093-1"
    sizes = ISO7093_SIZES
    chamfered = False

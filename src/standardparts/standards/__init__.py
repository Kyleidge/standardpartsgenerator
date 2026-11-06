"""Registry of available standards, in the order the UI lists them."""

from __future__ import annotations

from .base import ParameterError, Standard
from .din471 import DIN471
from .din472 import DIN472
from .din508 import DIN508
from .din580 import DIN580
from .din1587 import DIN1587
from .din6799 import DIN6799
from .din6885 import DIN6885
from .din7984 import DIN7984
from .hexscrew import ISO4014, ISO4017
from .hexscrew_fine import ISO8676, ISO8765
from .iso10642 import ISO10642
from .iso1234 import ISO1234
from .iso14581 import ISO14581
from .iso15 import ISO15
from .iso2338 import ISO2338
from .iso2351 import ISO2351
from .iso2725 import ISO2725
from .iso2936 import ISO2936
from .iso3601 import ISO3601
from .iso4032 import ISO4032
from .iso4035 import ISO4035
from .iso4161 import ISO4161
from .iso4162 import ISO4162
from .iso4762 import ISO4762
from .iso7045 import ISO7045
from .iso7046 import ISO7046
from .iso7089 import ISO7089, ISO7090
from .iso7092 import ISO7092, ISO7093
from .iso7379 import ISO7379
from .iso7380 import ISO7380
from .iso8673 import ISO8673
from .iso8734 import ISO8734
from .iso8735 import ISO8735
from .nyloc import ISO7040, ISO10511
from .set_screws import ISO4026, ISO4027, ISO4028, ISO4029

STANDARDS: dict[str, Standard] = {
    s.id: s
    for s in [
        # Screws
        ISO4762(), DIN7984(), ISO4014(), ISO4017(), ISO8765(), ISO8676(),
        ISO4162(), ISO10642(), ISO7380(), ISO7379(),
        ISO7045(), ISO7046(), ISO14581(),
        # Set screws
        ISO4026(), ISO4027(), ISO4028(), ISO4029(),
        # Nuts
        ISO4032(), ISO8673(), ISO4035(), ISO4161(), ISO7040(), ISO10511(),
        DIN1587(), DIN508(),
        # Washers
        ISO7089(), ISO7090(), ISO7092(), ISO7093(),
        # Retaining rings
        DIN471(), DIN472(), DIN6799(),
        # Pins and keys
        ISO8734(), ISO8735(), ISO2338(), ISO1234(), DIN6885(),
        # Seals
        ISO3601(),
        # Bearings
        ISO15(),
        # Lifting
        DIN580(),
        # Tools
        ISO2936(), ISO2351(), ISO2725(),
    ]
}

__all__ = ["STANDARDS", "ParameterError", "Standard"]

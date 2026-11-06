"""Progress events from long builds, for the progress bar in the browser.

A build is mostly single OpenCascade calls that cannot report how far they
are, so the builders report milestones instead, and the page turns them into
a time estimate:

* ("stage", name="model" | "preview"): building the solid, then the
  tessellated glTF preview.
* ("thread", turns=n): a helical thread of n turns is about to be fused.
  Thread booleans dominate the build time and scale with the turn count.
* ("retry",): a thread boolean failed its check and is being retried.

Nothing listens by default; the browser worker sets a listener.
"""

from __future__ import annotations

import json
from collections.abc import Callable

_listener: Callable[[str, str], None] | None = None


def set_listener(listener: Callable[[str, str], None] | None) -> None:
    """Call `listener(event, json_data)` for every event (None to stop)."""
    global _listener
    _listener = listener


def report(event: str, **data: object) -> None:
    if _listener is not None:
        _listener(event, json.dumps(data))

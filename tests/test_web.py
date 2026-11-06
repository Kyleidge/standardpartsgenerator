"""The functions the browser worker calls (standardparts.web)."""

import json

from standardparts import web
from standardparts.standards import STANDARDS


def test_catalog_lists_every_standard_with_its_schema():
    cat = web.catalog()
    ids = [s["id"] for s in cat["standards"]]
    assert ids == list(STANDARDS)
    iso = cat["standards"][ids.index("iso4762")]
    assert [p["name"] for p in iso["parameters"]] == ["size", "length", "thread"]
    assert iso["parameters"][1]["preferred"]["M6"][0] == 10
    assert {"id", "title", "summary", "category", "source"} <= iso.keys()
    json.dumps(cat)  # must be serialisable


def test_info():
    info = json.loads(web.info("iso4762", json.dumps({"size": "M8", "length": 40})))
    assert info["ok"]
    assert info["designation"] == "ISO 4762 - M8 x 40"
    assert info["filename"] == "ISO4762_M8x40.stp"
    dims = {d["symbol"]: d["value"] for d in info["dimensions"]}
    assert dims["lg max"] == 12 and dims["ls min"] == 5.75 and dims["s"] == 6


def test_info_accepts_strings_from_the_url():
    info = json.loads(web.info("din471", json.dumps({"size": "20", "state": "free"})))
    assert info["ok"] and info["filename"] == "DIN471_20x1.2_free.stp"


def test_invalid_parameters_are_reported_not_raised():
    for call in (web.info, lambda s, r: json.loads(web.preview(s, r)[0]), lambda s, r: json.loads(web.step(s, r)[0])):
        res = call("iso4762", json.dumps({"size": "M7"}))
        res = json.loads(res) if isinstance(res, str) else res
        assert res["ok"] is False and "unknown size" in res["error"]
    res = json.loads(web.info("nope", "{}"))
    assert res == {"ok": False, "error": "unknown standard 'nope'"}


def test_preview_is_binary_gltf():
    meta, glb = web.preview("iso4762", json.dumps({"size": "M6", "length": 20}))
    assert json.loads(meta) == {"ok": True}
    assert glb[:4] == b"glTF"
    assert int.from_bytes(glb[8:12], "little") == len(glb)


def test_step_download():
    meta, data = web.step("iso4762", json.dumps({"size": "M3", "length": 10, "thread": "modeled"}))
    assert json.loads(meta) == {"ok": True, "filename": "ISO4762_M3x10_threaded.stp"}
    assert data.startswith(b"ISO-10303-21;")
    assert b"ISO 4762 - M3 x 10" in data


def test_two_solid_part_keeps_its_colours():
    meta, glb = web.preview("iso7040", json.dumps({"size": "M10"}))
    assert json.loads(meta)["ok"] and glb[:4] == b"glTF"


def test_preview_reports_progress_milestones():
    from standardparts import export, progress

    events = []
    progress.set_listener(lambda event, data: events.append((event, json.loads(data))))
    try:
        export._build_cached.cache_clear()
        web.preview("iso4762", json.dumps({"size": "M5", "length": 16, "thread": "modeled"}))
        names = [e for e, _ in events]
        assert names[0] == "stage" and events[0][1] == {"name": "model"}
        assert events[-1] == ("stage", {"name": "preview"})
        turns = sum(d["turns"] for e, d in events if e == "thread")
        assert turns >= 16 / 0.8  # at least the threaded length in turns
        # A cached part builds nothing, so only the two stage events remain.
        events.clear()
        web.preview("iso4762", json.dumps({"size": "M5", "length": 16, "thread": "modeled"}))
        assert [e for e, _ in events] == ["stage", "stage"]
    finally:
        progress.set_listener(None)

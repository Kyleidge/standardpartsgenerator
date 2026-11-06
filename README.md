<img src="assets/icon.svg" width="64" height="64" alt="">

# StandardPartsGenerator

A website that generates STEP (`.stp`) models of ISO and DIN standard parts.
Pick a standard and its parameters, check the 3D preview, then download the
STEP file.

It is front-end only: the CAD kernel runs in the browser (Python and
OpenCascade compiled to WebAssembly), so the site is a folder of static files
that any static host can serve. There is no server-side code.

Supported standards (43):

| Standard | Part | Range | Options |
|---|---|---|---|
| ISO 4762 | Hexagon socket head cap screw | M1.6–M64 | length, thread |
| DIN 7984 | Hexagon socket head cap screw, low head | M3–M24 | length, thread |
| ISO 4014 | Hexagon head bolt, partially threaded | M1.6–M64 | length, thread |
| ISO 4017 | Hexagon head screw, fully threaded | M1.6–M64 | length, thread |
| ISO 8765 / 8676 | Hexagon head bolt / screw, metric fine pitch | M8x1–M64x4 | length, thread |
| ISO 4162 | Hexagon flange bolt, small series | M5–M16 | length, thread |
| ISO 10642 | Hexagon socket countersunk head screw | M3–M20 | length, thread |
| ISO 7380-1 | Hexagon socket button head screw | M3–M16 | length, thread |
| ISO 7379 | Hexagon socket shoulder screw | shoulder 6.5–25 (M5–M20) | shoulder length, thread |
| ISO 7045 | Pan head screw, cross recess | M1.6–M10 | length, thread, H / Z |
| ISO 7046-1 | Countersunk head screw, cross recess | M1.6–M10 | length, thread, H / Z |
| ISO 14581 | Countersunk head screw, hexalobular (Torx) | M2–M10 | length, thread |
| ISO 4026 / 4027 / 4028 / 4029 | Hexagon socket set screw, flat / cone / dog / cup point | M1.6–M24 | length, thread |
| ISO 4032 | Hexagon nut, style 1 | M1.6–M64 | thread |
| ISO 8673 | Hexagon nut, style 1, metric fine pitch | M8x1–M64x4 | thread |
| ISO 4035 | Hexagon thin nut | M1.6–M64 | thread |
| ISO 4161 | Hexagon nut with flange | M5–M20 | thread |
| ISO 7040 / 10511 | Nyloc nut, regular / thin (steel body + insert as two solids) | M3–M36 | thread |
| DIN 1587 | Hexagon domed cap (acorn) nut | M4–M24 | thread |
| DIN 508 | T-slot nut | slot 5–54 (M4–M48) | thread |
| ISO 7089 / 7090 | Plain washer, normal series / chamfered | 1.6–64 / 5–64 | |
| ISO 7092 / 7093-1 | Plain washer, small / large series | 1.6–36 / 3–36 | |
| DIN 471 | Retaining ring for shafts | d1 = 3–300 mm | free / installed |
| DIN 472 | Retaining ring for bores | d1 = 8–300 mm | free / installed |
| DIN 6799 | Retaining washer (E-clip) for shafts | d2 = 0.8–30 mm | |
| ISO 8734 | Parallel pin, hardened (dowel pin) | d = 1–20 mm | length |
| ISO 8735 | Parallel pin with internal thread | d = 6–50 mm | length, type A / B, vent, thread |
| ISO 2338 | Parallel pin, unhardened | d = 0.6–50 mm | length, m6 / h8 |
| ISO 1234 | Split pin | 0.6–20 | length |
| DIN 6885-1 | Parallel key, high form | 2×2 – 100×50 | length, form A / B / AB |
| ISO 3601-1 | O-ring, metric (A–E) and inch (AS568) series | 727 sizes | cross-section, inner diameter |
| ISO 15 | Deep groove ball bearing, series 60 / 62 / 63 | 6000–6322 | envelope / faces / rings and balls |
| DIN 580 | Lifting eye bolt | M8–M100x6 | thread |
| ISO 2936 | Hexagon socket screw key (hex key) | s = 0.7–36 | standard / long (M) / extra-long (L) |
| ISO 2351-3 | Screwdriver bit for hexagon socket screws, ISO 1173 drive end | s = 0.7–12, 61 combinations | drive end A 3 … G 7 |
| ISO 2725-1 | Square drive socket, hand-operated, ISO 1174-1 drive square | 6.3 / 10 / 12.5 drive, s = 3.2–34 | hex / bi-hex, type A / B, retainer C / D |

Thread modes everywhere: **simplified** (plain cylinder at d, threaded length
as its own face, ready for a cosmetic thread) or **modeled** (helical ISO 68-1
basic profile). Every data module (`src/standardparts/standards/*_data.py`)
names its sources in the docstring, and lists any values that are derived or
were not cross-checked.

## Running it

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run standardparts                                # build dist/ and serve it on http://127.0.0.1:8000
uv run standardparts serve --host 0.0.0.0 --port 8080
uv run standardparts build                          # only write dist/
```

The first build downloads the Python runtime and wheels (about 60 MB, checked
against pinned sha256 hashes) into `.cache/wasm/`; later builds are offline.

Run the tests with `uv run pytest`. They build every size in both thread
modes natively and take a while (around 15 minutes); run a single test file
to go faster. To check the built site in a real browser, which builds every
standard in the WebAssembly kernel:

```sh
uv run --with playwright playwright install chromium   # first time only
uv run --with playwright python scripts/check_site.py
```

## Hosting

The repository deploys itself to GitHub Pages: `.github/workflows/pages.yml`
builds the site on every push to `main` and publishes `dist/` (Pages source:
GitHub Actions).

`uv run standardparts build` writes `dist/` (about 60 MB, most of it the
OpenCascade and SciPy WebAssembly wheels). Upload that folder to any static
host: GitHub Pages, Cloudflare Pages, Netlify, an S3 bucket or plain nginx.
The largest file is 23 MB, under the per-file limits of the free tiers. All
URLs are relative, so the site also works from a sub-path such as
`https://user.github.io/repo/`. No special headers are needed; serve `.wasm`
as `application/wasm` and `.mjs` as `text/javascript`, as most hosts do.

What visitors get:

* **First visit**: the page and form appear at once, and the CAD kernel loads
  behind a progress bar (about 60 MB download, then 10 to 20 s to start).
  The browser caches the files, so later visits skip the download. The bar
  covers the download by bytes and the start-up steps by how long they took
  on this browser last time.
* **Progress while building**: builds longer than a moment show a bar over
  the viewer. OpenCascade cannot report progress, so the builders report
  milestones (`progress.py`: model, thread with n turns, retries, preview)
  and the page estimates the time from the thread turn count, calibrated to
  this browser's speed on earlier builds.
* **Builds** run about 3 to 5 times slower than native: most parts take well
  under a second, modeled threads a few seconds, and the longest modeled
  fine-pitch bolts up to a couple of minutes. A build cannot be interrupted,
  but form changes made during a build are merged, so only the last one is
  built next.
* Desktop browsers work well. Phones may struggle with the memory and download.

## How it works

* **Geometry**: [build123d](https://github.com/gumyr/build123d) on the
  OpenCascade kernel, so the STEP files hold exact B-rep geometry (cylinders,
  cones, planes and helical B-spline thread faces), not meshes.
* **In the browser**: `static/worker.js` is a Web Worker that loads
  [Pyodide](https://pyodide.org) (CPython in WebAssembly), the
  [OCP.wasm](https://github.com/yeicor/OCP.wasm) build of OpenCascade,
  build123d and this package, then calls `standardparts.web` for the part
  info, the glTF preview and the STEP file. The same Python code runs natively
  in the tests.
* **Page**: `static/` holds the page with a three.js preview. three.js is
  vendored under `static/vendor/`, so no CDN is needed. The form is generated
  from `catalog.json`, which the build writes from each standard's parameter
  schema, so it appears before the kernel has loaded.
* **Standard picker**: a searchable grid of line drawings, one per standard
  (`/` opens it). The build draws them natively as hidden-line SVGs of each
  standard's default part (`thumbs/<id>.svg`, about 80 kB for all of them),
  so they show before the kernel has loaded. The viewer shows the drawing
  until the 3D preview of a newly chosen standard is ready.
* **Build** (`src/standardparts/site.py`): copies `static/`, unpacks the
  Pyodide runtime, downloads the pinned wheels and writes this package as a
  wheel whose name carries a content hash. Two trims keep the download down:
  scikit-learn, IPython and SymPy are left out (build123d imports two of them
  at start-up, so `_stubs.py` provides placeholders), and the 90 MB of texture
  images in threejs-materials are stripped.
* **Pinned versions**: `wasm/runtime.json` (Pyodide) and
  `wasm/pyodide-lock.json` (every wheel with its sha256). build123d in
  `pyproject.toml` is pinned to the same version. To upgrade, change both,
  then run `uv run --with playwright python scripts/update_wasm_lock.py`.

OpenCascade is LGPL-2.1; its WebAssembly build is served unmodified as a
separate file (`pyodide/cadquery_ocp_novtk_ocp_wasm-*.whl`).

## ISO 4762 model

* Z is the screw axis. The underside of the head is at z = 0, the head goes
  up to z = k and the shank down to z = -l.
* Nominal sizes are used: dk max (plain head), k max, ds = d, socket s nom
  to depth t min with a 118° drill point. The model also has the underhead
  fillet r min, the top-edge chamfer v, the bearing-face chamfer to dw and an
  ISO 4753 chamfered point.
* Threaded up to the head, or partially threaded with b of thread, following
  the ls/lg values in Table 1.
* Thread modes:
  * **Simplified** (default): the shank is a plain cylinder at d, with the
    threaded length as its own face so CAD tools can attach a cosmetic thread.
    This is small (tens of kB) and is what most part libraries ship.
  * **Modeled**: a right-hand helical thread with the ISO 68-1 basic profile
    (flat root at d1) and a 2P runout. Files are roughly 0.4 to 1.7 MB.

### ISO 4762 data sources

`src/standardparts/standards/iso4762_data.py` holds the dimension table.
M1.6 to M12 come from ISO 4762:2004 Table 1. M14 to M64 come from published
tables (fasten.it, omdl) and were not checked against the standard itself. r min and dw min for M14 to M64 come from secondary
tables only; they shape only the small underhead fillet and bearing chamfer.
The rule that decides when a screw is threaded to the head reproduces Table 1
exactly for M1.6 to M12 (this is tested) and is applied to the larger sizes too.

## DIN 471 model

* The ring lies flat in the XY plane with its faces at z = 0 and z = s, its
  centre on the origin and the opening towards +Y.
* **Installed**: the inner edge sits on the groove diameter d2, so the ring
  drops straight onto a shaft modeled along Z.
* **Free**: the ring as supplied, inner diameter d3.
* The two states are one consistent ring. The tapered body opens from d3 to
  d2 with its middle fibre keeping its length, and the lugs move as rigid
  pieces, so the lug gap grows on installation. The model's gaps for both
  states are listed in the dimension table.
* DIN 471 fixes d3, s, a, b and d5 but leaves the lug outline to the
  manufacturer. The model uses typical proportions: the section tapers from b
  to 0.6 b at the lugs, and the lugs are round with the plier holes centred.
  Tests check that every installed ring stays inside the clearance diameter
  d4. For d1 ≥ 12 the free-state mass is within 20% of the table weight
  (mostly within 5%). Smaller rings model heavier than the table because their
  lugs dominate.

### DIN 471 data sources

`src/standardparts/standards/din471_data.py` comes from the DIN 471 table
shipped with bd_warehouse (Apache 2.0, see `THIRD_PARTY_NOTICES.md`), cross-checked against fasten.it's DIN 471 table.
One error was corrected: d1 = 48 has s = 1.75, not 2. A test checks that the
groove width m matches s on every row.

## Hand tools (ISO 2936, ISO 2351-3, ISO 2725-1)

Tool standards fix the interfaces (the hexagon that goes into the screw,
the drive end, the drive square) and limits for the rest; the shape between
them is the manufacturer's choice. The models keep every specified
dimension and use simple, documented choices elsewhere. Each part's notes
list the choices it uses.

* **ISO 2936 hex keys**: complete. Table 1 gives s, e, l1 (three series)
  and l2; Figure 1 gives the bend radius (r ≥ s, ≥ 1.5 mm), the flats in
  the bend plane and the largest end chamfer. The model sweeps the section
  (s max, corners at e max) along the centreline, with the smallest bend
  radius allowed and half the largest end chamfer.
* **ISO 2351-3 bits**: the tip is ISO 2936 (s, e) with length l2 min; the
  drive end is ISO 1173 form A, C, E or G (`standards/drive_ends.py`):
  hexagon or cylinder, retaining groove, end chamfer. Between them the model
  tapers the shank at 30° to the axis.
* **ISO 2725-1 sockets**: d1, d2, l, t min and d3 min from Tables 1–3, the
  opening at nominal s (the ISO 691 tolerance is not reproduced), a 120°
  mouth countersink (115–150° allowed), and an ISO 1174-1 female square
  (`standards/driving_squares.py`) with ball recesses (type C) or a plunger
  hole (type D).

Z is the tool axis everywhere, and the end that engages the screw or nut is
at z = 0.

### Hand tool data sources

The data modules name the edition of every table and any value that was
derived or corrected:

* ISO 2936:2014 Table 1, checked against its e max / e min formulas.
* ISO 1173:2001 Tables 1–7 (French edition) and ISO 1174-1:2011 Tables 1–2.
* ISO 2351-3:2002 Table 1. The 2014 edition is current; its Table 1 was not
  checked, and its foreword lists changes to the proof torques only.
* ISO 2725-1:2017 Tables 1–3. Drives 20 and 25 (Tables 4 and 5 of the 2017
  edition) were not checked, and the 2007 edition derives t and d3
  differently, so they are left out. One misprint is corrected: d3 = 5.8 for
  s = 9 on the 12.5 drive becomes 6.3 (1.05 × Dmax, as in Tables 1 and 2).
* The designation formats come from the 2007 and 1995 editions' clauses.
  The M / L suffixes of long and extra-long hex keys come from a secondary
  summary and were not checked against the standard's text.

## Adding a standard

1. Add a module under `src/standardparts/standards/` with a subclass of
   `Standard` (`base.py`). It defines the parameters, validation, designation,
   dimension table and a `build()` that returns a build123d `Part`.
2. Register it in `STANDARDS` in `standards/__init__.py`.

The UI picks it up automatically after the next build. Shared helpers:

* `geometry.py`: revolved profiles, ISO 68-1 thread data and helical ridges,
  hexagon sockets, chamfered hex bodies.
* `screws.py`: threaded shanks with a caller-supplied head
  (`threaded_screw`), headless threaded parts (`threaded_rod`), checked
  socket cuts.
* `nuts.py`: internal threads.
* `drives.py`: cross recess (H, Z) and hexalobular cutters, checked cuts.
* `tooling.py`: hexagon sections with turned corners, and revolved cutters
  for chamfers, tapers and grooves (used by the hand tools).

OpenCascade booleans against helical threads occasionally fail silently
(wrong volume or a dropped solid, no error). The shared builders check the
volume after every thread fuse and retry at another thread start angle, so a
part either builds correctly or raises. Keep that pattern for new parts, and
avoid booleans between coincident faces.

## Standards, data and licences

Copyright 2026 KLTMS. The code is licensed under the
[Apache License 2.0](LICENSE).

This project is not affiliated with or endorsed by ISO, DIN or any national
standards body, and it does not reproduce the text or figures of any
standard. The data modules hold the dimensions the standards specify, each
citing the standard, edition and table, plus the published reference tables
it was checked against. The models add documented modelling choices where a
standard leaves the shape to the manufacturer. Check critical dimensions
against the official standard. Everything is provided as is, without
warranty.

Data taken from other open-source projects (bd_warehouse, omdl) and the
software the site ships (three.js, Pyodide, OpenCascade, build123d and its
dependencies) are credited in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md),
with licence texts in [`LICENSES/`](LICENSES/). The build copies both into
the site.

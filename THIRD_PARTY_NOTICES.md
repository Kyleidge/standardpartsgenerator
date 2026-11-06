# Third-party notices

## Dimension data

The dimension tables in `src/standardparts/standards/*_data.py` give values
specified by the ISO and DIN standards they name. This project is not
affiliated with or endorsed by ISO, DIN or any national standards body, and
it does not reproduce the text or figures of any standard. Each data module's
docstring names the standard, the edition and the published reference tables
the values were checked against.

Two modules include data taken from open-source projects:

### bd_warehouse

`din471_data.py` and `din472_data.py` (DIN 471 / DIN 472 retaining ring
tables) are based on the retaining ring tables distributed with
[bd_warehouse](https://github.com/gumyr/bd_warehouse).

    Copyright Gumyr
    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at
        http://www.apache.org/licenses/LICENSE-2.0
    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

Changes: the tables were converted to Python, cross-checked against other
published tables and corrected where those agreed on a different value. The
module docstrings list every correction. Full licence text:
[`LICENSES/Apache-2.0.txt`](LICENSES/Apache-2.0.txt).

### omdl

The M14 to M64 rows of `iso4762_data.py` (ISO 4762 socket head cap screws)
agree with the ISO 4762 fastener database of
[omdl](https://github.com/royasutton/omdl) (Roy Allen Sutton), an OpenSCAD
mechanical design library licensed under the GNU Lesser General Public
License, version 2.1 or later, as well as with fasten.it's published table.
Full licence text: [`LICENSES/LGPL-2.1.txt`](LICENSES/LGPL-2.1.txt).

## Software shipped with the site

### three.js

`src/standardparts/static/vendor/` holds three.js and four of its add-ons
(OrbitControls, GLTFLoader, RoomEnvironment, BufferGeometryUtils), unmodified.
Copyright © 2010-2024 three.js authors, MIT licence: see
[`src/standardparts/static/vendor/three.LICENSE`](src/standardparts/static/vendor/three.LICENSE).

### The in-browser Python runtime

`uv run standardparts build` downloads the following and copies it into
`dist/pyodide/`. Each one is distributed under its own licence, which is
included in its package (`*.dist-info/` inside each wheel):

* [Pyodide](https://pyodide.org) runtime (Mozilla Public License 2.0),
  unmodified.
* OpenCascade from [OCP.wasm](https://github.com/yeicor/OCP.wasm)
  (`cadquery_ocp_novtk_ocp_wasm`; OpenCascade is LGPL-2.1 with the OCCT
  exception), unmodified and served as a separate file.
* [build123d](https://github.com/gumyr/build123d) (Apache-2.0) and its
  dependencies as pinned in `wasm/pyodide-lock.json`: NumPy, SciPy, Pillow,
  ezdxf, fontTools, requests and others, unmodified.
* `threejs-materials` (Apache-2.0), with its bundled texture images removed
  (`SLIMMED` in `src/standardparts/site.py`); nothing else is changed.

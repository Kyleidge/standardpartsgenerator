import * as THREE from "three";
import { OrbitControls } from "./vendor/OrbitControls.js";
import { GLTFLoader } from "./vendor/GLTFLoader.js";
import { RoomEnvironment } from "./vendor/RoomEnvironment.js";

const $ = (id) => document.getElementById(id);
const fmt = (x) => (typeof x === "number" ? String(+x.toFixed(3)) : x);

// ---------------------------------------------------------------- viewer --

const viewer = (() => {
  const el = $("viewer");
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setClearColor(0xeef0f3);
  el.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

  const camera = new THREE.PerspectiveCamera(35, 1, 0.01, 10000);
  camera.up.set(0, 0, 1);
  camera.position.set(1, -1.6, 0.9);

  const key = new THREE.DirectionalLight(0xffffff, 1.2);
  key.position.set(1, -2, 3);
  scene.add(key, new THREE.AmbientLight(0xffffff, 0.25));

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;

  const material = new THREE.MeshStandardMaterial({
    color: 0xa3a9b1,
    metalness: 0.65,
    roughness: 0.32,
    polygonOffset: true,
    polygonOffsetFactor: 1,
    polygonOffsetUnits: 1,
  });
  const plastics = new Map();
  function plasticMaterial(color) {
    const key = color.getHexString();
    if (!plastics.has(key)) {
      plastics.set(key, new THREE.MeshStandardMaterial({
        color: color.clone(),
        metalness: 0,
        roughness: 0.55,
        polygonOffset: true,
        polygonOffsetFactor: 1,
        polygonOffsetUnits: 1,
      }));
    }
    return plastics.get(key);
  }
  const edgeMaterial = new THREE.LineBasicMaterial({ color: 0x1f2630, transparent: true, opacity: 0.85 });

  let group = null;
  let showEdges = true;

  function resize() {
    const { clientWidth: w, clientHeight: h } = el;
    if (!w || !h) return;
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(el);
  resize();

  function fit() {
    if (!group) return;
    const sphere = new THREE.Box3().setFromObject(group).getBoundingSphere(new THREE.Sphere());
    const dir = camera.position.clone().sub(controls.target).normalize();
    const dist = sphere.radius / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2)) * 1.1;
    controls.target.copy(sphere.center);
    camera.position.copy(sphere.center).addScaledVector(dir, dist);
    camera.near = dist / 100;
    camera.far = dist * 100;
    camera.updateProjectionMatrix();
    controls.update();
  }

  // The preview is binary glTF from OpenCascade: one primitive per CAD
  // face with exact surface normals, so face boundaries are the B-rep edges.
  async function show(arrayBuffer, refit) {
    const gltf = await new GLTFLoader().parseAsync(arrayBuffer, "");
    const root = gltf.scene;
    root.rotation.x = Math.PI / 2; // glTF is Y-up, the parts are modeled Z-up
    const edges = [];
    root.traverse((o) => {
      if (!o.isMesh) return;
      // Steel parts share the metal material; other colours from the model
      // (e.g. a nylon insert) keep their colour on a non-metallic finish.
      const c = o.material.color;
      const grey = c && Math.abs(c.r - c.g) < 0.03 && Math.abs(c.g - c.b) < 0.05;
      const own = c && !grey ? plasticMaterial(c) : material;
      o.material.dispose();
      o.material = own;
      const line = new THREE.LineSegments(new THREE.EdgesGeometry(o.geometry, 30), edgeMaterial);
      line.visible = showEdges;
      edges.push(line);
      o.add(line);
    });

    if (group) {
      scene.remove(group);
      group.traverse((o) => o.geometry && o.geometry.dispose());
    }
    group = root;
    group.userData.edges = edges;
    scene.add(group);
    group.updateMatrixWorld(true);
    if (refit) fit();
  }

  function toggleEdges() {
    showEdges = !showEdges;
    if (group) for (const e of group.userData.edges) e.visible = showEdges;
    return showEdges;
  }

  renderer.setAnimationLoop(() => {
    controls.update();
    renderer.render(scene, camera);
  });

  return { show, fit, toggleEdges };
})();

$("fit").addEventListener("click", () => viewer.fit());
$("edges").addEventListener("click", (e) => {
  e.currentTarget.setAttribute("aria-pressed", String(viewer.toggleEdges()));
});

// -------------------------------------------------------------- progress --
// Neither start-up steps nor OpenCascade operations can say how far along
// they are, so the bars move against time estimates between real
// milestones. A segment [from, to] fills linearly up to 80% of the expected
// time, then slows down and approaches its end without reaching it, so a
// step that runs long never looks finished or stuck. The bar never moves
// backwards.

function ease(x) {
  return x < 0.8 ? x : 0.8 + 0.2 * (1 - Math.exp(-(x - 0.8) / 0.2));
}

function progressBar(bar) {
  let from = 0, to = 0, expected = 1, start = 0, shown = 0, raf = 0;
  function frame() {
    const t = (performance.now() - start) / 1000;
    const f = ease(t / expected);
    shown = Math.max(shown, from + (to - from) * f);
    bar.value = shown;
    raf = shown < to - 1e-4 ? requestAnimationFrame(frame) : 0;
  }
  const kick = () => { if (!raf) raf = requestAnimationFrame(frame); };
  return {
    get value() { return shown; },
    // Move towards `end`, expected to take `seconds`, from where the bar is now.
    toward(end, seconds) {
      from = shown;
      to = Math.max(end, shown);
      expected = Math.max(seconds, 0.05);
      start = performance.now();
      kick();
    },
    set(value) {
      shown = Math.max(shown, value);
      from = to = shown;
      bar.value = shown;
    },
    stop() {
      cancelAnimationFrame(raf);
      raf = 0;
    },
    reset() {
      this.stop();
      shown = from = to = 0;
      bar.value = 0;
    },
  };
}

const store = {
  get(key, fallback) {
    try { return JSON.parse(localStorage.getItem(`spg.${key}`)) ?? fallback; } catch { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem(`spg.${key}`, JSON.stringify(value)); } catch {}
  },
};

// Start-up: the download fills the first part of the bar by bytes, then the
// steps worker.js reports share the rest by how long each took the last
// time (or a typical time on the first visit).
const DOWNLOAD_SHARE = 0.4;
const STARTUP_STEPS = {
  python: 3.5,
  "packages-numeric": 4.0,
  "packages-occt": 6.5,
  "packages-rest": 0.5,
  "import-numeric": 2.0,
  "import-occt": 4.5,
  "import-build123d": 2.8,
  "import-standards": 0.3,
};

const loading = (() => {
  const box = $("loading");
  const text = $("loading-text");
  const bar = progressBar($("loading-bar"));
  const times = { ...STARTUP_STEPS, ...store.get("startup", {}) };
  const keys = Object.keys(STARTUP_STEPS);
  const total = keys.reduce((sum, k) => sum + times[k], 0);
  const measured = {};
  let current = null;
  let currentStart = 0;

  function closeStep() {
    if (current) measured[current] = (performance.now() - currentStart) / 1000;
  }
  function stepRange(key) {
    let before = 0;
    for (const k of keys) {
      if (k === key) break;
      before += times[k];
    }
    const span = 1 - DOWNLOAD_SHARE;
    return [DOWNLOAD_SHARE + (span * before) / total, DOWNLOAD_SHARE + (span * (before + times[key])) / total];
  }
  const mb = (x) => (x / 1e6).toFixed(0);

  return {
    download(got, totalBytes) {
      box.hidden = false;
      text.textContent = `Downloading the CAD kernel… ${mb(got)} of ${mb(totalBytes)} MB`;
      bar.set(DOWNLOAD_SHARE * (totalBytes ? got / totalBytes : 1));
    },
    phase(key, message) {
      box.hidden = false;
      closeStep();
      current = key;
      currentStart = performance.now();
      text.textContent = message;
      if (!(key in times)) return; // unknown step: keep the bar where it is
      const [start, end] = stepRange(key);
      bar.set(start);
      bar.toward(end, times[key]);
    },
    done() {
      closeStep();
      current = null;
      // Remember this browser's timings for the next visit.
      if (keys.every((k) => k in measured)) store.set("startup", measured);
      bar.set(1);
      bar.stop();
      box.hidden = true;
    },
    fail(message) {
      box.hidden = false;
      box.classList.add("failed");
      text.textContent = `The CAD kernel failed to load: ${message}`;
      $("loading-bar").hidden = true;
    },
  };
})();

// Part builds: the bar over the viewer. The time model is native seconds
// (0.25 s plus 0.04 s per thread turn, from measurements) times how much
// slower this browser has been so far, kept across visits.
const BUILD_BASE = 0.25;
const BUILD_PER_TURN = 0.04;
const MODEL_SHARE = 0.9;

const building = (() => {
  const box = $("viewer-status");
  const text = $("viewer-status-text");
  const bar = progressBar($("build-bar"));
  let speed = store.get("speed", 4.5);
  let job = null;
  let showTimer = 0;

  const nativeEstimate = (j) => (BUILD_BASE + BUILD_PER_TURN * j.turns) * (1 + 0.6 * j.retries);
  const elapsed = (j) => (performance.now() - j.start) / 1000;
  function aimModel(j) {
    const remaining = Math.max(speed * nativeEstimate(j) - elapsed(j), 0.2);
    bar.toward(MODEL_SHARE, remaining);
  }

  return {
    // A preview request was sent; the bar shows up if it takes a moment.
    begin() {
      clearTimeout(showTimer);
      bar.reset();
      job = { start: performance.now(), turns: 0, retries: 0, model: null };
      text.textContent = "Generating…";
      showTimer = setTimeout(() => { box.hidden = false; }, 150);
      aimModel(job);
      return job;
    },
    event(j, event, data) {
      if (j !== job) return;
      if (event === "stage" && data.name === "model") {
        j.start = performance.now();
        text.textContent = "Building the model…";
        aimModel(j);
      } else if (event === "thread") {
        j.turns += data.turns;
        text.textContent = `Building the thread (${j.turns} turns)…`;
        aimModel(j);
      } else if (event === "retry") {
        j.retries += 1;
        text.textContent = `Building the thread (${j.turns} turns, another attempt)…`;
        aimModel(j);
      } else if (event === "stage" && data.name === "preview") {
        j.model = elapsed(j);
        text.textContent = "Preparing the preview…";
        bar.set(MODEL_SHARE);
        bar.toward(1, speed * 0.05 + 0.1);
      }
    },
    end(j) {
      if (j !== job) return;
      clearTimeout(showTimer);
      bar.stop();
      box.hidden = true;
      job = null;
      // Learn how fast this browser is, from builds long enough to measure.
      if (j.model !== null && j.model > 0.3) {
        const observed = j.model / nativeEstimate(j);
        speed = Math.min(Math.max(0.7 * speed + 0.3 * observed, 0.5), 30);
        store.set("speed", speed);
      }
    },
  };
})();

// ---------------------------------------------------------------- engine --
// All geometry runs in worker.js (Python + OpenCascade in WebAssembly).

class Superseded extends Error {}

const engine = (() => {
  let worker = null;
  let nextId = 1;
  const calls = new Map();
  let readyResolve, readyReject;
  const ready = new Promise((res, rej) => { readyResolve = res; readyReject = rej; });
  ready.catch(() => {});

  function start(build) {
    worker = new Worker(`worker.js?build=${encodeURIComponent(build)}`, { type: "module" });
    worker.onmessage = ({ data: m }) => {
      if (m.type === "download") return loading.download(m.got, m.total);
      if (m.type === "phase") return loading.phase(m.key, m.text);
      if (m.type === "ready") { loading.done(); return readyResolve(); }
      if (m.type === "failed") {
        loading.fail(m.error);
        return readyReject(new Error(`The CAD kernel failed to load: ${m.error}`));
      }
      const call = calls.get(m.id);
      if (!call) return;
      if (m.type === "progress") return call.onProgress?.(m.event, m.data);
      calls.delete(m.id);
      if (m.ok) call.resolve(m);
      else call.reject(Object.assign(new Error(m.error), { invalid: !!m.invalid }));
    };
    worker.onerror = (e) => {
      const err = new Error(e.message || "The CAD worker stopped.");
      loading.fail(err.message);
      readyReject(err);
      for (const call of calls.values()) call.reject(err);
      calls.clear();
    };
  }

  function call(op, standardId, params, onProgress) {
    return new Promise((resolve, reject) => {
      const id = nextId++;
      calls.set(id, { resolve, reject, onProgress });
      worker.postMessage({ id, op, standard: standardId, params });
    });
  }

  // Requests on the same channel replace each other while they wait, so a
  // burst of form changes only builds the last one. `onStart` runs when the
  // request is actually sent.
  const channels = new Map();
  function latest(channel, op, standardId, params, { onStart, onProgress } = {}) {
    let ch = channels.get(channel);
    if (!ch) channels.set(channel, (ch = { busy: false, queued: null }));
    return new Promise((resolve, reject) => {
      if (ch.queued) ch.queued.reject(new Superseded());
      ch.queued = { op, standardId, params, onStart, onProgress, resolve, reject };
      pump(ch);
    });
  }
  async function pump(ch) {
    if (ch.busy || !ch.queued) return;
    const job = ch.queued;
    ch.queued = null;
    ch.busy = true;
    try {
      job.onStart?.();
      job.resolve(await call(job.op, job.standardId, job.params, job.onProgress));
    } catch (err) { job.reject(err); }
    finally { ch.busy = false; pump(ch); }
  }

  return { start, ready, call, latest };
})();

// ------------------------------------------------------------------ form --

let standard = null; // schema of the selected standard
let catalog = null;
let values = {};
let requestSeq = 0;
let lastFitKey = null;
let shownStandard = null; // standard of the model in the viewer
let currentInfo = null;

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: ${res.status} ${res.statusText}`);
  return res.json();
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (v !== undefined && v !== null) node.setAttribute(k, v);
  }
  node.append(...children);
  return node;
}

function renderForm() {
  const form = $("params");
  form.replaceChildren();
  for (const p of standard.parameters) {
    const field = el("label", { class: "field" }, el("span", { class: "field-label" }, p.label));
    if (p.kind === "select") {
      const select = el("select", { name: p.name });
      for (const o of p.options) select.append(el("option", { value: o.value }, o.label));
      select.value = values[p.name];
      select.addEventListener("change", () => {
        values[p.name] = select.value;
        // Dependent fields (e.g. lengths per size) need new options.
        for (const dep of standard.parameters) {
          if (dep.depends_on === p.name) coerceLength(dep);
        }
        renderForm();
        update();
      });
      field.append(select);
    } else if (p.kind === "length") {
      field.append(lengthControl(p));
    }
    if (p.help) field.append(el("span", { class: "field-help" }, p.help));
    form.append(field);
  }
}

function lengthOptions(p) {
  const key = values[p.depends_on];
  return { preferred: p.preferred[key] || [], limits: p.limits[key] || [0, Infinity] };
}

// Keep the length valid after the size changes: snap to the nearest
// preferred length when the current one falls outside the new range.
function coerceLength(p) {
  const { preferred, limits } = lengthOptions(p);
  const l = Number(values[p.name]);
  if (l >= limits[0] && l <= limits[1]) return;
  values[p.name] = preferred.reduce((best, x) => (Math.abs(x - l) < Math.abs(best - l) ? x : best), preferred[0]);
}

function lengthControl(p) {
  const { preferred, limits } = lengthOptions(p);
  const current = Number(values[p.name]);
  const isCustom = !preferred.includes(current);

  const select = el("select", { name: p.name });
  for (const l of preferred) select.append(el("option", { value: l }, `${fmt(l)} ${p.unit || ""}`));
  select.append(el("option", { value: "custom" }, "Custom…"));
  select.value = isCustom ? "custom" : String(current);

  const input = el("input", {
    type: "number",
    min: limits[0],
    max: limits[1],
    step: "0.5",
    value: current,
    "aria-label": `${p.label} (custom)`,
  });
  input.hidden = !isCustom;

  select.addEventListener("change", () => {
    if (select.value === "custom") {
      input.hidden = false;
      input.focus();
      return;
    }
    input.hidden = true;
    input.value = select.value;
    values[p.name] = Number(select.value);
    update();
  });

  let timer;
  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      if (input.value === "") return;
      values[p.name] = Number(input.value);
      update();
    }, 350);
  });

  const hint = el("span", { class: "field-help" }, `Standard range ${fmt(limits[0])}–${fmt(limits[1])} mm`);
  return el("div", {}, el("div", { class: "field-row" }, select, input), hint);
}

// ---------------------------------------------------------------- picker --
// Standards are chosen from a searchable grid of line drawings
// (thumbs/<id>.svg, drawn at build time by site.py), so visitors can see
// what each part looks like before the CAD kernel has loaded.

// Everyday names the catalog text does not use, for the search.
const ALIASES = {
  iso4762: "allen bolt socket cap screw shcs",
  din7984: "allen low head socket cap",
  iso4014: "hex bolt",
  iso4017: "hex bolt fully threaded",
  iso8765: "hex bolt fine",
  iso8676: "hex bolt fine fully threaded",
  iso4162: "flange bolt",
  iso10642: "allen countersunk flat head csk",
  iso7380: "allen button head bhcs",
  iso7379: "shoulder bolt",
  iso7045: "phillips pozidriv pozi cross head",
  iso7046: "phillips pozidriv pozi cross countersunk csk",
  iso14581: "torx countersunk csk",
  iso4026: "grub screw allen",
  iso4027: "grub screw allen",
  iso4028: "grub screw allen",
  iso4029: "grub screw allen",
  iso7040: "lock nut locknut nylon insert",
  iso10511: "lock nut locknut nylon insert",
  din1587: "acorn cap nut",
  din508: "t-nut tnut",
  iso7089: "flat washer",
  iso7090: "flat washer",
  iso7092: "flat washer",
  iso7093: "flat washer fender",
  din471: "circlip snap ring external seeger",
  din472: "circlip snap ring internal seeger",
  din6799: "e-clip eclip circlip",
  iso8734: "dowel",
  iso2338: "dowel",
  iso1234: "cotter",
  din6885: "keyway feather key",
  iso3601: "oring o-ring seal gasket as568",
  iso15: "ball bearing 6000 6200 6300 2rs 2z",
  din580: "eye bolt lifting ring",
  iso2936: "allen key hex key wrench",
  "iso2351-3": "hex bit allen bit",
  "iso2725-1": "socket wrench ratchet",
};

const thumbUrl = (id) => `thumbs/${encodeURIComponent(id)}.svg?v=${encodeURIComponent(catalog.build)}`;
const squash = (text) => text.toLowerCase().replace(/[\s\-–_.,/()]+/g, "");
const shortLabel = (label) => label.replace(/\s*\(.*$/, "");

// "Thread size: M1.6 x 0.35 … M64 x 6 (20 sizes)"-style lines for the detail pane.
function describeParameter(p) {
  if (p.kind === "length") return "preferred lengths per size, or custom";
  const labels = p.options.map((o) => shortLabel(o.label));
  if (labels.length <= 4) return labels.join(", ");
  return `${labels[0]} … ${labels.at(-1)} (${labels.length})`;
}

const picker = (() => {
  const dialog = $("picker");
  const query = $("picker-query");
  const results = $("picker-results");
  const cats = $("picker-cats");
  const detail = $("picker-detail");
  const count = $("picker-count");
  const finePointer = matchMedia("(pointer: fine)");
  let entries = [];
  let category = null; // null: every category
  let currentId = null;
  let onPick = () => {};

  // Lower is better; null when a word does not match at all.
  function score(entry, words) {
    let total = 0;
    for (const word of words) {
      const w = squash(word);
      if (!w) continue;
      if (entry.title.includes(w)) total += 0;
      else if (entry.words.some((x) => x.startsWith(word))) total += 1;
      else if (entry.text.includes(word)) total += 2;
      else if (entry.flat.includes(w)) total += 3;
      else return null;
    }
    return total;
  }

  function card(s, { showCategory = false } = {}) {
    const button = el("button", { type: "button", class: "pick", "data-id": s.id },
      el("span", { class: "pick-thumb" }, el("img", { src: thumbUrl(s.id), alt: "", loading: "lazy", decoding: "async" })),
      el("span", { class: "pick-title" }, s.title),
      el("span", { class: "pick-summary" }, s.summary),
    );
    if (showCategory) button.prepend(el("span", { class: "pick-cat" }, s.category));
    if (s.id === currentId) button.setAttribute("aria-current", "true");
    return button;
  }

  const grid = (cards) => el("div", { class: "pick-grid" }, ...cards);
  const section = (title, cards) => el("section", { class: "pick-group" }, el("h3", {}, title), grid(cards));

  function renderCats() {
    const counts = new Map();
    for (const { s } of entries) counts.set(s.category, (counts.get(s.category) || 0) + 1);
    const chip = (label, value, n) => el("button", {
      type: "button", class: "chip", "data-category": value ?? "", "aria-pressed": String(category === value),
    }, label, el("span", { class: "chip-count" }, String(n)));
    cats.replaceChildren(chip("All", null, entries.length), ...[...counts].map(([c, n]) => chip(c, c, n)));
  }

  function render() {
    const text = query.value.trim().toLowerCase();
    const words = text.split(/\s+/).filter(Boolean);
    const inCategory = entries.filter((e) => !category || e.s.category === category);
    const blocks = [];
    let shown = [];

    if (words.length) {
      shown = inCategory
        .map((e) => [score(e, words), e])
        .filter(([sc]) => sc !== null)
        .sort((a, b) => a[0] - b[0]) // stable: ties keep the catalog order
        .map(([, e]) => e);
      if (shown.length) blocks.push(grid(shown.map((e) => card(e.s, { showCategory: true }))));
    } else {
      shown = inCategory;
      const recent = store.get("recent", []).filter((id) => entries.some((e) => e.s.id === id));
      if (!category && recent.length > 1) {
        blocks.push(section("Recent", recent.map((id) => card(entries.find((e) => e.s.id === id).s))));
      }
      const groups = new Map();
      for (const e of shown) {
        if (!groups.has(e.s.category)) groups.set(e.s.category, []);
        groups.get(e.s.category).push(card(e.s));
      }
      for (const [c, cards] of groups) blocks.push(section(c, cards));
    }

    if (!shown.length) {
      const empty = el("div", { class: "pick-empty" }, el("p", {}, `No standard matches “${query.value.trim()}”`));
      const elsewhere = category && entries.some((e) => score(e, words) !== null);
      const retry = el("button", { type: "button", class: "chip" }, elsewhere ? "Search all categories" : "Clear search");
      retry.addEventListener("click", () => {
        if (elsewhere) category = null;
        else query.value = "";
        renderCats();
        render();
        query.focus();
      });
      empty.append(retry);
      blocks.push(empty);
    }

    results.replaceChildren(...blocks);
    results.scrollTop = 0;
    count.textContent = words.length || category ? `${shown.length} of ${entries.length}` : `${entries.length} standards`;
    showDetail(words.length && shown.length ? shown[0].s.id : currentId);
  }

  function showDetail(id) {
    const s = entries.find((e) => e.s.id === id)?.s;
    if (!s || detail.dataset.id === id) return;
    detail.dataset.id = id;
    const isCurrent = id === currentId;
    const use = el("button", { type: "button", class: "button", ...(isCurrent ? { "aria-disabled": "true" } : {}) },
      isCurrent ? "Current standard" : `Use ${s.title}`);
    use.addEventListener("click", () => { if (!isCurrent) pick(id); });
    detail.replaceChildren(
      el("div", { class: "detail-thumb" }, el("img", { src: thumbUrl(id), alt: `Line drawing of ${s.title}` })),
      el("div", { class: "detail-cat" }, s.category),
      el("h3", {}, s.title),
      el("p", {}, s.summary),
      el("dl", {}, ...s.parameters.flatMap((p) => [el("dt", {}, p.label), el("dd", {}, describeParameter(p))])),
      use,
    );
  }

  function pick(id) {
    dialog.close();
    if (id !== currentId) onPick(id);
  }

  // The card in direction `key` from `from`, by on-screen position, so it
  // works across group headings and any number of columns.
  function neighbour(from, key) {
    const cards = [...results.querySelectorAll(".pick")];
    const i = cards.indexOf(from);
    if (key === "ArrowLeft") return cards[i - 1];
    if (key === "ArrowRight") return cards[i + 1];
    if (key === "Home") return cards[0];
    if (key === "End") return cards.at(-1);
    const r = from.getBoundingClientRect();
    const cx = r.left + r.width / 2;
    const sign = key === "ArrowDown" ? 1 : -1;
    let best = null, bestDy = Infinity, bestDx = Infinity;
    for (const c of cards) {
      const cr = c.getBoundingClientRect();
      const dy = sign * (cr.top - r.top);
      if (dy < 4) continue;
      const dx = Math.abs(cr.left + cr.width / 2 - cx);
      if (dy < bestDy - 4 || (Math.abs(dy - bestDy) <= 4 && dx < bestDx)) {
        best = c; bestDy = dy; bestDx = dx;
      }
    }
    return best;
  }

  function focusCard(c) {
    if (!c) return;
    c.focus({ preventScroll: true });
    c.scrollIntoView({ block: "nearest" });
  }

  function init(list, handler) {
    onPick = handler;
    entries = list.map((s) => {
      const text = `${s.title} ${s.summary} ${s.category} ${ALIASES[s.id] || ""}`.toLowerCase();
      return { s, title: squash(s.title), text, words: text.split(/[^a-z0-9.]+/), flat: squash(text) };
    });

    query.addEventListener("input", render);
    query.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        focusCard(results.querySelector(".pick"));
      } else if (e.key === "Enter") {
        e.preventDefault();
        const first = results.querySelector(".pick");
        if (first) pick(first.dataset.id);
      } else if (e.key === "Escape" && query.value) {
        e.preventDefault(); // clear the search first, close on the next Esc
        query.value = "";
        render();
      }
    });

    cats.addEventListener("click", (e) => {
      const chip = e.target.closest(".chip");
      if (!chip) return;
      const value = chip.dataset.category || null;
      category = category === value ? null : value;
      renderCats();
      render();
    });

    results.addEventListener("click", (e) => {
      const c = e.target.closest(".pick");
      if (c) pick(c.dataset.id);
    });
    results.addEventListener("focusin", (e) => {
      const c = e.target.closest(".pick");
      if (c) showDetail(c.dataset.id);
    });
    results.addEventListener("pointerover", (e) => {
      const c = e.target.closest(".pick");
      if (c && e.pointerType === "mouse") showDetail(c.dataset.id);
    });
    results.addEventListener("keydown", (e) => {
      const c = e.target.closest(".pick");
      if (!c) return;
      if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(e.key)) {
        e.preventDefault();
        const next = neighbour(c, e.key);
        if (next) focusCard(next);
        else if (e.key === "ArrowUp" || (e.key === "ArrowLeft" && c === results.querySelector(".pick"))) query.focus();
      } else if (e.key.length === 1 && e.key !== " " && !e.ctrlKey && !e.metaKey && !e.altKey) {
        query.focus(); // typing anywhere searches
      }
    });

    // A click on the backdrop (outside the panel) closes the dialog.
    dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
    $("picker-close").addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => $("standard-button").focus());
  }

  function open() {
    if (dialog.open) return;
    query.value = "";
    category = null;
    delete detail.dataset.id;
    renderCats();
    render();
    dialog.showModal();
    // The last match is the one in its category (the first may be in Recent).
    const current = [...results.querySelectorAll("[aria-current]")].at(-1);
    current?.scrollIntoView({ block: "center" });
    // On touch screens, don't pop up the keyboard until the search is tapped.
    if (finePointer.matches) query.focus();
    else current?.focus({ preventScroll: true });
  }

  return {
    init,
    open,
    set current(id) {
      currentId = id;
      const recent = store.get("recent", []).filter((x) => x !== id);
      store.set("recent", [id, ...recent].slice(0, 8));
    },
  };
})();

// ---------------------------------------------------------------- update --

function query() {
  return new URLSearchParams(Object.entries(values).map(([k, v]) => [k, String(v)])).toString();
}

function showError(message) {
  const box = $("error");
  box.hidden = !message;
  box.textContent = message || "";
  setDownloadEnabled(!message && currentInfo !== null);
}

function setDownloadEnabled(enabled) {
  $("download").setAttribute("aria-disabled", enabled ? "false" : "true");
}

function renderInfo(info) {
  $("designation").textContent = info.designation;
  $("filename").textContent = info.filename;
  $("notes").replaceChildren(...info.notes.map((n) => el("li", {}, n)));
  $("dims").replaceChildren(
    ...info.dimensions
      .filter((d) => d.value !== null)
      .map((d) =>
        el("tr", {},
          el("td", { class: "sym" }, d.symbol),
          el("td", { class: "label" }, d.label),
          el("td", { class: "val" },
            typeof d.value === "number" ? fmt(d.value) + (d.unit && d.unit !== "mm" ? ` ${d.unit}` : "") : d.value),
        ),
      ),
  );
}

async function update() {
  const seq = ++requestSeq;
  const id = standard.id;
  const params = { ...values };
  history.replaceState(null, "", `?standard=${id}&${query()}`);
  currentInfo = null;
  setDownloadEnabled(false);

  try {
    await engine.ready;
    const { meta } = await engine.latest("info", "info", id, params);
    if (seq !== requestSeq) return;
    currentInfo = { standard: id, params, filename: meta.filename };
    showError(null);
    renderInfo(meta);
  } catch (err) {
    if (!(err instanceof Superseded) && seq === requestSeq) showError(err.message);
    return;
  }

  let job = null;
  try {
    const { data } = await engine.latest("preview", "preview", id, params, {
      onStart: () => { job = building.begin(); },
      onProgress: (event, detail) => building.event(job, event, detail),
    });
    if (seq !== requestSeq) return;
    // Refit when the part changes size class, not when only the thread mode changes.
    const fitKey = `${id}:${values.size}:${values.length}`;
    await viewer.show(data, fitKey !== lastFitKey);
    lastFitKey = fitKey;
    shownStandard = id;
    $("viewer-placeholder").hidden = true;
  } catch (err) {
    if (!(err instanceof Superseded) && seq === requestSeq) showError(err.message);
  } finally {
    if (job) building.end(job);
  }
}

async function download(event) {
  event.preventDefault();
  const button = $("download");
  if (!currentInfo || button.getAttribute("aria-disabled") === "true") return;
  const { standard: id, params } = currentInfo;
  const label = button.querySelector("span");
  const text = label.textContent;
  label.textContent = "Preparing STEP…";
  try {
    const { meta, data } = await engine.call("step", id, params);
    const url = URL.createObjectURL(new Blob([data], { type: "application/step" }));
    const a = el("a", { href: url, download: meta.filename });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
  } catch (err) {
    showError(err.message);
  } finally {
    label.textContent = text;
  }
}

async function selectStandard(id, initial = {}) {
  standard = catalog.standards.find((s) => s.id === id);
  picker.current = id;
  $("standard-title").textContent = standard.title;
  $("standard-summary").textContent = standard.summary;
  $("standard-thumb").src = thumbUrl(id);
  // Until this standard's 3D preview is ready, the viewer shows its drawing
  // instead of the previous part.
  const placeholder = $("viewer-placeholder");
  if (shownStandard !== id) {
    placeholder.querySelector("img").src = thumbUrl(id);
    placeholder.hidden = false;
  }
  $("dims-source").textContent = standard.source;
  document.title = `${standard.title} · Standard Parts Generator`;
  values = {};
  for (const p of standard.parameters) values[p.name] = initial[p.name] ?? p.default;
  for (const p of standard.parameters) if (p.kind === "length") values[p.name] = Number(values[p.name]);
  renderForm();
  await update();
}

async function init() {
  catalog = await getJSON("catalog.json");
  engine.start(catalog.build);
  const list = catalog.standards;
  picker.init(list, (id) => selectStandard(id));
  $("standard-button").addEventListener("click", () => picker.open());
  // "/" opens the picker from anywhere outside a text field.
  document.addEventListener("keydown", (e) => {
    if (e.key !== "/" || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.target.closest("input, select, textarea, dialog")) return;
    e.preventDefault();
    picker.open();
  });
  const url = Object.fromEntries(new URLSearchParams(location.search));
  const id = list.some((s) => s.id === url.standard) ? url.standard : list[0].id;
  $("download").addEventListener("click", download);
  await selectStandard(id, url);
}

init().catch((err) => showError(err.message));

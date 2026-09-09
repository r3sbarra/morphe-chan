#!/usr/bin/env python
"""reports/shape3d.py — Interactive 3D neural-shape graph for HTML reports.

Brings the same Three.js 3D graph used by the morphe-chan_web app into the
self-contained HTML reports. Two pieces:

  * ``build_shape3d_data(project_dir)`` — walks a project and produces the
    exact payload the 3D view consumes: per-file enriched vectors + real
    AST data-flow graphs, a merged cross-file graph, and a ``contrib`` map
    (dimension -> contributing files) for the click-to-inspect panel.

  * ``SHAPE3D_JS`` — the client-side Three.js renderer (orbit/pan/zoom,
    animated synapse particles, click-to-inspect, per-file selector). This is
    the same renderer as the web app's ``report.html``.

Three.js is vendored locally (``static/vendor/three.min.js``) so the report
works fully offline, matching how Chart.js is already vendored.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# Same language/extension map + skip dirs as composite_vector.py (kept in sync).
EXT = {
    "python": [".py"], "javascript": [".js", ".mjs", ".cjs"],
    "typescript": [".ts", ".tsx"], "java": [".java"],
    "c": [".c", ".h"], "cpp": [".cpp", ".cc", ".hpp"],
    "csharp": [".cs"], "go": [".go"], "rust": [".rs"],
    "ruby": [".rb"], "php": [".php"], "swift": [".swift"],
    "kotlin": [".kt", ".kts"], "sql": [".sql"], "html": [".html"],
    "css": [".css"], "shell": [".sh"], "json": [".json"],
    "yaml": [".yaml", ".yml"], "markdown": [".md"],
}
SKIP_DIRS = {"node_modules", ".git", "vendor", "dist", "build", "target",
             "__pycache__", ".venv", "venv", "test", "tests", "spec", "specs",
             "examples", "docs", "benchmark", "benchmarks", "third_party",
             "third-party", "external", "deps", "assets", "static", "coverage",
             ".github", "bin", "obj", "out", "migrations"}


def _lang_of(fn: str) -> Optional[str]:
    for lang, exts in EXT.items():
        if any(fn.endswith(e) for e in exts):
            return lang
    return None


def _iter_project_files(root: Path, max_files: int = 500):
    """Yield (rel_path, lang, code) for every scannable source file."""
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            lang = _lang_of(fn)
            if not lang:
                continue
            fpath = Path(dirpath) / fn
            try:
                code = fpath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if not code.strip() or len(code) > 20000:
                continue
            rel = str(fpath.relative_to(root))
            yield rel, lang, code
            count += 1
            if count >= max_files:
                return


def build_shape3d_data(project_dir: str, max_files: int = 500) -> Dict[str, Any]:
    """Build the 3D-graph payload for a project directory.

    Returns a dict shaped exactly like the web app's report ``DATA``:
      {
        "file_count": int,
        "composite": {dim: value},
        "files": [ {path, lang, shape, complexity, enriched, dataflow}, ... ],
        "merged_graph": {functions, file_of, call_edges, data_edges} | None,
        "contrib": {dim: [file, ...]},
      }
    The first ``files`` entry is the synthetic ``__project__`` aggregate view.
    """
    from code_shape.core.enriched_shape import enriched_shape
    from code_shape.core.program_shape import program_signature
    from code_shape.core.dataflow import project_dfg, merge_project_dfg
    from code_shape.core.composite_vector import composite_vector

    root = Path(project_dir)
    files: List[Dict[str, Any]] = []
    file_dfgs: Dict[str, Any] = {}
    composite: Dict[str, float] = {}

    try:
        composite = composite_vector(root, max_files=max_files)
    except Exception:
        composite = {}

    for rel, lang, code in _iter_project_files(root, max_files=max_files):
        vec: Dict[str, float] = {}
        sig: Optional[str] = None
        dfg: Optional[Dict[str, Any]] = None
        try:
            vec = enriched_shape(code, lang)
        except Exception:
            vec = {}
        try:
            sig = program_signature(code)
        except Exception:
            sig = None
        try:
            _p = project_dfg(code, lang)
            file_dfgs[rel] = _p
            dfg = {
                "functions": list(_p.functions.keys()),
                "call_edges": _p.call_edges,
                "data_edges": _p.data_edges,
            }
        except Exception:
            dfg = None
        files.append({
            "path": rel, "lang": lang, "shape": sig,
            "complexity": None, "enriched": vec, "dataflow": dfg,
        })

    # Project-level merged graph (truthful cross-file structure).
    merged_graph: Optional[Dict[str, Any]] = None
    try:
        _merged = merge_project_dfg(file_dfgs)
        merged_graph = {
            "functions": list(_merged.functions.keys()),
            "call_edges": _merged.call_edges,
            "data_edges": _merged.data_edges,
            "file_of": _merged.file_of,
        }
    except Exception:
        merged_graph = None

    # Aggregate per-file enriched dims into a project-level vector (normalized
    # by file count) so the whole repo renders as one neural net.
    agg: Dict[str, float] = {}
    for f in files:
        for k, v in f["enriched"].items():
            if isinstance(v, (int, float)):
                agg[k] = agg.get(k, 0.0) + v
    n = max(len(files), 1)
    agg = {k: round(v / n, 4) for k, v in agg.items()}
    files.insert(0, {
        "path": "__project__", "lang": "project",
        "shape": composite.get("COMPOSITE_SHAPE") or "PROJECT",
        "complexity": None, "enriched": agg, "dataflow": None,
    })

    # Dimension -> contributing files (for the click-to-inspect panel).
    contrib: Dict[str, List[str]] = {}
    for f in files[1:]:
        for k, v in f["enriched"].items():
            if isinstance(v, (int, float)) and v > 0:
                contrib.setdefault(k, []).append(f["path"])
    contrib = {k: v[:8] for k, v in contrib.items()}

    return {
        "file_count": len(files) - 1,
        "composite": composite,
        "files": files,
        "merged_graph": merged_graph,
        "contrib": contrib,
    }


def three_js_inline() -> str:
    """Return a CDN <script> tag for Three.js (keeps reports lean)."""
    return '<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>'


# ── Client-side 3D renderer (same as morphe-chan_web report.html) ─────────
SHAPE3D_JS = r"""
const CAT_COLORS = {
  IN: 0x58a6ff, FLOW: 0xd29922, PRIM: 0xa371f7, EFF: 0xf778ba,
  OUT: 0x3fb950, PROP: 0x58a6ff, VAL: 0xf778ba, TAINT: 0xf85149,
  LANG: 0x58a6ff, FUNC: 0xa371f7, DEPTH: 0x8b96a8
};
const CAT_ORDER = ['IN', 'FLOW', 'PRIM', 'EFF', 'OUT', 'PROP', 'VAL', 'TAINT'];
const CAT_DESC = {
  IN: 'input sources the code reads from', FLOW: 'transform operations values pass through',
  PRIM: 'primitive operations (assign, branch, loop, return…)', EFF: 'efficiency signals (complexity, loops, nesting)',
  OUT: 'output sinks (return, print, file write…)', PROP: 'structural properties',
  VAL: 'value-flow characteristics', TAINT: 'tainted inputs that propagate to outputs',
  LANG: 'language share', FUNC: 'function density', DEPTH: 'nesting depth'
};
const PRIM_SHAPES = {
  ASSIGN: 'box', BRANCH: 'cone', LOOP: 'torus', RETURN: 'sphere', READ: 'cylinder',
  WRITE: 'octahedron', SEARCH: 'icosahedron', FILTER: 'dodecahedron', SORT: 'torusKnot',
  RECURSE: 'tetrahedron', STATE: 'box', AGGREGATE: 'cone', COMPARE: 'cylinder',
  ARITH: 'torus', CONCAT: 'octahedron', CAST: 'icosahedron', SLICE: 'dodecahedron',
  JOIN: 'torusKnot', MAP: 'tetrahedron', SPLIT: 'cone', PARAM: 'sphere', CONSTANT: 'box',
  ENV: 'cylinder', REQUEST: 'octahedron', WEB_GET: 'icosahedron', FILE_READ: 'dodecahedron',
  RETURN: 'sphere', PRINT: 'cone', FILE_WRITE: 'box', WEB_POST: 'torus', EMIT: 'octahedron'
};

function groupByPrefix(vec) {
  const groups = {};
  for (const [k, v] of Object.entries(vec)) {
    if (typeof v !== 'number') continue;
    const prefix = k.split(':')[0];
    const label = k.includes(':') ? k.split(':').slice(1).join(':') : k;
    (groups[prefix] = groups[prefix] || []).push({ label, value: v, key: k });
  }
  return groups;
}
function truncate(s, n) {
  if (!s) return s;
  return s.length > n ? s.slice(0, n) + '…' : s;
}

let scene, camera, renderer, group, raycaster, mouse, autoRotate = true;
let showPrims = false, showEdges = true, showLabels = false, currentFile = null;
let nodeMeshes = [], edgeLines = [], labelSprites = [], synapses = [];
let zoomTarget = null;
let isOrbiting = false, isPanning = false, prevX = 0, prevY = 0, moved = 0;
let rotX = 0, rotY = 0, panX = 0, panY = 0;
let velRotX = 0, velRotY = 0, velPanX = 0, velPanY = 0;

function init3D() {
  const container = document.getElementById('shape3d');
  const W = container.clientWidth, H = container.clientHeight;
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(60, W / H, 0.1, 1000);
  camera.position.set(0, 2, 14);
  camera.lookAt(0, 0, 0);
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(W, H);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  container.appendChild(renderer.domElement);

  scene.add(new THREE.AmbientLight(0xffffff, 0.4));
  const dir = new THREE.DirectionalLight(0xffffff, 0.8); dir.position.set(5, 10, 7); scene.add(dir);
  const point = new THREE.PointLight(0xa371f7, 0.6, 30); point.position.set(-4, 3, -4); scene.add(point);

  group = new THREE.Group();
  scene.add(group);
  raycaster = new THREE.Raycaster();
  mouse = new THREE.Vector2();

  function resolveHit(hit) {
    let o = hit;
    while (o && !(o.userData && o.userData.key)) o = o.parent;
    return o;
  }

  moved = 0; prevX = 0; prevY = 0;
  rotX = 0; rotY = 0; panX = 0; panY = 0;
  velRotX = 0; velRotY = 0; velPanX = 0; velPanY = 0;
  const camDist = 14;

  container.addEventListener('mousedown', e => {
    moved = 0;
    prevX = e.clientX; prevY = e.clientY;
    velRotX = velRotY = velPanX = velPanY = 0;
    if (e.button === 2 || e.shiftKey) { isPanning = true; autoRotate = false; const t = document.getElementById('toggleAuto'); if (t) t.classList.remove('on'); }
    else { isOrbiting = true; autoRotate = false; const t = document.getElementById('toggleAuto'); if (t) t.classList.remove('on'); }
  });
  window.addEventListener('mouseup', () => { isOrbiting = false; isPanning = false; });
  container.addEventListener('contextmenu', e => e.preventDefault());
  container.addEventListener('mousemove', e => {
    const rect = container.getBoundingClientRect();
    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    const dx = e.clientX - prevX, dy = e.clientY - prevY;
    if (isOrbiting) {
      moved += Math.abs(dx) + Math.abs(dy);
      rotY += dx * 0.008; rotX += dy * 0.008;
      velRotY = dx * 0.008; velRotX = dy * 0.008;
      rotX = Math.max(-1.2, Math.min(1.2, rotX));
      prevX = e.clientX; prevY = e.clientY;
      group.rotation.x = rotX; group.rotation.y = rotY;
    } else if (isPanning) {
      moved += Math.abs(dx) + Math.abs(dy);
      panX += dx * 0.02; panY -= dy * 0.02;
      velPanX = dx * 0.02; velPanY = -dy * 0.02;
      prevX = e.clientX; prevY = e.clientY;
      group.position.x = panX; group.position.y = panY;
    } else {
      raycaster.setFromCamera(mouse, camera);
      const hits = raycaster.intersectObjects(group.children, true);
      const hitNode = hits.length ? resolveHit(hits[0].object) : null;
      nodeMeshes.forEach(m => {
        const isHit = hitNode && m.userData.key === hitNode.userData.key;
        const core = m.userData.core || m;
        m.scale.set(isHit ? 1.3 : 1, isHit ? 1.3 : 1, isHit ? 1.3 : 1);
        if (core && core.material && 'emissiveIntensity' in core.material) core.material.emissiveIntensity = isHit ? 1.2 : 0.5;
        if (core && core.material && 'opacity' in core.material) core.material.opacity = isHit ? 1.0 : 0.9;
      });
      container.style.cursor = hitNode ? 'pointer' : 'grab';
    }
  });
  container.addEventListener('wheel', e => {
    e.preventDefault();
    const f = e.deltaY < 0 ? 0.9 : 1.1;
    camera.position.z = Math.max(4, Math.min(30, camera.position.z * f));
  });
  container.addEventListener('click', e => {
    if (moved > 5) return;
    raycaster.setFromCamera(mouse, camera);
    const hits = raycaster.intersectObjects(group.children, true);
    if (hits.length) { const o = resolveHit(hits[0].object); if (o && o.userData && o.userData.key) openDetail(o.userData); }
  });
  container.addEventListener('dblclick', e => {
    raycaster.setFromCamera(mouse, camera);
    const hits = raycaster.intersectObjects(group.children, true);
    if (hits.length) { const o = resolveHit(hits[0].object); if (o && o.userData && o.userData.key) zoomInto(o.userData); }
  });

  window._resetView = () => {
    rotX = 0; rotY = 0; panX = 0; panY = 0;
    group.rotation.set(0, 0, 0);
    group.position.set(0, 0, 0);
    camera.position.set(0, 2, camDist);
    camera.lookAt(0, 0, 0);
    zoomTarget = null;
  };
  animate();
}

function animate() {
  requestAnimationFrame(animate);
  if (autoRotate) group.rotation.y += 0.002;
  if (!isOrbiting && !isPanning && (Math.abs(velRotX) > 0.0001 || Math.abs(velRotY) > 0.0001 || Math.abs(velPanX) > 0.0001 || Math.abs(velPanY) > 0.0001)) {
    rotY += velRotY; rotX += velRotX;
    rotX = Math.max(-1.2, Math.min(1.2, rotX));
    panX += velPanX; panY += velPanY;
    group.rotation.x = rotX; group.rotation.y = rotY;
    group.position.x = panX; group.position.y = panY;
    velRotX *= 0.95; velRotY *= 0.95; velPanX *= 0.95; velPanY *= 0.95;
  }
  synapses.forEach(s => {
    s.t += 0.006;
    if (s.t > 1) s.t = 0;
    const e = s.t < 0.5 ? 2 * s.t * s.t : 1 - Math.pow(-2 * s.t + 2, 2) / 2;
    const p = s.a.clone().lerp(s.b, e);
    s.mesh.position.copy(p);
    s.mesh.material.opacity = 0.4 + 0.6 * Math.sin(s.t * Math.PI);
  });
  if (zoomTarget) {
    const t = zoomTarget.pos;
    camera.position.lerp(new THREE.Vector3(t.x * 1.2, t.y * 1.2, t.z * 1.2 + 4), 0.06);
    camera.lookAt(t.x, t.y, t.z);
  }
  renderer.render(scene, camera);
}

function makeSynapses(edges, color = 0x58a6ff, count = 1) {
  edges.forEach(ed => {
    for (let i = 0; i < count; i++) {
      const geo = new THREE.SphereGeometry(0.05, 8, 8);
      const mat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.9 });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.copy(ed.a);
      group.add(mesh);
      synapses.push({ mesh, a: ed.a.clone(), b: ed.b.clone(), t: Math.random() });
    }
  });
}

function clearGroup() {
  while (group.children.length) {
    const c = group.children[0];
    group.remove(c);
    c.traverse && c.traverse(o => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); });
    if (c.geometry) c.geometry.dispose();
    if (c.material) c.material.dispose();
  }
  nodeMeshes = []; edgeLines = []; labelSprites = []; synapses = [];
}

function makeLabel(text, color) {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  canvas.width = 256; canvas.height = 48;
  ctx.font = 'bold 20px ui-monospace, monospace';
  ctx.fillStyle = '#e8edf5';
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText(text, 128, 24);
  const tex = new THREE.CanvasTexture(canvas);
  tex.minFilter = THREE.LinearFilter;
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false });
  const sprite = new THREE.Sprite(mat);
  sprite.scale.set(1.6, 0.3, 1);
  return sprite;
}

function makePrimitive(shape, radius, color) {
  const geo = {
    box: () => new THREE.BoxGeometry(radius * 1.6, radius * 1.6, radius * 1.6),
    sphere: () => new THREE.SphereGeometry(radius, 16, 16),
    cone: () => new THREE.ConeGeometry(radius, radius * 2, 16),
    cylinder: () => new THREE.CylinderGeometry(radius, radius, radius * 2, 16),
    torus: () => new THREE.TorusGeometry(radius, radius * 0.4, 10, 20),
    octahedron: () => new THREE.OctahedronGeometry(radius),
    icosahedron: () => new THREE.IcosahedronGeometry(radius),
    dodecahedron: () => new THREE.DodecahedronGeometry(radius),
    tetrahedron: () => new THREE.TetrahedronGeometry(radius),
    torusKnot: () => new THREE.TorusKnotGeometry(radius, radius * 0.3, 40, 8),
  }[shape] || (() => new THREE.SphereGeometry(radius, 16, 16));
  return new THREE.Mesh(geo(), new THREE.MeshPhongMaterial({ color, emissive: color, emissiveIntensity: 0.35, transparent: true, opacity: 0.95 }));
}

const FILE_COLORS = [
  0x58a6ff, 0xf778ba, 0x3fb950, 0xd29922, 0xa371f7,
  0x39c5cf, 0xf85149, 0x7ee787, 0xffa657, 0x79c0ff,
  0xbc8cff, 0xff7b72, 0x56d364, 0xe3b341, 0x76e3ea,
];
function fileColor(file) {
  let h = 0;
  for (let i = 0; i < file.length; i++) h = (h * 31 + file.charCodeAt(i)) >>> 0;
  return FILE_COLORS[h % FILE_COLORS.length];
}

function makeGlowNode(radius, color) {
  const wire = new THREE.Mesh(
    new THREE.IcosahedronGeometry(radius, 1),
    new THREE.MeshBasicMaterial({ color, wireframe: true, transparent: true, opacity: 0.9 })
  );
  const inner = new THREE.Mesh(
    new THREE.OctahedronGeometry(radius * 0.5, 0),
    new THREE.MeshBasicMaterial({ color, wireframe: true, transparent: true, opacity: 0.4 })
  );
  const g = new THREE.Group();
  g.add(wire); g.add(inner);
  g.userData.core = wire;
  return g;
}

function buildShape(file) {
  currentFile = file;
  clearGroup();
  zoomTarget = null;
  if (file.path === '__project__') { buildProjectGrouped(file); return; }
  const dfg = file.dataflow;
  const fns = (dfg && dfg.functions) || [];
  if (!fns.length) { buildHistogram(file); return; }
  const callEdges = (dfg && dfg.call_edges) || [];
  const dataEdges = (dfg && dfg.data_edges) || [];
  const nodePositions = {};
  const synapseEdges = [];
  const color = fileColor(file.path);
  const n = fns.length;
  const R = Math.max(2.5, n * 0.6);
  fns.forEach((fn, i) => {
    const angle = (i / n) * Math.PI * 2;
    const x = Math.cos(angle) * R;
    const y = Math.sin(angle) * R;
    const z = 0;
    const radius = 0.3 + (n - i) * 0.02;
    const node = makeGlowNode(radius, color);
    node.position.set(x, y, z);
    node.userData = { key: 'FN:' + fn, label: fn, cat: 'FUNCTION', value: 1, pos: { x, y, z }, file: file.path };
    group.add(node); nodeMeshes.push(node);
    nodePositions[fn] = { x, y, z };
    if (showLabels) {
      const lbl = makeLabel(fn, color); lbl.position.set(x, y + radius + 0.4, z); group.add(lbl); labelSprites.push(lbl);
    }
  });
  if (showEdges) {
    const callMat = new THREE.LineBasicMaterial({ color: 0x58a6ff, transparent: true, opacity: 0.6 });
    const dataMat = new THREE.LineBasicMaterial({ color: 0x3fb950, transparent: true, opacity: 0.8 });
    callEdges.forEach(([a, b]) => {
      if (!nodePositions[a] || !nodePositions[b]) return;
      const p1 = nodePositions[a], p2 = nodePositions[b];
      const geo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(p1.x, p1.y, p1.z), new THREE.Vector3(p2.x, p2.y, p2.z)]);
      const line = new THREE.Line(geo, callMat); group.add(line); edgeLines.push(line);
      synapseEdges.push({ a: new THREE.Vector3(p1.x, p1.y, p1.z), b: new THREE.Vector3(p2.x, p2.y, p2.z) });
    });
    dataEdges.forEach(([a, b]) => {
      if (!nodePositions[a] || !nodePositions[b]) return;
      const p1 = nodePositions[a], p2 = nodePositions[b];
      const geo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(p1.x, p1.y, p1.z), new THREE.Vector3(p2.x, p2.y, p2.z)]);
      const line = new THREE.Line(geo, dataMat); group.add(line); edgeLines.push(line);
    });
    makeSynapses(synapseEdges, 0x58a6ff, 1);
  }
  const chip = document.getElementById('shapeChip');
  if (chip) chip.textContent = file.path === '__project__' ? `whole project · ${DATA.file_count} files` : (file.shape ? `shape: ${truncate(file.shape, 60)}` : file.path);
}

function buildProjectGrouped(file) {
  const mg = DATA.merged_graph;
  const fns = (mg && mg.functions) || [];
  const fileOf = (mg && mg.file_of) || {};
  const callEdges = (mg && mg.call_edges) || [];
  const dataEdges = (mg && mg.data_edges) || [];
  if (!fns.length) { buildHistogram(file); return; }
  const byFile = {};
  fns.forEach(fn => {
    const f = fileOf[fn] || 'unknown';
    (byFile[f] = byFile[f] || []).push(fn);
  });
  const files = Object.keys(byFile);
  const cols = Math.ceil(Math.sqrt(files.length));
  const clusterGap = 5.5;
  const fnPositions = {};
  const synapseEdges = [];
  const fileColors = {};
  files.forEach((file, fi) => {
    const color = fileColor(file);
    fileColors[file] = color;
    const cx = (fi % cols - (cols - 1) / 2) * clusterGap;
    const cy = (Math.floor(fi / cols) - (Math.ceil(files.length / cols) - 1) / 2) * clusterGap;
    const cz = 0;
    const fnsInFile = byFile[file];
    const n = fnsInFile.length;
    const R = Math.min(2.2, 0.6 + n * 0.12);
    const center = makeGlowNode(0.4, color);
    center.position.set(cx, cy, cz);
    center.userData = { key: 'FILE:' + file, label: file.split('/').pop(), cat: 'FILE', value: 1, pos: { x: cx, y: cy, z: cz }, file };
    group.add(center); nodeMeshes.push(center);
    if (showLabels) {
      const lbl = makeLabel(file.split('/').pop(), color); lbl.position.set(cx, cy + 0.7, cz); group.add(lbl); labelSprites.push(lbl);
    }
    fnsInFile.forEach((fn, i) => {
      const angle = (i / n) * Math.PI * 2;
      const x = cx + Math.cos(angle) * R;
      const y = cy + Math.sin(angle) * R;
      const z = cz + Math.sin(angle * 2) * 0.3;
      const node = makeGlowNode(0.2, color);
      node.position.set(x, y, z);
      node.userData = { key: 'FN:' + fn, label: fn, cat: 'FUNCTION', value: 1, pos: { x, y, z }, file };
      group.add(node); nodeMeshes.push(node);
      fnPositions[fn] = { x, y, z, file, color };
      if (showLabels) {
        const lbl = makeLabel(fn, color); lbl.position.set(x, y + 0.35, z); group.add(lbl); labelSprites.push(lbl);
      }
      synapseEdges.push({ a: new THREE.Vector3(cx, cy, cz), b: new THREE.Vector3(x, y, z) });
    });
  });
  if (showEdges) {
    const seen = new Set();
    callEdges.forEach(([a, b]) => {
      if (!fnPositions[a] || !fnPositions[b]) return;
      const key = a + '>' + b;
      if (seen.has(key)) return;
      seen.add(key);
      const p1 = fnPositions[a], p2 = fnPositions[b];
      const color = p1.color || 0x58a6ff;
      const mat = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.5 });
      const geo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(p1.x, p1.y, p1.z), new THREE.Vector3(p2.x, p2.y, p2.z)]);
      const line = new THREE.Line(geo, mat); group.add(line); edgeLines.push(line);
      synapseEdges.push({ a: new THREE.Vector3(p1.x, p1.y, p1.z), b: new THREE.Vector3(p2.x, p2.y, p2.z) });
    });
    makeSynapses(synapseEdges, 0x58a6ff, 1);
  }
  const legend = document.getElementById('legend');
  if (legend) legend.innerHTML = `<div class="layer">files</div>` + files.map(f =>
    `<div class="row"><span class="dot" style="background:#${fileColors[f].toString(16).padStart(6,'0')};color:#${fileColors[f].toString(16).padStart(6,'0')}"></span><span class="lbl">${f.split('/').pop()}</span></div>`
  ).join('');
  const chip = document.getElementById('shapeChip');
  if (chip) chip.textContent = `whole project · ${files.length} files · ${fns.length} functions`;
}

function buildHistogram(file) {
  const groups = groupByPrefix(file.enriched);
  const layers = CAT_ORDER.filter(c => (groups[c] || []).some(x => x.value > 0));
  if (!layers.length) return;
  const layerGap = 3.2;
  const zStart = -(layers.length - 1) * layerGap / 2;
  const nodePositions = {};
  layers.forEach((cat, li) => {
    const items = groups[cat].filter(x => x.value > 0).sort((a, b) => b.value - a.value);
    const z = zStart + li * layerGap;
    const maxVal = Math.max(...items.map(x => x.value), 0.001);
    const color = CAT_COLORS[cat] || 0x8b96a8;
    items.forEach((it, ri) => {
      const spread = Math.min(4, items.length * 0.7);
      const y = items.length === 1 ? 0 : (ri / (items.length - 1) - 0.5) * spread;
      const x = (Math.sin(ri * 1.7) * 0.5) * spread * 0.6;
      const radius = 0.12 + (it.value / maxVal) * 0.22;
      const mesh = makePrimitive(showPrims ? (PRIM_SHAPES[it.label] || 'sphere') : 'sphere', radius, color);
      mesh.position.set(x, y, z);
      mesh.userData = { key: it.key, label: it.label, cat, value: it.value, pos: { x, y, z } };
      group.add(mesh); nodeMeshes.push(mesh);
      nodePositions[it.key] = { x, y, z };
      if (showLabels) {
        const lbl = makeLabel(it.label, color); lbl.position.set(x, y + radius + 0.35, z); group.add(lbl); labelSprites.push(lbl);
      }
    });
  });
  if (showEdges) {
    const lineMat = new THREE.LineBasicMaterial({ color: 0x8b96a8, transparent: true, opacity: 0.25 });
    const synapseEdges = [];
    for (let li = 0; li < layers.length - 1; li++) {
      const a = groups[layers[li]].filter(x => x.value > 0);
      const b = groups[layers[li + 1]].filter(x => x.value > 0);
      a.forEach(na => { if (!nodePositions[na.key]) return; b.forEach(nb => { if (!nodePositions[nb.key]) return; const p1 = nodePositions[na.key], p2 = nodePositions[nb.key]; const geo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(p1.x, p1.y, p1.z), new THREE.Vector3(p2.x, p2.y, p2.z)]); const line = new THREE.Line(geo, lineMat); group.add(line); edgeLines.push(line); synapseEdges.push({ a: new THREE.Vector3(p1.x, p1.y, p1.z), b: new THREE.Vector3(p2.x, p2.y, p2.z) }); }); });
    }
    makeSynapses(synapseEdges, 0x58a6ff, 1);
  }
  const chip = document.getElementById('shapeChip');
  if (chip) chip.textContent = file.path === '__project__' ? `whole project · ${DATA.file_count} files` : (file.shape ? `shape: ${truncate(file.shape, 60)}` : file.path);
}

function openDetail(ud) {
  const panel = document.getElementById('detailPanel');
  if (!panel) return;
  document.getElementById('detailKey').textContent = ud.key;
  document.getElementById('detailCat').textContent = ud.cat;
  document.getElementById('detailVal').textContent = ud.value.toFixed(4);
  document.getElementById('detailCat2').textContent = ud.cat;
  document.getElementById('detailDesc').textContent = CAT_DESC[ud.cat] || 'shape dimension';
  const filesEl = document.getElementById('detailFiles');
  const contrib = (DATA.contrib || {})[ud.key];
  if (ud.file) {
    filesEl.innerHTML = `<div class="ft">file</div><div class="f">${ud.file}</div>`;
  } else if (currentFile && currentFile.path === '__project__' && contrib && contrib.length) {
    filesEl.innerHTML = `<div class="ft">top contributing files</div>${contrib.map(f => `<div class="f">${f}</div>`).join('')}`;
  } else {
    filesEl.innerHTML = '';
  }
  panel.style.display = 'block';
  window._detailUD = ud;
}
function closeDetail() { const p = document.getElementById('detailPanel'); if (p) p.style.display = 'none'; window._detailUD = null; }

function zoomInto(ud) {
  zoomTarget = { pos: ud.pos, key: ud.key };
  nodeMeshes.forEach(m => {
    const core = m.userData.core || m;
    const isTarget = m.userData.key === ud.key;
    m.scale.set(isTarget ? 1.4 : 1, isTarget ? 1.4 : 1, isTarget ? 1.4 : 1);
    if (core && core.material && 'emissiveIntensity' in core.material) core.material.emissiveIntensity = isTarget ? 1.2 : 0.5;
    if (core && core.material && 'opacity' in core.material) core.material.opacity = isTarget ? 1.0 : 0.9;
  });
  openDetail(ud);
}

function renderLegend() {
  const el = document.getElementById('legend');
  if (!el) return;
  const rows = CAT_ORDER.filter(c => CAT_COLORS[c]).map(c => `<div class="row"><span class="dot" style="background:#${CAT_COLORS[c].toString(16).padStart(6,'0')}"></span><span class="lbl">${c}</span></div>`).join('');
  el.innerHTML = `<div class="layer">layers</div>${rows}`;
}

function initShape3D() {
  renderLegend();
  const sel = document.getElementById('fileSelect');
  if (sel) {
    sel.innerHTML = DATA.files.map(f => `<option value="${f.path}">${f.path === '__project__' ? '🌐 Whole project' : f.path}</option>`).join('');
    sel.addEventListener('change', () => { const f = DATA.files.find(x => x.path === sel.value); if (f) buildShape(f); });
  }
  init3D();
  const first = DATA.files[0];
  if (first) buildShape(first);
  const tPrims = document.getElementById('togglePrims');
  if (tPrims) tPrims.addEventListener('click', e => { showPrims = !showPrims; e.target.classList.toggle('on', showPrims); if (currentFile) buildShape(currentFile); });
  const tEdges = document.getElementById('toggleEdges');
  if (tEdges) tEdges.addEventListener('click', e => { showEdges = !showEdges; e.target.classList.toggle('on', showEdges); if (currentFile) buildShape(currentFile); });
  const tAuto = document.getElementById('toggleAuto');
  if (tAuto) tAuto.addEventListener('click', e => { autoRotate = !autoRotate; e.target.classList.toggle('on', autoRotate); });
  const tLabels = document.getElementById('toggleLabels');
  if (tLabels) tLabels.addEventListener('click', e => { showLabels = !showLabels; e.target.classList.toggle('on', showLabels); if (currentFile) buildShape(currentFile); });
  const reset = document.getElementById('resetView');
  if (reset) reset.addEventListener('click', () => { if (window._resetView) window._resetView(); });
  const dClose = document.getElementById('detailClose');
  if (dClose) dClose.addEventListener('click', closeDetail);
  const dZoom = document.getElementById('detailZoom');
  if (dZoom) dZoom.addEventListener('click', () => { if (window._detailUD) zoomInto(window._detailUD); });
  window.addEventListener('resize', () => { const c = document.getElementById('shape3d'); if (c && camera) { camera.aspect = c.clientWidth / c.clientHeight; camera.updateProjectionMatrix(); renderer.setSize(c.clientWidth, c.clientHeight); } });
}
"""


def shape3d_html(data: Dict[str, Any]) -> str:
    """Render the 3D graph section (stage + controls + script) for a report.

    ``data`` is the payload from :func:`build_shape3d_data`. Returns an empty
    string if there are no files to render.
    """
    files = data.get("files") or []
    if not files:
        return ""
    payload = json.dumps(data, default=str)
    return f"""
<h2>3D Neural Shape</h2>
<p class="note">Interactive 3D view of the project's geometric shape — real AST data-flow
graph, color-coded by file. Drag to orbit, right-drag/shift to pan, scroll to zoom,
click a node to inspect, double-click to zoom in.</p>
<div class="shape-stage">
  <div class="shape-overlay">
    <select id="fileSelect"></select>
    <span class="chip" id="shapeChip">—</span>
    <div class="controls">
      <button class="toggle" id="togglePrims">◆ primitives</button>
      <button class="toggle" id="toggleEdges">— edges</button>
      <button class="toggle" id="toggleAuto">⟳ auto-rotate</button>
      <button class="toggle" id="toggleLabels">🏷 labels</button>
      <button class="toggle" id="resetView">⟲ reset</button>
    </div>
  </div>
  <div class="shape-hud">left-drag rotate · right-drag/shift pan · scroll zoom · <b>click</b> inspect · <b>double-click</b> zoom in</div>
  <div class="shape-legend" id="legend"></div>
  <div class="detail-panel" id="detailPanel">
    <button class="close" id="detailClose">✕</button>
    <h3 id="detailKey"></h3>
    <div class="cat" id="detailCat"></div>
    <div class="row"><span class="k">value</span><span class="v" id="detailVal"></span></div>
    <div class="row"><span class="k">category</span><span class="v" id="detailCat2"></span></div>
    <div class="desc" id="detailDesc"></div>
    <div class="files" id="detailFiles"></div>
    <button class="zoom-btn" id="detailZoom">🔍 zoom into this node</button>
  </div>
  <div id="shape3d"></div>
</div>
<script>
const DATA = {payload};
{SHAPE3D_JS}
if (document.readyState === 'loading') {{
  document.addEventListener('DOMContentLoaded', initShape3D);
}} else {{
  initShape3D();
}}
</script>
"""

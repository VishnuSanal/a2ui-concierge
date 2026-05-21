// A2UI v0.8 interpreter for the Lumen Concierge custom catalog.
//
// Exposes window.a2ui with:
//   • ingest(messageJson)  — accept a single v0.8 message (surfaceUpdate,
//                            dataModelUpdate, beginRendering, deleteSurface).
//                            String or object both accepted; arrays trigger
//                            sequential ingestion.
//   • applyTheme(tokens)   — set CSS custom properties from a {name: value}
//                            map. Unchanged from the pre-spec shim.
//   • reset()              — drop all surface buffers; used between bubbles.
//
// On a beginRendering message the interpreter walks the named root,
// resolves every BoundValue against the surface's data model, instantiates
// the corresponding custom-element, and mounts it under #a2ui-root.
// User actions inside the component bubble up as `a2ui-action` CustomEvents
// carrying {name, context}; the shim wraps each into a v0.8 userAction
// envelope and ships it through window.AndroidBridge.onAction.
//
// The standard v0.8 catalog id is recognised but not implemented end-to-end
// — this build only renders catalog "lumen.com:concierge/v1". Surface
// updates carrying other catalog ids are logged and ignored.

import "./theme.css";
import "./components/chip-group.js";
import "./components/card-grid.js";
import "./components/product-detail.js";
import "./components/concierge-form.js";
import "./components/confirmation-card.js";
import "./components/payment-challenge.js";
import "./components/tx-detail.js";

export const CATALOG_ID = "lumen.com:concierge/v1";
export const STANDARD_CATALOG_ID =
  "https://a2ui.org/specification/v0_8/standard_catalog_definition.json";

// Custom-catalog component-type → custom-element tag-name.
const COMPONENT_TAG = {
  ChipGroup: "a2ui-chip-group",
  CardGrid: "a2ui-card-grid",
  ProductDetail: "a2ui-product-detail",
  ConciergeForm: "a2ui-form",
  ConfirmationCard: "a2ui-confirmation-card",
  PaymentChallenge: "a2ui-payment-challenge",
  TxDetail: "a2ui-tx-detail",
};

// Per-surface buffer: { components: Map<id, def>, dataModel: object,
//                       root?: string, catalogId?: string }
const surfaces = new Map();

function root() {
  return document.getElementById("a2ui-root");
}

function dlog(msg) {
  if (window.AndroidBridge?.log) window.AndroidBridge.log(msg);
}

// ── message dispatch ────────────────────────────────────────────────────

function ingest(msg) {
  if (msg == null) return;
  if (typeof msg === "string") {
    try { msg = JSON.parse(msg); } catch (e) { dlog(`ingest parse error: ${e}`); return; }
  }
  if (Array.isArray(msg)) {
    for (const m of msg) ingest(m);
    return;
  }
  if (msg.surfaceUpdate) handleSurfaceUpdate(msg.surfaceUpdate);
  else if (msg.dataModelUpdate) handleDataModelUpdate(msg.dataModelUpdate);
  else if (msg.beginRendering) handleBeginRendering(msg.beginRendering);
  else if (msg.deleteSurface) handleDeleteSurface(msg.deleteSurface);
  else dlog(`ingest: unknown message keys ${Object.keys(msg).join(",")}`);
}

function ensureSurface(surfaceId) {
  let s = surfaces.get(surfaceId);
  if (!s) {
    s = { surfaceId, components: new Map(), dataModel: {} };
    surfaces.set(surfaceId, s);
  }
  return s;
}

function handleSurfaceUpdate({ surfaceId, components }) {
  const s = ensureSurface(surfaceId);
  for (const c of components || []) {
    if (c && c.id) s.components.set(c.id, c);
  }
  dlog(`surfaceUpdate: ${surfaceId} components=${(components || []).length}`);
}

function handleDataModelUpdate({ surfaceId, path, contents }) {
  const s = ensureSurface(surfaceId);
  const entries = (contents || []).reduce((acc, e) => {
    if (!e || typeof e.key !== "string") return acc;
    if ("valueString" in e) acc[e.key] = e.valueString;
    else if ("valueNumber" in e) acc[e.key] = e.valueNumber;
    else if ("valueBoolean" in e) acc[e.key] = e.valueBoolean;
    else if ("valueMap" in e) acc[e.key] = mapFromEntries(e.valueMap);
    return acc;
  }, {});
  if (!path || path === "/") {
    s.dataModel = entries;
  } else {
    setByPath(s.dataModel, path, entries);
  }
  if (s.root) renderSurface(surfaceId);
}

function mapFromEntries(arr) {
  const out = {};
  for (const e of arr || []) {
    if (!e || typeof e.key !== "string") continue;
    if ("valueString" in e) out[e.key] = e.valueString;
    else if ("valueNumber" in e) out[e.key] = e.valueNumber;
    else if ("valueBoolean" in e) out[e.key] = e.valueBoolean;
  }
  return out;
}

function handleBeginRendering({ surfaceId, root: rootId, catalogId, styles }) {
  const s = ensureSurface(surfaceId);
  s.root = rootId;
  s.catalogId = catalogId || CATALOG_ID;
  if (styles) applyStyles(styles);
  if (s.catalogId !== CATALOG_ID && s.catalogId !== STANDARD_CATALOG_ID) {
    // Other catalog ids are logged and ignored — proceeding to renderSurface
    // would emit "unknown component" placeholders for foreign types. Also
    // clear any DOM previously mounted into this surface so a stale render
    // doesn't linger.
    dlog(`beginRendering: unsupported catalogId=${s.catalogId} — ignoring`);
    const r = root();
    if (r && r.dataset.surfaceId === surfaceId) {
      r.innerHTML = "";
      delete r.dataset.surfaceId;
    }
    return;
  }
  renderSurface(surfaceId);
}

function handleDeleteSurface({ surfaceId }) {
  surfaces.delete(surfaceId);
  const r = root();
  if (r && r.dataset.surfaceId === surfaceId) r.innerHTML = "";
}

// ── rendering ───────────────────────────────────────────────────────────

function renderSurface(surfaceId) {
  const r = root();
  if (!r) return;
  const s = surfaces.get(surfaceId);
  if (!s || !s.root) return;
  const def = s.components.get(s.root);
  if (!def) { dlog(`renderSurface: root ${s.root} not in buffer`); return; }
  lastReported = -1;
  r.innerHTML = "";
  r.dataset.surfaceId = surfaceId;
  const el = instantiate(def, s);
  if (!el) {
    r.textContent = `unknown component type: ${describeComponent(def)}`;
    reportSize();
    return;
  }
  r.appendChild(el);
  awaitRenderAndMeasure(el);
}

function describeComponent(def) {
  if (!def || !def.component) return "<no component>";
  return Object.keys(def.component)[0] || "<empty>";
}

function instantiate(def, surface) {
  const entry = Object.entries(def.component || {})[0];
  if (!entry) return null;
  const [type, rawProps] = entry;
  const tag = COMPONENT_TAG[type];
  if (!tag) return null;
  const el = document.createElement(tag);
  el._a2uiType = type;
  el._a2uiSurfaceId = surface.surfaceId;
  el._a2uiSourceComponentId = def.id;
  const resolved = resolveValue(rawProps, surface);
  if (resolved && typeof resolved === "object") {
    for (const [k, v] of Object.entries(resolved)) el[k] = v;
  }
  return el;
}

async function awaitRenderAndMeasure(el) {
  if (el && el.updateComplete) {
    try { await el.updateComplete; } catch { /* no-op */ }
  }
  reportSize();
  el?.addEventListener("load", reportSize, true);
  el?.addEventListener("error", reportSize, true);
  let n = 0;
  const id = setInterval(() => { reportSize(); if (++n > 10) clearInterval(id); }, 80);
}

// Resolve BoundValue objects against a surface's data model. The function
// walks plain objects and arrays so nested fields (e.g. an options list of
// `{value, label: {literalString}}`) are normalised in one pass.
function resolveValue(v, surface) {
  if (v == null) return v;
  if (Array.isArray(v)) return v.map(x => resolveValue(x, surface));
  if (typeof v !== "object") return v;
  if (isBoundValue(v)) return resolveBound(v, surface);
  const out = {};
  for (const [k, sub] of Object.entries(v)) out[k] = resolveValue(sub, surface);
  return out;
}

const BOUND_KEYS = new Set([
  "literalString", "literalNumber", "literalBoolean", "literalArray", "path",
]);

function isBoundValue(o) {
  const keys = Object.keys(o);
  if (keys.length === 0 || keys.length > 1) return false;
  return BOUND_KEYS.has(keys[0]);
}

function resolveBound(v, surface) {
  if ("literalString" in v) return v.literalString;
  if ("literalNumber" in v) return v.literalNumber;
  if ("literalBoolean" in v) return v.literalBoolean;
  if ("literalArray" in v) return v.literalArray;
  if ("path" in v) return getByPath(surface.dataModel, v.path);
  return undefined;
}

function getByPath(model, path) {
  if (!path || path === "/") return model;
  const parts = path.replace(/^\/+/, "").split("/");
  let cur = model;
  for (const p of parts) {
    if (cur == null) return undefined;
    cur = cur[p];
  }
  return cur;
}

function setByPath(model, path, value) {
  const parts = path.replace(/^\/+/, "").split("/").filter(Boolean);
  if (parts.length === 0) return;
  let cur = model;
  for (let i = 0; i < parts.length - 1; i++) {
    if (cur[parts[i]] == null || typeof cur[parts[i]] !== "object") {
      cur[parts[i]] = {};
    }
    cur = cur[parts[i]];
  }
  cur[parts[parts.length - 1]] = value;
}

// ── styles ──────────────────────────────────────────────────────────────

function applyStyles(styles) {
  for (const [k, v] of Object.entries(styles || {})) {
    if (k === "primaryColor") {
      document.documentElement.style.setProperty("--a2ui-color-accent", v);
    } else if (k === "font") {
      document.documentElement.style.setProperty("--a2ui-font-sans", v);
    } else {
      document.documentElement.style.setProperty(`--a2ui-${k}`, v);
    }
  }
}

function applyTheme(tokens) {
  for (const [k, v] of Object.entries(tokens || {})) {
    document.documentElement.style.setProperty(`--a2ui-${k}`, v);
  }
}

// ── action emission (client → server, v0.8 userAction envelope) ────────

function emitUserAction(detail, sourceEl) {
  const name = detail?.name;
  if (!name) return;
  const envelope = {
    userAction: {
      name,
      surfaceId: sourceEl?._a2uiSurfaceId ?? null,
      sourceComponentId: sourceEl?._a2uiSourceComponentId ?? null,
      timestamp: new Date().toISOString(),
      context: detail.context || {},
    },
  };
  const payload = JSON.stringify(envelope);
  if (window.AndroidBridge?.onAction) window.AndroidBridge.onAction(payload);
  window.parent?.postMessage({ type: "a2ui:userAction", message: envelope }, "*");
}

document.addEventListener("a2ui-action", (e) => {
  emitUserAction(e.detail || {}, e.target);
});

// ── size reporting (unchanged from pre-spec shim) ──────────────────────

let lastReported = -1;
function reportSize() {
  const r = root();
  if (!r) return;
  const sH = r.scrollHeight;
  const oH = r.offsetHeight;
  const cssH = Math.max(sH, oH) + 12;
  const cssClamped = Math.max(60, cssH);
  const dpr = window.devicePixelRatio || 1;
  const devicePx = Math.ceil(cssClamped * dpr);
  if (devicePx === lastReported) return;
  lastReported = devicePx;
  if (window.AndroidBridge?.onResize) window.AndroidBridge.onResize(devicePx);
  window.parent?.postMessage({ type: "a2ui:resize", height: devicePx }, "*");
}

const startObserving = () => {
  const r = root();
  if (!r) return;
  new ResizeObserver(reportSize).observe(r);
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", startObserving, { once: true });
} else {
  startObserving();
}

function reset() {
  surfaces.clear();
  const r = root();
  if (r) { r.innerHTML = ""; delete r.dataset.surfaceId; }
}

window.a2ui = { ingest, applyTheme, reset, CATALOG_ID, STANDARD_CATALOG_ID };

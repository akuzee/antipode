// Smoke-test the full app script from index.html under Node with a stub DOM:
// press Start, deliver a GPS fix and an orientation event, run a few frames,
// and check that coastlines, labels and HUD text were actually drawn.
// Usage: node test/dom-smoke.mjs
import { readFileSync } from 'fs';
import vm from 'vm';

const here = new URL('.', import.meta.url).pathname;
const html = readFileSync(here + '../index.html', 'utf8');
const blocks = [...html.matchAll(/<script(?: id="core")?>([\s\S]*?)<\/script>/g)].map(m => m[1]);
if (blocks.length !== 2) { console.error('expected 2 script blocks, got ' + blocks.length); process.exit(1); }

// ---- recording canvas context ----
const drawn = { moveTo: 0, lineTo: 0, stroke: 0, arc: 0, texts: [] };
const ctx2d = new Proxy({}, {
  get(_, k) {
    if (k === 'fillText' || k === 'strokeText') return (t) => { drawn.texts.push(String(t)); };
    if (k === 'moveTo') return () => drawn.moveTo++;
    if (k === 'lineTo') return () => drawn.lineTo++;
    if (k === 'stroke') return () => drawn.stroke++;
    if (k === 'arc') return () => drawn.arc++;
    return () => {};        // clearRect, setTransform, beginPath, fill, ...
  },
  set() { return true; }    // font, strokeStyle, lineWidth, ...
});

// ---- stub elements ----
function makeEl(id) {
  const listeners = {};
  return {
    id, value: '', textContent: '', style: {}, children: [],
    set innerHTML(v) { this.children = []; }, get innerHTML() { return ''; },
    classList: { add() {}, remove() {}, toggle() {} },
    addEventListener(type, fn) { (listeners[type] ||= []).push(fn); },
    fire(type, ev) { (listeners[type] || []).forEach(fn => fn.call(this, ev || {})); },
    appendChild(c) { this.children.push(c); },
    setPointerCapture() {},
    getContext(kind) { return kind === '2d' ? ctx2d : null; },
    play() { return { catch() {} }; },
  };
}
const els = {};
const byId = id => (els[id] ||= makeEl(id));

// ---- sandbox globals ----
const winListeners = {};
let rafCb = null;
const sandbox = {
  console,
  Math, JSON, Promise, Float32Array, Infinity, NaN, isFinite, parseFloat,
  performance, setTimeout, clearTimeout,
  document: {
    getElementById: byId,
    createElement: () => makeEl('anon'),
  },
  navigator: {
    geolocation: {
      getCurrentPosition(ok) { ok({ coords: { latitude: 40.7128, longitude: -74.0060 } }); },
    },
    // no mediaDevices: camera path degrades to a note, which is the point
  },
  screen: { orientation: { angle: 0 } },
  requestAnimationFrame(cb) { rafCb = cb; },
  innerWidth: 390, innerHeight: 844, devicePixelRatio: 2, orientation: 0,
  addEventListener(type, fn) { (winListeners[type] ||= []).push(fn); },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

let failed = 0;
const check = (name, ok, detail) => {
  console.log((ok ? 'PASS' : 'FAIL') + '  ' + name + (detail ? '  -- ' + detail : ''));
  if (!ok) failed++;
};

try {
  vm.runInContext(blocks[0], sandbox);   // core
  vm.runInContext(blocks[1], sandbox);   // app (IIFE, wires everything at load)
  check('scripts load without throwing', true);
} catch (e) {
  check('scripts load without throwing', false, String(e && e.stack || e));
  process.exit(1);
}

try {
  byId('startBtn').fire('click');        // start: attaches sensors, geo fires synchronously
  check('start flow runs (geo fix applied)', /loc 40\.71/.test(byId('chipLoc').textContent),
    JSON.stringify(byId('chipLoc').textContent));

  // phone flat, top edge north
  (winListeners['deviceorientation'] || []).forEach(fn =>
    fn({ alpha: 0, beta: 0, gamma: 0, absolute: false }));

  const t0 = performance.now();
  for (let i = 1; i <= 5 && rafCb; i++) { const cb = rafCb; rafCb = null; cb(t0 + i * 200); }

  check('coastlines drawn', drawn.lineTo > 2000, drawn.lineTo + ' lineTo calls');
  check('antipode reticle drawn', drawn.texts.some(t => t === 'ANTIPODE'));
  check('ring labels drawn', drawn.texts.some(t => /Θ \d+°/.test(t)),
    JSON.stringify(drawn.texts.filter(t => t.startsWith('Θ')).slice(0, 5)));
  check('city labels drawn', drawn.texts.some(t => t === 'Perth' || t === 'Sydney'),
    JSON.stringify(drawn.texts.filter(t => /^[A-Z]/.test(t)).slice(0, 8)));
  check('HUD readout shows ν and Θ', /ν 0\.0° · Θ 0\.0°/.test(byId('roMain').textContent),
    JSON.stringify(byId('roMain').textContent));
  check('HUD nearest place computed', /Perth|km/.test(byId('roSub').textContent),
    JSON.stringify(byId('roSub').textContent));

  // tilt 40 deg toward horizon, then run frames: nu should approach 40
  (winListeners['deviceorientation'] || []).forEach(fn =>
    fn({ alpha: 0, beta: 40, gamma: 0, absolute: false }));
  for (let i = 6; i <= 40 && rafCb; i++) { const cb = rafCb; rafCb = null; cb(t0 + i * 200); }
  const nu = parseFloat((byId('roMain').textContent.match(/ν ([\d.]+)°/) || [])[1]);
  check('tilt 40° -> readout ν ≈ 40°', Math.abs(nu - 40) < 1.5, 'ν = ' + nu + '°');

  // self-test button produces all-pass output
  byId('runTest').fire('click');
  const lines = byId('testOut').children.map(c => c.textContent).join('');
  check('in-app self-test panel: all pass', !/✗/.test(lines) && /\/14|\/13|\/12|passed/.test(lines),
    (lines.match(/(\d+\/\d+ passed)/) || [])[1]);
} catch (e) {
  check('interaction flow runs without throwing', false, String(e && e.stack || e));
}

console.log(failed === 0 ? '\nSMOKE TEST PASSED' : `\n${failed} CHECK(S) FAILED`);
process.exit(failed === 0 ? 0 : 1);

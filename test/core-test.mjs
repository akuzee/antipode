// Runs the <script id="core"> block from index.html under Node and verifies:
//  - the built-in self-test panel (same checks the browser "Run self-test" shows)
//  - a deep round-trip of the inlined coastline data against the build script's
//    reference decode (test/coast_reference.json)
// Usage: node test/core-test.mjs
import { readFileSync } from 'fs';
import vm from 'vm';

const here = new URL('.', import.meta.url).pathname;
const html = readFileSync(here + '../ar/index.html', 'utf8');

const m = html.match(/<script id="core">([\s\S]*?)<\/script>/);
if (!m) { console.error('core script block not found'); process.exit(1); }

const ctx = { console };
vm.createContext(ctx);
vm.runInContext(m[1], ctx);
const A = ctx.Antipode;

let failed = 0;

// 1. built-in self-test
for (const r of A.runSelfTest()) {
  console.log((r.pass ? 'PASS' : 'FAIL') + '  ' + r.name + (r.detail ? '  -- ' + r.detail : ''));
  if (!r.pass) failed++;
}

// 2. deep round-trip vs the Python build's reference decode
const ref = JSON.parse(readFileSync(here + 'coast_reference.json', 'utf8'));
const dec = A.decodeCoastInt(A.COAST_DATA);
let same = dec.length === ref.length;
if (same) {
  outer: for (let i = 0; i < ref.length; i++) {
    if (dec[i].length !== ref[i].length) { same = false; break; }
    for (let j = 0; j < ref[i].length; j++) {
      if (dec[i][j][0] !== ref[i][j][0] || dec[i][j][1] !== ref[i][j][1]) { same = false; break outer; }
    }
  }
}
console.log((same ? 'PASS' : 'FAIL') + '  JS decoder matches Python reference decode exactly'
  + `  -- ${dec.length} polylines`);
if (!same) failed++;

// 3. the data string must be raw-embeddable (no escaping surprises)
const bad = [...A.COAST_DATA].filter(c => {
  const k = c.charCodeAt(0);
  return k < 40 || k > 126 || k === 60 || k === 62 || k === 92 || k === 96;
});
console.log((bad.length === 0 ? 'PASS' : 'FAIL') + '  data uses only the 83-char safe alphabet');
if (bad.length) failed++;

console.log(failed === 0 ? '\nALL TESTS PASSED' : `\n${failed} TEST(S) FAILED`);
process.exit(failed === 0 ? 0 : 1);

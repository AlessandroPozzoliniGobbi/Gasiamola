/* node:test without a browser: verifies backwards-compatible local draft migration. */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const filename = require('node:path').resolve(__dirname, 'src/lib/analysisStorage.ts');
const source = fs.readFileSync(filename, 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }});
const saved = new Map();
const sandbox = { exports: {}, window: { localStorage: { getItem: k=>saved.get(k)??null, setItem: (k,v)=>saved.set(k,v) } }, console };
vm.runInNewContext(outputText, sandbox, { filename });
const a = sandbox.exports;
const key = 'fieldwise:analysis-drafts:v1';

test('standard analyses default to economics and future off', () => {
  assert.equal(a.defaultAnalysisDraft().advancedEconomics, false);
  assert.equal(a.defaultAnalysisDraft().includeFuture, false);
  assert.equal(a.defaultAnalysisDraft().futureHorizon, 10);
  assert.equal(a.defaultAnalysisDraft().futureSsp, "ssp245");
});

test('legacy drafts load without losing their crop rotation or priorities', () => {
  saved.clear();
  const old = a.defaultAnalysisDraft();
  delete old.advancedEconomics;
  delete old.includeFuture;
  old.priorities.profitto = 7;
  saved.set(key, JSON.stringify({'field-old': old}));
  const restored = a.loadAnalysisDraft('field-old');
  assert.equal(restored.advancedEconomics, false);
  assert.equal(restored.includeFuture, false);
  assert.equal(restored.futureHorizon, 10);
  assert.equal(restored.futureSsp, "ssp245");
  assert.equal(restored.priorities.profitto, 7);
});

test('advanced opt-in is stored per field and does not transfer to a new ID', () => {
  saved.clear();
  const enabled = { ...a.defaultAnalysisDraft(), advancedEconomics: true, includeFuture: true, futureHorizon: 20, futureSsp: "ssp585" };
  a.saveAnalysisDraft('old-field-id', enabled);
  const loadedOld = a.loadAnalysisDraft('old-field-id');
  assert.equal(loadedOld.advancedEconomics, true);
  assert.equal(loadedOld.includeFuture, true);
  assert.equal(loadedOld.futureHorizon, 20);
  assert.equal(loadedOld.futureSsp, "ssp585");

  const loadedFresh = a.loadAnalysisDraft('fresh-field-id');
  assert.equal(loadedFresh.advancedEconomics, false);
  assert.equal(loadedFresh.includeFuture, false);
});

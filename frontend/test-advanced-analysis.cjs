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

test('standard analyses default to economics off', () => {
  assert.equal(a.defaultAnalysisDraft().advancedEconomics, false);
});

test('legacy drafts load without losing their crop rotation or priorities', () => {
  saved.clear();
  const old = a.defaultAnalysisDraft();
  delete old.advancedEconomics;
  old.priorities.profitto = 7;
  saved.set(key, JSON.stringify({'field-old': old}));
  const restored = a.loadAnalysisDraft('field-old');
  assert.equal(restored.advancedEconomics, false);
  assert.equal(restored.priorities.profitto, 7);
});

test('advanced opt-in is stored per field and does not transfer to a new ID', () => {
  saved.clear();
  const enabled = { ...a.defaultAnalysisDraft(), advancedEconomics: true };
  a.saveAnalysisDraft('old-field-id', enabled);
  assert.equal(a.loadAnalysisDraft('old-field-id').advancedEconomics, true);
  assert.equal(a.loadAnalysisDraft('fresh-field-id').advancedEconomics, false);
});

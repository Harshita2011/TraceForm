const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/lib/draft-recovery.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
const mod = {exports:{}}; new Function('module','exports',code)(mod,mod.exports);
const {readDeviceCopies,clearAcknowledgedRecovery,recoveryPrefix} = mod.exports;
function storage() { const map = new Map(); return {get length(){return map.size}, key:i=>[...map.keys()][i], getItem:k=>map.get(k)??null, setItem:(k,v)=>map.set(k,v), removeItem:k=>map.delete(k)}; }

test('acknowledging one tab cannot remove another tab recovery copy', () => {
  const data=storage(); const prefix=recoveryPrefix('artifact','owner');
  data.setItem(prefix+':tab-a',JSON.stringify({content:'A'})); data.setItem(prefix+':tab-b',JSON.stringify({content:'B'}));
  clearAcknowledgedRecovery(data,prefix+':tab-a','A');
  assert.equal(data.getItem(prefix+':tab-a'),null);
  assert.deepEqual(readDeviceCopies(data,'artifact','owner','A').copies.map(c=>c.content),['B']);
  assert.equal(readDeviceCopies(data,'artifact','another-owner','A').copies.length,0);
});

test('a damaged old draft cannot hide valid legacy or recovery copies', () => {
  const data=storage(); data.setItem('traceform-draft:a','broken JSON');
  data.setItem('traceform-draft:a:versions',JSON.stringify([{content:'Old version'}]));
  data.setItem(recoveryPrefix('a','o')+':tab',JSON.stringify({content:'Recovered'}));
  const result=readDeviceCopies(data,'a','o','Server text');
  assert.equal(result.damaged,true); assert.deepEqual(result.copies.map(c=>c.content),['Recovered','Old version']);
});

test('recovery is retained until the exact text is acknowledged', () => {
  const data=storage(); const key=recoveryPrefix('a','o')+':tab'; data.setItem(key,JSON.stringify({content:'Newer typing'}));
  clearAcknowledgedRecovery(data,key,'Older in-flight save'); assert.ok(data.getItem(key));
});

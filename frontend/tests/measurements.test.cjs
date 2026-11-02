const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');const ts=require('typescript');
function client(fetch){
 const source=fs.readFileSync(path.join(__dirname,'../src/lib/measurements.ts'),'utf8');
 const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
 const mod={exports:{}};new Function('require','module','exports',code)(()=>({apiFetch:fetch}),mod,mod.exports);return mod.exports;
}
test('measurement transport retains idempotency and exact evidence annotations',async()=>{
 let calls=[];const api=client(async(url,options)=>{calls.push([url,options]);return {id:'execution'};});
 await api.executeDataset('dataset','retry-key');await api.executeDataset('dataset','retry-key');
 assert.deepEqual(calls[0],calls[1]);assert.deepEqual(JSON.parse(calls[0][1].body),{dataset_id:'dataset',request_id:'retry-key'});
 const data={name:'Release',version:'v1',notes:'',cases:[{version_id:'v',title:'Case',claims:[{claim:'Exact claim',verdict:'unsupported',reason:'Absent.'}],complete_claim_inventory:true,style_passed:false,style_notes:'Missing heading.'}]};
 await api.createDataset(data);assert.deepEqual(JSON.parse(calls[2][1].body),data);
});
test('request filters preserve UTC boundaries, model names and pagination',async()=>{
 const api=client(async(url)=>{const u=new URL(url,'http://test');assert.equal(u.searchParams.get('model'),'model / plus+');assert.equal(u.searchParams.get('offset'),'30');assert.equal(u.searchParams.get('since'),'2026-11-01T00:00:00Z');return {items:[],total:0};});
 await api.getRequests('2026-11-01T00:00:00Z','2026-11-02T00:00:00Z','failed','model / plus+',30);
});

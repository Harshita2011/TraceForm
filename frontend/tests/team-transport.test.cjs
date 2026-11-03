const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');const ts=require('typescript');
function proxy(fetch,env={}){
 const file=fs.readFileSync(path.join(__dirname,'../src/app/api/backend/[...path]/route.ts'),'utf8');
 const code=ts.transpileModule(file,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
 const mod={exports:{}};new Function('require','module','exports','process','fetch',code)(()=>({}),mod,mod.exports,{env},fetch);return mod.exports;
}
function request(url,headers={},method='GET'){
 const original=new Request('http://localhost:3000/api/backend'+url,{method,headers});
 return {method,headers:original.headers,nextUrl:new URL(original.url),arrayBuffer:()=>original.arrayBuffer(),cookies:{get:()=>headers.cookie?'synthetic-session':undefined}};
}
const context=parts=>({params:Promise.resolve({path:parts.split('/').filter(Boolean)})});
test('unauthenticated browser requests cannot use the installation key to reach documents',async()=>{
 let calls=0;const route=proxy(async()=>{calls++;throw Error('Must not reach backend');});
 const response=await route.GET(request('/api/v1/sources',{'X-API-Key':'public-key'}),context('/api/v1/sources'));
 assert.equal(response.status,401);assert.equal(calls,0);
});
test('session proxy preserves cookie/origin, drops browser keys and forbids cache',async()=>{
 const route=proxy(async(url,options)=>{
  assert.equal(url,'http://127.0.0.1:8000/api/v1/team-reviews?status=pending');
  assert.equal(options.headers.get('cookie'),'traceform_session=synthetic');
  assert.equal(options.headers.get('origin'),'http://localhost:3000');
  assert.equal(options.headers.get('X-API-Key'),null);assert.equal(options.redirect,'manual');
  return new Response('{}',{headers:{'Set-Cookie':'traceform_session=rotated; HttpOnly; SameSite=Strict'}});
 });
 const response=await route.GET(request('/api/v1/team-reviews?status=pending',{cookie:'traceform_session=synthetic',origin:'http://localhost:3000','X-API-Key':'must-not-forward'}),context('/api/v1/team-reviews'));
 assert.equal(response.status,200);assert.equal(response.headers.get('cache-control'),'no-store');assert.match(response.headers.get('set-cookie'),/HttpOnly/);
});
test('first-owner setup forwards only an explicitly entered installation key',async()=>{
 const route=proxy(async(url,options)=>{assert.equal(options.headers.get('X-API-Key'),'entered-admin-key');return new Response('{}',{status:201});});
 const response=await route.POST(request('/api/v1/auth/setup',{'X-Installation-Key':'entered-admin-key'},'POST'),context('/api/v1/auth/setup'));
 assert.equal(response.status,201);
});

test('public registration forwards credentials without requiring or exposing an installation key',async()=>{
 const route=proxy(async(url,options)=>{
  assert.equal(url,'https://api.example.test/api/v1/auth/register');
  assert.equal(options.method,'POST');
  assert.equal(options.headers.get('origin'),'https://app.example.test');
  assert.equal(options.headers.get('x-api-key'),null);
  assert.equal(options.headers.get('x-installation-key'),null);
  assert.equal(new TextDecoder().decode(options.body),'registration fixture');
  return new Response('{}',{status:201,headers:{'Set-Cookie':'traceform_session=registered; Secure; HttpOnly; SameSite=Strict; Path=/'}});
 },{VERCEL:'1',TRACEFORM_API_URL:'https://api.example.test'});
 const req=request('/api/v1/auth/register',{'origin':'https://app.example.test','x-installation-key':'must-not-forward'},'POST');
 req.arrayBuffer=async()=>new TextEncoder().encode('registration fixture').buffer;
 const response=await route.POST(req,context('/api/v1/auth/register'));
 assert.equal(response.status,201);
 assert.match(response.headers.get('set-cookie'),/Secure; HttpOnly/);
});
test('proxy rejects path traversal and non-API destinations before any upstream call',async()=>{
 const route=proxy(async()=>{throw Error('Must not fetch');});
 for(const parts of [['api','v1','..','settings'],['http:','attacker.test'],['api','v1','sources/../../settings']]){
  assert.equal((await route.GET(request('/ignored'),{params:Promise.resolve({path:parts})})).status,404);
 }
});
test('collection routes use canonical backend slashes without losing upload bodies to redirects',async()=>{
 const route=proxy(async(url,options)=>{
  assert.equal(url,'http://127.0.0.1:8000/api/v1/sources/');assert.equal(options.method,'POST');
  assert.equal(new TextDecoder().decode(options.body),'fixture text');
  return new Response('{}',{status:201});
 });
 const req=request('/api/v1/sources',{cookie:'traceform_session=synthetic'},'POST');
 req.arrayBuffer=async()=>new TextEncoder().encode('fixture text').buffer;
 assert.equal((await route.POST(req,context('/api/v1/sources'))).status,201);
});


test('hosted proxy requires an explicitly configured HTTPS backend',async()=>{
 const route=proxy(async()=>{throw Error('Must not fetch');},{VERCEL:'1'});
 assert.equal((await route.GET(request('/api/v1/auth/status'),context('/api/v1/auth/status'))).status,503);
});

test('hosted proxy rejects oversize requests before buffering or forwarding',async()=>{
 const route=proxy(async()=>{throw Error('Must not fetch');},{VERCEL:'1',TRACEFORM_API_URL:'https://api.example.test'});
 const req=request('/api/v1/sources',{'content-length':'4500000',cookie:'traceform_session=synthetic'},'POST');
 req.arrayBuffer=()=>{throw Error('Must not buffer oversize body');};
 assert.equal((await route.POST(req,context('/api/v1/sources'))).status,413);
});

test('hosted proxy streams exports and preserves request correlation',async()=>{
 const route=proxy(async(url)=>{
  assert.equal(url,'https://api.example.test/api/v1/artifacts/output/export');
  return new Response('fixture export',{headers:{'content-disposition':'attachment; filename=report.docx','x-request-id':'known-request'}});
 },{VERCEL:'1',TRACEFORM_API_URL:'https://api.example.test'});
 const response=await route.GET(request('/api/v1/artifacts/output/export',{cookie:'traceform_session=synthetic'}),context('/api/v1/artifacts/output/export'));
 assert.equal(await response.text(),'fixture export');assert.equal(response.headers.get('x-request-id'),'known-request');
 assert.match(response.headers.get('content-disposition'),/report.docx/);
});

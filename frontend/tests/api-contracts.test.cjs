const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const ts = require('typescript');

test('an override or missing evidence cannot inherit a verified badge', async () => {
  for (const status of ['overridden', 'unreviewed', 'needs_review']) {
    const api = client(async () => ({body:{id:'a',output_type:'executive_summary',content:'Draft',
      review_status:'passed',assurance_status:status,facts_used:[{claim:'Draft',source_span:'Draft'}]}}));
    const result = await api.getArtifact('a');
    assert.notEqual(result.review_status,'pass');
    assert.equal(result.citations[0].status,'pending');
  }
});

test('evidence assurance preserves the distinct budget-exceeded state', async () => {
  const api=client(async () => ({body:{id:'a',review_status:'budget_exceeded',assurance_status:'needs_review'}}));
  assert.equal((await api.getArtifact('a')).review_status,'budget_exceeded');
});

test('review findings and version-bound decision context survive normalization', async () => {
  const evidence = {content_version:'a'.repeat(64),findings:[{claim:'Invented entity',message:'Unsupported'}]};
  const api = client(async () => ({body:{id:'a',evidence,assurance_status:'needs_review',
    review_results:[{reviewer_name:'fact_reviewer',passed:false,details:{failing_claims:['Invented entity']}}]}}));
  const artifact=await api.getArtifact('a');
  assert.deepEqual(artifact.evidence,evidence);
  assert.equal(artifact.reviewer_outcomes[0].reason,'Invented entity');
  assert.equal(artifact.reviewer_outcomes[0].blocking,true);
});

test('compliance exception sends the content version and reloads the saved decision', async () => {
  const api=client(async (url,options) => {
    if(options.method==='POST') assert.deepEqual(JSON.parse(options.body),{reason:'Reviewed for internal use',expected_content_version:'a'.repeat(64)});
    return {body:{id:'a',assurance_status:'overridden'}};
  });
  const updated=await api.submitComplianceOverride({artifact_id:'a',override_reason:'Reviewed for internal use',expected_content_version:'a'.repeat(64),sensitivity:'internal'});
  assert.equal(updated.assurance_status,'overridden');
  assert.notEqual(updated.review_status,'pass');
});

function client(respond) {
  const source = fs.readFileSync(require('node:path').join(__dirname, '../src/lib/api.ts'), 'utf8');
  const code = ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
  const mod = {exports:{}};
  const mocks = {MOCK_GENERATIONS:[],MOCK_SOURCES:[],MOCK_ARTIFACTS:[],MOCK_HISTORY:[],MOCK_METRICS:{},MOCK_PIPELINE_STATUS:{}};
  new Function('require','module','exports','process','fetch','AbortController','FormData','File',code)(
    () => mocks, mod, mod.exports, {env:{NEXT_PUBLIC_API_URL:'http://localhost:8000'}}, async (url, options) => {
      const value = await respond(url, options);
      return {ok:value.status ? value.status < 400 : true,status:value.status || 200,json:async () => value.body};
    }, AbortController, FormData, File);
  return mod.exports;
}

test('browser requests use session cookies without copying an installation key',async()=>{
  const api=client(async(url,options)=>{
    assert.equal(options.credentials,'include');assert.equal(options.headers['X-API-Key'],undefined);
    return {body:[]};
  });
  await api.listCollections();
});

test('combined generation retains ordered sources, analysis and conflict choices', async () => {
  const selection={source_ids:['a','b'],analysis_id:'analysis',conflict_resolutions:{c:{choice:'prefer',preferred_source_id:'b'}}};
  const api=client(async (url,options) => {
    const body=JSON.parse(options.body);
    for(const [key,value] of Object.entries(selection)) assert.deepEqual(body[key],value);
    assert.equal(options.headers['Idempotency-Key'],'retry-key');
    return {body:{id:'run'}};
  });
  assert.equal((await api.createGeneration({...selection,source_id:'a',output_types:['executive_summary'],budget_type:'tokens',budget_ceiling:40000},'retry-key')).id,'run');
});

test('source passage requests bind the document to its run and version', async () => {
  const api=client(async (url) => {
    const parsed=new URL(url);
    assert.equal(parsed.pathname,'/api/v1/sources/b/text');
    assert.equal(parsed.searchParams.get('generation_id'),'run');
    assert.equal(parsed.searchParams.get('expected_version'),'hash');
    return {body:{id:'b',text:'Second document',source_version:'hash'}};
  });
  assert.equal((await api.getSourceText('b','run','hash')).id,'b');
});

test('collection updates include revision and preserve source order', async () => {
  const data={name:'Reports',source_ids:['b','a'],expected_revision:2};
  const api=client(async (url,options) => {
    assert.ok(url.endsWith('/collections/collection'));assert.equal(options.method,'PUT');
    assert.deepEqual(JSON.parse(options.body),data);return {body:{revision:3}};
  });
  assert.equal((await api.saveCollection(data,'collection')).revision,3);
});

test('draft saves send a revision, base hash and caller-owned retry key', async () => {
  const data = {content:'Edited 🧪',expected_revision:3,base_hash:'f'.repeat(64),request_id:'same-save'};
  const api = client(async (url, options) => {
    assert.equal(url,'http://localhost:8000/api/v1/artifacts/a/draft');
    assert.equal(options.method,'PUT'); assert.deepEqual(JSON.parse(options.body),data);
    return {body:{...data,revision:4}};
  });
  assert.equal((await api.saveOutputDraft('a',data)).revision,4);
});

test('saved edits normalize their own review state and never inherit an original pass', async () => {
  const api = client(async () => ({body:{id:'v',content:'Edited',artifact:{id:'a',review_status:'passed',assurance_status:'unreviewed'}}}));
  const version = await api.getOutputVersion('a','v');
  assert.equal(version.artifact.assurance_status,'unreviewed');
  assert.notEqual(version.artifact.review_status,'pass');
});

test('version actions and comparisons target the exact saved version', async () => {
  const data = {operation:'section',section_id:'section-hash',notes:'Shorter',budget_type:'tokens',budget_ceiling:40000,request_id:'same-task'};
  const api = client(async (url, options) => {
    if (options.method === 'POST') { assert.ok(url.endsWith('/versions/v/tasks')); assert.deepEqual(JSON.parse(options.body),data); return {body:{job_id:'job'}}; }
    assert.ok(url.endsWith('/compare?left=original&right=v')); return {body:{diff:'+New text',truncated:false}};
  });
  assert.equal((await api.startVersionTask('a','v',data)).job_id,'job');
  assert.equal((await api.compareOutputs('a','original','v')).diff,'+New text');
});

test('operational pass rate is not converted into benchmark accuracy', async () => {
  const api = client(async () => ({body:{total_artifacts:2,artifact_success_rate:1,average_cost_per_artifact:0}}));
  const result = await api.getMetrics();
  assert.equal(result.fact_accuracy_pct, null);
  assert.equal(result.style_adherence_pct, null);
  assert.equal(result.avg_latency_ms, null);
  assert.equal(result.avg_cost_per_artifact_usd, 0);
});

test('empty operational dataset does not fabricate a cost measurement', async () => {
  const api = client(async () => ({body:{total_artifacts:0,average_cost_per_artifact:0}}));
  assert.equal((await api.getMetrics()).avg_cost_per_artifact_usd, null);
});

test('history transport errors are not shown as an empty history', async () => {
  const api = client(async () => ({status:503,body:{detail:'Database unavailable'}}));
  await assert.rejects(api.getHistory(), error => error.message === 'Database unavailable');
});

test('missing artifact measurements and reviewer outcomes remain absent', async () => {
  const api = client(async () => ({body:{id:'a',output_type:'executive_summary',content:'Draft'}}));
  const artifact = await api.getArtifact('a');
  assert.deepEqual(artifact.reviewer_outcomes, []);
  assert.equal(artifact.latency_ms, null);
  assert.equal(artifact.quality_score, undefined);
});

test('feedback sends the comment field accepted by the backend', async () => {
  const api = client(async (url, options) => {
    assert.equal(url.endsWith('/api/v1/artifacts/a/feedback'), true);
    assert.deepEqual(JSON.parse(options.body), {rating:'positive',comment:'Useful'});
    return {body:{}};
  });
  await api.submitFeedback('a','positive','Useful');
});

test('missing benchmark result stays null', async () => {
  const api = client(async () => ({body:null}));
  assert.equal(await api.getEvaluationMetrics(), null);
});

test('repeated create calls send the same caller-owned idempotency key', async () => {
  const keys = [];
  const api = client(async (url, options) => {
    assert.equal(url.endsWith('/api/v1/generations/'), true);
    keys.push(options.headers['Idempotency-Key']);
    return {body:{id:'same-run'}};
  });
  const payload = {source_id:'source', output_types:['executive_summary'],budget_type:'tokens',budget_ceiling:10000};
  await api.createGeneration(payload, 'stable-key'); await api.createGeneration(payload, 'stable-key');
  assert.deepEqual(keys, ['stable-key','stable-key']);
});

test('cancel uses the durable generation endpoint', async () => {
  const api = client(async (url, options) => {
    assert.equal(url.endsWith('/api/v1/generations/run/cancel'), true);
    assert.equal(options.method,'POST'); return {body:{message:'Cancellation requested'}};
  });
  assert.equal((await api.cancelGeneration('run')).message, 'Cancellation requested');
});

test('settings save uses revision and never copies the credential into the URL', async () => {
  const api = client(async (url, options) => {
    assert.equal(url.endsWith('/api/v1/settings/provider'), true);
    assert.equal(options.method,'PUT'); assert.equal(url.includes('private-key'),false);
    assert.equal(JSON.parse(options.body).expected_revision,3);
    return {body:{revision:4,key_configured:true}};
  });
  assert.equal((await api.saveProviderSettings({expected_revision:3,api_key:'private-key'})).revision,4);
});

test('source library sends literal search, pagination and trash parameters', async () => {
 const api=client(async(url)=>{const u=new URL(url);assert.equal(u.pathname,'/api/v1/sources/library');assert.equal(u.searchParams.get('q'),'Garden & notes');assert.equal(u.searchParams.get('offset'),'12');assert.equal(u.searchParams.get('trash'),'true');return {body:{items:[],total:0}};});
 await api.getSourceLibrary('Garden & notes',12,'public',true);
});
test('preset updates send the revision and preserve section and brand settings',async()=>{
 const api=client(async(url,options)=>{assert.equal(url.endsWith('/api/v1/presets/preset'),true);const body=JSON.parse(options.body);assert.equal(body.expected_revision,4);assert.deepEqual(body.settings.params.sections,['Open questions']);assert.equal(body.settings.params.brand_name,'Garden');return {body:{revision:5}};});
 await api.savePreset('Leadership',{params:{sections:['Open questions'],brand_name:'Garden'},output_types:['executive_summary']},{id:'preset',revision:4});
});
test('create passes additional sections and brand guidance to the backend contract', async()=>{
 const api=client(async(url,options)=>{const body=JSON.parse(options.body);assert.deepEqual(body.params.sections,['Next steps']);assert.equal(body.params.brand_name,'Garden');assert.equal(body.params.detail_level,'low');return {body:{id:'run'}};});
 await api.createGeneration({source_id:'s',output_types:['presentation'],parameters:{sections:['Next steps'],brand_name:'Garden',detail:'low'},budget_type:'cost_usd',budget_ceiling:.3},'phase3-key');
});

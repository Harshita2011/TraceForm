'use client';
import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { Check, FileText, Loader2, X } from 'lucide-react';
import { useSourceLibrary } from '@/hooks/useSourceLibrary';
import { ConflictResolution, MultiSourceSelection, Source, SourceAnalysis, SourceCollection } from '@/lib/types';
import * as api from '@/lib/api';
import { SourcePassage } from './SourcePassage';

export function MultiSourcePicker({onReady,onBusy,initialCollection,initialSelection}: {onReady:(selection:MultiSourceSelection|null)=>void;onBusy:(busy:boolean)=>void;initialCollection?:string|null;initialSelection?:MultiSourceSelection|null}) {
  const [q,setQ]=useState('');const [offset,setOffset]=useState(0);const {data,loading,error,refetch}=useSourceLibrary(q,offset);
  const [selected,setSelected]=useState<Source[]>([]);const [collections,setCollections]=useState<SourceCollection[]>([]);
  const [collection,setCollection]=useState<SourceCollection|null>(null);const [name,setName]=useState('');const [archived,setArchived]=useState(false);
  const [analysis,setAnalysis]=useState<SourceAnalysis|null>(null);const [analysisId,setAnalysisId]=useState('');
  const [previous,setPrevious]=useState<{id:string;status:string;filenames:string[];created_at:string}[]>([]);
  const [decisions,setDecisions]=useState<Record<string,ConflictResolution>>({});const [budget,setBudget]=useState('0.50');
  const [busy,setBusy]=useState(false);const [failure,setFailure]=useState('');const [notice,setNotice]=useState('');
  const request=useRef<{signature:string;id:string}|null>(null);
  const resume=useRef(initialSelection);
  const working=!!analysis && ['queued','running','pending'].includes(analysis.status);
  const complete=analysis?.status==='completed' && selected.every(s=>s.status==='ready') &&
    analysis.documents.map(s=>s.id).join(':')===selected.map(s=>s.id).join(':') &&
    analysis.conflicts.every(c=>decisions[c.id] && (decisions[c.id].choice!=='prefer'||!!decisions[c.id].preferred_source_id));
  useEffect(()=>{onBusy(working||busy);return()=>onBusy(false);},[working,busy,onBusy]);
  useEffect(()=>{
    onReady(complete&&analysis?{source_ids:selected.map(s=>s.id),analysis_id:analysis.id,conflict_resolutions:decisions,
      documents:analysis.documents,analysis_budget_used:analysis.job.budget_used,analysis_budget_type:analysis.job.budget_type}:null);
  },[complete,analysis,selected,decisions,onReady]);
  useEffect(()=>{let active=true;Promise.all([api.listCollections(archived),api.listSourceAnalyses()]).then(([c,a])=>{if(active){setCollections(c);setPrevious(a);}}).catch(e=>{if(active)setFailure(e.message);});return()=>{active=false;};},[archived]);
  const acceptAnalysis=(value:SourceAnalysis)=>{setAnalysis(value);setAnalysisId(value.id);setPrevious(items=>items.map(item=>item.id===value.id?{...item,status:value.status}:item));setDecisions(current=>Object.fromEntries(value.conflicts.map(c=>[c.id,current[c.id]||{choice:'preserve'}])));};
  useEffect(()=>{
    if(!working||!analysisId)return;let active=true;let fetching=false;
    const timer=setInterval(()=>{if(fetching)return;fetching=true;api.getSourceAnalysis(analysisId).then(value=>{if(active)acceptAnalysis(value);}).catch(e=>{if(active)setFailure(e.message);}).finally(()=>{fetching=false;});},2500);
    return()=>{active=false;clearInterval(timer);};
  },[working,analysisId]);
  const act=async(action:()=>Promise<void>)=>{setBusy(true);setFailure('');setNotice('');try{await action();}catch(e){setFailure((e as Error).message||'Could not complete this action. Your selection is kept.');}finally{setBusy(false);}};
  const invalidate=()=>{setAnalysis(null);setAnalysisId('');setDecisions({});setNotice('Selection changed. Analyze these documents before continuing.');};
  const loadCollection=async(id:string)=>{if(!id){setCollection(null);return;}const value=await api.getCollection(id);setCollection(value);setName(value.name);setSelected(value.sources||[]);invalidate();};
  useEffect(()=>{
    let active=true;
    const restore=async()=>{
      if(!resume.current&&!initialCollection)return;
      setBusy(true);
      try {
        if(resume.current){
          const value=await api.getSourceAnalysis(resume.current.analysis_id);
          const sources=await Promise.all(value.documents.map(s=>api.getSourceDetail(s.id)));
          if(active){setSelected(sources);setAnalysis(value);setAnalysisId(value.id);setDecisions(resume.current.conflict_resolutions);}
        }else if(initialCollection){
          const value=await api.getCollection(initialCollection);
          if(active){setCollection(value);setName(value.name);setSelected(value.sources||[]);}
        }
      }catch(e){if(active)setFailure((e as Error).message);}finally{if(active)setBusy(false);}
    };
    void restore();return()=>{active=false;};
  },[initialCollection]);
  const toggle=(source:Source)=>{if(working||busy)return;if(selected.some(s=>s.id===source.id)){setSelected(v=>v.filter(s=>s.id!==source.id));invalidate();}else if(selected.length<8){setSelected(v=>[...v,source]);invalidate();}else setFailure('Choose up to eight documents.');};
  const save=async(asNew:boolean)=>{const value=await api.saveCollection({name:name.trim(),source_ids:selected.map(s=>s.id),...(!asNew&&collection?{expected_revision:collection.revision}:{})},!asNew?collection?.id:undefined);setCollection(value);setCollections(await api.listCollections(archived));setNotice('Collection saved. Future changes will not change existing run snapshots.');};
  const analyze=async()=>{const amount=Number(budget);if(!Number.isFinite(amount)||amount<=0)throw new Error('Enter a positive analysis budget.');const data={source_ids:selected.map(s=>s.id),budget_type:'cost_usd',budget_ceiling:amount};const signature=JSON.stringify(data);if(request.current?.signature!==signature)request.current={signature,id:crypto.randomUUID()};const accepted=await api.startSourceAnalysis({...data,request_id:request.current!.id});request.current=null;setAnalysisId(accepted.id);setAnalysis(null);acceptAnalysis(await api.getSourceAnalysis(accepted.id));setPrevious(await api.listSourceAnalyses());};
  const reopen=async(id:string)=>{if(!id)return;const value=await api.getSourceAnalysis(id);const sources=await Promise.all(value.documents.map(s=>api.getSourceDetail(s.id)));setSelected(sources);acceptAnalysis(value);setNotice('Opened the saved analysis. Review its conflicts and choices before continuing.');};
  return <div className="multi-source-picker">
    <h2>Combine source documents</h2><p className="muted">Choose 2–8 documents. We extract each separately, preserve attribution, and show potential conflicts before writing an output. Up to 200,000 combined characters; no silent truncation.</p>
    <details className="source-collections"><summary>Saved collections</summary><div className="synthesis-fields"><label>Collection<select className="flow-input" disabled={busy||working} value={collection?.id||''} onChange={e=>void act(()=>loadCollection(e.target.value))}><option value="">Choose a collection</option>{collections.map(c=><option key={c.id} value={c.id}>{c.name} ({c.source_ids.length})</option>)}</select></label><label>Collection name<input className="flow-input" value={name} maxLength={120} disabled={busy||working} onChange={e=>setName(e.target.value)} placeholder="For example: Garden planning"/></label></div><div className="synthesis-actions"><button type="button" className="flow-button secondary" disabled={busy||working||!name.trim()||!selected.length||archived} onClick={()=>void act(()=>save(false))}>{collection?'Update collection':'Save collection'}</button>{collection&&!archived&&<button type="button" className="quiet-link" disabled={busy||working||!name.trim()||!selected.length} onClick={()=>void act(()=>save(true))}>Save as new</button>}{collection&&<button type="button" className="quiet-link" disabled={busy||working} onClick={()=>void act(async()=>{await api.archiveCollection(collection.id,collection.archived);setCollection(null);setCollections(await api.listCollections(archived));setNotice(collection.archived?'Collection restored.':'Collection archived. Documents and existing runs are kept.');})}>{collection.archived?'Restore collection':'Archive collection'}</button>}<label className="version-check"><input type="checkbox" checked={archived} disabled={working||busy} onChange={e=>{setArchived(e.target.checked);setCollection(null);}}/>Show archived</label></div></details>
    <div className="selected-document-list" aria-label="Selected documents">{selected.map((s,i)=><div key={s.id}><FileText size={16}/><span><strong>{s.filename}</strong><small>{s.sensitivity} · {s.word_count?.toLocaleString()||0} words{s.status!=='ready'?' · Unavailable':''}</small></span><button type="button" className="icon-button" aria-label={`Remove ${s.filename}`} disabled={working||busy} onClick={()=>{setSelected(v=>v.filter((_,index)=>index!==i));invalidate();}}><X size={15}/></button></div>)}</div>
    <p className="muted">{selected.length} of 8 documents selected. The strictest source sensitivity applies to the combined output.</p>
    <label className="flow-label">Find saved sources<input className="flow-input" disabled={working} value={q} onChange={e=>{setQ(e.target.value);setOffset(0);}} placeholder="Search document names…"/></label>
    {error&&<p role="alert" className="flow-error">Could not load sources. <button type="button" onClick={refetch}>Retry</button></p>}
    {loading&&<p role="status" className="muted">Loading source documents…</p>}
    <div className="saved-sources">{data.items.map(s=><button type="button" key={s.id} className={`saved-source ${selected.some(v=>v.id===s.id)?'selected':''}`} disabled={working||busy||s.status!=='ready'} aria-pressed={selected.some(v=>v.id===s.id)} onClick={()=>toggle(s)}><FileText size={17}/><span><strong>{s.filename}</strong><small>{s.sensitivity} · {s.word_count.toLocaleString()} words</small></span>{selected.some(v=>v.id===s.id)&&<Check size={17}/>}</button>)}</div>
    <div className="library-pagination"><button type="button" className="quiet-link" disabled={!offset||loading||working} onClick={()=>setOffset(Math.max(0,offset-12))}>Previous sources</button><Link className="quiet-link" href="/dashboard/library">Add or inspect sources</Link><button type="button" className="quiet-link" disabled={offset+12>=data.total||loading||working} onClick={()=>setOffset(offset+12)}>Next sources</button></div>
    <div className="synthesis-analysis-controls"><h3>Analyze before writing</h3><p className="muted">This is a separate AI task with its own budget. It saves extracted facts and a conflict register. Creating outputs uses the generation budget shown in the next steps.</p><label className="flow-label">Analysis budget ceiling (USD)<input className="flow-input" type="number" min="0.01" step="0.01" value={budget} disabled={working||busy} onChange={e=>setBudget(e.target.value)}/></label><div className="synthesis-actions"><button type="button" className="flow-button" disabled={busy||working||selected.length<2||selected.some(s=>s.status!=='ready')||api.IS_DEMO_MODE} onClick={()=>void act(analyze)}>{working?<Loader2 size={15} className="animate-spin"/>:<FileText size={15}/>}Analyze selected documents</button>{analysis?.job.can_cancel&&<button type="button" className="flow-button secondary" disabled={busy} onClick={()=>void act(async()=>{await api.cancelSourceAnalysis(analysis.id);acceptAnalysis(await api.getSourceAnalysis(analysis.id));})}>Cancel analysis</button>}{analysisId&&<button type="button" className="quiet-link" disabled={busy} onClick={()=>void act(async()=>acceptAnalysis(await api.getSourceAnalysis(analysisId)))}>Refresh analysis</button>}</div>
      {analysis&&<p role="status">Analysis {analysis.status.replace('_',' ')} · {analysis.job.budget_used.toFixed(4)} / {analysis.job.budget_ceiling} {analysis.job.budget_type==='cost_usd'?'USD':'tokens'}{analysis.job.usage_incomplete?' · Some usage is unknown':''}</p>}{analysis?.job.message&&<p className="flow-error">{analysis.job.message}</p>}
      {previous.length>0&&<label className="flow-label">Reopen a saved analysis<select className="flow-input" value="" disabled={busy||working} onChange={e=>e.target.value&&void act(()=>reopen(e.target.value))}><option value="">Choose a previous analysis</option>{previous.map(a=><option key={a.id} value={a.id}>{a.filenames.join(' + ')} · {a.status} · {new Date(a.created_at).toLocaleString()}</option>)}</select></label>}
    </div>
    {analysis?.status==='completed'&&<section className="synthesis-results" aria-label="Source analysis results"><h3>{analysis.unique_facts} distinct facts · {analysis.conflicts.length} potential conflicts</h3><p className="muted">Repeated facts retain references to every supporting document. Conflict checks can miss differences; inspect important facts before use.</p><details className="analysis-fact-list"><summary>Inspect extracted facts and their references ({analysis.facts.length})</summary>{analysis.facts.map(f=><details key={f.fact_key}><summary>{f.claim} · {f.anchors.length} references</summary>{f.anchors.map((a,i)=><SourcePassage key={`${a.source_id}:${i}`} reference={a} generationId={analysis.id}/>)}</details>)}</details>{!analysis.conflicts.length&&<p className="synthesis-success">No potential conflicts were recorded. This is not a guarantee that every source agrees.</p>}{analysis.conflicts.map((c,index)=><article key={c.id} className="source-conflict-card"><span className="summary-label">Potential conflict {index+1}</span><p>{c.reason}</p><div className="conflict-accounts">{c.facts.map(f=><div key={f.fact_key}><strong>{f.claim}</strong>{f.anchors.map((a,i)=><SourcePassage key={`${a.source_id}:${i}`} reference={a} generationId={analysis.id}/>)}</div>)}</div><label className="flow-label">How should this conflict be handled?<select className="flow-input" value={decisions[c.id]?.choice||'preserve'} onChange={e=>setDecisions(v=>({...v,[c.id]:{choice:e.target.value as ConflictResolution['choice']}}))}><option value="preserve">Keep both accounts and flag uncertainty</option><option value="omit">Omit these disputed claims</option><option value="prefer">Prefer one source and note the discrepancy</option></select></label>{decisions[c.id]?.choice==='prefer'&&<label className="flow-label">Preferred source<select className="flow-input" value={decisions[c.id].preferred_source_id||''} onChange={e=>setDecisions(v=>({...v,[c.id]:{choice:'prefer',preferred_source_id:e.target.value}}))}><option value="">Choose a supporting source</option>{analysis.documents.filter(d=>c.facts.some(f=>f.anchors.some(a=>a.source_id===d.id))).map(d=><option key={d.id} value={d.id}>{d.filename}</option>)}</select></label>}</article>)}{complete&&<p className="synthesis-success">Sources analyzed. Review your choices, then continue to choose outputs.</p>}</section>}
    {failure&&<p role="alert" className="flow-error">{failure}</p>}{notice&&<p role="status" className="settings-notice">{notice}</p>}
  </div>;
}

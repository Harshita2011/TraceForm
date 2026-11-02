'use client';
import { SourceConflict, SourceDocument } from '@/lib/types';
import { SourcePassage } from './SourcePassage';

export function RunSourceSummary({documents,conflicts,generationId}: {documents:SourceDocument[];conflicts:SourceConflict[];generationId:string}) {
  if(documents.length<2)return null;
  return <details className="run-source-register"><summary>{documents.length} source documents · {conflicts.length} potential conflicts</summary><p className="muted">This run uses saved document snapshots. Editing a collection does not change these inputs.</p><ul>{documents.map(d=><li key={d.id}><strong>{d.filename}</strong><span>{d.sensitivity} · version {d.source_version.slice(0,10)}</span></li>)}</ul>{conflicts.map(c=><article className="source-conflict-card" key={c.id}><p>{c.reason}</p><p className="conflict-decision">Decision: {c.resolution.choice==='omit'?'Omit disputed claims':c.resolution.choice==='prefer'?`Prefer ${documents.find(d=>d.id===c.resolution.preferred_source_id)?.filename||'selected source'} and acknowledge the discrepancy`:'Keep both accounts and flag uncertainty'}</p><div className="conflict-accounts">{c.facts.map(f=><div key={f.fact_key}><strong>{f.claim}</strong>{f.anchors.map((a,i)=><SourcePassage key={`${a.source_id}:${i}`} reference={a} generationId={generationId}/>)}</div>)}</div></article>)}</details>;
}

'use client';
import {Suspense,useEffect,useState} from 'react';
import {useSearchParams} from 'next/navigation';
import {getArtifact,getGeneration} from '@/lib/api';
import {Artifact} from '@/lib/types';
import {OutputWorkspace} from '@/components/dashboard/OutputWorkspace';
function ExactOutput(){
  const params=useSearchParams();const id=params.get('artifact')||'';const [artifact,setArtifact]=useState<Artifact|null>(null);const [source,setSource]=useState('');const [error,setError]=useState('');
  useEffect(()=>{let active=true;if(!id)return;getArtifact(id).then(async a=>{const run=await getGeneration(a.generation_id);if(active){setArtifact(a);setSource(run.source_id);}}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[id]);
  return <div className="team-page"><a className="quiet-link" href="/dashboard/reviews">← Review inbox</a><h1>Saved output</h1>{error?<p role="alert" className="flow-error">{error}</p>:!id?<p>Choose an output from your workspace.</p>:!artifact?<p role="status">Opening exact output…</p>:<OutputWorkspace artifact={artifact} sourceId={source} onRegenerate={()=>window.location.assign(new URL('/dashboard/sources',window.location.origin).href)} regenerating={false} onUpdated={()=>{}}/>}</div>;
}
export default function Page(){return <Suspense fallback={<p role="status">Opening output…</p>}><ExactOutput/></Suspense>;}

'use client';
import {useEffect,useState} from 'react';
import Link from 'next/link';
import {useTeam} from './TeamSession';
import {TeamMember,TeamComment,teamMembers,teamApproval,teamComments,addComment,resolveComment,requestTeamReview} from '@/lib/teams';
export function TeamVersionPanel({versionId}:{versionId:string}){
  const {me}=useTeam();const [members,setMembers]=useState<TeamMember[]>([]);const [comments,setComments]=useState<TeamComment[]>([]);
  const [status,setStatus]=useState('');const [assignee,setAssignee]=useState('');const [body,setBody]=useState('');const [parent,setParent]=useState('');
  const [busy,setBusy]=useState(false);const [error,setError]=useState('');const [notice,setNotice]=useState('');const [reviewId,setReviewId]=useState('');const [more,setMore]=useState(false);
  useEffect(()=>{if(!me)return;let active=true;setStatus('');setNotice('');setReviewId('');setError('');setParent('');
    Promise.all([teamMembers(),teamApproval(versionId),teamComments(versionId)]).then(([m,a,c])=>{if(active){setMembers(m);setStatus(a.status);setComments(c);setMore(c.length===100);}}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[me,versionId]);
  if(!me)return null;
  const canWrite=me.role==='owner'||me.role==='editor';const canComment=me.role!=='viewer';
  const act=async(fn:()=>Promise<void>)=>{setBusy(true);setError('');try{await fn();}catch(e){setError((e as Error).message);}finally{setBusy(false);}};
  return <section className="team-card team-version"><h3>Team review & discussion</h3><p><span className="status-pill">{status?status.replaceAll('_',' '):'Loading approval…'}</span></p><p className="muted">Human decisions apply to this exact saved version. AI review results are shown separately. New edits need a new approval.</p>
    {error&&<p role="alert" className="flow-error">{error}</p>}{notice&&<p role="status">{notice} {reviewId&&<Link href={'/dashboard/reviews?review='+reviewId}>Open assigned review →</Link>}</p>}
    {canWrite&&<form className="team-form" onSubmit={e=>{e.preventDefault();void act(async()=>{const r=await requestTeamReview(versionId,assignee);setReviewId(r.id);setNotice('Review assigned. The reviewer can find it in their inbox.');});}}><label>Assign a reviewer<select required className="flow-input" value={assignee} onChange={e=>setAssignee(e.target.value)}><option value="">Choose a reviewer</option>{members.filter(m=>['owner','reviewer'].includes(m.role)).map(m=><option key={m.id} value={m.id}>{m.name} · {m.role}</option>)}</select></label><button disabled={busy||!assignee} className="flow-button">Request approval</button></form>}
    <h4>Comments</h4>{!comments.length&&!error&&<p className="muted">No comments on this version yet.</p>}
    <div className="team-comments">{comments.map(c=><article key={c.id} className={c.parent_id?'team-reply':''}><p><strong>{members.find(m=>m.id===c.actor)?.name||'Former member'}</strong><small>{new Date(c.created_at).toLocaleString()}{c.parent_id?' · Reply':''}</small></p><p className="team-comment-body">{c.body}</p>{!c.parent_id&&<div className="team-actions"><span>{c.resolved?'Resolved':'Open thread'}</span>{canComment&&<><button disabled={busy} className="quiet-link" onClick={()=>{setParent(c.id);setNotice('Replying to '+c.body.slice(0,60));}}>Reply</button><button disabled={busy} className="quiet-link" onClick={()=>void act(async()=>{await resolveComment(c.id,!c.resolved);setComments(await teamComments(versionId));})}>{c.resolved?'Reopen':'Resolve'}</button></>}</div>}</article>)}</div>
    {more&&<button disabled={busy} className="quiet-link" onClick={()=>void act(async()=>{const next=await teamComments(versionId,comments.length);setComments([...comments,...next]);setMore(next.length===100);})}>Load more comments</button>}
    {canComment&&<form className="team-comment-form" onSubmit={e=>{e.preventDefault();void act(async()=>{await addComment(versionId,body,parent||undefined);setBody('');setParent('');setNotice('Comment saved.');const c=await teamComments(versionId);setComments(c);setMore(c.length===100);});}}><label>{parent?'Reply to thread':'Add a comment'}<textarea required maxLength={5000} className="flow-input" value={body} onChange={e=>setBody(e.target.value)}/></label><div className="team-actions"><button className="flow-button" disabled={busy||!body.trim()}>Post comment</button>{parent&&<button type="button" className="quiet-link" onClick={()=>{setParent('');setNotice('');}}>Cancel reply</button>}</div></form>}
  </section>;
}

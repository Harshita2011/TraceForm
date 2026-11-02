'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Copy, Download, FileText, Pencil, RotateCcw, Save, ShieldCheck } from 'lucide-react';
import { Artifact, EvidenceSpan, OutputVersion, OutputVersionMeta, OutputVersionTask } from '@/lib/types';
import { outputLabel } from '@/lib/output-formats';
import { EvidencePanel } from './EvidencePanel';
import { DocumentContent } from './DocumentContent';
import { useOutputDraft } from '@/hooks/useOutputDraft';
import { cancelVersionTask, compareOutputs, downloadOutput, getOutputVersion, IS_DEMO_MODE, listOutputVersions,
  listVersionTasks, restoreOutputVersion, saveOutputVersion, startVersionTask } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useTeam } from './TeamSession';
import { TeamVersionPanel } from './TeamVersionPanel';

export function OutputWorkspace({ artifact, sourceId, onRegenerate, regenerating, onUpdated }: {
  artifact: Artifact; sourceId: string; onRegenerate: () => void; regenerating: boolean; onUpdated: () => void;
}) {
  const draft = useOutputDraft(artifact.id);
  const {me}=useTeam();
  const canEdit=!me||me.role==='owner'||me.role==='editor';
  const [view, setView] = useState('original');
  const [version, setVersion] = useState<OutputVersion | null>(null);
  const [versions, setVersions] = useState<OutputVersionMeta[]>([]);
  const [versionTotal, setVersionTotal] = useState(0);
  const [editing, setEditing] = useState(false);
  const [evidence, setEvidence] = useState(false);
  const [selectedSpans, setSelectedSpans] = useState<EvidenceSpan[]>([]);
  const [panel, setPanel] = useState<'versions' | 'ai' | 'export' | null>(null);
  const [message, setMessage] = useState('');
  const [failure, setFailure] = useState('');
  const [busy, setBusy] = useState(false);
  const [label, setLabel] = useState('');
  const [diff, setDiff] = useState('');
  const [tasks, setTasks] = useState<OutputVersionTask[]>([]);
  const [operation, setOperation] = useState<'review' | 'full' | 'section'>('review');
  const [sectionId, setSectionId] = useState('');
  const [notes, setNotes] = useState('');
  const [budgetType, setBudgetType] = useState('tokens');
  const [budget, setBudget] = useState('50000');
  const [format, setFormat] = useState('docx');
  const [citations, setCitations] = useState(false);
  const [provenance, setProvenance] = useState(false);
  const [compareLeft, setCompareLeft] = useState('original');
  const [deviceIndex, setDeviceIndex] = useState(0);
  const actionRequest = useRef<{signature: string; id: string} | null>(null);
  const completion = useRef('');
  const isDraft = view === 'draft';
  const isOriginal = view === 'original';
  const selected = isOriginal ? artifact : isDraft ? null : version?.artifact;
  const content = isOriginal ? artifact.content : isDraft ? draft.content : version?.content || '';
  const ready = !!draft.workspace && !busy && !regenerating && !IS_DEMO_MODE;
  useEffect(()=>{const id=new URLSearchParams(window.location.search).get('version');if(!id)return;let active=true;
    getOutputVersion(artifact.id,id).then(value=>{if(active){setVersion(value);setView(id);}}).catch(e=>{if(active)setFailure(e.message);});return()=>{active=false;};},[artifact.id]);
  const reviewState = isDraft ? 'unreviewed' : selected?.assurance_status;
  const title = isOriginal ? 'Original generated output' : isDraft ? 'Working draft' : version?.label || 'Saved version';
  const savedLabel = reviewState === 'checks_passed' ? 'Required checks passed' : reviewState === 'overridden' ?
    'Exception recorded · checks still failed' : reviewState === 'needs_review' ? 'Needs review' : 'Unreviewed';

  const refreshVersions = useCallback(async (offset = 0) => {
    const result = await listOutputVersions(artifact.id, offset);
    setVersions(current => offset ? [...current, ...result.items.filter(item => !current.some(c => c.id === item.id))] : result.items);
    setVersionTotal(result.total);
  }, [artifact.id]);
  useEffect(() => {
    if (IS_DEMO_MODE) return;
    let active = true;
    Promise.all([listOutputVersions(artifact.id), listVersionTasks(artifact.id)]).then(([v, t]) => {
      if (active) { setVersions(v.items); setVersionTotal(v.total); setTasks(t); }
    }).catch(e => { if (active) setFailure(e.message || 'Version history could not be loaded.'); });
    return () => { active = false; };
  }, [artifact.id]);
  const activeJobs = tasks.some(t => ['queued', 'running'].includes(t.job.status));
  useEffect(() => {
    if (!activeJobs) return;
    let active = true;
    let polling = false;
    const poll = async () => {
      if (polling) return;
      polling = true;
      try {
        const items = await listVersionTasks(artifact.id);
        if (!active) return;
        const done = items.filter(t => !['queued','running'].includes(t.job.status)).map(t => t.job_id).join(':');
        if (done !== completion.current) {
          await refreshVersions();
          if (view !== 'original' && view !== 'draft') {
            const result = await getOutputVersion(artifact.id, view); if (active) setVersion(result);
          }
          completion.current = done;
        }
        if (active) setTasks(items);
      } catch (e) { if (active) setFailure((e as Error).message || 'Task status could not be refreshed.'); }
      finally { polling = false; }
    };
    const timer = setInterval(() => { void poll(); }, 2500);
    return () => { active = false; clearInterval(timer); };
  }, [activeJobs, artifact.id, view, refreshVersions]);
  useEffect(() => {
    if (selectedSpans.length) { const target = document.getElementById(`output-highlight-${artifact.id}`); target?.focus({preventScroll:true}); target?.scrollIntoView({block:'center', behavior:'smooth'}); }
  }, [selectedSpans, artifact.id]);

  const act = async (work: () => Promise<void>) => {
    setBusy(true); setFailure(''); setMessage('');
    try { await work(); }
    catch (e) { setFailure((e as Error).message || 'The action failed. Your work is kept; retry when the service is available.'); }
    finally { setBusy(false); }
  };
  const requestId = (signature: string) => {
    if (actionRequest.current?.signature !== signature) actionRequest.current = {signature, id:crypto.randomUUID()};
    return actionRequest.current!.id;
  };
  const open = async (value: string) => {
    if (value !== 'original' && value !== 'draft') setVersion(await getOutputVersion(artifact.id, value));
    setView(value); setEditing(false); setSelectedSpans([]); setDiff(''); setSectionId('');
  };
  const saveVersion = async () => {
    const saved = isDraft ? await draft.flush() : null;
    const data = {source:isDraft ? 'draft' as const : 'original' as const, expected_revision:saved?.revision || 0,
      label:label.trim() || `Saved version ${versionTotal + 1}`};
    const result = await saveOutputVersion(artifact.id, {...data, request_id:requestId(JSON.stringify(data))});
    actionRequest.current = null; await refreshVersions(); setVersion(result); setView(result.id); setEditing(false);
    setMessage('Version saved to server. Run a review to check this exact content.'); setPanel('versions');
  };
  const restore = async () => {
    if (!version) return;
    const saved = await draft.flush();
    const result = await restoreOutputVersion(artifact.id, version.id, saved.revision, requestId(`restore:${version.id}:${saved.revision}`));
    actionRequest.current = null; draft.accept(result); await refreshVersions(); setView('draft'); setEditing(true);
    setMessage('Restored into your draft. The previous server draft was saved as a recovery version.');
  };
  const runTask = async () => {
    if (!version || isOriginal || isDraft) throw new Error('Save a version and select it before starting an AI task.');
    const amount = Number(budget);
    if (!Number.isFinite(amount) || amount <= 0) throw new Error('Enter a positive budget ceiling.');
    const settings = {operation, notes, section_id:operation === 'section' ? sectionId : undefined, budget_type:budgetType, budget_ceiling:amount};
    const submitted = await startVersionTask(artifact.id, version.id, {...settings, request_id:requestId(JSON.stringify([version.id, settings]))});
    actionRequest.current = null;
    const items = await listVersionTasks(artifact.id);
    if (items.some(item => item.job_id === submitted.job_id && !['queued','running'].includes(item.job.status))) {
      await refreshVersions(); setVersion(await getOutputVersion(artifact.id, version.id));
    }
    setTasks(items); setMessage('Task submitted. You can leave this page; the worker continues on the server.');
  };
  const download = async () => {
    const saved = isDraft ? await draft.flush() : null;
    const hash = isDraft && saved ? await crypto.subtle.digest('SHA-256', new TextEncoder().encode(saved.content)).then(buffer => Array.from(new Uint8Array(buffer)).map(v => v.toString(16).padStart(2,'0')).join('')) :
      isOriginal ? draft.workspace!.original_hash : version!.content_hash;
    await downloadOutput(artifact.id, {format, target:isOriginal ? 'original' : isDraft ? 'draft' : 'version', expected_hash:hash,
      ...(saved ? {expected_revision:String(saved.revision)} : {}), ...(!isOriginal && !isDraft && version ? {version_id:version.id} : {}), citations:String(citations), provenance:String(provenance)});
    setMessage(`Downloaded ${title.toLowerCase()} as ${format.toUpperCase()}.`);
  };

  return <section className="output-workspace version-workspace" aria-label="Output editor and versions">
    <div className="output-heading"><div><span className="summary-label">{title}</span><h2>{outputLabel(artifact.output_type)}</h2>
      <span className={cn('status-pill', reviewState === 'checks_passed' ? 'ready' : 'attention')}><ShieldCheck size={13}/>{savedLabel}</span></div>
      <div className="output-actions">
        <button className="flow-button secondary" disabled={!ready||!canEdit} onClick={() => { setView('draft'); setEditing(!editing || !isDraft); setSelectedSpans([]); }}><Pencil size={14}/>{editing && isDraft ? 'Preview draft' : 'Edit draft'}</button>
        <button className="flow-button secondary" onClick={() => void act(async () => { await navigator.clipboard.writeText(content); setMessage('Copied selected content.'); })}><Copy size={14}/>Copy</button>
        <button className="flow-button secondary" disabled={!ready} aria-expanded={panel === 'export'} onClick={() => setPanel(panel === 'export' ? null : 'export')}><Download size={14}/>Export</button>
        <button className="flow-button secondary" disabled={isDraft} aria-expanded={evidence} onClick={() => setEvidence(!evidence)}><FileText size={14}/>Evidence</button>
      </div>
    </div>
    <div className="version-toolbar">
      <div className="version-view-tabs" role="group" aria-label="Content view"><button disabled={busy} aria-pressed={isOriginal} onClick={() => void act(() => open('original'))}>Original</button><button disabled={!ready} aria-pressed={isDraft} onClick={() => void act(() => open('draft'))}>Working draft</button></div>
      <label className="version-picker"><span className="sr-only">Saved version</span><select className="flow-input" value={isOriginal || isDraft ? '' : view} disabled={!ready} onChange={e => e.target.value && void act(() => open(e.target.value))}><option value="">Saved versions ({versionTotal})</option>{versions.map(v => <option key={v.id} value={v.id}>{v.label} · {new Date(v.created_at).toLocaleString()}</option>)}</select></label>
      <button className="quiet-link" aria-expanded={panel === 'versions'} onClick={() => setPanel(panel === 'versions' ? null : 'versions')}>Version history</button>
      <span className="draft-save-state" role="status">{draft.status}</span>
    </div>
    {IS_DEMO_MODE && <div className="output-notice">Server editing is available in the connected workspace. Demo outputs are read-only.</div>}
    {draft.error && <div className="output-notice version-error" role="alert"><p>{draft.conflict ? 'Another tab saved a newer draft. Your text is still here.' : draft.error}</p><div className="output-actions">{!draft.workspace ? <button className="flow-button secondary" onClick={() => void draft.load()}>Retry loading</button> : draft.conflict ? <button className="flow-button" disabled={busy} onClick={() => void act(async () => { await draft.preserveAndReload(); await refreshVersions(); setMessage('Your conflicting text was saved as a recovery version. The latest server draft is now open.'); })}>Keep my copy & load latest</button> : <button className="flow-button secondary" onClick={() => void act(async () => { await draft.retry(); })}>Retry saving</button>}</div></div>}
    {failure && <div className="output-notice version-error" role="alert">{failure}</div>}
    {message && <div className="output-notice" role="status">{message}</div>}
    <div className="version-command-bar">
      {isOriginal || isDraft ? <><label><span className="sr-only">Version name</span><input className="flow-input" value={label} maxLength={120} onChange={e => setLabel(e.target.value)} placeholder="Version name (optional)"/></label><button className="flow-button" disabled={!ready || !canEdit || draft.conflict} onClick={() => void act(saveVersion)}><Save size={14}/>Save version</button></> : <><button className="flow-button secondary" disabled={!ready || !canEdit || draft.conflict} onClick={() => void act(restore)}><RotateCcw size={14}/>Restore as draft</button><button className="flow-button" disabled={!ready || !canEdit} onClick={() => setPanel(panel === 'ai' ? null : 'ai')}><ShieldCheck size={14}/>Review or regenerate</button></>}
      <p className="muted">{isDraft ? 'Autosaves to server. Edits need a new review.' : isOriginal ? 'The original stays available. Edit the working draft to make changes.' : 'Saved versions are read-only. Restore as draft to edit.'}</p>
    </div>
    {panel === 'versions' && <div className="version-panel">
      <div className="version-panel-heading"><h3>Saved versions</h3><button className="quiet-link" disabled={busy} onClick={() => void act(async () => { await refreshVersions(); setTasks(await listVersionTasks(artifact.id)); })}>Refresh</button></div>
      <p className="muted">Versions and drafts belong to your operator account. Each new version starts unreviewed.</p>
      {!versions.length && <p>No versions yet. Save the original or your working draft above.</p>}
      <div className="version-list">{versions.map(item => <button key={item.id} disabled={busy} aria-pressed={view === item.id} onClick={() => void act(() => open(item.id))}><strong>{item.label}</strong><span>{item.origin} · {new Date(item.created_at).toLocaleString()}</span></button>)}</div>
      {versions.length < versionTotal && <button className="flow-button secondary" disabled={busy} onClick={() => void act(() => refreshVersions(versions.length))}>Load more versions</button>}
      <div className="version-compare"><label>Compare with<select className="flow-input" value={compareLeft} onChange={e => setCompareLeft(e.target.value)}><option value="original">Original</option><option value="draft">Working draft</option>{versions.map(v => <option key={v.id} value={v.id}>{v.label}</option>)}</select></label><button className="flow-button secondary" disabled={!ready} onClick={() => void act(async () => { if (isDraft || compareLeft === 'draft') await draft.flush(); const result = await compareOutputs(artifact.id, compareLeft, view); setDiff(result.diff || 'No differences.'); if (result.truncated) setMessage('Comparison is abbreviated. Export both versions to inspect all content.'); })}>Compare selected content</button></div>
      {diff && <pre className="version-diff" tabIndex={0} aria-label="Version differences">{diff}</pre>}
      {!!draft.deviceCopies.length && <details className="device-import"><summary>Import drafts saved on this device ({draft.deviceCopies.length})</summary><p>Preview a copy, then import it as a separate unreviewed version. Your server draft is preserved.</p><label>Device copy<select className="flow-input" value={deviceIndex} onChange={e => setDeviceIndex(Number(e.target.value))}>{draft.deviceCopies.map((copy, i) => <option key={i} value={i}>{copy.label} {copy.savedAt ? new Date(copy.savedAt).toLocaleString() : ''}</option>)}</select></label><pre tabIndex={0}>{draft.deviceCopies[deviceIndex]?.content}</pre><button className="flow-button" disabled={!ready} onClick={() => void act(async () => { const copy = draft.deviceCopies[deviceIndex]; const data = {source:'import' as const, content:copy.content, label:copy.label}; const result = await saveOutputVersion(artifact.id, {...data, request_id:requestId(JSON.stringify(data))}); actionRequest.current = null; await refreshVersions(); setVersion(result); setView(result.id); setMessage('Device copy imported as a server version. Original browser storage is retained.'); })}>Import selected copy</button></details>}
      <button className="quiet-link new-run-link" disabled={regenerating} onClick={onRegenerate}>Create a separate generation run with current settings</button>
    </div>}
    {panel === 'ai' && version && !isOriginal && !isDraft && <form className="version-panel version-task-form" onSubmit={e => { e.preventDefault(); void act(runTask); }}><h3>Work on “{version.label}”</h3><p className="muted">Review checks this exact saved text. Regeneration creates an unreviewed version and preserves the selected version. Every task uses a fresh budget and the current provider.</p>
      <div className="version-form-grid"><label>Action<select className="flow-input" value={operation} onChange={e => setOperation(e.target.value as typeof operation)}><option value="review">Review saved text</option><option value="full">Regenerate full output</option><option value="section">Regenerate one section</option></select></label>{operation === 'section' && <label>Section (includes subsections)<select className="flow-input" required value={sectionId} onChange={e => setSectionId(e.target.value)}><option value="">Choose a section</option>{version.sections.map(s => <option key={s.id} value={s.id}>{s.title}</option>)}</select></label>}<label>Budget unit<select className="flow-input" value={budgetType} onChange={e => { setBudgetType(e.target.value); setBudget(e.target.value === 'tokens' ? '50000' : '1'); }}><option value="tokens">Tokens</option><option value="cost_usd">US dollars</option></select></label><label>Maximum budget<input className="flow-input" type="number" min={budgetType === 'tokens' ? 1 : .001} step="any" required value={budget} onChange={e => setBudget(e.target.value)}/></label></div>
      {operation !== 'review' && <label>Revision directions<textarea className="flow-input" value={notes} maxLength={4000} onChange={e => setNotes(e.target.value)} placeholder="What should change? Facts must remain grounded in the source."/></label>}
      <button className="flow-button" type="submit" disabled={!ready || activeJobs}>Start {operation === 'review' ? 'review' : 'regeneration'}</button>
    </form>}
    {panel === 'export' && <form className="version-panel version-export" onSubmit={e => { e.preventDefault(); void act(download); }}><h3>Export {title.toLowerCase()}</h3><p className="muted">{savedLabel}. The file records the selected version and review state.</p><label>File format<select className="flow-input" value={format} onChange={e => setFormat(e.target.value)}><option value="docx">Word (.docx)</option><option value="pdf">PDF (.pdf)</option><option value="md">Markdown (.md)</option><option value="txt">Plain text (.txt)</option>{artifact.output_type === 'presentation' && <option value="pptx">Editable PowerPoint outline (.pptx)</option>}</select></label><label className="version-check"><input type="checkbox" checked={citations} onChange={e => setCitations(e.target.checked)}/>Include recorded references</label><label className="version-check"><input type="checkbox" checked={provenance} onChange={e => setProvenance(e.target.checked)}/>Include source and version provenance</label><button className="flow-button" disabled={!ready || draft.conflict} type="submit"><Download size={14}/>{busy ? 'Preparing file…' : 'Download file'}</button></form>}
    {!isOriginal && !isDraft && version && <TeamVersionPanel versionId={version.id}/>}
    {tasks.length > 0 && <details className="version-jobs" open={activeJobs || undefined}><summary>Version tasks ({tasks.length}){activeJobs ? ' · in progress' : ''}</summary>{tasks.map(task => <article key={task.job_id}><div><strong>{task.operation === 'review' ? 'Review saved text' : task.operation === 'section' ? 'Regenerate section' : 'Regenerate full output'}</strong><span className="status-pill">{task.job.status}</span></div><p>{task.job.message || (task.job.status === 'completed' ? task.operation === 'review' ? 'Review finished. Open the version to inspect its findings.' : 'New unreviewed version saved.' : 'Waiting for the durable worker.')}</p><small>{task.job.budget_used.toLocaleString()} / {task.job.budget_ceiling.toLocaleString()} {task.job.budget_type === 'tokens' ? 'tokens' : 'USD'}{task.job.usage_incomplete ? ' · Some usage is unknown' : ''}</small><div className="output-actions"><button className="quiet-link" disabled={busy} onClick={() => void act(() => open(task.result_version_id || task.version_id))}>{task.result_version_id ? 'Open new version' : 'Open reviewed version'}</button>{task.job.can_cancel && <button className="quiet-link" disabled={busy} onClick={() => void act(async () => { await cancelVersionTask(artifact.id, task.job_id); setTasks(await listVersionTasks(artifact.id)); })}>Cancel task</button>}</div></article>)}</details>}
    <div className={cn('output-body', evidence && !isDraft && 'with-evidence')}><div className="output-document">
      {editing && isDraft ? <><label className="sr-only" htmlFor={`editor-${artifact.id}`}>Edit working draft</label><textarea id={`editor-${artifact.id}`} className="output-editor" maxLength={200000} value={draft.content} onChange={e => draft.change(e.target.value)}/><p className="muted">Markdown headings, lists, and tables are supported. Autosave runs after you pause typing.</p></> : <DocumentContent content={content} selected={selectedSpans} artifactId={artifact.id}/>}
      <div className="document-footer"><span>{content.trim() ? content.trim().split(/\s+/).length : 0} words</span><span>{isDraft ? `Draft revision ${draft.workspace?.draft.revision ?? 0}` : isOriginal ? 'Original' : `Version ${version?.content_hash.slice(0,8)}`}</span></div>
    </div>{evidence && !isDraft && selected && <EvidencePanel key={`${view}:${version?.review_id || ''}`} artifact={selected} sourceId={sourceId} changed={false} readOnly={!isOriginal} onLocate={setSelectedSpans} onUpdated={onUpdated}/>}</div>
  </section>;
}

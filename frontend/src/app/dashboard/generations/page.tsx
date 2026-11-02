'use client';

import { Suspense, useRef, useState } from 'react';

import { useSearchParams, useRouter } from 'next/navigation';

import Link from 'next/link';

import { ArrowRight, CheckCircle2, Clock3, FileText, Loader2, Plus, RefreshCw, Search, AlertCircle } from 'lucide-react';

import { useGenerations, useGeneration } from '@/hooks/useGeneration';

import { usePipelineStatus } from '@/hooks/usePipelineStatus';

import { retryGeneration, regenerateOutput, cancelGeneration } from '@/lib/api';

import { Generation } from '@/lib/types';
import { RunSourceSummary } from '@/components/dashboard/RunSourceSummary';

import { documentName, outputLabel } from '@/lib/output-formats';

import { cn, formatRelative } from '@/lib/utils';

import { PipelineStatusView } from '@/components/dashboard/PipelineStatusView';

import { OutputWorkspace } from '@/components/dashboard/OutputWorkspace';



const activeRun = (g: Generation) => ['running', 'queued', 'pending'].includes(g.status);

const needsHelp = (g: Generation) => ['failed', 'partial_failure', 'budget_exceeded', 'cancelled'].includes(g.status);

const needsReview = (g: Generation) => !activeRun(g) && g.artifacts.some(a => a.assurance_status !== 'checks_passed');

function statusLabel(g: Generation) {

  return g.status === 'cancelled' ? 'Cancelled' : activeRun(g) ? 'In progress' : needsHelp(g) ? 'Needs attention' : needsReview(g) ? 'Review needed' : 'Ready';

}



function RunDetail({ id, onRetry }: { id: string; onRetry: (id: string) => void }) {

  const { generation: run, loading, error, refetch } = useGeneration(id);

  const { status, error: progressError } = usePipelineStatus(id, 2000, !!run && activeRun(run));

  const [selected, setSelected] = useState('');

  const [retrying, setRetrying] = useState(false);

  const [retryError, setRetryError] = useState('');

  const [cancelling, setCancelling] = useState(false);

  const [cancelNotice, setCancelNotice] = useState('');

  const requestKeys = useRef<Record<string, string>>({});

  const keyFor = (action: string) => requestKeys.current[action] ||= crypto.randomUUID();

  const cancel = async () => {

    setCancelling(true); setRetryError('');

    try { const result = await cancelGeneration(id); setCancelNotice(result.message); refetch(); }

    catch (e) { setRetryError((e as Error).message || 'Could not cancel. Try again.'); }

    finally { setCancelling(false); }

  };

  const retry = async () => {

    setRetrying(true); setRetryError('');

    try { const result = await retryGeneration(id, keyFor('retry')); onRetry(result.id); }

    catch (e) { setRetryError((e as { message?: string }).message || 'Couldn’t retry. Please try again.'); }

    finally { setRetrying(false); }

  };

  const regenerate = async (outputType: string) => {

    setRetrying(true); setRetryError('');

    try { const result = await regenerateOutput(id, outputType, keyFor(`version:${outputType}`)); onRetry(result.id); }

    catch (e) { setRetryError((e as { message?: string }).message || 'Could not start a new version.'); }

    finally { setRetrying(false); }

  };

  if (loading && !run) return <div className="flow-panel loading-panel" role="status"><Loader2 className="animate-spin" size={24} />Loading your output…</div>;

  if (error || !run) return <div className="flow-panel"><h2>Couldn’t load this run</h2><p className="muted">{error?.message}</p><button className="flow-button secondary" onClick={refetch}>Try again</button></div>;

  const artifacts = run.artifacts.filter(a => a.content);

  const artifact = artifacts.find(a => a.id === selected) || artifacts[0];

  const ready = run.artifacts.filter(a => a.review_status === 'pass' || a.review_status === 'regenerated').length;

  return <div className="run-detail">

    <div className="run-header"><div><span className="summary-label">Source document</span><h2>{documentName(run.source_filename)}</h2><p className="muted">{formatRelative(run.created_at)} · {run.output_types.length} {run.output_types.length === 1 ? 'output' : 'outputs'} requested</p></div>

      <span className={cn('status-pill', activeRun(run) ? 'working' : needsHelp(run) || needsReview(run) ? 'attention' : 'ready')}>{activeRun(run) ? <Loader2 size={13} className="animate-spin" /> : needsHelp(run) || needsReview(run) ? <AlertCircle size={13} /> : <CheckCircle2 size={13} />}{statusLabel(run)}</span></div>

    {retryError && !needsHelp(run) && <div className="flow-error" role="alert">{retryError}</div>}

    <details className="run-progress" open={activeRun(run) || needsHelp(run)}><summary><span>{activeRun(run) ? 'Your output is on its way' : needsHelp(run) ? 'Run details & recovery' : `${ready} ${ready === 1 ? 'output' : 'outputs'} passed review`}</span><small>View progress</small></summary>

      <PipelineStatusView status={status} generationStatus={run.status} />

      {status?.job && <div className="job-notice"><div><strong>{run.status === 'cancelled' ? 'Cancelled' : status.job.cancel_requested ? 'Cancellation requested' : activeRun(run) ? status.job.status === 'queued' ? 'Waiting for the worker' : 'Generation in progress' : 'Run saved'}</strong><p className="muted mt-2">{cancelNotice || status.job.message || (!activeRun(run) ? 'Recorded outputs and usage are saved. Open an output below to review it.' : status.job.worker_online ? 'Your work is saved. You can leave this page while generation continues.' : 'The worker is offline. This job is saved and will wait until a worker reconnects.')}</p>

        {activeRun(run) && <p className="muted mt-2">Cancel stops remaining work and keeps saved outputs. Requests already submitted may still be billed.</p>}

        <div className="job-budget"><span>Used: {status.job.budget_type === 'cost_usd' ? `$${status.job.budget_used.toFixed(4)}` : `${status.job.budget_used.toLocaleString()} tokens`}</span><span>Reserved: {status.job.budget_type === 'cost_usd' ? `$${status.job.reserved_budget.toFixed(4)}` : `${status.job.reserved_budget.toLocaleString()} tokens`}</span><span>Limit: {status.job.budget_ceiling === null ? 'None' : status.job.budget_type === 'cost_usd' ? `$${status.job.budget_ceiling.toFixed(2)}` : status.job.budget_ceiling.toLocaleString()}</span></div>

        {(status.job.usage_incomplete || status.job.budget_overrun) && <p className="text-amber-300 mt-2">{status.job.budget_overrun ? 'Reported usage exceeded the admission estimate. Further calls are blocked by the remaining budget.' : 'Some provider usage or charges are unknown. Displayed totals may be incomplete.'}</p>}

      </div>{status.job.can_cancel && <button className="flow-button secondary" disabled={cancelling || !!cancelNotice} onClick={cancel}>{cancelling ? 'Cancelling…' : 'Cancel run'}</button>}</div>}

      {progressError && <p className="muted" role="status">Progress updates are temporarily unavailable. <button className="quiet-link" onClick={refetch}>Refresh this run</button></p>}

    </details>

    {needsHelp(run) && <div className="recovery-banner"><AlertCircle size={20} /><div><strong>{run.status === 'cancelled' ? 'Run cancelled' : artifacts.length ? 'Some outputs need attention' : 'This run couldn’t finish'}</strong><p>{status?.error || 'Retry to generate the outputs that did not pass. Your original run and any successful outputs are kept.'}</p>

      <p>A retry creates a new run with a fresh budget, using the current provider settings. Only outputs that did not pass are requested. Interrupted requests may have been billed.</p>

      {retryError && <p role="alert" className="text-rose-300">{retryError}</p>}</div><button className="flow-button secondary" disabled={retrying || ready === run.output_types.length} onClick={retry}><RefreshCw size={14} className={retrying ? 'animate-spin' : ''} />{retrying ? 'Starting…' : 'Retry remaining outputs'}</button></div>}

    {!needsHelp(run) && needsReview(run) && <p className="output-notice">The original outputs need review. Save a version, then choose Review or regenerate to check its exact text. Version review results appear on the selected version.</p>}
    <RunSourceSummary documents={run.source_documents || []} conflicts={run.source_conflicts || []} generationId={run.id}/>

    {artifacts.length > 0 ? <><div className="output-tabs" role="group" aria-label="Choose an output">{artifacts.map(a => <button key={a.id} aria-pressed={artifact?.id === a.id} className={cn(artifact?.id === a.id && 'active')} onClick={() => setSelected(a.id)}><FileText size={14} />{outputLabel(a.output_type)}<span className={a.review_status === 'pass' ? 'review-dot passed' : 'review-dot'} /></button>)}</div>

      {artifact && <OutputWorkspace key={`${artifact.id}:${artifact.evidence?.content_version || 'original'}`} artifact={artifact} sourceId={run.source_id} onUpdated={refetch} onRegenerate={() => regenerate(artifact.output_type)} regenerating={retrying || activeRun(run)} />}</> : <div className="empty-output"><div className="empty-output-icon">{activeRun(run) ? <Loader2 className="animate-spin" size={28} /> : <FileText size={28} />}</div><h3>{activeRun(run) ? 'Working from your source' : 'No output was produced'}</h3><p>{activeRun(run) ? 'You can leave this page and come back. Your run will continue, and the output will appear here when it’s ready.' : 'Use the retry button above to try again with the same document and settings.'}</p></div>}

    <details className="run-metadata"><summary>Technical details</summary><dl><div><dt>Model</dt><dd>{run.model_version || 'Not recorded'}</dd></div><div><dt>Tokens recorded</dt><dd>{run.total_tokens.toLocaleString()}</dd></div><div><dt>Estimated cost</dt><dd>${run.total_cost_usd.toFixed(4)}</dd></div>{status?.job && <><div><dt>Provider</dt><dd>{status.job.provider}</dd></div><div><dt>Pricing revision</dt><dd>{status.job.pricing.version} · {status.job.pricing.origin}</dd></div><div><dt>Worker attempts</dt><dd>{status.job.attempts}</dd></div><div><dt>Extraction reused</dt><dd>{status.job.extraction_reused ? 'Yes' : 'No'}</dd></div></>}<div><dt>Run ID</dt><dd>{run.id}</dd></div></dl></details>

  </div>;

}



function Studio({ initialId }: { initialId: string | null }) {

  const router = useRouter();

  const { generations, loading, error, refetch } = useGenerations();

  const [activeId, setActiveId] = useState(initialId);

  const [query, setQuery] = useState('');

  const [filter, setFilter] = useState('all');

  const selectedId = activeId || generations[0]?.id;

  const chooseRun = (id: string) => { setActiveId(id); router.replace(`/dashboard/generations?run=${encodeURIComponent(id)}`, { scroll: false }); };

  const visible = generations.filter(g => documentName(g.source_filename).toLowerCase().includes(query.toLowerCase()) && (filter === 'all' || (filter === 'attention' ? (needsHelp(g) || needsReview(g)) : filter === 'active' ? activeRun(g) : !activeRun(g) && !needsHelp(g) && !needsReview(g))));

  const completed = generations.reduce((n, g) => n + g.artifacts.filter(a => a.review_status === 'pass' || a.review_status === 'regenerated').length, 0);

  return <div className="outputs-page"><div className="workspace-page-heading"><div><p className="workspace-eyebrow">Your documents. New possibilities.</p><h1>My outputs</h1><p>Create, review, and refine. Everything starts with your source.</p></div><Link href="/dashboard/sources" className="flow-button"><Plus size={16} />Create output</Link></div>

    <div className="workspace-overview"><div><span className="overview-icon"><FileText size={20} /></span><p><strong>{completed}</strong><span>outputs passed review</span></p></div><div><span className="overview-icon"><Clock3 size={20} /></span><p><strong>{generations.filter(activeRun).length}</strong><span>runs in progress</span></p></div><div><span className="overview-icon"><AlertCircle size={20} /></span><p><strong>{generations.filter(g => needsHelp(g) || needsReview(g)).length}</strong><span>runs need attention</span></p></div><Link href="/dashboard/sources">Turn your next document into an output <ArrowRight size={16} /></Link></div>

    <div className="studio-grid"><aside className="studio-source-list"><div className="section-line"><h2>Recent work</h2><button className="icon-button" aria-label="Refresh recent work" onClick={refetch}><RefreshCw size={14} /></button></div>

      <div className="source-search"><Search size={14} /><input aria-label="Search recent work" value={query} onChange={e => setQuery(e.target.value)} placeholder="Find a document…" /></div>

      <select aria-label="Filter recent work" className="flow-input run-filter" value={filter} onChange={e => setFilter(e.target.value)}><option value="all">All runs</option><option value="ready">Ready</option><option value="active">In progress</option><option value="attention">Needs attention</option></select>

      {loading && !generations.length && <p className="muted" role="status">Loading recent work…</p>}

      {error && <div className="flow-error" role="alert">{error.message}<button onClick={refetch}>Try again</button></div>}

      <div className="recent-runs">{visible.map(g => <button key={g.id} aria-pressed={selectedId === g.id} className={cn('run-option', selectedId === g.id && 'selected')} onClick={() => chooseRun(g.id)}><div><FileText size={16} /><strong>{documentName(g.source_filename)}</strong></div><span><small>{formatRelative(g.created_at)}</small><small className={needsHelp(g) || needsReview(g) ? 'text-amber-300' : activeRun(g) ? 'text-stone-300' : 'text-emerald-300'}>{statusLabel(g)}</small></span></button>)}

        {!loading && !visible.length && <p className="muted">{generations.length ? 'No runs match your search.' : 'Your recent work will appear here.'}</p>}</div>

      <Link className="quiet-link history-link" href="/dashboard/history">View all history <ArrowRight size={13} /></Link>

    </aside>

    <div className="studio-content">{selectedId ? <RunDetail key={selectedId} id={selectedId} onRetry={id => { chooseRun(id); refetch(); }} /> : !loading && !error ? <div className="empty-output"><FileText size={34} /><h2>Your first output starts here.</h2><p>Upload a document, choose a format, and get a draft with source references and review results.</p><Link href="/dashboard/sources" className="flow-button">Create your first output <ArrowRight size={15} /></Link></div> : null}</div></div>

  </div>;

}

function StudioWithQuery() {

  const params = useSearchParams();

  const runId = params.get('run');

  return <Studio key={runId || 'latest'} initialId={runId} />;

}

export default function GenerationsPage() {

  return <Suspense fallback={<p role="status">Loading workspace…</p>}><StudioWithQuery /></Suspense>;

}

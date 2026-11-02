'use client';
import { useMemo, useState } from 'react';
import Link from 'next/link';
import { RefreshCw, Search } from 'lucide-react';
import { useHistory } from '@/hooks/useHistory';
import { documentName, outputLabel } from '@/lib/output-formats';
import { formatDate } from '@/lib/utils';

const labels: Record<string, string> = { cancelled: 'Cancelled', pending: 'Pending', queued: 'Queued', running: 'In progress', completed: 'Ready', complete: 'Ready', partial_failure: 'Needs attention', failed: 'Failed', budget_exceeded: 'Budget reached' };
export default function HistoryPage() {
  const { history, loading, error, refetch } = useHistory();
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [sensitivity, setSensitivity] = useState('');
  const [sort, setSort] = useState('newest');
  const rows = useMemo(() => history.filter(r => (!status || r.status === status) && (!sensitivity || r.sensitivity === sensitivity) && documentName(r.source_filename).toLowerCase().includes(query.toLowerCase())).sort((a, b) => sort === 'cost' ? b.total_cost_usd - a.total_cost_usd : sort === 'oldest' ? a.created_at.localeCompare(b.created_at) : b.created_at.localeCompare(a.created_at)), [history, status, sensitivity, query, sort]);
  return <div><div className="workspace-page-heading"><div><p className="workspace-eyebrow">Return to earlier work</p><h1>Run history</h1><p>Browse the latest 200 saved runs. Open a document to inspect its outputs and review results.</p></div><button className="flow-button secondary" disabled={loading} onClick={() => refetch()}><RefreshCw size={15} className={loading ? 'animate-spin' : ''} />Refresh</button></div>
    <div className="flex flex-wrap gap-3 mb-6"><div className="source-search flex-1 min-w-48"><Search size={15} /><input aria-label="Search run history" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search documents…" /></div>
      <select className="flow-input w-auto" aria-label="Filter history by status" value={status} onChange={e => setStatus(e.target.value)}><option value="">All statuses</option>{['queued', 'running', 'completed', 'partial_failure', 'failed', 'cancelled'].map(s => <option key={s} value={s}>{labels[s]}</option>)}</select>
      <select className="flow-input w-auto" aria-label="Filter by sensitivity" value={sensitivity} onChange={e => setSensitivity(e.target.value)}><option value="">All sensitivities</option>{['public', 'internal', 'restricted', 'confidential'].map(s => <option key={s}>{s}</option>)}</select>
      <select className="flow-input w-auto" aria-label="Sort run history" value={sort} onChange={e => setSort(e.target.value)}><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="cost">Highest estimated cost</option></select></div>
    {loading && <p role="status" className="muted">Loading run history…</p>}
    {error ? <div role="alert" className="flow-error">{error.message} <button onClick={() => refetch()}>Try again</button></div> : !loading && !rows.length ? <div className="flow-panel"><h2>{history.length ? 'No matching runs' : 'No runs yet'}</h2><p className="muted">{history.length ? 'Change your search or filters to find earlier work.' : 'Your runs will appear here after you create an output.'}</p><Link href="/dashboard/sources" className="quiet-link mt-4">Create an output →</Link></div> :
      <div className="overflow-x-auto rounded-xl border border-white/10" role="region" aria-label="Run history" tabIndex={0}><table className="w-full text-left text-sm min-w-[680px]"><thead className="bg-white/[0.03] text-stone-400"><tr>{['Document / date', 'Outputs requested', 'Status', 'Sensitivity', 'Estimated cost'].map(h => <th key={h} className="px-5 py-4 font-medium">{h}</th>)}</tr></thead><tbody>{rows.map(r => <tr key={r.id} className="border-t border-white/[0.06]"><td className="px-5 py-4"><Link className="text-stone-100 hover:underline block max-w-xs break-words" href={`/dashboard/generations?run=${r.id}`}>{documentName(r.source_filename)}</Link><span className="muted text-xs">{formatDate(r.created_at)}</span></td><td className="px-5 py-4 text-stone-400">{r.output_types.map(outputLabel).join(', ')}</td><td className="px-5 py-4"><span className={`status-pill ${r.status === 'completed' || r.status === 'complete' ? 'ready' : r.status === 'failed' || r.status === 'partial_failure' ? 'attention' : 'working'}`}>{labels[r.status] || r.status}</span></td><td className="px-5 py-4 text-stone-400 capitalize">{r.sensitivity || 'Not recorded'}</td><td className="px-5 py-4 font-mono text-stone-300">${r.total_cost_usd.toFixed(4)}</td></tr>)}</tbody></table></div>}
  </div>;
}

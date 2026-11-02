import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/** Merge Tailwind classes safely */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format USD cost */
export function formatCost(usd?: number | null): string {
  const val = typeof usd === 'number' && !isNaN(usd) ? usd : 0;
  if (val === 0) return '$0.0000';
  if (val < 0.0001) return '<$0.0001';
  return `$${val.toFixed(4)}`;
}

/** Format latency */
export function formatLatency(ms?: number | null): string {
  const val = typeof ms === 'number' && !isNaN(ms) ? ms : 0;
  if (val === 0) return '—';
  if (val >= 1000) return `${(val / 1000).toFixed(1)}s`;
  return `${Math.round(val)}ms`;
}

/** Format token count */
export function formatTokens(n?: number | null): string {
  const val = typeof n === 'number' && !isNaN(n) ? n : 0;
  if (val === 0) return '—';
  if (val >= 1000) return `${(val / 1000).toFixed(1)}k`;
  return `${Math.round(val)}`;
}

/** Format confidence percentage */
export function formatConfidence(score?: number | null): string {
  if (score == null) return 'Not measured';
  const val = typeof score === 'number' && !isNaN(score) ? score : 0;
  return `${Math.round(val * 100)}%`;
}

/** Format ISO date string to readable */
export function formatDate(iso?: string | null): string {
  if (!iso) return 'Just now';
  try {
    const d = new Date(iso.includes('T') && !/(Z|[+-]\d{2}:\d{2})$/i.test(iso) ? `${iso}Z` : iso);
    if (isNaN(d.getTime())) return 'Just now';
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(d);
  } catch {
    return 'Just now';
  }
}

/** Format relative time */
export function formatRelative(iso?: string | null): string {
  if (!iso) return 'just now';
  try {
    const d = new Date(iso.includes('T') && !/(Z|[+-]\d{2}:\d{2})$/i.test(iso) ? `${iso}Z` : iso);
    if (isNaN(d.getTime())) return 'just now';
    const diff = Date.now() - d.getTime();
    const minutes = Math.floor(diff / 60_000);
    if (minutes < 1)  return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24)   return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  } catch {
    return 'just now';
  }
}

/** Capitalize first letter */
export function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, ' ');
}

/** Sensitivity label + color class */
export function sensitivityMeta(s: string): { label: string; className: string; dotClass: string } {
  const map: Record<string, { label: string; className: string; dotClass: string }> = {
    public:       { label: 'Public',       className: 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20', dotClass: 'bg-emerald-400' },
    internal:     { label: 'Internal',     className: 'text-sky-400 bg-sky-500/10 border border-sky-500/20', dotClass: 'bg-sky-400' },
    restricted:   { label: 'Restricted',   className: 'text-amber-400 bg-amber-500/10 border border-amber-500/20', dotClass: 'bg-amber-400' },
    confidential: { label: 'Confidential', className: 'text-rose-400 bg-rose-500/10 border border-rose-500/20', dotClass: 'bg-rose-400' },
  };
  return map[s] ?? { label: s, className: 'text-neutral-400 bg-neutral-500/10 border border-neutral-500/20', dotClass: 'bg-neutral-400' };
}

/** Review status meta */
export function reviewStatusMeta(s: string): { label: string; className: string; dotClass: string } {
  const map: Record<string, { label: string; className: string; dotClass: string }> = {
    pass:           { label: 'Passed',          className: 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20', dotClass: 'bg-emerald-400' },
    fail:           { label: 'Needs Review',    className: 'text-rose-400 bg-rose-500/10 border border-rose-500/20', dotClass: 'bg-rose-400' },
    regenerated:    { label: 'Auto-Corrected',  className: 'text-amber-400 bg-amber-500/10 border border-amber-500/20', dotClass: 'bg-amber-400' },
    budget_exceeded:{ label: 'Budget Exceeded', className: 'text-neutral-400 bg-neutral-800 border border-neutral-700', dotClass: 'bg-neutral-500' },
    pending:        { label: 'Pending',         className: 'text-neutral-400 bg-neutral-800 border border-neutral-700', dotClass: 'bg-neutral-500' },
  };
  return map[s] ?? { label: s, className: 'text-neutral-400 bg-neutral-800 border border-neutral-700', dotClass: 'bg-neutral-500' };
}

/** Stage status meta */
export function stageMeta(s: string): { label: string; color: string } {
  const map: Record<string, { label: string; color: string }> = {
    queued:  { label: 'Queued',  color: '#737373' },
    running: { label: 'Running', color: '#3B82F6' },
    done:    { label: 'Done',    color: '#22C55E' },
    failed:  { label: 'Failed',  color: '#EF4444' },
  };
  return map[s] ?? { label: s, color: '#737373' };
}

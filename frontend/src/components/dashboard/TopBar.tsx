'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Search, ChevronRight, Plus } from 'lucide-react';
const labels: Record<string, string> = {
  '/dashboard/sources': 'Create output', '/dashboard/library': 'Source library', '/dashboard/generations': 'My outputs',
  '/dashboard/history': 'Run history', '/dashboard/evaluation': 'Evaluation',
  '/dashboard/settings': 'Settings',
  '/dashboard/team':'Team & workspace', '/dashboard/reviews':'Review inbox', '/dashboard/activity':'Activity', '/dashboard/output':'Saved output',
};
export function TopBar({ title, onCommandPalette }: { title?: string; onCommandPalette?: () => void }) {
  const pathname = usePathname();
  const label = title ?? labels[Object.keys(labels).find(key => pathname.startsWith(key)) ?? ''] ?? 'Overview';
  return (
    <header className="workspace-topbar">
      <div className="workspace-breadcrumb"><span>Workspace</span><ChevronRight size={13} /><strong>{label}</strong></div>
      <div className="workspace-topbar-actions">
        <button type="button" onClick={onCommandPalette} className="workspace-search" aria-label="Open command palette" aria-keyshortcuts="Control+K">
          <Search size={15} /><span>Search workspace</span><kbd>Ctrl K</kbd>
        </button>
        <Link href="/dashboard/sources" className="workspace-create" aria-label="Create output"><Plus size={15} /><span>Create output</span></Link>
      </div>
    </header>
  );
}

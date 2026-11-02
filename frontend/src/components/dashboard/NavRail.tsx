'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { UploadCloud, FolderOpen, Clock, BarChart3, Settings, Layers, ArrowUpRight } from 'lucide-react';
import { cn } from '@/lib/utils';

const items = [
  { href: '/dashboard/generations', icon: FolderOpen, label: 'My outputs' },
  { href: '/dashboard/sources', icon: UploadCloud, label: 'Create output' },
  { href: '/dashboard/library', icon: Layers, label: 'Source library' },
  { href: '/dashboard/history', icon: Clock, label: 'Run history' },
  { href: '/dashboard/evaluation', icon: BarChart3, label: 'Evaluation' },
  { href: '/dashboard/settings', icon: Settings, label: 'Settings' },
  { href: '/dashboard/team', icon: Layers, label: 'Team & workspace' },
  { href: '/dashboard/reviews', icon: FolderOpen, label: 'Review inbox' },
  { href: '/dashboard/activity', icon: Clock, label: 'Activity' },
];
export function NavRail() {
  const pathname = usePathname();
  return (
    <nav className="workspace-nav" aria-label="Dashboard navigation">
      <Link href="/" className="workspace-brand" aria-label="TraceForm home">
        <span className="workspace-mark"><Layers size={20} strokeWidth={1.6} /></span>
        <span className="workspace-brand-name">TraceForm<span>Intelligence workspace</span></span>
      </Link>
      <div className="workspace-nav-label">Workspace</div>
      <div className="workspace-links">
        {items.map(({ href, icon: Icon, label }) => (
          <Link key={href} href={href} className={cn('workspace-link', pathname.startsWith(href) && 'is-active')}
            aria-current={pathname.startsWith(href) ? 'page' : undefined}>
            <Icon size={18} strokeWidth={1.7} /><span>{label}</span>
          </Link>
        ))}
      </div>
      <div className="workspace-nav-footer">
        <div className="workspace-note"><Layers size={17} /><p>From source to output.<span>Evidence stays connected.</span></p></div>
        <Link href="/dashboard/sources" className="workspace-new">Create output<ArrowUpRight size={16} /></Link>
        <div className="workspace-profile"><span>TF</span><div>TraceForm workspace<small>Content & provenance</small></div></div>
      </div>
    </nav>
  );
}

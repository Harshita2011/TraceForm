'use client';
import { useState, useEffect, useCallback } from 'react';
import { NavRail }          from '@/components/dashboard/NavRail';
import { TopBar }           from '@/components/dashboard/TopBar';
import { CommandPalette }   from '@/components/dashboard/CommandPalette';
import { ExplainabilityDrawer } from '@/components/dashboard/ExplainabilityDrawer';
import { Artifact }         from '@/lib/types';

import { DrawerContext } from '@/components/dashboard/DrawerContext';
import { IS_DEMO_MODE } from '@/lib/api';
import { TeamSession } from '@/components/dashboard/TeamSession';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [cmdOpen, setCmdOpen]               = useState(false);
  const [drawerArtifact, setDrawerArtifact] = useState<Artifact | null>(null);
  const [drawerOpen, setDrawerOpen]         = useState(false);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCmdOpen(prev => !prev);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const openDrawer = useCallback((artifact: Artifact) => {
    setDrawerArtifact(artifact);
    setDrawerOpen(true);
  }, []);

  const closeDrawer = useCallback(() => setDrawerOpen(false), []);

  return (
    <TeamSession><DrawerContext.Provider value={{ openDrawer, closeDrawer }}>
      {/* Full-width workspace — no max-width constraint on the shell */}
      <div className="workspace-shell">

        {/* Sidebar — no border, continuous with canvas */}
        <a className="workspace-skip" href="#dashboard-main">Skip to content</a>
        <NavRail />

        {/* Main column */}
        <div className="flex-1 flex flex-col min-w-0">
          <TopBar onCommandPalette={() => setCmdOpen(true)} />
          {IS_DEMO_MODE && <div role="status" className="px-6 py-3 text-sm text-amber-200 bg-amber-950/40 border-b border-amber-800/40">Demo mode · sample data is shown. Changes do not update the live API.</div>}

          <div className="flex flex-1 min-w-0 overflow-hidden">
            {/* Page content — full width with generous inline padding */}
            <main
              id="dashboard-main"
              className="workspace-main"
              aria-label="Dashboard main content"
            >
              {children}
            </main>

            {/* Explainability drawer */}
            {drawerOpen && (
              <ExplainabilityDrawer
                artifact={drawerArtifact}
                open={drawerOpen}
                onClose={closeDrawer}
              />
            )}
          </div>
        </div>

        <CommandPalette open={cmdOpen} onClose={() => setCmdOpen(false)} />
      </div>
    </DrawerContext.Provider></TeamSession>
  );
}

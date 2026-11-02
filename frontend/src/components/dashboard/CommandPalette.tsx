'use client';
import { useEffect, useCallback, useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Zap, Settings, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';
import { overlayVariants, commandPaletteVariants } from '@/lib/motion';
import { CommandItem, CommandGroup } from '@/lib/types';

// ── Static command items ──────────────────────────────────────────────────────
// Dynamic items (recent generations, artifacts) would be fetched via hooks
function buildCommands(): CommandItem[] {
  return [
    // Navigate
    { id: 'nav-library', group: 'navigate', label: 'Source library', description: 'Find, preview and manage saved sources', href: '/dashboard/library' },
    { id: 'nav-sources',     group: 'navigate', label: 'Create output',              description: 'Choose a source and create outputs',  href: '/dashboard/sources',     shortcut: 'G S' },
    { id: 'nav-generations', group: 'navigate', label: 'My outputs',          description: 'View generation runs and artifacts',   href: '/dashboard/generations', shortcut: 'G G' },
    { id: 'nav-history',     group: 'navigate', label: 'History',              description: 'Filter past generation history',       href: '/dashboard/history',     shortcut: 'G H' },
    { id: 'nav-evaluation',  group: 'navigate', label: 'Evaluation',           description: 'Metrics and evaluation dashboard',     href: '/dashboard/evaluation',  shortcut: 'G E' },
    { id: 'nav-settings',    group: 'navigate', label: 'Settings',             description: 'API keys and configuration',           href: '/dashboard/settings',    shortcut: 'G ,' },
    // Generation actions
    { id: 'gen-new',         group: 'generation', label: 'Create output',       description: 'Upload a source and start generation',  href: '/dashboard/sources',   },
    // Settings
    { id: 'settings-api',    group: 'settings',  label: 'Connection status',     description: 'Test the configured AI provider connection',          href: '/dashboard/settings' },
  ];
}

const GROUP_LABELS: Record<CommandGroup, string> = {
  navigate:   'Navigate',
  generation: 'Generation',
  artifact:   'Artifact',
  settings:   'Settings',
};

const GROUP_ICON: Record<CommandGroup, React.ElementType> = {
  navigate:   ExternalLink,
  generation: Zap,
  artifact:   Search,
  settings:   Settings,
};

// ─────────────────────────────────────────────────────────────────────────────

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const router   = useRouter();
  const [query, setQuery]   = useState('');
  const [cursor, setCursor] = useState(0);

  const commands = buildCommands();

  const filtered = query.trim()
    ? commands.filter(c =>
        c.label.toLowerCase().includes(query.toLowerCase()) ||
        c.description?.toLowerCase().includes(query.toLowerCase()),
      )
    : commands;

  const groupedKeys = [...new Set(filtered.map(c => c.group))] as CommandGroup[];

  // Flatten for keyboard nav
  const flat = groupedKeys.flatMap(g => filtered.filter(c => c.group === g));

  const runCommand = useCallback((item: CommandItem) => {
    onClose();
    setQuery('');
    if (item.action) item.action();
    else if (item.href) router.push(item.href);
  }, [onClose, router]);

  // Keyboard handling
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') { e.preventDefault(); setCursor(c => Math.min(c + 1, flat.length - 1)); }
      if (e.key === 'ArrowUp')   { e.preventDefault(); setCursor(c => Math.max(c - 1, 0)); }
      if (e.key === 'Enter')     { e.preventDefault(); if (flat[cursor]) runCommand(flat[cursor]); }
      if (e.key === 'Escape')    { e.preventDefault(); onClose(); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, flat, cursor, runCommand, onClose]);

  // Reset on open
  useEffect(() => {
    if (open) { setQuery(''); setCursor(0); }
  }, [open]);

  // Global trigger: Ctrl/Cmd + K (handled in layout)

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 bg-canvas/60 backdrop-blur-xs z-50"
            variants={overlayVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            onClick={onClose}
            aria-hidden="true"
          />

          {/* Palette */}
          <motion.div
            className="fixed top-[20vh] left-1/2 -translate-x-1/2 w-full max-w-xl z-50 px-4"
            variants={commandPaletteVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            role="dialog"
            aria-label="Command palette"
            aria-modal="true"
          >
            <div className="rounded-lg border border-surface-border bg-surface shadow-2xl overflow-hidden">
              {/* Search input */}
              <div className="flex items-center gap-3 border-b border-surface-border px-4 py-3">
                <Search size={15} className="text-text-tertiary flex-shrink-0" aria-hidden="true" />
                <input
                  id="cmd-palette-input"
                  type="text"
                  autoFocus
                  placeholder="Search commands, generations, artifacts..."
                  value={query}
                  onChange={e => { setQuery(e.target.value); setCursor(0); }}
                  className="flex-1 bg-transparent text-sm text-text-primary placeholder:text-text-tertiary outline-none font-mono"
                  aria-label="Command search"
                  aria-autocomplete="list"
                  aria-controls="cmd-palette-results"
                />
                <kbd className="mono text-[10px] text-text-tertiary px-1.5 py-0.5 rounded border border-surface-border" aria-label="Escape to close">
                  ESC
                </kbd>
              </div>

              {/* Results */}
              <div
                id="cmd-palette-results"
                className="max-h-80 overflow-y-auto py-2"
                role="listbox"
                aria-label="Command results"
              >
                {flat.length === 0 ? (
                  <p className="px-4 py-8 text-center mono text-[11px] text-text-tertiary">
                    No commands match "{query}"
                  </p>
                ) : (
                  groupedKeys.map(group => {
                    const GroupIcon = GROUP_ICON[group];
                    const items = filtered.filter(c => c.group === group);
                    return (
                      <div key={group}>
                        <p className="px-4 py-1 mono text-[10px] tracking-widest text-text-tertiary uppercase flex items-center gap-1.5">
                          <GroupIcon size={10} aria-hidden="true" />
                          {GROUP_LABELS[group]}
                        </p>
                        {items.map(item => {
                          const idx = flat.indexOf(item);
                          const active = idx === cursor;
                          return (
                            <button
                              key={item.id}
                              id={`cmd-item-${item.id}`}
                              className={cn(
                                'w-full flex items-center justify-between px-4 py-2.5 text-left',
                                'transition-colors duration-100',
                                active ? 'bg-surface-elevated text-text-primary' : 'text-text-secondary hover:bg-surface-elevated hover:text-text-primary',
                              )}
                              onClick={() => runCommand(item)}
                              onMouseEnter={() => setCursor(idx)}
                              role="option"
                              aria-selected={active}
                            >
                              <div>
                                <span className="text-sm font-medium">{item.label}</span>
                                {item.description && (
                                  <span className="block mono text-[11px] text-text-tertiary">{item.description}</span>
                                )}
                              </div>
                              {item.shortcut && (
                                <span className="mono text-[10px] text-text-tertiary">{item.shortcut}</span>
                              )}
                            </button>
                          );
                        })}
                      </div>
                    );
                  })
                )}
              </div>

              {/* Footer hint */}
              <div className="border-t border-surface-border px-4 py-2 flex items-center gap-4">
                <span className="mono text-[10px] text-text-tertiary">↑↓ navigate</span>
                <span className="mono text-[10px] text-text-tertiary">↵ open</span>
                <span className="mono text-[10px] text-text-tertiary">ESC close</span>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
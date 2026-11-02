'use client';
import { useRef, useEffect, useState } from 'react';
import { motion, useInView, useReducedMotion, AnimatePresence } from 'framer-motion';
import { MOCK_AUDIT_LOG } from '@/lib/mock-data';
import { fadeUpContainerVariants, fadeUpVariants } from '@/lib/motion';

/**
 * TrustAuditLog — terminal-style audit log replacing generic trust cards.
 * Each line scrolls into view with a typewriter-like stagger effect.
 * Visualizes the actual pipeline audit trail — this IS the differentiator.
 */
export function TrustAuditLog() {
  const ref    = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: '-15%' });
  const prefersReducedMotion = useReducedMotion();
  const [visibleCount, setVisibleCount] = useState(0);

  useEffect(() => {
    if (!inView) return;
    if (prefersReducedMotion) { setVisibleCount(MOCK_AUDIT_LOG.length); return; }

    let i = 0;
    const interval = setInterval(() => {
      i++;
      setVisibleCount(i);
      if (i >= MOCK_AUDIT_LOG.length) clearInterval(interval);
    }, 280);
    return () => clearInterval(interval);
  }, [inView, prefersReducedMotion]);

  return (
    <section
      id="trust"
      ref={ref}
      className="py-32 px-6 border-t border-surface-border bg-surface"
      aria-labelledby="trust-audit-heading"
    >
      <div className="max-w-content mx-auto grid md:grid-cols-2 gap-16 items-center">
        {/* Left — copy */}
        <motion.div
          variants={prefersReducedMotion ? {} : fadeUpContainerVariants}
          initial="hidden"
          animate={inView ? 'visible' : 'hidden'}
        >
          <motion.p variants={fadeUpVariants} className="mono text-accent text-[11px] tracking-widest uppercase mb-3">
            Trust By Design
          </motion.p>
          <motion.h2 variants={fadeUpVariants} id="trust-audit-heading" className="display text-[clamp(2.2rem,4vw,3.5rem)] mb-6">
            REVIEW THE<br/>RECORDED RESULTS.
          </motion.h2>
          <motion.p variants={fadeUpVariants} className="text-text-secondary leading-relaxed mb-8 max-w-sm">
            Inspect saved reviewer findings and source references. The log shown here illustrates the workflow using sample data.
          </motion.p>
          <motion.div variants={fadeUpVariants} className="space-y-4">
            {[
              ['Source content is data, never instructions', 'Source text is separated from system instructions; review suspicious content.'],
              ['Every override is reasoned and logged',      'Compliance overrides require a typed reason and are attributed to the operator'],
              ['Sensitivity gates before generation',        'No artifact is generated before the sensitivity classification is confirmed'],
            ].map(([title, body]) => (
              <div key={title} className="border-l border-surface-border-sub pl-4">
                <p className="text-sm font-semibold text-text-primary mb-0.5">{title}</p>
                <p className="mono text-[11px] text-text-tertiary">{body}</p>
              </div>
            ))}
          </motion.div>
        </motion.div>

        {/* Right — terminal */}
        <div>
          <div
            className="rounded-lg border border-surface-border bg-canvas p-6 font-mono"
            role="log"
            aria-label="Illustrative audit log using sample data"
            aria-live="polite"
          >
            {/* Terminal header */}
            <div className="flex items-center gap-1.5 mb-4" aria-hidden="true">
              <div className="w-2.5 h-2.5 rounded-full bg-surface-border-sub" />
              <div className="w-2.5 h-2.5 rounded-full bg-surface-border-sub" />
              <div className="w-2.5 h-2.5 rounded-full bg-surface-border-sub" />
              <span className="ml-3 text-[10px] text-text-tertiary tracking-widest uppercase">sample audit.log · illustrative data</span>
            </div>

            <div className="space-y-0.5 min-h-[280px]">
              <AnimatePresence>
                {MOCK_AUDIT_LOG.slice(0, visibleCount).map((entry, i) => (
                  <motion.div
                    key={i}
                    className="terminal-line flex gap-0"
                    initial={{ opacity: 0, x: -4 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.2, ease: 'easeOut' }}
                  >
                    <span className="ts select-none">[{entry.ts}]</span>
                    <span className="event">{entry.event}</span>
                    <span className="detail hidden sm:inline">· {entry.detail}</span>
                  </motion.div>
                ))}
              </AnimatePresence>

              {/* Cursor blink */}
              {visibleCount < MOCK_AUDIT_LOG.length && (
                <motion.span
                  className="inline-block w-1.5 h-3.5 bg-accent"
                  animate={{ opacity: [1, 0, 1] }}
                  transition={{ duration: 0.8, repeat: Infinity }}
                  aria-hidden="true"
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

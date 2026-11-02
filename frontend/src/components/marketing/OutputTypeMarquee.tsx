'use client';
import { useRef } from 'react';
import { motion, useInView, useReducedMotion } from 'framer-motion';
import { OUTPUT_TYPES } from '@/lib/mock-data';
import { cn } from '@/lib/utils';

function Chip({ label, icon }: { label: string; icon: string }) {
  return (
    <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded border border-surface-border bg-surface text-text-secondary text-xs mono tracking-wide whitespace-nowrap mx-3 hover:border-surface-border-sub hover:text-text-primary transition-colors duration-150">
      <span aria-hidden="true" className="text-[13px]">{icon}</span>
      <span>{label}</span>
    </div>
  );
}

// Duplicate array for seamless loop
const ITEMS = [...OUTPUT_TYPES, ...OUTPUT_TYPES];

export function OutputTypeMarquee() {
  const ref  = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true });
  const prefersReducedMotion = useReducedMotion();

  return (
    <section
      ref={ref}
      className="py-12 border-y border-surface-border overflow-hidden"
      aria-label="Supported artifact types"
    >
      <motion.p
        className="text-center mono text-[10px] tracking-widest text-text-tertiary uppercase mb-6"
        initial={{ opacity: 0 }}
        animate={inView ? { opacity: 1 } : {}}
        transition={{ duration: 0.5 }}
      >
        Nine artifact types · one source
      </motion.p>

      <div
        className={cn('marquee-wrap relative', prefersReducedMotion && 'flex flex-wrap justify-center gap-2 px-6')}
        aria-hidden={!prefersReducedMotion}
      >
        {prefersReducedMotion ? (
          // Static grid for reduced motion
          OUTPUT_TYPES.map(t => <Chip key={t.id} label={t.label} icon={t.icon} />)
        ) : (
          <div className="marquee-track flex items-center">
            {ITEMS.map((t, i) => (
              <Chip key={`${t.id}-${i}`} label={t.label} icon={t.icon} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

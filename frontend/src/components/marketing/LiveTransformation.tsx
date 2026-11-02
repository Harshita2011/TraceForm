'use client';
import { useState, useRef } from 'react';
import { motion, useInView, useReducedMotion, AnimatePresence } from 'framer-motion';
import { CitationTrace } from '@/components/citation-trace/CitationTrace';
import { fadeUpContainerVariants, fadeUpVariants } from '@/lib/motion';

const TRANSFORMATIONS = [
  {
    id: 'threat-intel',
    domain: 'Threat Intel',
    sourceExcerpt: 'advanced persistent threat activity increased 34% YoY, with nation-state actors targeting financial sector in 67% of incidents',
    outputType: 'LinkedIn Post',
    claim: 'APT activity surged 34% year-over-year. Nation-state actors were behind 67% of financial sector incidents.',
    confidence: 0.97,
    spanLabel: 'Source · span 344–381',
  },
  {
    id: 'policy-brief',
    domain: 'Policy',
    sourceExcerpt: 'MiCA Article 47 requires firms to maintain operational resilience records for a minimum of 5 years',
    outputType: 'Advisory',
    claim: 'Under MiCA Article 47, all regulated firms must retain operational resilience documentation for at least 5 years.',
    confidence: 0.99,
    spanLabel: 'Source · span 122–189',
  },
  {
    id: 'product-roadmap',
    domain: 'Product',
    sourceExcerpt: 'The H2 roadmap prioritises cross-artifact consistency and latency improvements targeting sub-3s generation',
    outputType: 'Executive Summary',
    claim: 'H2 priorities: cross-artifact consistency and generation latency targeting sub-3 seconds.',
    confidence: 0.93,
    spanLabel: 'Source · span 88–147',
  },
];

export function LiveTransformation() {
  const [activeId, setActiveId] = useState(TRANSFORMATIONS[0].id);
  const ref    = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: '-10%' });
  const prefersReducedMotion = useReducedMotion();

  const active = TRANSFORMATIONS.find(t => t.id === activeId)!;

  return (
    <section
      id="product"
      ref={ref}
      className="py-32 px-6 max-w-content mx-auto"
      aria-labelledby="live-transform-heading"
    >
      <motion.div
        variants={prefersReducedMotion ? {} : fadeUpContainerVariants}
        initial="hidden"
        animate={inView ? 'visible' : 'hidden'}
        className="text-center mb-16"
      >
        <motion.p
          variants={fadeUpVariants}
          className="mono text-accent text-[11px] tracking-widest uppercase mb-3"
        >
          Illustrative transformation · sample data
        </motion.p>
        <motion.h2
          variants={fadeUpVariants}
          id="live-transform-heading"
          className="display text-[clamp(2.5rem,5vw,4rem)] text-text-primary"
        >
          SOURCE → VERIFIED → ARTIFACT
        </motion.h2>
        <motion.p
          variants={fadeUpVariants}
          className="mt-4 text-text-secondary text-lg max-w-xl mx-auto"
        >
          These examples explain the workflow; they are not live generation results.
          Click any transformation to see the trace.
        </motion.p>
      </motion.div>

      {/* Selector */}
      <motion.div
        className="flex flex-wrap justify-center gap-2 mb-12"
        initial={{ opacity: 0 }}
        animate={inView ? { opacity: 1 } : {}}
        transition={{ delay: 0.2, duration: 0.4 }}
      >
        {TRANSFORMATIONS.map(t => (
          <button
            key={t.id}
            id={`transform-tab-${t.id}`}
            onClick={() => setActiveId(t.id)}
            className={`px-3 py-1.5 text-xs mono tracking-wide rounded border transition-all duration-150 ${
              activeId === t.id
                ? 'border-accent bg-accent/10 text-accent'
                : 'border-surface-border text-text-tertiary hover:border-surface-border-sub hover:text-text-secondary'
            }`}
            aria-pressed={activeId === t.id}
            aria-label={`View ${t.domain} transformation`}
          >
            {t.domain} · {t.outputType}
          </button>
        ))}
      </motion.div>

      {/* Transformation card */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeId}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -12 }}
          transition={{ ease: [0.16, 1, 0.3, 1], duration: 0.35 }}
          className="max-w-3xl mx-auto border border-surface-border rounded-lg p-8 bg-surface"
        >
          <div className="flex items-start justify-between mb-2">
            <span className="mono text-[10px] tracking-widest text-text-tertiary uppercase">
              Source Document
            </span>
            <span className="mono text-[10px] tracking-widest text-accent uppercase">
              → {active.outputType}
            </span>
          </div>

          <CitationTrace
            sourceText={active.sourceExcerpt}
            generatedClaim={active.claim}
            confidence={active.confidence}
            status="verified"
            spanLabel={active.spanLabel}
            animateOnMount
          />
        </motion.div>
      </AnimatePresence>

      <motion.p
        className="text-center mono text-[10px] text-text-tertiary mt-8"
        initial={{ opacity: 0 }}
        animate={inView ? { opacity: 1 } : {}}
        transition={{ delay: 0.6 }}
      >
        The amber line is not decorative. It is the product.
      </motion.p>
    </section>
  );
}

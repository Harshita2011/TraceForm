'use client';
import Link from 'next/link';
import { useRef } from 'react';
import { motion, useInView, useReducedMotion } from 'framer-motion';

export function ClosingCTA() {
  const ref    = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: '-10%' });
  const prefersReducedMotion = useReducedMotion();

  return (
    <section
      ref={ref}
      className="relative py-40 px-6 border-t border-surface-border overflow-hidden text-center"
      aria-labelledby="closing-cta-heading"
    >
      {/* Radial glow */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: 'radial-gradient(ellipse 50% 60% at 50% 100%, rgba(245,166,35,0.05) 0%, transparent 70%)',
        }}
        aria-hidden="true"
      />

      <div className="relative z-10 max-w-4xl mx-auto">
        <motion.p
          className="mono text-accent text-[11px] tracking-widest uppercase mb-6"
          initial={{ opacity: 0 }}
          animate={inView ? { opacity: 1 } : {}}
          transition={{ duration: 0.4 }}
        >
          Ready to verify?
        </motion.p>

        <motion.h2
          id="closing-cta-heading"
          className="display text-text-primary"
          style={{ fontSize: 'clamp(3.5rem, 9vw, 8rem)', lineHeight: 1.0 }}
          initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 40 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ ease: [0.16, 1, 0.3, 1], duration: 0.75, delay: 0.1 }}
        >
          TRACE YOUR<br />
          <span className="text-accent">FIRST CLAIM.</span>
        </motion.h2>

        <motion.div
          className="mt-12"
          initial={{ opacity: 0, y: 16 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ ease: [0.16, 1, 0.3, 1], duration: 0.5, delay: 0.45 }}
        >
          <Link
            href="/dashboard"
            id="closing-cta-btn"
            className="inline-flex items-center gap-3 px-8 py-4 rounded bg-accent text-canvas text-sm font-semibold tracking-widest uppercase hover:bg-accent/90 transition-colors duration-150"
          >
            Open Dashboard
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
              <path d="M3 7h8M8 4l3 3-3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </Link>
        </motion.div>
      </div>
    </section>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-surface-border bg-surface py-16 px-6" aria-label="Site footer">
      <div className="max-w-content mx-auto grid grid-cols-2 md:grid-cols-4 gap-10">
        <div>
          <div className="flex items-center gap-2 mb-4">
            <span className="display text-[1rem] tracking-widest text-text-primary">TRACEFORM</span>
            <span className="w-1 h-1 rounded-full bg-accent" aria-hidden="true" />
          </div>
          <p className="mono text-[11px] text-text-tertiary leading-relaxed">
            Citation-backed AI generation<br />for compliance-grade operators.
          </p>
        </div>

        <nav aria-label="Product links">
          <p className="mono text-[10px] tracking-widest text-text-tertiary uppercase mb-3">Product</p>
          <ul className="space-y-2">
            {['How It Works', 'Explainability', 'Pipeline', 'Evaluation'].map(l => (
              <li key={l}>
                <a href="#" className="text-sm text-text-secondary hover:text-text-primary transition-colors duration-150">{l}</a>
              </li>
            ))}
          </ul>
        </nav>

        <nav aria-label="Pages links">
          <p className="mono text-[10px] tracking-widest text-text-tertiary uppercase mb-3">Pages</p>
          <ul className="space-y-2">
            {['Dashboard', 'Docs', 'API Reference', 'Changelog'].map(l => (
              <li key={l}>
                <a href="#" className="text-sm text-text-secondary hover:text-text-primary transition-colors duration-150">{l}</a>
              </li>
            ))}
          </ul>
        </nav>

        <nav aria-label="Legal links">
          <p className="mono text-[10px] tracking-widest text-text-tertiary uppercase mb-3">Legal</p>
          <ul className="space-y-2">
            {['Terms of Service', 'Privacy Policy', 'Security', 'Trust Center'].map(l => (
              <li key={l}>
                <a href="#" className="text-sm text-text-secondary hover:text-text-primary transition-colors duration-150">{l}</a>
              </li>
            ))}
          </ul>
        </nav>
      </div>

      <div className="max-w-content mx-auto mt-16 pt-8 border-t border-surface-border flex flex-col md:flex-row items-center justify-between gap-4">
        <p className="mono text-[10px] text-text-tertiary">
          © 2026 Traceform. All rights reserved.
        </p>
        <p className="mono text-[10px] text-text-tertiary">
          Inspect source references and review results in your workspace.
        </p>
      </div>
    </footer>
  );
}

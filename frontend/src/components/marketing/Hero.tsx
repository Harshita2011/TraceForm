'use client';
import { useEffect, useRef } from 'react';
import Link from 'next/link';
import { motion, useReducedMotion } from 'framer-motion';
import { CitationTrace } from '@/components/citation-trace/CitationTrace';
import { heroWordVariants } from '@/lib/motion';

// Animated background — floating citation nodes + subtle trace paths
function CitationNetworkBg() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let raf: number;

    const resize = () => {
      canvas.width  = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    // Nodes
    const NODE_COUNT = 18;
    type Node = { x: number; y: number; vx: number; vy: number; r: number; opacity: number };
    const nodes: Node[] = Array.from({ length: NODE_COUNT }, () => ({
      x:  Math.random() * canvas.width,
      y:  Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.25,
      vy: (Math.random() - 0.5) * 0.25,
      r:  Math.random() * 2 + 1.5,
      opacity: Math.random() * 0.4 + 0.15,
    }));

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Move nodes
      for (const n of nodes) {
        n.x += n.vx;
        n.y += n.vy;
        if (n.x < 0 || n.x > canvas.width)  n.vx *= -1;
        if (n.y < 0 || n.y > canvas.height) n.vy *= -1;
      }

      // Draw edges between nearby nodes
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x;
          const dy = nodes[i].y - nodes[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 180) {
            const alpha = (1 - dist / 180) * 0.12;
            ctx.beginPath();
            ctx.moveTo(nodes[i].x, nodes[i].y);
            ctx.lineTo(nodes[j].x, nodes[j].y);
            ctx.strokeStyle = `rgba(245,166,35,${alpha})`;
            ctx.lineWidth = 0.8;
            ctx.stroke();
          }
        }
      }

      // Draw nodes
      for (const n of nodes) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(245,166,35,${n.opacity})`;
        ctx.fill();
      }

      raf = requestAnimationFrame(draw);
    };

    draw();
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full pointer-events-none"
      aria-hidden="true"
    />
  );
}

const HEADLINE_WORDS = ['EVERY', 'CLAIM', 'TRACED.'];

export function Hero() {
  const prefersReducedMotion = useReducedMotion();

  return (
    <section
      className="relative min-h-dvh flex flex-col items-center justify-center overflow-hidden pt-14"
      aria-label="Traceform hero"
    >
      {/* Subtle grid */}
      <div className="marketing-grid-bg absolute inset-0" aria-hidden="true" />

      {/* Citation node network canvas */}
      {!prefersReducedMotion && <CitationNetworkBg />}

      {/* Radial glow from center */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            'radial-gradient(ellipse 60% 50% at 50% 50%, rgba(245,166,35,0.04) 0%, transparent 70%)',
        }}
        aria-hidden="true"
      />

      {/* Content */}
      <div className="relative z-10 text-center px-6 max-w-5xl mx-auto">
        {/* Eyebrow */}
        <motion.p
          className="mono text-accent text-[11px] tracking-widest uppercase mb-6"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ease: [0.16, 1, 0.3, 1], duration: 0.5, delay: 0.1 }}
        >
          Citation-Backed AI Generation
        </motion.p>

        {/* Kinetic headline — Bebas Neue, word-staggered */}
        <h1 className="display overflow-hidden mb-0" aria-label="Every claim traced.">
          {HEADLINE_WORDS.map((word, i) => (
            <span key={word} className="inline-block mr-[0.2em] last:mr-0">
              <motion.span
                className="block"
                style={{
                  fontSize: 'clamp(4.5rem, 11vw, 9rem)',
                  lineHeight: 1.0,
                  color: word === 'TRACED.' ? 'var(--color-accent)' : 'var(--color-text-primary)',
                }}
                custom={i}
                variants={prefersReducedMotion ? {} : heroWordVariants}
                initial="hidden"
                animate="visible"
              >
                {word}
              </motion.span>
            </span>
          ))}
        </h1>

        {/* Subhead */}
        <motion.p
          className="mt-6 text-text-secondary text-lg md:text-xl leading-relaxed max-w-2xl mx-auto"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ease: [0.16, 1, 0.3, 1], duration: 0.6, delay: 0.55 }}
        >
          Turn one source into every format you need — with every generated
          sentence traced back to an exact span in the original.
        </motion.p>

        {/* CTAs */}
        <motion.div
          className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ease: [0.16, 1, 0.3, 1], duration: 0.5, delay: 0.75 }}
        >
          <Link
            href="#product"
            id="hero-cta-live-trace"
            className="inline-flex items-center gap-2 px-6 py-3 rounded bg-accent text-canvas text-sm font-semibold tracking-wide hover:bg-accent/90 transition-colors duration-150"
          >
            See an Example Trace
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
              <path d="M3 7h8M8 4l3 3-3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </Link>
          <Link
            href="/dashboard"
            id="hero-cta-dashboard"
            className="inline-flex items-center gap-2 px-6 py-3 rounded border border-surface-border text-text-secondary text-sm font-semibold tracking-wide hover:border-surface-border-sub hover:text-text-primary transition-colors duration-150"
          >
            View Dashboard
          </Link>
        </motion.div>

        {/* Pipeline flow hint */}
        <motion.div
          className="mt-16 flex items-center justify-center gap-2 text-[11px] mono text-text-tertiary"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.1, duration: 0.5 }}
          aria-label="Pipeline flow: Source to Facts to Review to Artifact"
        >
          {['Source', '→', 'Facts', '→', 'Review', '→', 'Artifact'].map((t, i) => (
            <span
              key={i}
              className={t === '→' ? 'text-accent/40' : 'text-text-tertiary'}
            >
              {t}
            </span>
          ))}
        </motion.div>

        {/* Inline demo CitationTrace */}
        <motion.div
          className="mt-12 max-w-lg mx-auto"
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ease: [0.16, 1, 0.3, 1], duration: 0.7, delay: 1.3 }}
        >
          <p className="mono text-xs text-text-tertiary mb-3">Illustrative trace · sample data</p>
          <CitationTrace
            sourceText="advanced persistent threat activity increased 34% YoY"
            generatedClaim="APT activity surged 34% year-over-year according to our Q3 brief."
            confidence={0.97}
            status="verified"
            spanLabel="Source · span 344–381"
            animateOnMount
          />
        </motion.div>
      </div>

      {/* Scroll indicator */}
      <motion.div
        className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-1"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.8, duration: 0.5 }}
        aria-hidden="true"
      >
        <div className="w-px h-8 bg-gradient-to-b from-transparent to-surface-border-sub" />
        <span className="mono text-[10px] text-text-tertiary tracking-widest uppercase">scroll</span>
      </motion.div>
    </section>
  );
}

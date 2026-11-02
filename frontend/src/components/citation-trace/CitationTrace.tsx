'use client';
import { useRef, useEffect, useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { cn, formatConfidence } from '@/lib/utils';
import { CitationStatus } from '@/lib/types';

export interface CitationTraceProps {
  /** Text excerpt from the source document */
  sourceText: string;
  /** The generated claim that references the source */
  generatedClaim: string;
  /** Confidence score 0–1 */
  confidence: number | null;
  /** Verification status */
  status: CitationStatus;
  /** Character span for metadata display */
  spanLabel?: string;
  /** Compact mode — used in drawer, not hero */
  compact?: boolean;
  /** Additional class names */
  className?: string;
  /** Animate on mount vs on demand */
  animateOnMount?: boolean;
}

const STATUS_COLOR: Record<CitationStatus, string> = {
  verified: '#F5A623',
  failed:   '#9B4040',
  pending:  '#555555',
};

const STATUS_LABEL: Record<CitationStatus, string> = {
  verified: 'Verified',
  failed:   'Failed',
  pending:  'Pending',
};

/**
 * CitationTrace — the signature visual component.
 *
 * Renders an animated SVG path from a highlighted source span to a generated
 * claim chip, ending with a confidence score badge.
 *
 * Used in: Hero, LiveTransformation cards, HowItWorks step 2,
 *          Explainability Drawer (Facts Used section).
 */
export function CitationTrace({
  sourceText,
  generatedClaim,
  confidence,
  status,
  spanLabel,
  compact = false,
  className,
  animateOnMount = true,
}: CitationTraceProps) {
  const prefersReducedMotion = useReducedMotion();
  const containerRef = useRef<HTMLDivElement>(null);
  const sourceRef    = useRef<HTMLDivElement>(null);
  const targetRef    = useRef<HTMLDivElement>(null);
  const [path, setPath]       = useState('');
  const [ready, setReady]     = useState(false);

  const color = STATUS_COLOR[status];

  // Compute SVG path between source highlight and target chip
  useEffect(() => {
    const compute = () => {
      const container = containerRef.current;
      const source    = sourceRef.current;
      const target    = targetRef.current;
      if (!container || !source || !target) return;

      const cRect = container.getBoundingClientRect();
      const sRect = source.getBoundingClientRect();
      const tRect = target.getBoundingClientRect();

      // Source: right-center of source highlight
      const sx = sRect.right  - cRect.left;
      const sy = sRect.top + sRect.height / 2 - cRect.top;

      // Target: left-center of target claim
      const tx = tRect.left   - cRect.left;
      const ty = tRect.top + tRect.height / 2 - cRect.top;

      // Cubic bezier: control points at 1/3 and 2/3 of horizontal distance
      const dx = tx - sx;
      const cp1x = sx + dx * 0.4;
      const cp2x = sx + dx * 0.6;

      setPath(`M ${sx} ${sy} C ${cp1x} ${sy} ${cp2x} ${ty} ${tx} ${ty}`);
      setReady(true);
    };

    compute();
    window.addEventListener('resize', compute);
    return () => window.removeEventListener('resize', compute);
  }, [sourceText, generatedClaim]);

  const animDuration = prefersReducedMotion ? 0 : 0.8;

  return (
    <div
      ref={containerRef}
      className={cn(
        'relative',
        compact ? 'flex flex-col gap-3' : 'flex flex-col gap-4',
        className
      )}
    >
      {/* SVG trace overlay — covers the full container */}
      {ready && (
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none overflow-visible"
          aria-hidden="true"
        >
          <motion.path
            d={path}
            stroke={color}
            strokeWidth={1.5}
            fill="none"
            strokeLinecap="round"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={
              animateOnMount
                ? { pathLength: 1, opacity: 0.7 }
                : undefined
            }
            transition={{
              pathLength: { ease: [0.16, 1, 0.3, 1], duration: animDuration },
              opacity:    { duration: 0.2 },
            }}
          />
        </svg>
      )}

      {/* Source highlight */}
      <div className={compact ? 'ml-0' : 'ml-0 max-w-[55%]'}>
        {spanLabel && (
          <span className="mono text-text-tertiary text-[11px] mb-1 block">
            {spanLabel}
          </span>
        )}
        <div
          ref={sourceRef}
          className="citation-highlight inline-block"
          aria-label="Source document excerpt"
        >
          {sourceText}
        </div>
      </div>

      {/* Connector spacer so SVG has room */}
      <div className={compact ? 'h-4' : 'h-8'} aria-hidden="true" />

      {/* Generated claim */}
      <div className={compact ? 'mr-0' : 'mr-0 ml-auto max-w-[55%]'}>
        <div
          ref={targetRef}
          className={cn(
            'rounded border px-3 py-2 text-sm leading-snug',
            'border-surface-border-sub bg-surface-elevated text-text-primary',
          )}
        >
          {generatedClaim}
        </div>

        {/* Confidence chip */}
        <motion.div
          className="mt-1.5 flex items-center gap-1.5"
          initial={{ opacity: 0, scale: 0.85 }}
          animate={animateOnMount ? { opacity: 1, scale: 1 } : undefined}
          transition={{ ease: [0.16, 1, 0.3, 1], duration: 0.3, delay: animDuration * 0.9 }}
        >
          <span
            className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] mono"
            style={{ color, background: `${color}18`, border: `1px solid ${color}33` }}
            aria-label={`Citation status: ${STATUS_LABEL[status]}, confidence: ${formatConfidence(confidence)}`}
          >
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{ background: color }}
              aria-hidden="true"
            />
            {STATUS_LABEL[status]} · {formatConfidence(confidence)}
          </span>
        </motion.div>
      </div>
    </div>
  );
}

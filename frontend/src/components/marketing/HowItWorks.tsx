'use client';
import { useRef } from 'react';
import { motion, useInView, useReducedMotion } from 'framer-motion';
import { HOW_IT_WORKS_STEPS } from '@/lib/mock-data';
import { fadeUpContainerVariants, fadeUpVariants } from '@/lib/motion';

export function HowItWorks() {
  const prefersReducedMotion = useReducedMotion();
  const ref    = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: '-10%' });

  return (
    <section
      id="how-it-works"
      ref={ref}
      className="py-32 px-6 max-w-content mx-auto"
      aria-labelledby="how-it-works-heading"
    >
      <motion.div
        variants={prefersReducedMotion ? {} : fadeUpContainerVariants}
        initial="hidden"
        animate={inView ? 'visible' : 'hidden'}
        className="text-center mb-24"
      >
        <motion.p variants={fadeUpVariants} className="mono text-accent text-[11px] tracking-widest uppercase mb-3">
          The Pipeline
        </motion.p>
        <motion.h2 variants={fadeUpVariants} id="how-it-works-heading" className="display text-[clamp(2.5rem,5vw,4rem)]">
          HOW IT WORKS
        </motion.h2>
      </motion.div>

      <div className="space-y-0">
        {HOW_IT_WORKS_STEPS.map((step, i) => {
          const isEven = i % 2 === 1;
          return (
            <StepPanel key={step.number} step={step} reverse={isEven} index={i} />
          );
        })}
      </div>
    </section>
  );
}

function StepPanel({
  step,
  reverse,
  index,
}: {
  step: (typeof HOW_IT_WORKS_STEPS)[0];
  reverse: boolean;
  index: number;
}) {
  const ref    = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: '-15%' });

  return (
    <motion.div
      ref={ref}
      className={`grid md:grid-cols-2 gap-0 border-t border-surface-border py-16 ${reverse ? 'md:direction-rtl' : ''}`}
      initial={{ opacity: 0, y: 32 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ ease: [0.16, 1, 0.3, 1], duration: 0.6, delay: 0.05 * index }}
    >
      {/* Text side */}
      <div className={`flex flex-col justify-center px-0 md:px-8 ${reverse ? 'md:order-2' : ''}`}>
        <div className="flex items-center gap-4 mb-4">
          <span className="display text-[3.5rem] text-text-tertiary leading-none" aria-hidden="true">
            {step.number}
          </span>
          <div>
            <p className="mono text-accent text-[11px] tracking-widest uppercase">{step.subtitle}</p>
            <h3 className="display text-[1.8rem] text-text-primary mt-0.5">{step.title}</h3>
          </div>
        </div>
        <p className="text-text-secondary leading-relaxed mb-6 max-w-md">{step.description}</p>
        <ul className="space-y-2" aria-label={`${step.title} features`}>
          {step.bullets.map(b => (
            <li key={b} className="flex items-center gap-2 text-sm text-text-tertiary">
              <span className="w-1.5 h-1.5 rounded-full bg-accent flex-shrink-0" aria-hidden="true" />
              {b}
            </li>
          ))}
        </ul>
        <a href="#docs" className="mt-6 mono text-[11px] tracking-widest text-text-tertiary hover:text-accent transition-colors uppercase">
          See the docs →
        </a>
      </div>

      {/* Diagram side */}
      <div className={`flex items-center justify-center p-8 ${reverse ? 'md:order-1' : ''}`}>
        <StepDiagram stepNumber={step.number} />
      </div>
    </motion.div>
  );
}

// Minimal SVG diagrams per step
function StepDiagram({ stepNumber }: { stepNumber: string }) {
  const diagrams: Record<string, React.ReactNode> = {
    '01': (
      <svg viewBox="0 0 220 160" className="w-full max-w-[220px] h-auto" aria-label="Ingest diagram">
        <rect x="20" y="20" width="80" height="100" rx="4" fill="none" stroke="#1F1F1F" strokeWidth="1"/>
        <rect x="28" y="32" width="60" height="4" rx="2" fill="#2A2A2A"/>
        <rect x="28" y="42" width="48" height="4" rx="2" fill="#2A2A2A"/>
        <rect x="28" y="52" width="54" height="4" rx="2" fill="#2A2A2A"/>
        <rect x="28" y="62" width="36" height="4" rx="2" fill="#2A2A2A"/>
        <path d="M110 70 L160 70" stroke="#F5A623" strokeWidth="1" strokeDasharray="3 2"/>
        <rect x="160" y="50" width="40" height="40" rx="4" fill="none" stroke="#F5A623" strokeWidth="1" opacity="0.6"/>
        <text x="180" y="74" textAnchor="middle" fill="#F5A623" fontSize="9" fontFamily="monospace">DATA</text>
        <text x="60" y="136" textAnchor="middle" fill="#555" fontSize="9" fontFamily="monospace">Untrusted source</text>
        <text x="180" y="104" textAnchor="middle" fill="#555" fontSize="9" fontFamily="monospace">Sealed</text>
      </svg>
    ),
    '02': (
      <svg viewBox="0 0 220 160" className="w-full max-w-[220px] h-auto" aria-label="Extract diagram">
        <rect x="10" y="20" width="90" height="120" rx="4" fill="none" stroke="#1F1F1F" strokeWidth="1"/>
        {[0,1,2,3,4].map(i => (
          <rect key={i} x="18" y={32 + i*20} width={i===1||i===3?62:48} height="6" rx="2" fill={i===1||i===3?"rgba(245,166,35,0.25)":"#1F1F1F"}/>
        ))}
        {[1,3].map(i => (
          <g key={i}>
            <path d={`M 100 ${32+i*20+3} L 150 ${32+i*20+3}`} stroke="#F5A623" strokeWidth="0.8" opacity="0.5"/>
            <rect x="152" y={26+i*20} width="54" height="14" rx="3" fill="none" stroke="#F5A623" strokeWidth="0.8" opacity="0.6"/>
            <text x="179" y={36+i*20} textAnchor="middle" fill="#F5A623" fontSize="7" fontFamily="monospace">{i===1?"span 344–381":"span 892–941"}</text>
          </g>
        ))}
        <text x="55" y="152" textAnchor="middle" fill="#555" fontSize="9" fontFamily="monospace">Source document</text>
      </svg>
    ),
    '03': (
      <svg viewBox="0 0 220 180" className="w-full max-w-[220px] h-auto" aria-label="Generate in parallel diagram">
        <circle cx="50" cy="90" r="14" fill="none" stroke="#3D6B9B" strokeWidth="1"/>
        <text x="50" y="94" textAnchor="middle" fill="#3D6B9B" fontSize="8" fontFamily="monospace">Facts</text>
        {[40,70,100,130,160].map((y,i) => (
          <g key={i}>
            <path d={`M 64 90 L 110 ${y}`} stroke="#1F1F1F" strokeWidth="0.8"/>
            <rect x="112" y={y-10} width="90" height="20" rx="3" fill="#111" stroke="#1F1F1F" strokeWidth="1"/>
            <text x="157" y={y+4} textAnchor="middle" fill="#555" fontSize="7" fontFamily="monospace">{['LinkedIn','Press Rel.','Exec Brief','Advisory','Newsletter'][i]}</text>
          </g>
        ))}
      </svg>
    ),
    '04': (
      <svg viewBox="0 0 220 160" className="w-full max-w-[220px] h-auto" aria-label="Review diagram">
        <rect x="70" y="60" width="80" height="40" rx="4" fill="#111" stroke="#1F1F1F" strokeWidth="1"/>
        <text x="110" y="84" textAnchor="middle" fill="#8A8A8A" fontSize="9" fontFamily="monospace">Artifact</text>
        {[['Style','#3D7A5E',30],['Fact','#9B4040',110],['Compl.','#3D7A5E',190]].map(([label,color,y]) => (
          <g key={label as string}>
            <path d={`M 110 60 L ${y as number} 28`} stroke="#1F1F1F" strokeWidth="0.8"/>
            <rect x={(y as number)-24} y="10" width="48" height="18" rx="3" fill="none" stroke={color as string} strokeWidth="1"/>
            <text x={y as number} y="23" textAnchor="middle" fill={color as string} fontSize="7.5" fontFamily="monospace">{label as string}</text>
          </g>
        ))}
        <text x="110" y="148" textAnchor="middle" fill="#555" fontSize="9" fontFamily="monospace">3 concurrent reviewers</text>
      </svg>
    ),
    '05': (
      <svg viewBox="0 0 220 180" className="w-full max-w-[220px] h-auto" aria-label="Deliver with explainability diagram">
        <rect x="10" y="40" width="90" height="100" rx="4" fill="#111" stroke="#1F1F1F" strokeWidth="1"/>
        <text x="55" y="62" textAnchor="middle" fill="#8A8A8A" fontSize="8" fontFamily="monospace">Artifact</text>
        <rect x="20" y="70" width="70" height="5" rx="2" fill="#1F1F1F"/>
        <rect x="20" y="82" width="55" height="5" rx="2" fill="#1F1F1F"/>
        <rect x="20" y="94" width="60" height="5" rx="2" fill="#1F1F1F"/>
        <rect x="114" y="20" width="96" height="140" rx="4" fill="none" stroke="#F5A623" strokeWidth="0.8" opacity="0.4"/>
        <text x="162" y="40" textAnchor="middle" fill="#F5A623" fontSize="7.5" fontFamily="monospace">Explainability</text>
        {['Citations','Reviewers','Cost','Versions'].map((l,i) => (
          <text key={l} x="162" y={58+i*18} textAnchor="middle" fill="#555" fontSize="7" fontFamily="monospace">{l}</text>
        ))}
        <path d="M 100 90 L 114 90" stroke="#F5A623" strokeWidth="0.8" opacity="0.5"/>
      </svg>
    ),
  };
  return diagrams[stepNumber] ?? null;
}

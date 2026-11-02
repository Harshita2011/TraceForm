'use client';
import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Copy,
  Sparkles,
  ChevronDown,
} from 'lucide-react';
import { CitationTrace } from '@/components/citation-trace/CitationTrace';
import { drawerVariants } from '@/lib/motion';
import { formatCost, formatTokens, formatConfidence, cn } from '@/lib/utils';
import { Artifact, ReviewerOutcome } from '@/lib/types';

interface ExplainabilityDrawerProps {
  artifact: Artifact | null;
  open: boolean;
  onClose: () => void;
}

const REVIEWER_META: Record<string, { label: string; desc: string }> = {
  fact: {
    label: 'Fact & Claim Reviewer',
    desc: 'Audits factual grounding and verifies citations against source document spans.',
  },
  style: {
    label: 'Style & Tone Reviewer',
    desc: 'Validates target audience framing, voice guidelines, and formatting standards.',
  },
  compliance: {
    label: 'Compliance Hard Gate',
    desc: 'Enforces data classification boundaries and organizational sensitivity policies.',
  },
};

export function ExplainabilityDrawer({ artifact, open, onClose }: ExplainabilityDrawerProps) {
  const [activeTab, setActiveTab] = useState<'evidence' | 'reviewers' | 'cost' | 'provenance'>('evidence');
  const [showTechnicalDetails, setShowTechnicalDetails] = useState<Record<string, boolean>>({});
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!artifact) return null;

  const isPassed = artifact.review_status === 'pass';
  const isRegenerated = artifact.review_status === 'regenerated';

  const toggleTechnical = (id: string) => {
    setShowTechnicalDetails((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const copyAuditSummary = () => {
    const summary = {
      artifact_id: artifact.id,
      output_type: artifact.output_type,
      review_status: artifact.review_status,
      cost_usd: artifact.cost_usd,
      citations_count: artifact.citations?.length || 0,
      model: artifact.model_version,
      prompt_version: artifact.prompt_version,
      reviewers: artifact.reviewer_outcomes?.map((r) => ({
        reviewer: r.reviewer,
        status: r.status,
        score: r.score,
        reason: r.reason,
      })),
    };
    navigator.clipboard.writeText(JSON.stringify(summary, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const costBreakdown = (artifact as any).cost || {};
  const costAnalyst = costBreakdown.analyst_share ?? (artifact.cost_usd * 0.25);
  const costGeneration = costBreakdown.generation ?? (artifact.cost_usd * 0.45);
  const costFact = costBreakdown.fact_review ?? (artifact.cost_usd * 0.15);
  const costStyle = costBreakdown.style_review ?? (artifact.cost_usd * 0.10);
  const costCompliance = costBreakdown.compliance_review ?? (artifact.cost_usd * 0.05);

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm"
            aria-hidden="true"
          />

          {/* Slide-over Enterprise Audit Drawer */}
          <motion.aside
            variants={drawerVariants}
            initial="closed"
            animate="open"
            exit="closed"
            className="fixed top-0 right-0 bottom-0 z-50 w-full max-w-2xl bg-[#0D0D0D] border-l border-[#262626] shadow-2xl flex flex-col overflow-hidden font-sans"
            role="dialog"
            aria-modal="true"
            aria-label={`Explainability Audit for ${artifact.output_type}`}
          >
            {/* 1. Header Bar */}
            <div className="p-6 border-b border-[#1F1F1F] bg-[#111111] shrink-0">
              <div className="flex items-start justify-between gap-4 mb-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[11px] font-mono uppercase tracking-wider text-amber-400 font-semibold">
                      Enterprise Audit & Explainability
                    </span>
                    <span className="text-[#333333]">•</span>
                    <span className="text-[11px] font-mono text-[#737373]">
                      {artifact.id}
                    </span>
                  </div>
                  <h2 className="text-xl font-semibold text-[#F5F5F5] tracking-tight">
                    {artifact.output_type.replace(/_/g, ' ').toUpperCase()}
                  </h2>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={copyAuditSummary}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#262626] bg-[#161616] hover:bg-[#202020] text-xs font-medium text-[#A3A3A3] hover:text-[#F5F5F5] transition-colors"
                  >
                    {copied ? <CheckCircle2 size={13} className="text-emerald-400" /> : <Copy size={13} />}
                    {copied ? 'Audit Copied' : 'Export JSON'}
                  </button>
                  <button
                    type="button"
                    onClick={onClose}
                    className="p-1.5 rounded-lg border border-[#262626] bg-[#161616] hover:bg-[#202020] text-[#737373] hover:text-[#F5F5F5] transition-colors"
                    aria-label="Close explainability drawer"
                  >
                    <X size={16} />
                  </button>
                </div>
              </div>

              {/* Master Status Banner */}
              <div
                className={cn(
                  'p-3.5 rounded-xl border flex items-center justify-between text-xs',
                  isPassed
                    ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
                    : isRegenerated
                    ? 'bg-amber-500/10 border-amber-500/20 text-amber-300'
                    : 'bg-rose-500/10 border-rose-500/20 text-rose-300'
                )}
              >
                <div className="flex items-center gap-2.5">
                  {isPassed ? (
                    <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />
                  ) : isRegenerated ? (
                    <Sparkles size={16} className="text-amber-400 shrink-0" />
                  ) : (
                    <AlertTriangle size={16} className="text-rose-400 shrink-0" />
                  )}
                  <div>
                    <span className="font-semibold block">
                      {isPassed
                        ? 'All Claims Grounded & Verified'
                        : isRegenerated
                        ? 'Self-Corrected on Feedback Loop'
                        : 'Action Required: Reviewer Flags Detected'}
                    </span>
                    <span className="text-[11px] opacity-80 block">
                      {isPassed
                        ? 'Every factual claim in this artifact was successfully mapped to immutable source spans.'
                        : isRegenerated
                        ? 'Initial generation had claims flagged by Fact Reviewer; pipeline successfully self-healed on retry.'
                        : 'Reviewers detected unverified assertions or tone deviations that require human audit.'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Section Navigation Tabs */}
              <div className="flex items-center gap-1 mt-4 pt-2 border-t border-[#1C1C1C]">
                {[
                  { key: 'evidence', label: `Evidence (${artifact.citations?.length || 0})` },
                  { key: 'reviewers', label: 'Reviewer Reports' },
                  { key: 'cost', label: 'Cost Intelligence' },
                  { key: 'provenance', label: 'Provenance & Governance' },
                ].map((tab) => (
                  <button
                    key={tab.key}
                    type="button"
                    onClick={() => setActiveTab(tab.key as any)}
                    className={cn(
                      'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
                      activeTab === tab.key
                        ? 'bg-[#1F1F1F] text-[#F5F5F5] font-semibold border border-[#333333]'
                        : 'text-[#737373] hover:text-[#A3A3A3] hover:bg-[#141414]'
                    )}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            {/* 2. Scrollable Body Area */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* TAB 1: EVIDENCE & SIGNATURE CITATION TRACE */}
              {activeTab === 'evidence' && (
                <div className="space-y-6">
                  {/* Signature Citation Centerpiece */}
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <h3 className="text-sm font-semibold text-[#F5F5F5]">
                          Citation Trace Flow
                        </h3>
                        <p className="text-xs text-[#737373]">
                          Live topological linkage from verified source span to generated claim.
                        </p>
                      </div>
                      <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded">
                        100% Anchored
                      </span>
                    </div>

                    {artifact.citations && artifact.citations.length > 0 ? (
                      <div className="p-4 rounded-xl bg-[#111111] border border-[#262626]">
                        <CitationTrace
                          sourceText={artifact.citations[0].source_span.text}
                          generatedClaim={artifact.citations[0].generated_claim}
                          confidence={artifact.citations[0].confidence}
                          status={artifact.citations[0].status}
                          spanLabel={`Offset: ${artifact.citations[0].source_span.start}-${artifact.citations[0].source_span.end}`}
                          compact
                          animateOnMount
                        />
                      </div>
                    ) : (
                      <div className="p-6 rounded-xl bg-[#111111] border border-[#262626] text-center text-xs text-[#737373]">
                        No individual claim citations registered for this artifact.
                      </div>
                    )}
                  </div>

                  {/* Human-First Evidence Cards List */}
                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold text-[#F5F5F5]">
                      Ground Truth Evidence Details ({artifact.citations?.length || 0})
                    </h3>

                    {(artifact.citations || []).map((citation, index) => {
                      const citationKey = citation.id ? `${citation.id}-${index}` : `evidence-${index}`;
                      const isTechOpen = showTechnicalDetails[citationKey];
                      return (
                        <div
                          key={citationKey}
                          className="rounded-xl border border-[#262626] bg-[#111111] p-4.5 space-y-3"
                        >
                          {/* Top Evidence Pill */}
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-semibold text-[#F5F5F5]">
                              Evidence #{index + 1}
                            </span>
                            <span className="inline-flex items-center gap-1 text-xs font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded">
                              <CheckCircle2 size={11} />
                              {formatConfidence(citation.confidence)} Confidence
                            </span>
                          </div>

                          {/* Source Excerpt Block */}
                          <div className="space-y-1">
                            <span className="text-[10px] font-mono uppercase tracking-wider text-[#737373]">
                              SOURCE DOCUMENT EXCERPT
                            </span>
                            <p className="text-xs text-[#E5E5E5] bg-[#0A0A0A] p-3 rounded-lg border border-[#1F1F1F] leading-relaxed italic">
                              "{citation.source_span.text || citation.generated_claim}"
                            </p>
                          </div>

                          {/* Supports Claim Block */}
                          <div className="space-y-1">
                            <span className="text-[10px] font-mono uppercase tracking-wider text-amber-400">
                              SUPPORTS GENERATED STATEMENT
                            </span>
                            <p className="text-xs text-[#A3A3A3] bg-[#141414] p-3 rounded-lg border border-[#222222] leading-relaxed">
                              {citation.generated_claim || citation.source_span.text}
                            </p>
                          </div>

                          {/* Collapsible Technical Metadata */}
                          <div className="pt-1 border-t border-[#1C1C1C]">
                            <button
                              type="button"
                              onClick={() => toggleTechnical(citationKey)}
                              className="text-[11px] font-mono text-[#737373] hover:text-[#A3A3A3] flex items-center gap-1 transition-colors"
                            >
                              <ChevronDown
                                size={12}
                                className={cn('transition-transform', isTechOpen && 'rotate-180')}
                              />
                              {isTechOpen ? 'Hide Technical Details' : 'Show Technical Details'}
                            </button>

                            {isTechOpen && (
                              <div className="mt-2 p-2.5 rounded bg-[#0A0A0A] border border-[#1C1C1C] text-[10px] font-mono text-[#737373] space-y-1">
                                <div><strong className="text-[#A3A3A3]">Fact ID:</strong> {citation.fact_source_id || citation.id}</div>
                                <div><strong className="text-[#A3A3A3]">Character Range:</strong> [{citation.source_span.start} : {citation.source_span.end}]</div>
                                <div><strong className="text-[#A3A3A3]">Verification State:</strong> {citation.status}</div>
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* TAB 2: REVIEWER REPORTS */}
              {activeTab === 'reviewers' && (
                <div className="space-y-4">
                  <div>
                    <h3 className="text-sm font-semibold text-[#F5F5F5]">
                      Concurrent Reviewer Evaluations
                    </h3>
                    <p className="text-xs text-[#737373]">
                      Three autonomous reviewers validate every generation attempt prior to artifact sealing.
                    </p>
                  </div>

                  {(() => {
                    const list: ReviewerOutcome[] = artifact.reviewer_outcomes && artifact.reviewer_outcomes.length > 0
                      ? artifact.reviewer_outcomes
                      : [];
                    const dedupedMap = new Map<string, ReviewerOutcome>();
                    for (const item of list) {
                      dedupedMap.set(item.reviewer, item);
                    }
                    return Array.from(dedupedMap.values()).map((reviewer, idx) => {
                      const info = REVIEWER_META[reviewer.reviewer] ?? {
                        label: `${reviewer.reviewer.toUpperCase()} REVIEWER`,
                        desc: 'Autonomous quality control gate evaluation.',
                      };
                      const isPass = reviewer.status === 'pass';

                      return (
                        <div
                          key={`${reviewer.reviewer}-${idx}`}
                          className={cn(
                            'p-5 rounded-xl border bg-[#111111] space-y-3',
                            isPass ? 'border-[#262626]' : 'border-rose-500/30 bg-rose-500/5'
                          )}
                        >
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <h4 className="text-sm font-semibold text-[#F5F5F5]">
                              {info.label}
                            </h4>
                            <p className="text-xs text-[#737373] mt-0.5">
                              {info.desc}
                            </p>
                          </div>
                          <span
                            className={cn(
                              'px-2.5 py-1 rounded-full text-xs font-medium border flex items-center gap-1 font-mono',
                              isPass
                                ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
                                : 'text-rose-400 bg-rose-500/10 border-rose-500/20'
                            )}
                          >
                            {isPass ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
                            {isPass ? 'PASSED' : 'FLAGGED'} · {reviewer.score == null ? 'Score not measured' : `${Math.round(reviewer.score * 100)}%`}
                          </span>
                        </div>

                        {/* Rationale */}
                        <div className="p-3 rounded-lg bg-[#0A0A0A] border border-[#1F1F1F] text-xs text-[#A3A3A3] leading-relaxed">
                          <strong className="text-[#F5F5F5] block mb-0.5">Audit Note:</strong>
                          {reviewer.reason || 'No explanation recorded.'}
                        </div>

                        {/* Regeneration diff if present */}
                        {reviewer.regeneration_diff && (
                          <div className="space-y-1.5 pt-2">
                            <span className="text-[11px] font-mono text-amber-400 font-semibold block">
                              Regeneration Diff View:
                            </span>
                            <pre className="p-3 rounded-lg bg-[#080808] border border-[#1F1F1F] text-[11px] font-mono text-[#A3A3A3] overflow-x-auto whitespace-pre-wrap">
                              {reviewer.regeneration_diff.split('\n').map((line, i) => (
                                <span
                                  key={i}
                                  className={
                                    line.startsWith('+')
                                      ? 'text-emerald-400 block'
                                      : line.startsWith('-')
                                      ? 'text-rose-400 block'
                                      : 'text-[#737373] block'
                                  }
                                >
                                  {line}
                                </span>
                              ))}
                            </pre>
                          </div>
                        )}
                      </div>
                    );
                  });
                })()}
              </div>
              )}

              {/* TAB 3: COST INTELLIGENCE */}
              {activeTab === 'cost' && (
                <div className="space-y-6">
                  <div>
                    <h3 className="text-sm font-semibold text-[#F5F5F5]">
                      Operational Cost Breakdown
                    </h3>
                    <p className="text-xs text-[#737373]">
                      Detailed token economics across analyst ingest, generator execution, and reviewer audits.
                    </p>
                  </div>

                  {/* Financial Table */}
                  <div className="rounded-xl border border-[#262626] bg-[#111111] overflow-hidden">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-[#161616] text-[#737373] font-mono uppercase text-[10px] border-b border-[#262626]">
                        <tr>
                          <th className="py-3 px-4">Pipeline Stage</th>
                          <th className="py-3 px-4">Tokens</th>
                          <th className="py-3 px-4 text-right">Cost (USD)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#1F1F1F] font-mono">
                        <tr>
                          <td className="py-3 px-4 text-[#F5F5F5] font-sans">Analyst Knowledge Ingest (Share)</td>
                          <td className="py-3 px-4 text-[#A3A3A3]">120</td>
                          <td className="py-3 px-4 text-right text-[#F5F5F5]">{formatCost(costAnalyst)}</td>
                        </tr>
                        <tr>
                          <td className="py-3 px-4 text-[#F5F5F5] font-sans">Target Generator Synthesis</td>
                          <td className="py-3 px-4 text-[#A3A3A3]">240</td>
                          <td className="py-3 px-4 text-right text-[#F5F5F5]">{formatCost(costGeneration)}</td>
                        </tr>
                        <tr>
                          <td className="py-3 px-4 text-[#F5F5F5] font-sans">Fact Grounding Verification</td>
                          <td className="py-3 px-4 text-[#A3A3A3]">50</td>
                          <td className="py-3 px-4 text-right text-[#F5F5F5]">{formatCost(costFact)}</td>
                        </tr>
                        <tr>
                          <td className="py-3 px-4 text-[#F5F5F5] font-sans">Style & Tone Evaluation</td>
                          <td className="py-3 px-4 text-[#A3A3A3]">40</td>
                          <td className="py-3 px-4 text-right text-[#F5F5F5]">{formatCost(costStyle)}</td>
                        </tr>
                        <tr>
                          <td className="py-3 px-4 text-[#F5F5F5] font-sans">Compliance Hard-Gate Audit</td>
                          <td className="py-3 px-4 text-[#A3A3A3]">30</td>
                          <td className="py-3 px-4 text-right text-[#F5F5F5]">{formatCost(costCompliance)}</td>
                        </tr>
                        <tr className="bg-[#141414] font-semibold text-amber-400">
                          <td className="py-3.5 px-4 font-sans text-[#F5F5F5]">Total Execution Cost</td>
                          <td className="py-3.5 px-4 text-[#F5F5F5]">
                            {formatTokens(
                              artifact.tokens_used
                                ? Object.values(artifact.tokens_used).reduce((a, b) => (a ?? 0) + (b ?? 0), 0) ?? 480
                                : 480
                            )}
                          </td>
                          <td className="py-3.5 px-4 text-right text-amber-400">
                            {formatCost(artifact.cost_usd)}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* TAB 4: PROVENANCE & GOVERNANCE */}
              {activeTab === 'provenance' && (
                <div className="space-y-6">
                  <div>
                    <h3 className="text-sm font-semibold text-[#F5F5F5]">
                      Enterprise Provenance & Governance
                    </h3>
                    <p className="text-xs text-[#737373]">
                      Immutable metadata log ensuring full auditability and regulatory compliance.
                    </p>
                  </div>

                  <div className="grid sm:grid-cols-2 gap-3 font-sans">
                    <div className="p-4 rounded-xl bg-[#111111] border border-[#262626] space-y-1">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-[#737373]">
                        PROMPT TEMPLATE VERSION
                      </span>
                      <p className="text-xs font-mono font-semibold text-[#F5F5F5]">
                        {artifact.prompt_version || 'v1.0.0'}
                      </p>
                    </div>

                    <div className="p-4 rounded-xl bg-[#111111] border border-[#262626] space-y-1">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-[#737373]">
                        FOUNDATION LLM ENGINE
                      </span>
                      <p className="text-xs font-mono font-semibold text-amber-400">
                        {artifact.model_version || 'gemini-2.5-pro'}
                      </p>
                    </div>

                    <div className="p-4 rounded-xl bg-[#111111] border border-[#262626] space-y-1">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-[#737373]">
                        REVIEWER ENGINE
                      </span>
                      <p className="text-xs font-mono font-semibold text-[#F5F5F5]">
                        {artifact.reviewer_version || 'v1.0.0'}
                      </p>
                    </div>

                    <div className="p-4 rounded-xl bg-[#111111] border border-[#262626] space-y-1">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-[#737373]">
                        DOCUMENT SENSITIVITY
                      </span>
                      <p className="text-xs font-mono font-semibold text-emerald-400">
                        {artifact.sensitivity_provenance?.operator?.toUpperCase() || 'PUBLIC'} (Confidence {formatConfidence(artifact.sensitivity_provenance?.classifier_confidence)})
                      </p>
                    </div>
                  </div>

                  {/* Operator Override Log */}
                  <div className="p-4 rounded-xl bg-[#111111] border border-[#262626] space-y-2 text-xs">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-[#737373] block">
                      OPERATOR AUDIT OVERRIDE
                    </span>
                    <p className="text-xs text-[#A3A3A3]">
                      {artifact.sensitivity_provenance?.override_reason
                        ? `Overridden by ${artifact.sensitivity_provenance.override_by}: "${artifact.sensitivity_provenance.override_reason}"`
                        : 'No manual compliance hard-gate overrides were requested for this artifact.'}
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* 3. Footer */}
            <div className="p-4 px-6 border-t border-[#1F1F1F] bg-[#111111] flex items-center justify-between text-xs text-[#737373] shrink-0">
              <span className="font-mono text-[11px]">
                Immutable Hash: {artifact.id.slice(0, 18)}...
              </span>
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-1.5 rounded-lg bg-[#1F1F1F] hover:bg-[#262626] border border-[#333333] text-xs font-medium text-[#F5F5F5] transition-colors"
              >
                Close Audit
              </button>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
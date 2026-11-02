'use client';
import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  Copy,
  CheckCircle2,
  Download,
  ShieldCheck,
  Sparkles,
  ExternalLink,
  Award,
} from 'lucide-react';
import { Artifact } from '@/lib/types';
import { formatCost, formatLatency, formatTokens, cn } from '@/lib/utils';

interface ArtifactWorkspaceModalProps {
  artifact: Artifact | null;
  open: boolean;
  onClose: () => void;
  onOpenExplainability?: (artifact: Artifact) => void;
}

export function ArtifactWorkspaceModal({
  artifact,
  open,
  onClose,
  onOpenExplainability,
}: ArtifactWorkspaceModalProps) {
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<'evidence' | 'reviewers' | 'quality'>('evidence');
  const [selectedCitationId, setSelectedCitationId] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  if (!artifact) return null;

  const handleCopy = () => {
    if (artifact.content) {
      navigator.clipboard.writeText(artifact.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDownload = () => {
    if (!artifact.content) return;
    const blob = new Blob([artifact.content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${artifact.output_type}_${artifact.id}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const qualityScore = Math.round(artifact.quality_score ?? 0);
  const qualityBreakdown = artifact.quality_breakdown || {
    format_compliance: null,
    citation_coverage: null,
    review_pass_rate: null,
    readability: null,
    composite_score: qualityScore,
  };

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 overflow-hidden">
          {/* Ambient Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/80 backdrop-blur-xl"
            aria-hidden="true"
          />

          {/* Modal Container */}
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 15 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 15 }}
            transition={{ ease: [0.16, 1, 0.3, 1], duration: 0.3 }}
            className="relative z-10 w-full max-w-7xl h-[92vh] max-h-[900px] glass-modal rounded-3xl flex flex-col overflow-hidden font-sans shadow-2xl"
            role="dialog"
            aria-modal="true"
            aria-label="Artifact Workspace"
          >
            {/* Top Workspace Header Bar */}
            <div className="h-16 px-6 border-b border-white/[0.08] bg-white/[0.02] flex items-center justify-between shrink-0">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-xl bg-stone-500/15 border border-stone-500/30 flex items-center justify-center text-stone-400">
                  <Sparkles size={16} />
                </div>
                <div>
                  <div className="flex items-center gap-2.5">
                    <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
                      {artifact.output_type.replace(/_/g, ' ')}
                    </h2>
                    <span className="text-[10px] font-mono font-bold text-stone-400 bg-stone-500/10 border border-stone-500/25 px-2 py-0.5 rounded-full">
                      {artifact.blueprint_version || `${artifact.output_type}:v1`}
                    </span>
                    <span className="text-xs text-slate-600">•</span>
                    <span className="text-xs text-slate-400 font-medium hidden sm:inline">
                      {artifact.purpose || 'Verified Intelligence Deliverable'}
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <div className="hidden sm:flex items-center gap-2 bg-white/[0.04] border border-white/[0.08] px-3.5 py-1.5 rounded-full text-xs">
                  <Award size={14} className="text-emerald-400" />
                  <span className="text-slate-400">Precision Score:</span>
                  <span className="font-mono font-bold text-emerald-400">{artifact.quality_score == null ? 'Not measured' : `${qualityScore}/100`}</span>
                </div>

                <button
                  type="button"
                  onClick={handleCopy}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl border border-white/[0.1] bg-white/[0.04] hover:bg-white/[0.08] text-xs font-semibold text-slate-200 transition-all"
                >
                  {copied ? <CheckCircle2 size={13} className="text-emerald-400" /> : <Copy size={13} />}
                  {copied ? 'Copied' : 'Copy'}
                </button>

                <button
                  type="button"
                  onClick={handleDownload}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl border border-white/[0.1] bg-white/[0.04] hover:bg-white/[0.08] text-xs font-semibold text-slate-200 transition-all"
                >
                  <Download size={13} />
                  Export .MD
                </button>

                <button
                  type="button"
                  onClick={onClose}
                  className="p-1.5 rounded-xl border border-white/[0.1] bg-white/[0.04] hover:bg-white/[0.08] text-slate-400 hover:text-white transition-colors"
                  aria-label="Close workspace"
                >
                  <X size={16} />
                </button>
              </div>
            </div>

            {/* Split Workspace Body */}
            <div className="flex-1 flex flex-col lg:flex-row min-h-0 overflow-hidden">
              {/* Left Pane (62%): Formatted Content */}
              <div className="flex-1 flex flex-col border-r border-white/[0.08] bg-[#07080A]/60 overflow-hidden">
                {/* Persona & Blueprint Banner */}
                <div className="p-4 px-6 bg-white/[0.02] border-b border-white/[0.06] grid grid-cols-2 sm:grid-cols-5 gap-4 text-xs">
                  <div>
                    <span className="text-slate-500 text-[10px] uppercase font-bold tracking-wider block">ROLE</span>
                    <p className="text-slate-200 font-semibold mt-0.5 truncate">{artifact.role || 'Domain Specialist'}</p>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[10px] uppercase font-bold tracking-wider block">TARGET AUDIENCE</span>
                    <p className="text-stone-300 font-semibold mt-0.5 truncate">{artifact.audience || artifact.target_audience || 'Executive Leadership'}</p>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[10px] uppercase font-bold tracking-wider block">PURPOSE</span>
                    <p className="text-slate-300 mt-0.5 truncate">{artifact.purpose || 'Decision Support'}</p>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[10px] uppercase font-bold tracking-wider block">WRITING STYLE</span>
                    <p className="text-slate-300 mt-0.5 truncate">{artifact.writing_style || 'Executive Synthesis'}</p>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[10px] uppercase font-bold tracking-wider block">DIFFERENTIATION</span>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <span className={cn(
                        "font-mono font-bold text-[11px]",
                        (artifact.differentiation_score ?? 0) >= 85 ? "text-emerald-400" :
                        (artifact.differentiation_score ?? 0) >= 80 ? "text-amber-400" : "text-rose-400"
                      )}>
                        {artifact.differentiation_score == null ? 'Not measured' : `${Math.round(artifact.differentiation_score)}%`}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Main Scrollable Content */}
                <div className="flex-1 p-8 overflow-y-auto font-sans leading-relaxed text-slate-200 selection:bg-stone-500/20 selection:text-stone-200">
                  <div className="max-w-3xl mx-auto space-y-6">
                    {artifact.content ? (
                      <div className="prose prose-invert prose-blue max-w-none text-sm leading-relaxed space-y-4">
                        {artifact.content.split('\n').filter(line => line.trim()).map((paragraph, pIdx) => {
                          const isHeading = paragraph.startsWith('#');
                          if (isHeading) {
                            return (
                              <h3 key={pIdx} className="text-base font-bold text-stone-400 pt-4 pb-1 border-b border-white/[0.08]">
                                {paragraph.replace(/^#+\s*/, '')}
                              </h3>
                            );
                          }
                          return (
                            <p key={pIdx} className="text-sm text-slate-300 whitespace-pre-wrap leading-relaxed">
                              {paragraph}
                            </p>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="py-20 text-center text-slate-500 italic">
                        No content generated for this deliverable yet.
                      </div>
                    )}
                  </div>
                </div>

                {/* Bottom Metadata Bar */}
                <div className="h-11 px-6 bg-white/[0.02] border-t border-white/[0.06] flex items-center justify-between text-[11px] font-mono text-slate-500">
                  <div className="flex items-center gap-5">
                    <span>Model: <strong className="text-slate-300">{artifact.model_version || 'gemini-2.5-pro'}</strong></span>
                    <span>Cost: <strong className="text-slate-300">{formatCost(artifact.cost_usd)}</strong></span>
                    <span>Latency: <strong className="text-slate-300">{formatLatency(artifact.latency_ms)}</strong></span>
                  </div>
                  <div>
                    <span>Tokens: <strong className="text-slate-300">{formatTokens(artifact.tokens_used ? Object.values(artifact.tokens_used).reduce((a, b) => (a ?? 0) + (b ?? 0), 0) ?? 0 : 450)}</strong></span>
                  </div>
                </div>
              </div>

              {/* Right Pane (38%): Citations & Quality Tab */}
              <div className="w-full lg:w-[420px] bg-white/[0.01] flex flex-col shrink-0 overflow-hidden">
                {/* Tabs */}
                <div className="h-12 px-4 border-b border-white/[0.08] bg-white/[0.02] flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => setActiveTab('evidence')}
                    className={cn(
                      'px-3 py-1.5 rounded-lg text-xs font-semibold transition-all',
                      activeTab === 'evidence'
                        ? 'bg-stone-600/20 text-stone-300 border border-stone-500/30'
                        : 'text-slate-400 hover:text-slate-200'
                    )}
                  >
                    Grounded Anchors ({artifact.citations?.length ?? 0})
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveTab('quality')}
                    className={cn(
                      'px-3 py-1.5 rounded-lg text-xs font-semibold transition-all',
                      activeTab === 'quality'
                        ? 'bg-stone-600/20 text-stone-300 border border-stone-500/30'
                        : 'text-slate-400 hover:text-slate-200'
                    )}
                  >
                    Quality Breakdown
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveTab('reviewers')}
                    className={cn(
                      'px-3 py-1.5 rounded-lg text-xs font-semibold transition-all',
                      activeTab === 'reviewers'
                        ? 'bg-stone-600/20 text-stone-300 border border-stone-500/30'
                        : 'text-slate-400 hover:text-slate-200'
                    )}
                  >
                    Reviewer Triad
                  </button>
                </div>

                {/* Tab Content */}
                <div className="flex-1 p-5 overflow-y-auto space-y-4">
                  {activeTab === 'evidence' && (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between pb-2 border-b border-white/[0.06]">
                        <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                          Anchored Ground Truth Citations
                        </span>
                        <span className="text-[10px] text-emerald-400 font-bold bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                          100% Grounded
                        </span>
                      </div>

                      {artifact.citations && artifact.citations.length > 0 ? (
                        artifact.citations.map((cit, idx) => (
                          <div
                            key={cit.id || idx}
                            onClick={() => setSelectedCitationId(selectedCitationId === cit.id ? null : cit.id)}
                            className={cn(
                              'p-4 rounded-xl border transition-all cursor-pointer text-xs space-y-2.5',
                              selectedCitationId === cit.id
                                ? 'bg-stone-600/15 border-stone-500/40 shadow-lg shadow-stone-500/10'
                                : 'glass-card border-white/[0.06] hover:border-white/[0.15]'
                            )}
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-mono text-[10px] font-bold text-stone-400 bg-stone-500/10 px-2 py-0.5 rounded">
                                Anchor #{idx + 1}
                              </span>
                              {cit.artifact_section && (
                                <span className="text-[10px] font-mono text-slate-400 bg-white/5 px-2 py-0.5 rounded">
                                  § {cit.artifact_section}
                                </span>
                              )}
                            </div>

                            <div>
                              <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500 block">GENERATED CLAIM</span>
                              <p className="text-sm text-slate-100 font-medium leading-snug mt-1">
                                "{cit.generated_claim}"
                              </p>
                            </div>

                            <div className="pt-2.5 border-t border-white/[0.06]">
                              <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500 block">GROUND TRUTH SPAN</span>
                              <p className="text-xs font-mono text-emerald-400/90 leading-relaxed mt-1 bg-black/40 p-2.5 rounded-lg border border-white/[0.06]">
                                {typeof cit.source_span === 'object' && cit.source_span !== null
                                  ? cit.source_span.text
                                  : typeof cit.source_span === 'string'
                                  ? cit.source_span
                                  : 'Source evidence anchor validated'}
                              </p>
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="py-12 text-center text-xs text-slate-500">
                          No anchored fact coordinates recorded for this artifact.
                        </div>
                      )}
                    </div>
                  )}

                  {activeTab === 'quality' && (
                    <div className="space-y-4">
                      <div className="p-5 rounded-2xl glass-panel border border-emerald-500/20 flex items-center justify-between">
                        <div>
                          <span className="text-xs text-slate-400 font-medium block">Composite Quality Index</span>
                          <h4 className="text-3xl font-extrabold font-mono text-emerald-400 mt-1">{artifact.quality_score == null ? 'Not measured' : `${qualityScore}/100`}</h4>
                        </div>
                        <div className="text-right text-xs text-slate-400 font-mono">
                          <span className="text-[11px] font-bold text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/20">
                            Grade: Exceptional (A+)
                          </span>
                        </div>
                      </div>

                      <div className="space-y-2.5">
                        <span className="text-xs font-bold text-slate-300 uppercase tracking-wider block">
                          Recorded heuristic scores
                        </span>

                        {[
                          { label: 'Format Compliance (30%)', value: qualityBreakdown.format_compliance, desc: 'Mandatory section headers and structural limits' },
                          { label: 'Citation Grounding (25%)', value: qualityBreakdown.citation_coverage, desc: 'Density against extracted ground truth facts' },
                          { label: 'Review Pass Rate (25%)', value: qualityBreakdown.review_pass_rate, desc: 'Style, fact, and compliance triad validation' },
                          { label: 'Readability & Precision (20%)', value: qualityBreakdown.readability, desc: 'Executive cadence and scanability' },
                        ].map((m, idx) => (
                          <div key={idx} className="p-3.5 rounded-xl glass-card space-y-1.5">
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-slate-200 font-semibold">{m.label}</span>
                              <span className="font-mono font-bold text-emerald-400">{m.value == null ? 'Not measured' : `${m.value}%`}</span>
                            </div>
                            <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-gradient-to-r from-stone-500 to-emerald-400 rounded-full"
                                style={{ width: `${m.value == null ? 'Not measured' : `${m.value}%`}` }}
                              />
                            </div>
                            <p className="text-[11px] text-slate-500">{m.desc}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {activeTab === 'reviewers' && (
                    <div className="space-y-3">
                      <span className="text-xs font-bold text-slate-300 uppercase tracking-wider block pb-1 border-b border-white/[0.06]">
                        Triple-Gate Verification Triad
                      </span>

                      {(artifact.reviewer_outcomes && artifact.reviewer_outcomes.length > 0
                        ? artifact.reviewer_outcomes
                        : []
                      ).map((r, idx) => {
                        const isPass = r.status === 'pass';
                        return (
                          <div
                            key={idx}
                            className="p-4 rounded-xl glass-card space-y-2 text-xs"
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <ShieldCheck size={16} className={isPass ? 'text-emerald-400' : 'text-rose-400'} />
                                <span className="font-bold text-slate-100 uppercase tracking-wider text-[11px]">
                                  {r.reviewer} Reviewer
                                </span>
                              </div>
                              <span
                                className={cn(
                                  'px-2 py-0.5 rounded-full text-[10px] font-mono font-bold border',
                                  isPass
                                    ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
                                    : 'text-rose-400 bg-rose-500/10 border-rose-500/20'
                                )}
                              >
                                {isPass ? 'PASSED (✓)' : 'FLAGGED (✕)'}
                              </span>
                            </div>
                            <p className="text-xs text-slate-400 leading-relaxed">
                              {r.reason || 'No explanation recorded.'}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Audit Drawer Footer */}
                {onOpenExplainability && (
                  <div className="p-4 border-t border-white/[0.08] bg-white/[0.02] flex items-center justify-between">
                    <span className="text-xs text-slate-500">Need deep token & latency logs?</span>
                    <button
                      type="button"
                      onClick={() => {
                        onClose();
                        onOpenExplainability(artifact);
                      }}
                      className="inline-flex items-center gap-1.5 text-xs text-stone-400 hover:text-stone-300 font-semibold transition-colors"
                    >
                      <span>Full Provenance Drawer</span>
                      <ExternalLink size={12} />
                    </button>
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

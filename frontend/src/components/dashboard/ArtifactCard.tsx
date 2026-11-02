'use client';
import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  FileText,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Copy,
  ShieldCheck,
  Sparkles,
  RefreshCw,
  ChevronRight,
  ShieldAlert,
  Layers,
  TrendingUp,
} from 'lucide-react';
import { listItemVariants } from '@/lib/motion';
import { cn } from '@/lib/utils';
import { Artifact } from '@/lib/types';

interface ArtifactCardProps {
  artifact: Artifact;
  onOpenExplainability: (artifact: Artifact) => void;
  onOpenWorkspace?: (artifact: Artifact) => void;
  onRerun?: (_artifactId: string) => void;
}

const OUTPUT_TYPE_INFO: Record<string, {
  label: string;
  purpose: string;
  audience: string;
  icon: React.ElementType;
}> = {
  executive_briefing:  { label: 'Executive Briefing',      purpose: 'Decision Support',        audience: 'CEO / C-Suite',           icon: FileText },
  executive_summary:   { label: 'Executive Briefing',      purpose: 'Decision Support',        audience: 'CEO / C-Suite',           icon: FileText },
  press_release:       { label: 'Press Release',           purpose: 'Media Communication',     audience: 'News Media & Public',     icon: FileText },
  linkedin_post:       { label: 'LinkedIn Post',           purpose: 'Thought Leadership',      audience: 'Professional Network',    icon: Sparkles },
  strategic_memo:      { label: 'Strategic Memo',          purpose: 'Board Advisory',          audience: 'Board of Directors',      icon: ShieldCheck },
  advisory:            { label: 'Strategic Memo',          purpose: 'Board Advisory',          audience: 'Board of Directors',      icon: ShieldCheck },
  research_report:     { label: 'Research Report',         purpose: 'Empirical Analysis',      audience: 'Technical Decision Makers', icon: FileText },
  policy_memo:         { label: 'Policy Memo',             purpose: 'Governance Framework',    audience: 'Governance Committees',   icon: ShieldAlert },
  presentation:        { label: 'Executive Deck',          purpose: 'Slide Architecture',      audience: 'Leadership & Investors',  icon: Layers },
  infographic:         { label: 'Infographic Spec',        purpose: 'Data Visualization',      audience: 'Cross-Functional Teams',  icon: TrendingUp },
  video_package:       { label: 'Video Script',            purpose: 'Audiovisual Production',  audience: 'Video Viewers',           icon: Sparkles },
  newsletter:          { label: 'Newsletter',              purpose: 'Industry Digest',         audience: 'Subscribers',             icon: Sparkles },
  twitter_x:           { label: 'X / Twitter Thread',      purpose: 'Public Distribution',     audience: 'Tech Network & Public',   icon: Sparkles },
};

export function ArtifactCard({
  artifact,
  onOpenExplainability,
  onOpenWorkspace,
  onRerun,
}: ArtifactCardProps) {
  const [copied, setCopied] = useState(false);

  const typeInfo = OUTPUT_TYPE_INFO[artifact.output_type] ?? {
    label:    artifact.output_type.replace(/_/g, ' '),
    purpose:  artifact.purpose || 'Verified Deliverable',
    audience: artifact.target_audience || 'Stakeholders',
    icon:     FileText,
  };
  const Icon = typeInfo.icon;

  const isBudgetExceeded = artifact.review_status === 'budget_exceeded';
  const isFailed         = artifact.review_status === 'fail';
  const isVerified       = artifact.review_status === 'pass' || artifact.review_status === 'regenerated';

  const qualityScore = artifact.quality_score == null ? null : Math.round(artifact.quality_score);
  const insights     = artifact.key_insights?.length
    ? artifact.key_insights.slice(0, 3)
    : [];

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (artifact.content) {
      navigator.clipboard.writeText(artifact.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleOpen = () => {
    if (onOpenWorkspace) onOpenWorkspace(artifact);
    else onOpenExplainability(artifact);
  };

  // Budget exceeded state — clean placeholder
  if (isBudgetExceeded) {
    return (
      <motion.div
        variants={listItemVariants}
        className="rounded-lg border border-dashed border-[#27272A] bg-[#111113] p-6 flex flex-col items-center justify-center text-center gap-3 min-h-[180px]"
      >
        <AlertTriangle size={18} className="text-[#D97706]" />
        <div>
          <h3 className="text-[13px] font-semibold text-text-primary">{typeInfo.label}</h3>
          <p className="text-[12px] text-text-tertiary mt-1 max-w-[240px]">
            Budget ceiling reached before this deliverable was completed.
          </p>
        </div>
        {onRerun && (
          <button
            type="button"
            onClick={() => onRerun(artifact.id)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#17171A] hover:bg-[#27272A] border border-[#27272A] text-[12px] font-medium text-text-secondary hover:text-text-primary transition-colors"
          >
            <RefreshCw size={12} />
            Rerun with fresh budget
          </button>
        )}
      </motion.div>
    );
  }

  return (
    <motion.div
      variants={listItemVariants}
      className={cn(
        'deliverable-card flex flex-col overflow-hidden group',
        isFailed ? 'border-l-2 border-l-[#DC2626]' : ''
      )}
      onClick={handleOpen}
      role="button"
      tabIndex={0}
      onKeyDown={e => e.key === 'Enter' && handleOpen()}
      aria-label={`${typeInfo.label} — ${isVerified ? 'Verified' : isFailed ? 'Review failed' : 'Pending'}`}
    >
      {/* ── Header — type + audience + status ── */}
      <div className="px-5 pt-5 pb-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-md bg-[#17171A] border border-[#27272A] flex items-center justify-center flex-shrink-0 mt-0.5">
              <Icon size={14} className="text-text-secondary" />
            </div>
            <div>
              <h3 className="text-[14px] font-semibold text-text-primary leading-tight">
                {typeInfo.label}
              </h3>
              <p className="text-[12px] text-text-tertiary mt-0.5">{typeInfo.purpose}</p>
            </div>
          </div>

          {/* Verification status */}
          <div className="flex items-center gap-2 flex-shrink-0 pt-0.5">
            {isVerified ? (
              <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[#16A34A]">
                <CheckCircle2 size={11} />
                Verified
              </span>
            ) : isFailed ? (
              <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[#DC2626]">
                <XCircle size={11} />
                Failed
              </span>
            ) : null}

            <button
              type="button"
              onClick={handleCopy}
              title="Copy content"
              className="p-1 rounded text-[#52525B] hover:text-text-secondary transition-colors opacity-0 group-hover:opacity-100"
            >
              {copied ? <CheckCircle2 size={13} className="text-[#16A34A]" /> : <Copy size={13} />}
            </button>
          </div>
        </div>

        {/* Audience */}
        <p className="text-[11px] text-[#52525B] mt-3">
          Audience: <span className="text-text-tertiary">{typeInfo.audience}</span>
        </p>
      </div>

      {/* ── Key insights ── */}
      <div className="px-5 pb-4 flex-1 border-t border-[rgba(255,255,255,0.04)]">
        <div className="pt-4 space-y-2.5">
          {insights.map((insight, idx) => (
            <div key={idx} className="flex items-start gap-2.5">
              <span
                className="w-1 h-1 rounded-full bg-[#3F3F46] flex-shrink-0 mt-[7px]"
                aria-hidden="true"
              />
              <p className="text-[12px] text-text-secondary leading-relaxed line-clamp-2">
                {insight}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Footer — citations + score + open ── */}
      <div className="px-5 py-3 border-t border-[rgba(255,255,255,0.04)] flex items-center justify-between">
        <div className="flex items-center gap-4 text-[12px] text-text-tertiary">
          <span>{artifact.citations?.length ?? 0} citations</span>
          <span className="text-[#3F3F46]">·</span>
          <span>Score {qualityScore ?? 'not measured'}</span>
        </div>

        <button
          type="button"
          onClick={e => { e.stopPropagation(); handleOpen(); }}
          className="inline-flex items-center gap-1 text-[12px] font-medium text-[#2563EB] hover:text-[#3B82F6] transition-colors"
        >
          Open
          <ChevronRight size={13} className="group-hover:translate-x-0.5 transition-transform" />
        </button>
      </div>
    </motion.div>
  );
}

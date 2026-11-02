'use client';
import { AlertCircle, WifiOff, Clock, Zap, BarChart2, Upload, RefreshCw } from 'lucide-react';
import Link from 'next/link';
import { ApiErrorKind } from '@/lib/types';

// ── Empty States ──────────────────────────────────────────────────────────────

interface EmptyStateProps {
  icon?: React.ElementType;
  title: string;
  description: string;
  action?: { label: string; href?: string; onClick?: () => void };
}

export function EmptyState({ icon: Icon = Upload, title, description, action }: EmptyStateProps) {
  return (
    <div
      className="flex flex-col items-center justify-center min-h-[280px] text-center px-8"
      role="status"
      aria-live="polite"
    >
      {Icon && (
        <Icon size={20} className="text-[#52525B] mb-4" aria-hidden="true" />
      )}
      <h3 className="text-[14px] font-semibold text-text-primary mb-2">{title}</h3>
      <p className="text-[13px] text-text-tertiary max-w-xs leading-relaxed mb-6">{description}</p>
      {action && (
        action.href ? (
          <Link
            href={action.href}
            className="text-[13px] font-medium text-[#2563EB] hover:text-[#3B82F6] transition-colors"
          >
            {action.label} →
          </Link>
        ) : (
          <button
            onClick={action.onClick}
            className="text-[13px] font-medium text-[#2563EB] hover:text-[#3B82F6] transition-colors"
          >
            {action.label} →
          </button>
        )
      )}
    </div>
  );
}

export const EMPTY_STATES = {
  sources: (
    <EmptyState
      icon={Upload}
      title="No documents yet"
      description="Upload a source document to begin. PDF, DOCX, TXT, or plain text — classification is automatic."
      action={{ label: 'Upload a document', href: '/dashboard/sources' }}
    />
  ),
  generations: (
    <EmptyState
      icon={Zap}
      title="No documents analyzed"
      description="Upload a source document to generate verified deliverables. Each run produces fact-checked, audience-specific outputs."
      action={{ label: 'Go to Sources', href: '/dashboard/sources' }}
    />
  ),
  history: (
    <EmptyState
      icon={Clock}
      title="No audit records yet"
      description="Completed analysis runs will appear here. Every action is logged and filterable by status, date, and classification."
    />
  ),
  evaluation: (
    <EmptyState
      icon={BarChart2}
      title="No evaluation data yet"
      description="Run at least one document analysis to see fact accuracy, style adherence, and performance metrics."
    />
  ),
};

// ── Error States ──────────────────────────────────────────────────────────────

interface ErrorStateProps {
  kind: ApiErrorKind;
  message?: string;
  onRetry?: () => void;
}

const ERROR_CONFIGS: Record<ApiErrorKind, { icon: React.ElementType; title: string; description: string }> = {
  backend_unavailable: {
    icon: WifiOff,
    title: 'Service unavailable',
    description: 'Cannot reach the TraceForm API. Check that the backend is running at localhost:8000.',
  },
  api_timeout: {
    icon: Clock,
    title: 'Request timed out',
    description: 'The API did not respond within 15 seconds. This may be a temporary load spike.',
  },
  generation_failure: {
    icon: Zap,
    title: 'Analysis failed',
    description: 'The analysis pipeline encountered an error. Review the details and retry.',
  },
  reviewer_failure: {
    icon: AlertCircle,
    title: 'Review incomplete',
    description: 'One or more review stages could not complete. The deliverable may be in a partial state.',
  },
  metrics_unavailable: {
    icon: BarChart2,
    title: 'Metrics unavailable',
    description: 'Evaluation metrics could not be loaded. The metrics endpoint may be temporarily unavailable.',
  },
  unknown: {
    icon: AlertCircle,
    title: 'Unexpected error',
    description: 'An unknown error occurred. Please try again.',
  },
};

export function ErrorState({ kind, message, onRetry }: ErrorStateProps) {
  const config = ERROR_CONFIGS[kind] ?? ERROR_CONFIGS.unknown;
  const Icon   = config.icon;

  return (
    <div
      className="flex flex-col items-center justify-center min-h-[240px] text-center px-8"
      role="alert"
      aria-live="assertive"
    >
      <div className="w-10 h-10 rounded-full border border-[rgba(220,38,38,0.2)] bg-[rgba(220,38,38,0.06)] flex items-center justify-center text-[#DC2626] mb-4">
        <Icon size={18} aria-hidden="true" />
      </div>
      <h3 className="text-[14px] font-semibold text-text-primary mb-2">{config.title}</h3>
      <p className="text-[13px] text-text-tertiary max-w-xs leading-relaxed">{config.description}</p>
      {message && (
        <p className="text-[11px] text-text-tertiary mt-2 max-w-xs opacity-60">{message}</p>
      )}
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-6 inline-flex items-center gap-2 text-[13px] font-medium text-[#2563EB] hover:text-[#3B82F6] transition-colors"
          aria-label="Retry request"
        >
          <RefreshCw size={13} aria-hidden="true" />
          Retry
        </button>
      )}
    </div>
  );
}

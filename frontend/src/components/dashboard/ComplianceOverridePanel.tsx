'use client';
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, ShieldAlert } from 'lucide-react';
import { Artifact } from '@/lib/types';
import { sensitivityMeta, cn } from '@/lib/utils';
import * as api from '@/lib/api';

interface ComplianceOverridePanelProps {
  artifact: Artifact;
  open: boolean;
  onClose: () => void;
  onSuccess?: (updated: Artifact) => void;
}


/**
 * ComplianceOverridePanel — deliberately heavy interaction.
 *
 * Per spec §5.6:
 * - Requires a TYPED reason (no pre-filled text, no dark patterns)
 * - Shows exactly what will be logged and to whom it's attributed
 * - Submit is locked until reason is non-empty
 * - Clear confirmation UI before the action is irreversible
 */
export function ComplianceOverridePanel({ artifact, open, onClose, onSuccess }: ComplianceOverridePanelProps) {
  const newSensitivity = artifact.sensitivity_provenance.operator;
  const [reason, setReason]                 = useState('');
  const [submitting, setSubmitting]         = useState(false);
  const [error, setError]                   = useState('');

  const canSubmit = reason.trim().length >= 10 && !submitting;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;

    setSubmitting(true);
    setError('');
    try {
      const updated = await api.submitComplianceOverride({
        artifact_id: artifact.id,
        override_reason: reason.trim(),
        sensitivity: newSensitivity,
      });
      onSuccess?.(updated);
      onClose();
    } catch {
      setError('Override submission failed. Please try again.');
      setSubmitting(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 bg-canvas/70 backdrop-blur-xs z-60"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            aria-hidden="true"
          />

          {/* Panel */}
          <motion.div
            className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-md z-60 px-4"
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.96 }}
            transition={{ ease: [0.16, 1, 0.3, 1], duration: 0.25 }}
            role="dialog"
            aria-modal="true"
            aria-labelledby="override-dialog-title"
          >
            <form
              onSubmit={handleSubmit}
              className="rounded-lg border border-status-fail/30 bg-surface shadow-2xl overflow-hidden"
            >
              {/* Warning header */}
              <div className="flex items-center gap-3 px-5 py-4 bg-status-fail/8 border-b border-status-fail/20">
                <ShieldAlert size={18} className="text-status-fail flex-shrink-0" aria-hidden="true" />
                <div>
                  <h2 id="override-dialog-title" className="text-sm font-semibold text-text-primary">
                    Compliance Override
                  </h2>
                  <p className="mono text-[10px] text-text-tertiary">
                    This action is logged, attributed, and permanent.
                  </p>
                </div>
              </div>

              <div className="p-5 space-y-5">
                {/* What will be logged */}
                <div className="rounded border border-surface-border bg-canvas p-4 space-y-2">
                  <p className="mono text-[10px] tracking-widest text-text-tertiary uppercase mb-2">What will be logged</p>
                  <div className="flex justify-between">
                    <span className="mono text-[11px] text-text-tertiary">Artifact</span>
                    <span className="mono text-[11px] text-text-primary capitalize">{artifact.output_type.replace(/_/g, ' ')}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="mono text-[11px] text-text-tertiary">Current sensitivity</span>
                    <span className={cn('mono text-[11px]', sensitivityMeta(artifact.sensitivity_provenance.operator).className)}>
                      {artifact.sensitivity_provenance.operator}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="mono text-[11px] text-text-tertiary">Attributed to</span>
                    <span className="mono text-[11px] text-text-primary">Current operator</span>
                  </div>
                </div>

                <p className="muted">This override records your justification. It does not change the source document’s sensitivity classification.</p>

                {/* Typed reason — no pre-filled text, no dark patterns */}
                <div>
                  <label
                    htmlFor="override-reason"
                    className="mono text-[10px] tracking-widest text-text-tertiary uppercase block mb-2"
                  >
                    Reason for Override
                    <span className="text-status-fail ml-1" aria-label="required">*</span>
                  </label>
                  <textarea
                    id="override-reason"
                    value={reason}
                    onChange={e => setReason(e.target.value)}
                    placeholder="Type your reason here (minimum 10 characters)..."
                    rows={3}
                    className="w-full bg-canvas border border-surface-border rounded px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary font-mono focus:outline-none focus:border-accent transition-colors resize-none"
                    aria-required="true"
                    aria-describedby="override-reason-hint"
                  />
                  <p id="override-reason-hint" className="mono text-[10px] text-text-tertiary mt-1">
                    {reason.trim().length}/10 minimum · this text is stored verbatim in the audit log
                  </p>
                </div>

                {/* Warning */}
                <div className="flex items-start gap-2 p-3 rounded border border-amber-500/20 bg-amber-500/5">
                  <AlertTriangle size={13} className="text-amber-500 flex-shrink-0 mt-0.5" aria-hidden="true" />
                  <p className="mono text-[10px] text-amber-500/80">
                    This override cannot be undone. The original sensitivity selection remains visible
                    in the artifact's provenance history.
                  </p>
                </div>

                {error && (
                  <p className="mono text-[11px] text-status-fail" role="alert">{error}</p>
                )}

                {/* Actions */}
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={onClose}
                    className="flex-1 py-2.5 rounded border border-surface-border text-sm mono text-text-secondary hover:border-surface-border-sub hover:text-text-primary transition-colors duration-150"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={!canSubmit}
                    className="flex-1 py-2.5 rounded bg-status-fail text-white text-sm font-semibold hover:bg-status-fail/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors duration-150"
                    aria-label="Submit compliance override"
                    id="override-submit-btn"
                  >
                    {submitting ? 'Submitting...' : 'Submit Override'}
                  </button>
                </div>
              </div>
            </form>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

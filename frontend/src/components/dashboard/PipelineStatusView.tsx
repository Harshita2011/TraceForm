'use client';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { PipelineStatus, GenerationStatus } from '@/lib/types';
import { Check, Loader2, AlertCircle } from 'lucide-react';

interface PipelineStatusViewProps {
  status: PipelineStatus | null;
  generationStatus?: GenerationStatus | string;
  loading?: boolean;
}

const STAGES = [
  { id: 'ingest',   label: 'Source ready' },
  { id: 'extract',  label: 'Read source' },
  { id: 'generate', label: 'Write outputs' },
  { id: 'review',   label: 'Check content' },
  { id: 'deliver',  label: 'Save outputs' },
];

type NodeStatus = 'done' | 'running' | 'queued' | 'failed';

export function PipelineStatusView({ status, generationStatus, loading }: PipelineStatusViewProps) {
  const norm = (generationStatus || '').toLowerCase();
  const isComplete = norm === 'complete' || norm === 'completed';
  const isQueued   = norm === 'queued' || norm === 'pending';
  const stages     = status?.stages || [];

  const getStatus = (id: string): NodeStatus => {
    const found = stages.find(s => s.name === id);
    if (found?.status) return norm === 'cancelled' && found.status === 'running' ? 'queued' : found.status as NodeStatus;
    if (isComplete) return 'done';
    if (isQueued)   return id === 'ingest' ? 'done' : 'queued';

    if (id === 'ingest') return 'done';
    return 'queued';
  };

  const nodeStatuses = STAGES.map(s => getStatus(s.id));

  return (
    <div className="pipeline-stages flex items-center w-full py-2" role="list" aria-label={loading ? 'Loading progress' : 'Generation progress'}>
      {STAGES.map((stage, idx) => {
        const nodeStatus = nodeStatuses[idx];
        const isDone     = nodeStatus === 'done';
        const isRunning  = nodeStatus === 'running';
        const isFail     = nodeStatus === 'failed';

        return (
          <div key={stage.id} className="flex items-center flex-1 last:flex-none" role="listitem">
            {/* Stage Icon Node + Label */}
            <div className="flex flex-col items-center gap-2">
              <div className="relative flex items-center justify-center">
                {isRunning && (
                  <motion.div
                    className="absolute -inset-1.5 rounded-full border-2 border-stone-500/50 bg-stone-500/10"
                    animate={{ scale: [1, 1.4, 1], opacity: [0.8, 0.2, 0.8] }}
                    transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
                  />
                )}
                <div
                  className={cn(
                    'w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-semibold transition-all duration-300 shadow-md',
                    isDone    ? 'bg-emerald-500 text-white shadow-emerald-500/20' :
                    isRunning ? 'bg-stone-600 text-white shadow-stone-500/30' :
                    isFail    ? 'bg-rose-500 text-white shadow-rose-500/20' :
                                'bg-slate-800/80 text-slate-400 border border-white/10'
                  )}
                  aria-label={`${stage.label}: ${nodeStatus}`}
                >
                  {isDone ? (
                    <Check size={13} strokeWidth={3} />
                  ) : isRunning ? (
                    <Loader2 size={13} className="animate-spin" />
                  ) : isFail ? (
                    <AlertCircle size={13} />
                  ) : (
                    <span className="text-[10px]">{idx + 1}</span>
                  )}
                </div>
              </div>

              {/* Stage Name */}
              <span
                className={cn(
                  'text-[11px] font-semibold tracking-tight whitespace-nowrap transition-colors',
                  isDone    ? 'text-slate-300' :
                  isRunning ? 'text-stone-400' :
                  isFail    ? 'text-rose-400' :
                              'text-slate-500'
                )}
              >
                {stage.label}
              </span>
            </div>

            {/* Connector Line */}
            {idx < STAGES.length - 1 && (
              <div className="pipeline-connector flex-1 mx-3 mb-6">
                <div className="h-[2px] w-full bg-slate-800/80 rounded-full relative overflow-hidden">
                  {isDone && (
                    <motion.div
                      className="absolute inset-0 bg-gradient-to-r from-emerald-500 to-emerald-400"
                      initial={{ scaleX: 0, originX: 0 }}
                      animate={{ scaleX: 1 }}
                      transition={{ duration: 0.35, ease: 'easeOut' }}
                    />
                  )}
                  {isRunning && (
                    <motion.div
                      className="absolute inset-0 bg-gradient-to-r from-emerald-500 via-blue-500 to-slate-800"
                      initial={{ scaleX: 0, originX: 0 }}
                      animate={{ scaleX: 1 }}
                      transition={{ duration: 0.35, ease: 'easeOut' }}
                    />
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

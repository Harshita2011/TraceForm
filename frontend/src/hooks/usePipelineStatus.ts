'use client';
import { useState, useEffect, useCallback, useRef } from 'react';
import * as api from '@/lib/api';
import { PipelineStatus, ApiError } from '@/lib/types';

interface UsePipelineStatusState {
  status: PipelineStatus | null;
  loading: boolean;
  error: ApiError | null;
}

/**
 * usePipelineStatus — polls pipeline status for a running generation.
 *
 * Real-time readiness:
 *   To upgrade to SSE, replace the polling interval below with an EventSource:
 *     const es = new EventSource(`${BASE_URL}/api/v1/generations/${generationId}/status/stream`);
 *     es.onmessage = (e) => setStatus(JSON.parse(e.data));
 *   The hook's return type and consumer components need no changes.
 *
 * @param generationId  ID of the generation to track
 * @param pollMs        Polling interval in ms (default 2000). Pass 0 to disable.
 * @param active        Set false to suspend polling (e.g. when generation is complete)
 */
export function usePipelineStatus(
  generationId: string,
  pollMs = 2000,
  active = true,
): UsePipelineStatusState {
  const [status, setStatus]   = useState<PipelineStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<ApiError | null>(null);
  const intervalRef           = useRef<ReturnType<typeof setInterval> | null>(null);

  const poll = useCallback(async () => {
    if (!generationId) return;
    try {
      const data = await api.getPipelineStatus(generationId);
      setStatus(data);
      setError(null);
      setLoading(false);
    } catch (e) {
      setError(e as ApiError);
      setLoading(false);
    }
  }, [generationId]);

  useEffect(() => {
    if (!generationId) return;
    poll(); // immediate first fetch
    if (active && pollMs > 0) {
      intervalRef.current = setInterval(poll, pollMs);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [generationId, active, pollMs, poll]);

  return { status, loading, error };
}

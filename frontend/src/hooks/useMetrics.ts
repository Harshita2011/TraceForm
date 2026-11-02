'use client';
import { useState, useEffect, useCallback } from 'react';
import * as api from '@/lib/api';
import { AggregateMetrics, ApiError } from '@/lib/types';

interface UseMetricsState {
  metrics: AggregateMetrics | null;
  loading: boolean;
  error: ApiError | null;
  refetch: () => void;
}

export function useMetrics(): UseMetricsState {
  const [metrics, setMetrics] = useState<AggregateMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<ApiError | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getMetrics();
      setMetrics(data);
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  return { metrics, loading, error, refetch: fetch };
}

'use client';
import { useState, useEffect, useCallback } from 'react';
import * as api from '@/lib/api';
import { Source, ApiError } from '@/lib/types';

interface UseSourcesState {
  sources: Source[];
  loading: boolean;
  error: ApiError | null;
  refetch: () => void;
}

export function useSources(): UseSourcesState {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<ApiError | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getSources();
      setSources(data);
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  return { sources, loading, error, refetch: fetch };
}

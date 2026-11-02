'use client';
import { useState, useEffect, useCallback } from 'react';
import * as api from '@/lib/api';
import { HistoryEntry, ApiError } from '@/lib/types';

interface UseHistoryState {
  history: HistoryEntry[];
  loading: boolean;
  error: ApiError | null;
  refetch: (params?: { status?: string; output_type?: string; sensitivity?: string }) => void;
}

export function useHistory(): UseHistoryState {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<ApiError | null>(null);

  const fetch = useCallback(async (params?: { status?: string; output_type?: string; sensitivity?: string }) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getHistory(params);
      setHistory(data);
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  return { history, loading, error, refetch: fetch };
}

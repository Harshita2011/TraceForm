'use client';
import { useState, useEffect, useCallback, useRef } from 'react';
import * as api from '@/lib/api';
import { Generation, ApiError } from '@/lib/types';

interface UseGenerationsState {
  generations: Generation[];
  loading: boolean;
  error: ApiError | null;
  refetch: () => void;
}

export function useGenerations(): UseGenerationsState {
  const [generations, setGenerations] = useState<Generation[]>([]);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState<ApiError | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const fetch = useCallback(async (isPolling = false) => {
    if (!isPolling) setLoading(true);
    setError(null);
    try {
      const data = await api.getGenerations();
      setGenerations(data);

      const hasActive = data.some(g => g.status === 'running' || g.status === 'queued');
      if (hasActive) {
        if (timerRef.current) clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => {
          fetch(true);
        }, 2000);
      }
    } catch (e) {
      setError(e as ApiError);
    } finally {
      if (!isPolling) setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [fetch]);

  return { generations, loading, error, refetch: () => fetch(false) };
}

interface UseGenerationState {
  generation: Generation | null;
  loading: boolean;
  error: ApiError | null;
  refetch: () => void;
}

export function useGeneration(id: string): UseGenerationState {
  const [generation, setGeneration] = useState<Generation | null>(null);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState<ApiError | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const fetch = useCallback(async (isPolling = false) => {
    if (!id) return;
    if (!isPolling) setLoading(true);
    setError(null);
    try {
      const data = await api.getGeneration(id);
      setGeneration(data);

      // Auto poll every 2s if queued or running
      if (data.status === 'running' || data.status === 'queued') {
        if (timerRef.current) clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => {
          fetch(true);
        }, 2000);
      }
    } catch (e) {
      setError(e as ApiError);
    } finally {
      if (!isPolling) setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetch();
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [fetch]);

  return { generation, loading, error, refetch: () => fetch(false) };
}

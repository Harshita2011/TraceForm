'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { getOutputWorkspace, saveOutputDraft, saveOutputVersion } from '@/lib/api';
import { OutputDraft, OutputWorkspaceState } from '@/lib/types';
import { clearAcknowledgedRecovery, DeviceCopy, readDeviceCopies, recoveryPrefix } from '@/lib/draft-recovery';

export function useOutputDraft(artifactId: string) {
  const [workspace, setWorkspace] = useState<OutputWorkspaceState | null>(null);
  const [content, setContent] = useState('');
  const [status, setStatus] = useState('Loading saved work…');
  const [error, setError] = useState('');
  const [conflict, setConflict] = useState(false);
  const [deviceCopies, setDeviceCopies] = useState<DeviceCopy[]>([]);
  const state = useRef<{server: OutputDraft | null; desired: string; key: string; pending: {content: string; expected_revision: number; base_hash: string; request_id: string} | null; blocked: boolean}>({server:null, desired:'', key:'', pending:null, blocked:false});
  const flight = useRef<Promise<OutputDraft> | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const accept = useCallback((draft: OutputDraft) => {
    state.current.server = draft; state.current.desired = draft.content; state.current.pending = null; state.current.blocked = false;
    setContent(draft.content); setWorkspace(value => value ? {...value, draft} : value); setError(''); setConflict(false); setStatus('Saved to server');
  }, []);

  const load = useCallback(async () => {
    try {
      const value = await getOutputWorkspace(artifactId);
      const prefix = recoveryPrefix(artifactId, value.owner) + ':';
      if (!state.current.key.startsWith(prefix)) state.current.key = prefix + crypto.randomUUID();
      accept(value.draft); setWorkspace(value);
      try {
        const result = readDeviceCopies(localStorage, artifactId, value.owner, value.draft.content);
        setDeviceCopies(result.copies);
        if (result.damaged) setError('One browser copy is damaged. Other recovery copies and server drafts remain available.');
      } catch { setError('Browser recovery storage could not be read. Server drafts remain available.'); }
      return true;
    } catch (e) { setError((e as Error).message || 'Saved work could not be loaded.'); setStatus('Load failed'); return false; }
  }, [artifactId, accept]);

  useEffect(() => { void load(); return () => { if (timer.current) clearTimeout(timer.current); }; }, [load]);

  const flush = useCallback(async (): Promise<OutputDraft> => {
    if (timer.current) clearTimeout(timer.current);
    if (flight.current) return flight.current;
    if (!state.current.server) throw new Error('Wait for saved work to load.');
    if (state.current.blocked) throw new Error('Autosave is paused. Retry or preserve your recovery copy.');
    const work = async () => {
      while (state.current.pending || state.current.desired !== state.current.server!.content) {
        const current = state.current;
        const request = current.pending || {content:current.desired, expected_revision:current.server!.revision,
          base_hash:current.server!.base_hash, request_id:crypto.randomUUID()};
        current.pending = request; setStatus('Saving…');
        try {
          const saved = await saveOutputDraft(artifactId, request);
          current.server = saved; current.pending = null;
          setWorkspace(value => value ? {...value, draft:saved} : value);
          if (current.desired === saved.content) {
            try { clearAcknowledgedRecovery(localStorage, current.key, saved.content); } catch { /* Saved server copy is authoritative. */ }
          }
        } catch (e) {
          current.blocked = true; setConflict((e as {status?: number}).status === 409);
          setStatus('Autosave paused'); setError((e as Error).message || 'Save failed. Your text is kept here.'); throw e;
        }
      }
      setStatus('Saved to server'); setError(''); setConflict(false);
      return state.current.server!;
    };
    flight.current = work().finally(() => { flight.current = null; });
    return flight.current;
  }, [artifactId]);

  const change = useCallback((value: string) => {
    if (!state.current.server) return;
    state.current.desired = value; setContent(value); setStatus('Unsaved changes');
    try { localStorage.setItem(state.current.key, JSON.stringify({content:value, savedAt:new Date().toISOString()})); }
    catch { setError('Browser recovery storage is full or unavailable. Keep this page open until the server save succeeds.'); }
    if (timer.current) clearTimeout(timer.current);
    if (!state.current.blocked) timer.current = setTimeout(() => { void flush().catch(() => {}); }, 850);
  }, [flush]);

  useEffect(() => {
    const guard = (event: BeforeUnloadEvent) => {
      if (state.current.server && (state.current.pending || state.current.desired !== state.current.server.content)) { event.preventDefault(); event.returnValue = ''; }
    };
    window.addEventListener('beforeunload', guard); return () => window.removeEventListener('beforeunload', guard);
  }, []);

  const retry = async () => { state.current.blocked = false; await flush(); };
  const preserveAndReload = async () => {
    await saveOutputVersion(artifactId, {source:'recovery', content:state.current.desired, label:'Recovered conflicting draft', request_id:crypto.randomUUID()});
    if (!await load()) throw new Error('Your conflicting copy was saved as a version. Reload the latest draft when the API is available.');
  };
  return {workspace, content, status, error, conflict, deviceCopies, change, flush, retry, load, accept, preserveAndReload};
}

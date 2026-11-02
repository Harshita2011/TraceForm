'use client';
import { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, KeyRound, Loader2, RefreshCw, Save, Wifi } from 'lucide-react';
import { getProviderSettings, getProviderModels, saveProviderSettings, testProviderSettings } from '@/lib/api';
import { ProviderSettings, ProviderUpdate } from '@/lib/types';

export default function SettingsPage() {
  const [saved, setSaved] = useState<ProviderSettings | null>(null);
  const [form, setForm] = useState<ProviderUpdate | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [models, setModels] = useState<{ id: string; name: string }[]>([]);
  const [connection, setConnection] = useState<boolean | null>(null);
  const fill = (value: ProviderSettings) => {
    setSaved(value); setModels([]); setConnection(null);
    setForm({ expected_revision: value.revision, provider: value.provider, model: value.model,
      api_key: '', clear_key: false, input_per_million: value.pricing.input, output_per_million: value.pricing.output });
  };
  const load = useCallback(async () => {
    setLoading(true); setError(''); setNotice('');
    try { fill(await getProviderSettings()); }
    catch (e) { setError((e as Error).message || 'Could not load settings.'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  const change = (patch: Partial<ProviderUpdate>) => { setForm(f => f && { ...f, ...patch }); setConnection(null); setNotice(''); };
  const act = async (action: 'test' | 'save' | 'models') => {
    if (!form) return;
    setBusy(action); setError(''); setNotice('');
    try {
      if (action === 'test') {
        const result = await testProviderSettings(form); setConnection(result.available); setNotice(result.message);
      } else if (action === 'models') {
        const result = await getProviderModels({ ...form, model: form.model || 'model-discovery' }); setModels(result.models);
        setNotice(result.models.length ? `${result.models.length} models loaded. Choose one or enter its ID.` : 'No generation models returned. You can enter a model ID.');
      } else {
        const result = await saveProviderSettings(form);
        fill({ ...result, can_edit: saved?.can_edit, worker_online: saved?.worker_online });
        setConnection(result.key_configured ? true : null);
        setNotice(`Settings saved. Revision ${result.revision} applies to new runs.`);
      }
    } catch (e) { setError((e as Error).message || 'Request failed. Your changes are kept.'); }
    finally { setBusy(''); }
  };
  return <div className="max-w-3xl settings-page">
    <div className="workspace-page-heading"><div><p className="workspace-eyebrow">Workspace preferences</p><h1>Settings</h1><p>Connect your AI provider and keep generation ready to run.</p></div></div>
    {loading ? <div className="flow-panel loading-panel" role="status"><Loader2 className="animate-spin" size={22} />Loading configuration…</div> : <>
      {error && <div role="alert" className="flow-error">{error}<button type="button" className="quiet-link mt-3" disabled={!!busy} onClick={load}>Reload saved settings</button></div>}
      {form && saved && <form className="flow-panel" onSubmit={e => { e.preventDefault(); void act('save'); }}>
        <div className="settings-section-heading"><div><h2>AI connection</h2><p className="muted mt-2">{saved.applies_to}</p></div><span className={`status-pill ${connection === false || !saved.key_configured ? 'attention' : connection === true ? 'ready' : ''}`}>{connection === null ? saved.key_configured ? 'Key saved' : 'Key needed' : connection ? 'Connected' : 'Unavailable'}</span></div>
        {!saved.can_edit && <p className="flow-error">Only an administrator can edit this connection. Ask your workspace administrator to update these settings.</p>}
        <fieldset disabled={!!busy || !saved.can_edit} className="settings-fields">
          <div className="settings-grid"><label>Provider<select className="flow-input" value={form.provider} onChange={e => { change({ provider: e.target.value as ProviderUpdate['provider'], model: '', api_key: '', clear_key: false }); setModels([]); }}><option value="gemini">Google Gemini</option><option value="anthropic">Anthropic</option></select></label>
            <label>Model ID<input className="flow-input" required maxLength={150} pattern="[A-Za-z0-9._:/-]+" list="provider-models" value={form.model} placeholder="Enter a model ID" onChange={e => change({ model: e.target.value })} /><datalist id="provider-models">{models.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</datalist></label></div>
          <button type="button" className="quiet-link" onClick={() => act('models')}>{busy === 'models' ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}Load available models</button>
          <label>Provider API key<input className="flow-input" type="password" autoComplete="new-password" spellCheck={false} value={form.api_key || ''} disabled={form.clear_key} placeholder={saved.key_configured && saved.provider === form.provider ? 'Saved securely · leave blank to keep' : 'Enter your provider API key'} onChange={e => change({ api_key: e.target.value })} /></label>
          <p className="muted settings-hint"><KeyRound size={14} />Encrypted on the server. Saved keys are never returned to this browser.</p>
          {saved.key_configured && saved.provider === form.provider && <label className="settings-check"><input type="checkbox" checked={form.clear_key} onChange={e => change({ clear_key: e.target.checked, api_key: '' })} />Remove saved key for new runs</label>}
          <details className="settings-pricing"><summary>Budget estimates</summary><p className="muted mt-3">Enter USD per million tokens from your provider agreement. These rates estimate cost; your provider invoice is authoritative. New runs save this pricing revision.</p>
            <div className="settings-grid mt-4"><label>Input · USD / 1M tokens<input className="flow-input" type="number" min="0" max="10000" step="any" required value={form.input_per_million} onChange={e => change({ input_per_million: Number(e.target.value) })} /></label><label>Output · USD / 1M tokens<input className="flow-input" type="number" min="0" max="10000" step="any" required value={form.output_per_million} onChange={e => change({ output_per_million: Number(e.target.value) })} /></label></div>
          </details>
          <div className="settings-actions"><button type="button" className="flow-button secondary" disabled={!form.model || form.clear_key} onClick={() => act('test')}>{busy === 'test' ? <Loader2 size={15} className="animate-spin" /> : <Wifi size={15} />}Test connection</button><button type="submit" className="flow-button">{busy === 'save' ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}Save settings</button></div>
        </fieldset>
        <p className="muted mt-3">Testing and saving a key make a small provider request that may be billed.</p>
        {notice && <div className="settings-notice" role="status"><CheckCircle2 size={16} /><p>{notice}</p></div>}
      </form>}
      {!form && <button className="flow-button secondary" onClick={load}>Try again</button>}
      <section className="flow-panel mt-6"><div className="settings-section-heading"><h2>Generation worker</h2><span className={`status-pill ${saved?.worker_online ? 'ready' : 'attention'}`}>{saved?.worker_online ? 'Online' : 'Not connected'}</span></div><p className="muted mt-3">{saved?.worker_online ? 'The worker processes saved jobs independently. You can close this page while a run finishes.' : 'Queued work is saved. Start the generation worker to process it, then refresh this status.'}</p><button className="quiet-link mt-4" disabled={!!busy} onClick={load}><RefreshCw size={14} />Refresh status</button></section>
      <section className="flow-panel mt-6"><h2>Draft storage</h2><p className="muted mt-3">Original outputs are saved on the server. Manual edits and saved draft versions currently stay in this browser on this device. Download drafts you need elsewhere. Shared drafts and server autosave are planned for Phase 5.</p></section>
    </>}
  </div>;
}

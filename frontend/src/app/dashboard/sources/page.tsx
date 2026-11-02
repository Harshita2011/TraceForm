'use client';
import {UPLOAD_MAX_BYTES,UPLOAD_MAX_MB} from '@/lib/deployment';
import { Suspense, useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, ArrowRight, Check, CheckCircle2, FileText, Loader2, UploadCloud, X, Wifi } from 'lucide-react';
import { useSourceLibrary } from '@/hooks/useSourceLibrary';
import { PresetPicker } from '@/components/dashboard/PresetPicker';
import { MultiSourcePicker } from '@/components/dashboard/MultiSourcePicker';
import * as api from '@/lib/api';
import { OutputType, Sensitivity, Source, FormatContract, CreationPreset, MultiSourceSelection } from '@/lib/types';
import { OUTPUT_FORMATS, documentName, outputLabel } from '@/lib/output-formats';
import { cn, formatRelative } from '@/lib/utils';

function CreatePage() {
  const query = useSearchParams();
  const router = useRouter();

  const submission = useRef({ payload: '', key: '' });
  const input = useRef<HTMLInputElement>(null);
  const stepHeading = useRef<HTMLHeadingElement>(null);
  const [step, setStep] = useState(0);
  const [multiMode, setMultiMode] = useState(() => query.get('mode') === 'multi' || !!query.get('collection'));
  const [multiSelection, setMultiSelection] = useState<MultiSourceSelection | null>(null);
  const [multiBusy, setMultiBusy] = useState(false);
  const [moreFormats, setMoreFormats] = useState(false);
  useEffect(() => { stepHeading.current?.focus(); }, [step]);
  const goToStep = (next: number) => { setStep(next); setError(''); window.scrollTo(0, 0); };
  const [file, setFile] = useState<File | null>(null);
  const [sourceId, setSourceId] = useState('');
  const [uploadedId, setUploadedId] = useState('');
  const [search, setSearch] = useState('');
  const [offset, setOffset] = useState(0);
  const { data, loading, error: sourceError, refetch } = useSourceLibrary(search, offset);
  const sources = data.items;
  const [sourceInfo, setSourceInfo] = useState<Source | null>(null);
  const [contracts, setContracts] = useState<FormatContract[]>([]);
  const [brandName, setBrandName] = useState('');
  const [sections, setSections] = useState('');
  const [truncate, setTruncate] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [types, setTypes] = useState<OutputType[]>(['executive_summary']);
  const [sensitivity, setSensitivity] = useState<Sensitivity>('internal');
  const [audience, setAudience] = useState('general');
  const [tone, setTone] = useState('professional');
  const [detail, setDetail] = useState('medium');
  const [objective, setObjective] = useState('');
  const [style, setStyle] = useState('');
  const [language, setLanguage] = useState('en');
  const [budget, setBudget] = useState('0.50');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [health, setHealth] = useState<{ available: boolean; message: string } | null>(null);
  const [checking, setChecking] = useState(false);
  useEffect(() => { api.getFormatContracts().then(setContracts).catch(() => setError('Format requirements could not load. Refresh this page before starting.')); }, []);
  const linkedSource = query.get('source');
  useEffect(() => { if (!linkedSource) return; let active = true;
    api.getSourceDetail(linkedSource).then(value => { if (active) { if (value.status !== 'ready') { setError('Choose a ready source from the library.'); return; } setSourceId(value.id); setSourceInfo(value); setSensitivity(value.sensitivity); } }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [linkedSource]);
  const selectedSource = sourceInfo || sources.find(s => s.id === sourceId);
  const hasSource = multiMode ? !!multiSelection : !!(file || selectedSource);
  const name = multiMode ? multiSelection?.documents.map(d => d.filename).join(' + ') || 'Select and analyze documents' : file?.name || documentName(selectedSource?.filename);
  const effectiveSensitivity = multiMode && multiSelection ? [...multiSelection.documents].sort((a,b) => ['public','internal','restricted','confidential'].indexOf(b.sensitivity)-['public','internal','restricted','confidential'].indexOf(a.sensitivity))[0].sensitivity : sensitivity;
  const chooseFile = (value: File | undefined) => {
    if (!value || submitting) return;
    if (!/\.(pdf|docx|txt|md|png|jpg|jpeg|tiff|bmp|gif)$/i.test(value.name)) { setError('Choose a PDF, DOCX, text, Markdown, or supported image file.'); return; }
    if (value.size > UPLOAD_MAX_BYTES || value.size === 0) { setError(`Choose a non-empty file smaller than ${UPLOAD_MAX_MB} MB.`); return; }
    setFile(value); setSourceInfo(null); setSourceId(''); setUploadedId(''); setError('');
  };
  const toggle = (id: OutputType) => setTypes(v => v.includes(id) ? v.filter(t => t !== id) : [...v, id]);
  const checkHealth = async () => {
    setChecking(true);
    try { setHealth(await api.getProviderHealth()); }
    catch { setHealth({ available: false, message: 'Cannot reach the server. Check that the API is running.' }); }
    finally { setChecking(false); }
  };
  const submit = async () => {
    if (!hasSource || !types.length || submitting || multiBusy) return;
    if (!Number.isFinite(Number(budget)) || Number(budget) <= 0) { setError('Enter a budget greater than zero.'); return; }
    setSubmitting(true); setError('');
    try {
      let id = multiMode ? multiSelection!.source_ids[0] : sourceId || uploadedId;
      if (!id && file) {
        const data = new FormData(); data.append('file', file); data.append('sensitivity', sensitivity);
        const src = await api.uploadSource(data); id = src.id; setUploadedId(id);
      }
      const request = { source_id: id, output_types: types, sensitivity,
        ...(multiMode && multiSelection ? {source_ids:multiSelection.source_ids,analysis_id:multiSelection.analysis_id,conflict_resolutions:multiSelection.conflict_resolutions} : {}),
        budget_type: 'cost_usd' as const, budget_ceiling: Number(budget),
        parameters: { audience, tone, detail, language, objective, style, brand_name: brandName, sections: sections.split('\n').map(v => v.trim()).filter(Boolean) } };
      const payload = JSON.stringify(request);
      if (submission.current.payload !== payload) submission.current = { payload, key: crypto.randomUUID() };
      const run = await api.createGeneration(request, submission.current.key);
      router.push(`/dashboard/generations?run=${run.id}`);
    } catch (e) { setError((e as { message?: string }).message || 'Could not start. Please try again.'); }
    finally { setSubmitting(false); }
  };

  const presetSettings: CreationPreset['settings'] = { params: { audience, tone, language, detail_level: detail, objective, style, brand_name: brandName, sections: sections.split('\n').map(v => v.trim()).filter(Boolean) }, output_types: types };
  const applyPreset = (value: CreationPreset['settings']) => { const p = value.params;
    setTypes(value.output_types); setAudience(p.audience || 'general'); setTone(p.tone || 'professional'); setLanguage(p.language || 'en'); setDetail(p.detail_level || 'medium'); setObjective(p.objective || ''); setStyle(p.style || ''); setBrandName(p.brand_name || ''); setSections((p.sections || []).join('\n'));
  };
  const advance = async () => {
    if (step === 0 && file && !uploadedId) {
      setSubmitting(true); setError('');
      try { const body = new FormData(); body.append('file', file); body.append('sensitivity', sensitivity); body.append('truncate_long_content', String(truncate)); const value = await api.uploadSource(body); setUploadedId(value.id); setSourceInfo(value); }
      catch (e) { setError((e as Error).message); return; }
      finally { setSubmitting(false); }
    }
    if (step === 2 && (!Number.isFinite(Number(budget)) || Number(budget) <= 0)) { setError('Enter a budget greater than zero.'); return; }
    goToStep(step + 1);
  };
  return <div className="create-page">
    <Link href="/dashboard/generations" className="quiet-link"><ArrowLeft size={15} /> Back to my outputs</Link>
    <div className="workspace-page-heading"><div><p className="workspace-eyebrow">From a document to something useful</p>
      <h1>Create an output</h1><p>Bring the source. Choose what you need. We’ll help with the first draft.</p></div></div>
    <nav className="create-steps" aria-label="Creation steps">{['Choose a source', 'Choose outputs', 'Make it yours', 'Review & create'].map((label, i) =>
      <button key={label} type="button" className={cn(step === i && 'active', step > i && 'done')} aria-current={step === i ? 'step' : undefined}
        disabled={submitting || multiBusy || (i > 0 && !hasSource) || (i > 0 && !!file && !uploadedId) || (i > 1 && !types.length)} onClick={() => { goToStep(i); }}>
        <span>{step > i ? <Check size={14} /> : `0${i + 1}`}</span>{label}</button>)}</nav>
    <div className="create-layout"><section className="flow-panel" aria-label={`Step ${step + 1}`}>
      {step === 0 && <>
        <div className="synthesis-mode" role="group" aria-label="Source selection mode"><button type="button" aria-pressed={!multiMode} disabled={multiBusy} onClick={() => setMultiMode(false)}>One document</button><button type="button" aria-pressed={multiMode} disabled={multiBusy} onClick={() => { setMultiMode(true);setFile(null);setUploadedId(''); }}>Combine documents</button></div>
        {multiMode ? <MultiSourcePicker onReady={setMultiSelection} onBusy={setMultiBusy} initialCollection={query.get('collection')} initialSelection={multiSelection} /> : <>
        <h2 ref={stepHeading} tabIndex={-1}>What are we working with?</h2><p className="muted">Upload a new document or pick one you’ve already added.</p>
        <input ref={input} disabled={submitting} type="file" accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg,.tiff,.bmp,.gif" className="sr-only" aria-label="Upload source file" onChange={e => { chooseFile(e.target.files?.[0]); e.target.value = ''; }} />
        <div className={cn('upload-zone', dragging && 'dragging')} onDragOver={e => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)}
          onDrop={e => { e.preventDefault(); setDragging(false); chooseFile(e.dataTransfer.files[0]); }}>
          {hasSource ? <><CheckCircle2 size={30} className="text-emerald-400" /><strong>{name}</strong>
            <span>{selectedSource ? 'Saved source · no need to upload again' : `${((file?.size || 0) / 1024).toFixed(0)} KB · ready to upload`}</span>
            <button className="quiet-link" disabled={submitting} onClick={() => { setFile(null); setSourceInfo(null); setSourceId(''); setUploadedId(''); }}><X size={14} /> Change document</button></> :
            <><UploadCloud size={32} /><strong>Drop a document here</strong><span>PDF, DOCX, text, Markdown or images · up to {UPLOAD_MAX_MB} MB</span>
              <button className="flow-button secondary" disabled={submitting} onClick={() => input.current?.click()}>Browse files</button></>}
        </div>
        <p className="muted text-xs mt-4">Up to 15,000 words or 90,000 characters. Images require server OCR (60% minimum confidence); scanned PDFs need OCR first. DOCX reads paragraphs and tables, not embedded images.</p>
        {file && !uploadedId && <><label className="flow-label">Source sensitivity<select className="flow-input" value={sensitivity} onChange={e => setSensitivity(e.target.value as Sensitivity)}>{['public', 'internal', 'restricted', 'confidential'].map(v => <option key={v}>{v}</option>)}</select></label><label className="settings-check mt-4"><input type="checkbox" checked={truncate} onChange={e => setTruncate(e.target.checked)} />Allow truncation to the extraction limit</label></>}
        {selectedSource?.was_truncated && <div className="flow-error">This source was truncated. Review the extracted text in the <Link href="/dashboard/library">source library</Link> before continuing.</div>}
        <div className="section-line"><h3>Or use a saved source</h3><span>{data.total} documents</span></div>
        <input aria-label="Search saved sources" className="flow-input" placeholder="Search your documents…" value={search} onChange={e => { setSearch(e.target.value); setOffset(0); }} />
        {loading && <p className="muted" role="status">Loading your documents…</p>}
        {sourceError && <div role="alert" className="flow-error">Couldn’t load your saved sources. <button onClick={refetch}>Try again</button></div>}
        <div className="saved-sources">{sources.map(s =>
          <button key={s.id} className={cn('saved-source', sourceId === s.id && 'selected')} disabled={submitting || s.status !== 'ready'} onClick={() => { setSourceInfo(s); setSourceId(s.id); setFile(null); setUploadedId(''); setSensitivity(s.sensitivity); setError(''); }} aria-pressed={sourceId === s.id}>
            <FileText size={18} /><span><strong>{documentName(s.filename)}</strong><small>{s.word_count.toLocaleString()} words · {formatRelative(s.created_at)}</small></span>{sourceId === s.id && <Check size={17} />}</button>)}
          {!loading && !sourceError && !sources.length && <p className="muted">{search ? 'No matching documents.' : 'Your uploaded documents will appear here.'}</p>}</div>
        <div className="library-pagination"><button className="quiet-link" disabled={!offset || loading} onClick={() => setOffset(Math.max(0, offset - 12))}>Previous sources</button><Link className="quiet-link" href="/dashboard/library">Open source library</Link><button className="quiet-link" disabled={loading || offset + 12 >= data.total} onClick={() => setOffset(offset + 12)}>Next sources</button></div>
        </>}
      </>}
      {step === 1 && <><h2 ref={stepHeading} tabIndex={-1}>What would you like to create?</h2><p className="muted">Start with one format, or choose a few. You can make more later.</p>
        <div className="format-grid">{(moreFormats ? OUTPUT_FORMATS : OUTPUT_FORMATS.slice(0, 6)).map(f => <button key={f.id} className={cn('format-option', types.includes(f.id) && 'selected')} aria-pressed={types.includes(f.id)} onClick={() => toggle(f.id)}>
          <div><FileText size={18} /><span className="format-check">{types.includes(f.id) && <Check size={13} />}</span></div>
          <strong>{f.label}</strong><p>{f.description}</p><small>{contracts.find(c => c.id === f.id)?.sections.join(' → ') || f.preview}</small></button>)}</div><button className="quiet-link mt-5" onClick={() => setMoreFormats(!moreFormats)}>{moreFormats ? 'Show fewer formats' : 'Show 7 more formats'}</button></>}
      {step === 2 && <><h2 ref={stepHeading} tabIndex={-1}>A little direction goes a long way.</h2><p className="muted">The defaults work well. Add a goal to make the result more useful.</p>
        <PresetPicker settings={presetSettings} onApply={applyPreset} />
        <label className="flow-label">What should this output help you do? <span>Optional</span><textarea className="flow-input" rows={3} value={objective} onChange={e => setObjective(e.target.value)} placeholder="For example: explain the key findings and recommend the next steps for our leadership team." /></label>
        <div className="field-grid"><label className="flow-label">Audience<select className="flow-input" value={audience} onChange={e => setAudience(e.target.value)}>{!['general','executives','technical','customers'].includes(audience) && <option value={audience}>{audience}</option>}<option value="general">General readers</option><option value="executives">Leadership team</option><option value="technical">Technical team</option><option value="customers">Customers</option></select></label>
          <label className="flow-label">Tone<select className="flow-input" value={tone} onChange={e => setTone(e.target.value)}>{!['professional','conversational','formal','persuasive'].includes(tone) && <option>{tone}</option>}<option>professional</option><option>conversational</option><option>formal</option><option>persuasive</option></select></label></div>
        <details className="advanced-settings"><summary>Advanced settings <span>Length, language, budget & privacy</span></summary>
          <div className="field-grid"><label className="flow-label">Detail level<select className="flow-input" value={detail} onChange={e => setDetail(e.target.value)}><option value="low">Brief</option><option value="medium">Balanced</option><option value="high">Detailed</option></select></label>
            <label className="flow-label">Language<select className="flow-input" value={language} onChange={e => setLanguage(e.target.value)}><option value="en">English</option><option value="hi">Hindi</option><option value="es">Spanish</option><option value="fr">French</option></select></label>
            <label className="flow-label">Source sensitivity<select className="flow-input" disabled={multiMode || !!selectedSource} value={effectiveSensitivity} onChange={e => setSensitivity(e.target.value as Sensitivity)}>{['public', 'internal', 'restricted', 'confidential'].map(v => <option key={v}>{v}</option>)}</select>{multiMode ? <small>Uses the strictest classification across selected documents.</small> : selectedSource && <small>Uses the saved document’s classification.</small>}</label>
            <label className="flow-label">Budget ceiling (USD)<input className="flow-input" type="number" min="0.01" step="0.01" value={budget} onChange={e => setBudget(e.target.value)} /><small>Calls reserve an estimate before dispatch. Provider billing may differ; any overrun is shown.</small></label></div>
          <label className="flow-label">Brand name<input className="flow-input" maxLength={150} value={brandName} onChange={e => setBrandName(e.target.value)} /></label>
          <label className="flow-label">Additional section titles<textarea className="flow-input" rows={3} value={sections} onChange={e => setSections(e.target.value)} placeholder="One title per line. Required format sections are kept." /></label>
          <label className="flow-label">Writing or brand guidelines<textarea rows={2} className="flow-input" value={style} onChange={e => setStyle(e.target.value)} placeholder="For example: use plain language and avoid promotional claims." /></label>
        </details>
        <button className="quiet-link connection-check" disabled={checking} onClick={checkHealth}>{checking ? <Loader2 size={15} className="animate-spin" /> : <Wifi size={15} />} {checking ? 'Checking connection…' : 'Check AI connection'}</button>
        {health && <p role="status" className={health.available ? 'text-emerald-400 text-sm' : 'flow-error'}>{health.message}</p>}
      </>}
      {step === 3 && <><h2 ref={stepHeading} tabIndex={-1}>Ready to create?</h2><p className="muted">Check the source, formats and preferences. Generation sends the extracted source content to your configured AI provider.</p><dl className="review-list"><div><dt>Source</dt><dd>{name} · {effectiveSensitivity} · {multiSelection ? multiSelection.documents.length + ' documents' : (selectedSource?.word_count?.toLocaleString() || 'Extracted') + ' words'} {selectedSource?.was_truncated && !multiSelection ? '· Truncated' : ''}</dd></div><div><dt>Outputs</dt><dd>{types.map(t => <p key={t}>{outputLabel(t)} · {contracts.find(c => c.id === t)?.deliverable || 'Written output'}</p>)}</dd></div><div><dt>Audience / tone / language / detail</dt><dd>{audience} · {tone} · {language} · {detail}</dd></div><div><dt>Goal</dt><dd>{objective || 'Use the format defaults'}</dd></div><div><dt>Brand and writing guidance</dt><dd>{brandName || 'No brand'}{style ? `: ${style}` : ''}</dd></div><div><dt>Additional sections</dt><dd>{sections || 'Required format sections only'}</dd></div><div><dt>Budget admission limit</dt><dd>USD {Number(budget).toFixed(2)} · estimates may differ from provider billing.</dd></div></dl></>}
      {error && <div role="alert" className="flow-error">{error}</div>}
      {step === 3 && multiMode && multiSelection && <div className="synthesis-review"><h3>Combined source decisions</h3><p>{multiSelection.documents.length} saved source snapshots · {effectiveSensitivity} sensitivity</p><p>Source analysis used {multiSelection.analysis_budget_used.toFixed(4)} {multiSelection.analysis_budget_type === 'cost_usd' ? 'USD' : 'tokens'}. The output generation below uses a separate fresh budget.</p>{Object.entries(multiSelection.conflict_resolutions).map(([key,choice],index)=><p key={key}>Potential conflict {index+1}: {choice.choice === 'preserve' ? 'Keep both accounts and flag uncertainty' : choice.choice === 'omit' ? 'Omit disputed claims' : `Prefer ${multiSelection.documents.find(d=>d.id===choice.preferred_source_id)?.filename} and note the discrepancy`}</p>)}</div>}
      <div className="flow-footer"><button className="flow-button secondary" disabled={submitting || multiBusy} onClick={() => step ? goToStep(step - 1) : router.push('/dashboard/generations')}><ArrowLeft size={15} />{step ? 'Back' : 'Cancel'}</button>
        {step < 3 ? <button className="flow-button" disabled={submitting || multiBusy || !hasSource || (step === 1 && !types.length)} onClick={advance}>Continue <ArrowRight size={15} /></button> :
          <button className="flow-button" disabled={submitting || !types.length} onClick={submit}>{submitting ? <Loader2 size={16} className="animate-spin" /> : <ArrowRight size={16} />}{submitting ? 'Starting saved request…' : `Generate ${types.length === 1 ? 'output' : `${types.length} outputs`}`}</button>}</div>
    </section><aside className="creation-summary"><p className="workspace-eyebrow">Your next output</p><h3>{hasSource ? name : 'Start with a source'}</h3><p className="muted">{hasSource ? 'Your document stays connected to every output.' : 'Add a document to get started.'}</p>
      <div className="summary-divider" /><span className="summary-label">Selected formats</span>{types.map(t => <div className="summary-format" key={t}><FileText size={14} />{outputLabel(t)}</div>)}
      <div className="summary-divider" /><div className="summary-note"><CheckCircle2 size={17} /><p>Built-in checks<span>Every output goes through style, fact, and compliance reviews. Results are shown alongside the content.</span></p></div>
      <p className="summary-footnote">You can edit, copy, and download your output when it’s ready.</p></aside></div>
  </div>;
}

export default function SourcesPage() { return <Suspense fallback={<p role="status">Loading creation flow…</p>}><CreatePage /></Suspense>; }

'use client';
import { useEffect, useRef, useState } from 'react';
import { Artifact, EvidenceAnchor, EvidenceClaim, EvidenceSpan, ReviewContext } from '@/lib/types';
import { getReviewContext, getSourceText, submitComplianceOverride, submitFeedback } from '@/lib/api';
import { cn } from '@/lib/utils';

export function EvidencePanel({ artifact, sourceId, changed, readOnly = false, onLocate, onUpdated }: {
  artifact: Artifact; sourceId: string; changed: boolean;
  readOnly?: boolean; onLocate: (spans: EvidenceSpan[]) => void; onUpdated: () => void;
}) {
  const [tab, setTab] = useState<'findings' | 'sources' | 'checks' | 'decisions'>('findings');
  const [selected, setSelected] = useState<{ claim: EvidenceClaim; anchor: EvidenceAnchor } | null>(null);
  const [source, setSource] = useState<{ id: string; text: string; source_version: string; filename?: string } | null>(null);
  const [sourceFilter, setSourceFilter] = useState('');
  const [sourceState, setSourceState] = useState('');
  const [context, setContext] = useState<ReviewContext | null>(null);
  const [contextError, setContextError] = useState('');
  const [reload, setReload] = useState(0);
  const [rating, setRating] = useState<'positive' | 'negative'>('negative');
  const [comment, setComment] = useState('');
  const [reason, setReason] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const heading = useRef<HTMLHeadingElement>(null);
  const passageHeading = useRef<HTMLHeadingElement>(null);
  const sourceRequest = useRef(0);
  const evidence = artifact.evidence;
  useEffect(() => {
    heading.current?.focus({ preventScroll: true }); heading.current?.scrollIntoView({ block: 'start' });
  }, []);
  useEffect(() => {
    if (selected) { passageHeading.current?.focus({ preventScroll: true }); passageHeading.current?.scrollIntoView({ block: 'start' }); }
  }, [selected]);
  useEffect(() => {
    if (readOnly) return;
    let active = true;
    getReviewContext(artifact.id).then(value => { if (active) { setContext(value); setContextError(''); } })
      .catch((e) => { if (active) setContextError(e.message || 'Review permissions and history could not be loaded.'); });
    return () => { active = false; };
  }, [artifact.id, reload, readOnly]);
  const viewSource = async (claim: EvidenceClaim, anchor: EvidenceAnchor) => {
    const request = ++sourceRequest.current;
    setSelected({ claim, anchor }); setTab('sources'); setSourceState('Loading source passage…');
    try {
      const result = await getSourceText(anchor.source_id || sourceId, artifact.generation_id, anchor.source_version || undefined);
      if (request === sourceRequest.current) { setSource(result); setSourceState(''); }
    } catch (e) { if (request === sourceRequest.current) setSourceState((e as Error).message || 'Could not load the source. Select the passage to try again.'); }
  };
  const decide = async (action: 'feedback' | 'override') => {
    setBusy(true); setError(''); setNotice('');
    try {
      if (action === 'feedback') {
        await submitFeedback(artifact.id, rating, comment, evidence?.content_version);
        setNotice('Feedback saved with this output’s content version.'); setComment('');
      } else {
        await submitComplianceOverride({ artifact_id: artifact.id, override_reason: reason,
          sensitivity: artifact.sensitivity_provenance.operator, expected_content_version: evidence?.content_version });
        setNotice('Compliance exception recorded. Failed checks remain visible.'); setReason(''); setConfirmed(false);
      }
      setReload(value => value + 1); onUpdated();
    } catch (e) {
      const failure = e as { message?: string; kind?: string; status?: number };
      const message = failure.kind === 'backend_unavailable' && !failure.status ? 'Could not reach the API.' : failure.message || 'Could not save.';
      setError(`${message} Your input is kept. Try saving again when the service is available.`);
    }
    finally { setBusy(false); }
  };
  const anchor = selected?.anchor;
  const sourceMatches = source && anchor && source.source_version === anchor.source_version &&
    anchor.source_id === source.id && anchor.start !== null && anchor.end !== null &&
    Array.from(source.text).slice(anchor.start, anchor.end).join('') === anchor.text;
  const failedCompliance = artifact.reviewer_outcomes.some(r => r.reviewer === 'compliance' && r.status === 'fail');
  return <aside id={`evidence-panel-${artifact.id}`} className="evidence-panel phase4-evidence" aria-label="Evidence and review">
    <div className="evidence-summary"><h3 ref={heading} tabIndex={-1}>Evidence & review</h3><p>{evidence ? `${evidence.anchors_matched} of ${evidence.anchors_total} recorded source anchors matched` : 'No evidence validation was recorded.'}</p>
      <p className="muted">{changed ? 'You are editing a local draft. These checks and decisions apply to the original output.' : 'Exact quotes confirm location. They do not certify factual accuracy.'}</p></div>
    <div className="evidence-tabs" role="group" aria-label="Evidence view">{(['findings', 'sources', 'checks', ...(readOnly ? [] : ['decisions'])] as ('findings' | 'sources' | 'checks' | 'decisions')[]).map(value =>
      <button key={value} aria-pressed={tab === value} onClick={() => setTab(value)}>{value === 'findings' ? `Findings (${evidence?.findings.length ?? 0})` : value[0].toUpperCase() + value.slice(1)}</button>)}</div>
    <div className="evidence-tab-content">
      {tab === 'findings' && <>
        {!evidence && <p className="muted">This older output needs a new version to record evidence checks.</p>}
        {evidence && !evidence.findings.length && <p className="evidence-success">{artifact.assurance_status === 'unreviewed' ? 'Required reviews have not completed. This saved draft is unreviewed.' : 'No findings in the recorded checks. Read the source and assess the output before use.'}</p>}
        {evidence?.findings.map((finding, i) => <article className="evidence-finding" key={`${finding.id}-${i}`}><span className="summary-label">{finding.reviewer.replace(/_/g, ' ')} check</span>
          <p>{finding.message}</p>{finding.claim && finding.claim !== finding.message && <blockquote>{finding.claim}</blockquote>}
          {finding.output_spans.length > 0 && !changed ? <button className="quiet-link" onClick={() => onLocate(finding.output_spans)}>Show affected text</button> : <small className="muted">{changed ? 'View the original to locate findings.' : 'Applies to the output as a whole, or no exact excerpt was supplied.'}</small>}
          {finding.claim_id && evidence.claims.find(c => c.id === finding.claim_id)?.anchors.map(a => <button className="quiet-link" key={a.id} onClick={() => viewSource(evidence.claims.find(c => c.id === finding.claim_id)!, a)}>Inspect recorded source passage</button>)}
        </article>)}
        <p className="muted evidence-limitation">{evidence?.limitation}</p>
      </>}
      {tab === 'sources' && <>
        {(evidence?.source_documents?.length || 0) > 1 && <label className="flow-label">Filter references by document<select className="flow-input" value={sourceFilter} onChange={e => setSourceFilter(e.target.value)}><option value="">All source documents</option>{evidence!.source_documents!.map(doc => <option key={doc.id} value={doc.id}>{doc.filename}</option>)}</select></label>}
        <p className="muted">Select a reference to inspect its exact passage. Recommendations are proposals; calculations require cited inputs.</p>
        {evidence?.claims.filter(claim => !sourceFilter || claim.anchors.some(a => a.source_id === sourceFilter)).map((claim, i) => <article className="reference-card" key={claim.id}><span>{claim.kind === 'fact' ? 'Source fact' : claim.kind === 'calculation' ? 'Derived calculation' : claim.kind === 'recommendation' ? 'Recommendation' : 'Unsupported statement'} {i + 1}</span>
          <p>{claim.claim || 'Missing claim text'}</p><small>{claim.status === 'matched' ? claim.kind === 'recommendation' ? 'Explicitly labeled proposal' : 'Recorded reference checks passed' : 'Reference needs attention'}</small>
          {claim.calculation && <details><summary>Declared calculation</summary><p>Operation: {claim.calculation.operation.replace(/_/g, ' ')}<br />Inputs: {claim.calculation.inputs.join(', ')}<br />Result: {claim.calculation.result}</p></details>}
          {!changed && claim.output_spans.length > 0 && <button className="quiet-link" onClick={() => onLocate(claim.output_spans)}>Show in output</button>}
          {claim.anchors.map((a, j) => <button className="quiet-link" key={a.id + j} onClick={() => viewSource(claim, a)}>Open {a.filename || (claim.kind === 'calculation' ? `input ${j + 1}` : 'source passage')} →</button>)}
        </article>)}
        {!evidence?.claims.length && <p className="muted">No claim references are available.</p>}
        {selected && anchor && <section className="source-passage" aria-live="polite"><h4 ref={passageHeading} tabIndex={-1}>Stored source passage</h4>
          {source?.filename && <p className="summary-label">{source.filename} · version {anchor.source_version?.slice(0,10)}</p>}
          {sourceState ? <p role="status">{sourceState}</p> : sourceMatches ? <p>{Array.from(source!.text).slice(Math.max(0, anchor.start! - 180), anchor.start!).join('')}<mark>{anchor.text}</mark>{Array.from(source!.text).slice(anchor.end!, anchor.end! + 180).join('')}</p> : <><p role="alert">The document version or exact offsets do not match. This excerpt is unverified; no alternative passage was selected.</p><blockquote>{anchor.text}</blockquote></>}
          {anchor.reason && <p className="muted">{anchor.reason}</p>}
          {anchor.resolution === 'unique_quote' && <p className="muted">The server located this exact quote uniquely in the source and corrected the model’s offsets ({anchor.model_start}–{anchor.model_end}). The highlighted range is the validated source location.</p>}
          <details><summary>Reference details</summary><dl><dt>Source</dt><dd>{anchor.source_id || 'Not recorded'}</dd><dt>Text version</dt><dd>{anchor.source_version}</dd><dt>Character range</dt><dd>{anchor.start ?? '?'}–{anchor.end ?? '?'} (Unicode characters)</dd></dl></details>
        </section>}
      </>}
      {tab === 'checks' && <>
        <p className="muted">Model reviews are assessments, not certified accuracy. These results apply to this selected content version.</p>
        {artifact.reviewer_outcomes.map((review, i) => <article className="review-result" key={`${review.reviewer}-${i}`}><div><strong>{review.reviewer.replace(/_/g, ' ')} {review.blocking === false ? 'advisory' : 'check'}</strong><span className={cn('status-pill', review.status === 'pass' ? 'ready' : 'attention')}>{review.blocking === false ? (review.status === 'pass' ? 'Advisory passed' : 'Advisory findings') : review.status === 'pass' ? 'Passed' : 'Needs attention'}</span></div><p>{review.reason}</p></article>)}
        {!artifact.reviewer_outcomes.length && <p>No review results were recorded.</p>}
        {(artifact.review_attempts?.length ?? 0) > 0 && <details className="evidence-provenance"><summary>Correction history ({artifact.review_attempts!.length} attempts)</summary>{artifact.review_attempts!.map(attempt => <div key={attempt.attempt}><strong>Attempt {attempt.attempt}</strong><ul>{attempt.checks.map((check, i) => <li key={i}>{check.reviewer_name.replace(/_/g, ' ')}: {check.passed ? 'passed' : 'needs attention'}</li>)}</ul><small className="muted">Content version {attempt.content_version}</small></div>)}</details>}
        <details className="evidence-provenance"><summary>Technical provenance</summary><dl><dt>Model</dt><dd>{artifact.model_version}</dd><dt>Prompt</dt><dd>{artifact.prompt_version}</dd><dt>Evidence check</dt><dd>{evidence?.version || 'Not recorded'}</dd><dt>Content version</dt><dd>{evidence?.content_version || 'Not recorded'}</dd></dl></details>
      </>}
      {tab === 'decisions' && <>
        {notice && <p role="status" className="evidence-success">{notice}</p>}{error && <p role="alert" className="flow-error">{error}</p>}
        <form onSubmit={e => { e.preventDefault(); void decide('feedback'); }} className="review-form"><h4>Give feedback</h4><p className="muted">Feedback is saved against the original output and does not change its review result.</p>
          <label>Assessment<select className="flow-input" value={rating} disabled={busy || changed} onChange={e => setRating(e.target.value as typeof rating)}><option value="negative">Needs improvement</option><option value="positive">Useful</option></select></label>
          <label>Comment<textarea className="flow-input" rows={3} maxLength={4000} value={comment} disabled={busy || changed} onChange={e => setComment(e.target.value)} /></label><button className="flow-button secondary" disabled={busy || changed}>Save feedback</button></form>
        {contextError && <p role="alert">{contextError} <button className="quiet-link" onClick={() => setReload(v => v + 1)}>Try again</button></p>}
        {failedCompliance && <section className="review-exception"><h4>Compliance exception</h4><p className="muted">A reviewer or administrator can record a justified exception. It does not pass the failed check, verify facts, or change the source sensitivity.</p>
          {!context ? <p>{contextError ? 'Decision permissions are unavailable. Try loading them again above.' : 'Loading decision permissions…'}</p> : !context.can_override ? <p className="muted">Your role cannot record compliance exceptions.</p> : <form className="review-form" onSubmit={e => { e.preventDefault(); void decide('override'); }}>
            <label>Decision reason<textarea className="flow-input" rows={3} minLength={10} maxLength={2000} required value={reason} disabled={busy || changed} onChange={e => setReason(e.target.value)} /></label>
            <label className="review-confirm"><input type="checkbox" checked={confirmed} disabled={busy || changed} onChange={e => setConfirmed(e.target.checked)} />I understand this decision is attributed and saved permanently with the original content version.</label>
            <button className="flow-button secondary" disabled={busy || changed || !confirmed || reason.trim().length < 10}>Record exception</button></form>}
        </section>}
        <section className="review-history"><h4>Decision history</h4><p className="muted">Latest 50 recorded decisions for this output.</p>{context && !context.events.length && <p className="muted">No feedback or exceptions have been recorded yet.</p>}{context?.events.map(event => <article key={event.id}><strong>{event.event === 'USER_FEEDBACK' ? 'Feedback saved' : 'Compliance exception recorded'}</strong><p>{String(event.details.reason || event.details.comment || event.details.rating || '')}</p><small>{event.operator} · {new Date(event.created_at).toLocaleString()}</small><details><summary>Content version</summary><code>{String(event.details.content_version || 'Not recorded')}</code></details></article>)}</section>
      </>}
    </div>
  </aside>;
}

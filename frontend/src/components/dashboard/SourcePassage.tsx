'use client';
import { useState } from 'react';
import { SourceReference } from '@/lib/types';
import { getSourceText } from '@/lib/api';

export function SourcePassage({reference, generationId}: {reference: SourceReference; generationId: string}) {
  const [passage,setPassage] = useState<{before:string;quote:string;after:string}|null>(null);
  const [error,setError] = useState(''); const [busy,setBusy] = useState(false);
  const open = async () => {
    setBusy(true);setError('');
    try {
      const value = await getSourceText(reference.source_id,generationId,reference.source_version);
      const chars=Array.from(value.text);const quote=chars.slice(reference.start_char,reference.end_char).join('');
      if(quote!==reference.source_span) throw new Error('The exact passage could not be matched. No substitute passage was shown.');
      setPassage({before:chars.slice(Math.max(0,reference.start_char-200),reference.start_char).join(''),quote,
        after:chars.slice(reference.end_char,reference.end_char+200).join('')});
    } catch(e) {setError((e as Error).message);} finally {setBusy(false);}
  };
  return <div className="synthesis-passage"><p className="summary-label">{reference.filename || 'Source document'}</p><blockquote>{reference.source_span}</blockquote><small>Version {reference.source_version.slice(0,10)} · characters {reference.start_char}–{reference.end_char}</small><button type="button" className="quiet-link" disabled={busy} onClick={() => passage ? setPassage(null) : void open()}>{busy?'Loading…':passage?'Hide passage context':'Inspect exact source passage'}</button>{error&&<p role="alert" className="flow-error">{error}</p>}{passage&&<pre className="synthesis-context" tabIndex={0}>{passage.before}<mark>{passage.quote}</mark>{passage.after}</pre>}</div>;
}

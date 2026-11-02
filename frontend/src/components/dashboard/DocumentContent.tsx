'use client';
import { EvidenceSpan } from '@/lib/types';
import { ReactNode } from 'react';
function InlineText({ text }: { text: string }) {
  return <>{text.split(/(\*\*[^*]+\*\*)/g).map((part, i) => part.startsWith('**') ? <strong key={i}>{part.slice(2, -2)}</strong> : part)}</>;
}
export function DocumentContent({ content, selected, artifactId }: { content: string; selected: EvidenceSpan[]; artifactId: string }) {
  let first = true;
  const highlight = (line: string, start: number) => {
    const chars = Array.from(line);
    const intervals = selected.map(span => ({ start: Math.max(0, span.start - start), end: Math.min(chars.length, span.end - start) })).filter(span => span.end > span.start).sort((a, b) => a.start - b.start);
    const merged: EvidenceSpan[] = [];
    for (const span of intervals) { const last = merged.at(-1); if (last && span.start <= last.end) last.end = Math.max(last.end, span.end); else merged.push({ ...span }); }
    const parts = []; let cursor = 0;
    for (const span of merged) {
      parts.push(<InlineText key={`text-${cursor}`} text={chars.slice(cursor, span.start).join('')} />);
      parts.push(<mark key={`mark-${span.start}`} id={first ? `output-highlight-${artifactId}` : undefined} tabIndex={-1}><InlineText text={chars.slice(span.start, span.end).join('')} /></mark>); first = false; cursor = span.end;
    }
    parts.push(<InlineText key={`last-${cursor}`} text={chars.slice(cursor).join('')} />);
    return parts;
  };
  const lines = content.split('\n');
  const offsets: number[] = []; let offset = 0;
  for (const line of lines) { offsets.push(offset); offset += Array.from(line).length + 1; }
  const rendered: ReactNode[] = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]; const start = offsets[i];
    if (!line.trim()) { rendered.push(<div key={i} className="prose-space" />); continue; }
    const fence = line.match(/^\s*(```|~~~)/);
    if (fence) {
      const key = i; const code: ReactNode[] = []; i++;
      for (; i < lines.length && !lines[i].trimStart().startsWith(fence[1]); i++) code.push(<span key={i}>{highlight(lines[i], offsets[i])}{'\n'}</span>);
      rendered.push(<pre key={key} tabIndex={0}><code>{code}</code></pre>); continue;
    }
    if (i + 1 < lines.length && line.includes('|') && /^\s*\|?\s*:?-{3,}/.test(lines[i+1])) {
      const key = i; const rows: {line: string; start: number}[] = [{line, start}]; i += 2;
      while (i < lines.length && lines[i].includes('|') && lines[i].trim()) { rows.push({line:lines[i], start:offsets[i]}); i++; }
      i--;
      const cells = (row: {line: string; start: number}, header: boolean) => {
        const value = row.line.trim().replace(/^\||\|$/g, '');
        let position = row.line.indexOf(value);
        return value.split('|').map((cell, index) => {
          const begin = row.start + Array.from(row.line.slice(0, position)).length; position += cell.length + 1;
          return header ? <th scope="col" key={index}>{highlight(cell, begin)}</th> : <td key={index}>{highlight(cell, begin)}</td>;
        });
      };
      rendered.push(<div className="output-table-scroll" key={key} tabIndex={0} role="region" aria-label="Document table"><table><thead><tr>{cells(rows[0],true)}</tr></thead><tbody>{rows.slice(1).map((row,index) => <tr key={index}>{cells(row,false)}</tr>)}</tbody></table></div>); continue;
    }
    const heading = line.match(/^#{1,6}\s+(.+)/);
    if (heading) { rendered.push(<h3 key={i}>{highlight(heading[1], start + Array.from(line.slice(0, line.indexOf(heading[1]))).length)}</h3>); continue; }
    const bullet = line.match(/^\s*[-*•]\s+/);
    if (bullet) rendered.push(<p className="prose-bullet" key={i}><span aria-hidden="true">•</span><span>{highlight(line.slice(bullet[0].length), start + Array.from(bullet[0]).length)}</span></p>);
    else rendered.push(<p key={i}>{highlight(line, start)}</p>);
  }
  return <div className="output-prose">{rendered}</div>;
}

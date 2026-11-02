export function KeyFigures() {
  return <section id="key-figures" className="py-24 px-6 border-t border-surface-border bg-surface"><div className="max-w-content mx-auto">
    <p className="mono text-accent text-xs uppercase tracking-widest mb-4">Inspect the work</p><h2 className="display text-4xl mb-6">EVIDENCE YOU CAN OPEN.</h2>
    <p className="text-text-secondary max-w-2xl mb-10">Inspect source references, read reviewer findings, and keep the original output alongside your edits. Benchmark results belong to recorded evaluations, not sample counters.</p>
    <div className="grid md:grid-cols-3 gap-6">{[
      ['Source references', 'Open a recorded reference and compare it with the stored source passage.'],
      ['Review results', 'See the actual style, fact, and compliance results, including checks that need attention.'],
      ['Clear version status', 'Manual draft edits are labeled unreviewed. The original output remains available.'],
    ].map(([title, body]) => <div key={title} className="border border-surface-border rounded-xl p-7"><h3 className="text-xl mb-4">{title}</h3><p className="text-text-secondary text-sm leading-relaxed">{body}</p></div>)}</div>
  </div></section>;
}

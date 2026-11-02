export function TrustLog() {
  return <section className="py-24 px-6 border-t border-surface-border"><div className="max-w-content mx-auto"><p className="mono text-accent text-xs uppercase tracking-widest mb-4">Working principles</p>
    <h2 className="display text-4xl mb-8">KEEP THE CONTEXT.</h2><div className="grid md:grid-cols-3 gap-6">{[
      ['Keep the evidence close', 'A polished draft still needs judgment. Source references and review results stay available beside it.'],
      ['Make failures visible', 'Provider errors and unsuccessful checks need clear recovery paths, not a substituted success message.'],
      ['Label what changed', 'A manual edit is a new draft. Reviews of the original do not automatically verify your changes.'],
    ].map(([title, body]) => <div key={title} className="border border-surface-border rounded-xl p-7"><h3 className="text-lg mb-4">{title}</h3><p className="text-text-secondary text-sm leading-relaxed">{body}</p></div>)}</div></div></section>;
}

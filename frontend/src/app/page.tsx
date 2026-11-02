import type { Metadata } from 'next';
import { Nav }               from '@/components/marketing/Nav';
import { Hero }              from '@/components/marketing/Hero';
import { OutputTypeMarquee } from '@/components/marketing/OutputTypeMarquee';
import { LiveTransformation } from '@/components/marketing/LiveTransformation';
import { KeyFigures }        from '@/components/marketing/KeyFigures';
import { HowItWorks }        from '@/components/marketing/HowItWorks';
import { TrustAuditLog }     from '@/components/marketing/TrustAuditLog';
import { TrustLog }          from '@/components/marketing/TrustLog';
import { ClosingCTA, Footer } from '@/components/marketing/ClosingCTA';

export const metadata: Metadata = {
  title: 'Traceform — Every Claim Traced',
  description:
    'Turn one source into every format you need — with source references and recorded review results. Compare drafts with the evidence before you use them.',
};

export default function HomePage() {
  return (
    <>
      <Nav />
      <main id="main-content">
        {/* §3.2 — Full-viewport hero */}
        <Hero />

        {/* §3.3 — Output-type marquee */}
        <OutputTypeMarquee />

        {/* §3.4 — Live transformation showcase */}
        <LiveTransformation />

        {/* §3.5 — Key figures / animated counters */}
        <KeyFigures />

        {/* §3.6 — How It Works */}
        <HowItWorks />

        {/* §3.7 — Trust & Security (terminal audit log) */}
        <TrustAuditLog />

        {/* §3.9 — Trust Log (operator quotes) */}
        <TrustLog />

        {/* §3.10 — Closing CTA */}
        <ClosingCTA />
      </main>

      {/* §3.11 — Footer */}
      <Footer />
    </>
  );
}

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "TraceForm — Verified Intelligence Platform",
    template: "%s | TraceForm",
  },
  description:
    "Transform source intelligence into verified executive deliverables. Every output is fact-checked, provenance-traced, and audit-ready.",
  keywords: ["verified intelligence", "citation tracking", "compliance AI", "provenance", "executive deliverables"],
  openGraph: {
    type: "website",
    locale: "en_US",
    title: "TraceForm — Verified Intelligence Platform",
    description:
      "Verified intelligence for executives. Every deliverable is fact-checked, provenance-traced, and audit-ready.",
    siteName: "TraceForm",
  },
  twitter: {
    card: "summary_large_image",
    title: "TraceForm — Verified Intelligence Platform",
    description: "Verified intelligence for executives.",
  },
  robots: { index: true, follow: true },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-canvas text-text-primary antialiased">
        {children}
      </body>
    </html>
  );
}

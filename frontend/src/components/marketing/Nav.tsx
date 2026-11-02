'use client';
import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { motion, useReducedMotion } from 'framer-motion';
import { cn } from '@/lib/utils';

const NAV_LINKS = [
  { href: '#product',     label: 'Product' },
  { href: '#how-it-works',label: 'How it Works' },
  { href: '#trust',       label: 'Trust & Security' },
  { href: '#docs',        label: 'Docs' },
];

export function Nav() {
  const [scrolled, setScrolled]     = useState(false);
  const [visible, setVisible]       = useState(true);
  const lastScrollY                 = useRef(0);
  const prefersReducedMotion        = useReducedMotion();

  useEffect(() => {
    const onScroll = () => {
      const y = window.scrollY;
      setScrolled(y > 60);
      if (!prefersReducedMotion) {
        setVisible(y < lastScrollY.current || y < 80);
      }
      lastScrollY.current = y;
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, [prefersReducedMotion]);

  return (
    <motion.header
      className={cn(
        'fixed top-0 left-0 right-0 z-50',
        'transition-all duration-300',
        scrolled
          ? 'bg-canvas/90 backdrop-blur-sm border-b border-surface-border'
          : 'bg-transparent border-b border-transparent',
      )}
      animate={{ y: visible ? 0 : -80 }}
      transition={{ ease: [0.16, 1, 0.3, 1], duration: 0.3 }}
    >
      <div className="max-w-content mx-auto px-6 h-14 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 group" aria-label="Traceform home">
          <span className="display text-[1.1rem] tracking-widest text-text-primary group-hover:text-accent transition-colors duration-150">
            TRACEFORM
          </span>
          <span
            className="w-1.5 h-1.5 rounded-full bg-accent mt-0.5"
            aria-hidden="true"
          />
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-8" aria-label="Main navigation">
          {NAV_LINKS.map(({ href, label }) => (
            <a
              key={href}
              href={href}
              className="text-[11px] tracking-widest uppercase text-text-secondary hover:text-text-primary transition-colors duration-150 font-medium"
            >
              {label}
            </a>
          ))}
        </nav>

        {/* CTA */}
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard"
            className="hidden sm:block text-[11px] tracking-widest uppercase text-text-secondary hover:text-text-primary transition-colors duration-150 font-medium"
          >
            Dashboard
          </Link>
          <Link
            href="#product"
            className="inline-flex items-center px-4 py-2 text-[11px] tracking-widest uppercase font-medium rounded bg-accent text-canvas hover:bg-accent/90 transition-colors duration-150"
          >
            See an Example Trace
          </Link>
        </div>
      </div>
    </motion.header>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Traceform Design Tokens
// Single source of truth — maps 1:1 with CSS custom properties in globals.css
// ─────────────────────────────────────────────────────────────────────────────

export const colors = {
  // Base canvas
  canvas:           '#0A0A0A',
  surface:          '#111111',
  surfaceElevated:  '#161616',
  surfaceBorder:    '#1F1F1F',
  surfaceBorderSub: '#2A2A2A',

  // Text
  textPrimary:   '#F3F3EF',
  textSecondary: '#8A8A8A',
  textTertiary:  '#555555',
  textInverse:   '#0A0A0A',

  // Accent — amber/gold (citation highlight / verified motif)
  accent:        '#F5A623',
  accentSubtle:  'rgba(245,166,35,0.12)',
  accentBorder:  'rgba(245,166,35,0.25)',

  // Status (dashboard-only — desaturated, professional)
  statusPass:        '#3D7A5E',
  statusPassBg:      'rgba(61,122,94,0.12)',
  statusFail:        '#9B4040',
  statusFailBg:      'rgba(155,64,64,0.12)',
  statusBudget:      '#7A6B3D',
  statusBudgetBg:    'rgba(122,107,61,0.12)',
  statusPending:     '#555555',
  statusPendingBg:   'rgba(85,85,85,0.12)',
  statusRunning:     '#3D6B9B',
  statusRunningBg:   'rgba(61,107,155,0.12)',

  // Citation trace line
  traceLine:     'rgba(245,166,35,0.6)',
  traceLineFull: '#F5A623',
} as const;

export const typography = {
  fontDisplay: '"Bebas Neue", "Impact", sans-serif',
  fontBody:    '"Inter", "system-ui", sans-serif',
  fontMono:    '"JetBrains Mono", "Fira Code", monospace',

  // Scale (rem)
  sizeXs:  '0.75rem',   // 12px
  sizeSm:  '0.875rem',  // 14px
  sizeMd:  '1rem',      // 16px
  sizeLg:  '1.125rem',  // 18px
  sizeXl:  '1.25rem',   // 20px
  size2xl: '1.5rem',    // 24px
  size3xl: '1.875rem',  // 30px
  size4xl: '2.25rem',   // 36px
  size5xl: '3rem',      // 48px
  size6xl: '3.75rem',   // 60px
  size7xl: '4.5rem',    // 72px
  size8xl: '6rem',      // 96px
  size9xl: '8rem',      // 128px

  weightNormal:   '400',
  weightMedium:   '500',
  weightSemibold: '600',
  weightBold:     '700',

  lineHeightTight:  '1.1',
  lineHeightSnug:   '1.3',
  lineHeightNormal: '1.5',
  lineHeightRelaxed:'1.7',

  trackingTight:  '-0.04em',
  trackingNormal: '0em',
  trackingWide:   '0.08em',
  trackingWidest: '0.16em',
} as const;

export const spacing = {
  // 8px base scale
  px:   '1px',
  0.5:  '4px',
  1:    '8px',
  1.5:  '12px',
  2:    '16px',
  2.5:  '20px',
  3:    '24px',
  4:    '32px',
  5:    '40px',
  6:    '48px',
  8:    '64px',
  10:   '80px',
  12:   '96px',
  16:   '128px',
  20:   '160px',
  24:   '192px',
} as const;

// ─────────────────────────────────────────────────────────────────────────────
// Motion tokens — tagged by tier
// marketing: cinematic, scroll-driven
// dashboard: fast, functional
// ─────────────────────────────────────────────────────────────────────────────
export const motion = {
  // Shared
  durationFast:    150,  // ms — UI micro-interactions
  durationNormal:  200,  // ms — hovers, state changes
  durationMedium:  300,  // ms — drawer open/close, route wipe

  // Marketing tier only
  durationHeroKinetic:  750,  // ms — hero headline stagger
  durationScrollReveal: 500,  // ms — section fade-up
  durationCounter:      1400, // ms — count-up animations
  marqueeSpeed:         40,   // seconds for full loop

  // Easing
  easeDefault:     'cubic-bezier(0.4, 0, 0.2, 1)',
  easeOut:         'cubic-bezier(0, 0, 0.2, 1)',
  easeIn:          'cubic-bezier(0.4, 0, 1, 1)',
  easeInOut:       'cubic-bezier(0.4, 0, 0.2, 1)',
  easeOutExpo:     'cubic-bezier(0.16, 1, 0.3, 1)',
  easeOutQuart:    'cubic-bezier(0.25, 1, 0.5, 1)',
} as const;

export const layout = {
  navRailWidth:      '64px',
  navRailWidthOpen:  '220px',
  topBarHeight:      '56px',
  drawerWidth:       '420px',
  drawerWidthMobile: '100%',
  contentMaxWidth:   '1440px',
  dashboardMaxWidth: '1280px',

  // Breakpoints
  breakpointSm:  640,
  breakpointMd:  768,
  breakpointLg:  1024,
  breakpointXl:  1280,
  breakpoint2xl: 1536,
} as const;

export type ColorKey    = keyof typeof colors;
export type MotionTier  = 'marketing' | 'dashboard';

// ─────────────────────────────────────────────────────────────────────────────
// Framer Motion variant presets
// Import these in components instead of defining inline variants
// ─────────────────────────────────────────────────────────────────────────────
import { Variants, Transition } from 'framer-motion';

// ── Transitions ──────────────────────────────────────────────────────────────

export const transitionDefault: Transition = {
  ease: [0.4, 0, 0.2, 1],
  duration: 0.2,
};

export const transitionOutExpo: Transition = {
  ease: [0.16, 1, 0.3, 1],
  duration: 0.5,
};

export const transitionOutQuart: Transition = {
  ease: [0.25, 1, 0.5, 1],
  duration: 0.4,
};

export const transitionSpring = {
  type: 'spring' as const,
  stiffness: 400,
  damping: 30,
};

// ── Marketing — scroll reveal (section children fade up) ────────────────────

export const fadeUpVariants: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      ease: [0.16, 1, 0.3, 1],
      duration: 0.5,
    },
  },
};

export const fadeUpContainerVariants: Variants = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.08,
      delayChildren: 0.05,
    },
  },
};

// ── Marketing — hero headline character stagger ─────────────────────────────

export const heroCharVariants: Variants = {
  hidden: { opacity: 0, y: 40, skewY: 3 },
  visible: {
    opacity: 1,
    y: 0,
    skewY: 0,
    transition: {
      ease: [0.16, 1, 0.3, 1],
      duration: 0.75,
    },
  },
};

export const heroWordVariants: Variants = {
  hidden: { opacity: 0, y: 60 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: {
      ease: [0.16, 1, 0.3, 1],
      duration: 0.75,
      delay: i * 0.12,
    },
  }),
};

// ── Dashboard — drawer slide in from right ──────────────────────────────────

export const drawerVariants: Variants = {
  closed: { x: '100%', opacity: 0 },
  open: {
    x: 0,
    opacity: 1,
    transition: {
      ease: [0.16, 1, 0.3, 1],
      duration: 0.3,
    },
  },
};

// ── Dashboard — staggered list items (artifact cards, facts, etc.) ─────────

export const listContainerVariants: Variants = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.04,
    },
  },
};

export const listItemVariants: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      ease: [0.25, 1, 0.5, 1],
      duration: 0.25,
    },
  },
};

// ── Dashboard — status chip / badge pulse (running only) ───────────────────

export const pulseDotVariants: Variants = {
  idle: { opacity: 0.4, scale: 1 },
  pulse: {
    opacity: [0.4, 1, 0.4],
    scale: [1, 1.15, 1],
    transition: {
      duration: 1.6,
      repeat: Infinity,
      ease: 'easeInOut',
    },
  },
};

// ── Shared — command palette overlay ────────────────────────────────────────

export const overlayVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { duration: 0.15, ease: 'easeOut' },
  },
  exit: {
    opacity: 0,
    transition: { duration: 0.1, ease: 'easeIn' },
  },
};

export const commandPaletteVariants: Variants = {
  hidden: { opacity: 0, scale: 0.97, y: -8 },
  visible: {
    opacity: 1,
    scale: 1,
    y: 0,
    transition: {
      ease: [0.16, 1, 0.3, 1],
      duration: 0.2,
    },
  },
  exit: {
    opacity: 0,
    scale: 0.97,
    y: -8,
    transition: { duration: 0.12, ease: 'easeIn' },
  },
};

// ── Citation trace path draw ─────────────────────────────────────────────────

export const tracePathVariants: Variants = {
  hidden: { pathLength: 0, opacity: 0 },
  visible: {
    pathLength: 1,
    opacity: 1,
    transition: {
      pathLength: { ease: [0.16, 1, 0.3, 1], duration: 0.8 },
      opacity: { duration: 0.2 },
    },
  },
};

export const traceChipVariants: Variants = {
  hidden: { opacity: 0, scale: 0.8 },
  visible: {
    opacity: 1,
    scale: 1,
    transition: {
      ease: [0.16, 1, 0.3, 1],
      duration: 0.3,
      delay: 0.7,
    },
  },
};

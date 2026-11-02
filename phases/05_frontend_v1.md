# Traceform — Frontend UI/UX Design Prompt

**For:** a coding agent / design-engineer building the Traceform marketing site + operator dashboard
**Product source:** Traceform PRD v3.2
**Visual/motion inspiration:** [palominoprod.com](https://palominoprod.com/en) (Palomino Production — cinematic sports & brand film studio)
**Use:** paste this whole document as a single prompt, or split by the section breaks (marked `### PART`) if feeding a coding agent in stages.

---

## 0. What we're translating, and why it fits

Palomino is a film studio site — cinematic, kinetic, built on trust between brand and audience. Traceform is enterprise AI infrastructure — but its entire value proposition (§1.3 of the PRD) is also about **trust between a claim and its source**. That's the bridge: Palomino's site makes you *feel* premium craftsmanship before you see a single reel; Traceform's site and dashboard should make an operator *feel* verifiable precision before they see a single citation. Borrow Palomino's motion language (kinetic type, scroll-triggered reveals, counters, cinematic full-bleed hero, restrained testimonial trust-signals, a numbered "how it works" section) but replace its warm/emotional sports tone with a **cool, precise, editorial, "control-room" tone** — this is a compliance-grade tool, not a highlight reel.

Do not copy Palomino's literal content (sports, athletes, testimonials verbatim) — copy its **structural and motion patterns**, restyled for Traceform's domain (security/comms/policy operators, citation-backed AI, review pipelines).

---

## 1. Brand & Tone Direction

**Personality:** precise, calm, editorial, quietly confident. Not "AI hype" (no glowing gradients, no generic robot/neural-net imagery, no purple-blue SaaS gradient soup). Think: **investigative-journalism tooling meets air-traffic-control dashboard** — the visual register of something that verifies, cross-checks, and never lies to you about its own confidence.

**Core promise to visualize everywhere:** *every claim traces back to an exact place in the source.* This single idea should show up as a recurring visual motif — literal connecting lines/threads from a highlighted span of source text to the generated claim that came from it. This becomes the site's signature visual (its equivalent of Palomino's "frame by frame" cinematic imagery).

**Tone words:** traceable, verified, calm, exact, accountable, engineered — not: magical, revolutionary, effortless, futuristic.

**Reference-but-reroute list** (Palomino pattern → Traceform reroute):
- Palomino's full-bleed hero athlete photo → Traceform's hero is a **live-feeling animated diagram**: a document with a highlighted span, a thin animated line tracing to a generated sentence, a citation chip appearing with a confidence score. Motion, not stock photography.
- Palomino's kinetic two-word stacked headline ("SPORTS" / "INTO STORIES") → Traceform's hero headline: **"EVERY CLAIM" / "TRACED"** (or similar two-line kinetic lockup, see §3).
- Palomino's client-logo marquee → Traceform's **output-type marquee**: an infinite horizontal scroll of the nine artifact types (LinkedIn Post, Advisory, Executive Summary, Presentation, Infographic, Video Package, Newsletter, Press Release, Twitter/X) as small mono-style tags/icons, not brand logos (unless/until there are real customer logos to show).
- Palomino's "Selected Projects" hover-reveal grid → Traceform's **"Selected Transformations"**: a grid of source→artifact case examples, each hover-revealing a mini before/after (source excerpt → generated post) instead of a video still.
- Palomino's animated "Key Figures" counters → Traceform's counters pull directly from §3.8's evaluation framework: **Fact Accuracy %, Style Adherence %, Artifacts Generated, Avg Latency, Dataset Size** — counted up on scroll, exactly like Palomino's, but labeled honestly (small caption always states the eval-set size next to the number, per the PRD's own principle in §3.8/§10 — this is a brand-truthful easter egg: Traceform's own marketing site practices what the product preaches).
- Palomino's numbered "Services" alternating panels → Traceform's numbered **"How It Works"** panels mapped straight to the pipeline (§3.5): 1. Ingest, 2. Extract & Cite, 3. Generate in Parallel, 4. Review (Style/Fact/Compliance), 5. Deliver with Explainability.
- Palomino's testimonial carousel → Traceform's **"Trust Log"**: short, real-feeling operator quotes paired with a tiny inline stat chip (e.g. "Caught a mismatched figure before it went out.") — same visual rhythm as Palomino's testimonials, different substance.
- Palomino's closing CTA ("LET'S MAKE SOMETHING ICONIC") → Traceform's closing CTA: **"SEE THE CITATION."** or **"TRACE YOUR FIRST CLAIM."**

---

## 2. Visual System

### Color
- Base: near-black canvas (`#0A0B0D` or similar), not pure black — matches Palomino's cinematic dark backgrounds.
- Primary text: off-white (`#F3F3EF`), warm-neutral, not stark white — keeps the editorial paper-like feel.
- One accent color only, used sparingly and consistently for anything "traced"/"verified": a precise cool signal color — e.g. a calibrated cyan or amber (pick ONE; amber reads more "verification/highlighter," cyan reads more "system/technical" — recommend **amber `#F5A623`-family** for the citation-highlight motif specifically, since it visually reads as "highlighter pen on a source document," which is exactly the product's metaphor).
- Status colors (used ONLY inside the dashboard, never on marketing pages): pass = muted green, failed = muted red/rust, budget_exceeded = muted amber/grey, pending = neutral grey. Desaturated, not traffic-light-bright — this is a professional tool, not a game.
- Avoid: purple/blue AI-startup gradients, neon glows, glassmorphism blur-everything panels.

### Typography
- A geometric/grotesk sans for UI and body (e.g. in the family of Inter, Neue Montreal, or General Sans) — clean, technical, highly legible at small sizes for the dense dashboard views.
- A single large **display/kinetic typeface** for hero headlines and section numerals only — condensed, high-contrast, editorial (in the family of a tightly-tracked grotesk like Palomino's own stacked wordmark treatment). Used big, used rarely.
- Monospace accent font for anything literally representing data/citations: character offsets, confidence scores, prompt/model version strings, cost figures. This reinforces "exactness" the same way a timecode readout reinforces "this is really from the footage."

### Layout & Grid
- Marketing site: full-bleed sections, generous vertical rhythm (like Palomino's spacious scroll-driven sections), 12-col grid, content max-width ~1440px, edge padding scales with viewport.
- Dashboard: dense, information-forward, NOT full-bleed — this is a working tool. Left rail nav (Sources / Generations / History / Evaluation), main content area, right-side collapsible Explainability drawer (see §5).
- Consistent 8px spacing scale throughout both surfaces.

---

## 3. Marketing Site — Section-by-Section Spec

Build as a single scrolling homepage (Next.js), mirroring Palomino's information architecture:

### 3.1 Nav
Sticky, transparent-over-hero, solidifies to solid background on scroll (Palomino pattern). Logo left, links center/right: Product · How it Works · Trust & Security · Docs · Contact. Thin, all-caps, tracked-out nav labels — matches Palomino's `WORK / ABOUT / CONTACT` treatment.

### 3.2 Hero
- Kinetic two-line stacked headline, animates in on load (character or word stagger, ~600–900ms, easing like Palomino's — soft ease-out, no bounce): **"EVERY CLAIM" / "TRACED."**
- Subhead, one sentence, in body type: *"Turn one source into every format you need — with every generated sentence traced back to an exact span in the original."*
- Behind/around the headline: the animated citation-trace diagram described in §1 — subtle, looping, not distracting, rendered as SVG/canvas so it's crisp at any size.
- Primary CTA button: "See a Live Trace" (opens an interactive demo, not a generic "Get Started").

### 3.3 Output-Type Marquee
Infinite horizontal auto-scroll strip (Palomino's client-logo marquee pattern, duplicated seamlessly), showing the nine artifact types as small pill tags with icon + label, muted style, pauses on hover.

### 3.4 Selected Transformations
Grid (2–3 col responsive) of source→artifact examples. Each card: source domain tag (Threat Intel / Policy / News), a muted thumbnail of "source excerpt," on hover reveals a generated artifact preview with a visible citation-thread line connecting a highlighted phrase to the generated sentence — this is the site's core "wow" moment, replacing Palomino's hover-video-reveal. Link: "See all transformations."

### 3.5 Key Figures (animated counters, scroll-triggered)
Exactly like Palomino's numbered counter section, but content pulled straight from §3.8:
1. Fact Accuracy — e.g. "93%" — **with a persistent small caption directly beneath: "across a 20-source evaluation set" (never shown without this caption, by design principle, see §1)**
2. Style Adherence — e.g. "97%"
3. Avg. Cost per Artifact
4. Avg. Generation Latency
5. Output Types Supported — "9"
6. Reviewers per Artifact — "3, run concurrently"

### 3.6 How It Works (numbered alternating panels)
Five numbered sections, alternating image-left/text-right like Palomino's Services block, each with a short animated diagram (not a photo):
1. **Ingest** — any source, sensitivity-tagged, treated as untrusted data (a visual: a document being "sealed" into a data envelope, never touching the instruction channel)
2. **Extract & Cite** — knowledge extraction with visible character-offset citations
3. **Generate in Parallel** — nine artifact types fanning out simultaneously from one shared extraction
4. **Review, Concurrently** — three reviewer badges (Style / Fact / Compliance) lighting up together, one flagging a mismatch
5. **Deliver with Receipts** — the explainability panel sliding into view: citations, reviewer outcomes, cost, versions

Each panel: "See the docs" link, short services-style bullet list (mirroring Palomino's `SERVICES:` bullet block under each panel).

### 3.7 Trust & Security band
Not in Palomino's structure, but required given the PRD's emphasis (§3.1.1, §7) — a dedicated dark, minimal band: three columns — "Source content is data, never instructions" / "Every override is reasoned and logged" / "Sensitivity gates before generation" — small monospace supporting captions, no decoration. This is the section that makes security/compliance buyers trust the product; keep it sober, almost governmental in restraint.

### 3.8 Our Approach / Story
Palomino's "Our Story" pattern — one large image/diagram, short editorial paragraph on why traceability-first (not speed-first, not volume-first) is the design philosophy, referencing the deliberately deferred V2 features (§1.4) as evidence of discipline: *"We shipped citation-backed generation before cross-artifact consistency — because the second is a harder version of the first, and we don't ship things we haven't proven."*

### 3.9 Trust Log (testimonials)
Same rhythm as Palomino's testimonial carousel — quote, avatar-or-initials, name, role — but content should read like real operator feedback about specific catches (a caught fact mismatch, a flagged sensitivity conflict), not generic praise. Include a "See the generation" link on at least one, deep-linking to a real (or representative) explainability panel.

### 3.10 Closing CTA
Full-bleed, large kinetic type, same weight as Palomino's closing moment: **"TRACE YOUR FIRST CLAIM."** — single CTA button beneath.

### 3.11 Footer
Minimal, three columns like Palomino's (Info / Pages / Socials), plus a required Legal column (Terms, Security, Trust Center) given the compliance-heavy audience.

---

## 4. Motion & Transition Spec (the Palomino DNA, made literal)

This is the section to follow most precisely — Palomino's felt quality comes almost entirely from motion discipline, not decoration.

- **Smooth scroll:** implement inertial/smoothed scrolling (Lenis or equivalent) site-wide on the marketing pages so section transitions feel weighted, not default-browser-abrupt. Do NOT apply this inside the dashboard — operators need instant, native scroll for dense data tables.
- **Scroll-triggered reveals:** every section's content fades up + slightly translates on scroll-into-view (12–24px translate, 400–600ms, ease-out, slight stagger between child elements — headline first, then supporting text, then imagery/diagram). Use IntersectionObserver-driven triggers (Framer Motion `whileInView` or GSAP ScrollTrigger).
- **Counters:** animate count-up from 0 on first scroll-into-view only (not on every scroll pass), duration ~1.2–1.6s, ease-out-expo feel, matching Palomino's counter cadence.
- **Marquee:** true infinite CSS/JS marquee (duplicate content, translateX loop), pause-on-hover, consistent slow speed (not attention-grabbing fast).
- **Hover reveals (Selected Transformations grid):** on hover, image/thumbnail scales subtly (1.0 → 1.04, 400ms ease), overlay content (the citation-trace animation) fades/slides in; on touch devices, replace hover with a tap-to-reveal or always-visible compact state — don't hide critical info behind hover-only on mobile.
- **Nav behavior:** transparent over hero, solidifies with a soft background-blur/opacity transition once scrolled past hero height; hide-on-scroll-down / reveal-on-scroll-up for a cleaner reading experience on long pages (Palomino-style unobtrusive nav).
- **Page transitions (route changes, e.g. Home → How It Works → Docs):** a brief full-screen wipe/fade transition (250–400ms) between routes rather than a hard cut — consistent with Palomino's polished, produced feel. Keep it fast; this is a tool site, not a film reel — never let a transition exceed ~400ms or operators will feel friction.
- **Custom cursor (marketing pages only):** optional but recommended for the premium feel — a small dot cursor that expands into a ring or shows a contextual label ("View", "Play") when hovering interactive elements, exactly Palomino's pattern. Disable entirely on touch devices and inside the dashboard.
- **Citation-trace animation (signature motif):** a reusable animated component — a thin line draws (SVG stroke-dashoffset animation, ~800ms ease) from a highlighted span of source text to its corresponding generated sentence, ending in a small confidence-score chip fading in. Reuse this exact component in the hero, in Selected Transformations, in How It Works step 2, and inside the real dashboard's Explainability panel — this recurring motif is what visually unifies marketing and product, the way Palomino's "frame by frame" cinematic language unifies their reel and their site.
- **Reduced motion:** respect `prefers-reduced-motion` — fall back to simple opacity fades, no translate/scale, no marquee auto-scroll (pause by default), no custom cursor.

---

## 5. Product Dashboard — UI/UX Spec (§3.10 of the PRD, made concrete)

The dashboard is a different register from the marketing site: dense, fast, no scroll-linked motion, no marquee, no custom cursor — but it inherits the **color system, typography, and the citation-trace component** so the product feels like the continuation of the site's promise, not a bait-and-switch into generic SaaS-admin styling.

### 5.1 Layout
Left rail (icon + label nav: Sources, Generations, History, Evaluation, Settings) · top bar (search, API key/org switcher, operator avatar) · main content area · collapsible right-side Explainability drawer that slides in per-artifact (not a modal — operators need to compare artifact and explainability side by side).

### 5.2 Source Upload / Generation Setup screen
- Drag-and-drop source panel (text/PDF/DOCX/image/video-attach) with a live extracted-text preview once processed.
- Sensitivity selector: prominent segmented control (Public/Internal/Restricted/Confidential) with the classifier's suggestion shown as a **secondary, clearly-labeled ghost chip** next to the operator's actual selection ("Classifier suggests: Internal (81% confidence)") — never pre-filled silently, matching §3.1.1's provenance requirement visually.
- Output-type multi-select: the same pill-tag style as the marketing marquee, now interactive/selectable — visual continuity with the marketing site's output-type marquee.
- Parameter form (audience/tone/language/detail/objective/style): global fields with a small "override per output type" expandable section per selected type.

### 5.3 Generation Status / Pipeline view
Live status view mirroring §3.5's pipeline diagram — a horizontal stepper (Ingest → Extract → Generate ×N in parallel → Review ×3 in parallel → Assemble → Deliver), each stage showing real-time state (queued/running/done/failed) with subtle, non-distracting pulse animation only on the active stage — no bouncing, no confetti. Parallel stages render as a small fan-out cluster of nodes, not a flat list, so the concurrency (the PRD's core performance claim) is visually legible.

### 5.4 Artifact Result view + Explainability & Cost panel (§3.7 — the centerpiece)
This is the dashboard's signature screen and should directly reuse the citation-trace component:
- Left: the rendered artifact content.
- Right drawer: **Facts Used** (each with the citation-trace line back to a source-span excerpt, confidence score in monospace), **Reviewer Outcomes** (three status chips — Style/Fact/Compliance — pass/fail/regenerated, expandable to show the regeneration diff for Fact Reviewer's bounded retry), **Cost & Tokens** (small breakdown table, monospace figures), **Versions** (prompt/model/reviewer version strings), **Sensitivity Provenance** (operator vs. classifier, with any Compliance Override reason shown inline, timestamped).
- A `review_status: failed` artifact must be visually distinct at the artifact-card level (not just inside the drawer) — a clear, sober "Needs Review" state, never disguised as a pass.
- `budget_exceeded` artifacts show a distinct empty-state card with a one-click "Re-run this type" action (§4's fresh-budget rerun).

### 5.5 History & Evaluation views
- History: filterable table (status, output type, date, sensitivity) — dense, sortable, no unnecessary motion.
- Evaluation: reuses the marketing site's Key Figures counter component exactly, but live and drillable — clicking a metric shows the per-source breakdown. The dataset-size caption rule from §3.5 applies here too, non-negotiably.

### 5.6 Compliance Override flow
A deliberate, slightly "heavier" interaction than the rest of the dashboard (by design — this should feel like it matters): a confirmation panel requiring a typed reason, showing exactly what will be logged and to whom it's attributed, before the override can be submitted. No dark patterns, no pre-filled reason text.

---

## 6. Component & Design-Token Recommendations

- Build as a token-driven system (CSS variables or a Tailwind config extension) so marketing and dashboard share the same base palette/type scale/spacing but the dashboard disables the "cinematic" motion tokens (marquee-speed, hero-kinetic-duration, custom-cursor) entirely via a `motion-tier` context.
- Recommended stack: **Next.js**, **Tailwind CSS** for utility styling, **Framer Motion** for component-level animation (reveals, drawer, counters), **GSAP + ScrollTrigger** or **Lenis** for the marketing site's smooth-scroll/scroll-driven sequences specifically (Palomino's own site is built this way), **Radix UI primitives** for accessible dashboard components (drawer, segmented control, tabs) styled to match the token system rather than default Radix theming.
- The citation-trace component should be built once as a standalone SVG/React component with props for `sourceSpanRect`, `targetChipRect`, `confidence`, and `status` (verified/failed/pending) so it can be dropped into hero, marketing cards, and the real dashboard drawer without duplication.

---

## 7. Accessibility & Performance Constraints

- All motion must respect `prefers-reduced-motion` (§4).
- Color contrast: body text on dark background must meet WCAG AA at minimum; the amber accent must never be the sole carrier of meaning (status chips get icon + text, not color alone) — critical given this is a compliance tool likely to be screen-read by some operators.
- Dashboard must be fully usable via keyboard (drawer focus-trapping, stepper navigable, table sortable via keyboard) — no motion-only affordances for critical actions like the Compliance Override flow.
- Marketing site: lazy-load below-the-fold imagery/animations; the citation-trace SVG component should be lightweight (no heavy canvas/WebGL) so the hero loads fast — Palomino's site earns its cinematic feel through timing discipline, not asset weight, and Traceform should do the same.
- Dashboard must load and be interactive fast on a typical operator's corporate laptop — no smooth-scroll libraries, no marquees, no route-transition wipes inside the app shell; save the "produced" feeling for the marketing site only.

---

## 8. What NOT to do

- Don't turn the dashboard into a marketing-site clone — operators doing real compliance work need speed and density, not kinetic type.
- Don't use generic AI-SaaS visual clichés (glowing orbs, purple gradients, floating 3D shapes, robot mascots) — everything should visually earn its place by representing something real in the pipeline (a citation, a review status, a cost figure).
- Don't let any evaluation number appear without its dataset-size caption, anywhere in the product — this is a stated brand principle carried over from the PRD (§3.8, §10), not just a UI nicety.
- Don't hide the classifier-vs-operator sensitivity distinction behind a tooltip — it must be visible at a glance, per §3.1.1's "never a silent trust boundary" requirement.

---

## 9. Deliverable expectations for the build

Produce, in order:
1. Design tokens file (colors, type scale, spacing, motion durations/easings, tagged by `motion-tier: marketing | dashboard`).
2. The reusable citation-trace component, built and demoed in isolation before it's used anywhere else.
3. Marketing homepage, section by section per §3, each section's scroll-reveal wired per §4.
4. Dashboard shell (nav, top bar, drawer scaffold) per §5.1.
5. Source Upload/Generation Setup screen (§5.2).
6. Pipeline status view (§5.3).
7. Artifact Result + Explainability drawer (§5.4) — this is the highest-priority dashboard screen; treat it as the centerpiece deliverable, same weight Palomino gives its Selected Projects grid.
8. History, Evaluation, Compliance Override flow (§5.5–5.6).

Reference `palominoprod.com/en` directly for pacing/timing calibration during build (section reveal timing, marquee speed, counter duration) — but no imagery, copy, or literal layout should be reused; only the motion and structural rhythm.
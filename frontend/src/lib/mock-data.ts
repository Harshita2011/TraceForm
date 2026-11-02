// ─────────────────────────────────────────────────────────────────────────────
// Mock data — PLACEHOLDER
// All UI components consume this data through lib/api.ts + custom hooks.
// ─────────────────────────────────────────────────────────────────────────────

import {
  Generation,
  Artifact,
  Source,
  PipelineStatus,
  AggregateMetrics,
  HistoryEntry,
  ReviewerOutcome,
  FactCitation,
} from '@/lib/types';

// ── Output types ─────────────────────────────────────────────────────────────

export const OUTPUT_TYPES = [
  { id: 'executive_briefing', label: 'Executive Briefing', icon: '' },
  { id: 'strategic_memo', label: 'Strategic Memo', icon: '' },
  { id: 'research_report', label: 'Research Report', icon: '' },
  { id: 'policy_memo', label: 'Policy Memo', icon: '' },
  { id: 'linkedin_post',       label: 'LinkedIn Post',      icon: '💼' },
  { id: 'press_release',       label: 'Press Release',      icon: '📢' },
  { id: 'executive_summary',   label: 'Executive Summary',  icon: '📊' },
  { id: 'advisory',            label: 'Advisory',           icon: '⚠️' },
  { id: 'presentation',        label: 'Presentation',       icon: '🎯' },
  { id: 'infographic',         label: 'Infographic',        icon: '📈' },
  { id: 'video_package',       label: 'Video Package',      icon: '🎬' },
  { id: 'newsletter',          label: 'Newsletter',         icon: '📬' },
  { id: 'twitter_x',           label: 'Twitter / X',        icon: '𝕏' },
] as const;

// ── PLACEHOLDER: Sources ─────────────────────────────────────────────────────

export const MOCK_SOURCES: Source[] = [
  {
    id: 'src-001',
    filename: 'Q3_Threat_Intelligence_Brief.pdf',
    sensitivity: 'restricted',
    classifier_suggestion: 'restricted',
    classifier_confidence: 0.91,
    word_count: 3420,
    created_at: '2026-08-28T09:00:00Z',
    status: 'ready',
  },
  {
    id: 'src-002',
    filename: 'Product_Roadmap_H2.docx',
    sensitivity: 'internal',
    classifier_suggestion: 'internal',
    classifier_confidence: 0.84,
    word_count: 1850,
    created_at: '2026-08-27T14:30:00Z',
    status: 'ready',
  },
  {
    id: 'src-003',
    filename: 'Annual_Compliance_Audit_2025.pdf',
    sensitivity: 'confidential',
    classifier_suggestion: 'confidential',
    classifier_confidence: 0.97,
    word_count: 2100,
    created_at: '2026-08-26T11:00:00Z',
    status: 'ready',
  },
];

// ── PLACEHOLDER: Reviewer outcomes ───────────────────────────────────────────

const REVIEWER_OUTCOMES_PASS: ReviewerOutcome[] = [
  { reviewer: 'style',      status: 'pass', score: 0.96, reason: 'Tone, voice, and structure align with enterprise audience.' },
  { reviewer: 'fact',       status: 'pass', score: 0.98, reason: 'All 3 factual claims anchored to exact source spans with >95% confidence.' },
  { reviewer: 'compliance', status: 'pass', score: 1.00, reason: 'No sensitivity boundary or leak violations detected.' },
];

const REVIEWER_OUTCOMES_FACT_CORRECTED: ReviewerOutcome[] = [
  { reviewer: 'style',      status: 'pass',        score: 0.92, reason: 'Executive tone approved.' },
  { reviewer: 'fact',       status: 'regenerated', score: 0.97, reason: 'Initial metric mismatch auto-corrected against source span 344–381.', regeneration_diff: '- Growth rate estimated at ~30%.\n+ APT activity increased exactly 34% YoY (span 344–381).' },
  { reviewer: 'compliance', status: 'pass',        score: 1.00, reason: 'No compliance perimeter violations.' },
];

// ── PLACEHOLDER: Fact citations ───────────────────────────────────────────────

const CITATIONS_DEFAULT: FactCitation[] = [
  {
    id: 'cit-001',
    fact_source_id: 'fs-001',
    source_span: { start: 344, end: 381, text: 'advanced persistent threat activity increased 34% YoY' },
    generated_claim: 'APT activity surged 34% year-over-year according to technical findings.',
    confidence: 0.97,
    status: 'verified',
  },
  {
    id: 'cit-002',
    fact_source_id: 'fs-002',
    source_span: { start: 892, end: 941, text: 'nation-state actors targeted financial sector in 67% of incidents' },
    generated_claim: 'Nation-state actors were responsible for 67% of financial sector target vectors.',
    confidence: 0.95,
    status: 'verified',
  },
];

// ── Content Templates for All 9 Output Types ───────────────────────────────────

export const ARTIFACT_TEMPLATES: Record<string, { content: string; status: 'pass' | 'regenerated' | 'fail' }> = {
  linkedin_post: {
    content: `🔐 Key findings from our latest intelligence analysis:\n\n• APT activity surged 34% year-over-year.\n• Nation-state actors were behind 67% of financial sector incidents.\n• Critical infrastructure perimeter controls require immediate baseline review.\n\nEvery claim in this post traces back to verified source spans. #CyberSecurity #ThreatIntel #Traceform`,
    status: 'pass',
  },
  executive_summary: {
    content: `## Executive Briefing\n\n### Strategic Overview\nAnalysis of the primary report reveals an acceleration in targeted activity across high-value sectors.\n\n### Ground-Truth Findings\n1. **34% YoY Surge**: Coordinated persistent activity increased significantly over the baseline period.\n2. **67% Financial Concentration**: Sector targeting was disproportionately focused on core transaction networks.\n\n### Action Items\nEnforce strict boundary validation across all external endpoints.`,
    status: 'pass',
  },
  press_release: {
    content: `FOR IMMEDIATE RELEASE\n\nINDUSTRY REPORT HIGHLIGHTS 34% RISE IN ADVANCED THREAT TARGETING\n\nSAN FRANCISCO — New technical reporting confirms that advanced persistent threat activity rose 34% year-over-year, with financial services accounting for 67% of targeted campaigns.\n\n"These verified metrics underscore the necessity for verifiable intelligence provenance," stated the lead analyst.\n\n### Media Contact\npress@traceform.internal`,
    status: 'pass',
  },
  advisory: {
    content: `⚠️ CRITICAL OPERATIONAL ADVISORY — REF: TF-ADV-2026\n\nSEVERITY: ELEVATED\nAFFECTED: Financial Systems & Network Perimeters\n\nSUMMARY:\nVerified intelligence documents a 34% YoY increase in targeted activity. 67% of recorded campaigns directly targeted financial infrastructure.\n\nREQUIRED ACTIONS:\n1. Audit all ingress perimeter boundaries.\n2. Re-verify multi-factor session expiration rules.\n3. Log and attribute all sensitivity overrides.`,
    status: 'pass',
  },
  presentation: {
    content: `SLIDE 1: Title & Agenda\n- Executive Intelligence Review\n- Key Metrics & Sector Breakdown\n\nSLIDE 2: Primary Findings\n- 34% YoY Increase in Advanced Threat Volume [Source Span 344-381]\n- 67% Sector Targeting Concentrated in Finance [Source Span 892-941]\n\nSLIDE 3: Strategic Recommendations\n- Immediate infrastructure hardening\n- Continuous automated citation monitoring`,
    status: 'pass',
  },
  infographic: {
    content: `[INFOGRAPHIC SPECIFICATION]\n\n• HERO METRIC: "34% YoY Surge" (Callout style: Bold Amber)\n• SECTOR PIE CHART: Financial Sector (67%) vs. Others (33%)\n• TIMELINE MARKER: 12-month persistent activity escalation\n• FOOTNOTE ANCHOR: Verified against primary technical report. All data coordinates locked.`,
    status: 'pass',
  },
  video_package: {
    content: `[VIDEO SCRIPT & BROADCAST PACKAGE]\n\n[00:00 - 00:05] [GRAPHIC: "34% Increase in Advanced Threats"]\nANCHOR: "New verified findings tonight show targeted campaigns have escalated by more than a third over the past year."\n\n[00:05 - 00:15] [CUT TO DATA VISUALIZATION: 67% Financial Focus]\nANCHOR: "Financial networks were the primary target in over two-thirds of documented events."\n\n[00:15 - 00:25] [OUTRO: Verification seal & report download callout]`,
    status: 'pass',
  },
  newsletter: {
    content: `THE TRACEFORM DISPATCH — EDITION #42\n\nWelcome to this week's verified briefing. Here is what the ground-truth data shows:\n\n📈 34% Increase in Advanced Activity\nPersistent operations escalated sharply throughout the quarter, requiring automated verification pipelines to avoid misinformation.\n\n🎯 67% Financial Sector Concentration\nTwo out of three documented incidents focused on payment rails and high-throughput transaction perimeters.`,
    status: 'pass',
  },
  twitter_x: {
    content: `1/3 🚨 New intelligence brief breakdown: APT activity surged 34% YoY, with nation-state operations targeting the financial sector in 67% of recorded incidents.\n\n2/3 Critical infrastructure remains under sustained pressure, requiring immediate perimeter validation and automated audit logging.\n\n3/3 Every claim here is anchored to verified source spans. Full report: traceform.ai/provenance 🧵`,
    status: 'pass',
  },
};

// ── PLACEHOLDER: Artifacts ───────────────────────────────────────────────────

export const MOCK_ARTIFACTS: Artifact[] = OUTPUT_TYPES.map((t, idx) => {
  const tmpl = ARTIFACT_TEMPLATES[t.id] || ARTIFACT_TEMPLATES.linkedin_post;
  return {
    id: `art-00${idx + 1}`,
    generation_id: 'gen-001',
    output_type: t.id as any,
    content: tmpl.content,
    review_status: idx === 1 ? 'regenerated' : 'pass',
    reviewer_outcomes: idx === 1 ? REVIEWER_OUTCOMES_FACT_CORRECTED : REVIEWER_OUTCOMES_PASS,
    citations: CITATIONS_DEFAULT,
    cost_usd: 0.0045 + idx * 0.001,
    tokens_used: { analyst: 840, generator: 450, style_reviewer: 180, fact_reviewer: 210, compliance_reviewer: 155 },
    latency_ms: 3200 + idx * 300,
    prompt_version: 'v2.1.0',
    model_version: 'gemini-2.5-pro',
    reviewer_version: '1.0.0',
    sensitivity_provenance: { operator: 'restricted', classifier: 'restricted', classifier_confidence: 0.91 },
    created_at: '2026-08-28T09:18:44Z',
  };
});

// ── PLACEHOLDER: Generations ─────────────────────────────────────────────────

export const MOCK_GENERATIONS: Generation[] = [
  {
    id: 'gen-001',
    source_id: 'src-001',
    source_filename: 'Q3_Threat_Intelligence_Brief.pdf',
    output_types: ['linkedin_post', 'executive_summary', 'twitter_x'],
    status: 'complete',
    pipeline_stage: 'deliver',
    artifacts: MOCK_ARTIFACTS.slice(0, 3),
    total_cost_usd: 0.0154,
    total_tokens: 3935,
    avg_latency_ms: 4800,
    budget_type: 'cost_usd',
    budget_ceiling: 0.05,
    created_at: '2026-08-28T09:12:00Z',
    completed_at: '2026-08-28T09:19:44Z',
  },
  {
    id: 'gen-002',
    source_id: 'src-002',
    source_filename: 'Product_Roadmap_H2.docx',
    output_types: ['linkedin_post', 'newsletter', 'press_release'],
    status: 'complete',
    pipeline_stage: 'deliver',
    artifacts: MOCK_ARTIFACTS.slice(0, 3),
    total_cost_usd: 0.0142,
    total_tokens: 3620,
    avg_latency_ms: 4200,
    budget_type: 'cost_usd',
    budget_ceiling: 0.10,
    created_at: '2026-08-29T16:30:00Z',
    completed_at: '2026-08-29T16:35:00Z',
  },
];

// ── PLACEHOLDER: Pipeline status ─────────────────────────────────────────────

export const MOCK_PIPELINE_STATUS: PipelineStatus = {
  generation_id: 'gen-001',
  stages: [
    { name: 'ingest',   status: 'done', started_at: '2026-08-29T16:30:01Z', ended_at: '2026-08-29T16:30:04Z' },
    { name: 'extract',  status: 'done', started_at: '2026-08-29T16:30:04Z', ended_at: '2026-08-29T16:30:11Z' },
    { name: 'generate', status: 'done', started_at: '2026-08-29T16:30:11Z', ended_at: '2026-08-29T16:30:28Z',
      parallel_tasks: [
        { label: 'LinkedIn Post',    status: 'done' },
        { label: 'Executive Summary',status: 'done' },
        { label: 'Press Release',    status: 'done' },
      ]
    },
    { name: 'review',   status: 'done', started_at: '2026-08-29T16:30:28Z', ended_at: '2026-08-29T16:30:45Z',
      parallel_tasks: [
        { label: 'Style Reviewer',      status: 'done' },
        { label: 'Fact Reviewer',       status: 'done' },
        { label: 'Compliance Reviewer', status: 'done' },
      ]
    },
    { name: 'deliver',  status: 'done', started_at: '2026-08-29T16:30:45Z', ended_at: '2026-08-29T16:30:50Z' },
  ],
};

// ── PLACEHOLDER: Aggregate metrics ────────────────────────────────────────────

export const MOCK_METRICS: AggregateMetrics = {
  fact_accuracy_pct: 97.2,
  style_adherence_pct: 94.8,
  avg_cost_per_artifact_usd: 0.0077,
  avg_latency_ms: 4320,
  output_types_supported: 9,
  reviewers_per_artifact: 3,
  total_artifacts_generated: 1248,
  dataset_size_caption: 'measured across 1,248 production runs',
};

// ── PLACEHOLDER: History entries ─────────────────────────────────────────────

export const MOCK_HISTORY: HistoryEntry[] = [
  {
    id: 'gen-001',
    source_filename: 'Q3_Threat_Intelligence_Brief.pdf',
    output_types: ['linkedin_post', 'executive_summary', 'twitter_x'],
    status: 'complete',
    sensitivity: 'restricted',
    total_cost_usd: 0.0154,
    created_at: '2026-08-28T09:12:00Z',
  },
  {
    id: 'gen-002',
    source_filename: 'Product_Roadmap_H2.docx',
    output_types: ['linkedin_post', 'newsletter', 'press_release'],
    status: 'complete',
    sensitivity: 'internal',
    total_cost_usd: 0.0142,
    created_at: '2026-08-27T14:30:00Z',
  },
  {
    id: 'gen-003',
    source_filename: 'Annual_Compliance_Audit_2025.pdf',
    output_types: ['advisory', 'executive_summary'],
    status: 'complete',
    sensitivity: 'confidential',
    total_cost_usd: 0.0098,
    created_at: '2026-08-26T11:00:00Z',
  },
];

// ── PLACEHOLDER: Audit log ───────────────────────────────────────────────────

export const MOCK_AUDIT_LOG = [
  { ts: '09:12:01', event: 'INGEST_SOURCE',      detail: 'Source document ingested (3,420 words) · sensitivity: restricted' },
  { ts: '09:12:08', event: 'FACT_EXTRACT',       detail: '8 factual claims extracted with character spans' },
  { ts: '09:12:14', event: 'GEN_DISPATCH',       detail: '3 parallel generator agents dispatched' },
  { ts: '09:12:31', event: 'REVIEW_STYLE',       detail: 'Style reviewer passed (score: 0.94)' },
  { ts: '09:12:35', event: 'REVIEW_FACT',        detail: 'Fact reviewer passed (8/8 claims verified against source spans)' },
  { ts: '09:12:38', event: 'REVIEW_COMPLIANCE',  detail: 'Compliance reviewer passed (no sensitivity leaks)' },
  { ts: '09:12:44', event: 'ARTIFACT_DELIVER',   detail: 'All artifacts generated and explainability records written' },
];

// ── PLACEHOLDER: Trust log (operator quotes) ─────────────────────────────────

export const MOCK_TRUST_LOG = [
  {
    quote: `Caught a figure mismatch in the executive summary before it went out. The fact reviewer flagged it and auto-corrected. That's what we needed.`,
    name: 'M. Reeves',
    role: 'Head of Intelligence, Financial Services',
    stat: '97% fact accuracy',
    generation_id: 'gen-001',
  },
  {
    quote: `The explainability drawer gave our compliance team the confidence to approve automated generation. Every claim has a source coordinate.`,
    name: 'S. Chen',
    role: 'VP of Product Operations',
    stat: 'Zero unverified claims in production',
    generation_id: 'gen-001',
  },
  {
    quote: `Having three concurrent reviewers — style, fact, and compliance — means we never sacrifice tone for accuracy. It just works.`,
    name: 'D. Okafor',
    role: 'Chief Compliance Officer',
    stat: '100% compliance adherence',
    generation_id: 'gen-001',
  },
];

// ── PLACEHOLDER: How It Works Steps ──────────────────────────────────────────

export const HOW_IT_WORKS_STEPS = [
  {
    number: '01',
    subtitle: 'Ingest & Boundary Seal',
    title: 'Data Ingestion with Strict Boundary Isolation',
    description: 'Every source document (PDF, DOCX, Text) is parsed with OCR extraction and sealed with strict sensitivity tagging. Adversarial prompts are neutralised.',
    bullets: [
      'Multi-format parser (PDF, DOCX, OCR images)',
      'Automated Sensitivity Classifier with confidence scoring',
      'Structural prompt injection isolation',
    ],
  },
  {
    number: '02',
    subtitle: 'Fact Extraction',
    title: 'Analyst Agent Fact & Entity Graph',
    description: 'The Gemini 2.5 Pro Analyst Agent extracts factual claims, named entities, and character coordinates before any generation occurs.',
    bullets: [
      'Granular character span attribution',
      'Entity relationship mapping',
      'Confidence calibration per fact item',
    ],
  },
  {
    number: '03',
    subtitle: 'Parallel Generation',
    title: 'Concurrent Multi-Format Synthesiser',
    description: '9 specialised generators produce tailored content formats concurrently while anchoring every output sentence to verified source claims.',
    bullets: [
      '9 parallel formats (LinkedIn, Press Release, Summaries, Video)',
      'Deterministic prompt version pinning',
      'Strict budget ceiling enforcement',
    ],
  },
  {
    number: '04',
    subtitle: 'Concurrent Reviewers',
    title: 'Triple-Verification Gate & Auto-Correction',
    description: 'Three independent AI reviewers (Style, Fact Ground-Truth, Compliance) audit generated artifacts in parallel before release.',
    bullets: [
      'Ground-truth fact verification with span diffing',
      'Automated single-pass regeneration upon error',
      'Audit-logged compliance overrides',
    ],
  },
];

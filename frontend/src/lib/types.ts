// ─────────────────────────────────────────────────────────────────────────────
// Shared TypeScript types
// Single canonical type definitions used by API client, hooks, and all components
// ─────────────────────────────────────────────────────────────────────────────

export type Sensitivity = 'public' | 'internal' | 'restricted' | 'confidential';

export type OutputType =
  | 'executive_briefing'
  | 'executive_summary'
  | 'press_release'
  | 'linkedin_post'
  | 'strategic_memo'
  | 'advisory'
  | 'research_report'
  | 'policy_memo'
  | 'presentation'
  | 'infographic'
  | 'video_package'
  | 'newsletter'
  | 'twitter_x';

export type ReviewStatus = 'pass' | 'fail' | 'regenerated' | 'budget_exceeded' | 'pending';
export type PipelineStage = 'ingest' | 'extract' | 'generate' | 'review' | 'deliver';
export type StageStatus = 'queued' | 'running' | 'done' | 'failed';
export type GenerationStatus = 'pending' | 'queued' | 'running' | 'complete' | 'completed' | 'partial_failure' | 'failed' | 'budget_exceeded' | 'cancelled';
export type BudgetType = 'tokens' | 'cost_usd';
export type CitationStatus = 'verified' | 'failed' | 'pending';
export type ReviewerName = 'style' | 'fact' | 'compliance' | 'format' | 'evidence' | 'specialist' | 'correction';
export type ReviewerStatus = 'pass' | 'fail' | 'regenerated';
export type SourceStatus = 'uploading' | 'processing' | 'ready' | 'failed' | 'reference_only' | 'removed';

// ── Quality Score Breakdown ───────────────────────────────────────────────────

export interface QualityScoreBreakdown {
  format_compliance: number;
  citation_coverage: number;
  review_pass_rate: number;
  readability: number;
  composite_score: number;
}

export interface FormatSpecificMeta {
  headline?: string;
  subheadline?: string;
  quote?: string;
  hook?: string;
  hashtags?: string[];
  recommendations?: string[];
  risks?: string[];
  risk_level?: string;
  strategic_impact?: string;
  [key: string]: any;
}

// ── Source ────────────────────────────────────────────────────────────────────

export interface Source {
  id: string;
  filename: string;
  sensitivity: Sensitivity;
  classifier_suggestion: Sensitivity | null;
  classifier_confidence: number | null; // 0–1; null when not recorded
  word_count: number;
  created_at: string;
  status: SourceStatus;
  sensitivity_source?: string;
  content_type?: string | null;
  extraction_method?: string;
  was_truncated?: boolean;
  generation_count?: number;
  can_delete?: boolean;
  deleted_at?: string | null;
}

// ── Fact Citation ─────────────────────────────────────────────────────────────

export interface SourceSpan {
  start: number;
  end: number;
  text: string;
}

export interface FactCitation {
  id: string;
  fact_source_id: string;
  source_span: SourceSpan;
  generated_claim: string;
  artifact_section?: string;
  confidence: number | null; // 0–1; null when not recorded
  status: CitationStatus;
}

// ── Reviewer Outcome ──────────────────────────────────────────────────────────

export interface ReviewerOutcome {
  reviewer: ReviewerName;
  status: ReviewerStatus | 'pass';
  score: number | null; // 0–1; null when not measured
  reason: string;
  regeneration_diff?: string;
  blocking?: boolean;
}

export interface EvidenceSpan { start: number; end: number }
export interface EvidenceAnchor {
  filename?: string | null;
  id: string; source_id: string | null; source_version: string; text: string;
  start: number | null; end: number | null; status: 'matched' | 'invalid'; reason: string | null;
  resolution?: string; model_start?: number | null; model_end?: number | null;
}
export interface EvidenceClaim {
  id: string; claim: string; kind: 'fact' | 'calculation' | 'recommendation' | 'unsupported';
  output_spans: EvidenceSpan[]; anchors: EvidenceAnchor[]; status: 'matched' | 'invalid'; reasons: string[];
  calculation?: { operation: string; inputs: string[]; result: string };
}
export interface EvidenceFinding {
  id: string; reviewer: string; claim: string; message: string; output_spans: EvidenceSpan[]; claim_id: string | null;
}
export interface EvidenceReport {
  version: string; source_id: string | null; source_version: string; content_version: string; passed: boolean;
  claims: EvidenceClaim[]; findings: EvidenceFinding[]; anchors_matched: number; anchors_total: number; limitation: string;
  source_documents?: SourceDocument[];
}
export interface ReviewContext {
  can_override: boolean;
  events: { id: string; event: string; operator: string; created_at: string; details: Record<string, unknown> }[];
}

// ── Sensitivity Provenance ────────────────────────────────────────────────────

export interface SensitivityProvenance {
  operator: Sensitivity;
  classifier: Sensitivity;
  classifier_confidence: number;
  override_reason?: string;
  override_by?: string;
  override_at?: string;
}

// ── Artifact ──────────────────────────────────────────────────────────────────

export interface TokenUsage {
  analyst?: number;
  generator?: number;
  style_reviewer?: number;
  fact_reviewer?: number;
  compliance_reviewer?: number;
  [key: string]: number | undefined;
}

export interface Artifact {
  id: string;
  generation_id: string;
  output_type: OutputType;
  content: string;
  review_status: ReviewStatus;
  reviewer_outcomes: ReviewerOutcome[];
  citations: FactCitation[];
  cost_usd: number;
  tokens_used: TokenUsage;
  latency_ms: number | null;
  prompt_version: string;
  model_version: string;
  reviewer_version: string;
  sensitivity_provenance: SensitivityProvenance;
  created_at: string;
  evidence?: EvidenceReport;
  assurance_status?: 'checks_passed' | 'needs_review' | 'unreviewed' | 'overridden';
  compliance_override?: { reason: string; operator_id: string; created_at: string; applies_to_current_content: boolean } | null;
  feedback?: { rating: string; comment?: string } | null;
  review_attempts?: { attempt: number; content_version: string; checks: { reviewer_name: string; passed: boolean; details?: Record<string, unknown> }[] }[];
  // Phase X Extensions
  blueprint_version?: string;
  purpose?: string;
  target_audience?: string;
  decision_focus?: string;
  key_insights?: string[];
  quality_score?: number;
  quality_breakdown?: QualityScoreBreakdown;
  format_meta?: FormatSpecificMeta;
  role?: string;
  audience?: string;
  writing_style?: string;
  differentiation_score?: number;
  uniqueness_score?: number;
  is_generic?: boolean;
}

export interface OutputDraft { content: string; revision: number; base_hash: string; updated_at: string | null }
export interface OutputWorkspaceState { owner: string; original_hash: string; draft: OutputDraft }
export interface OutputVersionMeta { id: string; label: string; origin: string; content_hash: string; source_hash: string; parent_id: string | null; created_at: string }
export interface OutputVersion extends OutputVersionMeta { content: string; sections: {id: string; title: string; level: number}[]; artifact: Artifact; review_id: string | null }
export interface OutputVersionTask { job_id: string; version_id: string; operation: 'review' | 'full' | 'section'; result_version_id: string | null; job: {status: string; message: string | null; can_cancel: boolean; budget_type: string; budget_used: number; budget_ceiling: number; uncertain_calls: number; usage_incomplete: boolean} }

// ── Pipeline Stage ────────────────────────────────────────────────────────────

export interface ParallelTask {
  label: string;
  status: StageStatus;
}

export interface PipelineStageState {
  name: PipelineStage;
  status: StageStatus;
  started_at: string | null;
  ended_at: string | null;
  parallel_tasks?: ParallelTask[];
}

export interface PipelineStatus {
  generation_id: string;
  stages: PipelineStageState[];
  error?: string | null;
  job?: JobInfo | null;
}

export interface JobInfo {
  status: string; attempts: number; message: string | null;
  cancel_requested: boolean; can_cancel: boolean; worker_online: boolean;
  heartbeat_at: string | null; configuration_id: string; provider: string; model: string;
  pricing: { input: number; output: number; origin: string; version: string };
  reserved_budget: number; budget_used: number; budget_ceiling: number | null;
  budget_type: BudgetType; budget_overrun: boolean; uncertain_calls: number;
  call_count: number; usage_incomplete: boolean; extraction_reused: boolean;
}

export interface ProviderSettings {
  revision: number; provider: 'gemini' | 'anthropic'; model: string;
  key_configured: boolean; pricing: JobInfo['pricing']; applies_to: string;
  worker_online?: boolean; can_edit?: boolean;
}
export interface ProviderUpdate {
  expected_revision: number; provider: ProviderSettings['provider']; model: string;
  api_key?: string; clear_key: boolean; input_per_million: number; output_per_million: number;
}

// ── Generation ────────────────────────────────────────────────────────────────

export interface Generation {
  id: string;
  source_id: string;
  source_filename?: string;
  source_documents?: SourceDocument[];
  source_conflicts?: SourceConflict[];
  output_types: OutputType[];
  status: GenerationStatus;
  pipeline_stage?: PipelineStage;
  artifacts: Artifact[];
  total_cost_usd: number;
  total_tokens: number;
  avg_latency_ms?: number;
  model_version?: string;
  prompt_version?: string;
  budget_type: BudgetType;
  budget_ceiling: number;
  created_at: string;
  completed_at?: string | null;
}

// ── History ───────────────────────────────────────────────────────────────────

export interface HistoryEntry {
  id: string;
  source_filename: string;
  output_types: OutputType[];
  status: GenerationStatus;
  sensitivity: Sensitivity;
  total_cost_usd: number;
  created_at: string;
}

// ── Metrics ───────────────────────────────────────────────────────────────────

export interface AggregateMetrics {
  fact_accuracy_pct: number | null;
  style_adherence_pct: number | null;
  avg_cost_per_artifact_usd: number | null;
  avg_latency_ms: number | null;
  output_types_supported: number;
  reviewers_per_artifact: number;
  dataset_size_caption: string; // Always displayed — brand principle
  total_artifacts_generated: number;
}

// ── Generation request ────────────────────────────────────────────────────────

export interface GenerationParameters {
  audience?: string;
  tone?: string;
  language?: string;
  detail?: string;
  objective?: string;
  style?: string;
  brand_name?: string;
  sections?: string[];
}

export interface CreateGenerationRequest {
  source_id: string;
  source_ids?: string[];
  analysis_id?: string;
  conflict_resolutions?: Record<string, ConflictResolution>;
  output_types: OutputType[];
  sensitivity: Sensitivity;
  budget_type: BudgetType;
  budget_ceiling: number;
  parameters?: GenerationParameters;
  output_type_overrides?: Record<OutputType, Partial<GenerationParameters>>;
}

export interface SourceDocument { id: string; filename: string; source_version: string; sensitivity: Sensitivity }
export interface SourceReference { source_id: string; source_version: string; source_span: string; start_char: number; end_char: number; filename?: string }
export interface SynthesisFact { fact_key: string; claim: string; source_id: string; source_span: string; anchors: SourceReference[] }
export interface ConflictResolution { choice: 'preserve' | 'omit' | 'prefer'; preferred_source_id?: string | null }
export interface SourceConflict { id: string; reason: string; kind: string; fact_keys: string[]; facts: SynthesisFact[]; resolution: ConflictResolution }
export interface SourceAnalysis { id: string; status: string; documents: SourceDocument[]; manifest_hash: string; conflicts: SourceConflict[]; facts: SynthesisFact[]; unique_facts: number; job: {status: string; can_cancel: boolean; message: string | null; budget_used: number; budget_type: string; budget_ceiling: number; usage_incomplete: boolean} }
export interface SourceCollection { id: string; name: string; source_ids: string[]; revision: number; archived: boolean; sources?: Source[] }
export interface MultiSourceSelection { source_ids: string[]; analysis_id: string; conflict_resolutions: Record<string, ConflictResolution>; documents: SourceDocument[]; analysis_budget_used: number; analysis_budget_type: string }

// ── API error ─────────────────────────────────────────────────────────────────

export type ApiErrorKind =
  | 'backend_unavailable'
  | 'api_timeout'
  | 'generation_failure'
  | 'reviewer_failure'
  | 'metrics_unavailable'
  | 'unknown';

export interface ApiError {
  kind: ApiErrorKind;
  message: string;
  status?: number;
}

// ── Compliance override ───────────────────────────────────────────────────────

export interface ComplianceOverrideRequest {
  artifact_id: string;
  override_reason: string;
  sensitivity: Sensitivity;
  expected_content_version?: string;
}

// ── Rerun request ─────────────────────────────────────────────────────────────

export interface RerunRequest {
  generation_id: string;
  output_types?: OutputType[];
  budget_type: BudgetType;
  budget_ceiling: number;
}

// ── Command palette item ──────────────────────────────────────────────────────

export type CommandGroup = 'navigate' | 'generation' | 'artifact' | 'settings';

export interface CommandItem {
  id: string;
  group: CommandGroup;
  label: string;
  description?: string;
  shortcut?: string;
  href?: string;
  action?: () => void;
}

export interface SourcePage { items: Source[]; total: number; offset: number; limit: number }
export interface SourceDetail extends Source { text: string }
export interface FormatContract { id: OutputType; label: string; sections: string[]; version: string; deliverable: string; word_target: number }
export interface CreationPreset { id: string; name: string; revision: number; settings: { params: Omit<GenerationParameters, 'detail'> & { detail_level?: string }; output_types: OutputType[] } }

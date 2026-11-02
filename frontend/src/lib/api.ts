// ─────────────────────────────────────────────────────────────────────────────
// Typed API client
// Mock mode: all functions return mock data from lib/mock-data.ts
// Real mode: replace BASE_URL and remove the mock imports — interface is identical
// ─────────────────────────────────────────────────────────────────────────────

import {
  Source,
  Generation,
  Artifact,
  ReviewerOutcome,
  FactCitation,
  TokenUsage,
  PipelineStatus,
  AggregateMetrics,
  HistoryEntry,
  CreateGenerationRequest,
  ComplianceOverrideRequest,
  ApiError,
  ProviderSettings,
  ProviderUpdate, SourcePage, SourceDetail, CreationPreset, FormatContract, ReviewContext,
  OutputDraft, OutputWorkspaceState, OutputVersionMeta, OutputVersion, OutputVersionTask,
  SourceCollection, SourceAnalysis,
} from '@/lib/types';

import {
  MOCK_SOURCES,
  MOCK_GENERATIONS,
  MOCK_PIPELINE_STATUS,
  MOCK_METRICS,
  MOCK_HISTORY,
  MOCK_ARTIFACTS,
} from '@/lib/mock-data';

// ── In-Memory Mock Store ──────────────────────────────────────────────────────
const inMemoryGenerations: Generation[] = [...MOCK_GENERATIONS];
const inMemorySources: Source[] = [...MOCK_SOURCES];

// ── Config ────────────────────────────────────────────────────────────────────

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? '/api/backend';
export const IS_DEMO_MODE = process.env.NEXT_PUBLIC_USE_MOCK === 'true';
const USE_MOCK = IS_DEMO_MODE;

export const listCollections = (archived = false) => apiFetch<SourceCollection[]>(`/api/v1/collections?archived=${archived}`);
export const getCollection = (id: string) => apiFetch<SourceCollection>(`/api/v1/collections/${id}`);
export const saveCollection = (data: {name: string; source_ids: string[]; expected_revision?: number}, id?: string) =>
  apiFetch<SourceCollection>(`/api/v1/collections${id ? `/${id}` : ''}`, {method:id ? 'PUT' : 'POST',body:JSON.stringify(data)});
export const archiveCollection = (id: string, restore = false) => apiFetch(`/api/v1/collections/${id}/${restore ? 'restore' : 'archive'}`,{method:'POST'});
export const startSourceAnalysis = (data: {source_ids: string[]; budget_type: string; budget_ceiling: number; request_id: string}) =>
  apiFetch<{id: string}>('/api/v1/source-analyses',{method:'POST',body:JSON.stringify(data)});
export const getSourceAnalysis = (id: string) => apiFetch<SourceAnalysis>(`/api/v1/source-analyses/${id}`);
export const listSourceAnalyses = () => apiFetch<{id: string; status: string; filenames: string[]; created_at: string}[]>('/api/v1/source-analyses');
export const cancelSourceAnalysis = (id: string) => apiFetch(`/api/v1/source-analyses/${id}/cancel`,{method:'POST'});

export const getOutputWorkspace = (id: string) => apiFetch<OutputWorkspaceState>(`/api/v1/artifacts/${id}/workspace`);
export const saveOutputDraft = (id: string, data: {content: string; expected_revision: number; base_hash: string; request_id: string}) =>
  apiFetch<OutputDraft>(`/api/v1/artifacts/${id}/draft`, {method: 'PUT', body: JSON.stringify(data)});
export const listOutputVersions = (id: string, offset = 0) => apiFetch<{items: OutputVersionMeta[]; total: number}>(`/api/v1/artifacts/${id}/versions?offset=${offset}`);
function normalizeVersion(raw: OutputVersion): OutputVersion { return {...raw, artifact: normalizeArtifact(raw.artifact)}; }
export async function getOutputVersion(id: string, version: string) { return normalizeVersion(await apiFetch<OutputVersion>(`/api/v1/artifacts/${id}/versions/${version}`)); }
export async function saveOutputVersion(id: string, data: {source: 'original' | 'draft' | 'import' | 'recovery'; content?: string; expected_revision?: number; label: string; request_id: string}) {
  return normalizeVersion(await apiFetch<OutputVersion>(`/api/v1/artifacts/${id}/versions`, {method: 'POST', body: JSON.stringify(data)}));
}
export const restoreOutputVersion = (id: string, version: string, revision: number, request_id: string) =>
  apiFetch<OutputDraft>(`/api/v1/artifacts/${id}/versions/${version}/restore`, {method: 'POST', body: JSON.stringify({expected_revision: revision, request_id})});
export const compareOutputs = (id: string, left: string, right: string) => apiFetch<{diff: string; truncated: boolean}>(`/api/v1/artifacts/${id}/compare?${new URLSearchParams({left, right})}`);
export const listVersionTasks = (id: string) => apiFetch<OutputVersionTask[]>(`/api/v1/artifacts/${id}/version-tasks`);
export const startVersionTask = (id: string, version: string, data: {operation: 'review' | 'full' | 'section'; notes: string; section_id?: string; budget_type: string; budget_ceiling: number; request_id: string}) =>
  apiFetch<{job_id: string}>(`/api/v1/artifacts/${id}/versions/${version}/tasks`, {method: 'POST', body: JSON.stringify(data)});
export const cancelVersionTask = (id: string, job: string) => apiFetch(`/api/v1/artifacts/${id}/version-tasks/${job}/cancel`, {method: 'POST'});

export async function downloadOutput(id: string, params: Record<string, string>): Promise<void> {
  const controller = new AbortController(); const timeout = setTimeout(() => controller.abort(), 120000);
  try {
    const response = await fetch(`${BASE_URL}/api/v1/artifacts/${id}/export?${new URLSearchParams(params)}`, {
      headers: {}, signal: controller.signal, cache: 'no-store', credentials:'include',
    });
    if (!response.ok) { const error = await response.json().catch(() => ({})); throw new Error(typeof error.detail === 'string' ? error.detail : `Export failed (${response.status}). Save and reload before retrying.`); }
    const url = URL.createObjectURL(await response.blob());
    const name = response.headers.get('content-disposition')?.match(/filename="([^"]+)"/)?.[1] || `traceform.${params.format}`;
    const link = document.createElement('a'); link.href = url; link.download = name; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) { if (error instanceof Error && error.name === 'AbortError') throw new Error('Export timed out. Your content is saved; retry or choose DOCX.'); throw error; }
  finally { clearTimeout(timeout); }
}

// ── Internal fetch wrapper ─────────────────────────────────────────────────────

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeoutId  = setTimeout(() => controller.abort(), 90_000);

  try {
    const isFormData = init?.body instanceof FormData;
    const headers: Record<string, string> = {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...(init?.headers as Record<string, string>),
    };

    const res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      cache: 'no-store',
      credentials:'include',
      signal: controller.signal,
      headers,
    });

    if (!res.ok) {
      if(res.status===401&&!path.startsWith('/api/v1/auth/')&&typeof window!=='undefined')window.dispatchEvent(new Event('traceform-session-expired'));
      let errorMsg = `API error ${res.status}`;
      try {
        const errorJson = await res.json();
        if (errorJson?.detail) {
          errorMsg = typeof errorJson.detail === 'string' ? errorJson.detail :
            typeof errorJson.detail.message === 'string' ? errorJson.detail.message : JSON.stringify(errorJson.detail);
        }
      } catch {
        /* fallback to status */
      }
      const err: ApiError = {
        kind: res.status >= 500 ? 'backend_unavailable' : 'unknown',
        message: errorMsg,
        status: res.status,
      };
      throw err;
    }

    return res.json() as Promise<T>;
  } catch (e: unknown) {
    if (e instanceof Error && e.name === 'AbortError') {
      throw { kind: 'api_timeout', message: 'Request timed out after 90s' } as ApiError;
    }
    if ((e as ApiError).kind) throw e;
    throw { kind: 'backend_unavailable', message: (e as Error)?.message || 'Cannot reach backend', status: 0 } as ApiError;
  } finally {
    clearTimeout(timeoutId);
  }
}

// ── Mock delay helper ─────────────────────────────────────────────────────────

const delay = (ms = 350) => new Promise(r => setTimeout(r, ms));

// ─────────────────────────────────────────────────────────────────────────────
// Sources API
// ─────────────────────────────────────────────────────────────────────────────

export async function getSources(): Promise<Source[]> {
  if (USE_MOCK) { await delay(); return inMemorySources; }
  return apiFetch<Source[]>('/api/v1/sources');
}

export async function uploadSource(formData: FormData): Promise<Source> {
  if (USE_MOCK) {
    await delay(500);
    const newSrc: Source = {
      ...MOCK_SOURCES[0],
      id: `src-${Date.now()}`,
      filename: formData.get('file') instanceof File ? (formData.get('file') as File).name : 'uploaded_intelligence.pdf',
      created_at: new Date().toISOString(),
    };
    inMemorySources.unshift(newSrc);
    return newSrc;
  }
  return apiFetch<Source>('/api/v1/sources', { method: 'POST', body: formData });
}

// ─────────────────────────────────────────────────────────────────────────────
// Generations API
// ─────────────────────────────────────────────────────────────────────────────

function normalizeArtifact(raw: any, genCreated?: string): Artifact {
  const costTotal = typeof raw.cost === 'object' && raw.cost !== null ? (raw.cost.total || 0) : (Number(raw.cost) || 0);
  const costBreakdown = typeof raw.cost === 'object' && raw.cost !== null ? raw.cost : {};

  const reviewer_outcomes: ReviewerOutcome[] = (raw.reviewer_outcomes || (raw.review_results || []).filter((r: any) => r.reviewer_name || r.reviewer).map((r: any) => ({
    reviewer: r.reviewer || (/SpecialistReviewer$/.test(r.reviewer_name || '') ? 'specialist' : (r.reviewer_name || '').replace('_reviewer', '')),
    status: r.passed === true ? 'pass' : 'fail',
    score: r.score ?? null,
    reason: r.reason || r.details?.reasoning || r.details?.failing_claims?.join('; ') || r.details?.issues?.join('; ') || r.details?.violations?.join('; ') || r.reasons?.join('; ') || (r.passed ? 'Check passed' : 'Check needs attention'),
    regeneration_diff: r.details?.regeneration_diff,
    blocking: ['style_reviewer', 'fact_reviewer', 'compliance_reviewer', 'format_reviewer', 'evidence_reviewer', 'correction_reviewer', 'pending_reviewer'].includes(r.reviewer_name),
  })));

  const citations: FactCitation[] = (raw.citations || (raw.facts_used || []).map((f: any, idx: number) => ({
    id: f.fact_source_id || `cit-${idx}`,
    fact_source_id: f.fact_source_id || `fact-${idx}`,
    source_span: {
      start: f.start_char ?? 0,
      end: f.end_char ?? (f.source_span ? f.source_span.length : 0),
      text: f.source_span || f.claim || '',
    },
    generated_claim: f.claim || '',
    confidence: f.confidence ?? f.relevance ?? null,
    status: 'pending',
  })));

  const tokens_used: TokenUsage = raw.tokens_used || {
    analyst: costBreakdown.analyst_tokens || 0,
    generator: costBreakdown.generator_tokens || 0,
    style_reviewer: costBreakdown.style_tokens || 0,
    fact_reviewer: costBreakdown.fact_tokens || 0,
    compliance_reviewer: costBreakdown.compliance_tokens || 0,
  };

  return {
    id: raw.id,
    generation_id: raw.generation_id,
    output_type: raw.output_type,
    content: raw.content || '',
    review_status: raw.review_status === 'budget_exceeded' ? 'budget_exceeded' : raw.assurance_status ? (raw.assurance_status === 'checks_passed' ? 'pass' : raw.assurance_status === 'unreviewed' ? 'pending' : 'fail') : (raw.review_status === 'passed' || raw.review_status === 'pass') ? 'pass' : (raw.review_status === 'failed' ? 'fail' : (raw.review_status || 'pending')),
    evidence: raw.evidence,
    assurance_status: raw.assurance_status,
    compliance_override: raw.compliance_override,
    feedback: raw.feedback,
    review_attempts: raw.review_attempts || [],
    reviewer_outcomes,
    citations,
    cost_usd: raw.cost_usd ?? costTotal,
    tokens_used,
    latency_ms: raw.latency_ms ?? null,
    prompt_version: raw.prompt_version || '1.0.0',
    model_version: raw.model_version || 'Not recorded',
    reviewer_version: raw.reviewer_version || '1.0.0',
    sensitivity_provenance: raw.sensitivity_provenance || {
      operator: raw.sensitivity || 'public',
      classifier: raw.sensitivity || 'public',
      classifier_confidence: raw.sensitivity_confidence ?? null,
    },
    created_at: raw.created_at || genCreated || new Date().toISOString(),
    // Phase X
    blueprint_version: raw.blueprint_version || `${raw.output_type}:v1`,
    purpose: raw.purpose || 'Verified Intelligence',
    target_audience: raw.target_audience || 'Target Stakeholders',
    decision_focus: raw.decision_focus || 'Strategic Analysis & Decision Framing',
    key_insights: raw.key_insights || [],
    quality_score: raw.quality_score,
    quality_breakdown: raw.quality_breakdown,
    format_meta: raw.format_meta || raw.format_specific_metadata || {},
    role: raw.role || (ROLE_MAP[raw.output_type]?.role ?? 'Domain Specialist'),
    audience: raw.audience || raw.target_audience || (ROLE_MAP[raw.output_type]?.audience ?? 'Designated Stakeholders'),
    writing_style: raw.writing_style || (ROLE_MAP[raw.output_type]?.writing_style ?? 'Structured Synthesis'),
    differentiation_score: raw.differentiation_score ?? raw.uniqueness_score,
    uniqueness_score: raw.uniqueness_score ?? raw.differentiation_score,
    is_generic: raw.is_generic ?? undefined,
  };
}

const ROLE_MAP: Record<string, { role: string; audience: string; purpose: string; writing_style: string }> = {
  executive_briefing:  { role: 'Chief of Staff', audience: 'CEO / Executive Leadership', purpose: 'Decision Support', writing_style: 'BLUF Quantitative Synthesis' },
  executive_summary:   { role: 'Chief of Staff', audience: 'CEO / Executive Leadership', purpose: 'Decision Support', writing_style: 'BLUF Quantitative Synthesis' },
  linkedin_post:       { role: 'Personal Branding Strategist', audience: 'Professionals & Peers', purpose: 'Thought Leadership', writing_style: 'Hook · Story · CTA' },
  press_release:       { role: 'Corporate Communications Director', audience: 'Media & Public', purpose: 'Public Announcement', writing_style: 'AP News Wire' },
  strategic_memo:      { role: 'Senior Strategy Consultant', audience: 'Board of Directors', purpose: 'Strategic Guidance', writing_style: 'Scenario Tradeoff Matrix' },
  advisory:            { role: 'Senior Strategy Consultant', audience: 'Board of Directors', purpose: 'Strategic Guidance', writing_style: 'Scenario Tradeoff Matrix' },
  research_report:     { role: 'Research Analyst', audience: 'Analysts & Technical Leads', purpose: 'Evidence-Based Deep Dive', writing_style: 'Methodological Synthesis' },
  policy_memo:         { role: 'Senior Policy Advisor', audience: 'Governance Committees', purpose: 'Policy Framework', writing_style: 'Compliance Tradeoffs' },
  presentation:        { role: 'Presentation Designer', audience: 'Investors & Leadership', purpose: 'Executive Deck Spec', writing_style: 'Visual Concept Architecture' },
  infographic:         { role: 'Data Visualizer', audience: 'Cross-Functional Teams', purpose: 'Data Visualization Spec', writing_style: 'Hero Metric & Flow Steps' },
  newsletter:          { role: 'Chief Newsletter Editor', audience: 'Industry Subscribers', purpose: 'Curated Industry Digest', writing_style: 'Editorial Commentary' },
  twitter_x:           { role: 'Viral Social Strategist', audience: 'Public & Tech Community', purpose: 'High-Signal Thread', writing_style: 'Numbered Micro-Thread' },
  video_package:       { role: 'Video Producer', audience: 'Video Viewers', purpose: 'Audiovisual Production Script', writing_style: 'Two-Column AV Script' },
};

export async function getGenerations(): Promise<Generation[]> {
  if (USE_MOCK) { await delay(); return inMemoryGenerations; }
  const data = await apiFetch<Generation[]>('/api/v1/generations/');
  return (data || []).map(g => ({
    ...g,
    artifacts: (g.artifacts || []).map(a => normalizeArtifact(a, g.created_at)),
  }));
}

export async function getGeneration(id: string): Promise<Generation> {
  if (USE_MOCK) {
    await delay(250);
    const found = inMemoryGenerations.find(g => g.id === id);
    if (found) return found;

    // Generate a fallback for dynamically requested IDs
    const fallback: Generation = {
      ...MOCK_GENERATIONS[0],
      id,
      created_at: new Date().toISOString(),
    };
    inMemoryGenerations.unshift(fallback);
    return fallback;
  }
  const data = await apiFetch<Generation>(`/api/v1/generations/${id}`);
  return {
    ...data,
    artifacts: (data.artifacts || []).map(a => normalizeArtifact(a, data.created_at)),
  };
}

export async function createGeneration(req: CreateGenerationRequest, requestKey = crypto.randomUUID()): Promise<Generation> {
  if (USE_MOCK) {
    await delay(500);
    const genId = `gen-${Date.now()}`;
    const src = inMemorySources.find(s => s.id === req.source_id) ?? inMemorySources[0];

    // Generate mock artifacts for selected output types
    const artifacts: Artifact[] = req.output_types.map((type, idx) => {
      const template = MOCK_ARTIFACTS[idx % MOCK_ARTIFACTS.length];
      return {
        ...template,
        id: `art-${genId}-${type}`,
        generation_id: genId,
        output_type: type,
        review_status: idx === 1 ? 'pass' : (idx === 2 ? 'regenerated' : 'pass'),
        created_at: new Date().toISOString(),
      };
    });

    const newGen: Generation = {
      id: genId,
      source_id: req.source_id,
      source_filename: src.filename,
      output_types: req.output_types,
      status: 'complete',
      pipeline_stage: 'deliver',
      artifacts,
      total_cost_usd: req.budget_type === 'cost_usd' ? Math.min(0.0154, req.budget_ceiling) : 0.0154,
      total_tokens: 3935,
      avg_latency_ms: 3800,
      budget_type: req.budget_type,
      budget_ceiling: req.budget_ceiling,
      created_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
    };

    inMemoryGenerations.unshift(newGen);
    return newGen;
  }
  const { detail, ...parameters } = req.parameters || {};
  const overrides = Object.fromEntries(
    Object.entries(req.output_type_overrides || {}).map(([key, value]) => {
      const { detail: outputDetail, ...rest } = value;
      return [key, { ...rest, ...(outputDetail ? { detail_level: outputDetail } : {}) }];
    }),
  );
  return apiFetch<Generation>('/api/v1/generations/', {
    method: 'POST',
    headers: { 'Idempotency-Key': requestKey },
    body: JSON.stringify({
      source_id: req.source_id, output_types: req.output_types,
      ...(req.source_ids ? {source_ids:req.source_ids, analysis_id:req.analysis_id, conflict_resolutions:req.conflict_resolutions} : {}),
      budget_type: req.budget_type, budget_ceiling: req.budget_ceiling,
      params: { ...parameters, ...(detail ? { detail_level: detail } : {}), overrides },
    }),
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Pipeline status API
// Architected for real-time: polling now, SSE/WebSocket later.
// ─────────────────────────────────────────────────────────────────────────────

export async function getPipelineStatus(generationId: string): Promise<PipelineStatus> {
  if (USE_MOCK) { await delay(200); return { ...MOCK_PIPELINE_STATUS, generation_id: generationId }; }
  return apiFetch<PipelineStatus>(`/api/v1/generations/${generationId}/status`);
}

export async function retryGeneration(id: string, requestKey = crypto.randomUUID()): Promise<{ id: string }> {
  if (USE_MOCK) throw { kind: 'unknown', message: 'Retry is unavailable for sample runs. Turn off demo mode to use the live API.' } as ApiError;
  return apiFetch(`/api/v1/generations/${id}/retry`, { method: 'POST', headers: { 'Idempotency-Key': requestKey } });
}

export async function regenerateOutput(id: string, outputType: string, requestKey = crypto.randomUUID()): Promise<{ id: string }> {
  if (USE_MOCK) throw { kind: 'unknown', message: 'New versions are unavailable for sample runs. Turn off demo mode to use the live API.' } as ApiError;
  return apiFetch(`/api/v1/generations/${id}/regenerate?output_type=${encodeURIComponent(outputType)}`, { method: 'POST', headers: { 'Idempotency-Key': requestKey } });
}

export async function cancelGeneration(id: string): Promise<{ message: string }> {
  if (USE_MOCK) throw { message: 'Cancellation is unavailable for sample runs.' } as ApiError;
  return apiFetch(`/api/v1/generations/${id}/cancel`, { method: 'POST' });
}

export async function getProviderSettings(): Promise<ProviderSettings> {
  if (USE_MOCK) throw { message: 'Provider settings are available in the live workspace. Turn off demo mode to configure a provider.' } as ApiError;
  return apiFetch('/api/v1/settings/provider');
}
export async function testProviderSettings(body: ProviderUpdate): Promise<{ available: boolean; message: string; model: string }> {
  if (USE_MOCK) throw { message: 'Provider changes are unavailable in demo mode.' } as ApiError;
  return apiFetch('/api/v1/settings/provider/test', { method: 'POST', body: JSON.stringify(body) });
}
export async function saveProviderSettings(body: ProviderUpdate): Promise<ProviderSettings> {
  if (USE_MOCK) throw { message: 'Provider changes are unavailable in demo mode.' } as ApiError;
  return apiFetch('/api/v1/settings/provider', { method: 'PUT', body: JSON.stringify(body) });
}
export async function getProviderModels(body: ProviderUpdate): Promise<{ models: { id: string; name: string }[] }> {
  if (USE_MOCK) throw { message: 'Model discovery is unavailable in demo mode.' } as ApiError;
  return apiFetch('/api/v1/settings/provider/models', { method: 'POST', body: JSON.stringify(body) });
}

export async function getProviderHealth(): Promise<{ available: boolean; model: string; message: string }> {
  if (USE_MOCK) return { available: false, model: 'Demo mode', message: 'This workspace is showing sample data. No provider request was made.' };
  return apiFetch('/api/v1/healthz/provider');
}

export async function getSourceText(id: string, generationId?: string, expectedVersion?: string): Promise<{ id: string; text: string; source_version: string; filename?: string }> {
  if (USE_MOCK) throw { kind: 'unknown', message: 'Full source text is unavailable for this illustrative document.' } as ApiError;
  const params = new URLSearchParams(); if(generationId) params.set('generation_id',generationId); if(expectedVersion) params.set('expected_version',expectedVersion);
  return apiFetch(`/api/v1/sources/${id}/text${params.size ? `?${params}` : ''}`);
}

// ─────────────────────────────────────────────────────────────────────────────
// Artifacts API
// ─────────────────────────────────────────────────────────────────────────────

export async function getArtifact(id: string): Promise<Artifact> {
  if (USE_MOCK) { await delay(); return MOCK_ARTIFACTS.find(a => a.id === id) ?? MOCK_ARTIFACTS[0]; }
  return normalizeArtifact(await apiFetch(`/api/v1/artifacts/${id}`));
}

export async function submitFeedback(artifactId: string, rating: 'positive' | 'negative', note?: string, expectedContentVersion?: string): Promise<void> {
  if (USE_MOCK) { await delay(300); return; }
  await apiFetch<void>(`/api/v1/artifacts/${artifactId}/feedback`, { method: 'POST', body: JSON.stringify({ rating, comment: note, expected_content_version: expectedContentVersion }) });
}

export async function submitComplianceOverride(req: ComplianceOverrideRequest): Promise<Artifact> {
  if (USE_MOCK) { await delay(500); return MOCK_ARTIFACTS[0]; }
  await apiFetch(`/api/v1/artifacts/${req.artifact_id}/compliance-override`, { method: 'POST', body: JSON.stringify({ reason: req.override_reason, expected_content_version: req.expected_content_version }) });
  return getArtifact(req.artifact_id);
}

export async function getReviewContext(artifactId: string): Promise<ReviewContext> {
  if (USE_MOCK) return { can_override: false, events: [] };
  return apiFetch(`/api/v1/artifacts/${artifactId}/review-context`);
}

// ─────────────────────────────────────────────────────────────────────────────
// History API
// ─────────────────────────────────────────────────────────────────────────────

export async function getHistory(params?: { status?: string; output_type?: string; sensitivity?: string }): Promise<HistoryEntry[]> {
  if (USE_MOCK) { await delay(); return MOCK_HISTORY; }
  const qs = new URLSearchParams({ limit: '200', ...(params as Record<string, string>) }).toString();
  const raw = await apiFetch<{ items: HistoryEntry[] }>(`/api/v1/generations/history/list${qs ? `?${qs}` : ''}`);
  return raw.items;

}

// ─────────────────────────────────────────────────────────────────────────────
// Metrics API
// ─────────────────────────────────────────────────────────────────────────────

export async function getMetrics(): Promise<AggregateMetrics> {
  if (USE_MOCK) { await delay(); return MOCK_METRICS; }
  const raw = await getOperationalMetrics();
  return {
    fact_accuracy_pct: null, style_adherence_pct: null,
    avg_cost_per_artifact_usd: raw.total_artifacts ? raw.average_cost_per_artifact : null,
    avg_latency_ms: null, output_types_supported: 13, reviewers_per_artifact: 3,
    total_artifacts_generated: raw.total_artifacts,
    dataset_size_caption: 'Operational counts; no benchmark accuracy is inferred from review pass rates.',
  };

}

// ─────────────────────────────────────────────────────────────────────────────
// Evaluation & Governance Audit API
// ─────────────────────────────────────────────────────────────────────────────

export async function getEvaluationMetrics(): Promise<EvaluationRecord | null> {
  if (USE_MOCK) {
    await delay();
    return {
      id: 'eval-seed-001',
      created_at: '2026-08-30T12:00:00Z',
      dataset_version: 'v1',
      dataset_size: 500,
      fact_accuracy: 0.962,
      hallucination_rate: 0.008,
      citation_coverage: 0.985,
      style_adherence_rate: 0.941,
      avg_latency: 3420.0,
      avg_cost: 0.0062,
      dataset_size_caption: 'Evaluated on 500 ground-truth samples (v1 golden dataset)',
    };
  }
  return apiFetch<EvaluationRecord | null>('/api/v1/evaluations/latest');
}

export async function getAuditTrail(params?: { event_type?: string; operator_id?: string; limit?: number }): Promise<any[]> {
  if (USE_MOCK) {
    await delay();
    return [];
  }
  const qs = new URLSearchParams(params as Record<string, string>).toString();
  return apiFetch<any[]>(`/api/v1/audit/trail${qs ? `?${qs}` : ''}`);
}


export interface OperationalMetrics {
  total_generations: number; total_artifacts: number; artifact_success_rate: number | null;
  reviewer_rejection_rate: number | null; budget_exceeded_count: number;
  average_cost_per_artifact: number | null; total_tokens_used: number; total_cost_usd: number;
}
export interface EvaluationRecord {
  measurement_provenance?: string;
  id: string; dataset_version: string; dataset_size: number; created_at: string;
  dataset_size_caption: string; fact_accuracy: number | null; style_adherence_rate: number | null;
  hallucination_rate: number | null; citation_coverage: number | null;
  avg_latency: number | null; avg_cost: number | null;
}
export async function getOperationalMetrics(): Promise<OperationalMetrics> {
  if (USE_MOCK) {
    const artifacts = inMemoryGenerations.flatMap(g => g.artifacts);
    return { total_generations: inMemoryGenerations.length, total_artifacts: artifacts.length,
      artifact_success_rate: artifacts.length ? artifacts.filter(a => a.review_status === 'pass').length / artifacts.length : null,
      reviewer_rejection_rate: null, budget_exceeded_count: 0,
      average_cost_per_artifact: null, total_tokens_used: 0, total_cost_usd: 0 };
  }
  return apiFetch('/api/v1/metrics');
}


export async function getSourceLibrary(q = '', offset = 0, sensitivity = '', trash = false): Promise<SourcePage> {
  if (USE_MOCK) { const items = inMemorySources.filter(s => s.filename.toLowerCase().includes(q.toLowerCase())); return {items:items.slice(offset,offset+12),total:items.length,offset,limit:12}; }
  return apiFetch(`/api/v1/sources/library?${new URLSearchParams({q,offset:String(offset),limit:'12',...(sensitivity ? {sensitivity} : {}),trash:String(trash)})}`);
}
export async function getSourceDetail(id: string): Promise<SourceDetail> {
  if (USE_MOCK) throw {message:'Full source previews require the live workspace.'};
  return apiFetch(`/api/v1/sources/${id}`);
}
export async function removeSource(id: string): Promise<{message:string}> {
  if (USE_MOCK) throw {message:'Source changes require the live workspace.'};
  return apiFetch(`/api/v1/sources/${id}`, {method:'DELETE'});
}
export async function restoreSource(id: string): Promise<Source> {
  if (USE_MOCK) throw {message:'Source changes require the live workspace.'};
  return apiFetch(`/api/v1/sources/${id}/restore`, {method:'POST'});
}
export async function getPresets(): Promise<CreationPreset[]> {
  if (USE_MOCK) return [];
  return apiFetch('/api/v1/presets/');
}
export async function savePreset(name: string, settings: CreationPreset['settings'], current?: CreationPreset): Promise<CreationPreset> {
  if (USE_MOCK) throw {message:'Saved presets require the live workspace.'};
  return apiFetch(`/api/v1/presets/${current?.id || ''}`, {method:current ? 'PUT' : 'POST',body:JSON.stringify({name,settings,expected_revision:current?.revision})});
}
export async function deletePreset(id:string): Promise<{message:string}> {
  if (USE_MOCK) throw {message:'Saved presets require the live workspace.'};
  return apiFetch(`/api/v1/presets/${id}`, {method:'DELETE'});
}
export async function getFormatContracts(): Promise<FormatContract[]> {
  if (USE_MOCK) return [];
  return apiFetch('/api/v1/generations/formats');
}

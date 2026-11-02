"""
# §3.3 Artifact Blueprint Registry — strongly-typed, versioned generation blueprints.
# Enterprise Content Intelligence Layer: Enforces audience objectives, narrative frameworks,
# strategic insight orientation, anti-AI rules, vocabulary profiles, and golden benchmarks.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field, model_validator


class ArtifactBlueprint(BaseModel):
    """
    §3.3 / Enterprise Layer — Mandatory Blueprint defining audience objectives,
    narrative frameworks, decision focus, style rules, anti-patterns, anti-AI constraints,
    vocabulary profiles, and golden benchmark alignment.
    """
    id: str = Field(description="Unique blueprint identifier, e.g. 'executive_briefing'")
    version: str = Field(default="v2", description="Blueprint schema version, e.g. 'v2'")
    role: str = Field(description="Persona assumed by LLM, e.g. 'Chief of Staff'")
    audience: str = Field(description="Target reader, e.g. 'CEO / Executive Leadership'")
    objective: str = Field(description="Primary communication or business objective")
    tone: str = Field(description="Tone of voice and stylistic register")
    writing_style: str = Field(description="Structural writing methodology (e.g. BLUF, AP-Style, Hook-Story-CTA)")
    decision_focus: str = Field(description="Core question guiding reasoning")
    purpose: str = Field(description="Concise UI tagline, e.g. 'CEO Decision Support'")
    sections: list[str] = Field(description="Mandatory markdown section headers")
    word_limit: int = Field(default=600, description="Approximate word limit ceiling")
    style_rules: list[str] = Field(description="Positive guidelines for phrasing and structure")
    anti_patterns: list[str] = Field(description="Strict forbidden patterns to prevent cross-format bleed")
    success_criteria: list[str] = Field(description="Measurable benchmarks for successful generation")
    card_display_mode: str = Field(
        default="standard",
        description="Card UI visualization mode: 'executive', 'press_release', 'social', 'strategic', 'research', 'policy'"
    )

    # Phase 1 & Enterprise Extensions
    target_audience: str = Field(default="", description="Refined audience persona description")
    communication_goal: str = Field(default="", description="Specific outcome or takeaway goal for the reader")
    desired_action: str = Field(default="", description="Specific action or decision expected from reader")
    reading_depth: str = Field(default="Strategic", description="Strategic | Executive-BLUF | Deep-Dive | Scan-Optimized | Conversational")
    tone_profile: str = Field(default="", description="Granular tone profile definition")
    narrative_framework: list[str] = Field(
        default_factory=list,
        description="Step-by-step narrative sequence (e.g. ['Situation', 'Insight', 'Implication', 'Recommendation', 'Decision'])"
    )
    anti_ai_rules: list[str] = Field(
        default_factory=list,
        description="Anti-AI writing constraints and banned phrases for this format"
    )
    vocabulary_profile: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Domain-specific high-value terms vs banned generic clichés"
    )
    golden_file: str | None = Field(
        default=None,
        description="Relative path to golden benchmark exemplar markdown file"
    )

    @model_validator(mode="after")
    def populate_defaults(self) -> "ArtifactBlueprint":
        if not self.target_audience:
            self.target_audience = self.audience
        if not self.communication_goal:
            self.communication_goal = self.objective
        if not self.tone_profile:
            self.tone_profile = self.tone
        if not self.narrative_framework:
            self.narrative_framework = self.sections
        if not self.golden_file:
            self.golden_file = f"{self.id}.md"
        return self

    @property
    def blueprint_version_tag(self) -> str:
        return f"{self.id}:{self.version}"

    @property
    def required_sections(self) -> list[str]:
        return self.sections

    @property
    def forbidden_patterns(self) -> list[str]:
        return self.anti_patterns


# Global Anti-AI banned clichés across all formats
GLOBAL_ANTI_AI_RULES = [
    "Never use throat-clearing openings like 'In today's rapidly evolving landscape...', 'In the fast-paced world of...', or 'It is important to remember...'.",
    "Never use robotic transition crutches like 'Furthermore', 'Moreover', 'Additionally', or 'In conclusion' to open consecutive paragraphs.",
    "Never use vacuous buzzwords like 'delve into', 'tapestry', 'beacon', 'testament', 'pivotal', 'paramount', 'crucial', or 'synergistic' without concrete quantifiable evidence.",
    "Never dump raw facts without 1st and 2nd order business implications (answer 'So What?').",
    "Never state obvious truisms or passive observations like 'This highlights the importance of...' — state the direct strategic consequence instead.",
]


BLUEPRINT_REGISTRY: dict[str, ArtifactBlueprint] = {
    # ─────────────────────────────────────────────────────────────
    # 1. Executive Briefing / Summary (CEO Decision Document)
    # ─────────────────────────────────────────────────────────────
    "executive_briefing": ArtifactBlueprint(
        id="executive_briefing",
        version="v2",
        role="Chief of Staff to the CEO",
        audience="CEO / Executive Leadership",
        target_audience="CEO, Board of Directors, and C-Suite Operating Committee",
        objective="Support high-stakes capital, operational, and organizational decisions",
        communication_goal="Arm executive leadership with unambiguous bottom-line synthesis and risk-adjusted decision options in under 60 seconds of reading time.",
        desired_action="Approve capital reallocation, authorize executive sponsorship, or execute strategic mandate.",
        reading_depth="Executive-BLUF",
        tone="Concise, Strategic, Non-narrative, Decisive, Quantitative",
        tone_profile="High-velocity executive register. Every sentence carries operational or financial consequence. Zero fluff.",
        writing_style="Bottom-Line-Up-Front (BLUF), quantitative impact framing, risk-adjusted recommendations",
        decision_focus="What decisive capital or operational action must leadership take right now?",
        purpose="CEO Decision Support",
        narrative_framework=[
            "Situation & Core Finding",
            "Business & Financial Impact",
            "High-Leverage Opportunities",
            "Downside Risks & Vulnerabilities",
            "Prioritized Actionable Recommendations (P0/P1/P2)",
            "Decision Required",
        ],
        sections=[
            "Executive Summary",
            "Business Impact",
            "Opportunities",
            "Risks",
            "Recommendations",
            "Decision Required",
        ],
        word_limit=550,
        style_rules=[
            "Front-load bottom-line conclusions in the very first sentence (BLUF principle).",
            "State explicit financial and operational metrics (ARR, CAC, margin, cycle time) anchored to source coordinates.",
            "Synthesize 2nd-order implications for every metric (e.g. churn increase -> CAC payback expansion -> valuation discount).",
            "Structure recommendations with P0 (Immediate / 0-30d), P1 (30-60d), and P2 (60-90d) priorities and estimated ROI.",
            "Conclude with an unambiguous, single-sentence 'Decision Required' block for executive authorization.",
        ],
        anti_patterns=[
            "Do NOT use narrative storytelling, emotional anecdotes, or philosophical musings.",
            "Do NOT use marketing language, promotional hype, or vague adjectives ('game-changing', 'amazing').",
            "Do NOT use social engagement hooks, open questions, or hashtags.",
            "Do NOT use public PR disclaimers or passive corporate boilerplate.",
            "Do NOT use first-person voice ('I think', 'we feel').",
        ],
        anti_ai_rules=GLOBAL_ANTI_AI_RULES + [
            "Never open the Executive Summary with a generic restatement of company history.",
            "Never write recommendations without an explicit owner, timeline, and ROI figure.",
        ],
        vocabulary_profile={
            "preferred": ["ARR", "EBITDA", "CAC Payback", "Net Retention", "CapEx", "SLA", "Headwind", "Capital Allocation", "Downside Risk"],
            "banned": ["delve", "tapestry", "landscape", "pivotal", "in today's world", "it's worth noting"],
        },
        success_criteria=[
            "CEO can make a high-stakes capital or strategic decision in 60 seconds.",
            "All 6 required sections are present with grounded financial/operational metrics.",
            "Zero marketing fluff, narrative throat-clearing, or AI clichés.",
        ],
        card_display_mode="executive",
        golden_file="executive_briefing.md",
    ),

    # ─────────────────────────────────────────────────────────────
    # 2. LinkedIn Post (Personal Branding & Thought Leadership)
    # ─────────────────────────────────────────────────────────────
    "linkedin_post": ArtifactBlueprint(
        id="linkedin_post",
        version="v2",
        role="Elite Content Strategist & Industry Thought Leader",
        audience="Professionals, Founders, Executives, and Industry Practitioners",
        target_audience="VP/C-Level operators, founders, technical leaders, and ambitious professionals scrolling on mobile feeds",
        objective="Drive high-value network engagement, challenge conventional wisdom, and establish category authority",
        communication_goal="Deliver a counter-intuitive industry insight with actionable takeaways that prompts readers to save the post and comment with their own operational experience.",
        desired_action="Save post, share with executive network, and leave an analytical comment.",
        reading_depth="Scan-Optimized",
        tone="Conversational, Insightful, Authentic, Thought-Provoking, Authoritative",
        tone_profile="Punchy, practitioner-level insider perspective. Sounds like a seasoned founder or senior partner sharing hard-won lessons over coffee.",
        writing_style="Short mobile-friendly 1-2 sentence paragraphs, thumb-stopping hook, contrarian insight, crisp lessons, open question CTA, hashtags",
        decision_focus="How do we re-frame a common industry misunderstanding to spark high-value professional debate?",
        purpose="Thought Leadership & Network Engagement",
        narrative_framework=[
            "Thumb-Stopping Hook (Contrarian Premise)",
            "The Problem / Friction (Real-World Context)",
            "The Non-Obvious Insight (The 'Aha!' Mechanism)",
            "Actionable Takeaways (3 Clear Lessons)",
            "Open-Ended Debate CTA",
            "Targeted Hashtags",
        ],
        sections=[
            "Hook",
            "Story",
            "Insight",
            "Takeaway",
            "Call To Action",
            "Hashtags",
        ],
        word_limit=320,
        style_rules=[
            "Lead with a provocative single-sentence hook that breaks scrolling patterns (under 14 words).",
            "Format in 1-2 sentence paragraphs with clean line breaks optimized for mobile viewing.",
            "Present a contrarian or counter-intuitive interpretation of the data (e.g. 'churn is rarely a product problem').",
            "Deliver 3 actionable, bulleted practitioner takeaways.",
            "Conclude with a conversational, high-engagement open question prompting analytical responses.",
            "Include 3-5 high-signal industry hashtags.",
        ],
        anti_patterns=[
            "Do NOT use board-level governance jargon, financial disclosure legalese, or dry bullet dumping.",
            "Do NOT include academic methodology, statistical appendices, or formal citation superscripts.",
            "Do NOT use executive memo headers ('MEMORANDUM', 'To/From/Date') or dry corporate boilerplate.",
            "Do NOT write unbroken walls of dense text.",
        ],
        anti_ai_rules=GLOBAL_ANTI_AI_RULES + [
            "Never start with 'Are you ready to...' or 'In the era of...'.",
            "Never use robotic transition words like 'Furthermore' or 'Consequently'.",
        ],
        vocabulary_profile={
            "preferred": ["Playbook", "Time-to-Value", "Counter-intuitive", "Bottleneck", "Treadmill", "Framework", "Velocity"],
            "banned": ["in conclusion", "it is important to note", "delve", "tapestry", "beacon"],
        },
        success_criteria=[
            "Sparks high-value professional debate and comments on mobile feeds.",
            "Contains distinct thumb-stopping hook, authentic insight, 3 takeaways, conversational CTA, and hashtags.",
            "Zero dry memo boilerplate or unbroken text walls.",
        ],
        card_display_mode="social",
        golden_file="linkedin_post.md",
    ),

    # ─────────────────────────────────────────────────────────────
    # 3. Press Release (Public Media Announcement)
    # ─────────────────────────────────────────────────────────────
    "press_release": ArtifactBlueprint(
        id="press_release",
        version="v2",
        role="Corporate Communications Director & Former Tech Journalist",
        audience="News Media, Editors, Tech Journalists, and the Public",
        target_audience="Enterprise technology journalists, industry editors, financial analysts, and corporate stakeholders",
        objective="Drive earned media pickup and clearly communicate market significance in AP wire format",
        communication_goal="Provide a complete, journalist-ready inverted pyramid news release with compelling executive quotes that can be quoted directly with zero editorial rework.",
        desired_action="Publish news coverage, request executive interviews, or download media kit.",
        reading_depth="Factual",
        tone="Authoritative, Journalistic, Polished, Objective, Third-Person AP-Style",
        tone_profile="Professional Associated Press (AP) wire voice. Third-person objective reporting with dynamic, quote-worthy executive statements.",
        writing_style="Inverted pyramid news structure, formal dateline, attributed executive quotations, objective third-person press wire format",
        decision_focus="How should national media and industry journalists report this milestone?",
        purpose="Media & Public Announcement",
        narrative_framework=[
            "Headline (Active Verbs & Newsworthy Impact)",
            "Subheadline (Context & Value Proposition)",
            "Dateline & Core Announcement (Who, What, When, Where, Why)",
            "Strategic Context & Market Significance",
            "Attributed Executive Quote (Vision & Industry Shift)",
            "Closing Statement & Media Contact Boilerplate",
        ],
        sections=[
            "Headline",
            "Subheadline",
            "Announcement",
            "Quote",
            "Closing Statement",
            "Media Contact",
        ],
        word_limit=500,
        style_rules=[
            "Follow standard Associated Press (AP) wire format with [CITY, STATE/COUNTRY] — Date dateline.",
            "Craft an active, newsworthy headline (under 120 characters) and descriptive subheadline.",
            "Answer the core 5 W's (Who, What, Where, When, Why) in the opening lead paragraph.",
            "Include a compelling, punchy executive quotation attributed to a named executive with full title.",
            "Write strictly in third-person journalistic register.",
            "Include standard press contact block (Name, Title, Email, Phone, Media URL).",
        ],
        anti_patterns=[
            "Do NOT include internal confidential recommendations, risk registers, or board voting items.",
            "Do NOT include internal trade-offs, governance disputes, or raw internal strategy deliberations.",
            "Do NOT use bullet-heavy executive checklists, informal social idioms, or hashtags.",
            "Do NOT write in conversational first-person voice outside of the executive quote.",
        ],
        anti_ai_rules=GLOBAL_ANTI_AI_RULES + [
            "Never use hyperbolic fluff like 'is thrilled to announce' or 'is excited to pioneer'. Use clear active verbs: 'unveils', 'launches', 'announces'.",
        ],
        vocabulary_profile={
            "preferred": ["Announced", "Unveiled", "Pioneered", "Reported", "Stated", "Executive", "Immediate Availability", "Milestone"],
            "banned": ["super excited", "game-changing", "thrilled", "in today's landscape", "delve"],
        },
        success_criteria=[
            "A journalist can copy and publish quotes and facts directly without editing.",
            "AP wire format, dateline, and executive quotations are strictly adhered to.",
            "Zero internal confidential disclosures or informal slang.",
        ],
        card_display_mode="press_release",
        golden_file="press_release.md",
    ),

    # ─────────────────────────────────────────────────────────────
    # 4. Strategic Advisory Memo (Board-Level Governance & Risk)
    # ─────────────────────────────────────────────────────────────
    "strategic_memo": ArtifactBlueprint(
        id="strategic_memo",
        version="v2",
        role="Partner at Top-Tier Management Consultancy",
        audience="Board of Directors & Senior Executive Committee",
        target_audience="Board Members, Audit/Governance Committees, and Senior Executive Officers",
        objective="Deliver rigorous strategic analysis, structural risk modeling, and defensible fiduciary options",
        communication_goal="Present a comprehensive scenario analysis and trade-off evaluation guiding fiduciary voting and long-term enterprise value protection.",
        desired_action="Board vote on recommended strategic option and authorization of capital governance framework.",
        reading_depth="Strategic",
        tone="Analytical, Rigorous, Governance-Grade, Objective, Defensible",
        tone_profile="Senior management consulting partner voice. Unsparing analytical rigor, structured scenario tradeoffs, and clear fiduciary clarity.",
        writing_style="Formal strategy consulting memo, structured scenario analysis, multi-option tradeoff matrix",
        decision_focus="What are the structural risks, market implications, and strategic options for the board?",
        purpose="Board-Level Strategic Analysis",
        narrative_framework=[
            "Strategic Situation & Macro Context",
            "Governance & Operational Assessment",
            "Second-Order Financial & Market Implications",
            "Downside Risks & Regulatory Vulnerabilities",
            "Comparative Strategic Options Matrix (Option A vs Option B)",
            "Unambiguous Board Recommendation & Fiduciary Rationale",
        ],
        sections=[
            "Situation",
            "Assessment",
            "Implications",
            "Risks",
            "Strategic Options",
            "Recommendation",
        ],
        word_limit=700,
        style_rules=[
            "Frame macroeconomic, competitive, and regulatory drivers with analytical rigor.",
            "Quantify second-order implications on enterprise valuation, margin structure, and customer cohorts.",
            "Detail specific risks with likelihood, financial impact, and mitigation pathways.",
            "Contrast at least 2 distinct strategic options with explicit trade-offs before recommending a path.",
            "Deliver an unambiguous, defensible recommendation suitable for formal board adoption.",
        ],
        anti_patterns=[
            "Do NOT use social media casualness, informal idioms, or promotional copy.",
            "Do NOT omit downside risks or gloss over trade-offs.",
            "Do NOT use emojis, hashtags, or promotional hooks.",
            "Do NOT write vague, non-committal recommendations ('teams should look into it').",
        ],
        anti_ai_rules=GLOBAL_ANTI_AI_RULES + [
            "Never hedge with weak phrases like 'It might be beneficial to'. Use decisive consulting framing: 'The Board should mandate...'.",
        ],
        vocabulary_profile={
            "preferred": ["Fiduciary", "Valuation Multiple", "Margin Dilution", "Downside Sensitivity", "Tradeoff Matrix", "CapEx", "Governance"],
            "banned": ["delve", "tapestry", "landscape", "pivotal", "in conclusion"],
        },
        success_criteria=[
            "Board members can evaluate fiduciary liabilities and vote on strategic pathways.",
            "All 6 governance sections are thoroughly articulated with quantitative evidence.",
            "Completely free of marketing hype and social tone.",
        ],
        card_display_mode="strategic",
        golden_file="strategic_memo.md",
    ),

    # ─────────────────────────────────────────────────────────────
    # 5. Research Report (Evidence-Based Deep Dive)
    # ─────────────────────────────────────────────────────────────
    "research_report": ArtifactBlueprint(
        id="research_report",
        version="v2",
        role="Principal Industry Research Analyst",
        audience="Domain Experts, Technical Architects, and Quantitative Analysts",
        target_audience="Senior research analysts, quantitative strategists, technical decision-makers, and institutional investors",
        objective="Deliver evidence-based empirical synthesis and analytical methodology",
        communication_goal="Provide an unassailable empirical breakdown of source evidence with explicit methodology, data findings, and analytical boundaries.",
        desired_action="Incorporate findings into quantitative models, technical roadmaps, or investment theses.",
        reading_depth="Deep-Dive",
        tone="Scholarly, Empirical, Systematic, Thorough, Precise",
        tone_profile="Peer-reviewed research and institutional analyst voice. Methodologically exhaustive, precise, and epistemically humble.",
        writing_style="Academic research structure, explicit methodology documentation, cited evidence synthesis, analytical boundaries",
        decision_focus="What does the empirical source evidence rigorously prove?",
        purpose="Empirical Research Synthesis",
        narrative_framework=[
            "Research Background & Problem Perimeter",
            "Analytical Methodology & Data Bounds",
            "Empirical Findings & Data Synthesis",
            "Comparative Analysis & 2nd-Order Mechanisms",
            "Empirical Conclusions & Scope Limits",
            "Ground-Truth References & Citations",
        ],
        sections=[
            "Background",
            "Methodology",
            "Findings",
            "Analysis",
            "Conclusions",
            "References",
        ],
        word_limit=850,
        style_rules=[
            "Anchor all findings to explicit empirical facts, data points, and coordinate citations.",
            "Document analytical methodology, sampling bounds, and evaluation criteria explicitly.",
            "Strictly separate raw findings from interpretive analytical synthesis.",
            "Provide formal cross-references to extracted ground truth coordinates.",
        ],
        anti_patterns=[
            "Do NOT use marketing language, sales pitches, or unsubstantiated opinions.",
            "Do NOT make speculative claims without citing source spans.",
            "Do NOT use conversational social slang or informal register.",
        ],
        anti_ai_rules=GLOBAL_ANTI_AI_RULES,
        vocabulary_profile={
            "preferred": ["Empirical", "Methodology", "Statistical Significance", "Coordinate Recall", "Variance", "Systematic", "Precision"],
            "banned": ["delve", "tapestry", "beacon", "in today's world"],
        },
        success_criteria=[
            "An analyst can independently verify all empirical claims against source references.",
            "Methodology and findings sections are separated and exhaustively detailed.",
            "Zero promotional bias or unsupported assertions.",
        ],
        card_display_mode="research",
        golden_file="research_report.md",
    ),

    # ─────────────────────────────────────────────────────────────
    # 6. Policy Memo (Governance Framework)
    # ─────────────────────────────────────────────────────────────
    "policy_memo": ArtifactBlueprint(
        id="policy_memo",
        version="v2",
        role="Senior Policy & Compliance Counsel",
        audience="Executive Leadership & Governance Committees",
        target_audience="General Counsel, Chief Compliance Officer, and Risk Governance Committees",
        objective="Establish a defensible policy decision framework",
        communication_goal="Formulate a compliant, audit-ready governance perimeter balancing operational speed against regulatory risk.",
        desired_action="Adopt formal organizational policy and mandate departmental compliance auditing.",
        reading_depth="Strategic",
        tone="Pragmatic, Balanced, Compliance-Aligned, Framework-Oriented",
        tone_profile="Senior regulatory and compliance counsel voice. Precise, risk-weighted, and audit-proof.",
        writing_style="Structured tradeoff matrix, regulatory compliance mapping, multi-option comparative evaluation",
        decision_focus="What regulatory, ethical, and operational trade-offs govern this policy choice?",
        purpose="Governance & Policy Decision Framework",
        narrative_framework=[
            "Governance Issue & Statutory Scope",
            "Operational & Regulatory Context",
            "Structured Policy Options (Option 1 vs Option 2)",
            "Comparative Tradeoffs & Risk Exposures",
            "Defensible Governance Recommendation",
        ],
        sections=[
            "Issue",
            "Context",
            "Policy Options",
            "Tradeoffs",
            "Recommendation",
        ],
        word_limit=650,
        style_rules=[
            "Frame the central governance issue with precise operational scope and regulatory boundaries.",
            "Outline at least two viable policy options with distinct risk profiles.",
            "Systematically contrast tradeoffs across cost, compliance, speed, and security.",
            "Provide a defensible, risk-weighted policy recommendation.",
        ],
        anti_patterns=[
            "Do NOT advocate a single option without assessing realistic alternatives.",
            "Do NOT use biased, partisan, or emotional rhetoric.",
            "Do NOT ignore compliance vulnerabilities or regulatory perimeters.",
        ],
        anti_ai_rules=GLOBAL_ANTI_AI_RULES,
        vocabulary_profile={
            "preferred": ["Compliance Perimeter", "Statutory Scope", "Audit-Ready", "Governance", "Exposure", "Liability", "Mitigation"],
            "banned": ["delve", "tapestry", "landscape", "pivotal"],
        },
        success_criteria=[
            "Governance committee has a defensible, audit-ready policy rationale.",
            "Tradeoffs are balanced across multiple compliance dimensions.",
        ],
        card_display_mode="policy",
        golden_file="policy_memo.md",
    ),

    # ─────────────────────────────────────────────────────────────
    # 7. Presentation Deck Spec (Slide-By-Slide Architecture)
    # ─────────────────────────────────────────────────────────────
    "presentation": ArtifactBlueprint(
        id="presentation",
        version="v2",
        role="Executive Presentation Designer & Storyteller",
        audience="Conference Attendees, Investors, and Leadership Audiences",
        target_audience="Executive audiences, conference delegates, and investment committees expecting visual scanability",
        objective="Structure source insights into an actionable executive slide deck outline",
        communication_goal="Sequence source intelligence into a slide-by-slide architecture with explicit visual concepts and scan-optimized takeaway bullets.",
        desired_action="Present slide deck to executive stakeholders or convert directly into PPTX slides.",
        reading_depth="Scan-Optimized",
        tone="Crisp, Structured, Visual-First, Memorable, Hierarchical",
        tone_profile="High-impact visual presentation designer voice. Brief, structured, visual, and punchy.",
        writing_style="Slide-by-slide modular architecture, explicit visual concepts, bullet brevity constrained under 12 words",
        decision_focus="How do we visually sequence ideas for maximum audience comprehension and impact?",
        purpose="Executive Deck Specification",
        narrative_framework=[
            "Slide 1: Title & Core Thesis (Why It Matters)",
            "Slide 2: Strategic Context & Friction (The Core Problem)",
            "Slide 3: Key Data & Evidence Architecture (Validated Proof)",
            "Slide 4: Solution Architecture & Capabilities (The Breakthrough)",
            "Slide 5: Execution Roadmap & Phased Timeline (Execution Steps)",
        ],
        sections=[
            "Slide 1: Title & Core Thesis",
            "Slide 2: Strategic Context",
            "Slide 3: Key Data & Evidence",
            "Slide 4: Solution Architecture",
            "Slide 5: Execution Roadmap",
        ],
        word_limit=450,
        style_rules=[
            "Organize each slide with a Slide Title, Visual Concept layout description, and 3 Bullet Takeaways.",
            "Keep slide bullet points strictly under 12 words for presentation scanability.",
            "Sequence ideas logically from context to data, architecture, and timeline.",
        ],
        anti_patterns=[
            "Do NOT write long narrative paragraphs on slides.",
            "Do NOT overwhelm slides with dense text walls or multi-clause sentences.",
            "Do NOT omit visual concept instructions for each slide.",
        ],
        anti_ai_rules=GLOBAL_ANTI_AI_RULES,
        vocabulary_profile={
            "preferred": ["Core Thesis", "Visual Layout", "Takeaway", "Milestone", "Roadmap", "Architecture"],
            "banned": ["delve", "tapestry", "furthermore", "moreover"],
        },
        success_criteria=[
            "A designer can immediately assemble PowerPoint or Keynote slides from the spec.",
            "Each slide has distinct visual concepts and concise bullet takeaways.",
        ],
        card_display_mode="standard",
        golden_file="presentation.md",
    ),

    # ─────────────────────────────────────────────────────────────
    # 8. Infographic Content Blueprint
    # ─────────────────────────────────────────────────────────────
    "infographic": ArtifactBlueprint(
        id="infographic",
        version="v2",
        role="Information Architect & Data Visualizer",
        audience="Visual Learners, Stakeholders, and Cross-Functional Teams",
        target_audience="Cross-functional stakeholders and visual learners seeking instant data clarity",
        objective="Extract vital statistics, comparative graphs, and flow steps for visual layout",
        communication_goal="Transform dense source metrics into a visual blueprint with a hero statistic, core data points, comparative breakdowns, and process steps.",
        desired_action="Hand off spec to graphic design team for direct visual layout assembly.",
        reading_depth="Scan-Optimized",
        tone="Visual, Data-Centric, Modular, Crisp, Clear",
        tone_profile="Information design architect voice. Modular, quantitative, and graphic-oriented.",
        writing_style="Hero metric callouts, quantitative data points, numbered sequential flow steps, modular visual layout",
        decision_focus="How can key metrics and relationships be grasped at a single glance?",
        purpose="Data Visualization Spec",
        narrative_framework=[
            "Hero Statistic Callout",
            "Core Data Points & Metrics",
            "Comparative Breakdown Matrix",
            "Numbered Sequential Process Flow",
            "Central Strategic Takeaway",
        ],
        sections=[
            "Hero Statistic",
            "Core Data Points",
            "Comparative Breakdown",
            "Process Flow Steps",
            "Key Takeaway",
        ],
        word_limit=350,
        style_rules=[
            "Format hero statistics with prominent numbers and short contextual labels.",
            "Organize process steps into numbered sequential stages (Step 1, Step 2, Step 3).",
            "Structure comparative data points in clean contrast pairs.",
        ],
        anti_patterns=[
            "Do NOT write long continuous prose or essay paragraphs.",
            "Do NOT include text without accompanying numerical or graphical anchors.",
        ],
        anti_ai_rules=GLOBAL_ANTI_AI_RULES,
        vocabulary_profile={
            "preferred": ["Hero Metric", "Benchmark", "Workflow", "Comparative", "Takeaway"],
            "banned": ["delve", "tapestry", "in conclusion", "furthermore"],
        },
        success_criteria=[
            "An information designer can build an infographic layout directly from the spec.",
            "Contains prominent hero stats, structured data points, and numbered flow steps.",
        ],
        card_display_mode="standard",
        golden_file="infographic.md",
    ),

    # ─────────────────────────────────────────────────────────────
    # 9. Market Newsletter Digest
    # ─────────────────────────────────────────────────────────────
    "newsletter": ArtifactBlueprint(
        id="newsletter",
        version="v2",
        role="Chief Newsletter Editor & Industry Curator",
        audience="Subscribers, Industry Practitioners, and Decision Makers",
        target_audience="Senior operators, technology executives, and industry subscribers seeking high-signal weekly curation",
        objective="Deliver a high-signal curated weekly digest with editorial analysis",
        communication_goal="Engage subscribers with a sharp editorial thesis, data-driven main feature, standout stat, and concrete weekly action item.",
        desired_action="Click through to full analysis, share newsletter, and execute the weekly action item.",
        reading_depth="Conversational",
        tone="Curated, Accessible, Engaging, Informative, Analytical",
        tone_profile="Top-tier industry newsletter author voice (think Stratechery / The Information). Crisp, analytical, and engaging.",
        writing_style="Editorial note framing, deep-dive main feature, data spotlight, practical industry action items",
        decision_focus="What are the essential market developments readers need to know this week?",
        purpose="Curated Industry Digest",
        narrative_framework=[
            "Editor Note & Core Thesis",
            "Main Feature & Analytical Synthesis",
            "Data Spotlight (Surprising Stat)",
            "Industry Implication & Trend Impact",
            "Immediate Practitioner Action Item",
        ],
        sections=[
            "Editor Note",
            "Main Feature",
            "Data Spotlight",
            "Industry Implication",
            "Action Item",
        ],
        word_limit=550,
        style_rules=[
            "Open with a brief, punchy editorial note framing the core theme.",
            "Break down the main feature with clear subheadings and highlighted takeaways.",
            "Include a designated Data Spotlight block highlighting a surprising fact.",
            "End with an actionable takeaway for practitioners.",
        ],
        anti_patterns=[
            "Do NOT sound like dry legal compliance documentation or academic papers.",
            "Do NOT use formal press release wire formats or corporate disclaimers.",
        ],
        anti_ai_rules=GLOBAL_ANTI_AI_RULES,
        vocabulary_profile={
            "preferred": ["Editor Note", "Data Spotlight", "Takeaway", "Implication", "Playbook", "Signal"],
            "banned": ["delve", "tapestry", "in conclusion", "it is important to note"],
        },
        success_criteria=[
            "Subscribers read the newsletter with high engagement and clear takeaways.",
            "Editorial tone is engaging while preserving strict factual accuracy.",
        ],
        card_display_mode="standard",
        golden_file="newsletter.md",
    ),

    # ─────────────────────────────────────────────────────────────
    # 10. Twitter / X Thread
    # ─────────────────────────────────────────────────────────────
    "twitter_x": ArtifactBlueprint(
        id="twitter_x",
        version="v2",
        role="Viral Social Strategist & Tech Educator",
        audience="Tech Community, Founders, Engineers, and General Public",
        target_audience="Tech community, founders, developers, and practitioners browsing fast-paced social feeds",
        objective="Disseminate key facts in an informative, step-by-step thread format",
        communication_goal="Hook readers with a compelling thread premise, explain the core problem, reveal the breakthrough with proof, and drive bookmarks and retweets.",
        desired_action="Retweet, bookmark, follow, and read linked documentation.",
        reading_depth="Scan-Optimized",
        tone="Punchy, Educational, Fast-Paced, High-Signal, Engaging",
        tone_profile="Viral high-signal tech educator voice. Short lines, numbered tweets, compelling hooks, and punchy data proof.",
        writing_style="Numbered tweet thread (1/5, 2/5, etc.), 280-character bounded micro-posts, crisp line breaks, viral hook",
        decision_focus="How do we break down complex insights into a viral, high-value thread?",
        purpose="Viral High-Signal Thread",
        narrative_framework=[
            "Tweet 1: The Viral Hook (Underlying Tension)",
            "Tweet 2: The Core Problem (Why Old Ways Fail)",
            "Tweet 3: The Breakthrough (New Architecture/Insight)",
            "Tweet 4: The Empirical Proof & Data",
            "Tweet 5: The Big Takeaway & Bookmark Call to Action",
        ],
        sections=[
            "Tweet 1: The Hook",
            "Tweet 2: The Core Problem",
            "Tweet 3: The Breakthrough",
            "Tweet 4: The Proof & Data",
            "Tweet 5: The Big Takeaway",
        ],
        word_limit=280,
        style_rules=[
            "Number each tweet sequentially (1/5, 2/5, etc.).",
            "Keep each individual tweet strictly under 280 characters with crisp line breaks.",
            "Lead with a compelling hook tweet and conclude with a bookmark-worthy takeaway.",
        ],
        anti_patterns=[
            "Do NOT write single massive paragraphs or continuous essays.",
            "Do NOT use corporate buzzwords, legal disclaimers, or formal headers.",
        ],
        anti_ai_rules=GLOBAL_ANTI_AI_RULES,
        vocabulary_profile={
            "preferred": ["Thread", "Breakdown", "Trap", "Breakthrough", "Takeaway", "Bookmark"],
            "banned": ["in conclusion", "furthermore", "delve", "tapestry", "beacon"],
        },
        success_criteria=[
            "Thread format is immediately readable on social feeds.",
            "Tweets are sequentially numbered with high informational density.",
        ],
        card_display_mode="social",
        golden_file="twitter_x.md",
    ),

    # ─────────────────────────────────────────────────────────────
    # 11. Video Package Script
    # ─────────────────────────────────────────────────────────────
    "video_package": ArtifactBlueprint(
        id="video_package",
        version="v2",
        role="Executive Video Producer & Scriptwriter",
        audience="Video Viewers, YouTube & Webinar Audiences",
        target_audience="Webinar attendees, YouTube viewers, and enterprise prospects consuming audiovisual media",
        objective="Provide a two-column video production script with visual cues and voiceover",
        communication_goal="Synchronize high-impact visual cues with conversational spoken narration across a 5-scene retention-optimized video script.",
        desired_action="Video production handoff for immediate filming and motion graphic animation.",
        reading_depth="Scan-Optimized",
        tone="Dynamic, Audiovisual, Structured, Pacing-Conscious",
        tone_profile="Executive video producer voice. Clean timing cues, dynamic visuals, and natural conversational cadence.",
        writing_style="Scene-by-scene script with synchronized [VISUAL CUE] and [VOICEOVER / AUDIO] timing instructions",
        decision_focus="How do we combine visual cues and spoken narration for high viewer retention?",
        purpose="Audiovisual Production Script",
        narrative_framework=[
            "Scene 1: Visual Hook (0:00 - 0:15)",
            "Scene 2: Problem Statement & Friction (0:15 - 0:40)",
            "Scene 3: Solution Showcase & Capabilities (0:40 - 1:10)",
            "Scene 4: Supporting Evidence & Metrics (1:10 - 1:35)",
            "Scene 5: Outro & Clear Call to Action (1:35 - 1:50)",
        ],
        sections=[
            "Scene 1: Visual Hook",
            "Scene 2: Problem Statement",
            "Scene 3: Solution Showcase",
            "Scene 4: Supporting Evidence",
            "Scene 5: Outro & Call to Action",
        ],
        word_limit=500,
        style_rules=[
            "Format each scene with synchronized [VISUAL CUE] and [VOICEOVER / AUDIO] blocks.",
            "Include approximate timing markers per scene (e.g. 0:00 - 0:15).",
            "Ensure spoken voiceover matches natural conversational pacing.",
        ],
        anti_patterns=[
            "Do NOT write monologue text without visual instructions.",
            "Do NOT write continuous prose without scene subdivisions.",
        ],
        anti_ai_rules=GLOBAL_ANTI_AI_RULES,
        vocabulary_profile={
            "preferred": ["VISUAL CUE", "VOICEOVER", "TIMING", "Motion Graphic", "Outro", "Demo"],
            "banned": ["delve", "tapestry", "in conclusion", "furthermore"],
        },
        success_criteria=[
            "Video editors and voice actors have precise, synchronized production cues.",
            "Every scene features clear visual and audio directions.",
        ],
        card_display_mode="standard",
        golden_file="video_package.md",
    ),
}

# Aliases mapping legacy output_type keys to canonical blueprints
BLUEPRINT_ALIASES: dict[str, str] = {
    "executive_summary": "executive_briefing",
    "advisory": "strategic_memo",
    "twitter_post": "twitter_x",
    "research": "research_report",
    "policy": "policy_memo",
}


def get_blueprint(output_type: str) -> ArtifactBlueprint:
    """
    Retrieve the versioned ArtifactBlueprint for an output type key,
    supporting canonical names and legacy aliases.
    """
    canonical_key = BLUEPRINT_ALIASES.get(output_type, output_type)
    if canonical_key in BLUEPRINT_REGISTRY:
        return BLUEPRINT_REGISTRY[canonical_key]

    # Dynamic fallback blueprint if an unknown type is requested
    clean_title = output_type.replace("_", " ").title()
    return ArtifactBlueprint(
        id=output_type,
        version="v2",
        role=f"{clean_title} Specialist",
        audience="Target Stakeholders",
        target_audience="Target Stakeholders and Decision Makers",
        objective=f"Synthesize verified intelligence into a high-quality {clean_title}.",
        communication_goal=f"Deliver a clear, actionable {clean_title} grounded in source facts.",
        desired_action="Review findings and execute relevant next steps.",
        reading_depth="Strategic",
        tone="Professional, structured, grounded",
        tone_profile="Professional and concise.",
        writing_style="Structured section-driven domain synthesis",
        decision_focus="What key insights and actions must be communicated?",
        purpose=f"{clean_title} Synthesis",
        sections=["Executive Summary", "Key Findings", "Strategic Analysis", "Recommendations"],
        word_limit=500,
        style_rules=["Use clear subheadings and grounded citations."],
        anti_patterns=["Do not invent facts not grounded in source material."],
        anti_ai_rules=GLOBAL_ANTI_AI_RULES,
        success_criteria=[f"Delivers a coherent, grounded {clean_title}."],
        card_display_mode="standard",
        golden_file="executive_briefing.md",
    )

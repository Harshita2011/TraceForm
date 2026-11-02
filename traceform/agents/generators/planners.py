"""
# Artifact Intelligence Layer — Artifact Planners Engine
#
# Dedicated planner agents for every artifact format.
# Before writing begins, each planner constructs:
#   1. Audience Model (Target Persona, Cognitive Load, Consumption Context)
#   2. Communication Goal (Primary Outcome & Mindset Shift)
#   3. Output Structure (Native Format Hierarchy)
#   4. Reasoning Path (Logic Flow & Mental Model)
#   5. Narrative Strategy (Pacing, Information Density, Tone)
#   6. Writing Blueprint (Sentence Rhythm, Vocabulary, Anti-Patterns)
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from agents.analyst.insight_graph import EvidenceAndInsightGraph, InsightNode


class AudienceModel(BaseModel):
    """Deep model of the target reader consuming the artifact."""
    persona: str
    decision_mandate: str
    cognitive_load: str  # "Scan-Only (30s)", "Executive-BLUF (2m)", "Deep-Study (15m)", "Mobile-Feed (15s)"
    technical_depth: str # "High", "Strategic-Only", "Layperson-Accessible", "Board-Level"
    primary_question: str # The single question the reader asks when opening the document


class CommunicationGoal(BaseModel):
    """Specific measurable outcome of the artifact."""
    objective: str
    desired_mindset_shift: str
    action_or_decision: str
    engagement_type: str  # "Decision-Approval", "Public-Awareness", "Social-Discussion", "Technical-Adoption"


class WritingBlueprint(BaseModel):
    """Stylistic and structural instructions for the generator."""
    writing_style: str
    sentence_cadence: str
    vocabulary_register: str
    mandatory_sections: list[str]
    forbidden_tropes: list[str]
    formatting_requirements: list[str]


class ArtifactPlan(BaseModel):
    """Complete pre-generation intelligence plan produced by an Artifact Planner."""
    artifact_type: str
    audience_model: AudienceModel
    communication_goal: CommunicationGoal
    native_structure: list[str]
    reasoning_path: list[str]
    narrative_strategy: str
    writing_blueprint: WritingBlueprint
    selected_insight_ids: list[str] = Field(default_factory=list)

    def render_prompt_instructions(self) -> str:
        """Render markdown prompt block for generator injection."""
        sections_fmt = "\n".join(f"  {idx+1}. {s}" for idx, s in enumerate(self.native_structure))
        reasoning_fmt = " -> ".join(self.reasoning_path)
        forbidden_fmt = "\n".join(f"  - {f}" for f in self.writing_blueprint.forbidden_tropes)
        formatting_fmt = "\n".join(f"  - {fmt}" for fmt in self.writing_blueprint.formatting_requirements)

        return (
            f"=== ARTIFACT INTELLIGENCE PLAN [{self.artifact_type.upper()}] ===\n"
            f"TARGET AUDIENCE: {self.audience_model.persona}\n"
            f"PRIMARY READER QUESTION: '{self.audience_model.primary_question}'\n"
            f"COGNITIVE LOAD BUDGET: {self.audience_model.cognitive_load} | DEPTH: {self.audience_model.technical_depth}\n"
            f"COMMUNICATION OBJECTIVE: {self.communication_goal.objective}\n"
            f"DESIRED ACTION/DECISION: {self.communication_goal.action_or_decision}\n"
            f"NARRATIVE REASONING PATH: {reasoning_fmt}\n"
            f"NARRATIVE STRATEGY: {self.narrative_strategy}\n\n"
            f"MANDATORY NATIVE STRUCTURE (Use these EXACT Markdown ## headers):\n{sections_fmt}\n\n"
            f"NATIVE FORMATTING RULES:\n{formatting_fmt}\n\n"
            f"FORBIDDEN BLEED & TROPES:\n{forbidden_fmt}\n"
            f"==============================================================="
        )


# ─────────────────────────────────────────────────────────────────────────────
# Planner Implementations
# ─────────────────────────────────────────────────────────────────────────────

def plan_linkedin_post(graph: EvidenceAndInsightGraph) -> ArtifactPlan:
    return ArtifactPlan(
        artifact_type="linkedin_post",
        audience_model=AudienceModel(
            persona="Professionals, Founders, Managers, and Enterprise Operators on LinkedIn feed",
            decision_mandate="Seeking actionable industry insights, tactical lessons, and thoughtful discussion",
            cognitive_load="Mobile-Feed (45-60s)",
            technical_depth="Strategic-Only (No dense equations; high clarity)",
            primary_question="What counter-intuitive industry truth or operating insight can I apply immediately?",
        ),
        communication_goal=CommunicationGoal(
            objective="Generate high-value professional engagement and drive thoughtful peer discussion",
            desired_mindset_shift="From conventional assumption to sharp, differentiated reality",
            action_or_decision="Engage with the post, share with teams, and adapt their operating playbook",
            engagement_type="Social-Discussion",
        ),
        native_structure=[
            "Hook",
            "Problem",
            "Key Insight",
            "Supporting Story",
            "Takeaways",
            "Call To Action",
        ],
        reasoning_path=["Provocative Hook", "Hidden Friction/Problem", "Differentiated Insight", "Concrete Evidence Story", "3 Bulleted Takeaways", "Conversation CTA"],
        narrative_strategy="Conversational yet authoritative thought leadership. Uses short paragraph bursts (1-2 sentences), whitespace, and a powerful punchy hook.",
        writing_blueprint=WritingBlueprint(
            writing_style="Hook-Story-Lesson-CTA",
            sentence_cadence="Punchy, line-broken cadence optimized for mobile feed readability.",
            vocabulary_register="Modern operator vocabulary (e.g., 'playbook', 'velocity', 'unit economics', 'bottleneck').",
            mandatory_sections=["Hook", "Problem", "Key Insight", "Supporting Story", "Takeaways", "Call To Action"],
            forbidden_tropes=[
                "Never write like a corporate press release or academic report.",
                "Never use formal memo headers or bureaucratic language.",
                "Never use generic hashtags like #AI #Success #Blessed; use focused domain tags if any.",
                "Never open with 'I am excited to announce...' or 'In today's fast-paced world...'.",
            ],
            formatting_requirements=[
                "Start with a 1-2 line irresistible hook with a line break.",
                "Use bullet points for the 3 key takeaways.",
                "End with an open-ended engagement question driving comments.",
            ],
        ),
        selected_insight_ids=[n.id for n in graph.insight_nodes[:3]],
    )


def plan_twitter_x(graph: EvidenceAndInsightGraph) -> ArtifactPlan:
    return ArtifactPlan(
        artifact_type="twitter_x",
        audience_model=AudienceModel(
            persona="X/Twitter Tech & Business Audience, Analysts, Tech Enthusiasts",
            decision_mandate="Rapid knowledge consumption and retweet/bookmark curation",
            cognitive_load="Mobile-Feed (30s skimmable thread)",
            technical_depth="High-Impact Punchy Points",
            primary_question="What is the 10x takeaway distilled into 5 tweets?",
        ),
        communication_goal=CommunicationGoal(
            objective="Maximize viral shares, bookmarks, and fast transmission of key findings",
            desired_mindset_shift="Instant recognition of a critical breakthrough or strategic shift",
            action_or_decision="Retweet, bookmark thread, follow for domain analysis",
            engagement_type="Public-Viral",
        ),
        native_structure=[
            "1/n Hook",
            "2/n Context",
            "3/n Insight",
            "4/n Supporting Insight",
            "5/n Actionable Takeaway",
        ],
        reasoning_path=["1/n Curiosity Gap Hook", "2/n Baseline Context", "3/n Core Breakthrough Insight", "4/n Concrete Metric Evidence", "5/n Actionable Playbook Takeaway"],
        narrative_strategy="High-energy, information-dense, numbered thread with zero fluff. Every tweet must stand on its own as a screenshot-worthy insight.",
        writing_blueprint=WritingBlueprint(
            writing_style="Numbered X Thread (1/n format)",
            sentence_cadence="Ultra-crisp, short statements with curiosity gaps and bolded anchors.",
            vocabulary_register="Sharp, viral tech/business analysis register.",
            mandatory_sections=["1/n Hook", "2/n Context", "3/n Insight", "4/n Supporting Insight", "5/n Actionable Takeaway"],
            forbidden_tropes=[
                "Never write multi-paragraph walls of text.",
                "Never forget the '1/n', '2/n' tweet numbering prefixes.",
                "Never use passive corporate language.",
            ],
            formatting_requirements=[
                "Format strictly as 5 distinct numbered tweets (1/n through 5/n).",
                "Keep each tweet under 280 characters.",
                "Include concrete metrics and key entity names in tweets 3 and 4.",
            ],
        ),
        selected_insight_ids=[n.id for n in graph.insight_nodes[:3]],
    )


def plan_executive_summary(graph: EvidenceAndInsightGraph) -> ArtifactPlan:
    return ArtifactPlan(
        artifact_type="executive_summary",
        audience_model=AudienceModel(
            persona="CEO, VP, General Manager, Senior Leadership",
            decision_mandate="Requires rapid decision support and immediate bottom-line impact",
            cognitive_load="Executive-BLUF (2m max reading time, 1 page limit)",
            technical_depth="Executive-Strategic (High business signal, zero implementation minutiae)",
            primary_question="What is the bottom-line business impact and what decision must we make?",
        ),
        communication_goal=CommunicationGoal(
            objective="Enable rapid, high-confidence resource and strategy decisions in under 2 minutes",
            desired_mindset_shift="From ambiguity to total clarity on priority, risk, and ROI",
            action_or_decision="Approve recommendations and assign operational execution teams",
            engagement_type="Decision-Approval",
        ),
        native_structure=[
            "Key Findings",
            "Business Impact",
            "Risks",
            "Recommendations",
            "Next Steps",
        ],
        reasoning_path=["Bottom-Line Findings (BLUF)", "Financial & Operational Impact", "Critical Exposure & Risks", "Prioritized Recommendations", "30-Day Next Steps"],
        narrative_strategy="Bottom-Line-Up-Front (BLUF). Direct, objective, numbers-backed synthesis. Max 1 page.",
        writing_blueprint=WritingBlueprint(
            writing_style="BLUF Executive Briefing",
            sentence_cadence="Concise, declarative sentences led by quantifiable business metrics.",
            vocabulary_register="C-Suite executive register (e.g. 'capital allocation', 'margin impact', 'exposure', 'governance').",
            mandatory_sections=["Key Findings", "Business Impact", "Risks", "Recommendations", "Next Steps"],
            forbidden_tropes=[
                "Never exceed 1 page (keep strictly under 450 words).",
                "Never write open-ended conversational musings.",
                "Never bury the lead in the second paragraph.",
            ],
            formatting_requirements=[
                "Bold every critical metric or entity.",
                "Use bulleted lists under Risks and Recommendations for rapid scanning.",
                "Conclude with explicit, time-bound Next Steps.",
            ],
        ),
        selected_insight_ids=[n.id for n in graph.insight_nodes[:4]],
    )


def plan_executive_briefing(graph: EvidenceAndInsightGraph) -> ArtifactPlan:
    return ArtifactPlan(
        artifact_type="executive_briefing",
        audience_model=AudienceModel(
            persona="CEO / C-Suite Officer preparing for immediate strategic action",
            decision_mandate="Immediate situational awareness and tactical orientation",
            cognitive_load="Scan-Optimized BLUF (90 seconds)",
            technical_depth="Strategic-Operational",
            primary_question="What must leadership know and act on right now?",
        ),
        communication_goal=CommunicationGoal(
            objective="Equip CEO with immediate situational intelligence for imminent meetings and decisions",
            desired_mindset_shift="Instant grasp of operational urgency and strategic leverage points",
            action_or_decision="Issue executive directives and mobilize operational leads",
            engagement_type="Executive-Directive",
        ),
        native_structure=[
            "Situation",
            "Why It Matters",
            "Critical Developments",
            "Strategic Risks",
            "Recommended Actions",
        ],
        reasoning_path=["Current Situation", "Why It Matters (Core Stakeholder Impact)", "Critical Developments", "Strategic Risks", "Recommended Immediate Actions"],
        narrative_strategy="Crisp military/intelligence briefing style. High signal-to-noise ratio.",
        writing_blueprint=WritingBlueprint(
            writing_style="Intelligence Briefing Format",
            sentence_cadence="Crisp, telegraphic, high-density statements.",
            vocabulary_register="Executive leadership vocabulary.",
            mandatory_sections=["Situation", "Why It Matters", "Critical Developments", "Strategic Risks", "Recommended Actions"],
            forbidden_tropes=[
                "Never use conversational transitions or throat-clearing openings.",
                "Never include long narrative backstories.",
            ],
            formatting_requirements=[
                "Use the 5 exact mandatory headers.",
                "Include specific risks and direct recommended actions.",
            ],
        ),
        selected_insight_ids=[n.id for n in graph.insight_nodes[:4]],
    )


def plan_strategic_memo(graph: EvidenceAndInsightGraph) -> ArtifactPlan:
    return ArtifactPlan(
        artifact_type="strategic_memo",
        audience_model=AudienceModel(
            persona="Board of Directors, Executive Committee, Strategy Leads",
            decision_mandate="Multi-year strategy, capital allocation, and risk management governance",
            cognitive_load="Deep-Study (10-15m reading time)",
            technical_depth="Comprehensive Strategic & Financial Rigor (McKinsey / Bain / BCG caliber)",
            primary_question="What is the comprehensive strategic, competitive, and economic thesis for our organization?",
        ),
        communication_goal=CommunicationGoal(
            objective="Present an unassailable strategic analysis and multi-phase implementation roadmap",
            desired_mindset_shift="From short-term tactical thinking to structured, long-term competitive advantage",
            action_or_decision="Board ratification of strategic recommendations and multi-quarter resource commitment",
            engagement_type="Board-Governance",
        ),
        native_structure=[
            "Executive Context",
            "Strategic Analysis",
            "Market Implications",
            "Competitive Analysis",
            "Business Risks",
            "Growth Opportunities",
            "Strategic Recommendations",
            "Implementation Roadmap",
        ],
        reasoning_path=[
            "Executive Context & Baseline",
            "Core Strategic Analysis",
            "Market Dynamics & Shifts",
            "Competitive Moats & Threats",
            "Quantified Business Risks",
            "High-Conviction Growth Vectors",
            "Prioritized Strategic Recommendations",
            "Phased Implementation Roadmap (0-30d, 30-90d, 90-180d)",
        ],
        narrative_strategy="Top-tier management consulting advisory paper. Rigorous, structured (Pyramid Principle), highly analytical.",
        writing_blueprint=WritingBlueprint(
            writing_style="McKinsey/Bain Management Consulting Memo",
            sentence_cadence="Formal, highly articulate, analytical sentences with structured parallel arguments.",
            vocabulary_register="Strategy consulting lexicon (e.g. 'strategic moat', 'structural headwind', 'TAM expansion', 'capital efficiency', 'asymmetric upside').",
            mandatory_sections=[
                "Executive Context",
                "Strategic Analysis",
                "Market Implications",
                "Competitive Analysis",
                "Business Risks",
                "Growth Opportunities",
                "Strategic Recommendations",
                "Implementation Roadmap",
            ],
            forbidden_tropes=[
                "Never write casual or conversational text.",
                "Never omit the phased Implementation Roadmap.",
                "Never make assertions without analytical backing.",
            ],
            formatting_requirements=[
                "Strictly follow the 8 consulting sections.",
                "Break implementation into explicit phases (Phase 1: Immediate, Phase 2: Scaling, Phase 3: Long-term).",
            ],
        ),
        selected_insight_ids=[n.id for n in graph.insight_nodes],
    )


def plan_press_release(graph: EvidenceAndInsightGraph) -> ArtifactPlan:
    return ArtifactPlan(
        artifact_type="press_release",
        audience_model=AudienceModel(
            persona="Journalists, Media Editors, Industry Analysts, Public Stakeholders",
            decision_mandate="Evaluating story newsworthiness, editorial quoting, and wire distribution",
            cognitive_load="Scan-Optimized Journalistic (2m)",
            technical_depth="Public-Accessible (AP Style wire standard)",
            primary_question="What is the major announcement, why does it matter, and who is the official spokesperson?",
        ),
        communication_goal=CommunicationGoal(
            objective="Secure positive media pickup and establish authoritative public record",
            desired_mindset_shift="Recognition of major organizational milestone or market milestone",
            action_or_decision="Publish articles, schedule media interviews, syndicate announcement",
            engagement_type="Media-Syndication",
        ),
        native_structure=[
            "Headline",
            "Subheadline",
            "Announcement",
            "Supporting Details",
            "Executive Quote",
            "Additional Information",
            "Company Boilerplate",
        ],
        reasoning_path=["Wire Dateline Headline", "Subheadline Summary", "Lead Announcement (Who/What/When/Where)", "Supporting Evidence Details", "Attributed Executive Quote", "Contextual Information", "Standard About Boilerplate"],
        narrative_strategy="Standard AP Wire corporate press release. Inverted pyramid news structure.",
        writing_blueprint=WritingBlueprint(
            writing_style="AP Wire Press Release",
            sentence_cadence="Objective, journalistic third-person voice.",
            vocabulary_register="Corporate communications standard.",
            mandatory_sections=["Headline", "Subheadline", "Announcement", "Supporting Details", "Executive Quote", "Additional Information", "Company Boilerplate"],
            forbidden_tropes=[
                "Never write in first person outside of the executive quote.",
                "Never omit the executive quote or company boilerplate.",
                "Never use internal jargon or confidential references.",
            ],
            formatting_requirements=[
                "Include a bold dateline (e.g. '[CITY, STATE] — [DATE] —').",
                "Include a realistic, impactful quote attributed to an executive.",
                "Conclude with an 'About [Organization]' boilerplate and media contact placeholder.",
            ],
        ),
        selected_insight_ids=[n.id for n in graph.insight_nodes[:3]],
    )


def plan_newsletter(graph: EvidenceAndInsightGraph) -> ArtifactPlan:
    return ArtifactPlan(
        artifact_type="newsletter",
        audience_model=AudienceModel(
            persona="Dedicated Subscribers, Industry Professionals, Community Members",
            decision_mandate="Staying informed on industry trends with curated expert commentary",
            cognitive_load="Editorial Reading (3-5m)",
            technical_depth="Engaging, Expert-Curated",
            primary_question="What are the essential industry developments this week and what do they mean?",
        ),
        communication_goal=CommunicationGoal(
            objective="Deliver high-retention editorial value and build trusted subscriber affinity",
            desired_mindset_shift="Feeling well-informed and ahead of industry peers",
            action_or_decision="Share digest with colleagues, click through deep dives",
            engagement_type="Subscriber-Editorial",
        ),
        native_structure=[
            "Opening Note",
            "Major Developments",
            "Analysis",
            "Key Takeaways",
            "Closing Commentary",
        ],
        reasoning_path=["Warm Editorial Opening", "Curated Major Developments", "Deep-Dive Editorial Analysis", "Actionable Takeaway Bullets", "Sign-Off Closing Commentary"],
        narrative_strategy="Engaging newsletter editor voice (like Stratechery or Morning Brew). Analytical yet approachable.",
        writing_blueprint=WritingBlueprint(
            writing_style="Substack/Editorial Newsletter",
            sentence_cadence="Engaging, rhythmic narrative voice.",
            vocabulary_register="Knowledgeable industry insider.",
            mandatory_sections=["Opening Note", "Major Developments", "Analysis", "Key Takeaways", "Closing Commentary"],
            forbidden_tropes=[
                "Never write like a dry bureaucratic report.",
                "Never use generic greetings like 'Dear Reader'.",
            ],
            formatting_requirements=[
                "Include an engaging Opening Note setting the theme.",
                "Provide thoughtful commentary on Major Developments.",
            ],
        ),
        selected_insight_ids=[n.id for n in graph.insight_nodes[:4]],
    )


def plan_technical_report(graph: EvidenceAndInsightGraph) -> ArtifactPlan:
    return ArtifactPlan(
        artifact_type="technical_report",
        audience_model=AudienceModel(
            persona="Engineers, System Architects, Researchers, Technical Analysts",
            decision_mandate="Technical validation, architectural implementation, empirical evaluation",
            cognitive_load="Deep Technical Study (15-20m)",
            technical_depth="Deep Empirical & Methodological Rigor",
            primary_question="What are the exact technical specifications, verified metrics, methodologies, and limitations?",
        ),
        communication_goal=CommunicationGoal(
            objective="Provide an unassailable empirical analysis with rigorous methodology and explicit limitations",
            desired_mindset_shift="From theoretical assumptions to verified technical reality",
            action_or_decision="Implement architectural changes or validate engineering roadmap",
            engagement_type="Technical-Validation",
        ),
        native_structure=[
            "Abstract",
            "Introduction",
            "Methodology",
            "Analysis",
            "Findings",
            "Limitations",
            "Conclusion",
        ],
        reasoning_path=["Abstract Summary", "Introduction & Scope", "Methodology & Instrumentation", "Quantitative Analysis", "Empirical Findings", "Systemic Limitations & Edge Cases", "Technical Conclusion"],
        narrative_strategy="Peer-reviewed technical whitepaper/report. Strict prioritization of evidence, metrics, and methodology over storytelling.",
        writing_blueprint=WritingBlueprint(
            writing_style="IEEE/ACM Technical Whitepaper",
            sentence_cadence="Precise, unambiguous, passive/active scientific statements.",
            vocabulary_register="Engineering, systems, and empirical research vocabulary.",
            mandatory_sections=["Abstract", "Introduction", "Methodology", "Analysis", "Findings", "Limitations", "Conclusion"],
            forbidden_tropes=[
                "Never use marketing hype, buzzwords, or hand-waving claims.",
                "Never omit the Limitations section.",
                "Never assert conclusions without referencing methodology and findings.",
            ],
            formatting_requirements=[
                "Include a concise formal Abstract at the top.",
                "Detail exact parameters and metrics in the Analysis and Findings sections.",
                "Explicitly document technical Limitations.",
            ],
        ),
        selected_insight_ids=[n.id for n in graph.insight_nodes],
    )


def plan_generic_fallback(artifact_type: str, graph: EvidenceAndInsightGraph) -> ArtifactPlan:
    """Fallback planner for additional formats (advisory, policy_memo, presentation, infographic, video_package)."""
    return ArtifactPlan(
        artifact_type=artifact_type,
        audience_model=AudienceModel(
            persona=f"Specialized Stakeholders for {artifact_type.replace('_', ' ').title()}",
            decision_mandate=f"Domain-specific decision support for {artifact_type}",
            cognitive_load="Targeted Format Review",
            technical_depth="Domain-Appropriate",
            primary_question=f"What are the key findings and requirements for {artifact_type}?",
        ),
        communication_goal=CommunicationGoal(
            objective=f"Deliver specialized {artifact_type.replace('_', ' ')} asset",
            desired_mindset_shift="Comprehensive domain understanding",
            action_or_decision="Execute domain recommendations",
            engagement_type="Domain-Specialized",
        ),
        native_structure=["Overview", "Key Analysis", "Operational Directives", "Next Steps"],
        reasoning_path=["Context", "Analysis", "Directives", "Execution"],
        narrative_strategy="Audience-aligned specialized communication.",
        writing_blueprint=WritingBlueprint(
            writing_style="Domain-Specific Blueprint",
            sentence_cadence="Clear, structured phrasing.",
            vocabulary_register="Specialized professional lexicon.",
            mandatory_sections=["Overview", "Key Analysis", "Operational Directives", "Next Steps"],
            forbidden_tropes=["Never use generic summary templates."],
            formatting_requirements=["Maintain clean section hierarchy."],
        ),
        selected_insight_ids=[n.id for n in graph.insight_nodes[:4]],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Planner Dispatcher
# ─────────────────────────────────────────────────────────────────────────────

PLANNER_MAP = {
    "linkedin_post": plan_linkedin_post,
    "twitter_x": plan_twitter_x,
    "executive_summary": plan_executive_summary,
    "executive_briefing": plan_executive_briefing,
    "strategic_memo": plan_strategic_memo,
    "press_release": plan_press_release,
    "newsletter": plan_newsletter,
    "technical_report": plan_technical_report,
    "research_report": plan_technical_report,
}


def create_artifact_plan(artifact_type: str, graph: EvidenceAndInsightGraph) -> ArtifactPlan:
    """
    Constructs an ArtifactPlan tailored strictly to the requested artifact type.
    """
    planner_fn = PLANNER_MAP.get(artifact_type)
    if planner_fn:
        return planner_fn(graph)
    return plan_generic_fallback(artifact_type, graph)

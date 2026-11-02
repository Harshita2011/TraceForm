"""Shared format contracts used by admission, presets, generation checks and the UI."""
import re
from pydantic import BaseModel, Field
from agents.generators.blueprints import get_blueprint

FORMAT_LABELS = {
 'executive_summary':'Executive summary','executive_briefing':'Leadership briefing',
 'research_report':'Research report','presentation':'Presentation outline','linkedin_post':'LinkedIn post',
 'press_release':'Press release','strategic_memo':'Strategy memo','advisory':'Advisory memo',
 'policy_memo':'Policy memo','newsletter':'Newsletter','twitter_x':'X thread',
 'infographic':'Infographic outline','video_package':'Video script'}

class OutputEnvelope(BaseModel):
    content: str = Field(min_length=1)
    facts_used: list[dict] = Field(default_factory=list)
    key_insights: list[str] = Field(default_factory=list)
    format_specific_metadata: dict = Field(default_factory=dict)

def format_catalog():
    return [{'id':key,'label':label,'sections':get_blueprint(key).sections,
             'version':get_blueprint(key).blueprint_version_tag,
             'deliverable':'Written outline' if key in ('presentation','infographic') else
                           'Written script' if key=='video_package' else 'Written document',
             'word_target':get_blueprint(key).word_limit} for key,label in FORMAT_LABELS.items()]

def validate_format(output_type, content, sections=()):
    """Headings must stand alone and contain a body; a mentioned title is insufficient."""
    required = list(dict.fromkeys(get_blueprint(output_type).sections + list(sections)))
    headings = list(re.finditer(r'(?m)^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$',content))
    found = {}
    for i, match in enumerate(headings):
        end=next((h.start() for h in headings[i+1:] if len(h.group(1))<=len(match.group(1))),len(content))
        body=re.sub(r'(?m)^\s*#{1,6}\s+.*$','',content[match.end():end]).strip()
        found[match.group(2).strip().casefold()] = body
    issues=[]
    for title in required:
        body=found.get(title.casefold())
        if body is None: issues.append(f'Missing heading: {title}')
        elif not body or 'source does not provide enough information to complete this section' in body.lower():
            issues.append(f'Section needs content: {title}')
    return {'version':get_blueprint(output_type).blueprint_version_tag,'passed':not issues,
            'required_sections':required,'issues':issues}

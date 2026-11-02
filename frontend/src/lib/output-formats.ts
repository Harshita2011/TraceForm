import { OutputType } from './types';
export const OUTPUT_FORMATS: { id: OutputType; label: string; description: string; preview: string }[] = [
  { id: 'executive_summary', label: 'Executive summary', description: 'The key findings, in a quick read.', preview: 'Summary → Key findings → Recommendations' },
  { id: 'executive_briefing', label: 'Leadership briefing', description: 'Decisions and risks for your leadership team.', preview: 'Business impact → Risks → Decision required' },
  { id: 'research_report', label: 'Research report', description: 'A structured look at the evidence.', preview: 'Background → Method → Findings → Limitations' },
  { id: 'presentation', label: 'Presentation', description: 'A structured outline for your next slide deck.', preview: 'Opening → Key points → Evidence → Next steps' },
  { id: 'linkedin_post', label: 'LinkedIn post', description: 'A focused story for your professional network.', preview: 'Hook → Story → Takeaway → Call to action' },
  { id: 'press_release', label: 'Press release', description: 'A news announcement grounded in your source.', preview: 'Headline → Announcement → Details → Background' },
  { id: 'strategic_memo', label: 'Strategy memo', description: 'Options, tradeoffs, and a course of action.', preview: 'Context → Options → Tradeoffs → Recommendation' },
  { id: 'advisory', label: 'Advisory memo', description: 'Practical guidance on risks and next steps.', preview: 'Issue → Assessment → Guidance' },
  { id: 'policy_memo', label: 'Policy memo', description: 'Explain implications for policy and governance.', preview: 'Issue → Evidence → Implications → Actions' },
  { id: 'newsletter', label: 'Newsletter', description: 'An accessible digest for your subscribers.', preview: 'Opening → Highlights → What it means' },
  { id: 'twitter_x', label: 'X thread', description: 'Short, connected posts with a clear takeaway.', preview: 'Hook → Key points → Closing' },
  { id: 'infographic', label: 'Infographic outline', description: 'A written visual plan; no image is generated.', preview: 'Main message → Data points → Layout notes' },
  { id: 'video_package', label: 'Video script', description: 'A script and scene plan; no video is generated.', preview: 'Opening → Narration → Scene directions' },
];
export const outputLabel = (id: string) => OUTPUT_FORMATS.find(f => f.id === id)?.label ?? id.replace(/_/g, ' ');
export const documentName = (name = 'Untitled document') => name.split(/[\\/]/).pop()?.replace(/_[0-9a-f]{8}(\.[a-zA-Z0-9]+)$/, '$1') || 'Untitled document';

"""Pure helpers shared by the API, worker and exporters."""
import hashlib
import json
import re


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def payload_hash(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str))


def json_object(raw):
    value = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip())
    return json.loads(value)


def sections(content):
    """Markdown heading sections, with code-point offsets and nested sections included."""
    headings = []
    offset = 0
    in_code = False
    for line in content.splitlines(keepends=True):
        if re.match(r'^\s*(```|~~~)', line):
            in_code = not in_code
        match = None if in_code else re.match(r'^(#{1,6})\s+(.+?)\s*\n?$', line)
        if match:
            headings.append({'title': match[2], 'level': len(match[1]), 'start': offset,
                             'body_start': offset + len(line)})
        offset += len(line)
    for i, item in enumerate(headings):
        item['end'] = next((h['start'] for h in headings[i+1:] if h['level'] <= item['level']), len(content))
        item['id'] = digest(f"{digest(content)}:{item['start']}:{item['end']}")[:24]
    return headings


def replace_section(content, section_id, replacement):
    item = next((s for s in sections(content) if s['id'] == section_id), None)
    if not item:
        raise ValueError('The section changed. Choose it again from the saved version.')
    if any(s['level'] <= item['level'] for s in sections(replacement)):
        raise ValueError('The provider returned headings outside the selected section. No version was changed.')
    if not replacement.strip():
        raise ValueError('The provider returned an empty section. No version was changed.')
    return content[:item['body_start']] + replacement.rstrip('\n') + '\n' + content[item['end']:]


def policy_hash():
    from orchestrator.runtime import plan_fingerprint
    return plan_fingerprint()


def review_policy(source):
    """Compliance results also depend on the source sensitivity decision."""
    return payload_hash([policy_hash(), str(source.sensitivity), str(source.sensitivity_source), source.sensitivity_confidence])

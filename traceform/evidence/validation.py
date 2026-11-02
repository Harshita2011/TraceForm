"""Deterministic evidence checks. An exact quote proves location, not semantic truth."""
import hashlib
import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation, Inexact, localcontext

VERSION = 'evidence:1.0'
BLOCKING_REVIEWERS = {'style_reviewer', 'fact_reviewer', 'compliance_reviewer',
                     'format_reviewer', 'evidence_reviewer', 'correction_reviewer', 'source_conflict_reviewer'}
LIMITATION = ('Anchor checks validate recorded references, not every statement or factual accuracy. '
              'Semantic support is assessed separately by model reviewers and can be wrong.')
NUMBER = re.compile(r'(?<![\w.])-?\d+(?:,\d{3})*(?:\.\d+)?(?:%|[bBmMkK](?!\w))?(?!\d|\.\d)')
INSTRUCTION = re.compile(r'ignore (?:all |the |any )?(?:previous|prior|system) instructions|'
                         r'(?:system|developer)\s*prompt|you (?:must|should) (?:output|respond)|'
                         r'override (?:the )?(?:rules|instructions)', re.I)


def version(text):
    if isinstance(text, dict):
        text = json.dumps(text, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256((text or '').encode('utf8')).hexdigest()


def numbers(text):
    return {m.group().replace(',', '') for m in NUMBER.finditer(text or '')}


def occurrences(content, claim):
    if not claim:
        return []
    return [{'start': m.start(), 'end': m.end()} for m in re.finditer(re.escape(claim), content)]


def has_visible_label(item, claim, default_labels):
    if re.match(r'^(?:' + default_labels + r')\s*:', claim, re.I):
        return True
    # Translated labels remain visible in the requested language. Their meaning is
    # assessed by the language/fact reviewers; this check only proves the marker exists.
    label = item.get('label')
    if not isinstance(label, str) or not 1 <= len(label.strip()) <= 40:
        return False
    label = label.strip()
    if not all(unicodedata.category(c)[0] in {'L', 'M'} or c in ' -' for c in label):
        return False
    if label.casefold() in {'fact', 'verified', 'approved', 'source fact'}:
        return False
    return bool(re.match(re.escape(label) + r'\s*:', claim, re.I))


def anchor(item, source_text, source_id, source_version):
    filename = None
    if isinstance(source_text, dict):
        named_id = str(item.get('source_id') or '')
        document = source_text.get(named_id)
        if document is None:
            linked = anchor(item, None, named_id or None, item.get('source_version'))
            linked['reason'] = 'Select a recorded source document for this reference; no substitute document was used.'
            return linked
        filename = document.get('filename')
        source_text, source_id = document['text'], named_id
        source_version = document['source_version']
    quote, start, end = item.get('source_span'), item.get('start_char'), item.get('end_char')
    reason = None
    if source_text is None:
        reason = 'The stored source is unavailable.'
    elif item.get('source_id') and str(item['source_id']) != str(source_id):
        reason = 'This reference names a different source document.'
    elif item.get('source_version') and item['source_version'] != source_version:
        reason = 'The source text has changed since this reference was recorded.'
    elif not isinstance(quote, str) or not quote.strip():
        reason = 'A verbatim source passage is missing.'
    elif (type(start) is not int or type(end) is not int or
          not 0 <= start < end <= len(source_text) or source_text[start:end] != quote):
        reason = 'The recorded offsets do not match the exact source passage. No substitute passage was selected.'
    elif INSTRUCTION.search(quote):
        reason = 'This passage contains instruction-like text. Treat it as document data and review it manually.'
    identifier = version(f'{source_id}:{source_version}:{start}:{end}:{quote}')
    return {'id': 'span_' + identifier, 'source_id': str(source_id) if source_id else None, 'filename': filename,
            'source_version': source_version, 'text': quote if isinstance(quote, str) else '',
            'start': start if type(start) is int else None, 'end': end if type(end) is int else None,
            'resolution': item.get('anchor_resolution', 'recorded_offsets'),
            'model_start': item.get('model_start_char'), 'model_end': item.get('model_end_char'),
            'status': 'matched' if reason is None else 'invalid', 'reason': reason}


def calculation_check(item, source_text, source_id, source_version):
    calculation = item.get('calculation') or {}
    if not isinstance(calculation, dict):
        return [], 'Calculation metadata is malformed.'
    inputs = calculation.get('inputs', [])
    if not isinstance(inputs, list) or not 2 <= len(inputs) <= 10:
        return [], 'A calculation needs 2–10 cited inputs.'
    anchors, values = [], []
    try:
        for operand in inputs:
            if not isinstance(operand, dict):
                raise ValueError()
            linked = anchor(operand, source_text, source_id, source_version)
            anchors.append(linked)
            raw = str(operand.get('value', ''))
            if len(raw) > 64 or raw.endswith('%') or raw not in numbers(linked['text']) or linked['status'] != 'matched':
                raise ValueError()
            value = Decimal(raw.rstrip('%'))
            if not value.is_finite():
                raise ValueError()
            values.append(value)
        raw_result = str(calculation.get('result', ''))
        if len(raw_result) > 64 or raw_result not in numbers(item.get('claim', '')):
            raise ValueError()
        if raw_result.endswith('%') and calculation.get('operation') != 'percent_change':
            raise ValueError()
        result = Decimal(raw_result.rstrip('%'))
        with localcontext() as ctx:
            # At most ten 64-character operands: finite sums/products fit within
            # this precision. Non-terminating division must fail, never round.
            ctx.prec = 1024
            ctx.traps[Inexact] = True
            operation = calculation.get('operation')
            if operation == 'sum':
                expected = sum(values)
            elif operation == 'difference' and len(values) == 2:
                expected = values[0] - values[1]
            elif operation == 'product':
                expected = Decimal(1)
                for value in values:
                    expected *= value
            elif operation == 'ratio' and len(values) == 2:
                expected = values[0] / values[1]
            elif operation == 'percent_change' and len(values) == 2:
                expected = (values[1] - values[0]) / values[0] * 100
            else:
                raise ValueError()
            # Exact decimal result only: no hidden rounding tolerance or arbitrary eval.
            if not result.is_finite() or expected != result:
                raise ValueError()
        if not numbers(item.get('claim', '')).issubset({str(x.get('value', '')) for x in inputs} | {raw_result}):
            raise ValueError()
        return anchors, None
    except (ValueError, InvalidOperation, ArithmeticError, AttributeError):
        return anchors, 'The calculation, cited input values, or stated result could not be validated.'


def validate_evidence(content, citations, source_text, source_id, reviews=None):
    content = content or ''
    digest = version(source_text)
    claims, findings = [], []
    for index, item in enumerate(citations or []):
        if not isinstance(item, dict):
            item = {}
        claim = item.get('claim') if isinstance(item.get('claim'), str) else ''
        kind = item.get('claim_type', 'fact')
        if kind not in {'fact', 'calculation', 'recommendation', 'unsupported'}:
            kind = 'unsupported'
        positions = occurrences(content, claim)
        reasons, anchors = [], []
        if not positions:
            reasons.append('The recorded claim is not an exact excerpt of this output.')
        if kind == 'recommendation':
            if not has_visible_label(item, claim, 'recommendation|suggestion|proposed action'):
                reasons.append('Add a visible proposal label such as “Recommendation:”; record translated labels in the reference metadata.')
        elif kind == 'calculation':
            if not has_visible_label(item, claim, 'calculation|derived calculation'):
                reasons.append('Add a visible calculation label such as “Calculation:”; record translated labels in the reference metadata.')
            anchors, error = calculation_check(item, source_text, source_id, digest)
            if error:
                reasons.append(error)
        elif kind == 'fact':
            recorded = item.get('anchors') or [item]
            if not isinstance(recorded, list) or not 1 <= len(recorded) <= 8 or any(not isinstance(a, dict) for a in recorded):
                recorded = [item]
            anchors = [anchor(a, source_text, source_id, digest) for a in recorded]
            for linked in anchors:
                if linked['reason']:
                    reasons.append(linked['reason'])
                if numbers(claim) - numbers(linked['text']):
                    reasons.append('This claim introduces a number, date or percentage absent from its cited passage.')
        else:
            reasons.append('This statement is explicitly unsupported; remove it or supply evidence.')
        claim_id = 'claim_' + version(f'{digest}:{index}:{claim}')
        entry = {'id': claim_id, 'claim': claim, 'kind': kind, 'output_spans': positions,
                 'anchors': anchors, 'status': 'invalid' if reasons else 'matched', 'reasons': reasons,
                 'fact_source_id': item.get('fact_source_id')}
        calculation = item.get('calculation')
        if kind == 'calculation' and isinstance(calculation, dict):
            operands = calculation.get('inputs')
            entry['calculation'] = {
                'operation': str(calculation.get('operation', ''))[:40],
                'inputs': [str(o.get('value', ''))[:64] for o in operands[:10] if isinstance(o, dict)] if isinstance(operands, list) else [],
                'result': str(calculation.get('result', ''))[:64]}
        claims.append(entry)
        if reasons:
            message = ' '.join(reasons)
            findings.append({'id': version(claim_id + message), 'reviewer': 'evidence', 'claim': claim,
                             'message': message, 'output_spans': positions, 'claim_id': claim_id})
    if not claims:
        findings.append({'id': 'missing-references', 'reviewer': 'evidence', 'claim': '',
                         'message': 'No claim references were recorded. This output needs an evidence review.',
                         'output_spans': [], 'claim_id': None})
    for review in reviews or []:
        if (not isinstance(review, dict) or not review.get('reviewer_name') or
                review.get('passed') is True or review.get('reviewer_name') == 'evidence_reviewer'):
            continue
        details = review.get('details') if isinstance(review.get('details'), dict) else {}
        messages = []
        for key in ('failing_claims', 'issues', 'violations', 'missing_sections'):
            values = details.get(key) or []
            if isinstance(values, list):
                for value in values:
                    if isinstance(value, dict):
                        messages.append((str(value.get('claim') or value.get('text') or ''),
                                         str(value.get('reason') or value.get('message') or value)))
                    else:
                        messages.append((str(value), str(value)))
        if not messages:
            messages = [('', str(details.get('reasoning') or details.get('error') or 'This check needs attention.'))]
        for claim, message in messages:
            findings.append({'id': version(review['reviewer_name'] + claim + message),
                             'reviewer': review['reviewer_name'].replace('_reviewer', ''),
                             'claim': claim, 'message': message, 'output_spans': occurrences(content, claim),
                             'claim_id': None})
    total = sum(len(c['anchors']) for c in claims)
    matched = sum(a['status'] == 'matched' for c in claims for a in c['anchors'])
    return {'version': VERSION, 'source_id': str(source_id) if source_id else None, 'source_version': digest,
            'content_version': version(content), 'passed': bool(claims) and all(c['status'] == 'matched' for c in claims),
            'claims': claims, 'findings': findings, 'anchors_matched': matched, 'anchors_total': total,
            'source_documents': [{k: v for k, v in doc.items() if k != 'text'} for doc in source_text.values()] if isinstance(source_text, dict) else [],
            'limitation': LIMITATION}


def assurance(evidence, reviews, overridden=False):
    recorded = {}
    for review in reviews or []:
        if isinstance(review, dict) and review.get('reviewer_name'):
            name = review['reviewer_name']
            recorded[name] = recorded.get(name, True) and review.get('passed') is True
    required = {'style_reviewer', 'fact_reviewer', 'compliance_reviewer', 'format_reviewer', 'evidence_reviewer'}
    if len(evidence.get('source_documents', [])) > 1:
        required.add('source_conflict_reviewer')
    if overridden:
        return 'overridden'
    if not evidence['passed'] or any(not passed for name, passed in recorded.items() if name in BLOCKING_REVIEWERS):
        return 'needs_review'
    if not required.issubset(recorded):
        return 'unreviewed'
    return 'checks_passed'

import json
from types import SimpleNamespace
from uuid import UUID
from sqlalchemy import select
from db.models import GenerationDocument, Source
from schemas.enums import SensitivityLevel, SensitivitySource
from evidence.validation import version

MAX_DOCUMENTS = 8
MAX_COMBINED_CHARACTERS = 200000
SENSITIVITY_ORDER = ['public', 'internal', 'restricted', 'confidential']


class SourceUnavailable(ValueError):
    pass


def value(item):
    return item.value if hasattr(item, 'value') else item


def manifest_hash(documents):
    return version(json.dumps([{k: doc[k] for k in ('id','source_version','sensitivity','sensitivity_source','sensitivity_confidence')}
                               for doc in documents], sort_keys=True))


def metadata(row):
    return {'id': str(row.source_id), 'filename': row.filename, 'source_version': row.source_version,
            'sensitivity': row.sensitivity, 'sensitivity_source': row.sensitivity_source,
            'sensitivity_confidence': row.sensitivity_confidence}


async def selected_sources(db, ids, lock=False):
    from sqlalchemy import update
    if not 1 <= len(ids) <= MAX_DOCUMENTS or len(set(ids)) != len(ids):
        raise SourceUnavailable(f'Choose 1–{MAX_DOCUMENTS} distinct source documents.')
    result = []
    # Fixed lock order avoids deadlocks when concurrent selections overlap.
    for source_id in sorted(ids, key=str):
        if lock:
            await db.execute(update(Source).where(Source.id == source_id).values(filename=Source.filename))
        source = await db.get(Source, source_id, populate_existing=True)
        from api.routes.sources import usable
        if not source or not usable(source):
            raise SourceUnavailable('A selected source is unavailable, removed or reference-only. Refresh the source selection.')
        result.append(source)
    if sum(len(s.extracted_text) for s in result) > MAX_COMBINED_CHARACTERS:
        raise SourceUnavailable('Selected sources exceed 200,000 characters. Choose fewer or smaller documents; no text was truncated.')
    return sorted(result, key=lambda s: ids.index(s.id))


async def save_manifest(db, generation_id, sources):
    rows = []
    for position, source in enumerate(sources):
        row = GenerationDocument(generation_id=generation_id, source_id=source.id, position=position,
            filename=source.filename or 'Text source', text=source.extracted_text, source_version=version(source.extracted_text),
            sensitivity=value(source.sensitivity), sensitivity_source=value(source.sensitivity_source),
            sensitivity_confidence=source.sensitivity_confidence)
        db.add(row); rows.append(row)
    await db.flush()
    return rows


async def document_rows(db, generation_id):
    return list((await db.execute(select(GenerationDocument).where(GenerationDocument.generation_id == generation_id)
                                 .order_by(GenerationDocument.position))).scalars().all())


async def assert_current(db, generation_id):
    rows = await document_rows(db, generation_id)
    if not rows: return
    sources = (await db.execute(select(Source).where(Source.id.in_([r.source_id for r in rows]))
                               .execution_options(populate_existing=True))).scalars().all()
    live = {s.id: s for s in sources}
    for row in rows:
        source = live.get(row.source_id)
        if (not source or source.deleted_at or version(source.extracted_text) != row.source_version or
            value(source.sensitivity) != row.sensitivity or value(source.sensitivity_source) != row.sensitivity_source or
            source.sensitivity_confidence != row.sensitivity_confidence):
            raise SourceUnavailable('A linked source changed or was removed. Choose current sources and analyze them again.')


async def load_context(db, generation):
    source = await db.get(Source, generation.source_id)
    rows = await document_rows(db, generation.id)
    if not rows: return source
    await assert_current(db, generation.id)
    documents = [metadata(r) for r in rows]
    dominant = max(rows, key=lambda r: SENSITIVITY_ORDER.index(r.sensitivity))
    text = rows[0].text if len(rows) == 1 else json.dumps(
        [{'id': str(r.source_id), 'version': r.source_version, 'text': r.text} for r in rows], ensure_ascii=False)
    return SimpleNamespace(id=source.id, filename=' + '.join(r.filename for r in rows), extracted_text=text,
        sensitivity=SensitivityLevel(dominant.sensitivity), sensitivity_source=SensitivitySource(dominant.sensitivity_source),
        sensitivity_confidence=dominant.sensitivity_confidence, deleted_at=None,
        source_documents=documents, documents={str(r.source_id): {'text': r.text, **metadata(r)} for r in rows},
        context_version=manifest_hash(documents),
        conflicts=(generation.synthesis or {}).get('conflicts', []),
        evidence_text={str(r.source_id): {'text': r.text, **metadata(r)} for r in rows} if len(rows) > 1 else rows[0].text)


async def copy_manifest(db, parent_id, generation_id):
    for row in await document_rows(db, parent_id):
        db.add(GenerationDocument(generation_id=generation_id, **{key: getattr(row, key) for key in
            ('source_id','position','filename','text','source_version','sensitivity','sensitivity_source','sensitivity_confidence')}))


def evidence_text(source):
    return getattr(source, 'evidence_text', source.extracted_text) if source else None

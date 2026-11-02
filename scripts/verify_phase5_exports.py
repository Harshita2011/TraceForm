"""Generate deterministic export fixtures using the application renderer, then render every PDF page."""
from pathlib import Path
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'traceform'))
from revisions.exports import docx_export, pptx_export, convert_document


def main():
    output = ROOT / '.runtime/phase5-exports'
    output.mkdir(parents=True, exist_ok=True)
    for prefix in ['document', 'slides']:
        for page in output.glob(prefix + '-[0-9][0-9].png'):
            assert page.resolve().parent == output.resolve()
            page.unlink()
    content = '# Layout and Unicode\nA fixture with **bold emphasis**, *italic text*, and `inline code`.\n\n' + \
        'Unicode sample: हिंदी 中文 🧪 café — Ελληνικά.\n\n' + \
        '- First item\n- Second item\n\n3. Preserve this number\n4. Keep this item\n\n' + \
        '| Measure | Description | Value |\n| --- | --- | --- |\n| Beds | Community garden fixture | 6 |\n| Volunteers | Morning shift | 12 |\n\n' + \
        '## Long content\n' + '\n\n'.join(f'Paragraph {i}. ' + 'This is a deterministic export fixture for pagination and text preservation. ' * 5 for i in range(1, 10)) + \
        '\n\n## Long table\n| Item | Notes |\n| --- | --- |\n' + \
        '\n'.join(f'| Row {i} | ' + 'Long table cell text remains readable and editable. ' * 2 + '|' for i in range(1, 12)) + \
        '\n\n## Code sample\n```python\nvalue = 42\nprint(value)\n```\n\nFinal preservation marker: END_OF_PHASE5_FIXTURE.'
    appendix = 'Synthetic fixture only. No real-provider review was performed.\nSource: test fixture\nContent version: export-layout-v1'
    docx = docx_export(content, 'Phase 5 export fixture', 'Saved version · Unreviewed', appendix)
    pptx = pptx_export(content, 'Phase 5 export fixture', 'Saved version · Unreviewed', appendix)
    (output / 'fixture.docx').write_bytes(docx)
    (output / 'fixture.pptx').write_bytes(pptx)
    for kind, binary in [('document', docx), ('slides', pptx)]:
        pdf = convert_document(binary, 'docx' if kind == 'document' else 'pptx')
        (output / (kind + '.pdf')).write_bytes(pdf)
        import pypdfium2 as pdfium
        document = pdfium.PdfDocument(pdf)
        texts = []
        for i, page in enumerate(document):
            texts.append(page.get_textpage().get_text_range())
            page.render(scale=1.2).to_pil().save(output / f'{kind}-{i+1:02}.png')
        assert 'END_OF_PHASE5_FIXTURE' in ''.join(texts)
        (output / (kind + '-text.txt')).write_text('\n'.join(texts), encoding='utf-8')
        print(f'{kind}: {len(document)} pages; final marker preserved', flush=True)
    (output / 'fixture.md').write_text(content, encoding='utf-8')


if __name__ == '__main__': main()

"""Portable exports with bounded layout, no remote resources and no content truncation."""
from io import BytesIO
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
import threading

_conversion_slot = threading.BoundedSemaphore(1)


def plain(text):
    text = re.sub(r'!?\[([^\]]*)\]\(([^)]+)\)', lambda m: f'{m[1]} ({m[2]})', text)
    text = re.sub(r'\*\*(.+?)\*\*|__(.+?)__', lambda m: m[1] or m[2], text)
    text = re.sub(r'(?<!\w)\*([^*\n]+)\*(?!\w)', r'\1', text)
    return text.replace('`', '')


def blocks(content):
    """Parse our supported Markdown blocks without evaluating HTML or fetching assets."""
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r'^\s*(```|~~~)', line):
            fence = re.match(r'^\s*(```|~~~)', line)[1]
            code = []
            i += 1
            while i < len(lines) and not lines[i].lstrip().startswith(fence):
                code.append(lines[i]); i += 1
            yield 'code', '\n'.join(code)
        elif i + 1 < len(lines) and '|' in line and re.match(r'^\s*\|?\s*:?-{3,}', lines[i+1]):
            rows = [[c.strip() for c in line.strip().strip('|').split('|')]]
            i += 2
            while i < len(lines) and '|' in lines[i] and lines[i].strip():
                rows.append([c.strip() for c in lines[i].strip().strip('|').split('|')]); i += 1
            width = max(len(r) for r in rows)
            yield 'table', [r + [''] * (width - len(r)) for r in rows]
            continue
        elif match := re.match(r'^(#{1,6})\s+(.+)$', line):
            yield 'heading', (len(match[1]), match[2])
        elif match := re.match(r'^\s*([-*+]\s+|\d+[.)]\s+)(.*)$', line):
            yield 'list', (match[1], match[2])
        else:
            yield 'paragraph', line
        i += 1


def text_export(content, title, state, appendix, markdown=False):
    body = content if markdown else '\n'.join(
        ' | '.join(row) if isinstance(row, list) else str(row)
        for kind, value in blocks(content)
        for row in (value if kind == 'table' else [value[1] if kind == 'heading' else ''.join(value) if kind == 'list' else value]))
    return (f'{title}\n{state}\n\n{body}\n' + ('\n' + appendix if appendix else '')).encode('utf-8')


def _runs(paragraph, text):
    for part in re.split(r'(\*\*.+?\*\*|`[^`]+`|\*[^*\n]+\*)', text):
        run = paragraph.add_run(part[2:-2] if part.startswith('**') and part.endswith('**') else
                                part[1:-1] if part.startswith(('`', '*')) and part.endswith(part[0]) else part)
        if part.startswith('**'): run.bold = True
        elif part.startswith('`'): run.font.name = 'Liberation Mono'
        elif part.startswith('*'): run.italic = True


def docx_export(content, title, state, appendix):
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    doc = Document()
    section = doc.sections[0]
    section.top_margin = section.bottom_margin = Inches(.7)
    section.left_margin = section.right_margin = Inches(.8)
    normal = doc.styles['Normal']
    normal.font.name, normal.font.size = 'Noto Sans', Pt(10)
    normal.paragraph_format.space_after = Pt(7)
    normal.paragraph_format.line_spacing = 1.15
    for name in ['Normal', 'Title', 'Subtitle', *[f'Heading {n}' for n in range(1, 7)]]:
        style = doc.styles[name]
        style.font.name = 'Noto Sans'
        style.font.color.rgb = RGBColor.from_string('182025')
        fonts = style.element.get_or_add_rPr().get_or_add_rFonts()
        for attribute in list(fonts.attrib):
            if 'theme' in attribute.lower(): del fonts.attrib[attribute]
        fonts.set(qn('w:eastAsia'), 'Noto Sans CJK SC')
        fonts.set(qn('w:cs'), 'Noto Sans Devanagari')
        for border in list(style.element.iter(qn('w:pBdr'))): border.getparent().remove(border)
    doc.styles['Title'].font.color.rgb = RGBColor(0, 0, 0)
    doc.styles['Title'].font.underline = False
    doc.styles['Title'].font.size = Pt(24)
    doc.styles['Subtitle'].font.size = Pt(10)
    doc.styles['Subtitle'].font.italic = False
    doc.add_paragraph(title, 'Title')
    doc.add_paragraph(state, 'Subtitle')
    for kind, value in blocks(content):
        if kind == 'table':
            table = doc.add_table(rows=0, cols=len(value[0]))
            table.style = 'Table Grid'
            for index, row in enumerate(value):
                table_row = table.add_row()
                table_row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
                cells = table_row.cells
                for cell, text in zip(cells, row):
                    _runs(cell.paragraphs[0], text)
                    if index == 0:
                        for run in cell.paragraphs[0].runs: run.bold = True
                if index == 0:
                    repeat = OxmlElement('w:tblHeader')
                    table.rows[0]._tr.get_or_add_trPr().append(repeat)
            doc.add_paragraph()
        elif kind == 'heading':
            _runs(doc.add_paragraph(style=f'Heading {value[0]}'), value[1])
        elif kind == 'list':
            # Preserve explicit ordinal/bullet markers, including lists starting above one.
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(.18)
            _runs(p, ''.join(value))
        elif kind == 'code':
            for line in value.split('\n'):
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(0)
                r = p.add_run(line); r.font.name = 'Liberation Mono'; r.font.size = Pt(9)
        else:
            if value.strip(): _runs(doc.add_paragraph(), value)
    if appendix:
        heading = doc.add_heading('References and provenance', 1)
        heading.paragraph_format.page_break_before = True
        for line in appendix.splitlines(): doc.add_paragraph(line)
    footer = section.footer.paragraphs[0]
    footer.add_run('TraceForm  •  ')
    field = OxmlElement('w:fldSimple'); field.set(qn('w:instr'), 'PAGE'); footer._p.append(field)
    output = BytesIO(); doc.save(output)
    return output.getvalue()


def convert_document(data, extension='docx', to='pdf'):
    """Headless conversion. Each invocation owns its profile; no shell or remote networking."""
    with _conversion_slot, tempfile.TemporaryDirectory(prefix='traceform-export-') as tmp:
        directory = Path(tmp)
        source = directory / f'document.{extension}'
        source.write_bytes(data)
        output = directory / 'output'; output.mkdir()
        soffice = shutil.which('libreoffice') or shutil.which('soffice')
        if not soffice and os.name == 'nt':
            candidate = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'LibreOffice/program/soffice.exe'
            if candidate.is_file(): soffice = str(candidate)
        name = None
        if soffice:
            cmd = [soffice, '-env:UserInstallation=' + (directory / 'profile').as_uri(), '--headless',
                   '--convert-to', to, '--outdir', str(output), str(source)]
        else:
            docker = shutil.which('docker')
            if not docker and os.name == 'nt':
                candidate = Path('C:/Program Files/Docker/Docker/resources/bin/docker.exe')
                if candidate.is_file(): docker = str(candidate)
            if not docker or os.name != 'nt':
                raise RuntimeError('PDF export needs LibreOffice. Install it or rebuild the documented Docker image.')
            from uuid import uuid4
            name = 'traceform-export-' + uuid4().hex
            cmd = [docker, 'run', '--rm', '--name', name, '--network', 'none', '--cap-drop', 'ALL',
                   '--security-opt', 'no-new-privileges', '--memory', '1g', '--pids-limit', '128',
                   '--mount', f'type=bind,source={directory},target=/export', 'traceform:local',
                   'libreoffice', '-env:UserInstallation=file:///tmp/export-profile', '--headless',
                   '--convert-to', to, '--outdir', '/export/output', f'/export/document.{extension}']
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=90, creationflags=(0x08000000 if os.name == 'nt' else 0))
            target = output / f'document.{to}'
            if result.returncode or not target.is_file():
                raise RuntimeError('Document conversion is unavailable. Install LibreOffice or rebuild and start Docker, then retry.')
            return target.read_bytes()
        except subprocess.TimeoutExpired:
            if name:
                subprocess.run([docker, 'rm', '-f', name], capture_output=True, timeout=15, creationflags=0x08000000)
            raise RuntimeError('Document conversion timed out. Your content is saved; try DOCX or a smaller document.')


def pptx_export(content, title, state, appendix):
    """Editable widescreen outline. Continuation slides preserve every line and table cell."""
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    deck = Presentation(); deck.slide_width = Inches(13.333); deck.slide_height = Inches(7.5)
    heading, pending = title, []

    def slide(label):
        item = deck.slides.add_slide(deck.slide_layouts[6])
        box = item.shapes.add_textbox(Inches(.65), Inches(.4), Inches(12), Inches(.9))
        box.text_frame.word_wrap = True
        p = box.text_frame.paragraphs[0]; p.text = label; p.font.name = 'Noto Sans'; p.font.size = Pt(26); p.font.bold = True; p.line_spacing = Pt(29)
        foot = item.shapes.add_textbox(Inches(.65), Inches(6.98), Inches(12), Inches(.4))
        foot.text_frame.word_wrap = True
        p = foot.text_frame.paragraphs[0]; p.text = f'{state}  •  {len(deck.slides)}'; p.font.size = Pt(9); p.line_spacing = Pt(11)
        return item

    def flush():
        nonlocal pending
        while pending and not pending[0].strip(): pending.pop(0)
        while pending and not pending[-1].strip(): pending.pop()
        while pending:
            chunk, pending = pending[:13], pending[13:]
            item = slide(heading if not getattr(flush, 'continued', False) else heading + ' (continued)')
            box = item.shapes.add_textbox(Inches(.65), Inches(1.55), Inches(12), Inches(5.1))
            frame = box.text_frame; frame.word_wrap = True
            for index, line in enumerate(chunk):
                p = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
                p.text = line; p.font.name = 'Noto Sans'; p.font.size = Pt(18); p.line_spacing = Pt(24); p.space_after = Pt(0)
            flush.continued = True

    for kind, value in list(blocks(content)) + ([('heading', (1, 'References and provenance')), ('paragraph', appendix)] if appendix else []):
        if kind == 'heading':
            flush(); heading = plain(value[1]); flush.continued = False
            if len(heading) > 110:
                pending.extend(textwrap.wrap(heading, width=68, replace_whitespace=False))
                heading = 'Section title'
        elif kind == 'table':
            flush()
            columns = len(value[0]); chars = max(6, 100 // columns)
            # Split long rows into explicit continuation rows; fit by actual wrapped line counts.
            expanded = []
            for row in value:
                wrapped = [textwrap.wrap(plain(cell), width=chars, replace_whitespace=False) or [''] for cell in row]
                for start in range(0, max(map(len, wrapped)), 5):
                    expanded.append(['\n'.join(cell[start:start+5]) for cell in wrapped])
            header, rows = expanded[0], expanded[1:]
            while rows or not getattr(flush, 'table_started', False):
                selected = [header]; capacity = max(1, 17 - max(cell.count('\n') + 1 for cell in header))
                while rows:
                    height = max(cell.count('\n') + 1 for cell in rows[0])
                    if height > capacity and len(selected) > 1: break
                    selected.append(rows.pop(0)); capacity -= height
                    if capacity <= 0: break
                item = slide(heading)
                table = item.shapes.add_table(len(selected), columns, Inches(.65), Inches(1.55), Inches(12), Inches(.4)).table
                for row_index, row in enumerate(selected):
                    table.rows[row_index].height = Inches(.26 * max(cell.count('\n') + 1 for cell in row) + .14)
                    for col, text in enumerate(row):
                        cell = table.cell(row_index, col); cell.text = text
                        for p in cell.text_frame.paragraphs:
                            p.font.name = 'Noto Sans'; p.font.size = Pt(12); p.font.bold = row_index == 0
                            p.font.color.rgb = RGBColor(24, 32, 37)
                flush.table_started = True
                if not rows: break
            flush.table_started = False
        else:
            text = ''.join(value) if kind == 'list' else value
            for line in plain(text).split('\n'):
                pending.extend(textwrap.wrap(line, width=68, replace_whitespace=False) or [''])
    flush()
    if not deck.slides: slide(title)
    output = BytesIO(); deck.save(output)
    return output.getvalue()


MIMES = {'md': 'text/markdown; charset=utf-8', 'txt': 'text/plain; charset=utf-8',
         'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
         'pdf': 'application/pdf', 'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'}


def export(content, title, state, appendix, format):
    if format in {'md', 'txt'}: return text_export(content, title, state, appendix, format == 'md')
    if format == 'pptx': return pptx_export(content, title, state, appendix)
    docx = docx_export(content, title, state, appendix)
    return convert_document(docx) if format == 'pdf' else docx
